"""Point d'entrée FastAPI."""

from __future__ import annotations

from importlib.resources import files

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, sessionmaker

from app.agent.client import creer_client_anthropic
from app.api import alertes, auth, cles_api, mesures, moteurs, sites
from app.core.config import Settings, get_settings
from app.core.logging import configurer_logging
from app.core.rate_limit import Limiteur
from app.db.session import creer_engine, creer_session_factory
from app.services.email.factory import get_email_provider

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configurer_logging(settings.log_level)

    app = FastAPI(
        title="MaintenanceAI",
        version="0.1.0",
        description="Maintenance prédictive des moteurs électriques : règles normatives + agent Claude.",
    )
    # Objets construits une fois au démarrage, sans état propre à une requête.
    app.state.settings = settings
    app.state.session_factory = session_factory or creer_session_factory(creer_engine(settings.database_url))
    app.state.client_llm = creer_client_anthropic(settings)
    app.state.email_provider = get_email_provider(settings)
    app.state.limiteur_analyse = Limiteur(settings.rate_limit_analyse, settings.rate_limit_storage_uri)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # auth par en-têtes (Bearer / X-API-Key), pas par cookies
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    api = APIRouter(prefix=API_PREFIX)
    for module in (auth, sites, moteurs, cles_api, mesures, alertes):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/", tags=["health"])
    def racine() -> dict[str, str]:
        return {"message": "API MaintenanceAI", "docs": "/docs", "interface": "/app"}

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    def interface() -> str:
        return files("app").joinpath("static/app.html").read_text(encoding="utf-8")

    return app


app = create_app()
