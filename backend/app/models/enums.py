"""Énumérations métier partagées entre ORM, schémas et services."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    TECHNICIEN = "technicien"


class ClasseIsolation(StrEnum):
    A = "A"
    E = "E"
    B = "B"
    F = "F"
    H = "H"


class GroupeIso20816(StrEnum):
    """ISO 20816-3 : groupe 1 = > 300 kW, groupe 2 = 15 kW à 300 kW."""

    GROUPE_1 = "groupe_1"
    GROUPE_2 = "groupe_2"


class TypeFondation(StrEnum):
    RIGIDE = "rigide"
    FLEXIBLE = "flexible"


class NiveauRisque(StrEnum):
    NORMAL = "normal"
    SURVEILLANCE = "surveillance"
    ELEVE = "eleve"
    CRITIQUE = "critique"
    INDETERMINE = "indetermine"


class SourceMesure(StrEnum):
    API_KEY = "api_key"
    UTILISATEUR = "utilisateur"


class StatutAnalyse(StrEnum):
    OK = "ok"
    ERREUR_LLM = "erreur_llm"


class StatutAlerte(StrEnum):
    OUVERTE = "ouverte"
    ACQUITTEE = "acquittee"
    RESOLUE = "resolue"
    FAUSSE_ALERTE = "fausse_alerte"


class StatutEnvoi(StrEnum):
    NON_ENVOYE = "non_envoye"
    ENVOYE = "envoye"
    ECHEC = "echec"
    AUCUN_DESTINATAIRE = "aucun_destinataire"
