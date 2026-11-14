"""Limitation de débit des endpoints qui appellent Claude (clé = organisation)."""

from __future__ import annotations

import math
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from limits import parse, storage, strategies

from app.api.deps import Principal, get_principal


class Limiteur:
    """Fenêtre glissante. Stockage memory:// par défaut (un seul processus) ou redis:// (multi-instances)."""

    def __init__(self, regle: str, storage_uri: str = "memory://") -> None:
        self._limite = parse(regle)
        self._strategie = strategies.MovingWindowRateLimiter(storage.storage_from_string(storage_uri))

    def consommer(self, cle: str) -> int | None:
        """Renvoie None si autorisé, sinon le nombre de secondes avant de réessayer."""
        if self._strategie.hit(self._limite, cle):
            return None
        stats = self._strategie.get_window_stats(self._limite, cle)
        return max(1, math.ceil(stats.reset_time - time.time()))


def limiter_analyse(request: Request, principal: Annotated[Principal, Depends(get_principal)]) -> None:
    limiteur: Limiteur = request.app.state.limiteur_analyse
    attente = limiteur.consommer(f"analyse:org:{principal.organisation_id}")
    if attente is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop d'analyses pour cette organisation. Réessayer dans {attente} s.",
            headers={"Retry-After": str(attente)},
        )
