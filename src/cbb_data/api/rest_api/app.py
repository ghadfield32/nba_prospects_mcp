"""
FastAPI application for college basketball data API.

Main application setup with middleware, routes, and OpenAPI documentation.
"""

import logging
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .routes import router
from .middleware import add_middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Application Factory
# ============================================================================

def create_app(config: Dict[str, Any] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        config: Optional configuration dictionary with keys:
            - cors_origins: List of allowed CORS origins
            - rate_limit: Requests per minute limit
            - enable_logging: Enable request logging
            - title: API title
            - description: API description
            - version: API version

    Returns:
        Configured FastAPI application
    """
    if config is None:
        config = {}

    # Create FastAPI app with OpenAPI documentation
    app = FastAPI(
        title=config.get("title", "College Basketball Data API"),
        description=config.get(
            "description",
            """
# College Basketball Data API

A unified REST API for accessing college and international basketball data.

## Features

- **Multi-League Support**: NCAA Men's, NCAA Women's, and EuroLeague
- **8 Dataset Types**: Schedule, player stats, team stats, play-by-play, shots, and season aggregates
- **Flexible Filtering**: Filter by league, season, team, player, date, and more
- **High Performance**: Built-in caching for fast repeated queries
- **Historical Data**: 20+ years of basketball data

## Quick Start

### List Available Datasets
```
GET /datasets
```

### Query Player Stats
```
POST /datasets/player_game
{
    "filters": {
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke"]
    },
    "limit": 50
}
```

### Get Recent Games
```
GET /recent-games/NCAA-MBB?days=2
```

## Data Sources

- **ESPN**: NCAA Men's & Women's schedules, scores
- **CBBpy**: NCAA box scores and advanced stats
- **EuroLeague API**: Official EuroLeague data
- **DuckDB**: High-performance caching layer

## Rate Limiting

- Default: 60 requests per minute per IP
- Rate limit headers included in all responses
- Status 429 returned when limit exceeded

## Support

- Documentation: https://github.com/ghadfield32/nba_prospects_mcp
- Issues: https://github.com/ghadfield32/nba_prospects_mcp/issues
            """
        ),
        version=config.get("version", "1.0.0"),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "API Support",
            "url": "https://github.com/ghadfield32/nba_prospects_mcp"
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    )

    # Add middleware (CORS, rate limiting, error handling)
    add_middleware(app, config)

    # Include routes
    app.include_router(router)

    # Root endpoint - redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect root to API documentation."""
        return RedirectResponse(url="/docs")

    logger.info(
        f"FastAPI application created: {config.get('title', 'CBB Data API')} "
        f"v{config.get('version', '1.0.0')}"
    )

    return app


# ============================================================================
# Default Application Instance
# ============================================================================

# Create default app instance for direct import
app = create_app()

# Export for imports
__all__ = ["app", "create_app"]
