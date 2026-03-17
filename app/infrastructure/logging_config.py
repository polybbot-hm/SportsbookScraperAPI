"""Configuración de logging estructurado con structlog + contextvars."""
from __future__ import annotations

import logging
import logging.handlers
import sys
from contextlib import contextmanager
from typing import Any

import structlog
import structlog.contextvars


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    output: str = "stdout",
    file_path: str = "logs/app.log",
) -> None:
    """
    Inicializa structlog.

    Args:
        level:     Nivel de log (DEBUG, INFO, WARNING, ERROR).
        fmt:       Formato de salida: 'json' (producción) o 'console' (desarrollo).
        output:    Destino: 'stdout' o 'file'.
        file_path: Ruta del fichero de log (solo cuando output='file').
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Handler de destino
    if output == "file":
        import os
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    else:
        handler = logging.StreamHandler(sys.stdout)

    logging.basicConfig(
        format="%(message)s",
        handlers=[handler],
        level=numeric_level,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if fmt == "console"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ── Helpers de contexto ───────────────────────────────────────────────────────

def bind_scraping_context(bookmaker: str, competition_key: str | None = None) -> None:
    """Vincula contexto de scraping al log del hilo/coroutine actual."""
    structlog.contextvars.bind_contextvars(
        bookmaker=bookmaker,
        competition_key=competition_key,
    )


def unbind_scraping_context() -> None:
    structlog.contextvars.unbind_contextvars("bookmaker", "competition_key")


@contextmanager
def scraping_log_context(bookmaker: str, competition_key: str | None = None):
    """Context manager que vincula y libera el contexto de scraping automáticamente."""
    structlog.contextvars.bind_contextvars(
        bookmaker=bookmaker,
        competition_key=competition_key,
    )
    try:
        yield
    finally:
        structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> Any:
    """Factoría de logger estructurado."""
    return structlog.get_logger(name)


# Mantener compatibilidad con llamadas antiguas (debug: bool)
def configure_logging_legacy(debug: bool = False) -> None:
    configure_logging(
        level="DEBUG" if debug else "INFO",
        fmt="console" if debug else "json",
    )
