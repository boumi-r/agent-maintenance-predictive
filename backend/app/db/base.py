"""Base déclarative SQLAlchemy et types communs."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

# Noms de contraintes stables pour Alembic (indispensable pour SQLite en mode batch et pour les diffs).
CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def maintenant() -> datetime:
    """Horodatage timezone-aware en UTC (remplace datetime.utcnow, déprécié)."""
    return datetime.now(UTC)


def enum_col(enum_cls: type[enum.Enum]) -> Enum:
    """Enum stocké en VARCHAR + CHECK : ajouter une valeur ne demande pas d'ALTER TYPE Postgres."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSON,
        list[Any]: JSON,
    }
