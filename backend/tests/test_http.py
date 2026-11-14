"""Rate limiting, CORS, configuration et interface statique."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.rate_limit import Limiteur
from app.main import create_app
from tests.conftest import Org
from tests.test_analyse import MESURE_SAINE, FauxClient, FauxProvider, msg, texte


def test_rate_limit_par_organisation(
    settings: Settings, session_factory: sessionmaker[Session], org_a: Org, org_b: Org
) -> None:
    app = create_app(settings.model_copy(update={"rate_limit_analyse": "2/minute"}), session_factory)
    app.state.client_llm = FauxClient(*[msg([texte("ok")], "end_turn") for _ in range(3)])
    app.state.email_provider = FauxProvider()
    client = TestClient(app)

    codes = [
        client.post("/api/v1/analyser-moteur", json=MESURE_SAINE, headers=org_a.machine).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]
    r = client.post("/api/v1/analyser-moteur", json=MESURE_SAINE, headers=org_a.jwt)
    assert r.status_code == 429  # même organisation, autre mode d'authentification
    assert int(r.headers["Retry-After"]) >= 1
    # Une autre organisation n'est pas pénalisée
    assert client.post("/api/v1/analyser-moteur", json=MESURE_SAINE, headers=org_b.machine).status_code == 200
    # L'ingestion simple n'est pas limitée
    assert client.post("/api/v1/mesures", json=MESURE_SAINE, headers=org_a.machine).status_code == 201


def test_limiteur_unitaire() -> None:
    lim = Limiteur("1/minute")
    assert lim.consommer("x") is None
    attente = lim.consommer("x")
    assert attente is not None and 1 <= attente <= 60
    assert lim.consommer("y") is None


def test_cors_origine_autorisee(client: TestClient) -> None:
    r = client.options(
        "/api/v1/moteurs",
        headers={"Origin": "https://app.exemple.be", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "https://app.exemple.be"


def test_cors_origine_refusee(client: TestClient) -> None:
    r = client.options(
        "/api/v1/moteurs",
        headers={"Origin": "https://pirate.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers
    r = client.get("/health", headers={"Origin": "https://pirate.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_joker_interdit() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins=["*"])


def test_cors_depuis_variable_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.be, https://b.be")
    assert Settings(_env_file=None).cors_origins == ["https://a.be", "https://b.be"]  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("brute", "attendue"),
    [
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_normalisation_database_url(brute: str, attendue: str) -> None:
    assert Settings(database_url=brute).database_url == attendue


def test_interface_servie(client: TestClient) -> None:
    r = client.get("/app")
    assert r.status_code == 200
    html = r.text
    assert "window.location.origin" in html
    assert "web-production-eebd7" not in html  # plus d'URL codée en dur
    assert "email_maintenance" not in html  # plus de destinataire côté client
    assert "vibration_rms_mm_s" in html
    assert "DOMPurify.sanitize" in html


def test_racine(client: TestClient) -> None:
    assert client.get("/").json()["docs"] == "/docs"
