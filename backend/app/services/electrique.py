"""Grandeurs électriques dérivées des mesures triphasées.

Convention : tension_ph1..3 sont les tensions **composées** (entre phases), comme le
« 380 V » du prototype. La définition NEMA fonctionne aussi sur des tensions simples ;
le VUF (IEC) n'est valable que sur des tensions composées.
"""

from __future__ import annotations

import math


def desequilibre_nema(a: float, b: float, c: float) -> float | None:
    """Déséquilibre en % selon NEMA MG-1 (LVUR) : écart max à la moyenne / moyenne × 100.

    Utilisé pour la tension et pour le courant. Renvoie None si la moyenne est nulle ou
    négative (moteur à l'arrêt, capteur absent) : on ne fabrique pas de valeur.
    """
    valeurs = (a, b, c)
    if any(math.isnan(v) or v < 0 for v in valeurs):
        return None
    moyenne = sum(valeurs) / 3
    if moyenne <= 0:
        return None
    ecart_max = max(abs(v - moyenne) for v in valeurs)
    return ecart_max / moyenne * 100


def desequilibre_vuf_iec(uab: float, ubc: float, uca: float) -> float | None:
    """Facteur de déséquilibre VUF = V2/V1 × 100 (IEC 61000-2-1 / CEI), à partir des seules
    amplitudes des tensions composées (formule β, exacte car la somme vectorielle des tensions
    composées est nulle).

    Renvoie None si les trois amplitudes ne peuvent pas former un triangle (mesure incohérente).
    """
    carres = (uab**2, ubc**2, uca**2)
    somme = sum(carres)
    if somme <= 0:
        return None
    beta = sum(x**2 for x in carres) / somme**2
    discriminant = 3 - 6 * beta
    if discriminant < 0:
        return None
    racine = math.sqrt(discriminant)
    return math.sqrt((1 - racine) / (1 + racine)) * 100
