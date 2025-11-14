# LNB Pro A Game-Level Data Investigation Guide

**Status**: 🔍 INVESTIGATION REQUIRED
**Priority**: HIGH (critical for comprehensive LNB coverage)
**Last Updated**: 2025-11-14

---

## Overview

This guide outlines the investigation workflow for discovering and implementing **game-level data** for LNB Pro A (French professional basketball). Currently, LNB has **player_season** and **team_season** data via HTML scraping. The goal is to add:

- ✅ **schedule** - Game calendar with dates/teams/scores
- ✅ **player_game** - Per-game player box scores
- ✅ **team_game** - Per-game team box scores
- 🤔 **pbp** - Play-by-play (if available via FIBA route)
- 🤔 **shots** - Shot chart with X/Y coordinates (if available via FIBA route)

---

## Two Potential Scenarios

### **Scenario 1: LNB Stats Centre JSON API** (Most Likely)

**Evidence:**
- LNB uses a modern "Stats Centre" at https://lnb.fr/pro-a/statistiques
- Similar French league (LFB - women's) has Azure-hosted JSON API
- Website shows advanced filters (season, team, competition)

**Expected Endpoints:**
```
GET https://lnbstatscenter.azurewebsites.net/api/players?season=2024&division=PRO_A
GET https://lnbstatscenter.azurewebsites.net/api/teams?season=2024&division=PRO_A
GET https://lnbstatscenter.azurewebsites.net/api/games?season=2024&division=PRO_A
GET https://lnbstatscenter.azurewebsites.net/api/games/{game_id}/boxscore
```

**Data Available (if this route works):**
- ✅ schedule - Full game calendar
- ✅ player_game - Per-game box scores
- ✅ team_game - Per-game team stats
- ❌ pbp - Not typically available in stats center
- ❌ shots - Not typically available in stats center

**Implementation Path:**
1. Confirm endpoints via browser DevTools (see Section 3 below)
2. Test with `tools/lnb/api_discovery_helper.py --test-endpoint "URL"`
3. Document in `tools/lnb/discovered_endpoints.json`
4. Implement in `src/cbb_data/fetchers/lnb.py` (replace NotImplementedError stubs)

---

### **Scenario 2: FIBA LiveStats for FFBB Competitions** (Alternative)

**Evidence:**
- LNB Pro A is organized by FFBB (French Basketball Federation)
- FFBB uses FIBA LiveStats for international competitions (EuroBasket qualifiers, etc.)
- Same infrastructure as BCL/BAL/ABA/LKL (already implemented)

**Expected URL Pattern:**
```
https://fibalivestats.dcd.shared.geniussports.com/u/FFBB/{GAME_ID}/bs.html
https://fibalivestats.dcd.shared.geniussports.com/u/FFBB/{GAME_ID}/pbp.html
https://fibalivestats.dcd.shared.geniussports.com/data/{GAME_ID}/data.json
```

**Data Available (if this route works):**
- ✅ schedule - Via game index HTML scraping
- ✅ player_game - Via JSON API + HTML fallback
- ✅ team_game - Aggregated from player_game
- ✅ pbp - Full play-by-play with running score
- ✅ shots - Shot chart with X/Y coordinates

**Implementation Path:**
1. Find FFBB competition codes on FIBA LiveStats
2. Test with existing FIBA infrastructure:
   ```python
   from src.cbb_data.fetchers.fiba_html_common import (
       build_fiba_schedule_from_html,
       fetch_fiba_boxscore_json_or_html,
       fetch_fiba_pbp,
       fetch_fiba_shots
   )
   ```
3. Wire into `lnb.py` using shared FIBA utilities
4. Add `COMP_CODE = "FFBB_PROA"` constant

---

## Investigation Workflow (3 Phases)

### **Phase 1: Browser DevTools Investigation** (30-60 minutes)

**Goal**: Determine which scenario applies (Stats Centre API vs FIBA LiveStats)

**Step 1A - Test Stats Centre API:**

1. Open https://lnb.fr/pro-a/statistiques in Chrome/Firefox
2. Open DevTools (F12) → Network tab → Filter: "XHR" or "Fetch"
3. Select season "2024-25" from dropdown
4. Filter by team, position, etc.
5. **Look for API requests**:
   - Azure domains: `lnbstatscenter.azurewebsites.net`
   - JSON responses with player/team/game data
   - Query parameters: `?season=2024&division=PRO_A`

**Step 1B - Test FIBA LiveStats Route:**

1. Visit https://www.fiba.basketball/
2. Search for "France" or "FFBB" competitions
3. Check if LNB Pro A games listed
4. Click on a game → Check URL structure:
   - If `fibalivestats.dcd.shared.geniussports.com` → Scenario 2 confirmed
   - If redirects to `lnb.fr` → Scenario 1 more likely

**Step 1C - Test Game Pages:**

1. Visit https://lnb.fr/pro-a/calendrier-resultats
2. Click on a completed game
3. Open DevTools → Network tab
4. **Look for**:
   - Box score API calls (`/api/games/{game_id}/boxscore`)
   - Embedded JSON in `<script>` tags (`window.__INITIAL_STATE__`)
   - FIBA LiveStats iframe or redirect

**Record Your Findings:**

Create a file: `docs/lnb_investigation_findings.md`

```markdown
# LNB Investigation Findings

**Date**: 2025-11-14
**Investigator**: [Your Name]

## Scenario Determination

- [ ] **Scenario 1** (Stats Centre JSON API) - Evidence:
  - Azure domain found: Yes/No
  - API endpoints discovered: [list URLs]
  - Sample JSON structure: [paste snippet]

- [ ] **Scenario 2** (FIBA LiveStats) - Evidence:
  - FIBA competition code found: [e.g., "FFBB_PROA"]
  - Sample game URL: [paste URL]
  - JSON API accessible: Yes/No

- [ ] **Scenario 3** (HTML-only, no JSON APIs)
  - Game data embedded in HTML
  - Requires advanced HTML scraping
  - May need Selenium/Playwright

## Discovered Endpoints

### Player Game Stats
- URL:
- Method:
- Params:
- Response structure:

### Team Game Stats
- URL:
- Method:
- Params:
- Response structure:

### Schedule
- URL:
- Method:
- Params:
- Response structure:
```

---

### **Phase 2: Endpoint Testing & Validation** (30-60 minutes)

**Goal**: Confirm discovered endpoints work and return expected data

**For Scenario 1 (Stats Centre API):**

```bash
# Test player stats endpoint
python tools/lnb/api_discovery_helper.py --test-endpoint \
  "https://lnbstatscenter.azurewebsites.net/api/players?season=2024&division=PRO_A"

# Test game schedule endpoint
python tools/lnb/api_discovery_helper.py --test-endpoint \
  "https://lnbstatscenter.azurewebsites.net/api/games?season=2024&division=PRO_A"

# Test box score endpoint (replace GAME_ID)
python tools/lnb/api_discovery_helper.py --test-endpoint \
  "https://lnbstatscenter.azurewebsites.net/api/games/12345/boxscore"
```

**Check Output:**
- ✅ Status Code: 200 (success)
- ✅ Valid JSON response
- ✅ Contains player names, stats, teams
- ✅ Sample saved to `tools/lnb/sample_responses/`

**For Scenario 2 (FIBA LiveStats):**

```python
# Test in Python REPL
from src.cbb_data.fetchers.fiba_html_common import (
    build_fiba_schedule_from_html,
    fetch_fiba_boxscore_json_or_html
)

# Test schedule fetch (replace COMP_CODE)
schedule = build_fiba_schedule_from_html(
    comp_code="FFBB_PROA",  # Or discovered code
    season="2024"
)
print(f"Found {len(schedule)} games")

# Test box score fetch (replace GAME_ID)
boxscore = fetch_fiba_boxscore_json_or_html(
    game_id="123456",
    comp_code="FFBB_PROA"
)
print(f"Found {len(boxscore)} player-game records")
```

**Validation Checklist:**
- [ ] Schedule: Returns list of games with dates, teams, scores
- [ ] Player game: Returns box scores with PTS, REB, AST, etc.
- [ ] Team game: Aggregatable from player_game or separate endpoint
- [ ] PBP: Available (Scenario 2 only)
- [ ] Shots: Available (Scenario 2 only)
- [ ] Historical data: Works for past seasons (2023-24, 2022-23, etc.)

---

### **Phase 3: Implementation** (2-4 hours)

**Goal**: Replace NotImplementedError stubs in `lnb.py` with working code

**For Scenario 1 (Stats Centre API):**

1. **Document endpoints** in `tools/lnb/discovered_endpoints.json`:

```json
{
  "schedule": {
    "url": "https://lnbstatscenter.azurewebsites.net/api/games",
    "method": "GET",
    "params": {
      "season": "2024",
      "division": "PRO_A"
    },
    "response_key": "games"
  },
  "player_game": {
    "url": "https://lnbstatscenter.azurewebsites.net/api/games/{game_id}/boxscore",
    "method": "GET",
    "response_key": "players"
  }
}
```

2. **Generate code skeleton**:

```bash
python tools/lnb/api_discovery_helper.py --generate-code
```

3. **Implement in `lnb.py`** (replace lines 421-456):

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_schedule(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A schedule via Stats Centre API"""
    rate_limiter.acquire("lnb")

    url = "https://lnbstatscenter.azurewebsites.net/api/games"
    params = {"season": season, "division": "PRO_A"}

    response = requests.get(url, params=params, headers=LNB_HEADERS, timeout=15)
    response.raise_for_status()

    data = response.json()
    games = data.get("games", [])

    df = pd.DataFrame([
        {
            "GAME_ID": game.get("id"),
            "GAME_DATE": game.get("date"),
            "HOME_TEAM": game.get("homeTeam"),
            "AWAY_TEAM": game.get("awayTeam"),
            "HOME_SCORE": game.get("homeScore"),
            "AWAY_SCORE": game.get("awayScore"),
            "LEAGUE": "LNB_PROA",
            "SEASON": season,
            "COMPETITION": "LNB Pro A",
            "SOURCE": "lnb_statscenter_api"
        }
        for game in games
    ])

    return df

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A player game stats via Stats Centre API"""
    # 1. Get schedule first
    schedule = fetch_lnb_schedule(season)

    if schedule.empty:
        logger.warning(f"No schedule for {season}, cannot fetch player_game")
        return pd.DataFrame()

    # 2. Fetch box score for each game
    all_player_games = []

    for game_id in schedule["GAME_ID"].unique():
        rate_limiter.acquire("lnb")

        url = f"https://lnbstatscenter.azurewebsites.net/api/games/{game_id}/boxscore"

        try:
            response = requests.get(url, headers=LNB_HEADERS, timeout=15)
            response.raise_for_status()

            data = response.json()
            players = data.get("players", [])

            for player in players:
                all_player_games.append({
                    "GAME_ID": game_id,
                    "PLAYER_NAME": player.get("name"),
                    "TEAM": player.get("team"),
                    "MIN": player.get("minutes"),
                    "PTS": player.get("points"),
                    "REB": player.get("rebounds"),
                    "AST": player.get("assists"),
                    # ... other stats
                    "LEAGUE": "LNB_PROA",
                    "SEASON": season,
                    "SOURCE": "lnb_statscenter_api"
                })

        except Exception as e:
            logger.error(f"Failed to fetch game {game_id}: {e}")
            continue

    return pd.DataFrame(all_player_games)
```

**For Scenario 2 (FIBA LiveStats):**

1. **Update `lnb.py`** to use shared FIBA utilities:

```python
# At top of lnb.py
from .fiba_html_common import (
    build_fiba_schedule_from_html,
    fetch_fiba_boxscore_json_or_html,
    fetch_fiba_pbp,
    fetch_fiba_shots
)

# Constants
LNB_FIBA_COMP_CODE = "FFBB_PROA"  # Or discovered code

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_schedule(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A schedule via FIBA LiveStats"""
    logger.info(f"Fetching LNB schedule via FIBA LiveStats: {season}")

    df = build_fiba_schedule_from_html(
        comp_code=LNB_FIBA_COMP_CODE,
        season=season
    )

    # Add LNB-specific columns
    df["LEAGUE"] = "LNB_PROA"
    df["COMPETITION"] = "LNB Pro A"
    df["SOURCE"] = "fiba_livestats_html"

    return df

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_lnb_player_game(season: str = "2024") -> pd.DataFrame:
    """Fetch LNB Pro A player game via FIBA LiveStats"""
    # Get schedule first
    schedule = fetch_lnb_schedule(season)

    if schedule.empty:
        return pd.DataFrame()

    # Fetch box scores for all games
    all_games = []

    for game_id in schedule["GAME_ID"].unique():
        rate_limiter.acquire("lnb")

        game_df = fetch_fiba_boxscore_json_or_html(
            game_id=game_id,
            comp_code=LNB_FIBA_COMP_CODE
        )

        if not game_df.empty:
            game_df["LEAGUE"] = "LNB_PROA"
            game_df["SEASON"] = season
            all_games.append(game_df)

    return pd.concat(all_games, ignore_index=True) if all_games else pd.DataFrame()

# Similar for fetch_lnb_pbp() and fetch_lnb_shots()
```

2. **Update `golden_lnb.py`** to include game-level data:

```python
def fetch_schedule(self) -> pd.DataFrame:
    """Fetch LNB schedule (now available!)"""
    try:
        df = lnb.fetch_lnb_schedule(self.season)
        logger.info(f"Fetched {len(df)} LNB games")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch LNB schedule: {e}")
        return pd.DataFrame()

def fetch_player_game(self) -> pd.DataFrame:
    """Fetch LNB player game (now available!)"""
    try:
        df = lnb.fetch_lnb_player_game(self.season)
        logger.info(f"Fetched {len(df)} LNB player-game records")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch LNB player_game: {e}")
        return pd.DataFrame()
```

---

## Success Criteria

**Minimum Viable (Must Have):**
- ✅ Schedule with game dates, teams, scores for current season
- ✅ Player game box scores (PTS, REB, AST, MIN, etc.)
- ✅ Team game aggregates (derived from player_game)
- ✅ Historical data back to 2020-21 season minimum

**Nice to Have (Bonus):**
- ⭐ Play-by-play data (Scenario 2 only)
- ⭐ Shot chart with X/Y coordinates (Scenario 2 only)
- ⭐ Historical data back to 2015-16 season
- ⭐ Playoff game differentiation

---

## Troubleshooting

### Issue: No API endpoints found in DevTools

**Solutions:**
1. Try different browsers (Chrome, Firefox, Edge)
2. Disable ad blockers and privacy extensions
3. Check "All" filter in Network tab, not just "XHR"
4. Look for WebSocket connections
5. Inspect `<script>` tags for embedded JSON: `window.__INITIAL_STATE__`

### Issue: API returns 403 Forbidden

**Solutions:**
1. Copy exact headers from browser request (F12 → Network → Right-click request → Copy as cURL)
2. Include `Referer: https://lnb.fr/` header
3. Check if cookies/authentication tokens needed
4. Try from different IP (not container - may be blocked)
5. Add realistic User-Agent header

### Issue: API returns empty data

**Solutions:**
1. Verify season format: "2024" vs "2024-25" vs "24-25"
2. Check competition parameter: "PRO_A" vs "PROA" vs "betclic_elite"
3. Ensure division filter correct: "PRO_A" not "PRO_B"
4. Try different seasons (current vs previous)

### Issue: JSON structure different than expected

**Solutions:**
1. Save sample response: `tools/lnb/sample_responses/`
2. Inspect actual keys: `data.keys()`, `data['players'][0].keys()`
3. Update column mapping in implementation
4. Check for nested structures: `data['result']['players']`

---

## Next Steps After Implementation

1. **Test with golden script**:
   ```bash
   python scripts/golden_lnb.py --season 2024-25
   ```

2. **Validate data quality**:
   - Check for duplicates: `df[df.duplicated(['GAME_ID', 'PLAYER_ID'])]`
   - Verify scores: PBP final score should match team_game PTS
   - Confirm game counts: Schedule should match team_game/2

3. **Update documentation**:
   - Mark LNB as ✅ COMPLETE in `docs/DATA_COVERAGE_INTERNATIONAL.md`
   - Add findings to `docs/lnb_investigation_findings.md`
   - Update `PROJECT_LOG.md` with implementation details

4. **Create PR**:
   ```bash
   git add .
   git commit -m "feat: Add LNB game-level data via [Scenario 1/2]"
   git push -u origin claude/add-data-sources-01FK5MDUR2DKLSF5QdHJxKJU
   ```

---

## Questions? Need Help?

**If you get stuck:**
1. Review existing implementations:
   - FIBA route: `src/cbb_data/fetchers/bcl.py`
   - Stats Centre pattern: `src/cbb_data/fetchers/gleague.py` (if exists)
   - HTML scraping: `src/cbb_data/fetchers/acb.py`

2. Check existing tools:
   - `tools/lnb/api_discovery_helper.py` for endpoint testing
   - `src/cbb_data/utils/data_qa.py` for validation helpers

3. Document blockers in `docs/lnb_investigation_findings.md`

---

**Good luck with the investigation! 🏀🇫🇷**
