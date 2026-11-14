"""Abstraction d'envoi d'email : un provider ne lève jamais, il renvoie l'erreur complète."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailResult:
    ok: bool
    provider: str
    status_code: int | None = None
    body: str | None = None
    message_id: str | None = None

    def resume_erreur(self) -> str:
        return f"{self.provider} status={self.status_code} body={self.body}"


class EmailProvider(Protocol):
    nom: str

    def send(self, to: list[str], subject: str, html: str, text: str) -> EmailResult: ...
