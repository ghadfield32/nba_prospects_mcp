# Data Source Integration Plan

Detailed plan for wiring each league's data sources to enable accurate, healthy, historical data pulls.

## Overview

This document maps the **reality** of what data is available for free from each league, and provides concrete implementation steps to wire those sources into our fetchers.

### Data Availability Reality Check

| League | Schedule | Player Game | Team Game | PBP | Shots | Player Season | Team Season |
|--------|----------|-------------|-----------|-----|-------|---------------|-------------|
| **BCL** | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ (agg) | ✅ (agg) |
| **BAL** | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ (agg) | ✅ (agg) |
| **ABA** | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ (agg) | ✅ (agg) |
| **LKL** | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ FIBA | ✅ (agg) | ✅ (agg) |
| **ACB** | ⚠️ HTML | ⚠️ HTML | ⚠️ HTML | ❌ Rarely | ❌ Rarely | ✅ HTML/Zenodo | ✅ HTML/agg |
| **LNB** | ⚠️ HTML | ⚠️ JSON? | ⚠️ JSON? | ❌ None | ❌ None | ✅ Stats Centre | ✅ Stats Centre |

**Legend:**
- ✅ = Reliably available, free, public
- ⚠️ = Available but requires discovery/wiring
- ❌ = Not publicly available for free

---

## FIBA Cluster (BCL, BAL, ABA, LKL)

### Data Sources

All four leagues use **FIBA LiveStats** (Genius Sports platform):

**Base URL Pattern:**
```
https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE}/{GAME_ID}/
```

**Available Endpoints:**
- `/bs.html` - Box score (HTML page that loads JSON)
- `/data.json` - Game data JSON (player stats, team stats)
- `/pbp.json` - Play-by-play JSON
- `/shotchart.json` - Shot chart with X/Y coordinates

**Authentication:** None required (public data)

**Rate Limits:** ~2 requests/second recommended (shared across all FIBA leagues)

### Current Status

**Code:** ✅ Complete
- All fetchers implemented: schedule, player_game, team_game, pbp, shots, player_season, team_season
- JSON-first → HTML-fallback pattern in place
- Source metadata tracking implemented

**Data:** ❌ Blocked
- Game indexes only have 3 placeholder IDs per league
- Need 20-50 real FIBA game IDs per season

### Integration Steps

#### 1. Collect Real Game IDs (Manual - 2-4 hours per league)

**BCL (Basketball Champions League):**
```bash
# Interactive collection
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive

# Steps:
# 1. Visit https://www.championsleague.basketball/schedule
# 2. Click on games → "Stats" link
# 3. Copy FIBA LiveStats URL (contains game ID)
# 4. Enter into collector tool
# 5. Collect 20-50 games (focus on Regular Season + Playoffs)
```

**Game ID Pattern:** BCL games typically have IDs in range 500000-600000

**BAL (Basketball Africa League):**
```bash
python tools/fiba/collect_game_ids.py --league BAL --season 2024 --interactive

# Visit: https://thebal.com/schedule/
# BAL has fewer games (~30-40 per season)
# Collect all Regular Season + Playoffs games
```

**Game ID Pattern:** BAL games typically 400000-500000

**ABA (Adriatic League):**
```bash
python tools/fiba/collect_game_ids.py --league ABA --season 2023-24 --interactive

# Visit: https://www.aba-liga.com/schedule.php
# ABA has ~140 games per season (14 teams × 2 rounds + playoffs)
```

**Game ID Pattern:** ABA games typically 600000-700000

**LKL (Lithuanian League):**
```bash
python tools/fiba/collect_game_ids.py --league LKL --season 2023-24 --interactive

# Visit: https://lkl.lt/en/schedule
# LKL has ~100 games per season (10 teams + playoffs)
```

**Game ID Pattern:** LKL games typically 300000-400000

#### 2. Validate Game Indexes

```bash
# For each league
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids
python tools/fiba_game_index_validator.py --league BAL --season 2024 --verify-ids
python tools/fiba_game_index_validator.py --league ABA --season 2023-24 --verify-ids
python tools/fiba_game_index_validator.py --league LKL --season 2023-24 --verify-ids
```

**Expected Output:**
- ✅ All game IDs validate against FIBA LiveStats (HTTP 200)
- ✅ No placeholder patterns (234/1234 endings)
- ✅ Date ranges match official season

#### 3. Run Golden Season Script

```bash
# Once game indexes are validated
python scripts/golden_fiba_bcl.py --season 2023-24
python scripts/golden_fiba_bal.py --season 2024
python scripts/golden_fiba_aba.py --season 2023-24
python scripts/golden_fiba_lkl.py --season 2023-24
```

**Expected Behavior:**
1. Fetches schedule from game index
2. For each game:
   - Fetches player_game stats (JSON → HTML fallback)
   - Fetches team_game stats
   - Fetches PBP events
   - Fetches shot chart with X/Y coords
3. Aggregates to player_season/team_season
4. Runs QA checks
5. Saves to Parquet

**QA Checks:**
- Team totals = sum of player stats
- PBP final score = boxscore final score
- Shot coords within court bounds (0-100 normalized)
- No duplicate player records per game
- Source metadata present (`fiba_json` or `fiba_html`)

#### 4. Backfill Historical Seasons

Once 2023-24 works:

```bash
# Collect IDs for older seasons
python tools/fiba/collect_game_ids.py --league BCL --season 2022-23 --interactive
python tools/fiba/collect_game_ids.py --league BCL --season 2021-22 --interactive

# Run golden season script
python scripts/golden_fiba_bcl.py --season 2022-23
python scripts/golden_fiba_bcl.py --season 2021-22
```

**Historical Coverage:**
- BCL: 2016-17 onwards (when FIBA LiveStats launched)
- BAL: 2021 onwards (inaugural season)
- ABA: ~2015 onwards
- LKL: ~2015 onwards

### FIBA Success Criteria

✅ **Schedule:** 20+ games per season with real IDs
✅ **Player Game:** 200+ player-game records
✅ **Team Game:** 40+ team-game records (2 per game)
✅ **PBP:** 10,000+ events across all games
✅ **Shots:** 1,000+ shots with valid X/Y coords
✅ **QA:** All cross-granularity checks pass

---

## ACB (Spanish League)

### Data Sources

**Official Site:** https://www.acb.com

**Available Data:**

1. **Season Stats Pages (HTML):**
   - Player season stats: `/estadisticas/jugador/estadisticas-individuales`
   - Team season stats: `/estadisticas/equipo/estadisticas-equipo`
   - Reliable, comprehensive, goes back decades

2. **Game Pages (HTML):**
   - Schedule: `/resultados-clasificacion/calendario`
   - Box scores: Individual game pages
   - Variable structure across seasons

3. **Zenodo Historical Dataset:**
   - Record ID: TBD (find actual Zenodo ACB dataset)
   - Coverage: 1983-2023 season stats
   - Format: CSV files per season

**Known Issues:**
- ACB website blocks some IP ranges (403 errors)
- Game-level data structure varies by season
- PBP/shots not consistently available

### Current Status

**Code:** ⚠️ Partial
- Season-level functions implemented
- Game-level functions are placeholders
- Zenodo integration helper exists but not wired

**Data:** ❌ Not tested
- No Zenodo data downloaded
- No recent season tested

### Integration Steps

#### 1. Lock in Season-Level Data (Priority 1)

**Zenodo Integration:**

```bash
# Step 1: Find actual Zenodo dataset
# Search zenodo.org for "ACB basketball" or "Liga Endesa"
# Update ZENODO_RECORD_ID in tools/acb/setup_zenodo_data.py

# Step 2: Download historical data
python tools/acb/setup_zenodo_data.py --download

# Step 3: Validate historical season
python tools/acb/setup_zenodo_data.py --validate --season 2022
python tools/acb/setup_zenodo_data.py --test --season 2022
```

**HTML Scraping (Current Seasons):**

Test from local machine (not container, to avoid 403):

```bash
# Test fetch from local environment
python -c "
from src.cbb_data.fetchers import acb
df_player = acb.fetch_acb_player_season('2023-24')
df_team = acb.fetch_acb_team_season('2023-24')
print(f'Players: {len(df_player)}, Teams: {len(df_team)}')
"
```

**Expected Output:**
- Players: 150-200 (12 teams × ~12 players)
- Teams: 12

#### 2. Implement Game-Level for Recent Season (Priority 2)

**Scope:** 2023-24 season only (expand later)

**Implementation Plan:**

1. **Schedule:**
   - Scrape https://www.acb.com/resultados-clasificacion/calendario
   - Extract: date, home, away, score, round
   - Map to internal GAME_ID (ACB_2023_24_001, ACB_2023_24_002, etc.)

2. **Box Score:**
   - For each game, scrape box score page
   - Extract player stats → player_game table
   - Extract team stats → team_game table

**Code Changes Needed:**

```python
# src/cbb_data/fetchers/acb.py

def fetch_acb_schedule(season: str = "2023-24") -> pd.DataFrame:
    """Fetch ACB schedule for a season"""
    # Implementation:
    # 1. Hit calendario page
    # 2. Parse table rows
    # 3. Return DataFrame with GAME_ID, DATE, HOME, AWAY, etc.
    pass

def fetch_acb_player_game(season: str = "2023-24", game_ids: Optional[List[str]] = None) -> pd.DataFrame:
    """Fetch ACB player game stats"""
    # Implementation:
    # 1. If game_ids not provided, get from schedule
    # 2. For each game, hit box score page
    # 3. Parse player stats table
    # 4. Return DataFrame
    pass

def fetch_acb_team_game(season: str = "2023-24", game_ids: Optional[List[str]] = None) -> pd.DataFrame:
    """Fetch ACB team game stats"""
    # Implementation:
    # 1. Aggregate from player_game, OR
    # 2. Parse team totals from box score page
    pass
```

#### 3. PBP/Shots - Best Effort Only

**Approach:**
- Inspect a few recent game pages via DevTools
- If PBP/shot data exposed via XHR, document endpoints
- Otherwise, explicitly document as "not available"

**Documentation Update:**

```markdown
## ACB Data Availability

### Guaranteed:
- ✅ Player Season (HTML/Zenodo): All seasons, comprehensive
- ✅ Team Season (HTML/agg): All seasons

### Best Effort:
- ⚠️ Schedule: Recent seasons via HTML
- ⚠️ Player/Team Game: 2023-24 confirmed, older seasons variable

### Not Available:
- ❌ PBP: Rarely public
- ❌ Shots: Not consistently available
```

### ACB Success Criteria

**Season-Level (Must Have):**
✅ Player season: 150+ players for 2023-24
✅ Team season: 12 teams for 2023-24
✅ Historical: Zenodo data validated for 5+ older seasons

**Game-Level (Nice to Have):**
✅ Schedule: 300+ games for 2023-24 (full season)
⚠️ Player/Team game: At least one round (9 games) working
❌ PBP/Shots: Explicitly documented as unavailable

---

## LNB Pro A (French League)

### Data Sources

**Official Site:** https://lnb.fr

**Available Data:**

1. **Stats Centre (JSON/HTML):**
   - Player stats: Individual player pages → "Stats de saison" tab
   - Team stats: Team overview pages
   - Likely backed by JSON API

2. **Schedule Pages:**
   - Fixtures: `/calendrier-resultats/`
   - Results with basic box scores

**To Discover:**
- JSON API endpoints for season stats
- Whether game-level JSON exists

### Current Status

**Code:** ❌ Placeholder
- Functions exist but return empty DataFrames
- No API endpoints discovered yet

**Data:** ❌ None
- No API discovery session completed

### Integration Steps

#### 1. API Discovery (Manual - 2-3 hours)

**DevTools Session:**

```bash
# Run discovery helper
python tools/lnb/api_discovery_helper.py --discover
```

**Steps:**
1. Open https://lnb.fr in Chrome/Firefox with DevTools
2. Navigate to Stats → Joueurs (Players)
3. Network tab → XHR filter
4. Switch seasons, teams, filters
5. Document URLs that return JSON

**Expected Endpoints to Find:**

```
# Player season stats
GET https://lnb.fr/api/stats/players?season=2023-24&competition=betclic-elite

# Team season stats
GET https://lnb.fr/api/stats/teams?season=2023-24&competition=betclic-elite

# (Possibly) Game schedule
GET https://lnb.fr/api/calendar?season=2023-24
```

**Document in:**
`tools/lnb/discovered_endpoints.json`

```json
{
  "player_season_stats": {
    "url": "https://lnb.fr/api/stats/players",
    "method": "GET",
    "params": {
      "season": "2023-24",
      "competition": "betclic-elite"
    },
    "headers": {
      "User-Agent": "...",
      "Referer": "https://lnb.fr/stats/"
    }
  }
}
```

#### 2. Implement Season-Level Fetchers

**Code Changes:**

```python
# src/cbb_data/fetchers/lnb.py

# After discovery, update these functions:

def fetch_lnb_player_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LNB player season stats via discovered API"""
    url = "https://lnb.fr/api/stats/players"  # Use discovered URL
    params = {
        "season": season,
        "competition": "betclic-elite"
    }

    response = requests.get(url, params=params, headers=HEADERS)
    response.raise_for_status()

    data = response.json()

    # Parse JSON to DataFrame
    # (Structure depends on actual API response)
    players = data.get("players", [])
    df = pd.DataFrame([
        {
            "LEAGUE": "LNB",
            "SEASON": season,
            "PLAYER_ID": p.get("id"),
            "PLAYER_NAME": p.get("name"),
            "TEAM": p.get("team"),
            "GP": p.get("games_played"),
            "MIN": p.get("minutes"),
            "PTS": p.get("points"),
            # ... other stats
        }
        for p in players
    ])

    return df

def fetch_lnb_team_season(season: str = "2023-24") -> pd.DataFrame:
    """Fetch LNB team season stats via discovered API"""
    # Similar implementation for teams
    pass
```

#### 3. Game-Level - Decide Scope

**Two Options:**

**Option A: Skip game-level for v1**
- Focus on season-level scouting data
- Mark schedule/player_game/team_game as "not implemented"
- Faster to production

**Option B: Implement if JSON exists**
- If discovery finds game-level JSON, implement
- Otherwise, fallback to Option A

**Recommendation:** Option A (season-level only for v1)

LNB's primary value is for player scouting. Season aggregates are sufficient for that use case.

### LNB Success Criteria

**Must Have:**
✅ Player season: 150+ players for 2023-24
✅ Team season: 18 teams for 2023-24
✅ API endpoints documented in tools/lnb/discovered_endpoints.json

**Nice to Have:**
⚠️ Schedule: If JSON found, implement
❌ PBP/Shots: Explicitly out of scope

---

## Data Quality Standards (All Leagues)

### Minimum Data Requirements

**Schedule:**
- Row count: >= 10 games
- No duplicate GAME_IDs
- All dates valid format (YYYY-MM-DD)
- LEAGUE and SEASON match expected values

**Player Game:**
- Row count: >= 50 player-games
- No duplicates on (GAME_ID, TEAM_ID, PLAYER_ID)
- PTS in range [0, 100]
- MIN in range [0, 60]

**Team Game:**
- Row count: >= 20 team-games
- No duplicates on (GAME_ID, TEAM_ID)
- PTS in range [0, 200]
- Exactly 2 teams per game

**Cross-Granularity:**
- Team totals = sum of player stats (tolerance: ±1)
- All games in player_game exist in schedule
- PBP final score = boxscore (sample of 10 games)

### Storage Format

**Parquet (Recommended):**
```python
save_to_disk(df, f"data/golden/{league}/{season}/player_game.parquet", format="parquet")
```

**File Structure:**
```
data/golden/
├── bcl/
│   ├── 2023_24/
│   │   ├── schedule.parquet
│   │   ├── player_game.parquet
│   │   ├── team_game.parquet
│   │   ├── pbp.parquet
│   │   ├── shots.parquet
│   │   ├── player_season.parquet
│   │   ├── team_season.parquet
│   │   └── SUMMARY.txt
│   └── 2022_23/
│       └── ...
├── bal/
├── aba/
├── lkl/
├── acb/
└── lnb/
```

---

## Timeline Estimates

### FIBA Cluster (BCL/BAL/ABA/LKL)

**Per League:**
- Game ID collection: 2-3 hours (manual)
- Validation: 30 minutes (automated)
- Golden season script run: 10-15 minutes
- QA review: 15 minutes

**Total for all 4 leagues:** ~12-15 hours

### ACB

**Season-Level:**
- Zenodo discovery: 1 hour
- Zenodo download: 30 minutes
- Historical validation: 1 hour
- Current season HTML test: 1 hour

**Game-Level (one season):**
- Schedule scraper: 2 hours
- Box score scraper: 3 hours
- Testing & QA: 1 hour

**Total:** ~9-10 hours

### LNB

**API Discovery:**
- DevTools session: 2-3 hours
- Endpoint documentation: 1 hour
- Implementation: 2-3 hours
- Testing: 1 hour

**Total:** ~6-8 hours

### Grand Total

**All leagues production-ready:** 27-33 hours

**Critical path:** FIBA cluster (blocks most value)

---

## Next Steps (Priority Order)

### Week 1: FIBA Cluster

- [ ] BCL: Collect 30 game IDs for 2023-24
- [ ] BCL: Validate and run golden season script
- [ ] BAL: Collect 30 game IDs for 2024
- [ ] BAL: Validate and run golden season script
- [ ] ABA: Collect 40 game IDs for 2023-24
- [ ] ABA: Validate and run golden season script
- [ ] LKL: Collect 30 game IDs for 2023-24
- [ ] LKL: Validate and run golden season script

**Deliverable:** 4 leagues fully operational for recent season

### Week 2: ACB + LNB

- [ ] ACB: Find and download Zenodo dataset
- [ ] ACB: Validate 5 historical seasons
- [ ] ACB: Test current season HTML scraping
- [ ] LNB: DevTools API discovery session
- [ ] LNB: Implement player_season/team_season
- [ ] LNB: Test with 2023-24 data

**Deliverable:** ACB season-level working, LNB season-level working

### Week 3: Backfill + Documentation

- [ ] FIBA: Backfill 2 more seasons per league (2022-23, 2021-22)
- [ ] ACB: Implement schedule + box score for 2023-24
- [ ] Update capability matrix
- [ ] Update PROJECT_LOG
- [ ] Document known limitations

**Deliverable:** Multi-season historical coverage, comprehensive docs

---

## Success Metrics

**Production Ready = All of:**

1. ✅ At least 1 recent season working per league
2. ✅ All core granularities present (schedule, player_game, team_game)
3. ✅ All QA checks passing
4. ✅ Data saved to Parquet with proper schema
5. ✅ Golden season script runs end-to-end
6. ✅ Known limitations documented

**Bonus:**
- Historical backfill (2+ seasons per league)
- PBP and shots data (FIBA cluster)
- Game-level data (ACB 2023-24)

Last Updated: 2025-11-14
