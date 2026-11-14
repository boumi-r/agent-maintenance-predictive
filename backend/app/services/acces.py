"""Accès aux ressources toujours filtré par organisation.

Toute lecture d'une ressource identifiée par l'utilisateur passe par ces fonctions.
Une ressource d'une autre organisation est traitée comme inexistante (None -> 404).
"""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Alerte, Analyse, DestinataireAlerte, Moteur, Site


def site_de_org(session: Session, organisation_id: int, site_id: int) -> Site | None:
    return session.scalar(select(Site).where(Site.id == site_id, Site.organisation_id == organisation_id))


def requete_moteurs_org(organisation_id: int) -> Select[Moteur]:
    return select(Moteur).join(Site).where(Site.organisation_id == organisation_id)


def moteur_de_org(session: Session, organisation_id: int, moteur_id: int) -> Moteur | None:
    return session.scalar(requete_moteurs_org(organisation_id).where(Moteur.id == moteur_id))


def moteurs_par_code(session: Session, organisation_id: int, code: str) -> list[Moteur]:
    """Un code est unique par site ; plusieurs sites d'une organisation peuvent le réutiliser."""
    return list(session.scalars(requete_moteurs_org(organisation_id).where(Moteur.code == code)))


def analyse_de_org(session: Session, organisation_id: int, analyse_id: int) -> Analyse | None:
    return session.scalar(
        select(Analyse)
        .join(Moteur, Analyse.moteur_id == Moteur.id)
        .join(Site)
        .where(Analyse.id == analyse_id, Site.organisation_id == organisation_id)
    )


def alerte_de_org(session: Session, organisation_id: int, alerte_id: int) -> Alerte | None:
    return session.scalar(
        select(Alerte)
        .join(Moteur, Alerte.moteur_id == Moteur.id)
        .join(Site)
        .where(Alerte.id == alerte_id, Site.organisation_id == organisation_id)
    )


def destinataire_de_org(session: Session, organisation_id: int, dest_id: int) -> DestinataireAlerte | None:
    return session.scalar(
        select(DestinataireAlerte).where(
            DestinataireAlerte.id == dest_id, DestinataireAlerte.organisation_id == organisation_id
        )
    )
