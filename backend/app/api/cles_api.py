"""Clés API machine (ingestion). Stockées hachées ; la clé en clair n'est renvoyée qu'à la création."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import AdminDep, SessionDep, SettingsDep
from app.core.security import generer_cle_api
from app.models import CleApi
from app.schemas.gestion import CleApiCreeeOut, CleApiIn, CleApiOut

router = APIRouter(tags=["cles-api"])


@router.get("/cles-api", response_model=list[CleApiOut])
def lister_cles(principal: AdminDep, session: SessionDep) -> list[CleApi]:
    return list(session.scalars(select(CleApi).where(CleApi.organisation_id == principal.organisation_id)))


@router.post("/cles-api", response_model=CleApiCreeeOut, status_code=status.HTTP_201_CREATED)
def creer_cle(
    donnees: CleApiIn, principal: AdminDep, session: SessionDep, settings: SettingsDep
) -> CleApiCreeeOut:
    generee = generer_cle_api(settings)
    cle = CleApi(
        organisation_id=principal.organisation_id, nom=donnees.nom, prefixe=generee.prefixe, hash=generee.hash
    )
    session.add(cle)
    session.commit()
    return CleApiCreeeOut.model_validate({**CleApiOut.model_validate(cle).model_dump(), "cle": generee.clair})


@router.delete("/cles-api/{cle_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoquer_cle(cle_id: int, principal: AdminDep, session: SessionDep) -> Response:
    cle = session.scalar(
        select(CleApi).where(CleApi.id == cle_id, CleApi.organisation_id == principal.organisation_id)
    )
    if cle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clé introuvable")
    cle.active = False
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
