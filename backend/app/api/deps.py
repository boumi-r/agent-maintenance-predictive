"""Dépendances FastAPI : settings, session DB, authentification."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Literal

import anthropic
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import decoder_jwt, hacher_cle_api
from app.db.base import maintenant
from app.models import CleApi, Utilisateur
from app.models.enums import Role
from app.services.email.base import EmailProvider


def get_settings_app(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_client_llm(request: Request) -> anthropic.Anthropic:
    client: anthropic.Anthropic = request.app.state.client_llm
    return client


def get_email_provider(request: Request) -> EmailProvider:
    provider: EmailProvider = request.app.state.email_provider
    return provider


SettingsDep = Annotated[Settings, Depends(get_settings_app)]
ClientLLMDep = Annotated[anthropic.Anthropic, Depends(get_client_llm)]
EmailProviderDep = Annotated[EmailProvider, Depends(get_email_provider)]
SessionDep = Annotated[Session, Depends(get_session)]

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Qui appelle : une machine (clé API) ou un utilisateur (JWT). Toujours rattaché à une organisation."""

    organisation_id: int
    type: Literal["api_key", "utilisateur"]
    utilisateur_id: int | None = None
    role: Role | None = None
    cle_api_id: int | None = None


_NON_AUTHENTIFIE = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentification requise (X-API-Key ou Bearer JWT)",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_principal(
    session: SessionDep,
    settings: SettingsDep,
    cle: Annotated[str | None, Security(_api_key_header)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> Principal:
    principal: Principal | None = None
    if cle:
        ligne = session.scalar(select(CleApi).where(CleApi.hash == hacher_cle_api(settings, cle)))
        if ligne is None or not ligne.active:
            raise _NON_AUTHENTIFIE
        ligne.derniere_utilisation = maintenant()
        session.commit()
        principal = Principal(organisation_id=ligne.organisation_id, type="api_key", cle_api_id=ligne.id)
    elif bearer:
        claims = decoder_jwt(settings, bearer.credentials)
        if claims is None:
            raise _NON_AUTHENTIFIE
        utilisateur = session.get(Utilisateur, claims.utilisateur_id)
        if (
            utilisateur is None
            or not utilisateur.actif
            or utilisateur.organisation_id != claims.organisation_id
        ):
            raise _NON_AUTHENTIFIE
        principal = Principal(
            organisation_id=utilisateur.organisation_id,
            type="utilisateur",
            utilisateur_id=utilisateur.id,
            role=utilisateur.role,
        )
    if principal is None:
        raise _NON_AUTHENTIFIE
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def get_utilisateur(principal: PrincipalDep) -> Principal:
    if principal.type != "utilisateur":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux utilisateurs connectés (JWT)")
    return principal


UtilisateurDep = Annotated[Principal, Depends(get_utilisateur)]


def get_admin(principal: UtilisateurDep) -> Principal:
    if principal.role is not Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    return principal


AdminDep = Annotated[Principal, Depends(get_admin)]
