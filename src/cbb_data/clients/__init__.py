"""External API clients for basketball data sources

This module contains thin wrappers around 3rd-party basketball data APIs.

**Design Principles**:
- Thin adapters (wrap external APIs, don't reinvent)
- Aggressive caching (reduce API costs)
- Rate limit management (stay within quotas)
- Graceful degradation (empty DataFrame, not crash)

**Available Clients**:
- APIBasketballClient: api-sports.io (426 leagues worldwide)
"""

from .api_basketball import APIBasketballClient, get_api_basketball_league_id

__all__ = [
    "APIBasketballClient",
    "get_api_basketball_league_id",
]
