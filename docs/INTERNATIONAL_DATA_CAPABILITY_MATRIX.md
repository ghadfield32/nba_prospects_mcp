# International Basketball Data Capability Matrix

Comprehensive overview of data availability across international basketball leagues.

**Last Updated**: 2025-11-14 (Session 2025-11-14C)

## Quick Reference

| League | Player Season | Team Season | Schedule | Player Game | Team Game | PBP | Shots | Notes |
|--------|--------------|-------------|----------|-------------|-----------|-----|-------|-------|
| **BCL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | JSON API + HTML fallback |
| **BAL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | JSON API + HTML fallback |
| **ABA** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | JSON API + HTML fallback |
| **LKL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | JSON API + HTML fallback |
| **ACB** | ✅ | ✅ | 📋 | 📋 | 📋 | 📋 | 📋 | Web scraping + CSV fallback |
| **LNB** | 📋 | ✅ | 📋 | 📋 | 📋 | 📋 | 📋 | Team standings only |

**Legend**:
- ✅ **Available**: Fully implemented and tested
- 📋 **Requires Implementation**: Framework exists, needs API discovery or scraping logic
- ❌ **Not Available**: Data source doesn't provide this granularity

---

## Detailed Breakdown

### FIBA Cluster (BCL, BAL, ABA, LKL)

All FIBA leagues share the same infrastructure using FIBA LiveStats API.

#### Data Sources
1. **Primary**: FIBA LiveStats JSON API
   - Rich data with shot coordinates (X/Y)
   - Play-by-play with timestamps
   - Full box scores with advanced stats

2. **Fallback**: FIBA LiveStats HTML Scraping
   - Used when JSON API fails
   - Basic box scores (no shot coordinates)
   - Play-by-play events

#### Availability Matrix

| Granularity | BCL | BAL | ABA | LKL | Implementation | Data Source |
|-------------|-----|-----|-----|-----|----------------|-------------|
| **schedule** | ✅ | ✅ | ✅ | ✅ | `fetch_schedule()` | Game index CSV → JSON/HTML |
| **player_game** | ✅ | ✅ | ✅ | ✅ | `fetch_player_game()` | JSON API → HTML fallback |
| **team_game** | ✅ | ✅ | ✅ | ✅ | `fetch_team_game()` | Aggregated from player_game |
| **pbp** | ✅ | ✅ | ✅ | ✅ | `fetch_pbp()` | JSON API → HTML fallback |
| **shots** | ✅ | ✅ | ✅ | ✅ | `fetch_shots()` | JSON API only (has X/Y coords) |
| **player_season** | ✅ | ✅ | ✅ | ✅ | `fetch_player_season()` | Aggregated from player_game |
| **team_season** | ✅ | ✅ | ✅ | ✅ | `fetch_team_season()` | Aggregated from team_game |

#### Column Availability

**player_game** (JSON API):
- ✅ Basic: PLAYER_NAME, TEAM, MIN, PTS, REB, AST, STL, BLK, TOV, PF
- ✅ Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
- ✅ Rebounds: OREB, DREB
- ✅ Advanced: PLUS_MINUS, EFF_RATING
- ✅ Metadata: GAME_ID, SEASON, LEAGUE, SOURCE

**shots** (JSON API):
- ✅ Location: X, Y (0-100 scale, court coordinates)
- ✅ Shot Info: SHOT_TYPE (2PT/3PT), SHOT_RESULT (MADE/MISSED)
- ✅ Context: PLAYER_NAME, TEAM, PERIOD, CLOCK
- ✅ Metadata: GAME_ID, SEASON, LEAGUE, SOURCE

**pbp** (JSON API):
- ✅ Events: ACTION_TYPE, DESCRIPTION
- ✅ Timing: PERIOD, CLOCK, EVENT_NUM
- ✅ Players: PLAYER_NAME, TEAM
- ✅ Score: SCORE_HOME, SCORE_AWAY
- ✅ Metadata: GAME_ID, SEASON, LEAGUE, SOURCE

#### Game Index Requirements

FIBA leagues require game index CSV files to map seasons to game IDs:

**Location**: `data/game_indexes/{LEAGUE}_{SEASON}.csv`

**Required Columns**:
```csv
LEAGUE,SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE,VERIFIED
BCL,2023-24,123456,2023-10-15,Team A,Team B,85,72,True
```

**Building Indexes**:
```bash
# Manual discovery (recommended)
python tools/fiba/build_game_index.py --league BCL --season 2023-24

# Automated scraping (requires league-specific HTML parsing)
python tools/fiba/build_game_index.py --league BCL --season 2023-24 --validate
```

See `tools/fiba/README.md` for detailed instructions.

#### Historical Coverage

| League | Earliest Season | Data Availability |
|--------|----------------|-------------------|
| **BCL** | 2016-17 | All seasons with game index |
| **BAL** | 2021 | All seasons with game index |
| **ABA** | 2000-01 | All seasons with game index |
| **LKL** | 2018-19 | Reliable data from 2018-19+ |

---

### ACB (Spanish League)

#### Data Sources
1. **Primary**: ACB Website Scraping
   - Subject to 403 blocking
   - Requires User-Agent and headers

2. **Fallback 1**: Manual CSV Files
   - User-created from acb.com
   - Placed in `data/manual/acb/`

3. **Fallback 2**: Zenodo Historical Archive
   - Seasons 1983-2023
   - Automatic fallback for old seasons

#### Availability Matrix

| Granularity | Status | Implementation | Notes |
|-------------|--------|----------------|-------|
| **player_season** | ✅ | `fetch_acb_player_season()` | Totals, PerGame, Per100Poss |
| **team_season** | ✅ | `fetch_acb_team_season()` | W-L, ratings, standings |
| **schedule** | 📋 | `fetch_acb_schedule()` | Requires API discovery |
| **player_game** | 📋 | `fetch_acb_box_score()` | Requires API discovery |
| **team_game** | 📋 | N/A | Would aggregate from player_game |
| **pbp** | 📋 | `fetch_acb_play_by_play()` | Requires API discovery |
| **shots** | 📋 | `fetch_acb_shot_chart()` | Requires API discovery |

#### Column Availability

**player_season** (available):
- ✅ Basic: PLAYER_NAME, TEAM, GP, MIN, PTS, REB, AST, STL, BLK, TOV, PF
- ✅ Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
- ✅ Advanced: EFF, PLUS_MINUS, TS_PCT
- ✅ Per-Mode: Totals, PerGame, Per100Poss, Per36Min
- ✅ Metadata: SEASON, LEAGUE, SOURCE

**team_season** (available):
- ✅ Record: GP, W, L, WIN_PCT
- ✅ Ratings: OFF_RATING, DEF_RATING, NET_RATING
- ✅ Pace: PACE, POSS
- ✅ Metadata: SEASON, LEAGUE

**schedule** (requires implementation):
- 📋 Game Info: GAME_ID, GAME_DATE, HOME_TEAM, AWAY_TEAM
- 📋 Scores: HOME_SCORE, AWAY_SCORE
- 📋 Venue: ARENA, ATTENDANCE
- 📋 Status: GAME_STATUS (scheduled/final/postponed)

**player_game** (requires implementation):
- 📋 Would match player_season columns on per-game basis
- 📋 Additional: GAME_ID, STARTER (bool)

#### Implementation Status

**✅ Implemented**:
- Player season aggregates (all per-modes)
- Team season aggregates
- Error handling (403, timeout, network)
- Manual CSV fallback mechanism
- Zenodo historical data integration

**📋 Requires Implementation**:
- Schedule scraping (see `tools/acb/README.md`)
- Box score scraping
- Play-by-play scraping
- Shot chart scraping

**Implementation Guide**: `tools/acb/README.md`
- Browser DevTools workflow
- API endpoint discovery
- Manual CSV format specifications
- Error handling patterns

#### Historical Coverage

| Era | Status | Data Source |
|-----|--------|-------------|
| **1983-2023** | ✅ | Zenodo archive (automatic) |
| **2024+** | ✅ | Web scraping (subject to 403) |
| **Manual CSV** | ✅ | User-provided fallback |

---

### LNB Pro A (French League)

#### Data Sources
1. **Available**: Static HTML (team standings)
   - Scrapes standings table
   - French character support (UTF-8)

2. **Requires Discovery**: JavaScript Stats Centre
   - Uses dynamic loading
   - Requires browser DevTools to find API

#### Availability Matrix

| Granularity | Status | Implementation | Notes |
|-------------|--------|----------------|-------|
| **player_season** | 📋 | `fetch_lnb_player_season()` | Requires API discovery |
| **team_season** | ✅ | `fetch_lnb_team_season()` | HTML scraping works |
| **schedule** | 📋 | `fetch_lnb_schedule()` | Requires API discovery |
| **player_game** | 📋 | N/A | Requires API discovery |
| **team_game** | 📋 | N/A | Requires API discovery |
| **pbp** | 📋 | N/A | Requires API discovery |
| **shots** | 📋 | N/A | Requires API discovery |

#### Column Availability

**team_season** (available):
- ✅ Standings: RANK, TEAM, GP, W, L, WIN_PCT
- ✅ Points: PTS_FOR, PTS_AGAINST, PTS_DIFF
- ✅ Splits: HOME_RECORD, AWAY_RECORD
- ✅ Form: FORM (recent W/L string), NEXT_OPPONENT
- ✅ Metadata: LEAGUE, SEASON, COMPETITION

**player_season** (requires implementation):
- 📋 Expected: PLAYER_NAME, TEAM, GP, MIN, PTS, REB, AST
- 📋 Shooting: FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT
- 📋 Advanced: STL, BLK, TOV, PF
- 📋 Metadata: LEAGUE, SEASON, COMPETITION

#### Implementation Status

**✅ Implemented**:
- Team standings (HTML scraping)
- UTF-8 French character support
- Rate limiting
- Empty DataFrame placeholders with correct schemas

**📋 Requires Implementation**:
- Stats Centre API discovery
- Player statistics
- Game schedules
- Box scores
- Play-by-play

**Implementation Guide**: `tools/lnb/README.md`
- Browser DevTools workflow for API discovery
- Endpoint documentation templates
- JSON parsing patterns
- Header/cookie requirements

#### Historical Coverage

| Era | Status | Notes |
|-----|--------|-------|
| **Current Season** | ✅ | Team standings via HTML |
| **Historical** | 📋 | Depends on API availability |
| **Manual CSV** | ✅ | Can be created manually |

---

## Source Metadata Tracking

All fetchers track data source for transparency and debugging.

### FIBA Leagues

| SOURCE Value | Meaning | Quality |
|-------------|---------|---------|
| `fiba_json` | FIBA LiveStats JSON API | ⭐⭐⭐ High (has shot coords) |
| `fiba_html` | FIBA LiveStats HTML fallback | ⭐⭐ Medium (no shot coords) |

### ACB

| SOURCE Value | Meaning | Quality |
|-------------|---------|---------|
| `acb_api` | ACB website JSON API | ⭐⭐⭐ High |
| `acb_html` | ACB website HTML scraping | ⭐⭐ Medium |
| `manual_csv` | User-provided CSV file | ⭐ Variable (user-dependent) |
| `zenodo` | Historical archive | ⭐⭐⭐ High (validated) |

### LNB

| SOURCE Value | Meaning | Quality |
|-------------|---------|---------|
| `lnb_html` | LNB website HTML scraping | ⭐⭐ Medium (team standings) |
| `lnb_api` | LNB Stats Centre API | ⭐⭐⭐ High (once discovered) |

---

## Usage Examples

### Check Data Availability

```python
from src.cbb_data.fetchers import bcl, acb, lnb

# FIBA - check source breakdown
bcl_data = bcl.fetch_player_game("2023-24")
print("BCL sources:")
print(bcl_data["SOURCE"].value_counts())

# ACB - check if data is available
acb_data = acb.fetch_acb_player_season("2024")
if not acb_data.empty:
    print(f"ACB: {len(acb_data)} players")
    if "SOURCE" in acb_data.columns:
        print(f"Source: {acb_data['SOURCE'].iloc[0]}")

# LNB - check team standings (available)
lnb_standings = lnb.fetch_lnb_team_season("2024")
if not lnb_standings.empty:
    print(f"LNB standings: {len(lnb_standings)} teams")
else:
    print("LNB standings not available")

# LNB - check player season (not yet implemented)
lnb_players = lnb.fetch_lnb_player_season("2024")
if lnb_players.empty:
    print("LNB player season requires API discovery")
    print("See tools/lnb/README.md for implementation guide")
```

### Validate Data Completeness

```python
def check_data_availability(fetcher_module, league_name, season):
    """Check what data is available for a league"""
    results = {}

    # Try each granularity
    try:
        schedule = fetcher_module.fetch_schedule(season)
        results["schedule"] = not schedule.empty
    except:
        results["schedule"] = False

    try:
        player_game = fetcher_module.fetch_player_game(season)
        results["player_game"] = not player_game.empty
    except:
        results["player_game"] = False

    try:
        pbp = fetcher_module.fetch_pbp(season)
        results["pbp"] = not pbp.empty
    except:
        results["pbp"] = False

    try:
        shots = fetcher_module.fetch_shots(season)
        results["shots"] = not shots.empty
    except:
        results["shots"] = False

    print(f"\n{league_name} Data Availability:")
    for key, available in results.items():
        status = "✅" if available else "❌"
        print(f"  {status} {key}")

    return results

# Check all FIBA leagues
from src.cbb_data.fetchers import bcl, bal, aba, lkl

for name, module in [("BCL", bcl), ("BAL", bal), ("ABA", aba), ("LKL", lkl)]:
    check_data_availability(module, name, "2023-24")
```

---

## Development Roadmap

### High Priority
1. ✅ Fix FIBA league fetchers (aba.py, bal.py, lkl.py) - **COMPLETE**
2. ✅ Add validation test suite - **COMPLETE**
3. 📋 Complete game index builders for FIBA leagues (requires website inspection)
4. 📋 Implement ACB schedule/box score (requires API discovery)
5. 📋 Implement LNB Stats Centre API (requires API discovery)

### Medium Priority
1. Shot chart visualization examples
2. Advanced analytics (four factors, efficiency ratings)
3. Historical data integration (expand Zenodo coverage)
4. Performance optimization (parallel fetching, better caching)

### Low Priority
1. Additional European leagues (BBL, BSL, VTB)
2. Asian leagues (CBA, KBL, B.League)
3. Latin American leagues (LNB Argentina, NBB Brazil)

---

## Contributing

To improve data availability:

1. **FIBA Leagues**: Create game index CSVs
   - See `tools/fiba/build_game_index.py`
   - Manual discovery from league websites

2. **ACB**: Discover API endpoints
   - See `tools/acb/README.md`
   - Use browser DevTools on acb.com

3. **LNB**: Discover Stats Centre API
   - See `tools/lnb/README.md`
   - Use browser DevTools on lnb.fr

4. **New Leagues**: Follow existing patterns
   - JSON-first, HTML fallback
   - Source metadata tracking
   - Comprehensive error handling

---

## References

- **Validation Tests**: `tests/test_international_data_sources.py`
- **Usage Examples**: `docs/INTERNATIONAL_LEAGUES_EXAMPLES.md`
- **Web Scraping Findings**: `docs/LEAGUE_WEB_SCRAPING_FINDINGS.md`
- **FIBA Tools**: `tools/fiba/`
- **ACB Tools**: `tools/acb/`
- **LNB Tools**: `tools/lnb/`
- **Project History**: `PROJECT_LOG.md`

---

**Maintainer**: Data Engineering Team
**Last Updated**: 2025-11-14 (Session 2025-11-14C)
