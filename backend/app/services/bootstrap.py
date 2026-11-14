"""Création initiale d'une organisation (utilisé par scripts/bootstrap.py et les tests)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import generer_cle_api, hacher_mot_de_passe
from app.models import CleApi, DestinataireAlerte, Organisation, Site, Utilisateur
from app.models.enums import Role


@dataclass(frozen=True)
class OrganisationCreee:
    organisation_id: int
    site_id: int
    admin_id: int
    cle_api: str  # en clair, à afficher une seule fois


def slugifier(nom: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-") or "org"


def creer_organisation(
    session: Session,
    settings: Settings,
    *,
    nom: str,
    admin_email: str,
    admin_mot_de_passe: str,
    site_nom: str = "Site principal",
    destinataire_email: str | None = None,
) -> OrganisationCreee:
    org = Organisation(nom=nom, slug=slugifier(nom))
    session.add(org)
    session.flush()
    site = Site(organisation_id=org.id, nom=site_nom)
    admin = Utilisateur(
        organisation_id=org.id,
        email=admin_email.lower(),
        mot_de_passe_hash=hacher_mot_de_passe(admin_mot_de_passe),
        role=Role.ADMIN,
    )
    generee = generer_cle_api(settings)
    cle = CleApi(organisation_id=org.id, nom="bootstrap", prefixe=generee.prefixe, hash=generee.hash)
    session.add_all([site, admin, cle])
    session.flush()
    if destinataire_email:
        session.add(DestinataireAlerte(organisation_id=org.id, email=destinataire_email.lower()))
    session.commit()
    return OrganisationCreee(org.id, site.id, admin.id, generee.clair)
