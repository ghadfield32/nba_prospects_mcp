# HTML-Only Data Scraping Implementation Plan

**Date**: 2025-11-14
**Objective**: Replace API/JSON dependencies with pure HTML scraping for all international leagues

---

## Current State Analysis

### What Exists
1. **FIBA JSON Client** (`fiba_livestats_json.py`)
   - Fetches from `data.json` endpoints
   - Status: Works but we want HTML-first

2. **FIBA HTML Common** (`fiba_html_common.py`)
   - `load_fiba_game_index()` - Loads game IDs from CSV
   - `scrape_fiba_box_score()` - Scrapes HTML box scores
   - `scrape_fiba_play_by_play()` - Scrapes HTML PBP
   - Missing: Shot charts, schedule scrapers

3. **Per-League Fetchers** (bcl.py, bal.py, aba.py, lkl.py)
   - Currently: JSON first → HTML fallback
   - Target: HTML-only

4. **ACB & LNB**
   - ACB: Basic fetchers exist, need HTML implementation
   - LNB: Placeholder functions only

---

## Architecture Changes

### 1. HTML Scraping Utilities (New)

**File**: `src/cbb_data/fetchers/html_scrapers.py` (NEW)

Core HTML scraping utilities that all leagues will use:

```python
# Generic HTML table parser
def parse_html_table(soup, table_selector) -> pd.DataFrame

# FIBA schedule page scraper
def scrape_fiba_schedule_page(league_url) -> List[Dict]

# FIBA shot chart HTML scraper
def scrape_fiba_shot_chart_html(league_code, game_id) -> pd.DataFrame

# ACB schedule scraper
def scrape_acb_schedule_page(season) -> pd.DataFrame

# ACB box score scraper
def scrape_acb_boxscore_page(game_url) -> Tuple[pd.DataFrame, pd.DataFrame]

# LNB stats table scraper
def scrape_lnb_stats_table(stats_url) -> pd.DataFrame
```

### 2. FIBA HTML Extensions (Update)

**File**: `src/cbb_data/fetchers/fiba_html_common.py` (UPDATE)

Add missing functions:

```python
# Schedule builder from HTML
def build_fiba_schedule_from_html(league_code, season, schedule_url) -> pd.DataFrame:
    """
    Scrape league schedule HTML page to get game IDs and metadata.

    Extracts:
    - GAME_ID from fibalivestats.../u/{LEAGUE}/{GAME_ID}/bs.html links
    - Date, time from table rows
    - Home team, away team, score
    - Competition phase (Regular Season, Playoffs, etc.)
    """

# Shot chart HTML scraper
def scrape_fiba_shot_chart_html(league_code, game_id) -> pd.DataFrame:
    """
    Scrape FIBA LiveStats shot chart HTML page.

    URL: .../u/{LEAGUE}/{GAME_ID}/sh.html or embedded in bs.html

    Extracts from <script> tags or HTML elements:
    - X, Y coordinates
    - SHOT_VALUE (2/3)
    - MADE (0/1)
    - PLAYER_ID, PLAYER_NAME
    - PERIOD, GAME_CLOCK
    """
```

### 3. Per-League Fetcher Changes

**Update**: bcl.py, bal.py, aba.py, lkl.py

Change from JSON-first to HTML-only:

```python
# OLD (JSON first):
def fetch_bcl_player_game(season):
    try:
        return _json_client.fetch_player_game("BCL", season)  # JSON
    except:
        return scrape_fiba_box_score("BCL", season)  # HTML fallback

# NEW (HTML-only):
def fetch_bcl_player_game(season):
    game_index = load_fiba_game_index("BCL", season)
    return scrape_fiba_box_score("BCL", season, game_index)  # HTML primary
```

**Add**:
```python
def fetch_bcl_schedule_html(season):
    """Build schedule by scraping BCL games page"""
    return build_fiba_schedule_from_html(
        league_code="BCL",
        season=season,
        schedule_url="https://www.championsleague.basketball/schedule"
    )

def fetch_bcl_shots_html(season):
    """Scrape shot charts from FIBA HTML"""
    game_index = load_fiba_game_index("BCL", season)
    return scrape_fiba_shot_chart_html("BCL", season, game_index)
```

### 4. ACB Fetchers (Implement)

**File**: `src/cbb_data/fetchers/acb.py` (UPDATE)

Replace placeholders with HTML scrapers:

```python
def fetch_acb_schedule_html(season):
    """Scrape ACB schedule/results pages"""
    return scrape_acb_schedule_page(season)

def fetch_acb_player_game_html(season):
    """Scrape ACB game-centre boxscore pages"""
    schedule = fetch_acb_schedule_html(season)

    all_games = []
    for game_url in schedule['GAME_URL']:
        player_df, team_df = scrape_acb_boxscore_page(game_url)
        all_games.append(player_df)

    return pd.concat(all_games, ignore_index=True)

def fetch_acb_player_season_html(season):
    """Scrape ACB season stats pages or aggregate from games"""
    # Option 1: Scrape season tables
    stats_url = f"https://www.acb.com/estadisticas/jugador/{season}"
    return scrape_lnb_stats_table(stats_url)  # Generic table scraper

    # Option 2: Aggregate from game-level
    # player_games = fetch_acb_player_game_html(season)
    # return aggregate_player_season(player_games)
```

### 5. LNB Fetchers (Implement)

**File**: `src/cbb_data/fetchers/lnb.py` (UPDATE)

Implement HTML scrapers:

```python
def fetch_lnb_player_season_html(season):
    """Scrape LNB Stats Centre player tables"""
    stats_url = f"https://lnb.fr/stats/joueurs?season={season}"
    return scrape_lnb_stats_table(stats_url)

def fetch_lnb_schedule_html(season):
    """Scrape LNB fixtures/results pages"""
    url = f"https://lnb.fr/calendrier-resultats?season={season}"
    # Parse HTML table with dates, teams, scores
    return parse_html_table(url, selector="table.fixtures")
```

---

## Implementation Priority

### Phase 1: Core HTML Utilities (Week 1, Day 1-2)
1. Create `html_scrapers.py` with generic utilities
2. Add `build_fiba_schedule_from_html()` to `fiba_html_common.py`
3. Add `scrape_fiba_shot_chart_html()` to `fiba_html_common.py`
4. Test on BCL 2023-24

### Phase 2: FIBA Cluster (Week 1, Day 3-5)
1. Update BCL to HTML-only (template for others)
2. Apply same changes to BAL, ABA, LKL
3. Collect 20-50 real game IDs per league
4. Run golden season scripts
5. Validate QA passes

### Phase 3: ACB (Week 2, Day 1-3)
1. Implement `scrape_acb_schedule_page()`
2. Implement `scrape_acb_boxscore_page()`
3. Update ACB fetchers to use HTML scrapers
4. Test with 2022-23 season (accessible)
5. Validate and compare with Zenodo

### Phase 4: LNB (Week 2, Day 4-5)
1. Implement `scrape_lnb_stats_table()`
2. Implement `scrape_lnb_schedule_html()`
3. Update LNB fetchers
4. Test with 2023-24 season
5. Validate QA passes

### Phase 5: Documentation & Cleanup (Week 3)
1. Update all function docstrings
2. Add HTML scraping examples to docs
3. Update capability matrix
4. Clean up old JSON client code
5. Update PROJECT_LOG

---

## Data Source Mapping

### FIBA Cluster (BCL, BAL, ABA, LKL)

| Dataset | HTML Source | URL Pattern |
|---------|-------------|-------------|
| Schedule | League games page | championsleague.basketball/schedule |
| Player Game | FIBA bs.html | fibalivestats.../u/{LEAGUE}/{GAME_ID}/bs.html |
| Team Game | FIBA bs.html (totals row) | Same as above |
| PBP | FIBA pbp.html | fibalivestats.../u/{LEAGUE}/{GAME_ID}/pbp.html |
| Shots | FIBA sh.html or <script> | fibalivestats.../u/{LEAGUE}/{GAME_ID}/sh.html |
| Player Season | Aggregate from Player Game | N/A (computed) |
| Team Season | Aggregate from Team Game | N/A (computed) |

### ACB

| Dataset | HTML Source | URL Pattern |
|---------|-------------|-------------|
| Schedule | ACB calendario | acb.com/resultados-clasificacion/calendario |
| Player Game | ACB game centre | acb.com/partido/estadisticas/{GAME_ID} |
| Team Game | ACB game centre (totals) | Same as above |
| PBP | ACB pbp tab (if exists) | acb.com/partido/pbp/{GAME_ID} (rare) |
| Shots | Not available | N/A |
| Player Season | ACB season stats OR aggregate | acb.com/estadisticas/jugador/{SEASON} |
| Team Season | ACB team stats OR aggregate | acb.com/estadisticas/equipo/{SEASON} |

### LNB Pro A

| Dataset | HTML Source | URL Pattern |
|---------|-------------|-------------|
| Schedule | LNB fixtures | lnb.fr/calendrier-resultats?season={SEASON} |
| Player Game | LNB game page (if exists) | lnb.fr/match/{GAME_ID} |
| Team Game | LNB game page (if exists) | Same as above |
| PBP | Not available | N/A |
| Shots | Not available | N/A |
| Player Season | LNB Stats Centre | lnb.fr/stats/joueurs?season={SEASON} |
| Team Season | LNB Stats Centre | lnb.fr/stats/equipes?season={SEASON} |

---

## Testing Strategy

### Unit Tests
```python
def test_parse_fiba_schedule_html():
    # Test schedule scraper on sample HTML

def test_scrape_fiba_shot_chart():
    # Test shot chart scraper with known game ID

def test_scrape_acb_boxscore():
    # Test ACB game centre scraper
```

### Integration Tests
```python
def test_bcl_full_flow_html_only():
    # Fetch schedule → player_game → shots
    # Validate QA passes

def test_acb_season_level():
    # Fetch player_season from HTML
    # Compare row counts with expected
```

### Validation
```bash
# Run existing validation tools
python tools/test_league_complete_flow.py --league BCL --season 2023-24
python tools/run_complete_validation.py BCL BAL ABA LKL ACB LNB
```

---

## Backward Compatibility

### Keep JSON Client (Optional)
- Move `fiba_livestats_json.py` to `_fiba_livestats_json_deprecated.py`
- Add `use_json=False` flag to fetchers for opt-in JSON mode
- Default to HTML-only

### Migration Path
```python
# OLD: JSON-first
df = fetch_bcl_player_game(season="2023-24")  # Used JSON

# NEW: HTML-only (default)
df = fetch_bcl_player_game(season="2023-24")  # Uses HTML

# OPTIONAL: Force JSON (for testing)
df = fetch_bcl_player_game(season="2023-24", use_json=True)
```

---

## Success Criteria

### FIBA Cluster
- ✅ Schedule has 20+ games per season
- ✅ Player game has 200+ records
- ✅ Shot coordinates present and valid
- ✅ All data from HTML sources only
- ✅ QA checks pass

### ACB
- ✅ Season-level player/team stats working
- ✅ Schedule parsing successful for recent seasons
- ✅ Game-level data available for at least 1 season
- ✅ All HTML sources, no Zenodo dependency

### LNB
- ✅ Season-level player/team stats working
- ✅ Schedule parsing successful (if available)
- ✅ PBP/shots documented as unavailable
- ✅ All HTML sources

---

## Risk Mitigation

### HTML Structure Changes
- **Risk**: League websites change HTML structure
- **Mitigation**:
  - Version HTML parsers with date stamps
  - Add structure validation tests
  - Graceful degradation on parse failures

### Rate Limiting
- **Risk**: Too many requests trigger blocks
- **Mitigation**:
  - Use existing rate limiter (0.5s between requests)
  - Cache HTML responses
  - Respect robots.txt

### Missing Data
- **Risk**: Some games/seasons don't have full data
- **Mitigation**:
  - Design for partial data (return what's available)
  - Add data quality flags (SOURCE column)
  - Document known gaps

---

## Code Changes Summary

### New Files
- `src/cbb_data/fetchers/html_scrapers.py` (~500 lines)

### Updated Files
- `src/cbb_data/fetchers/fiba_html_common.py` (+200 lines)
- `src/cbb_data/fetchers/bcl.py` (~50 lines changed)
- `src/cbb_data/fetchers/bal.py` (~50 lines changed)
- `src/cbb_data/fetchers/aba.py` (~50 lines changed)
- `src/cbb_data/fetchers/lkl.py` (~50 lines changed)
- `src/cbb_data/fetchers/acb.py` (~300 lines new)
- `src/cbb_data/fetchers/lnb.py` (~200 lines new)

### Deprecated Files
- `src/cbb_data/fetchers/fiba_livestats_json.py` → `_fiba_livestats_json_deprecated.py`

### Total LOC
- New: ~1,400 lines
- Modified: ~400 lines
- **Total**: ~1,800 lines

---

## Timeline

**Week 1**: FIBA Cluster HTML-only (16-20 hours)
- Day 1-2: Core utilities and FIBA extensions
- Day 3-5: Per-league updates and testing

**Week 2**: ACB + LNB (12-16 hours)
- Day 1-3: ACB implementation and testing
- Day 4-5: LNB implementation and testing

**Week 3**: Documentation and Polish (6-8 hours)
- Day 1-2: Update all docs
- Day 3: Final testing and validation

**Total**: 34-44 hours

---

Last Updated: 2025-11-14
