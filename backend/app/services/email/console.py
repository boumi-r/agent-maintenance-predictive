"""Provider de développement : journalise l'email au lieu de l'envoyer."""

from __future__ import annotations

import logging

from app.services.email.base import EmailResult

logger = logging.getLogger(__name__)


class ConsoleProvider:
    nom = "console"

    def send(self, to: list[str], subject: str, html: str, text: str) -> EmailResult:
        logger.info("EMAIL (console) à=%s sujet=%r\n%s", to, subject, text)
        return EmailResult(True, self.nom, status_code=None, body="journalisé, non envoyé")
