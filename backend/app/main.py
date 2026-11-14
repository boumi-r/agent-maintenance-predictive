"""Point d'entrée FastAPI."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.agent.client import creer_client_anthropic
from app.api import alertes, auth, cles_api, mesures, moteurs, sites
from app.core.config import Settings, get_settings
from app.core.logging import configurer_logging
from app.db.session import creer_engine, creer_session_factory
from app.services.email.factory import get_email_provider

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configurer_logging(settings.log_level)

    app = FastAPI(title="MaintenanceAI", version="0.1.0")
    # Objets construits une fois au démarrage et en lecture seule ensuite : aucun état de requête ici.
    app.state.settings = settings
    app.state.session_factory = session_factory or creer_session_factory(creer_engine(settings.database_url))
    app.state.client_llm = creer_client_anthropic(settings)
    app.state.email_provider = get_email_provider(settings)

    api = APIRouter(prefix=API_PREFIX)
    for module in (auth, sites, moteurs, cles_api, mesures, alertes):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
