"""Configuración básica de logging."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=numeric,
        stream=sys.stdout,
    )
