"""Ingestion des mesures et orchestration d'une analyse (règles → agent → alerte)."""

from __future__ import annotations

import logging

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.orchestrateur import executer_agent
from app.agent.outils import ContexteAnalyse
from app.core.config import Settings
from app.db.base import maintenant
from app.models import Alerte, Analyse, Mesure, Moteur
from app.models.enums import SourceMesure, StatutAlerte, StatutAnalyse
from app.schemas.analyse import ValeursMesureIn
from app.services import acces, alertes
from app.services.electrique import desequilibre_nema
from app.services.email.base import EmailProvider
from app.services.regles import ORDRE_NIVEAUX, FicheMoteur, ValeursMesure, evaluer

logger = logging.getLogger(__name__)


class MoteurIntrouvableError(LookupError):
    pass


class MoteurAmbiguError(LookupError):
    pass


def resoudre_moteur(
    session: Session, organisation_id: int, moteur_id: int | None, code: str | None
) -> Moteur:
    if moteur_id is not None:
        moteur = acces.moteur_de_org(session, organisation_id, moteur_id)
        if moteur is None:
            raise MoteurIntrouvableError
        return moteur
    candidats = acces.moteurs_par_code(session, organisation_id, code or "")
    if not candidats:
        raise MoteurIntrouvableError
    if len(candidats) > 1:
        raise MoteurAmbiguError
    return candidats[0]


def enregistrer_mesure(session: Session, moteur: Moteur, d: ValeursMesureIn, source: SourceMesure) -> Mesure:
    mesure = Mesure(
        moteur_id=moteur.id,
        mesure_le=d.mesure_le or maintenant(),
        source=source,
        tension_ph1_v=d.tension_ph1_v,
        tension_ph2_v=d.tension_ph2_v,
        tension_ph3_v=d.tension_ph3_v,
        courant_ph1_a=d.courant_ph1_a,
        courant_ph2_a=d.courant_ph2_a,
        courant_ph3_a=d.courant_ph3_a,
        vibration_rms_mm_s=d.vibration_rms_mm_s,
        temperature_roulements_c=d.temperature_roulements_c,
        temperature_bobinage_c=d.temperature_bobinage_c,
        observations=d.observations,
        desequilibre_tension_pct=desequilibre_nema(d.tension_ph1_v, d.tension_ph2_v, d.tension_ph3_v),
        desequilibre_courant_pct=desequilibre_nema(d.courant_ph1_a, d.courant_ph2_a, d.courant_ph3_a),
    )
    session.add(mesure)
    session.flush()
    return mesure


def fiche(moteur: Moteur) -> FicheMoteur:
    return FicheMoteur(
        puissance_kw=moteur.puissance_kw,
        courant_nominal_a=moteur.courant_nominal_a,
        classe_isolation=moteur.classe_isolation,
        groupe_iso20816=moteur.groupe_iso20816,
        type_fondation=moteur.type_fondation,
    )


def valeurs(m: Mesure) -> ValeursMesure:
    return ValeursMesure(
        tension_ph1_v=m.tension_ph1_v,
        tension_ph2_v=m.tension_ph2_v,
        tension_ph3_v=m.tension_ph3_v,
        courant_ph1_a=m.courant_ph1_a,
        courant_ph2_a=m.courant_ph2_a,
        courant_ph3_a=m.courant_ph3_a,
        vibration_rms_mm_s=m.vibration_rms_mm_s,
        temperature_roulements_c=m.temperature_roulements_c,
        temperature_bobinage_c=m.temperature_bobinage_c,
    )


def vibration_precedente(session: Session, mesure: Mesure) -> float | None:
    return session.scalar(
        select(Mesure.vibration_rms_mm_s)
        .where(
            Mesure.moteur_id == mesure.moteur_id,
            Mesure.id != mesure.id,
            Mesure.mesure_le <= mesure.mesure_le,
        )
        .order_by(Mesure.mesure_le.desc(), Mesure.id.desc())
        .limit(1)
    )


def _alerte_ouverte_equivalente(session: Session, ctx: ContexteAnalyse) -> Alerte | None:
    """Une alerte encore ouverte/acquittée de niveau ≥ suffit : on ne renvoie pas d'email à chaque mesure."""
    ouvertes = session.scalars(
        select(Alerte).where(
            Alerte.moteur_id == ctx.moteur.id,
            Alerte.statut.in_([StatutAlerte.OUVERTE, StatutAlerte.ACQUITTEE]),
        )
    )
    niveau = ORDRE_NIVEAUX[ctx.regles.niveau_global]
    for a in ouvertes:
        if ORDRE_NIVEAUX.get(a.niveau, -1) >= niveau:
            return a
    return None


def declencher_alerte(ctx: ContexteAnalyse, message: str, par: str) -> Alerte:
    existante = _alerte_ouverte_equivalente(ctx.session, ctx)
    if existante is not None:
        logger.info("analyse=%s : alerte %s déjà ouverte, pas de nouvel envoi", ctx.analyse.id, existante.id)
        ctx.alerte = existante
        return existante
    alerte = alertes.creer_alerte(ctx.session, ctx.analyse, ctx.regles.niveau_global, message, par)
    ctx.alerte = alerte
    return alertes.envoyer_alerte(ctx.session, alerte, ctx.email_provider)


def _message_automatique(ctx: ContexteAnalyse) -> str:
    franchies = [
        f"{r.libelle} = {r.valeur} {r.unite} ({r.niveau.value})"
        for r in ctx.regles.resultats
        if ORDRE_NIVEAUX.get(r.niveau, 0) >= ORDRE_NIVEAUX[ctx.regles.niveau_global]
    ]
    return f"Niveau {ctx.regles.niveau_global.value} détecté par les règles : " + "; ".join(franchies)


def analyser(
    session: Session,
    settings: Settings,
    client: anthropic.Anthropic,
    provider: EmailProvider,
    moteur: Moteur,
    donnees: ValeursMesureIn,
    source: SourceMesure,
) -> ContexteAnalyse:
    mesure = enregistrer_mesure(session, moteur, donnees, source)
    regles = evaluer(fiche(moteur), valeurs(mesure), vibration_precedente(session, mesure))
    analyse = Analyse(
        mesure_id=mesure.id,
        moteur_id=moteur.id,
        niveau_risque=regles.niveau_global,
        resultats_regles=regles.en_dict()["resultats"],
        sources=sorted({r.source for r in regles.resultats if r.source != "—"}),
        version_regles=regles.version,
        versions_modeles={},
        modele_llm=settings.anthropic_model,
    )
    session.add(analyse)
    # Mesure et niveau normatif sont persistés AVANT l'appel LLM : rien n'est perdu si Claude échoue.
    session.commit()

    ctx = ContexteAnalyse(
        session=session,
        moteur=moteur,
        mesure=mesure,
        analyse=analyse,
        regles=regles,
        email_provider=provider,
        declencher=declencher_alerte,
    )
    resultat = executer_agent(client, settings, ctx)
    analyse.diagnostic = resultat.diagnostic
    analyse.statut = StatutAnalyse.OK if resultat.ok else StatutAnalyse.ERREUR_LLM
    analyse.erreur = resultat.erreur

    # Garde-fou déterministe : élevé/critique => alerte, même si l'agent ne l'a pas déclenchée
    if ctx.alerte is None and regles.niveau_global in alertes.NIVEAUX_ALERTABLES:
        declencher_alerte(ctx, _message_automatique(ctx), "regles")
    session.commit()
    return ctx
