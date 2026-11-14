"""Outils exposés à Claude. Chaque exécution reçoit le contexte de SON analyse (aucun état global)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from anthropic.types import ToolParam
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alerte, Analyse, Mesure, Moteur
from app.services.email.base import EmailProvider
from app.services.regles import ResultatRegles


@dataclass
class ContexteAnalyse:
    """État d'UNE analyse. Créé par requête, jamais partagé."""

    session: Session
    moteur: Moteur
    mesure: Mesure
    analyse: Analyse
    regles: ResultatRegles
    email_provider: EmailProvider
    # Callback qui crée et envoie l'alerte (services.analyse) ; renvoie l'alerte
    declencher: Callable[[ContexteAnalyse, str, str], Alerte]
    alerte: Alerte | None = None
    historique_consulte: bool = False
    outils_appeles: list[str] = field(default_factory=list)


class _SansArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ArgsHistorique(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limite: int = Field(default=5, ge=1, le=20)


class _ArgsAlerte(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)


DEFINITIONS: list[ToolParam] = [
    {
        "name": "consulter_historique",
        "description": (
            "Renvoie les dernières mesures de ce moteur (hors mesure courante) avec le niveau de "
            "risque de leur analyse, de la plus récente à la plus ancienne. Sert à détecter une tendance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"limite": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}},
            "additionalProperties": False,
        },
    },
    {
        "name": "fiche_moteur",
        "description": (
            "Renvoie la fiche signalétique du moteur (puissance, In, classe d'isolation, groupe ISO...)."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "declencher_alerte",
        "description": (
            "Crée l'alerte de cette analyse et l'envoie aux destinataires configurés côté serveur. "
            "Uniquement si le niveau des règles est « eleve » ou « critique ». Un seul appel par analyse."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message court et actionnable pour l'équipe de maintenance",
                }
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
]


class OutilError(Exception):
    """Erreur renvoyée à Claude dans un tool_result is_error (n'interrompt pas l'analyse)."""


def _mesure_dict(m: Mesure) -> dict[str, Any]:
    return {
        "mesure_le": m.mesure_le.isoformat(),
        "tensions_v": [m.tension_ph1_v, m.tension_ph2_v, m.tension_ph3_v],
        "courants_a": [m.courant_ph1_a, m.courant_ph2_a, m.courant_ph3_a],
        "vibration_rms_mm_s": m.vibration_rms_mm_s,
        "temperature_roulements_c": m.temperature_roulements_c,
        "temperature_bobinage_c": m.temperature_bobinage_c,
        "desequilibre_tension_pct": m.desequilibre_tension_pct,
        "desequilibre_courant_pct": m.desequilibre_courant_pct,
        "observations": m.observations,
    }


def fiche_dict(moteur: Moteur) -> dict[str, Any]:
    return {
        "code": moteur.code,
        "designation": moteur.designation,
        "puissance_kw": moteur.puissance_kw,
        "tension_nominale_v": moteur.tension_nominale_v,
        "courant_nominal_a": moteur.courant_nominal_a,
        "vitesse_nominale_tr_min": moteur.vitesse_nominale_tr_min,
        "nombre_poles": moteur.nombre_poles,
        "classe_isolation": moteur.classe_isolation,
        "type_roulements": moteur.type_roulements,
        "groupe_iso20816": moteur.groupe_iso20816,
        "type_fondation": moteur.type_fondation,
        "date_mise_en_service": moteur.date_mise_en_service.isoformat()
        if moteur.date_mise_en_service
        else None,
    }


def historique(ctx: ContexteAnalyse, limite: int) -> list[dict[str, Any]]:
    lignes = ctx.session.execute(
        select(Mesure, Analyse.niveau_risque)
        .outerjoin(Analyse, Analyse.mesure_id == Mesure.id)
        .where(Mesure.moteur_id == ctx.moteur.id, Mesure.id != ctx.mesure.id)
        .order_by(Mesure.mesure_le.desc(), Mesure.id.desc())
        .limit(limite)
    ).all()
    return [{**_mesure_dict(m), "niveau_risque": n.value if n else None} for m, n in lignes]


def _consulter_historique(ctx: ContexteAnalyse, brut: dict[str, Any]) -> Any:
    args = _ArgsHistorique.model_validate(brut)
    ctx.historique_consulte = True
    return historique(ctx, args.limite)


def _fiche_moteur(ctx: ContexteAnalyse, brut: dict[str, Any]) -> Any:
    _SansArgs.model_validate(brut)
    return fiche_dict(ctx.moteur)


def _declencher_alerte(ctx: ContexteAnalyse, brut: dict[str, Any]) -> Any:
    args = _ArgsAlerte.model_validate(brut)
    from app.services.alertes import NIVEAUX_ALERTABLES  # import local : évite un cycle

    if ctx.regles.niveau_global not in NIVEAUX_ALERTABLES:
        raise OutilError(
            f"Alerte refusée : niveau des règles = {ctx.regles.niveau_global.value} "
            "(alerte réservée à eleve / critique)"
        )
    if ctx.alerte is not None:
        raise OutilError(f"Alerte déjà créée pour cette analyse (id {ctx.alerte.id})")
    alerte = ctx.declencher(ctx, args.message, "agent")
    return {
        "alerte_id": alerte.id,
        "niveau": alerte.niveau.value,
        "envoi_statut": alerte.envoi_statut.value,
        "envoi_erreur": alerte.envoi_erreur,
        "destinataires": len(alerte.envoi_destinataires),
    }


HANDLERS: dict[str, Callable[[ContexteAnalyse, dict[str, Any]], Any]] = {
    "consulter_historique": _consulter_historique,
    "fiche_moteur": _fiche_moteur,
    "declencher_alerte": _declencher_alerte,
}


def executer_outil(ctx: ContexteAnalyse, nom: str, brut: object) -> tuple[str, bool]:
    """Renvoie (contenu JSON, is_error)."""
    ctx.outils_appeles.append(nom)
    handler = HANDLERS.get(nom)
    if handler is None:
        return json.dumps({"erreur": f"Outil inconnu : {nom}"}), True
    if not isinstance(brut, dict):
        return json.dumps({"erreur": "Arguments invalides : objet JSON attendu"}), True
    try:
        return json.dumps(handler(ctx, brut), ensure_ascii=False, default=str), False
    except ValidationError as exc:
        return json.dumps(
            {"erreur": f"Arguments invalides : {exc.errors(include_url=False)}"}, default=str
        ), True
    except OutilError as exc:
        return json.dumps({"erreur": str(exc)}, ensure_ascii=False), True
