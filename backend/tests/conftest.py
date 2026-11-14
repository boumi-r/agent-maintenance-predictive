"""Fixtures : base SQLite en mémoire, application FastAPI, deux organisations isolées."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from app.models import Moteur
from app.models.enums import ClasseIsolation, GroupeIso20816, TypeFondation
from app.services.bootstrap import creer_organisation

MOT_DE_PASSE = "mot-de-passe-de-test-solide"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        database_url="sqlite://",
        jwt_secret=SecretStr("secret-de-test-suffisamment-long-pour-hs256"),
        api_key_salt=SecretStr("sel-de-test"),
        cors_origins=["https://app.exemple.be"],
        email_provider="console",
        anthropic_api_key=SecretStr("sk-test"),
        rate_limit_analyse="1000/minute",
    )


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def app(settings: Settings, session_factory: sessionmaker[Session]) -> FastAPI:
    return create_app(settings, session_factory)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@dataclass
class Org:
    organisation_id: int
    site_id: int
    moteur_id: int
    cle_api: str
    token: str
    email: str

    @property
    def jwt(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @property
    def machine(self) -> dict[str, str]:
        return {"X-API-Key": self.cle_api}


def _creer_org(client: TestClient, session: Session, settings: Settings, nom: str) -> Org:
    email = f"admin@{nom.lower()}.be"
    creee = creer_organisation(
        session,
        settings,
        nom=nom,
        admin_email=email,
        admin_mot_de_passe=MOT_DE_PASSE,
        destinataire_email=f"maintenance@{nom.lower()}.be",
    )
    moteur = Moteur(
        site_id=creee.site_id,
        code="moteur-A1",
        puissance_kw=75,
        courant_nominal_a=140,
        classe_isolation=ClasseIsolation.F,
        groupe_iso20816=GroupeIso20816.GROUPE_2,
        type_fondation=TypeFondation.RIGIDE,
    )
    session.add(moteur)
    session.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 200, r.text
    return Org(
        creee.organisation_id, creee.site_id, moteur.id, creee.cle_api, r.json()["access_token"], email
    )


@pytest.fixture
def org_a(client: TestClient, session: Session, settings: Settings) -> Org:
    return _creer_org(client, session, settings, "Alpha")


@pytest.fixture
def org_b(client: TestClient, session: Session, settings: Settings) -> Org:
    return _creer_org(client, session, settings, "Beta")
