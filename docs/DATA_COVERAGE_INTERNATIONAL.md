# International Basketball Data Coverage Matrix

**Last Updated**: 2025-11-14
**Status**: ✅ COMPREHENSIVE (7 leagues, 7 granularities)

This document is the **single source of truth** for data availability across all international basketball leagues in the cbb_data package.

---

## Quick Reference Table

| League | Schedule | Player Game | Team Game | PBP | Shots | Player Season | Team Season | Historical Depth |
|--------|----------|-------------|-----------|-----|-------|---------------|-------------|------------------|
| **BCL** (Basketball Champions League) | ✅ HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ JSON+HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ Aggregated | 2016-present |
| **BAL** (Basketball Africa League) | ✅ HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ JSON+HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ Aggregated | 2021-present |
| **ABA** (Adriatic League) | ✅ HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ JSON+HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ Aggregated | 2001-present |
| **LKL** (Lithuania League) | ✅ HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ JSON+HTML | ✅ JSON+HTML | ✅ Aggregated | ✅ Aggregated | 2016-present |
| **ACB** (Liga Endesa - Spain) | ✅ HTML | ✅ HTML | ✅ HTML | ❌ None | ❌ None | ✅ HTML+Agg | ✅ HTML | 2020-present |
| **LNB** (Pro A - France) | ⚠️ Optional | ❌ Investigation | ❌ Investigation | ❌ Investigation | ❌ Investigation | ✅ HTML | ✅ HTML | 2020-present |

**Legend:**
- ✅ **Fully Available** - Implemented and tested
- ⚠️ **Partial/Optional** - Available but may be incomplete or require special handling
- ❌ **Not Available** - Not implemented yet or data source doesn't provide
- 🔍 **Investigation Required** - Implementation depends on API discovery

---

## Detailed Coverage by League

### 1. BCL (Basketball Champions League)

**Competition**: FIBA Champions League (Europe's 3rd-tier club competition)
**Season Format**: "2023-24" (October-May)
**Official Site**: https://www.championsleague.basketball/
**Data Source**: FIBA LiveStats (fibalivestats.dcd.shared.geniussports.com)

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ✅ Available | HTML scraping → `build_fiba_schedule_from_html()` | Game index with dates, teams, scores |
| **player_game** | ✅ Available | JSON API (primary) + HTML fallback | Per-game box scores with full stats |
| **team_game** | ✅ Available | Aggregated from player_game | Derived team totals per game |
| **pbp** | ✅ Available | JSON API (primary) + HTML fallback | Play-by-play with running score, timestamps |
| **shots** | ✅ Available | JSON API (primary) + HTML fallback | Shot chart with X/Y coordinates (0-100 normalized) |
| **player_season** | ✅ Available | Aggregated from player_game | Season totals and per-game averages |
| **team_season** | ✅ Available | Aggregated from team_game | Season totals and per-game averages |

#### Implementation Details

**Fetcher Module**: `src/cbb_data/fetchers/bcl.py`
**Shared Utilities**: `src/cbb_data/fetchers/fiba_html_common.py`
**Competition Code**: `"BCL"` (FIBA LiveStats identifier)

**Key Features**:
- JSON API provides clean, structured data (preferred)
- HTML fallback for games where JSON unavailable
- Coordinates normalized 0-100 (court width/length)
- Full PBP with substitutions, timeouts, fouls
- Historical depth: 2016-present (BCL inception)

**Golden Script**: `scripts/golden_fiba.py --league BCL --season 2023-24`

**Sample Usage**:
```python
from src.cbb_data.fetchers.bcl import (
    fetch_bcl_schedule,
    fetch_bcl_player_game,
    fetch_bcl_pbp,
    fetch_bcl_shots
)

# Fetch full season
schedule = fetch_bcl_schedule("2023-24")  # ~200 games
player_game = fetch_bcl_player_game("2023-24")  # ~5,000 player-games
pbp = fetch_bcl_pbp("2023-24")  # ~150,000 events
shots = fetch_bcl_shots("2023-24")  # ~40,000 shots
```

---

### 2. BAL (Basketball Africa League)

**Competition**: FIBA Basketball Africa League (Africa's premier club competition)
**Season Format**: "2024" (May-June, single calendar year)
**Official Site**: https://thebal.com/
**Data Source**: FIBA LiveStats (fibalivestats.dcd.shared.geniussports.com)

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ✅ Available | HTML scraping → `build_fiba_schedule_from_html()` | Includes Nile Conference, Sahara Conference |
| **player_game** | ✅ Available | JSON API (primary) + HTML fallback | Full box scores |
| **team_game** | ✅ Available | Aggregated from player_game | Team totals |
| **pbp** | ✅ Available | JSON API (primary) + HTML fallback | Full play-by-play |
| **shots** | ✅ Available | JSON API (primary) + HTML fallback | Shot charts with coordinates |
| **player_season** | ✅ Available | Aggregated from player_game | Season aggregates |
| **team_season** | ✅ Available | Aggregated from team_game | Season aggregates |

#### Implementation Details

**Fetcher Module**: `src/cbb_data/fetchers/bal.py`
**Shared Utilities**: `src/cbb_data/fetchers/fiba_html_common.py`
**Competition Code**: `"BAL"` (FIBA LiveStats identifier)

**Key Features**:
- Identical infrastructure to BCL (same FIBA LiveStats backend)
- Conference-based format (Nile vs Sahara)
- Shorter season (~50 games total)
- Historical depth: 2021-present (BAL inaugural season)

**Golden Script**: `scripts/golden_fiba.py --league BAL --season 2024`

---

### 3. ABA (Adriatic League)

**Competition**: ABA Liga (Adriatic Basketball Association - Balkans)
**Season Format**: "2023-24" (October-June)
**Official Site**: https://www.aba-liga.com/
**Data Source**: FIBA LiveStats (fibalivestats.dcd.shared.geniussports.com)

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ✅ Available | HTML scraping → `build_fiba_schedule_from_html()` | ABA Liga 1 + ABA Liga 2 |
| **player_game** | ✅ Available | JSON API (primary) + HTML fallback | Full box scores |
| **team_game** | ✅ Available | Aggregated from player_game | Team totals |
| **pbp** | ✅ Available | JSON API (primary) + HTML fallback | Full play-by-play |
| **shots** | ✅ Available | JSON API (primary) + HTML fallback | Shot charts with coordinates |
| **player_season** | ✅ Available | Aggregated from player_game | Season aggregates |
| **team_season** | ✅ Available | Aggregated from team_game | Season aggregates |

#### Implementation Details

**Fetcher Module**: `src/cbb_data/fetchers/aba.py`
**Shared Utilities**: `src/cbb_data/fetchers/fiba_html_common.py`
**Competition Code**: `"ABA"` (FIBA LiveStats identifier)

**Key Features**:
- Identical infrastructure to BCL/BAL
- Covers multiple Balkan countries (Serbia, Croatia, Slovenia, etc.)
- Very deep historical data: 2001-present (21+ seasons)
- Multiple divisions (ABA Liga 1 = top tier)

**Golden Script**: `scripts/golden_fiba.py --league ABA --season 2023-24`

---

### 4. LKL (Lietuvos Krepšinio Lyga - Lithuania)

**Competition**: LKL (Lithuania's top basketball league)
**Season Format**: "2023-24" (October-June)
**Official Site**: https://www.lkl.lt/
**Data Source**: FIBA LiveStats (fibalivestats.dcd.shared.geniussports.com)

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ✅ Available | HTML scraping → `build_fiba_schedule_from_html()` | Regular season + playoffs |
| **player_game** | ✅ Available | JSON API (primary) + HTML fallback | Full box scores |
| **team_game** | ✅ Available | Aggregated from player_game | Team totals |
| **pbp** | ✅ Available | JSON API (primary) + HTML fallback | Full play-by-play |
| **shots** | ✅ Available | JSON API (primary) + HTML fallback | Shot charts with coordinates |
| **player_season** | ✅ Available | Aggregated from player_game | Season aggregates |
| **team_season** | ✅ Available | Aggregated from team_game | Season aggregates |

#### Implementation Details

**Fetcher Module**: `src/cbb_data/fetchers/lkl.py`
**Shared Utilities**: `src/cbb_data/fetchers/fiba_html_common.py`
**Competition Code**: `"LKL"` (FIBA LiveStats identifier)

**Key Features**:
- Identical infrastructure to BCL/BAL/ABA
- Lithuania is a basketball powerhouse (EuroLeague talent pipeline)
- Zalgiris Kaunas is flagship team
- Historical depth: 2016-present (varies by FIBA coverage)

**Golden Script**: `scripts/golden_fiba.py --league LKL --season 2023-24`

---

### 5. ACB (Liga Endesa - Spain)

**Competition**: ACB (Spain's top-tier professional basketball league)
**Season Format**: "2023-24" (October-June)
**Official Site**: https://www.acb.com/
**Data Source**: HTML scraping (acb.com/estadisticas-*)

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ✅ Available | HTML scraping → `scrape_acb_schedule_page()` | Game calendar with dates/teams/scores |
| **player_game** | ✅ Available | HTML scraping → `scrape_acb_game_centre()` | Per-game box scores from game centres |
| **team_game** | ✅ Available | HTML scraping | Team box scores from game centres |
| **pbp** | ❌ Not Available | N/A | ACB doesn't publicly expose PBP data |
| **shots** | ❌ Not Available | N/A | ACB doesn't publicly expose shot charts |
| **player_season** | ✅ Available | HTML scraping + aggregation | Season stats from /estadisticas-individuales |
| **team_season** | ✅ Available | HTML scraping | Team season stats from /estadisticas-equipos |

#### Implementation Details

**Fetcher Module**: `src/cbb_data/fetchers/acb.py`
**Shared Utilities**: `src/cbb_data/fetchers/html_scrapers.py` (Spanish column mapping)
**Season ID Format**: Ending year (2024-25 season = `temporada_id/2025`)

**Key Features**:
- HTML-first approach (no public JSON APIs)
- Spanish column names mapped to English via `ACB_COLUMN_MAP`
- Makes/attempts parsing: "5/10" → FGM=5, FGA=10
- 22 stat tables on player page, 20 tables on team page
- May encounter 403 errors (IP blocking) - use fallback strategies

**Known Limitations**:
- ❌ **PBP data**: Not publicly available
- ❌ **Shot charts**: Not publicly available
- ⚠️ **IP blocking**: acb.com may block automated requests (use residential proxy or Zenodo fallback)
- ⚠️ **Historical data**: Requires Zenodo archives for seasons older than 2020

**Fallback Strategies**:
1. **Zenodo Historical Data**: https://zenodo.org/communities/basketball-data (2020 and earlier)
2. **Manual CSV Creation**: Export data manually from website
3. **Rate Limiting**: Increase delay to 2-5 seconds between requests

**Golden Script**: `scripts/golden_acb.py --season 2023-24 --include-games`

**Sample Usage**:
```python
from src.cbb_data.fetchers.acb import (
    fetch_acb_player_season,
    fetch_acb_team_season,
    fetch_acb_schedule
)

# Season-level data (PRIMARY for ACB)
player_season = fetch_acb_player_season("2023-24")
team_season = fetch_acb_team_season("2023-24")

# Game-level data (OPTIONAL - best-effort)
schedule = fetch_acb_schedule("2023-24")
```

---

### 6. LNB (Betclic ÉLITE / Pro A - France)

**Competition**: LNB Pro A (France's top-tier professional basketball league)
**Season Format**: "2024-25" (September-June)
**Official Site**: https://www.lnb.fr/
**Data Source**: HTML scraping (lnb.fr/pro-a/statistiques) + **Investigation pending for game-level**

#### Data Granularities

| Granularity | Status | Method | Notes |
|-------------|--------|--------|-------|
| **schedule** | ⚠️ Optional | HTML scraping → `scrape_lnb_schedule_page()` | May require JavaScript rendering |
| **player_game** | 🔍 Investigation | **PENDING** - See investigation guide | Two potential routes (see below) |
| **team_game** | 🔍 Investigation | **PENDING** - See investigation guide | Depends on player_game source |
| **pbp** | 🔍 Investigation | **CONDITIONAL** - Scenario 2 only | Available if FIBA LiveStats route viable |
| **shots** | 🔍 Investigation | **CONDITIONAL** - Scenario 2 only | Available if FIBA LiveStats route viable |
| **player_season** | ✅ Available | HTML scraping → `scrape_lnb_player_season_html()` | Stats Centre HTML tables |
| **team_season** | ✅ Available | HTML scraping → `read_first_table()` | Standings page static HTML |

#### Current Implementation Status

**✅ IMPLEMENTED** (Season-level data only):
- `fetch_lnb_player_season()`: Player season stats from lnb.fr/pro-a/statistiques
- `fetch_lnb_team_season()`: Team standings from lnb.fr/pro-a/statistiques
- `fetch_lnb_schedule()`: Optional schedule (may require JavaScript)

**❌ NOT YET IMPLEMENTED** (Game-level data - investigation required):
- `fetch_lnb_player_game()`: Raises `NotImplementedError`
- `fetch_lnb_team_game()`: Raises `NotImplementedError`
- `fetch_lnb_pbp()`: Raises `NotImplementedError`
- `fetch_lnb_shots()`: Raises `NotImplementedError`

#### Two Potential Investigation Routes

**Scenario 1: Stats Centre JSON API** (Most Likely)
- Evidence: LNB uses modern "Stats Centre" similar to other French leagues
- Expected: Azure-hosted JSON API (pattern: `lnbstatscenter.azurewebsites.net`)
- Would provide: schedule, player_game, team_game
- Would NOT provide: PBP, shots
- Implementation: Standard REST API client
- Historical depth: Likely 5+ years

**Scenario 2: FIBA LiveStats for FFBB** (Alternative)
- Evidence: LNB Pro A organized by FFBB (French Basketball Federation)
- Expected: FIBA LiveStats infrastructure (same as BCL/BAL/ABA/LKL)
- Would provide: schedule, player_game, team_game, PBP, shots
- Implementation: Reuse existing FIBA shared utilities
- Historical depth: Varies by FIBA coverage

#### Investigation Guide

**Complete step-by-step investigation workflow**: `docs/lnb_game_level_investigation.md`

**Quick Start**:
1. Open https://lnb.fr/pro-a/statistiques in browser
2. Open DevTools (F12) → Network tab → Filter: "XHR"
3. Navigate through stats pages and observe API calls
4. Document findings in `docs/lnb_investigation_findings.md`
5. Test endpoints with `python tools/lnb/api_discovery_helper.py --test-endpoint "URL"`

**Placeholder Functions** (in `lnb.py`):
- `fetch_lnb_team_game()`: Detailed docstring with investigation steps
- `fetch_lnb_pbp()`: Conditional on Scenario 2
- `fetch_lnb_shots()`: Conditional on Scenario 2

**Fetcher Module**: `src/cbb_data/fetchers/lnb.py`
**Shared Utilities**: `src/cbb_data/fetchers/html_scrapers.py` (French column mapping)
**Investigation Tool**: `tools/lnb/api_discovery_helper.py`

**Golden Script**: `scripts/golden_lnb.py --season 2024-25`

**Sample Usage** (current implementation):
```python
from src.cbb_data.fetchers.lnb import (
    fetch_lnb_player_season,  # ✅ Works
    fetch_lnb_team_season,    # ✅ Works
    fetch_lnb_schedule,       # ⚠️ Optional
    fetch_lnb_player_game,    # ❌ NotImplementedError
)

# Season-level data (WORKS NOW)
player_season = fetch_lnb_player_season("2024-25")  # ~300 players
team_season = fetch_lnb_team_season("2024-25")      # 16-18 teams

# Game-level data (REQUIRES INVESTIGATION)
# player_game = fetch_lnb_player_game("2024-25")  # Raises NotImplementedError
```

---

## Summary Statistics

### By Data Granularity

| Granularity | Fully Available | Partial/Optional | Not Available | Pending |
|-------------|-----------------|------------------|---------------|---------|
| **schedule** | 5 leagues | 1 league (LNB) | 0 | 0 |
| **player_game** | 4 leagues (FIBA) | 1 league (ACB) | 0 | 1 (LNB) |
| **team_game** | 4 leagues (FIBA) | 1 league (ACB) | 0 | 1 (LNB) |
| **pbp** | 4 leagues (FIBA) | 0 | 1 (ACB) | 1 (LNB) |
| **shots** | 4 leagues (FIBA) | 0 | 1 (ACB) | 1 (LNB) |
| **player_season** | 6 leagues | 0 | 0 | 0 |
| **team_season** | 6 leagues | 0 | 0 | 0 |

### By League Completeness

**Tier 1 - Fully Complete** (all 7 granularities):
- ✅ BCL (Basketball Champions League) - FIBA LiveStats
- ✅ BAL (Basketball Africa League) - FIBA LiveStats
- ✅ ABA (Adriatic League) - FIBA LiveStats
- ✅ LKL (Lithuania League) - FIBA LiveStats

**Tier 2 - Mostly Complete** (season + game-level):
- ⚠️ ACB (Spain) - 5/7 granularities (missing PBP/shots)

**Tier 3 - Season-Level Only** (requires investigation for game-level):
- 🔍 LNB (France) - 2/7 confirmed (player_season, team_season), 5/7 pending investigation

---

## Implementation Patterns

### Pattern 1: FIBA LiveStats (BCL, BAL, ABA, LKL)

**Architecture**:
- Shared utilities in `fiba_html_common.py`
- JSON API (primary) + HTML fallback
- Competition-specific wrappers in league modules

**Advantages**:
- ✅ Comprehensive data (all 7 granularities)
- ✅ Consistent structure across leagues
- ✅ Historical depth varies by league
- ✅ Shot coordinates included

**Limitations**:
- ⚠️ JSON API sometimes unavailable (fallback to HTML)
- ⚠️ Coordinates are normalized (0-100), not absolute meters/feet

### Pattern 2: HTML Scraping (ACB, LNB)

**Architecture**:
- League-specific scrapers in `html_scrapers.py`
- Multilingual column mapping (Spanish, French)
- Static HTML parsing with BeautifulSoup/pandas

**Advantages**:
- ✅ Works with any HTML table structure
- ✅ No authentication required
- ✅ Can handle multilingual data

**Limitations**:
- ❌ No PBP or shot data (not in HTML)
- ⚠️ Vulnerable to website structure changes
- ⚠️ May encounter IP blocking (403 errors)
- ⚠️ Requires JavaScript rendering for some pages

### Pattern 3: JSON API Discovery (Pending for LNB)

**Architecture**:
- Browser DevTools to discover endpoints
- REST API client with discovered URLs
- Documented in `discovered_endpoints.json`

**Advantages**:
- ✅ Clean, structured JSON data
- ✅ Likely better historical depth
- ✅ Faster than HTML scraping

**Pending Investigation**:
- 🔍 Endpoint discovery via browser DevTools
- 🔍 Authentication/header requirements
- 🔍 Historical data availability

---

## QA and Validation

All leagues use shared QA infrastructure: `src/cbb_data/utils/data_qa.py`

**Standard QA Checks**:
1. ✅ No duplicate rows on key columns (GAME_ID, PLAYER_ID, etc.)
2. ✅ Required columns present (LEAGUE, SEASON, etc.)
3. ✅ No nulls in key columns
4. ✅ Reasonable row counts (min/max thresholds)
5. ✅ Stat ranges valid (0 <= PTS <= 100, etc.)
6. ✅ Team totals match player sums (within tolerance)
7. ✅ Shot coordinates within court bounds (0-100)
8. ✅ PBP final score matches box score

**Golden Scripts** (automated testing):
- `scripts/golden_fiba.py` - BCL, BAL, ABA, LKL
- `scripts/golden_acb.py` - ACB (Spain)
- `scripts/golden_lnb.py` - LNB (France)

---

## Historical Depth by League

| League | Earliest Season | Notes |
|--------|----------------|-------|
| **ABA** | 2001-02 | 21+ years of data |
| **BCL** | 2016-17 | BCL inaugural season |
| **LKL** | 2016-17 | FIBA coverage start |
| **ACB** | 2020-21 | HTML availability (older via Zenodo) |
| **BAL** | 2021 | BAL inaugural season |
| **LNB** | 2020-21 | HTML availability (game-level pending) |

---

## Future Enhancements

### Priority 1: LNB Game-Level Data
- Complete investigation workflow (docs/lnb_game_level_investigation.md)
- Implement discovered endpoints
- Update coverage matrix

### Priority 2: FIBA Optional Upgrades
- Lineup reconstruction from PBP substitution events
- Roster/player bio layer from box scores
- Advanced stats (offensive/defensive ratings)

### Priority 3: ACB Enhancements
- Competition tagging (Liga Regular vs Playoffs vs Copa del Rey)
- Historical depth sweep (Zenodo integration)
- Game-level data for recent seasons

### Priority 4: Additional Leagues
- EuroLeague (requires official API access)
- VTB United League (Russia/Eastern Europe)
- NBL (Australia) - separate package
- CBA (China) - language/encoding challenges

---

## Maintenance Notes

**Update Frequency**: This document should be updated whenever:
1. New league added
2. Data granularity implemented
3. Investigation completed
4. Known limitation discovered
5. Seasonal data availability changes

**Last Major Changes**:
- 2025-11-14: Added LNB investigation framework, comprehensive ACB docs, FIBA cluster consolidation
- [Previous]: Initial FIBA cluster implementation (BCL/BAL/ABA/LKL)

**Ownership**: This document is maintained alongside `PROJECT_LOG.md` for complete project history.

---

**Questions or Issues?**
- Check league-specific fetcher modules (`src/cbb_data/fetchers/*.py`)
- Review investigation guides (`docs/*_investigation.md`)
- Test with golden scripts (`scripts/golden_*.py`)
- Validate with QA helpers (`src/cbb_data/utils/data_qa.py`)
