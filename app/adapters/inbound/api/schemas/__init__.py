from app.adapters.inbound.api.schemas.requests import (
    CompareQueryParams,
    OddsQueryParams,
    ScrapeRequest,
)
from app.adapters.inbound.api.schemas.responses import (
    BookmakerResponse,
    CompareItemResponse,
    EventResponse,
    OddsGroupedResponse,
    OddsItemResponse,
    PartidoSummary,
    ScrapeSummaryResponse,
    ScrapeStatusResponse,
)

__all__ = [
    "ScrapeRequest",
    "OddsQueryParams",
    "CompareQueryParams",
    "OddsItemResponse",
    "OddsGroupedResponse",
    "CompareItemResponse",
    "BookmakerResponse",
    "EventResponse",
    "ScrapeStatusResponse",
    "ScrapeSummaryResponse",
    "PartidoSummary",
]
