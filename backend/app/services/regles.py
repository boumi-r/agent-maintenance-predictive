"""Couche de règles normatives : détermine le niveau de risque de façon déterministe.

L'agent Claude ne choisit jamais le niveau de risque ; il lit ces résultats et les explique.
Chaque résultat porte sa valeur, le seuil appliqué, la source et sa nature (norme / heuristique).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.enums import ClasseIsolation, GroupeIso20816, NiveauRisque, TypeFondation
from app.services import regles_constantes as rc
from app.services.electrique import desequilibre_nema, desequilibre_vuf_iec
from app.services.regles_constantes import Nature, Seuil

ORDRE_NIVEAUX: dict[NiveauRisque, int] = {
    NiveauRisque.NORMAL: 0,
    NiveauRisque.SURVEILLANCE: 1,
    NiveauRisque.ELEVE: 2,
    NiveauRisque.CRITIQUE: 3,
}


@dataclass(frozen=True)
class FicheMoteur:
    puissance_kw: float | None = None
    courant_nominal_a: float | None = None
    classe_isolation: ClasseIsolation | None = None
    groupe_iso20816: GroupeIso20816 | None = None
    type_fondation: TypeFondation | None = None


@dataclass(frozen=True)
class ValeursMesure:
    tension_ph1_v: float
    tension_ph2_v: float
    tension_ph3_v: float
    courant_ph1_a: float
    courant_ph2_a: float
    courant_ph3_a: float
    vibration_rms_mm_s: float
    temperature_roulements_c: float
    temperature_bobinage_c: float


@dataclass(frozen=True)
class ResultatRegle:
    code: str
    libelle: str
    valeur: float | None
    unite: str
    niveau: NiveauRisque
    seuil: str | None
    source: str
    nature: Nature
    note: str | None = None


@dataclass(frozen=True)
class ResultatRegles:
    niveau_global: NiveauRisque
    resultats: list[ResultatRegle]
    non_evaluees: list[str] = field(default_factory=list)
    version: str = rc.VERSION_REGLES

    def en_dict(self) -> dict[str, Any]:
        return {
            "niveau_global": self.niveau_global.value,
            "version": self.version,
            "resultats": [{**asdict(r), "niveau": r.niveau.value} for r in self.resultats],
            "non_evaluees": list(self.non_evaluees),
        }


# ---------------------------------------------------------------------------
# Outils génériques
# ---------------------------------------------------------------------------


def _appliquer_seuils(
    code: str,
    libelle: str,
    valeur: float,
    unite: str,
    seuils: Sequence[Seuil],
    note: str | None = None,
) -> ResultatRegle:
    """Niveau = bande la plus haute franchie. Sous toutes les bandes : normal, en citant
    le premier seuil (celui qui ferait passer en surveillance)."""
    franchis = [s for s in seuils if s.franchi(valeur)]
    if franchis:
        s = max(franchis, key=lambda x: ORDRE_NIVEAUX[x.niveau])
        return ResultatRegle(
            code, libelle, valeur, unite, s.niveau, s.description(unite), s.source, s.nature, note
        )
    premier = seuils[0]
    return ResultatRegle(
        code,
        libelle,
        valeur,
        unite,
        NiveauRisque.NORMAL,
        f"sous {premier.description(unite)}",
        premier.source,
        premier.nature,
        note,
    )


def _indetermine(code: str, libelle: str, valeur: float | None, unite: str, raison: str) -> ResultatRegle:
    return ResultatRegle(
        code, libelle, valeur, unite, NiveauRisque.INDETERMINE, None, "—", "heuristique", raison
    )


def _seuils_zones(zones: tuple[float, float, float], source: str, nature: Nature) -> tuple[Seuil, Seuil]:
    _ab, bc, cd = zones
    return (
        Seuil(NiveauRisque.ELEVE, bc, f"{source} — zone C", nature),
        Seuil(NiveauRisque.CRITIQUE, cd, f"{source} — zone D", nature),
    )


def _zone_label(valeur: float, zones: tuple[float, float, float]) -> str:
    ab, bc, cd = zones
    if valeur > cd:
        return "D"
    if valeur > bc:
        return "C"
    if valeur > ab:
        return "B"
    return "A"


# ---------------------------------------------------------------------------
# Règles
# ---------------------------------------------------------------------------


def _zones_vibration(fiche: FicheMoteur) -> tuple[tuple[float, float, float], str, Nature, str] | str:
    """Renvoie (zones, source, nature, note) ou une raison d'indétermination."""
    if fiche.puissance_kw is None:
        return "puissance du moteur inconnue : impossible de choisir le référentiel vibratoire"
    if fiche.puissance_kw < rc.PUISSANCE_MIN_ISO_20816_3_KW:
        return (
            rc.ZONES_ISO_10816_1_CLASSE_I,
            rc.SOURCE_ISO_10816_1_CLASSE_I,
            "heuristique",
            f"hors champ ISO 20816-3 (P = {fiche.puissance_kw:g} kW < 15 kW)",
        )
    if fiche.groupe_iso20816 is None or fiche.type_fondation is None:
        return "groupe ISO 20816 ou type de fondation absent de la fiche moteur"
    zones = rc.ZONES_ISO_20816_3[(fiche.groupe_iso20816, fiche.type_fondation)]
    note = f"{fiche.groupe_iso20816.value}, fondation {fiche.type_fondation.value}"
    return zones, rc.SOURCE_ISO_20816_3, "norme", note


def regle_vibration(fiche: FicheMoteur, vibration: float) -> ResultatRegle:
    code, libelle, unite = "vibration_zone", "Vibration (vitesse efficace)", "mm/s"
    ref = _zones_vibration(fiche)
    if isinstance(ref, str):
        return _indetermine(code, libelle, vibration, unite, ref)
    zones, source, nature, note = ref
    r = _appliquer_seuils(code, libelle, vibration, unite, _seuils_zones(zones, source, nature))
    note_complete = f"zone {_zone_label(vibration, zones)} ; {note}"
    if r.niveau is NiveauRisque.NORMAL:
        # Zones A et B : normal. On cite la limite B/C, pas une bande surveillance (il n'y en a pas).
        return ResultatRegle(
            code,
            libelle,
            vibration,
            unite,
            r.niveau,
            f"≤ {zones[1]:g} {unite} (limite B/C)",
            source,
            nature,
            note_complete,
        )
    return ResultatRegle(
        code, libelle, vibration, unite, r.niveau, r.seuil, r.source, r.nature, note_complete
    )


def regle_tendance_vibration(fiche: FicheMoteur, vibration: float, precedente: float) -> ResultatRegle | str:
    code, libelle, unite = "vibration_tendance", "Hausse de vibration depuis la mesure précédente", "mm/s"
    ref = _zones_vibration(fiche)
    if isinstance(ref, str):
        return ref
    zones = ref[0]
    limite = rc.TENDANCE_VIBRATION_FRACTION_BC * zones[1]
    hausse = vibration - precedente
    seuil = Seuil(NiveauRisque.SURVEILLANCE, round(limite, 4), rc.SOURCE_TENDANCE_VIBRATION, "heuristique")
    note = f"{precedente:g} → {vibration:g} mm/s ; seuil = 25 % de la limite B/C ({zones[1]:g} mm/s)"
    return _appliquer_seuils(code, libelle, round(hausse, 4), unite, (seuil,), note)


def regle_desequilibre_tension(m: ValeursMesure) -> ResultatRegle:
    code, libelle, unite = "desequilibre_tension", "Déséquilibre de tension (NEMA)", "%"
    valeur = desequilibre_nema(m.tension_ph1_v, m.tension_ph2_v, m.tension_ph3_v)
    if valeur is None:
        return _indetermine(code, libelle, None, unite, "tensions nulles ou invalides")
    vuf = desequilibre_vuf_iec(m.tension_ph1_v, m.tension_ph2_v, m.tension_ph3_v)
    note = f"VUF IEC = {vuf:.2f} % (informatif)" if vuf is not None else None
    return _appliquer_seuils(code, libelle, round(valeur, 3), unite, rc.SEUILS_DESEQUILIBRE_TENSION, note)


def regle_desequilibre_courant(m: ValeursMesure) -> ResultatRegle:
    code, libelle, unite = "desequilibre_courant", "Déséquilibre de courant (NEMA)", "%"
    valeur = desequilibre_nema(m.courant_ph1_a, m.courant_ph2_a, m.courant_ph3_a)
    if valeur is None:
        return _indetermine(code, libelle, None, unite, "courants nuls ou invalides (moteur à l'arrêt ?)")
    return _appliquer_seuils(code, libelle, round(valeur, 3), unite, rc.SEUILS_DESEQUILIBRE_COURANT)


def regle_temperature_bobinage(fiche: FicheMoteur, temperature: float) -> ResultatRegle:
    code, libelle, unite = "temperature_bobinage", "Température bobinage", "°C"
    if fiche.classe_isolation is None:
        return _indetermine(
            code, libelle, temperature, unite, "classe d'isolation absente de la fiche moteur"
        )
    return _appliquer_seuils(code, libelle, temperature, unite, rc.seuils_bobinage(fiche.classe_isolation))


def regle_temperature_roulements(temperature: float) -> ResultatRegle:
    return _appliquer_seuils(
        "temperature_roulements",
        "Température roulements",
        temperature,
        "°C",
        rc.SEUILS_TEMPERATURE_ROULEMENTS,
    )


def regle_surcharge_courant(fiche: FicheMoteur, m: ValeursMesure) -> ResultatRegle:
    code, libelle, unite = "surcharge_courant", "Courant max / courant nominal", "× In"
    i_max = max(m.courant_ph1_a, m.courant_ph2_a, m.courant_ph3_a)
    if fiche.courant_nominal_a is None or fiche.courant_nominal_a <= 0:
        return _indetermine(code, libelle, None, unite, "courant nominal absent de la fiche moteur")
    ratio = round(i_max / fiche.courant_nominal_a, 4)
    note = f"I max = {i_max:g} A, In = {fiche.courant_nominal_a:g} A"
    return _appliquer_seuils(code, libelle, ratio, unite, rc.SEUILS_SURCHARGE_COURANT, note)


# ---------------------------------------------------------------------------
# Évaluation complète
# ---------------------------------------------------------------------------


def agreger(resultats: Sequence[ResultatRegle]) -> NiveauRisque:
    """Max des niveaux évalués. Si ce max est « normal » mais qu'une règle n'a pas pu être
    évaluée, on renvoie « indetermine » : on ne déclare pas normal ce qu'on n'a pas vérifié."""
    evalues = [r.niveau for r in resultats if r.niveau is not NiveauRisque.INDETERMINE]
    if not evalues:
        return NiveauRisque.INDETERMINE
    pire = max(evalues, key=lambda n: ORDRE_NIVEAUX[n])
    if pire is NiveauRisque.NORMAL and len(evalues) < len(resultats):
        return NiveauRisque.INDETERMINE
    return pire


def evaluer(
    fiche: FicheMoteur, mesure: ValeursMesure, vibration_precedente: float | None = None
) -> ResultatRegles:
    resultats = [
        regle_vibration(fiche, mesure.vibration_rms_mm_s),
        regle_desequilibre_tension(mesure),
        regle_desequilibre_courant(mesure),
        regle_surcharge_courant(fiche, mesure),
        regle_temperature_bobinage(fiche, mesure.temperature_bobinage_c),
        regle_temperature_roulements(mesure.temperature_roulements_c),
    ]
    non_evaluees: list[str] = []
    if vibration_precedente is None:
        non_evaluees.append("vibration_tendance : pas de mesure précédente")
    else:
        tendance = regle_tendance_vibration(fiche, mesure.vibration_rms_mm_s, vibration_precedente)
        if isinstance(tendance, str):
            non_evaluees.append(f"vibration_tendance : {tendance}")
        else:
            resultats.insert(1, tendance)
    return ResultatRegles(niveau_global=agreger(resultats), resultats=resultats, non_evaluees=non_evaluees)
