from __future__ import annotations

import math

import pytest

from app.services.electrique import desequilibre_nema, desequilibre_vuf_iec


def test_nema_equilibre_vaut_zero() -> None:
    assert desequilibre_nema(400, 400, 400) == 0


def test_nema_exemple_de_reference() -> None:
    # Exemple classique NEMA MG-1 : 460, 467, 450 V -> moyenne 459, écart max 9 -> 1,96 %
    assert desequilibre_nema(460, 467, 450) == pytest.approx(9 / 459 * 100)


def test_nema_ordre_des_phases_indifferent() -> None:
    assert desequilibre_nema(380, 381, 379) == desequilibre_nema(379, 380, 381)


def test_nema_corrige_la_formule_du_prototype() -> None:
    # Le prototype calculait max(|écarts entre phases|) / max × 100 = 2/381×100 ≈ 0,525 %.
    # NEMA : écart max à la moyenne (1 V) / moyenne (380 V) ≈ 0,263 %.
    assert desequilibre_nema(380, 381, 379) == pytest.approx(1 / 380 * 100)


def test_nema_courants() -> None:
    assert desequilibre_nema(15, 15, 18) == pytest.approx(2 / 16 * 100)


@pytest.mark.parametrize("valeurs", [(0, 0, 0), (-1, 0, 1), (math.nan, 10, 10), (-5, 10, 10)])
def test_nema_valeurs_invalides(valeurs: tuple[float, float, float]) -> None:
    assert desequilibre_nema(*valeurs) is None


def test_nema_une_phase_perdue() -> None:
    # Perte de phase : 0, 400, 400 -> moyenne 266,7, écart max 266,7 -> 100 %
    assert desequilibre_nema(0, 400, 400) == pytest.approx(100)


def test_vuf_equilibre_vaut_zero() -> None:
    assert desequilibre_vuf_iec(400, 400, 400) == pytest.approx(0, abs=1e-6)


def test_vuf_proche_de_nema_pour_faible_desequilibre() -> None:
    vuf = desequilibre_vuf_iec(460, 467, 450)
    assert vuf is not None
    # Pour de faibles déséquilibres, VUF et NEMA sont du même ordre (VUF un peu plus grand ici)
    assert 1.5 < vuf < 2.5


def test_vuf_triangle_impossible() -> None:
    assert desequilibre_vuf_iec(100, 100, 400) is None


def test_vuf_tensions_nulles() -> None:
    assert desequilibre_vuf_iec(0, 0, 0) is None
