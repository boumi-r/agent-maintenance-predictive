"""Schémas des endpoints de gestion (auth, sites, moteurs, destinataires, clés, utilisateurs)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ClasseIsolation, GroupeIso20816, Role, TypeFondation


class Entree(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---


class LoginIn(Entree):
    email: EmailStr
    mot_de_passe: str = Field(min_length=1, max_length=256)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class UtilisateurIn(Entree):
    email: EmailStr
    nom: str | None = Field(default=None, max_length=200)
    mot_de_passe: str = Field(min_length=12, max_length=256)
    role: Role = Role.TECHNICIEN


class UtilisateurOut(Sortie):
    id: int
    organisation_id: int
    email: str
    nom: str | None
    role: Role
    actif: bool


# --- Sites et destinataires ---


class SiteIn(Entree):
    nom: str = Field(min_length=1, max_length=200)
    adresse: str | None = Field(default=None, max_length=500)


class SiteOut(Sortie):
    id: int
    nom: str
    adresse: str | None


class DestinataireIn(Entree):
    email: EmailStr


class DestinataireOut(Sortie):
    id: int
    site_id: int | None
    email: str
    actif: bool


# --- Moteurs ---


class MoteurBase(Entree):
    designation: str | None = Field(default=None, max_length=200)
    puissance_kw: float | None = Field(default=None, gt=0, le=100_000)
    tension_nominale_v: float | None = Field(default=None, gt=0, le=20_000)
    courant_nominal_a: float | None = Field(default=None, gt=0, le=10_000)
    vitesse_nominale_tr_min: float | None = Field(default=None, gt=0, le=10_000)
    nombre_poles: int | None = Field(default=None, ge=2, le=64)
    classe_isolation: ClasseIsolation | None = None
    type_roulements: str | None = Field(default=None, max_length=100)
    groupe_iso20816: GroupeIso20816 | None = None
    type_fondation: TypeFondation | None = None
    date_mise_en_service: date | None = None


class MoteurIn(MoteurBase):
    site_id: int
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")


class MoteurPatch(MoteurBase):
    """Tous les champs optionnels ; seuls les champs envoyés sont modifiés."""


class MoteurOut(Sortie):
    id: int
    site_id: int
    code: str
    designation: str | None
    puissance_kw: float | None
    tension_nominale_v: float | None
    courant_nominal_a: float | None
    vitesse_nominale_tr_min: float | None
    nombre_poles: int | None
    classe_isolation: ClasseIsolation | None
    type_roulements: str | None
    groupe_iso20816: GroupeIso20816 | None
    type_fondation: TypeFondation | None
    date_mise_en_service: date | None


# --- Clés API ---


class CleApiIn(Entree):
    nom: str = Field(min_length=1, max_length=100)


class CleApiOut(Sortie):
    id: int
    nom: str
    prefixe: str
    active: bool
    cree_le: datetime
    derniere_utilisation: datetime | None


class CleApiCreeeOut(CleApiOut):
    cle: str = Field(description="Clé en clair : affichée une seule fois, à conserver en lieu sûr")
