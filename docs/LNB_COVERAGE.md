# LNB Pro A - Data Coverage Documentation

**Last Updated:** 2025-11-15
**Validation Date:** 2025-11-15

## Executive Summary

LNB Pro A is integrated with **7/7 datasets** but has **limited historical coverage** due to API constraints. The LNB Schedule API only provides current season data; historical coverage was obtained through manual UUID discovery.

**Coverage Overview:**
- **Normalized Box Scores:** 2021-2025 (4 seasons, 34 total games)
- **PBP/Shots Data:** 2025-2026 (8 games, 3,336 events, 973 shots)
- **Live API Data:** Current season only (2024-2025)

---

## Dataset Coverage Matrix

### 1. Schedule Data (`schedule`)

| Source | Coverage | Games | Method |
|--------|----------|-------|--------|
| LNB API | **Current season only** (2024-2025) | 8 games | `fetch_lnb_schedule_v2()` |

**Limitation:** LNB Schedule API (`/match/getCalenderByDivision`) only maintains current season data. Historical seasons return empty responses.

**Test Result:**
```
Tested seasons 2015-2025:
- 2024-2025: ✅ 8 games with UUIDs
- 2015-2024: ❌ All empty responses
```

---

### 2. Player Season Stats (`player_season`)

| Source | Coverage | Method |
|--------|----------|--------|
| LNB API | **Current season only** (2024-2025) | `fetch_lnb_player_season_v2()` |

**Limitation:** Requires individual `player_id` parameter lookups. No bulk endpoint for all players.

**Usage:**
```python
# Single player lookup
df = fetch_lnb_player_season_v2(season=2025, player_id=5622)
```

---

### 3. Team Season Stats (`team_season`)

| Source | Coverage | Method |
|--------|----------|--------|
| LNB API | **Current season only** (2024-2025) | `fetch_lnb_team_season_v2()` |

**Limitation:** Same as schedule - API only provides current season standings/rankings.

---

### 4. Player Game Stats (`player_game`) - Normalized

| Season | Games | Player Records | Status | Source |
|--------|-------|----------------|--------|--------|
| 2021-2022 | 1 | 18 | ✅ Valid | Manual UUID discovery |
| 2022-2023 | 1 | 17 | ✅ Valid | Manual UUID discovery |
| 2023-2024 | 16 | 288 | ✅ Valid | Manual UUID discovery |
| 2024-2025 | 16 | 294 | ✅ Valid | Manual UUID discovery |
| **Total** | **34** | **617** | | |

**Format:** Parquet files partitioned by season
**Location:** `data/normalized/lnb/player_game/season=YYYY-YYYY/`
**Schema:** 27 columns (standardized box score format)

**Key Insight:** The 2023-2024 and 2024-2025 data (16 games each) likely represent a specific competition (e.g., Leaders Cup, playoffs) rather than full regular season coverage.

---

### 5. Team Game Stats (`team_game`) - Normalized

| Season | Games | Team Records | Status | Source |
|--------|-------|--------------|--------|--------|
| 2021-2022 | 1 | 2 | ✅ Valid | Manual UUID discovery |
| 2022-2023 | 1 | 2 | ✅ Valid | Manual UUID discovery |
| 2023-2024 | 16 | 32 | ✅ Valid | Manual UUID discovery |
| 2024-2025 | 16 | 32 | ✅ Valid | Manual UUID discovery |
| **Total** | **34** | **68** | | |

**Format:** Parquet files partitioned by season
**Location:** `data/normalized/lnb/team_game/season=YYYY-YYYY/`
**Schema:** 26 columns (standardized team box score format)

---

### 6. Play-by-Play (`pbp`)

| Season | Games | Events | Status | Source |
|--------|-------|--------|--------|--------|
| 2025-2026 | 8 | 3,336 | ✅ Valid | Atrium Sports API via UUIDs |

**Format:** Parquet file
**Location:** `data/lnb/historical/2025-2026/pbp_events.parquet`
**Schema:** Event-level data with timestamps, action types, player IDs, scores

**Limitation:** Only current/recent season data available. Older seasons would require manual UUID discovery.

---

### 7. Shot Data (`shots`)

| Season | Games | Shots | Status | Source |
|--------|-------|-------|--------|--------|
| 2025-2026 | 8 | 973 | ✅ Valid | Atrium Sports API via UUIDs |

**Format:** Parquet file
**Location:** `data/lnb/historical/2025-2026/shots.parquet`
**Schema:** Shot coordinates (X, Y), shot type, made/missed, player IDs

**Limitation:** Same as PBP - requires UUIDs from manual discovery for historical seasons.

---

## Data Quality Assessment

**Validation Date:** 2025-11-15

### Summary Statistics

- **Total Seasons Covered:** 5 (2021-2022 through 2025-2026)
- **Total Games:** 42 (34 normalized + 8 raw PBP/shots)
- **Total Player-Game Records:** 617
- **Total Team-Game Records:** 68
- **Total PBP Events:** 3,336
- **Total Shots:** 973
- **Data Quality Issues:** None detected

### Data Integrity

✅ **All datasets passed validation:**
- No null values in critical columns (GAME_ID, GAME_DATE, PLAYER_ID, TEAM_ID)
- Consistent schemas across seasons
- Valid date ranges
- Unique game/player/team identifiers present

---

## API Limitations

### LNB Schedule API

**Endpoint:** `https://api-prod.lnb.fr/match/getCalenderByDivision`

**Parameters:**
- `division_external_id`: Division ID (1 = Betclic ÉLITE)
- `year`: Season end year (e.g., 2025 for 2024-2025)

**Limitation:** Only returns current season schedule. Historical seasons return empty response:
```
parse_calendar: Empty or invalid input (expected list of games)
```

**Test Results (2025-11-15):**
- ✅ `year=2025` (2024-2025): 8 games
- ❌ `year=2024` (2023-2024): Empty
- ❌ `year=2023` (2022-2023): Empty
- ❌ `year=2015-2022`: All empty

### Atrium Sports API

**Endpoint:** Requires game UUIDs from LNB.fr website

**Access Method:**
1. Navigate to LNB.fr game center for specific game
2. Extract UUID from URL: `https://www.lnb.fr/matchs/[UUID]`
3. Use UUID to fetch PBP/shots from Atrium API

**Limitation:** Manual discovery process; no bulk historical UUID endpoint available.

---

## Historical Coverage Methodology

The existing normalized data (2021-2025) was obtained through:

1. **Manual UUID Discovery:** Scraping LNB.fr game center for historical game UUIDs
2. **Atrium API Ingestion:** Using discovered UUIDs to fetch PBP/shots data
3. **Normalization Pipeline:** Transforming PBP events into standardized box scores
4. **Parquet Export:** Partitioning by season and saving to data lake

**Evidence:**
- `tools/lnb/discover_historical_fixture_uuids.py` - Manual UUID scraper
- `tools/lnb/bulk_ingest_pbp_shots.py` - Bulk data ingestion pipeline
- `tools/lnb/create_normalized_tables.py` - Transformation pipeline

---

## Coverage Gaps

### Missing Seasons

**No data available for:**
- 2010-2020 (11 seasons)
- Pre-2010 historical seasons

**Reason:** Would require extensive manual UUID discovery from LNB.fr website archives.

### Incomplete Seasons

**Partial coverage for:**
- 2021-2022: Only 1 game (likely test/validation)
- 2022-2023: Only 1 game (likely test/validation)
- 2023-2024: 16 games (subset of season, possibly playoff/cup games)
- 2024-2025: 16 games (subset of season, possibly playoff/cup games)

**Regular Season Context:**
- LNB Pro A regular season: ~306 games per season (18 teams × 34 games each ÷ 2)
- Current coverage: 16 games ≈ 5% of full season

---

## Extension Possibilities

### Option A: Current Season Monitoring (Recommended)
**Effort:** Low (1-2 hours setup)
**Coverage:** Ongoing current season updates

**Implementation:**
1. Scheduled fetch of current season schedule (weekly)
2. Extract new game UUIDs
3. Ingest PBP/shots after game completion
4. Update normalized tables

**Tools:**
- `tools/lnb/pull_all_historical_data.py` - Already exists
- Add cron/scheduler for automation

### Option B: Manual Historical Backfill
**Effort:** High (2-4 hours per season)
**Coverage:** Additional historical seasons (e.g., 2018-2021)

**Implementation:**
1. Scrape LNB.fr game archives for UUIDs
2. Bulk ingest PBP/shots via Atrium API
3. Run normalization pipeline

**Tools:**
- `tools/lnb/discover_historical_fixture_uuids.py` - Requires manual work
- `tools/lnb/bulk_ingest_pbp_shots.py` - Already exists

### Option C: Full Regular Season Coverage
**Effort:** Very High (20+ hours)
**Coverage:** Complete regular season for selected years

**Challenges:**
- Atrium API may not have PBP for all games
- Older games may lack detailed event data
- Rate limiting on bulk requests

---

## Recommendations

### For Current Use

1. **Leverage Existing Coverage:**
   - Use 2023-2025 normalized data (32 games) for analysis
   - Use 2025-2026 PBP/shots (8 games) for event-level research

2. **API Usage:**
   - Use Schedule/Player/Team Season APIs for **current season only**
   - Do not expect historical data from these endpoints

3. **Data Fetching:**
   - Call `get_dataset()` with appropriate filters
   - For normalized data, specify `season="2023-2024"` (4-digit format)
   - For API data, specify `season="2024-25"` (2-digit format)

### For Future Development

1. **Automation:**
   - Set up weekly schedule monitoring for current season
   - Auto-ingest completed games
   - Maintain running game index

2. **Documentation:**
   - Update this file when new seasons are added
   - Document any API changes or new endpoints
   - Track data quality metrics

3. **Historical Expansion:**
   - Prioritize recent seasons (2020-2023) if backfilling
   - Focus on playoff/cup games for higher value data
   - Consider cost/benefit of full season coverage

---

## Usage Examples

### Current Season Schedule
```python
from cbb_data.fetchers import lnb

# Current season only (2024-2025)
df = lnb.fetch_lnb_schedule_v2(season=2025, division=1)
print(f"Found {len(df)} games")
```

### Normalized Box Scores (Historical)
```python
from cbb_data.fetchers import lnb

# Player game logs for 2023-2024
df = lnb.fetch_lnb_player_game_normalized(season="2023-2024")
print(f"Found {len(df)} player-game records across {df['GAME_ID'].nunique()} games")
```

### PBP/Shots (Current Season)
```python
from cbb_data.fetchers import lnb

# Play-by-play for 2025-2026
df = lnb.fetch_lnb_pbp_historical(season="2025-2026")
print(f"Found {len(df)} PBP events")

# Shot data for 2025-2026
df = lnb.fetch_lnb_shots_historical(season="2025-2026")
print(f"Found {len(df)} shots")
```

---

## Files and Tools Reference

### Discovery Tools
- `tools/lnb/discover_max_historical_coverage.py` - API coverage tester
- `tools/lnb/discover_historical_fixture_uuids.py` - Manual UUID scraper
- `tools/lnb/validate_existing_coverage.py` - Data validation tool

### Ingestion Tools
- `tools/lnb/build_game_index.py` - Master game index builder
- `tools/lnb/bulk_ingest_pbp_shots.py` - Bulk PBP/shots fetcher
- `tools/lnb/pull_all_historical_data.py` - Complete pipeline orchestrator

### Normalization Tools
- `tools/lnb/create_normalized_tables.py` - PBP to box score transformer

### Reports
- `tools/lnb/historical_coverage_report.json` - API availability report
- `tools/lnb/coverage_validation_report.json` - Data quality report
- `tools/lnb/fixture_uuids_by_season.json` - UUID mapping registry

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-15 | 1.0 | Initial documentation after validation |

---

## Contact & Support

For questions about LNB data coverage:
- Review this documentation first
- Check validation reports in `tools/lnb/`
- Consult fetcher source code in `src/cbb_data/fetchers/lnb.py`
