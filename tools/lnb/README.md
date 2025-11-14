# LNB Pro A API Discovery Guide

Tools and documentation for discovering and validating LNB Pro A (French basketball) API endpoints.

## Overview

LNB Pro A's official website (lnb.fr) uses a JavaScript-driven "Stats Centre" that loads data dynamically via XHR/Fetch requests. This guide shows how to discover these API endpoints using browser DevTools.

## Current Implementation Status

### ✅ Available
- **Team Season**: Via standings page HTML scraping (`fetch_lnb_team_season()`)

### ❌ Requires API Discovery
- **Player Season**: Player statistics (PTS, REB, AST, etc.)
- **Schedule**: Game dates, teams, scores
- **Player Game**: Per-game player box scores
- **Team Game**: Per-game team box scores
- **Play-by-Play**: Event-level game data
- **Shots**: Shot locations (if available)

## API Discovery Process

### Step 1: Open Stats Centre in Browser

1. Visit https://www.lnb.fr/pro-a/statistiques
2. Navigate to the player statistics section
3. Open browser DevTools (F12 or Right-click → Inspect)
4. Switch to the **Network** tab
5. Filter by **XHR** or **Fetch** requests

### Step 2: Identify API Endpoints

Click through different filters/tabs in the Stats Centre and watch for JSON responses:

```
Expected patterns:
- /api/stats/players?season=2024&...
- /api/players/season/2024
- /stats/json/players.json
- Similar patterns for games, teams, schedules
```

### Step 3: Inspect Response Structure

Click on a captured request in DevTools:
1. Check the **Response** tab to see JSON structure
2. Check the **Headers** tab for:
   - Request URL (full endpoint)
   - Query parameters (season, team, date, etc.)
   - Required headers (User-Agent, Referer, cookies, etc.)
   - Authentication (API keys, tokens, etc.)

### Step 4: Document Endpoint Patterns

Create a mapping of discovered endpoints:

```python
# Example endpoint patterns (to be discovered)
LNB_API_ENDPOINTS = {
    "player_season": "https://www.lnb.fr/api/stats/players?season={season}",
    "schedule": "https://www.lnb.fr/api/games?season={season}",
    "box_score": "https://www.lnb.fr/api/games/{game_id}/boxscore",
    "team_stats": "https://www.lnb.fr/api/stats/teams?season={season}",
}
```

### Step 5: Test Endpoints with curl

Before implementing in Python, validate with curl:

```bash
# Example (adjust based on discovered endpoints)
curl "https://www.lnb.fr/api/stats/players?season=2024" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Referer: https://www.lnb.fr/pro-a/statistiques"

# Check response:
# - 200 OK: Success (proceed with implementation)
# - 403 Forbidden: Need authentication or headers
# - 404 Not Found: Wrong endpoint
```

## Implementation Template

Once endpoints are discovered, create `src/cbb_data/fetchers/lnb_api.py`:

```python
"""LNB Pro A API Client

Client for LNB Pro A Stats Centre API (discovered via browser DevTools).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Discovered API endpoints (UPDATE AFTER DISCOVERY)
LNB_BASE_URL = "https://www.lnb.fr"
LNB_API_BASE = f"{LNB_BASE_URL}/api"  # Adjust based on actual endpoints

class LnbApiClient:
    """Client for LNB Pro A Stats Centre API"""

    def __init__(self, rate_limit_seconds: float = 0.5):
        self.rate_limit = rate_limit_seconds
        self.last_request_time = 0

        # Headers (adjust based on requirements)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.lnb.fr/pro-a/statistiques",
            "Accept": "application/json",
        }

    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def fetch_player_season(self, season: str) -> pd.DataFrame:
        """Fetch player season statistics

        Args:
            season: Season year (e.g., "2024" for 2024-25)

        Returns:
            DataFrame with player statistics
        """
        self._rate_limit()

        # TODO: Update endpoint after discovery
        url = f"{LNB_API_BASE}/stats/players"
        params = {"season": season}

        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # TODO: Parse response structure
        # df = pd.json_normalize(data['players'])  # Adjust key
        # return df

        raise NotImplementedError("Update after API discovery")

    def fetch_schedule(self, season: str) -> pd.DataFrame:
        """Fetch game schedule"""
        raise NotImplementedError("Update after API discovery")

    def fetch_box_score(self, game_id: str) -> pd.DataFrame:
        """Fetch game box score"""
        raise NotImplementedError("Update after API discovery")
```

## Validation Checklist

After implementing API client:

- [ ] Player season stats match website display
- [ ] Schedule includes all games for season
- [ ] Box scores sum to team totals
- [ ] Data types are correct (int for counts, float for percentages)
- [ ] Player/team names are consistent
- [ ] Date formats are standardized (YYYY-MM-DD)
- [ ] Rate limiting is respected (0.5-1 sec between requests)
- [ ] Error handling for:
  - Missing games (404)
  - Rate limits (429)
  - Network errors (timeouts)
  - Invalid seasons

## Common Issues

### Issue: 403 Forbidden
**Solution**: Add required headers (User-Agent, Referer). Check if cookies are needed.

### Issue: Empty Response
**Solution**: Verify query parameters match what browser sends.

### Issue: Different JSON Structure
**Solution**: Different endpoints may have different formats. Parse each carefully.

### Issue: Rate Limiting (429)
**Solution**: Increase rate_limit_seconds (try 1.0 or 2.0).

## Historical Data

Based on initial exploration:
- **Availability**: Unknown (depends on API implementation)
- **Expected Range**: Current season + possibly 1-2 past seasons
- **Older Data**: May require manual CSV creation or Zenodo historical archives

## Integration with Main Fetcher

Once API client is implemented, update `src/cbb_data/fetchers/lnb.py`:

```python
from .lnb_api import LnbApiClient

_api_client = LnbApiClient()

def fetch_lnb_player_season(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A player season statistics

    Uses Stats Centre API (discovered via browser DevTools).
    """
    try:
        df = _api_client.fetch_player_season(season)
        df["LEAGUE"] = "LNB_PROA"
        df["SEASON"] = season
        return df
    except Exception as e:
        logger.error(f"Failed to fetch LNB player season: {e}")
        return pd.DataFrame()
```

## Next Steps

1. **API Discovery**: Use browser DevTools to find endpoints
2. **Validation**: Test endpoints with curl
3. **Implementation**: Create `lnb_api.py` with discovered patterns
4. **Testing**: Validate against website data
5. **Documentation**: Update this README with discovered endpoints
6. **Integration**: Update main LNB fetcher

## References

- LNB Official Site: https://www.lnb.fr/
- Stats Centre: https://www.lnb.fr/pro-a/statistiques
- Related Doc: `docs/LEAGUE_WEB_SCRAPING_FINDINGS.md`

## Last Updated

2025-11-14

## Maintainer

Data Engineering Team
