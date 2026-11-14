"""Choix du provider selon EMAIL_PROVIDER."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.email.base import EmailProvider
from app.services.email.console import ConsoleProvider
from app.services.email.resend import ResendProvider
from app.services.email.sendgrid import SendGridProvider

TIMEOUT_S = 10.0


def get_email_provider(settings: Settings, client: httpx.Client | None = None) -> EmailProvider:
    if settings.email_provider == "console":
        return ConsoleProvider()
    client = client or httpx.Client(timeout=TIMEOUT_S)
    if settings.email_provider == "sendgrid":
        return SendGridProvider(
            settings.sendgrid_api_key.get_secret_value(),
            settings.email_from,
            settings.email_from_name,
            client,
        )
    return ResendProvider(
        settings.resend_api_key.get_secret_value(), settings.email_from, settings.email_from_name, client
    )
