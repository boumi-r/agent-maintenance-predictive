"""SendGrid via l'API REST v3 (httpx) : status code et body toujours disponibles en cas d'échec."""

from __future__ import annotations

import httpx

from app.services.email.base import EmailResult

URL_SENDGRID = "https://api.sendgrid.com/v3/mail/send"


class SendGridProvider:
    nom = "sendgrid"

    def __init__(self, api_key: str, from_email: str, from_name: str, client: httpx.Client) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name
        self._client = client

    def send(self, to: list[str], subject: str, html: str, text: str) -> EmailResult:
        if not self._api_key:
            return EmailResult(False, self.nom, body="SENDGRID_API_KEY absente de l'environnement")
        payload = {
            "personalizations": [{"to": [{"email": e} for e in to]}],
            "from": {"email": self._from_email, "name": self._from_name},
            "subject": subject,
            "content": [{"type": "text/plain", "value": text}, {"type": "text/html", "value": html}],
        }
        try:
            r = self._client.post(
                URL_SENDGRID, json=payload, headers={"Authorization": f"Bearer {self._api_key}"}
            )
        except httpx.HTTPError as exc:
            return EmailResult(False, self.nom, body=f"{type(exc).__name__}: {exc}")
        # SendGrid répond 202 Accepted en cas de succès
        return EmailResult(
            ok=r.status_code == 202,
            provider=self.nom,
            status_code=r.status_code,
            body=r.text,
            message_id=r.headers.get("X-Message-Id"),
        )
