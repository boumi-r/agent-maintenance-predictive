"""Seuils de la couche de règles, avec leur source et leur nature.

nature = "norme"       : valeur publiée dans une norme et appliquée dans son domaine.
nature = "heuristique" : valeur de pratique courante, choix de conception, ou norme utilisée
                         hors de son domaine. À recaler avec les retours techniciens.

Toutes les bandes « surveillance » sont heuristiques (choix de conception MaintenanceAI).
Modifier un seuil => incrémenter VERSION_REGLES (stockée dans chaque Analyse).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.enums import ClasseIsolation, GroupeIso20816, NiveauRisque, TypeFondation

VERSION_REGLES = "2026.11-1"

Nature = Literal["norme", "heuristique"]


@dataclass(frozen=True)
class Seuil:
    """Franchi si valeur > limite (ou >= limite si inclusif)."""

    niveau: NiveauRisque
    limite: float
    source: str
    nature: Nature
    inclusif: bool = False

    def franchi(self, valeur: float) -> bool:
        return valeur >= self.limite if self.inclusif else valeur > self.limite

    def description(self, unite: str) -> str:
        op = "≥" if self.inclusif else ">"
        return f"{op} {self.limite:g} {unite}"


# ---------------------------------------------------------------------------
# Vibration — vitesse efficace (mm/s RMS)
# ---------------------------------------------------------------------------

#: ISO 20816-3 ne s'applique qu'aux machines de plus de 15 kW.
PUISSANCE_MIN_ISO_20816_3_KW = 15.0

SOURCE_ISO_20816_3 = "ISO 20816-3:2022, zones d'évaluation (valeurs reprises de l'ISO 10816-3)"

#: Limites de zones (A/B, B/C, C/D) en mm/s RMS, par groupe et type de fondation.
#: Zone A/B -> normal ; zone C (> B/C) -> élevé ; zone D (> C/D) -> critique.
ZONES_ISO_20816_3: dict[tuple[GroupeIso20816, TypeFondation], tuple[float, float, float]] = {
    (GroupeIso20816.GROUPE_1, TypeFondation.RIGIDE): (2.3, 4.5, 7.1),
    (GroupeIso20816.GROUPE_1, TypeFondation.FLEXIBLE): (3.5, 7.1, 11.0),
    (GroupeIso20816.GROUPE_2, TypeFondation.RIGIDE): (1.4, 2.8, 4.5),
    (GroupeIso20816.GROUPE_2, TypeFondation.FLEXIBLE): (2.3, 4.5, 7.1),
}

#: Repli pour P < 15 kW (hors champ ISO 20816-3) : ISO 10816-1:1995 annexe B, classe I
#: (petites machines). Norme retirée, valeurs indicatives -> nature heuristique.
SOURCE_ISO_10816_1_CLASSE_I = (
    "ISO 10816-1:1995 annexe B, classe I (norme retirée, valeurs indicatives ; "
    "repli car hors champ ISO 20816-3)"
)
ZONES_ISO_10816_1_CLASSE_I: tuple[float, float, float] = (0.71, 1.8, 4.5)

#: Bande surveillance vibration = règle de tendance : hausse depuis la mesure précédente
#: supérieure à 25 % de la limite B/C. Inspirée de la recommandation de l'ISO 20816-3 sur
#: les alarmes de variation ; choix du critère et de son usage = heuristique.
TENDANCE_VIBRATION_FRACTION_BC = 0.25
SOURCE_TENDANCE_VIBRATION = (
    "Heuristique MaintenanceAI inspirée de l'ISO 20816-3 (variation > 25 % de la limite B/C)"
)


# ---------------------------------------------------------------------------
# Déséquilibre de tension (NEMA MG-1, %)
# ---------------------------------------------------------------------------

SEUILS_DESEQUILIBRE_TENSION: tuple[Seuil, ...] = (
    Seuil(
        NiveauRisque.SURVEILLANCE,
        1.0,
        "NEMA MG-1 : déclassement du moteur requis au-delà de 1 % (bande surveillance = heuristique)",
        "heuristique",
    ),
    Seuil(NiveauRisque.ELEVE, 2.0, "EN 50160 : déséquilibre réseau admissible ≤ 2 %", "norme"),
    Seuil(NiveauRisque.CRITIQUE, 5.0, "NEMA MG-1 : fonctionnement déconseillé au-delà de 5 %", "norme"),
)


# ---------------------------------------------------------------------------
# Déséquilibre de courant (%, définition NEMA) — aucune norme moteur, heuristique
# ---------------------------------------------------------------------------

SOURCE_DESEQUILIBRE_COURANT = (
    "Heuristique terrain (le déséquilibre de courant vaut typiquement 6 à 10 fois celui de tension ; "
    "amplifié à faible charge)"
)
SEUILS_DESEQUILIBRE_COURANT: tuple[Seuil, ...] = (
    Seuil(NiveauRisque.SURVEILLANCE, 5.0, SOURCE_DESEQUILIBRE_COURANT, "heuristique"),
    Seuil(NiveauRisque.ELEVE, 10.0, SOURCE_DESEQUILIBRE_COURANT, "heuristique"),
    Seuil(NiveauRisque.CRITIQUE, 20.0, SOURCE_DESEQUILIBRE_COURANT, "heuristique"),
)


# ---------------------------------------------------------------------------
# Température bobinage (°C) — limite de classe thermique IEC 60085
# ---------------------------------------------------------------------------

SOURCE_IEC_60085 = "IEC 60085 : température maximale de la classe thermique"
LIMITE_CLASSE_ISOLATION_C: dict[ClasseIsolation, float] = {
    ClasseIsolation.A: 105.0,
    ClasseIsolation.E: 120.0,
    ClasseIsolation.B: 130.0,
    ClasseIsolation.F: 155.0,
    ClasseIsolation.H: 180.0,
}
#: Marges sous la limite de classe (K). Heuristiques : une sonde bobinage mesure en général
#: moins que le point chaud réel, d'où une marge avant la limite.
MARGE_BOBINAGE_SURVEILLANCE_K = 20.0
MARGE_BOBINAGE_ELEVE_K = 10.0
SOURCE_MARGE_BOBINAGE = "Heuristique MaintenanceAI : marge sous la limite IEC 60085"


def seuils_bobinage(classe: ClasseIsolation) -> tuple[Seuil, ...]:
    limite = LIMITE_CLASSE_ISOLATION_C[classe]
    return (
        Seuil(
            NiveauRisque.SURVEILLANCE,
            limite - MARGE_BOBINAGE_SURVEILLANCE_K,
            f"{SOURCE_MARGE_BOBINAGE} (classe {classe.value} − {MARGE_BOBINAGE_SURVEILLANCE_K:g} K)",
            "heuristique",
            inclusif=True,
        ),
        Seuil(
            NiveauRisque.ELEVE,
            limite - MARGE_BOBINAGE_ELEVE_K,
            f"{SOURCE_MARGE_BOBINAGE} (classe {classe.value} − {MARGE_BOBINAGE_ELEVE_K:g} K)",
            "heuristique",
            inclusif=True,
        ),
        Seuil(
            NiveauRisque.CRITIQUE,
            limite,
            f"{SOURCE_IEC_60085} (classe {classe.value})",
            "norme",
            inclusif=True,
        ),
    )


# ---------------------------------------------------------------------------
# Température roulements (°C) — pas de norme générale, heuristique
# ---------------------------------------------------------------------------

SOURCE_ROULEMENTS = "Heuristique terrain (seuils usuels d'alarme / déclenchement des paliers à roulements)"
SEUILS_TEMPERATURE_ROULEMENTS: tuple[Seuil, ...] = (
    Seuil(NiveauRisque.SURVEILLANCE, 80.0, SOURCE_ROULEMENTS, "heuristique", inclusif=True),
    Seuil(NiveauRisque.ELEVE, 90.0, SOURCE_ROULEMENTS, "heuristique", inclusif=True),
    Seuil(NiveauRisque.CRITIQUE, 100.0, SOURCE_ROULEMENTS, "heuristique", inclusif=True),
)


# ---------------------------------------------------------------------------
# Courant de phase max / courant nominal (ratio) — heuristique
# ---------------------------------------------------------------------------

SOURCE_SURCHARGE = "Heuristique : courant de phase max rapporté au courant nominal de plaque"
SEUILS_SURCHARGE_COURANT: tuple[Seuil, ...] = (
    Seuil(NiveauRisque.SURVEILLANCE, 1.0, SOURCE_SURCHARGE, "heuristique"),
    Seuil(NiveauRisque.ELEVE, 1.1, SOURCE_SURCHARGE, "heuristique"),
    Seuil(NiveauRisque.CRITIQUE, 1.25, SOURCE_SURCHARGE, "heuristique"),
)
