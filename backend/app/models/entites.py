"""Modèle de données multi-entreprise.

Organisation → Site → Moteur → Mesure → Analyse → Alerte → RetourTechnicien.
L'isolation entre organisations passe toujours par Site.organisation_id.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, enum_col, maintenant
from app.models.enums import (
    ClasseIsolation,
    GroupeIso20816,
    NiveauRisque,
    Role,
    SourceMesure,
    StatutAlerte,
    StatutAnalyse,
    StatutEnvoi,
    TypeFondation,
)


class Organisation(Base):
    __tablename__ = "organisation"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)

    sites: Mapped[list[Site]] = relationship(back_populates="organisation")


class CleApi(Base):
    """Clé API machine. Seul le HMAC est stocké ; la clé en clair n'est montrée qu'à la création."""

    __tablename__ = "cle_api"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisation.id", ondelete="CASCADE"), index=True
    )
    nom: Mapped[str] = mapped_column(String(100))
    prefixe: Mapped[str] = mapped_column(String(16), index=True)
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)
    derniere_utilisation: Mapped[datetime | None]


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisation.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nom: Mapped[str | None] = mapped_column(String(200))
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_col(Role), default=Role.TECHNICIEN)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisation.id", ondelete="CASCADE"), index=True
    )
    nom: Mapped[str] = mapped_column(String(200))
    adresse: Mapped[str | None] = mapped_column(String(500))
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)

    organisation: Mapped[Organisation] = relationship(back_populates="sites")
    moteurs: Mapped[list[Moteur]] = relationship(back_populates="site")


class DestinataireAlerte(Base):
    """Seule source des destinataires d'alerte. site_id NULL = toute l'organisation."""

    __tablename__ = "destinataire_alerte"
    __table_args__ = (UniqueConstraint("organisation_id", "site_id", "email", name="uq_destinataire"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisation.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[int | None] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)


class Moteur(Base):
    """Fiche signalétique d'un moteur physique."""

    __tablename__ = "moteur"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_moteur_site_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    designation: Mapped[str | None] = mapped_column(String(200))
    puissance_kw: Mapped[float | None] = mapped_column(Float)
    tension_nominale_v: Mapped[float | None] = mapped_column(Float)
    courant_nominal_a: Mapped[float | None] = mapped_column(Float)
    vitesse_nominale_tr_min: Mapped[float | None] = mapped_column(Float)
    nombre_poles: Mapped[int | None] = mapped_column(Integer)
    classe_isolation: Mapped[ClasseIsolation | None] = mapped_column(enum_col(ClasseIsolation))
    type_roulements: Mapped[str | None] = mapped_column(String(100))
    groupe_iso20816: Mapped[GroupeIso20816 | None] = mapped_column(enum_col(GroupeIso20816))
    type_fondation: Mapped[TypeFondation | None] = mapped_column(enum_col(TypeFondation))
    date_mise_en_service: Mapped[date | None]
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)

    site: Mapped[Site] = relationship(back_populates="moteurs")


class Mesure(Base):
    """Un relevé horodaté de toutes les grandeurs d'un moteur."""

    __tablename__ = "mesure"
    __table_args__ = (Index("ix_mesure_moteur_date", "moteur_id", "mesure_le"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    moteur_id: Mapped[int] = mapped_column(ForeignKey("moteur.id", ondelete="CASCADE"))
    mesure_le: Mapped[datetime] = mapped_column(default=maintenant)
    recu_le: Mapped[datetime] = mapped_column(default=maintenant)
    source: Mapped[SourceMesure] = mapped_column(enum_col(SourceMesure))

    tension_ph1_v: Mapped[float] = mapped_column(Float)
    tension_ph2_v: Mapped[float] = mapped_column(Float)
    tension_ph3_v: Mapped[float] = mapped_column(Float)
    courant_ph1_a: Mapped[float] = mapped_column(Float)
    courant_ph2_a: Mapped[float] = mapped_column(Float)
    courant_ph3_a: Mapped[float] = mapped_column(Float)
    vibration_rms_mm_s: Mapped[float] = mapped_column(Float)
    temperature_roulements_c: Mapped[float] = mapped_column(Float)
    temperature_bobinage_c: Mapped[float] = mapped_column(Float)
    observations: Mapped[str | None] = mapped_column(Text)

    # Grandeurs dérivées, calculées à l'ingestion (services.electrique)
    desequilibre_tension_pct: Mapped[float | None] = mapped_column(Float)
    desequilibre_courant_pct: Mapped[float | None] = mapped_column(Float)


class Analyse(Base):
    __tablename__ = "analyse"
    __table_args__ = (Index("ix_analyse_moteur_date", "moteur_id", "cree_le"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mesure_id: Mapped[int] = mapped_column(ForeignKey("mesure.id", ondelete="CASCADE"), index=True)
    moteur_id: Mapped[int] = mapped_column(ForeignKey("moteur.id", ondelete="CASCADE"))
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)
    niveau_risque: Mapped[NiveauRisque] = mapped_column(enum_col(NiveauRisque))
    diagnostic: Mapped[str | None] = mapped_column(Text)
    resultats_regles: Mapped[list[Any]] = mapped_column(default=list)
    sources: Mapped[list[Any]] = mapped_column(default=list)
    version_regles: Mapped[str] = mapped_column(String(32))
    versions_modeles: Mapped[dict[str, Any]] = mapped_column(default=dict)
    modele_llm: Mapped[str | None] = mapped_column(String(100))
    statut: Mapped[StatutAnalyse] = mapped_column(enum_col(StatutAnalyse), default=StatutAnalyse.OK)
    erreur: Mapped[str | None] = mapped_column(Text)


class Alerte(Base):
    __tablename__ = "alerte"
    __table_args__ = (Index("ix_alerte_moteur_statut", "moteur_id", "statut"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analyse_id: Mapped[int] = mapped_column(ForeignKey("analyse.id", ondelete="CASCADE"), index=True)
    moteur_id: Mapped[int] = mapped_column(ForeignKey("moteur.id", ondelete="CASCADE"))
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)
    niveau: Mapped[NiveauRisque] = mapped_column(enum_col(NiveauRisque))
    message: Mapped[str] = mapped_column(Text)
    declenchee_par: Mapped[str] = mapped_column(String(32))  # "agent" ou "regles"

    statut: Mapped[StatutAlerte] = mapped_column(enum_col(StatutAlerte), default=StatutAlerte.OUVERTE)
    acquittee_par_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id", ondelete="SET NULL"))
    acquittee_le: Mapped[datetime | None]
    resolue_le: Mapped[datetime | None]

    envoi_statut: Mapped[StatutEnvoi] = mapped_column(enum_col(StatutEnvoi), default=StatutEnvoi.NON_ENVOYE)
    envoi_erreur: Mapped[str | None] = mapped_column(Text)
    envoi_destinataires: Mapped[list[Any]] = mapped_column(default=list)
    envoye_le: Mapped[datetime | None]


class RetourTechnicien(Base):
    """Vérité terrain : sert à réentraîner et calibrer les modèles plus tard."""

    __tablename__ = "retour_technicien"
    __table_args__ = (Index("ix_retour_moteur_date", "moteur_id", "cree_le"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    moteur_id: Mapped[int] = mapped_column(ForeignKey("moteur.id", ondelete="CASCADE"))
    analyse_id: Mapped[int | None] = mapped_column(ForeignKey("analyse.id", ondelete="SET NULL"), index=True)
    alerte_id: Mapped[int | None] = mapped_column(ForeignKey("alerte.id", ondelete="SET NULL"), index=True)
    utilisateur_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id", ondelete="SET NULL"))
    cree_le: Mapped[datetime] = mapped_column(default=maintenant)
    defaut_confirme: Mapped[bool | None] = mapped_column(Boolean)
    type_defaut: Mapped[str | None] = mapped_column(String(100))
    commentaire: Mapped[str | None] = mapped_column(Text)
    intervention_le: Mapped[datetime | None]
