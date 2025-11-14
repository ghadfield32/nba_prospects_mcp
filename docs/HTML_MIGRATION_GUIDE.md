# HTML-Only Migration Guide

Step-by-step guide for migrating international basketball league fetchers from API/JSON to HTML-only sources.

**Date**: 2025-11-14

---

## Quick Overview

**Goal**: Replace JSON API dependencies with pure HTML scraping for all international leagues.

**What Changed**:
- ✅ Created: `src/cbb_data/fetchers/html_scrapers.py` (generic HTML utilities)
- ⏳ Update: `src/cbb_data/fetchers/fiba_html_common.py` (add schedule + shot chart)
- ⏳ Update: `src/cbb_data/fetchers/bcl.py` (template for other FIBA leagues)
- ⏳ Update: `src/cbb_data/fetchers/acb.py` (HTML implementation)
- ⏳ Update: `src/cbb_data/fetchers/lnb.py` (HTML implementation)

---

## Step 1: Add Functions to FIBA HTML Common

**File**: `src/cbb_data/fetchers/fiba_html_common.py`

Add these two functions at the end of the file (before `if __name__ == "__main__"` if it exists):

```python
# ==============================================================================
# Schedule Builder from HTML
# ==============================================================================


def build_fiba_schedule_from_html(
    league_code: str,
    season: str,
    schedule_url: str,
) -> pd.DataFrame:
    """
    Build FIBA league schedule by scraping league website HTML.

    Scrapes league schedule pages that link to FIBA LiveStats boxscores.
    Extracts game IDs from fibalivestats.dcd.shared.geniussports.com links.

    This function replaces manual game index CSV creation with automatic
    HTML scraping of league websites.

    Args:
        league_code: FIBA league code (e.g., "BCL", "BAL", "ABA", "LKL")
        season: Season string (e.g., "2023-24")
        schedule_url: URL of league's schedule/results page

    Returns:
        DataFrame with columns:
        - LEAGUE: Standardized league name
        - SEASON: Season string
        - GAME_ID: FIBA game ID (integer)
        - GAME_DATE: Date of game (if extractable)
        - HOME_TEAM: Home team name (if extractable)
        - AWAY_TEAM: Away team name (if extractable)
        - HOME_SCORE: Final home score (if game completed)
        - AWAY_SCORE: Final away score (if game completed)
        - COMPETITION_PHASE: Phase (Regular Season, Playoffs, etc.)
        - FIBA_URL: Link to FIBA LiveStats page

    Example:
        >>> df = build_fiba_schedule_from_html(
        ...     "BCL",
        ...     "2023-24",
        ...     "https://www.championsleague.basketball/schedule"
        ... )
        >>> print(f"Found {len(df)} games")

    Note:
        This uses the generic scraper from html_scrapers.py.
        Some metadata (team names, dates) may need to be filled
        from boxscore pages if not extractable from schedule HTML.
    """
    from .html_scrapers import scrape_fiba_schedule_page

    logger.info(f"Building {league_code} {season} schedule from HTML")

    df = scrape_fiba_schedule_page(schedule_url, league_code, season)

    if df.empty:
        logger.warning(f"No games found at {schedule_url}")
        return pd.DataFrame()

    # Add standardized league name (may differ from FIBA code)
    df["LEAGUE"] = league_code  # Or map to standard name if needed

    logger.info(f"Built schedule with {len(df)} games")

    return df


# ==============================================================================
# Shot Chart HTML Scraper
# ==============================================================================


def scrape_fiba_shots(
    league_code: str,
    game_id: str | int,
    league: str | None = None,
    season: str | None = None,
) -> pd.DataFrame:
    """
    Scrape shot chart data from FIBA LiveStats HTML pages.

    Extracts shot coordinates (X, Y) and metadata from FIBA's shot chart
    HTML pages or embedded JSON in boxscore pages.

    Args:
        league_code: FIBA league code (e.g., "BCL", "BAL")
        game_id: FIBA game ID
        league: Optional standardized league name
        season: Optional season string

    Returns:
        DataFrame with columns:
        - GAME_ID: Game ID
        - LEAGUE: League name
        - TEAM_ID: Team ID
        - TEAM_NAME: Team name
        - PLAYER_ID: Player ID
        - PLAYER_NAME: Player name
        - PERIOD: Quarter/period
        - GAME_CLOCK: Time remaining
        - X: X coordinate (0-100 normalized or absolute)
        - Y: Y coordinate (0-100 normalized or absolute)
        - SHOT_VALUE: Points (2 or 3)
        - MADE: 1 if made, 0 if missed
        - SHOT_TYPE: Type of shot
        - SOURCE: "fiba_html_shotchart"

    Example:
        >>> df = scrape_fiba_shots("BCL", "123456", league="BCL", season="2023-24")
        >>> print(f"Found {len(df)} shots")

    Note:
        Shot coordinate availability depends on league and season.
        Some games may not have detailed shot chart data.
    """
    from .html_scrapers import scrape_fiba_shot_chart_html

    logger.info(f"Scraping shots for {league_code} game {game_id}")

    game_id_int = int(game_id) if isinstance(game_id, str) else game_id

    df = scrape_fiba_shot_chart_html(league_code, game_id_int)

    if df.empty:
        logger.warning(f"No shot data found for game {game_id}")
        return pd.DataFrame()

    # Add league and season if provided
    if league:
        df["LEAGUE"] = league

    if season:
        df["SEASON"] = season

    logger.info(f"Scraped {len(df)} shots from game {game_id}")

    return df
```

---

## Step 2: Update BCL Fetcher (Template for Other FIBA Leagues)

**File**: `src/cbb_data/fetchers/bcl.py`

### 2.1: Add Schedule HTML Function

Add this function (around line 100, after the imports section):

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_bcl_schedule_html(season: str = "2023-24") -> pd.DataFrame:
    """
    Fetch BCL schedule by scraping championsleague.basketball HTML pages.

    **HTML-ONLY**: This function scrapes public HTML pages and does not
    require any API keys or authentication.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with BCL schedule

    Example:
        >>> df = fetch_bcl_schedule_html("2023-24")
        >>> print(df[['GAME_ID', 'GAME_DATE', 'HOME_TEAM', 'AWAY_TEAM']])

    Note:
        This replaces manual game index CSV creation. Game IDs are
        extracted directly from FIBA LiveStats links on the BCL website.
    """
    logger.info(f"Fetching BCL schedule for {season} (HTML scraping)")

    from .fiba_html_common import build_fiba_schedule_from_html

    # BCL schedule URL
    # Note: May need season parameter or filtering in URL
    schedule_url = "https://www.championsleague.basketball/schedule"

    df = build_fiba_schedule_from_html(
        league_code=FIBA_LEAGUE_CODE,  # "BCL"
        season=season,
        schedule_url=schedule_url,
    )

    if df.empty:
        logger.warning(f"No BCL games found for {season}")
        return pd.DataFrame()

    # Ensure standard columns
    df = ensure_standard_columns(df, "schedule")

    logger.info(f"Fetched {len(df)} BCL games for {season}")

    return df
```

### 2.2: Add Shot Chart HTML Function

Add this function:

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_bcl_shots_html(season: str = "2023-24") -> pd.DataFrame:
    """
    Fetch BCL shot chart data by scraping FIBA LiveStats HTML.

    **HTML-ONLY**: Extracts shot coordinates from FIBA HTML pages.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with shot data including X/Y coordinates

    Example:
        >>> df = fetch_bcl_shots_html("2023-24")
        >>> print(df[['PLAYER_NAME', 'X', 'Y', 'SHOT_VALUE', 'MADE']])

    Note:
        Shot coordinate availability depends on FIBA's HTML structure.
        Some games may not have complete shot chart data.
    """
    logger.info(f"Fetching BCL shots for {season} (HTML scraping)")

    from .fiba_html_common import load_fiba_game_index, scrape_fiba_shots

    # Load game index
    game_index = load_fiba_game_index(FIBA_LEAGUE_CODE, season)

    if game_index.empty:
        logger.warning(f"No game index found for BCL {season}")
        return pd.DataFrame()

    # Scrape shots for each game
    all_shots = []

    for _, game in game_index.iterrows():
        game_id = game["GAME_ID"]

        df_shots = scrape_fiba_shots(
            league_code=FIBA_LEAGUE_CODE,
            game_id=game_id,
            league=LEAGUE,
            season=season,
        )

        if not df_shots.empty:
            all_shots.append(df_shots)

        # Rate limiting handled by scraper

    if not all_shots:
        logger.warning(f"No shot data found for BCL {season}")
        return pd.DataFrame()

    df = pd.concat(all_shots, ignore_index=True)

    # Ensure standard columns
    df = ensure_standard_columns(df, "shots")

    logger.info(f"Fetched {len(df)} shots for BCL {season}")

    return df
```

### 2.3: Update Main fetch_schedule Function

Find the `fetch_schedule()` function and update it to use HTML:

```python
# OLD VERSION (JSON first):
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_schedule(season: str = "2023-24") -> pd.DataFrame:
    """Fetch BCL schedule"""
    return load_fiba_game_index(FIBA_LEAGUE_CODE, season)

# NEW VERSION (HTML scraping):
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_schedule(season: str = "2023-24") -> pd.DataFrame:
    """
    Fetch BCL schedule from HTML or game index.

    Tries HTML scraping first, falls back to game index CSV if available.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with BCL schedule
    """
    logger.info(f"Fetching BCL schedule for {season}")

    # Try HTML scraping first
    try:
        df = fetch_bcl_schedule_html(season)

        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"HTML scraping failed: {e}, trying game index")

    # Fallback to game index if it exists
    from .fiba_html_common import load_fiba_game_index

    df = load_fiba_game_index(FIBA_LEAGUE_CODE, season)

    if df.empty:
        logger.warning(f"No schedule found for BCL {season}")

    return df
```

### 2.4: Add fetch_shots Function

If it doesn't exist, add this public API function:

```python
def fetch_shots(season: str = "2023-24") -> pd.DataFrame:
    """
    Fetch BCL shot chart data.

    Public API function for shot data with coordinates.

    Args:
        season: Season string (e.g., "2023-24")

    Returns:
        DataFrame with shot data

    Example:
        >>> from cbb_data.fetchers import bcl
        >>> shots = bcl.fetch_shots("2023-24")
        >>> print(shots[['PLAYER_NAME', 'X', 'Y', 'MADE']].head())
    """
    return fetch_bcl_shots_html(season)
```

---

## Step 3: Apply Same Changes to Other FIBA Leagues

### BAL (Basketball Africa League)

**File**: `src/cbb_data/fetchers/bal.py`

Copy the BCL changes and update:
- Schedule URL: `"https://thebal.com/schedule/"`
- League code: Already `"BAL"`

### ABA (Adriatic League)

**File**: `src/cbb_data/fetchers/aba.py`

Copy the BCL changes and update:
- Schedule URL: `"https://www.aba-liga.com/schedule.php"`
- League code: Already `"ABA"`

### LKL (Lithuanian League)

**File**: `src/cbb_data/fetchers/lkl.py`

Copy the BCL changes and update:
- Schedule URL: `"https://lkl.lt/en/schedule"`
- League code: Already `"LKL"`

---

## Step 4: Test HTML-Only Mode

### Test BCL

```bash
# Test schedule scraping
python -c "
from src.cbb_data.fetchers import bcl
df = bcl.fetch_schedule('2023-24')
print(f'Schedule: {len(df)} games')
print(df[['GAME_ID', 'GAME_DATE']].head())
"

# Test player game (existing)
python -c "
from src.cbb_data.fetchers import bcl
df = bcl.fetch_player_game('2023-24')
print(f'Player game: {len(df)} records')
print(df[['PLAYER_NAME', 'PTS']].head())
"

# Test shots (new)
python -c "
from src.cbb_data.fetchers import bcl
df = bcl.fetch_shots('2023-24')
print(f'Shots: {len(df)} shots')
print(df[['PLAYER_NAME', 'X', 'Y', 'MADE']].head())
"

# Run golden season script
python scripts/golden_fiba.py --league BCL --season 2023-24
```

### Verify QA Passes

```bash
# Run complete validation
python tools/test_league_complete_flow.py --league BCL --season 2023-24

# Check results
cat data/golden/bcl/2023_24/SUMMARY.txt
```

---

## Step 5: Deprecate JSON Client (Optional)

### Option A: Keep as Fallback

Keep `fiba_livestats_json.py` but make HTML primary:

```python
# In bcl.py
def fetch_player_game(season: str = "2023-24", use_json: bool = False) -> pd.DataFrame:
    """Fetch player game stats (HTML primary, JSON optional)"""

    if use_json:
        # Use JSON client
        try:
            return _json_client.fetch_player_game("BCL", season)
        except:
            pass  # Fall through to HTML

    # HTML scraping (primary)
    return scrape_fiba_box_score("BCL", season)
```

### Option B: Remove Completely

1. Delete or rename `fiba_livestats_json.py` → `_fiba_livestats_json_deprecated.py`
2. Remove JSON client imports from all league fetchers
3. Update all functions to HTML-only

---

## Step 6: Update Documentation

### Update Capability Matrix

**File**: `docs/DATA_SOURCE_INTEGRATION_PLAN.md`

Update the table to reflect HTML-only sources:

```markdown
| League | Schedule | Player Game | Team Game | PBP | Shots | Source |
|--------|----------|-------------|-----------|-----|-------|--------|
| BCL | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | fibalivestats.dcd.shared.geniussports.com |
| BAL | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | fibalivestats.dcd.shared.geniussports.com |
| ABA | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | fibalivestats.dcd.shared.geniussports.com |
| LKL | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | ✅ HTML | fibalivestats.dcd.shared.geniussports.com |
```

### Update README

Add note about HTML-only sources:

```markdown
## Data Sources

All international basketball data is sourced from publicly available HTML pages:

- **FIBA Leagues**: Scraped from FIBA LiveStats HTML pages (no API required)
- **ACB**: Scraped from acb.com HTML pages
- **LNB**: Scraped from lnb.fr HTML pages

No authentication or API keys required.
```

---

## Troubleshooting

### Schedule Scraping Returns Empty

**Problem**: `fetch_bcl_schedule_html()` returns 0 games

**Solutions**:
1. Check if schedule URL is correct for current season
2. Inspect HTML structure (may have changed)
3. Look for FIBA LiveStats links manually on page
4. Fall back to manual game index CSV

### Shot Data Not Found

**Problem**: `fetch_bcl_shots_html()` returns empty DataFrame

**Solutions**:
1. Verify shot chart pages exist for games (sh.html)
2. Check if shot data is embedded in different format
3. Some seasons may not have shot coordinates - this is expected

### Rate Limiting / Blocking

**Problem**: Getting 429 or 403 errors

**Solutions**:
1. Increase rate limiter delay (currently 0.5s)
2. Add random jitter to requests
3. Use caching to avoid re-scraping
4. Respect robots.txt

---

## Next Steps

After completing FIBA cluster (BCL/BAL/ABA/LKL):

1. **Week 2**: Implement ACB HTML scrapers
   - `scrape_acb_schedule_page()`
   - `scrape_acb_boxscore_page()`
   - Update `acb.py` functions

2. **Week 2**: Implement LNB HTML scrapers
   - `scrape_lnb_stats_table()`
   - `scrape_lnb_schedule_html()`
   - Update `lnb.py` functions

3. **Week 3**: Polish and documentation
   - Update all docstrings
   - Add usage examples
   - Update PROJECT_LOG

---

## Summary of Changes

### Files Created
- ✅ `src/cbb_data/fetchers/html_scrapers.py` (500 lines)

### Files Updated
- ⏳ `src/cbb_data/fetchers/fiba_html_common.py` (+150 lines)
- ⏳ `src/cbb_data/fetchers/bcl.py` (+100 lines)
- ⏳ `src/cbb_data/fetchers/bal.py` (+100 lines)
- ⏳ `src/cbb_data/fetchers/aba.py` (+100 lines)
- ⏳ `src/cbb_data/fetchers/lkl.py` (+100 lines)

### Files to Update (Week 2)
- ⏳ `src/cbb_data/fetchers/acb.py` (~300 lines)
- ⏳ `src/cbb_data/fetchers/lnb.py` (~200 lines)

### Total New/Modified Code
~1,550 lines

---

Last Updated: 2025-11-14
