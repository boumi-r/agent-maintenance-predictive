"""Sites et destinataires d'alerte (configurés côté serveur uniquement)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminDep, SessionDep, UtilisateurDep
from app.models import DestinataireAlerte, Site
from app.schemas.gestion import DestinataireIn, DestinataireOut, SiteIn, SiteOut
from app.services import acces

router = APIRouter(tags=["sites"])


def _site_ou_404(session: SessionDep, organisation_id: int, site_id: int) -> Site:
    site = acces.site_de_org(session, organisation_id, site_id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site introuvable")
    return site


@router.get("/sites", response_model=list[SiteOut])
def lister_sites(principal: UtilisateurDep, session: SessionDep) -> list[Site]:
    return list(
        session.scalars(
            select(Site).where(Site.organisation_id == principal.organisation_id).order_by(Site.id)
        )
    )


@router.post("/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def creer_site(donnees: SiteIn, principal: AdminDep, session: SessionDep) -> Site:
    site = Site(organisation_id=principal.organisation_id, **donnees.model_dump())
    session.add(site)
    session.commit()
    return site


@router.get("/destinataires", response_model=list[DestinataireOut])
def lister_destinataires(principal: UtilisateurDep, session: SessionDep) -> list[DestinataireAlerte]:
    return list(
        session.scalars(
            select(DestinataireAlerte).where(DestinataireAlerte.organisation_id == principal.organisation_id)
        )
    )


def _ajouter_destinataire(
    session: SessionDep, organisation_id: int, site_id: int | None, email: str
) -> DestinataireAlerte:
    existant = session.scalar(
        select(DestinataireAlerte).where(
            DestinataireAlerte.organisation_id == organisation_id,
            DestinataireAlerte.site_id.is_(None)
            if site_id is None
            else DestinataireAlerte.site_id == site_id,
            DestinataireAlerte.email == email,
        )
    )
    if existant is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Destinataire déjà configuré")
    dest = DestinataireAlerte(organisation_id=organisation_id, site_id=site_id, email=email)
    session.add(dest)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Destinataire déjà configuré") from exc
    return dest


@router.post("/destinataires", response_model=DestinataireOut, status_code=status.HTTP_201_CREATED)
def ajouter_destinataire_org(
    donnees: DestinataireIn, principal: AdminDep, session: SessionDep
) -> DestinataireAlerte:
    """Destinataire de toutes les alertes de l'organisation."""
    return _ajouter_destinataire(session, principal.organisation_id, None, donnees.email.lower())


@router.post(
    "/sites/{site_id}/destinataires", response_model=DestinataireOut, status_code=status.HTTP_201_CREATED
)
def ajouter_destinataire_site(
    site_id: int, donnees: DestinataireIn, principal: AdminDep, session: SessionDep
) -> DestinataireAlerte:
    _site_ou_404(session, principal.organisation_id, site_id)
    return _ajouter_destinataire(session, principal.organisation_id, site_id, donnees.email.lower())


@router.delete("/destinataires/{dest_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_destinataire(dest_id: int, principal: AdminDep, session: SessionDep) -> Response:
    dest = acces.destinataire_de_org(session, principal.organisation_id, dest_id)
    if dest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destinataire introuvable")
    session.delete(dest)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
