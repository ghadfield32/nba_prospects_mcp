# ACB (Spanish Basketball) API Discovery Guide

Tools and documentation for discovering and implementing ACB (Liga ACB) data endpoints.

## Overview

ACB (Liga ACB) is Spain's top professional basketball league. The official website (www.acb.com) provides game schedules, box scores, and statistics. This guide helps discover and implement the endpoints for fetching this data.

## Current Implementation Status

### ✅ Available
- **Player Season**: Aggregated player statistics (fetch_acb_player_season)
- **Team Season**: Aggregated team statistics (fetch_acb_team_season)
- **Error Handling**: Comprehensive error handling with 403/timeout/connection error classification
- **Manual CSV Fallback**: Support for manual CSV files when website blocks automated requests
- **Zenodo Integration**: Historical data fallback (1983-2023 seasons)

### ❌ Requires Implementation
- **Schedule**: Game dates, teams, scores (fetch_acb_schedule)
- **Player Game**: Per-game player box scores (fetch_acb_box_score)
- **Team Game**: Per-game team box scores
- **Play-by-Play**: Event-level game data (fetch_acb_play_by_play)
- **Shot Chart**: Shot locations (fetch_acb_shot_chart)

## Known Challenges

### 1. 403 Access Denied Errors

ACB website frequently blocks automated requests. Solutions:

**A. Browser DevTools Approach (Recommended)**:
1. Open acb.com in browser
2. Open DevTools (F12) → Network tab → Filter by XHR/Fetch
3. Navigate to stats pages manually
4. Capture API endpoints and headers
5. Look for JSON responses

**B. Manual CSV Fallback**:
- For blocked data, create manual CSV files
- Place in `data/manual/acb/`
- Fetcher will automatically detect and use them
- See `src/cbb_data/fetchers/acb.py` for CSV schema

**C. Zenodo Historical Data**:
- Historical ACB seasons (1983-2023) available via Zenodo
- Automatic fallback for older seasons
- Current season requires manual CSV or API discovery

### 2. Dynamic JavaScript Content

ACB website may load data dynamically via JavaScript. If HTML scraping fails:
- Use Selenium or Playwright for JavaScript execution
- Or discover the JSON API endpoints it calls

## API Discovery Process

### Step 1: Identify Schedule Endpoint

1. Visit https://www.acb.com/calendario (or equivalent)
2. Open DevTools → Network tab → Filter XHR
3. Look for requests returning schedule data
4. Check response structure

Expected patterns:
```
- /api/calendar?season=2024
- /api/games?season=2024
- /estadisticas/calendario/...
```

### Step 2: Identify Box Score Endpoint

1. Visit a specific game page on acb.com
2. Open DevTools → Network tab
3. Look for requests containing box score data
4. Extract game ID format from URL

Expected patterns:
```
- /api/game/{game_id}/boxscore
- /api/game/{game_id}/stats
- /estadisticas/partidos/{game_id}
```

### Step 3: Document Headers and Parameters

For each endpoint, record:
- Full URL with parameters
- Required headers (User-Agent, Referer, cookies)
- Authentication requirements (API keys, tokens)
- Request method (GET/POST)
- Query parameters

### Step 4: Test with curl

Before implementing in Python, validate with curl:

```bash
# Example schedule request
curl "https://www.acb.com/api/calendar?season=2024" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Referer: https://www.acb.com/calendario" \
  -H "Accept: application/json"

# Check response:
# - 200 OK: Success
# - 403 Forbidden: Need different headers/cookies
# - 404 Not Found: Wrong endpoint
```

## Implementation Template

Once endpoints are discovered, implement in `src/cbb_data/fetchers/acb.py`:

### Schedule Implementation

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_schedule(season: str = "2024-25", season_type: str = "Regular Season") -> pd.DataFrame:
    """Fetch ACB schedule"""
    logger.info(f"Fetching ACB schedule: {season}")

    # Try API endpoint (adjust after discovery)
    try:
        url = f"https://www.acb.com/api/calendar"
        params = {"season": season}

        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Parse JSON structure (adjust based on actual format)
        games = data.get("games", [])

        df = pd.DataFrame([
            {
                "GAME_ID": game["id"],
                "SEASON": season,
                "GAME_DATE": game["date"],
                "HOME_TEAM": game["homeTeam"]["name"],
                "AWAY_TEAM": game["awayTeam"]["name"],
                "HOME_SCORE": game.get("homeScore"),
                "AWAY_SCORE": game.get("awayScore"),
                "LEAGUE": "ACB",
                "SOURCE": "acb_api"
            }
            for game in games
        ])

        return df

    except requests.HTTPError as e:
        # Handle errors with helper function
        return _handle_acb_error(e, "schedule", season, fallback_to_csv=True)
```

### Box Score Implementation

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_box_score(game_id: str) -> pd.DataFrame:
    """Fetch ACB box score for a game"""
    logger.info(f"Fetching ACB box score: {game_id}")

    try:
        url = f"https://www.acb.com/api/game/{game_id}/boxscore"

        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Parse player stats from both teams
        players = []
        for team in ["homeTeam", "awayTeam"]:
            for player in data[team]["players"]:
                players.append({
                    "GAME_ID": game_id,
                    "PLAYER_NAME": player["name"],
                    "TEAM": data[team]["name"],
                    "MIN": player.get("minutes"),
                    "PTS": player.get("points"),
                    "REB": player.get("rebounds"),
                    "AST": player.get("assists"),
                    # ... other stats
                    "LEAGUE": "ACB",
                    "SOURCE": "acb_api"
                })

        return pd.DataFrame(players)

    except requests.HTTPError as e:
        return _handle_acb_error(e, "box_score", game_id, fallback_to_csv=False)
```

## Manual CSV Fallback Format

If API discovery fails, create manual CSV files:

### Schedule CSV Format

`data/manual/acb/schedule_{season}.csv`:
```csv
GAME_ID,SEASON,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE,VENUE,LEAGUE
12345,2024-25,2024-10-01,Real Madrid,Barcelona,85,82,WiZink Center,ACB
12346,2024-25,2024-10-02,Valencia,Baskonia,90,88,La Fonteta,ACB
```

### Box Score CSV Format

`data/manual/acb/box_score_{game_id}.csv`:
```csv
GAME_ID,PLAYER_NAME,TEAM,MIN,PTS,FGM,FGA,FG_PCT,FG3M,FG3A,FG3_PCT,FTM,FTA,FT_PCT,OREB,DREB,REB,AST,STL,BLK,TOV,PF,LEAGUE
12345,Player A,Real Madrid,32,18,7,12,58.3,2,5,40.0,2,2,100.0,1,4,5,3,1,0,2,1,ACB
12345,Player B,Real Madrid,28,15,6,10,60.0,1,3,33.3,2,3,66.7,0,3,3,5,0,1,1,2,ACB
```

The fetcher will automatically detect and load these CSV files when API requests fail.

## Testing Implementation

After implementing endpoints:

1. **Unit Tests**: Add tests to `tests/test_acb_fetchers.py`
2. **Validation**: Compare scraped data with website display
3. **Schema Check**: Verify all required columns are present
4. **Error Handling**: Test 403/timeout/network error scenarios
5. **Manual CSV Fallback**: Test CSV loading when API fails

## Common Issues & Solutions

### Issue: 403 Forbidden

**Solution 1**: Add/update required headers
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 ...",
    "Referer": "https://www.acb.com/",
    "Accept": "application/json",
    # Add cookies if needed:
    # "Cookie": "session=...; token=..."
}
```

**Solution 2**: Use manual CSV fallback
- Document the CSV schema
- Users can create CSVs manually from acb.com
- Fetcher loads CSV automatically

### Issue: Dynamic JavaScript Content

**Solution**: Use Selenium/Playwright
```python
from selenium import webdriver

def fetch_with_javascript():
    driver = webdriver.Chrome()
    driver.get("https://www.acb.com/calendario")
    # Wait for content to load
    time.sleep(3)
    html = driver.page_source
    # Parse HTML with BeautifulSoup
    return html
```

### Issue: Changing URL Patterns

**Solution**: Version detection
```python
def detect_acb_api_version():
    """Detect which ACB API version is active"""
    # Try different endpoint patterns
    patterns = [
        "https://www.acb.com/api/v1/calendar",
        "https://www.acb.com/api/v2/calendar",
        "https://www.acb.com/estadisticas/calendario",
    ]
    for pattern in patterns:
        if test_endpoint(pattern):
            return pattern
    raise ValueError("Could not detect ACB API endpoint")
```

## Historical Data (Zenodo)

ACB historical data (1983-2023) is available via Zenodo:
- Dataset: `eurohoops/acb-historical-stats`
- Automatically used for seasons before 2024
- See `src/cbb_data/fetchers/acb.py` for integration

## Next Steps

1. **API Discovery**: Use browser DevTools to find endpoints
2. **Validation**: Test endpoints with curl
3. **Implementation**: Update fetch functions in acb.py
4. **Testing**: Add tests and validate against website
5. **Documentation**: Update this README with discovered endpoints

## References

- ACB Official Site: https://www.acb.com/
- Stats Page: https://www.acb.com/estadisticas
- Calendar: https://www.acb.com/calendario
- Related Files:
  - `src/cbb_data/fetchers/acb.py` - Main ACB fetcher
  - `docs/LEAGUE_WEB_SCRAPING_FINDINGS.md` - General scraping notes

## Last Updated

2025-11-14

## Maintainer

Data Engineering Team
