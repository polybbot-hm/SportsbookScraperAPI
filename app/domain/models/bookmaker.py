"""Modelo de casa de apuestas."""
from enum import Enum


class BookmakerName(str, Enum):
    """Identificador de cada casa de apuestas."""

    CODERE = "codere"
    PAF = "paf"
    RETABET = "retabet"
    SPEEDY = "speedy"
    GRANMADRID = "granmadrid"
    KIROL = "kirol"
