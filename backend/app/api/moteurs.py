"""Fiches signalétiques des moteurs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminDep, PrincipalDep, SessionDep, UtilisateurDep
from app.models import Moteur
from app.schemas.gestion import MoteurIn, MoteurOut, MoteurPatch
from app.services import acces

router = APIRouter(tags=["moteurs"])


def moteur_ou_404(session: SessionDep, organisation_id: int, moteur_id: int) -> Moteur:
    moteur = acces.moteur_de_org(session, organisation_id, moteur_id)
    if moteur is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moteur introuvable")
    return moteur


@router.get("/moteurs", response_model=list[MoteurOut])
def lister_moteurs(principal: PrincipalDep, session: SessionDep, site_id: int | None = None) -> list[Moteur]:
    requete = acces.requete_moteurs_org(principal.organisation_id).order_by(Moteur.id)
    if site_id is not None:
        requete = requete.where(Moteur.site_id == site_id)
    return list(session.scalars(requete))


@router.post("/moteurs", response_model=MoteurOut, status_code=status.HTTP_201_CREATED)
def creer_moteur(donnees: MoteurIn, principal: AdminDep, session: SessionDep) -> Moteur:
    if acces.site_de_org(session, principal.organisation_id, donnees.site_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site introuvable")
    moteur = Moteur(**donnees.model_dump())
    session.add(moteur)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Code moteur déjà utilisé sur ce site") from exc
    return moteur


@router.get("/moteurs/{moteur_id}", response_model=MoteurOut)
def lire_moteur(moteur_id: int, principal: PrincipalDep, session: SessionDep) -> Moteur:
    return moteur_ou_404(session, principal.organisation_id, moteur_id)


@router.patch("/moteurs/{moteur_id}", response_model=MoteurOut)
def modifier_moteur(
    moteur_id: int, donnees: MoteurPatch, principal: UtilisateurDep, session: SessionDep
) -> Moteur:
    moteur = moteur_ou_404(session, principal.organisation_id, moteur_id)
    for champ, valeur in donnees.model_dump(exclude_unset=True).items():
        setattr(moteur, champ, valeur)
    session.commit()
    return moteur
