"""Ingestion de mesures (clé API machine ou utilisateur) et analyse par l'agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClientLLMDep, EmailProviderDep, Principal, PrincipalDep, SessionDep, SettingsDep
from app.models import Analyse, Mesure, Moteur
from app.models.enums import SourceMesure
from app.schemas.analyse import (
    AlerteOut,
    AnalyseOut,
    HistoriqueOut,
    LigneHistorique,
    MesureIn,
    MesureOut,
    ResultatAnalyseOut,
)
from app.services import acces
from app.services import analyse as service

router = APIRouter(tags=["mesures et analyses"])


def _source(principal: Principal) -> SourceMesure:
    return SourceMesure.API_KEY if principal.type == "api_key" else SourceMesure.UTILISATEUR


def _moteur(session: SessionDep, principal: Principal, donnees: MesureIn) -> Moteur:
    try:
        return service.resoudre_moteur(
            session, principal.organisation_id, donnees.moteur_id, donnees.moteur_code
        )
    except service.MoteurIntrouvableError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moteur introuvable") from exc
    except service.MoteurAmbiguError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Code moteur présent sur plusieurs sites : utiliser moteur_id"
        ) from exc


@router.post("/mesures", response_model=MesureOut, status_code=status.HTTP_201_CREATED)
def enregistrer_mesure(donnees: MesureIn, principal: PrincipalDep, session: SessionDep) -> Mesure:
    """Stocke une mesure sans appeler l'agent (ingestion haute fréquence)."""
    moteur = _moteur(session, principal, donnees)
    mesure = service.enregistrer_mesure(session, moteur, donnees, _source(principal))
    session.commit()
    return mesure


@router.post("/analyser-moteur", response_model=ResultatAnalyseOut)
def analyser_moteur(
    donnees: MesureIn,
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientLLMDep,
    provider: EmailProviderDep,
) -> ResultatAnalyseOut:
    """Stocke la mesure, applique les règles normatives, puis demande à l'agent d'expliquer.

    Les destinataires d'alerte ne sont jamais fournis ici : ils sont configurés côté serveur.
    """
    moteur = _moteur(session, principal, donnees)
    ctx = service.analyser(session, settings, client, provider, moteur, donnees, _source(principal))
    return ResultatAnalyseOut(
        analyse_id=ctx.analyse.id,
        moteur_id=moteur.id,
        moteur_code=moteur.code,
        niveau_risque=ctx.analyse.niveau_risque,
        diagnostic=ctx.analyse.diagnostic,
        statut=ctx.analyse.statut,
        erreur=ctx.analyse.erreur,
        regles=ctx.regles.en_dict(),
        mesure=MesureOut.model_validate(ctx.mesure),
        alerte=AlerteOut.model_validate(ctx.alerte) if ctx.alerte else None,
        historique_consulte=ctx.historique_consulte,
    )


def _historique(session: SessionDep, moteur: Moteur, limite: int) -> HistoriqueOut:
    lignes = session.execute(
        select(Mesure, Analyse)
        .outerjoin(Analyse, Analyse.mesure_id == Mesure.id)
        .where(Mesure.moteur_id == moteur.id)
        .order_by(Mesure.mesure_le.desc(), Mesure.id.desc())
        .limit(limite)
    ).all()
    return HistoriqueOut(
        moteur_id=moteur.id,
        moteur_code=moteur.code,
        nombre_mesures=len(lignes),
        mesures=[
            LigneHistorique(
                mesure=MesureOut.model_validate(m),
                niveau_risque=a.niveau_risque if a else None,
                analyse_id=a.id if a else None,
            )
            for m, a in lignes
        ],
    )


@router.get("/moteurs/{moteur_id}/historique", response_model=HistoriqueOut)
def historique_par_id(
    moteur_id: int, principal: PrincipalDep, session: SessionDep, limite: int = 100
) -> HistoriqueOut:
    moteur = acces.moteur_de_org(session, principal.organisation_id, moteur_id)
    if moteur is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moteur introuvable")
    return _historique(session, moteur, min(max(limite, 1), 1000))


@router.get("/historique/{moteur_code}", response_model=HistoriqueOut)
def historique_par_code(
    moteur_code: str, principal: PrincipalDep, session: SessionDep, limite: int = 100
) -> HistoriqueOut:
    """Équivalent de l'ancien GET /historique/{moteur_id} du prototype (identifiant = code moteur)."""
    try:
        moteur = service.resoudre_moteur(session, principal.organisation_id, None, moteur_code)
    except service.MoteurIntrouvableError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moteur introuvable") from exc
    except service.MoteurAmbiguError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Code ambigu : utiliser /moteurs/{id}/historique"
        ) from exc
    return _historique(session, moteur, min(max(limite, 1), 1000))


@router.get("/moteurs/{moteur_id}/analyses", response_model=list[AnalyseOut])
def analyses_moteur(moteur_id: int, principal: PrincipalDep, session: SessionDep) -> list[Analyse]:
    if acces.moteur_de_org(session, principal.organisation_id, moteur_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moteur introuvable")
    return list(
        session.scalars(
            select(Analyse).where(Analyse.moteur_id == moteur_id).order_by(Analyse.cree_le.desc()).limit(100)
        )
    )


@router.get("/analyses/{analyse_id}", response_model=AnalyseOut)
def lire_analyse(analyse_id: int, principal: PrincipalDep, session: SessionDep) -> Analyse:
    analyse = acces.analyse_de_org(session, principal.organisation_id, analyse_id)
    if analyse is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analyse introuvable")
    return analyse
