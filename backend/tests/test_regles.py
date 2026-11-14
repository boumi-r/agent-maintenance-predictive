"""Tests aux bornes de chaque seuil (juste en dessous / égal / au-dessus)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.models.enums import ClasseIsolation, GroupeIso20816, NiveauRisque, TypeFondation
from app.services import regles
from app.services.regles import FicheMoteur, ValeursMesure

N, S, E, CR, IND = (
    NiveauRisque.NORMAL,
    NiveauRisque.SURVEILLANCE,
    NiveauRisque.ELEVE,
    NiveauRisque.CRITIQUE,
    NiveauRisque.INDETERMINE,
)

FICHE = FicheMoteur(
    puissance_kw=75,
    courant_nominal_a=140,
    classe_isolation=ClasseIsolation.F,
    groupe_iso20816=GroupeIso20816.GROUPE_2,
    type_fondation=TypeFondation.RIGIDE,
)

MESURE_SAINE = ValeursMesure(
    tension_ph1_v=400,
    tension_ph2_v=400,
    tension_ph3_v=400,
    courant_ph1_a=120,
    courant_ph2_a=120,
    courant_ph3_a=120,
    vibration_rms_mm_s=1.0,
    temperature_roulements_c=60,
    temperature_bobinage_c=90,
)


# --- Vibration ISO 20816-3 ---------------------------------------------------


@pytest.mark.parametrize(
    ("groupe", "fondation", "bc", "cd"),
    [
        (GroupeIso20816.GROUPE_1, TypeFondation.RIGIDE, 4.5, 7.1),
        (GroupeIso20816.GROUPE_1, TypeFondation.FLEXIBLE, 7.1, 11.0),
        (GroupeIso20816.GROUPE_2, TypeFondation.RIGIDE, 2.8, 4.5),
        (GroupeIso20816.GROUPE_2, TypeFondation.FLEXIBLE, 4.5, 7.1),
    ],
)
def test_vibration_iso_20816_3_bornes(
    groupe: GroupeIso20816, fondation: TypeFondation, bc: float, cd: float
) -> None:
    fiche = replace(FICHE, groupe_iso20816=groupe, type_fondation=fondation)
    attendus = [(bc - 0.01, N), (bc, N), (bc + 0.01, E), (cd, E), (cd + 0.01, CR)]
    for valeur, niveau in attendus:
        r = regles.regle_vibration(fiche, valeur)
        assert r.niveau is niveau, (groupe, fondation, valeur)
        assert r.nature == "norme"
        assert "ISO 20816-3" in r.source


def test_vibration_zone_b_reste_normale() -> None:
    r = regles.regle_vibration(FICHE, 2.0)  # G2 rigide : zone B = 1.4 – 2.8
    assert r.niveau is N
    assert r.note is not None and r.note.startswith("zone B")


@pytest.mark.parametrize("puissance", [0.75, 7.5, 14.99])
def test_vibration_moins_de_15_kw_hors_champ(puissance: float) -> None:
    fiche = replace(FICHE, puissance_kw=puissance, groupe_iso20816=None, type_fondation=None)
    for valeur, niveau in [(1.8, N), (1.81, E), (4.5, E), (4.51, CR)]:
        r = regles.regle_vibration(fiche, valeur)
        assert r.niveau is niveau, valeur
        assert r.nature == "heuristique"
        assert "ISO 10816-1" in r.source
        assert r.note is not None and "hors champ ISO 20816-3" in r.note


def test_vibration_15_kw_pile_entre_dans_le_champ_iso() -> None:
    r = regles.regle_vibration(replace(FICHE, puissance_kw=15), 2.0)
    assert "ISO 20816-3" in r.source


@pytest.mark.parametrize(
    "fiche",
    [
        replace(FICHE, puissance_kw=None),
        replace(FICHE, groupe_iso20816=None),
        replace(FICHE, type_fondation=None),
    ],
)
def test_vibration_fiche_incomplete_indeterminee(fiche: FicheMoteur) -> None:
    assert regles.regle_vibration(fiche, 1.0).niveau is IND


# --- Tendance vibration (bande surveillance) ---------------------------------


def test_tendance_vibration_bornes() -> None:
    # G2 rigide : B/C = 2.8 -> seuil de hausse = 0.7 mm/s
    for hausse, niveau in [(0.69, N), (0.70, N), (0.71, S)]:
        r = regles.regle_tendance_vibration(FICHE, 1.0 + hausse, 1.0)
        assert not isinstance(r, str)
        assert r.niveau is niveau, hausse
        assert r.nature == "heuristique"


def test_tendance_baisse_est_normale() -> None:
    r = regles.regle_tendance_vibration(FICHE, 0.5, 2.0)
    assert not isinstance(r, str)
    assert r.niveau is N


def test_tendance_petit_moteur_utilise_classe_i() -> None:
    fiche = replace(FICHE, puissance_kw=5)
    r = regles.regle_tendance_vibration(fiche, 1.0 + 0.46, 1.0)  # 25 % de 1.8 = 0.45
    assert not isinstance(r, str)
    assert r.niveau is S


def test_tendance_fiche_incomplete() -> None:
    assert isinstance(regles.regle_tendance_vibration(replace(FICHE, puissance_kw=None), 2, 1), str)


# --- Déséquilibre de tension ------------------------------------------------


def _tensions(pct: float) -> ValeursMesure:
    """Tensions dont le déséquilibre NEMA vaut exactement pct (moyenne 400 V)."""
    d = 400 * pct / 100
    return replace(MESURE_SAINE, tension_ph1_v=400 + d, tension_ph2_v=400 - d / 2, tension_ph3_v=400 - d / 2)


@pytest.mark.parametrize(
    ("pct", "niveau", "nature"),
    [
        (0.99, N, "heuristique"),
        (1.0, N, "heuristique"),
        (1.01, S, "heuristique"),
        (2.0, S, "heuristique"),
        (2.01, E, "norme"),
        (5.0, E, "norme"),
        (5.01, CR, "norme"),
    ],
)
def test_desequilibre_tension_bornes(pct: float, niveau: NiveauRisque, nature: str) -> None:
    r = regles.regle_desequilibre_tension(_tensions(pct))
    assert r.valeur == pytest.approx(pct, abs=1e-3)
    assert r.niveau is niveau
    assert r.nature == nature


def test_desequilibre_tension_cite_les_sources() -> None:
    assert "EN 50160" in regles.regle_desequilibre_tension(_tensions(3)).source
    assert "NEMA" in regles.regle_desequilibre_tension(_tensions(6)).source
    assert regles.regle_desequilibre_tension(_tensions(3)).note is not None  # VUF informatif


def test_desequilibre_tension_nulle() -> None:
    m = replace(MESURE_SAINE, tension_ph1_v=0, tension_ph2_v=0, tension_ph3_v=0)
    assert regles.regle_desequilibre_tension(m).niveau is IND


# --- Déséquilibre de courant ------------------------------------------------


def _courants(pct: float) -> ValeursMesure:
    d = 100 * pct / 100
    return replace(MESURE_SAINE, courant_ph1_a=100 + d, courant_ph2_a=100 - d / 2, courant_ph3_a=100 - d / 2)


@pytest.mark.parametrize(
    ("pct", "niveau"),
    [(5.0, N), (5.01, S), (10.0, S), (10.01, E), (20.0, E), (20.01, CR)],
)
def test_desequilibre_courant_bornes(pct: float, niveau: NiveauRisque) -> None:
    r = regles.regle_desequilibre_courant(_courants(pct))
    assert r.niveau is niveau
    assert r.nature == "heuristique"


def test_desequilibre_courant_moteur_arrete() -> None:
    m = replace(MESURE_SAINE, courant_ph1_a=0, courant_ph2_a=0, courant_ph3_a=0)
    assert regles.regle_desequilibre_courant(m).niveau is IND


# --- Température bobinage ---------------------------------------------------


@pytest.mark.parametrize(
    ("classe", "limite"),
    [
        (ClasseIsolation.A, 105),
        (ClasseIsolation.E, 120),
        (ClasseIsolation.B, 130),
        (ClasseIsolation.F, 155),
        (ClasseIsolation.H, 180),
    ],
)
def test_bobinage_bornes(classe: ClasseIsolation, limite: float) -> None:
    fiche = replace(FICHE, classe_isolation=classe)
    attendus = [
        (limite - 20.1, N, "heuristique"),
        (limite - 20, S, "heuristique"),
        (limite - 10.1, S, "heuristique"),
        (limite - 10, E, "heuristique"),
        (limite - 0.1, E, "heuristique"),
        (limite, CR, "norme"),
    ]
    for valeur, niveau, nature in attendus:
        r = regles.regle_temperature_bobinage(fiche, valeur)
        assert r.niveau is niveau, (classe, valeur)
        assert r.nature == nature


def test_bobinage_sans_classe() -> None:
    assert regles.regle_temperature_bobinage(replace(FICHE, classe_isolation=None), 100).niveau is IND


# --- Température roulements -------------------------------------------------


@pytest.mark.parametrize(
    ("t", "niveau"),
    [(79.9, N), (80, S), (89.9, S), (90, E), (99.9, E), (100, CR)],
)
def test_roulements_bornes(t: float, niveau: NiveauRisque) -> None:
    r = regles.regle_temperature_roulements(t)
    assert r.niveau is niveau
    assert r.nature == "heuristique"


# --- Surcharge courant ------------------------------------------------------


@pytest.mark.parametrize(
    ("ratio", "niveau"),
    [(1.0, N), (1.01, S), (1.1, S), (1.11, E), (1.25, E), (1.26, CR)],
)
def test_surcharge_bornes(ratio: float, niveau: NiveauRisque) -> None:
    i = 140 * ratio
    m = replace(MESURE_SAINE, courant_ph1_a=i, courant_ph2_a=i, courant_ph3_a=i)
    assert regles.regle_surcharge_courant(FICHE, m).niveau is niveau


def test_surcharge_sans_courant_nominal() -> None:
    assert regles.regle_surcharge_courant(replace(FICHE, courant_nominal_a=None), MESURE_SAINE).niveau is IND


# --- Agrégation -------------------------------------------------------------


def test_evaluer_moteur_sain() -> None:
    res = regles.evaluer(FICHE, MESURE_SAINE)
    assert res.niveau_global is N
    assert {r.code for r in res.resultats} == {
        "vibration_zone",
        "desequilibre_tension",
        "desequilibre_courant",
        "surcharge_courant",
        "temperature_bobinage",
        "temperature_roulements",
    }
    assert res.non_evaluees == ["vibration_tendance : pas de mesure précédente"]


def test_evaluer_prend_le_pire_niveau() -> None:
    m = replace(MESURE_SAINE, temperature_roulements_c=85, vibration_rms_mm_s=5.0)
    assert regles.evaluer(FICHE, m).niveau_global is CR


def test_evaluer_tendance_ajoute_surveillance() -> None:
    res = regles.evaluer(FICHE, replace(MESURE_SAINE, vibration_rms_mm_s=2.0), vibration_precedente=1.0)
    assert res.niveau_global is S
    assert any(r.code == "vibration_tendance" for r in res.resultats)


def test_evaluer_fiche_incomplete_sans_anomalie_est_indeterminee() -> None:
    res = regles.evaluer(FicheMoteur(), MESURE_SAINE)
    assert res.niveau_global is IND


def test_evaluer_fiche_incomplete_avec_anomalie_garde_le_niveau() -> None:
    res = regles.evaluer(FicheMoteur(), replace(MESURE_SAINE, temperature_roulements_c=95))
    assert res.niveau_global is E


def test_agreger_liste_vide() -> None:
    assert regles.agreger([]) is IND


def test_en_dict_serialisable() -> None:
    import json

    d = regles.evaluer(FICHE, MESURE_SAINE, vibration_precedente=1.0).en_dict()
    json.dumps(d)
    assert d["version"] == "2026.11-1"
    assert d["niveau_global"] == "normal"
