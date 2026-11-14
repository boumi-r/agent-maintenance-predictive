"""Mots de passe, JWT utilisateurs et clés API machine."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.models.enums import Role

_hasher = PasswordHash.recommended()  # argon2 ; objet sans état, sûr à partager

PREFIXE_CLE = "mai"


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hasher.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hash_: str) -> bool:
    return _hasher.verify(mot_de_passe, hash_)


# --- JWT ---------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimsJwt:
    utilisateur_id: int
    organisation_id: int
    role: Role


def creer_jwt(settings: Settings, utilisateur_id: int, organisation_id: int, role: Role) -> str:
    maintenant = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(utilisateur_id),
        "org": organisation_id,
        "role": role.value,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)


def decoder_jwt(settings: Settings, token: str) -> ClaimsJwt | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "org", "exp"]},
        )
        return ClaimsJwt(int(payload["sub"]), int(payload["org"]), Role(payload["role"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# --- Clés API ----------------------------------------------------------------


@dataclass(frozen=True)
class CleGeneree:
    clair: str  # montré une seule fois
    prefixe: str
    hash: str


def hacher_cle_api(settings: Settings, cle: str) -> str:
    return hmac.new(
        settings.api_key_salt.get_secret_value().encode(), cle.encode(), hashlib.sha256
    ).hexdigest()


def generer_cle_api(settings: Settings) -> CleGeneree:
    prefixe = secrets.token_hex(4)
    clair = f"{PREFIXE_CLE}_{prefixe}_{secrets.token_urlsafe(32)}"
    return CleGeneree(clair=clair, prefixe=prefixe, hash=hacher_cle_api(settings, clair))
