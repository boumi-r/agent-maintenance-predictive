"""Configuration du logging applicatif."""

from __future__ import annotations

import logging


def configurer_logging(niveau: str) -> None:
    logging.basicConfig(
        level=niveau.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
