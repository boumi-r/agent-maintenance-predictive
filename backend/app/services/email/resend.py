"""Resend via son API REST (httpx)."""

from __future__ import annotations

import httpx

from app.services.email.base import EmailResult

URL_RESEND = "https://api.resend.com/emails"


class ResendProvider:
    nom = "resend"

    def __init__(self, api_key: str, from_email: str, from_name: str, client: httpx.Client) -> None:
        self._api_key = api_key
        self._from = f"{from_name} <{from_email}>"
        self._client = client

    def send(self, to: list[str], subject: str, html: str, text: str) -> EmailResult:
        if not self._api_key:
            return EmailResult(False, self.nom, body="RESEND_API_KEY absente de l'environnement")
        payload = {"from": self._from, "to": to, "subject": subject, "html": html, "text": text}
        try:
            r = self._client.post(
                URL_RESEND, json=payload, headers={"Authorization": f"Bearer {self._api_key}"}
            )
        except httpx.HTTPError as exc:
            return EmailResult(False, self.nom, body=f"{type(exc).__name__}: {exc}")
        message_id: str | None = None
        if r.is_success:
            try:
                message_id = r.json().get("id")
            except ValueError:
                message_id = None
        return EmailResult(r.is_success, self.nom, r.status_code, r.text, message_id)
