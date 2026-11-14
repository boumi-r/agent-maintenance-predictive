from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import creer_jwt, decoder_jwt, hacher_cle_api
from app.models import CleApi, Utilisateur
from app.models.enums import Role
from tests.conftest import MOT_DE_PASSE, Org

MOTEURS = "/api/v1/moteurs"


def test_health_sans_auth(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_sans_authentification(client: TestClient, org_a: Org) -> None:
    assert client.get(MOTEURS).status_code == 401


def test_login_mauvais_mot_de_passe(client: TestClient, org_a: Org) -> None:
    r = client.post("/api/v1/auth/login", json={"email": org_a.email, "mot_de_passe": "faux"})
    assert r.status_code == 401


def test_login_email_inconnu(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "x@inconnu.be", "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 401


def test_jwt_valide(client: TestClient, org_a: Org) -> None:
    r = client.get("/api/v1/auth/me", headers=org_a.jwt)
    assert r.status_code == 200
    assert r.json()["email"] == org_a.email
    assert r.json()["role"] == "admin"


def test_jwt_expire(client: TestClient, settings: Settings, org_a: Org) -> None:
    payload = {
        "sub": "1",
        "org": org_a.organisation_id,
        "role": "admin",
        "exp": datetime.now(UTC) - timedelta(1),
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    assert client.get(MOTEURS, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_jwt_mauvaise_signature(client: TestClient, org_a: Org) -> None:
    payload = {
        "sub": "1",
        "org": org_a.organisation_id,
        "role": "admin",
        "exp": datetime.now(UTC) + timedelta(1),
    }
    token = jwt.encode(payload, "autre-secret-tres-long-pour-hs256-xxxxxxxx", algorithm="HS256")
    assert client.get(MOTEURS, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_jwt_org_falsifiee_refusee(client: TestClient, settings: Settings, org_a: Org, org_b: Org) -> None:
    # Jeton signé correctement mais dont l'organisation ne correspond pas à l'utilisateur
    me = client.get("/api/v1/auth/me", headers=org_a.jwt).json()
    token = creer_jwt(settings, me["id"], org_b.organisation_id, Role.ADMIN)
    assert client.get(MOTEURS, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_utilisateur_desactive(client: TestClient, session: Session, org_a: Org) -> None:
    u = session.scalar(select(Utilisateur).where(Utilisateur.email == org_a.email))
    assert u is not None
    u.actif = False
    session.commit()
    assert client.get(MOTEURS, headers=org_a.jwt).status_code == 401


def test_decoder_jwt_invalide(settings: Settings) -> None:
    assert decoder_jwt(settings, "pas-un-jwt") is None


def test_cle_api_valide(client: TestClient, session: Session, org_a: Org) -> None:
    r = client.get(MOTEURS, headers=org_a.machine)
    assert r.status_code == 200
    cle = session.scalar(select(CleApi).where(CleApi.organisation_id == org_a.organisation_id))
    assert cle is not None
    session.refresh(cle)
    assert cle.derniere_utilisation is not None


def test_cle_api_invalide(client: TestClient, org_a: Org) -> None:
    assert client.get(MOTEURS, headers={"X-API-Key": "mai_faux_faux"}).status_code == 401


def test_cle_api_stockee_hachee(session: Session, settings: Settings, org_a: Org) -> None:
    cle = session.scalar(select(CleApi).where(CleApi.organisation_id == org_a.organisation_id))
    assert cle is not None
    assert cle.hash != org_a.cle_api
    assert org_a.cle_api not in cle.hash
    assert cle.hash == hacher_cle_api(settings, org_a.cle_api)


def test_creation_et_revocation_de_cle(client: TestClient, org_a: Org) -> None:
    r = client.post("/api/v1/cles-api", json={"nom": "automate-ligne-2"}, headers=org_a.jwt)
    assert r.status_code == 201
    corps = r.json()
    assert corps["cle"].startswith("mai_")
    assert client.get(MOTEURS, headers={"X-API-Key": corps["cle"]}).status_code == 200
    # La liste ne renvoie jamais la clé en clair
    assert all("cle" not in c for c in client.get("/api/v1/cles-api", headers=org_a.jwt).json())

    assert client.delete(f"/api/v1/cles-api/{corps['id']}", headers=org_a.jwt).status_code == 204
    assert client.get(MOTEURS, headers={"X-API-Key": corps["cle"]}).status_code == 401


def test_cle_api_refusee_sur_gestion(client: TestClient, org_a: Org) -> None:
    assert client.post("/api/v1/sites", json={"nom": "X"}, headers=org_a.machine).status_code == 403
    assert client.get("/api/v1/cles-api", headers=org_a.machine).status_code == 403


def test_technicien_ne_peut_pas_administrer(client: TestClient, org_a: Org) -> None:
    r = client.post(
        "/api/v1/utilisateurs",
        json={"email": "tech@alpha.be", "mot_de_passe": "technicien-solide-123", "role": "technicien"},
        headers=org_a.jwt,
    )
    assert r.status_code == 201
    token = client.post(
        "/api/v1/auth/login", json={"email": "tech@alpha.be", "mot_de_passe": "technicien-solide-123"}
    ).json()["access_token"]
    tech = {"Authorization": f"Bearer {token}"}
    assert client.get(MOTEURS, headers=tech).status_code == 200
    assert client.post("/api/v1/sites", json={"nom": "X"}, headers=tech).status_code == 403
    assert client.post("/api/v1/cles-api", json={"nom": "x"}, headers=tech).status_code == 403
    assert client.get("/api/v1/utilisateurs", headers=tech).status_code == 403


def test_email_utilisateur_unique(client: TestClient, org_a: Org) -> None:
    corps = {"email": org_a.email, "mot_de_passe": "un-autre-mot-de-passe"}
    assert client.post("/api/v1/utilisateurs", json=corps, headers=org_a.jwt).status_code == 409
