"""Alertes (cycle de vie, renvoi) et retours techniciens (vérité terrain pour le réentraînement)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import EmailProviderDep, SessionDep, UtilisateurDep
from app.models import Alerte, Moteur, RetourTechnicien, Site
from app.models.enums import StatutAlerte
from app.schemas.analyse import AlerteOut, AlertePatch, RetourIn, RetourOut
from app.services import acces
from app.services import alertes as service

router = APIRouter(tags=["alertes et retours"])


def _alerte_ou_404(session: SessionDep, organisation_id: int, alerte_id: int) -> Alerte:
    alerte = acces.alerte_de_org(session, organisation_id, alerte_id)
    if alerte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerte introuvable")
    return alerte


@router.get("/alertes", response_model=list[AlerteOut])
def lister_alertes(
    principal: UtilisateurDep, session: SessionDep, statut: StatutAlerte | None = None
) -> list[Alerte]:
    requete = (
        select(Alerte)
        .join(Moteur, Alerte.moteur_id == Moteur.id)
        .join(Site)
        .where(Site.organisation_id == principal.organisation_id)
        .order_by(Alerte.cree_le.desc())
        .limit(200)
    )
    if statut is not None:
        requete = requete.where(Alerte.statut == statut)
    return list(session.scalars(requete))


@router.get("/alertes/{alerte_id}", response_model=AlerteOut)
def lire_alerte(alerte_id: int, principal: UtilisateurDep, session: SessionDep) -> Alerte:
    return _alerte_ou_404(session, principal.organisation_id, alerte_id)


@router.patch("/alertes/{alerte_id}", response_model=AlerteOut)
def changer_statut(
    alerte_id: int, donnees: AlertePatch, principal: UtilisateurDep, session: SessionDep
) -> Alerte:
    alerte = _alerte_ou_404(session, principal.organisation_id, alerte_id)
    try:
        service.changer_statut(alerte, donnees.statut, principal.utilisateur_id)
    except service.TransitionInvalideError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    session.commit()
    return alerte


@router.post("/alertes/{alerte_id}/renvoyer", response_model=AlerteOut)
def renvoyer(
    alerte_id: int, principal: UtilisateurDep, session: SessionDep, provider: EmailProviderDep
) -> Alerte:
    alerte = _alerte_ou_404(session, principal.organisation_id, alerte_id)
    return service.envoyer_alerte(session, alerte, provider)


@router.post("/alertes/{alerte_id}/retours", response_model=RetourOut, status_code=status.HTTP_201_CREATED)
def retour_sur_alerte(
    alerte_id: int, donnees: RetourIn, principal: UtilisateurDep, session: SessionDep
) -> RetourTechnicien:
    alerte = _alerte_ou_404(session, principal.organisation_id, alerte_id)
    retour = RetourTechnicien(
        moteur_id=alerte.moteur_id,
        analyse_id=alerte.analyse_id,
        alerte_id=alerte.id,
        utilisateur_id=principal.utilisateur_id,
        **donnees.model_dump(),
    )
    session.add(retour)
    session.commit()
    return retour


@router.post("/analyses/{analyse_id}/retours", response_model=RetourOut, status_code=status.HTTP_201_CREATED)
def retour_sur_analyse(
    analyse_id: int, donnees: RetourIn, principal: UtilisateurDep, session: SessionDep
) -> RetourTechnicien:
    analyse = acces.analyse_de_org(session, principal.organisation_id, analyse_id)
    if analyse is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analyse introuvable")
    retour = RetourTechnicien(
        moteur_id=analyse.moteur_id,
        analyse_id=analyse.id,
        utilisateur_id=principal.utilisateur_id,
        **donnees.model_dump(),
    )
    session.add(retour)
    session.commit()
    return retour


@router.get("/retours", response_model=list[RetourOut])
def lister_retours(
    principal: UtilisateurDep, session: SessionDep, moteur_id: int | None = None
) -> list[RetourTechnicien]:
    requete = (
        select(RetourTechnicien)
        .join(Moteur, RetourTechnicien.moteur_id == Moteur.id)
        .join(Site)
        .where(Site.organisation_id == principal.organisation_id)
        .order_by(RetourTechnicien.cree_le.desc())
    )
    if moteur_id is not None:
        requete = requete.where(RetourTechnicien.moteur_id == moteur_id)
    return list(session.scalars(requete))
