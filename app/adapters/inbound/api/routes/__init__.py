from app.adapters.inbound.api.routes.bookmakers_routes import router as bookmakers_router
from app.adapters.inbound.api.routes.comparison_routes import router as comparison_router
from app.adapters.inbound.api.routes.odds_routes import router as odds_router
from app.adapters.inbound.api.routes.scraping_routes import router as scraping_router

__all__ = ["scraping_router", "odds_router", "comparison_router", "bookmakers_router"]
