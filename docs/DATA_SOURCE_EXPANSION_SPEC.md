# Data Source Expansion Specification

**Date**: 2025-11-18
**Status**: Planning Complete - Awaiting User Decision
**Scope**: ACB PBP/Shots, NZ-NBL Full FIBA, LNB Team Game

---

## Executive Summary

**Current Status**:
1. **LNB team_game**: ✅ **ALREADY COMPLETE** - Verified 488 rows (244 games)
2. **NZ-NBL expansion**: ⏸️ Planned - Can implement in 2-3 hours (high value, no new deps)
3. **ACB PBP/shots**: ⚠️ Deferred - Requires R environment (complex, modern era only)

**Recommendation**: **Option A** - Implement NZ-NBL expansion (quick win, high ROI)

---

## Part 1: LNB Team Game - VERIFICATION COMPLETE ✅

### Status
**ALREADY FULLY IMPLEMENTED** - No code changes needed

### Verification Results
```
Function: get_lnb_normalized_team_game(season, game_ids, team, limit, league)
Location: src/cbb_data/api/lnb_historical.py:514-600
Test: 2024-2025 season, league='LNB_PROA'
Result: 488 rows (244 games × 2 teams)
Features:
  - League filtering: ✅ LNB_PROA, LNB_ELITE2, LNB_ESPOIRS_ELITE, LNB_ESPOIRS_PROB
  - Aggregation source: ✅ Player stats (derived from PBP)
  - Opponent data: ✅ OPP_ID, OPP_PTS
  - Win/Loss: ✅ WIN boolean column
  - All stats: ✅ PTS, FGM/FGA, FG2M/FG2A, FG3M/FG3A, FTM/FTA, REB, AST, STL, BLK, TOV, PF, percentages
```

### Schema
```python
Columns (26 total):
  - GAME_ID: Game identifier (fixture UUID)
  - TEAM_ID: Team identifier
  - PTS, FGM, FGA: Points and field goal stats
  - FG2M, FG2A: 2-point stats
  - FG3M, FG3A: 3-point stats
  - FTM, FTA: Free throw stats
  - REB, AST, STL, BLK, TOV, PF: Traditional box score stats
  - FG_PCT, FG2_PCT, FG3_PCT, FT_PCT: Shooting percentages
  - SEASON, LEAGUE: Metadata
  - OPP_ID, OPP_PTS: Opponent info
  - WIN: Boolean win/loss indicator
```

### Usage Examples
```python
from src.cbb_data.fetchers.lnb import fetch_lnb_team_game_normalized

# All teams for a season
team_game = fetch_lnb_team_game_normalized(season="2024-2025")

# Specific league
elite2_stats = fetch_lnb_team_game_normalized(
    season="2024-2025",
    league="LNB_ELITE2"
)

# Specific team
monaco_games = fetch_lnb_team_game_normalized(
    season="2024-2025",
    league="LNB_PROA",
    team="Monaco"
)
```

### Catalog Integration
Already wired in `src/cbb_data/fetchers/lnb.py:1720-1750`:
```python
def fetch_lnb_team_game_normalized(season, game_ids, league, **kwargs):
    """Fetch LNB team-game box scores from normalized parquet files"""
    from ..api.lnb_historical import get_lnb_normalized_team_game
    return get_lnb_normalized_team_game(season=season, game_ids=game_ids, league=league, **kwargs)
```

### Conclusion
**No implementation needed** - LNB team_game is production-ready for all 4 leagues.

---

## Part 2: NZ-NBL FIBA Expansion - PLANNED ⏸️

### Current State
- **Schedule**: ⚠️ Index-only (2 games) - needs full discovery
- **Player Game**: ⚠️ Basic (via index) - works but limited coverage
- **Team Game**: ⚠️ Aggregated from player game - works but limited
- **PBP**: ❌ Not implemented
- **Shot Charts**: ❌ Not implemented

### Proposed Implementation

#### 2.1 Schedule Discovery

**Goal**: Scrape nznbl.basketball for complete season schedules + FIBA game IDs

**Approach**:
```python
# src/cbb_data/fetchers/nz_nbl_fiba.py

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_schedule_full(season: str) -> pd.DataFrame:
    """
    Scrape NZ-NBL website for complete schedule + FIBA LiveStats game IDs

    Data Source: https://nznbl.basketball/stats/results/

    Args:
        season: Season year (e.g., "2024" for 2024 season)

    Returns:
        DataFrame with columns:
        - LEAGUE: "NZ-NBL"
        - SEASON: Season string
        - GAME_DATE: Game date
        - HOME_TEAM: Home team name
        - AWAY_TEAM: Away team name
        - HOME_SCORE: Home team final score (if available)
        - AWAY_SCORE: Away team final score (if available)
        - FIBA_COMP_ID: FIBA competition code ("NZN")
        - FIBA_GAME_ID: FIBA game ID (extracted from LiveStats URL)
        - VENUE: Venue name (if available)
        - STATUS: Game status (FINAL, SCHEDULED, etc.)
    """
    # 1. Build season URL(s) - follow pagination links
    base_url = f"https://nznbl.basketball/stats/results/?season={season}"

    # 2. Parse all games table rows with BeautifulSoup
    # 3. Extract FIBA LiveStats URLs per game
    # 4. Parse FIBA comp_id and game_id with regex:
    #    r'fibalivestats\.dcd\.shared\.geniussports\.com/u/([A-Z]+)/(\d+)'
    # 5. Normalize columns to canonical schema

    # Implementation: ~100 lines (HTML parsing + table extraction)
```

**Estimated Lines**: ~120 lines
**Dependencies**: requests, beautifulsoup4 (already installed)
**Coverage**: Full season schedules (FIBA era ~2018-present)

---

#### 2.2 Play-by-Play Fetcher

**Goal**: Extract PBP event stream from FIBA LiveStats HTML pages

**Approach**:
```python
# src/cbb_data/fetchers/nz_nbl_fiba.py

def _fetch_fiba_pbp_html(comp_id: str, game_id: str) -> BeautifulSoup:
    """Fetch FIBA PBP HTML page"""
    url = f"https://fibalivestats.dcd.shared.geniussports.com/u/{comp_id}/{game_id}/pbp.html"
    response = requests.get(url, timeout=10)
    return BeautifulSoup(response.text, 'html.parser')

def _parse_fiba_pbp(soup: BeautifulSoup, season: str, game_id: str) -> pd.DataFrame:
    """
    Parse FIBA PBP HTML into structured event stream

    Returns DataFrame with columns:
    - EVENT_ID: Sequential event number
    - SEASON, LEAGUE, GAME_ID: Metadata
    - PERIOD: Quarter (1-4) or OT (5+)
    - CLOCK: Game clock (MM:SS)
    - TEAM: Team identifier
    - PLAYER_ID, PLAYER_NAME: Player info
    - EVENT_TYPE: SHOT_MADE, SHOT_MISS, FOUL, TURNOVER, REBOUND, SUB, etc.
    - POINTS: Points scored (for scoring events)
    - X, Y: Shot coordinates (if available)
    - SCORE_HOME, SCORE_AWAY: Running score
    - DESCRIPTION: Event description text
    """
    # Parse PBP table rows from HTML
    # Map event codes to canonical EVENT_TYPE
    # Extract coordinates from shot events

    # Implementation: ~150 lines (HTML parsing + event normalization)

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_pbp(season: str) -> pd.DataFrame:
    """Fetch NZ-NBL play-by-play for all games in a season"""
    schedule = fetch_nz_nbl_schedule_full(season)

    frames = []
    for _, row in schedule.iterrows():
        soup = _fetch_fiba_pbp_html(row["FIBA_COMP_ID"], row["FIBA_GAME_ID"])
        df_pbp = _parse_fiba_pbp(soup, season, row["FIBA_GAME_ID"])
        frames.append(df_pbp)

    return pd.concat(frames, ignore_index=True)
```

**Estimated Lines**: ~200 lines total
**Dependencies**: requests, beautifulsoup4 (already installed)
**Coverage**: Games with FIBA LiveStats coverage (~2018-present)

---

#### 2.3 Shot Chart Fetcher

**Goal**: Extract shot x,y coordinates from FIBA LiveStats

**Approach**:
```python
# src/cbb_data/fetchers/nz_nbl_fiba.py

def _fetch_fiba_shots_html(comp_id: str, game_id: str) -> BeautifulSoup:
    """Fetch FIBA shot chart HTML page"""
    url = f"https://fibalivestats.dcd.shared.geniussports.com/u/{comp_id}/{game_id}/sc.html"
    response = requests.get(url, timeout=10)
    return BeautifulSoup(response.text, 'html.parser')

def _parse_fiba_shots(soup: BeautifulSoup, season: str, game_id: str) -> pd.DataFrame:
    """
    Parse FIBA shot chart HTML/JavaScript into structured shot data

    Returns DataFrame with columns:
    - SHOT_ID: Sequential shot number
    - SEASON, LEAGUE, GAME_ID: Metadata
    - PERIOD: Quarter (1-4) or OT (5+)
    - CLOCK: Game clock when shot taken
    - TEAM: Team identifier
    - PLAYER_ID, PLAYER_NAME: Player info
    - X, Y: Shot coordinates (normalized to court dimensions)
    - SHOT_TYPE: "2PT", "3PT", "FT"
    - SHOT_RESULT: "MADE", "MISSED"
    - POINTS: Points scored (0 if missed)
    - DISTANCE: Distance from basket (if calculable)
    - ZONE: Court zone (if categorizable)
    """
    # Parse JavaScript shot data from HTML
    # Extract coordinates from embedded JSON or data attributes
    # Normalize coordinates to canonical court system

    # Implementation: ~150 lines (HTML/JS parsing + coordinate normalization)

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_nz_nbl_shot_chart(season: str) -> pd.DataFrame:
    """Fetch NZ-NBL shot charts for all games in a season"""
    schedule = fetch_nz_nbl_schedule_full(season)

    frames = []
    for _, row in schedule.iterrows():
        soup = _fetch_fiba_shots_html(row["FIBA_COMP_ID"], row["FIBA_GAME_ID"])
        df_shots = _parse_fiba_shots(soup, season, row["FIBA_GAME_ID"])
        frames.append(df_shots)

    return pd.concat(frames, ignore_index=True)
```

**Estimated Lines**: ~200 lines total
**Dependencies**: requests, beautifulsoup4 (already installed)
**Coverage**: Games with FIBA shot chart data (~2018-present)

**Note**: FIBA shot coordinates may be embedded in JavaScript/JSON within HTML (not just table data)

---

### Implementation Effort Summary

| Component | Lines | Complexity | Dependencies | Time |
|-----------|-------|------------|--------------|------|
| Schedule Discovery | ~120 | Medium | None (existing) | 45 min |
| PBP Fetcher | ~200 | Medium-High | None (existing) | 1 hour |
| Shot Chart Fetcher | ~200 | Medium-High | None (existing) | 1 hour |
| Testing | ~100 | Low | pytest | 30 min |
| **Total** | **~620** | **Medium** | **None (all exist)** | **3-3.5 hours** |

### Historical Coverage Discovery

Add probe script:
```python
# scripts/probe_nz_nbl_coverage.py

for season in range(2017, 2025):
    try:
        schedule = fetch_nz_nbl_schedule_full(str(season))
        pbp = fetch_nz_nbl_pbp(str(season))
        shots = fetch_nz_nbl_shot_chart(str(season))

        print(f"{season}: {len(schedule)} games, {len(pbp)} events, {len(shots)} shots")
    except Exception as e:
        print(f"{season}: ERROR - {e}")

# Output to STATE_HEALTH_NZ_NBL.md
```

---

## Part 3: ACB BAwiR Integration - DEFERRED ⚠️

### Proposed Implementation (For Reference)

#### 3.1 R Bridge Setup

**Dependencies**:
- `rpy2` (Python package for R integration)
- `BAwiR` (R package from CRAN)
- R environment (4.0+)

**Installation**:
```bash
# Install R (platform-specific)
# Windows: https://cran.r-project.org/bin/windows/base/
# macOS: brew install r
# Linux: apt-get install r-base

# Install rpy2
uv pip install rpy2

# Install BAwiR in R
R -e 'install.packages("BAwiR")'
```

#### 3.2 Game Index Fetcher

```python
# src/cbb_data/fetchers/acb_bawir.py (NEW FILE)

import pandas as pd
from rpy2 import robjects
from rpy2.robjects import pandas2ri

from cbb_data.utils.decorators import retry_on_error, cached_dataframe

pandas2ri.activate()
BAWIR = robjects.packages.importr("BAwiR")

@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_game_index(season: str) -> pd.DataFrame:
    """Return ACB game index for a season (game codes, days, etc.)

    Args:
        season: Season ending year (e.g., "2024" for 2023-24 season)

    Returns:
        DataFrame with game_code, day, date, home_team, away_team
    """
    r_days = BAWIR.do_scrape_days_acb(season, "user_agent", True, 1000, 975)
    df_days = pandas2ri.rpy2py(r_days)

    # Normalize column names to canonical schema
    return normalize_acb_game_index(df_days, season)
```

#### 3.3 PBP Fetcher

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_pbp(season: str, game_codes: list[str] | None = None) -> pd.DataFrame:
    """Fetch ACB play-by-play for season or specific games

    Args:
        season: Season ending year
        game_codes: List of ACB game codes (optional)

    Returns:
        DataFrame with canonical PBP schema
    """
    idx = fetch_acb_game_index(season)
    if game_codes:
        idx = idx[idx["game_code"].isin(game_codes)]

    all_games = []
    for _, row in idx.iterrows():
        # Call BAwiR to get PBP HTML via RSelenium
        r_pbp = BAWIR.do_get_pbp_for_game(row["day"], row["game_code"])
        df_pbp_raw = pandas2ri.rpy2py(r_pbp)
        df_pbp = normalize_acb_pbp(df_pbp_raw, season, row["game_code"])
        all_games.append(df_pbp)

    return pd.concat(all_games, ignore_index=True)
```

#### 3.4 Shot Chart Fetcher

```python
@retry_on_error(max_attempts=3, backoff_seconds=2.0)
@cached_dataframe
def fetch_acb_shot_chart(season: str, game_codes: list[str] | None = None) -> pd.DataFrame:
    """Fetch ACB shot charts for season or specific games

    Args:
        season: Season ending year
        game_codes: List of ACB game codes (optional)

    Returns:
        DataFrame with canonical shot chart schema (x, y, result, etc.)
    """
    idx = fetch_acb_game_index(season)
    if game_codes:
        idx = idx[idx["game_code"].isin(game_codes)]

    r_shots = BAWIR.do_scrape_shots_acb(idx, True, "user_agent", "x_apikey")
    df_shots_raw = pandas2ri.rpy2py(r_shots)

    return normalize_acb_shots(df_shots_raw, season)
```

### Implementation Effort Summary

| Component | Lines | Complexity | Dependencies | Time |
|-----------|-------|------------|--------------|------|
| R Environment Setup | N/A | High | R, rpy2, BAwiR | 1-2 hours |
| Game Index | ~80 | Low | rpy2 | 30 min |
| PBP Fetcher | ~150 | Medium | rpy2, RSelenium | 1.5 hours |
| Shot Chart Fetcher | ~120 | Medium | rpy2 | 1 hour |
| Schema Normalization | ~200 | Medium | None | 1.5 hours |
| Testing (cross-platform) | ~150 | High | pytest, R | 2 hours |
| **Total** | **~700** | **High** | **R + rpy2** | **7-9 hours** |

### Challenges

1. **Platform Dependency**: Requires R installation on all dev/prod environments (Windows, macOS, Linux)
2. **RSelenium Setup**: BAwiR uses RSelenium for browser automation (additional complexity)
3. **Coverage Uncertainty**: PBP/shots likely only available "modern era" (mid-2010s forward), not full 42-year history
4. **Maintenance**: R package updates could break Python bridge
5. **Testing**: Cross-platform testing required (Windows/macOS/Linux)

### Alternative: Direct ACB Scraping

**Simpler approach** (no R dependency):
```python
# src/cbb_data/fetchers/acb_direct.py

@cached_dataframe
def fetch_acb_pbp_direct(season: str) -> pd.DataFrame:
    """Scrape ACB PBP directly from live.acb.com (no BAwiR)"""
    # Direct HTML scraping of https://live.acb.com/en/{game_id}/playbyplay
    # More fragile but no R dependency
```

**Trade-off**: More fragile (HTML structure changes), but no R environment needed

---

## Recommendation Matrix

| Option | Effort | Value | Dependencies | Risk | Recommendation |
|--------|--------|-------|--------------|------|----------------|
| **LNB team_game** | ✅ None (done) | ✅ High | None | ✅ None | ✅ **Verify Only** |
| **NZ-NBL expansion** | ⏸️ 3 hours | ✅ High | None (exists) | ✅ Low | ✅ **IMPLEMENT NOW** |
| **ACB BAwiR** | ⚠️ 7-9 hours | ⏸️ Medium | R + rpy2 | ⚠️ High | ⚠️ **DEFER** |
| **ACB Direct** | ⏸️ 4-5 hours | ⏸️ Medium | None | ⏸️ Medium | ⏸️ **Consider Later** |

---

## Proposed Execution Plan

### Phase 1: Documentation & Verification (DONE ✅)
- ✅ Verify LNB team_game functionality
- ✅ Update PROJECT_LOG
- ✅ Create this spec document

### Phase 2: NZ-NBL Expansion (Recommended Next)
**Estimated**: 3-3.5 hours

1. **Implement Schedule Discovery** (45 min)
   - Add `fetch_nz_nbl_schedule_full(season)` to nz_nbl_fiba.py
   - Scrape nznbl.basketball results pages
   - Extract FIBA game IDs from LiveStats URLs
   - Test on 2024 season

2. **Implement PBP Fetcher** (1 hour)
   - Add `fetch_nz_nbl_pbp(season)` to nz_nbl_fiba.py
   - Parse FIBA PBP HTML tables
   - Normalize event types to canonical schema
   - Test on 2-3 games

3. **Implement Shot Chart Fetcher** (1 hour)
   - Add `fetch_nz_nbl_shot_chart(season)` to nz_nbl_fiba.py
   - Parse FIBA shot chart data (HTML/JavaScript)
   - Normalize coordinates to canonical court system
   - Test on 2-3 games

4. **Testing & Validation** (30 min)
   - Smoke tests for all 3 functions
   - Coverage probe script (2017-2024 seasons)
   - Update STATE_HEALTH_NZ_NBL.md

5. **Catalog Integration** (15 min)
   - Wire new functions into src/cbb_data/catalog/sources.py
   - Update data availability matrix

### Phase 3: ACB Integration (Deferred)
**Decision Point**: Requires user confirmation on:
- R environment setup acceptance
- Priority vs other features
- BAwiR vs direct scraping approach

---

## Testing Strategy

### NZ-NBL Tests

```python
# tests/test_nz_nbl_expansion.py

def test_nz_nbl_schedule_discovery():
    """Test schedule discovery for recent season"""
    schedule = fetch_nz_nbl_schedule_full("2024")
    assert len(schedule) > 0
    assert "FIBA_GAME_ID" in schedule.columns
    assert all(schedule["LEAGUE"] == "NZ-NBL")

def test_nz_nbl_pbp_smoke():
    """Smoke test PBP fetcher on 1-2 games"""
    pbp = fetch_nz_nbl_pbp("2024", game_limit=2)
    assert len(pbp) > 0
    assert "EVENT_TYPE" in pbp.columns
    assert pbp["EVENT_TYPE"].isin(["SHOT_MADE", "SHOT_MISS", "FOUL"]).any()

def test_nz_nbl_shots_smoke():
    """Smoke test shot chart fetcher on 1-2 games"""
    shots = fetch_nz_nbl_shot_chart("2024", game_limit=2)
    assert len(shots) > 0
    assert all(col in shots.columns for col in ["X", "Y", "SHOT_RESULT"])
```

### ACB Tests (When Implemented)

```python
# tests/test_acb_bawir.py

@pytest.mark.skipif(not R_AVAILABLE, reason="R environment not available")
def test_acb_game_index():
    """Test ACB game index fetcher via BAwiR"""
    idx = fetch_acb_game_index("2024")
    assert len(idx) > 0
    assert "game_code" in idx.columns
```

---

## User Decision Required

Please select an option:

**Option A (Recommended)**:
- ✅ Implement NZ-NBL expansion now (3 hours)
- ⏸️ Defer ACB BAwiR to future sprint
- ✅ Document LNB as complete

**Option B**:
- ⏸️ Skip NZ-NBL for now
- ✅ Implement ACB direct scraping (4-5 hours, no R)
- ✅ Document LNB as complete

**Option C**:
- ⏸️ Document only (no new implementation)
- ✅ Update data availability matrix
- ✅ Mark ACB PBP/shots as "future work"

**Option D (Full Implementation)**:
- ✅ Implement NZ-NBL expansion (3 hours)
- ✅ Implement ACB BAwiR (7-9 hours)
- **Total**: 10-12 hours (substantial work)

---

**Please indicate your preference and I'll proceed with implementation accordingly.**
