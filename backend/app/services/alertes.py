"""Création, envoi et cycle de vie des alertes.

Les destinataires viennent exclusivement de la configuration serveur (DestinataireAlerte).
Un échec d'envoi est journalisé ET stocké sur l'alerte (envoi_statut / envoi_erreur).
"""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.base import maintenant
from app.models import Alerte, Analyse, DestinataireAlerte, Moteur
from app.models.enums import NiveauRisque, StatutAlerte, StatutEnvoi
from app.services.email.base import EmailProvider
from app.services.email.templates import rendre_alerte

logger = logging.getLogger(__name__)

NIVEAUX_ALERTABLES = frozenset({NiveauRisque.ELEVE, NiveauRisque.CRITIQUE})

TRANSITIONS: dict[StatutAlerte, frozenset[StatutAlerte]] = {
    StatutAlerte.OUVERTE: frozenset(
        {StatutAlerte.ACQUITTEE, StatutAlerte.RESOLUE, StatutAlerte.FAUSSE_ALERTE}
    ),
    StatutAlerte.ACQUITTEE: frozenset({StatutAlerte.RESOLUE, StatutAlerte.FAUSSE_ALERTE}),
    StatutAlerte.RESOLUE: frozenset(),
    StatutAlerte.FAUSSE_ALERTE: frozenset(),
}


class TransitionInvalideError(ValueError):
    pass


def destinataires(session: Session, organisation_id: int, site_id: int) -> list[str]:
    emails = session.scalars(
        select(DestinataireAlerte.email).where(
            DestinataireAlerte.organisation_id == organisation_id,
            DestinataireAlerte.actif.is_(True),
            or_(DestinataireAlerte.site_id.is_(None), DestinataireAlerte.site_id == site_id),
        )
    )
    return sorted(set(emails))


def creer_alerte(
    session: Session, analyse: Analyse, niveau: NiveauRisque, message: str, declenchee_par: str
) -> Alerte:
    alerte = Alerte(
        analyse_id=analyse.id,
        moteur_id=analyse.moteur_id,
        niveau=niveau,
        message=message,
        declenchee_par=declenchee_par,
    )
    session.add(alerte)
    session.flush()
    return alerte


def envoyer_alerte(session: Session, alerte: Alerte, provider: EmailProvider) -> Alerte:
    moteur = session.get(Moteur, alerte.moteur_id)
    if moteur is None:  # pragma: no cover - contrainte FK
        raise ValueError("moteur introuvable")
    site = moteur.site
    dests = destinataires(session, site.organisation_id, site.id)
    alerte.envoi_destinataires = dests
    if not dests:
        alerte.envoi_statut = StatutEnvoi.AUCUN_DESTINATAIRE
        alerte.envoi_erreur = "Aucun destinataire configuré pour ce site ni pour l'organisation"
        logger.warning("alerte=%s non envoyée : aucun destinataire", alerte.id)
        session.commit()
        return alerte

    analyse = session.get(Analyse, alerte.analyse_id)
    regles = [
        f"{r['libelle']} : {r['valeur']} {r['unite']} → {r['niveau']} ({r['seuil']} ; {r['source']})"
        for r in (analyse.resultats_regles if analyse else [])
        if r.get("niveau") not in ("normal", "indetermine")
    ]
    email = rendre_alerte(
        moteur_code=moteur.code,
        site_nom=site.nom,
        niveau=alerte.niveau.value,
        message=alerte.message,
        regles=regles,
    )
    resultat = provider.send(dests, email.sujet, email.html, email.texte)
    if resultat.ok:
        alerte.envoi_statut = StatutEnvoi.ENVOYE
        alerte.envoi_erreur = None
        alerte.envoye_le = maintenant()
        logger.info("alerte=%s envoyée via %s à %s", alerte.id, resultat.provider, dests)
    else:
        alerte.envoi_statut = StatutEnvoi.ECHEC
        alerte.envoi_erreur = resultat.resume_erreur()
        logger.error("alerte=%s échec d'envoi : %s", alerte.id, alerte.envoi_erreur)
    session.commit()
    return alerte


def changer_statut(alerte: Alerte, nouveau: StatutAlerte, utilisateur_id: int | None) -> None:
    if nouveau == alerte.statut:
        return
    if nouveau not in TRANSITIONS[alerte.statut]:
        raise TransitionInvalideError(f"Transition {alerte.statut.value} → {nouveau.value} interdite")
    if nouveau is StatutAlerte.ACQUITTEE:
        alerte.acquittee_par_id = utilisateur_id
        alerte.acquittee_le = maintenant()
    if nouveau in (StatutAlerte.RESOLUE, StatutAlerte.FAUSSE_ALERTE):
        alerte.resolue_le = maintenant()
    alerte.statut = nouveau
