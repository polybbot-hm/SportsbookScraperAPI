"""Jerarquía de excepciones de dominio para SportsbookScraperAPI."""


class SportsbookError(Exception):
    """Base de todas las excepciones de dominio."""

    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.context: dict = context or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.args[0]!r}, context={self.context!r})"


# ── Scraping ───────────────────────────────────────────────────────────────────

class ScrapingError(SportsbookError):
    """Error genérico durante el scraping de una casa de apuestas."""


class TokenCaptureError(ScrapingError):
    """No se pudo capturar el token de autenticación (p.ej. Casino Gran Madrid)."""


class EventsNotFoundError(ScrapingError):
    """La API o web no devolvió eventos para la liga/competición solicitada."""


class MarketParseError(ScrapingError):
    """Error al parsear o normalizar un mercado individual."""


class HttpRequestError(ScrapingError):
    """Fallo HTTP después de todos los reintentos."""

    def __init__(self, message: str, status_code: int | None = None, context: dict | None = None):
        super().__init__(message, context)
        self.status_code = status_code


# ── Persistencia ──────────────────────────────────────────────────────────────

class RepositoryError(SportsbookError):
    """Error genérico de persistencia."""


class ConnectionError(RepositoryError):
    """No se pudo conectar a la base de datos."""


class DocumentNotFoundError(RepositoryError):
    """Documento no encontrado en la base de datos."""


class SaveError(RepositoryError):
    """Error al guardar documentos en la base de datos."""


# ── Configuración ─────────────────────────────────────────────────────────────

class ConfigurationError(SportsbookError):
    """Error genérico de configuración."""


class MissingConfigError(ConfigurationError):
    """Falta un campo obligatorio en la configuración YAML."""


class InvalidConfigError(ConfigurationError):
    """Valor inválido en la configuración YAML."""


# ── Normalización ─────────────────────────────────────────────────────────────

class NormalizationError(SportsbookError):
    """Error al normalizar datos de mercados."""
