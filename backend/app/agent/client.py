"""Construction du client Anthropic (une instance par application, sans état de requête)."""

from __future__ import annotations

import anthropic

from app.core.config import Settings


def creer_client_anthropic(settings: Settings) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value() or None, max_retries=2)
