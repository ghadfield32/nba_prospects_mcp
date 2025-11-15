# LNB Historical Data Pipeline - Implementation Plan

**Date**: 2025-11-15
**Goal**: Build production-ready historical data ingestion and validation pipeline for LNB Pro A

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     LNB Data Pipeline                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
          ┌─────────▼─────────┐    ┌─────────▼─────────┐
          │  Game Index        │    │  Data Sources     │
          │  (Single Source    │    │  - LNB API        │
          │   of Truth)        │    │  - Atrium API     │
          └─────────┬─────────┘    │  - Web Scraper    │
                    │               └────────┬──────────┘
                    │                        │
          ┌─────────▼─────────────────────────▼──────────┐
          │         Bulk Ingestion Pipeline              │
          │  - PBP fetcher (by game UUID)                │
          │  - Shots fetcher (by game UUID)              │
          │  - Boxscore fetcher (by game UUID)           │
          │  - Checkpointing & error logging             │
          └─────────┬────────────────────────────────────┘
                    │
          ┌─────────▼─────────────────────────────────────┐
          │     Raw Data Storage (Partitioned Parquet)    │
          │  data/raw/lnb/                                │
          │    ├── pbp/season=YYYY-YYYY/game_id=<uuid>    │
          │    ├── shots/season=YYYY-YYYY/game_id=<uuid>  │
          │    └── boxscore/season=YYYY-YYYY/...          │
          └─────────┬────────────────────────────────────┘
                    │
          ┌─────────▼─────────────────────────────────────┐
          │  Cross-Validation & Quality Checks            │
          │  - PBP vs Boxscore consistency                │
          │  - Shots vs Boxscore FG counts                │
          │  - Coordinate validation                      │
          │  - Schema compliance                          │
          └─────────┬────────────────────────────────────┘
                    │
          ┌─────────▼─────────────────────────────────────┐
          │  Seasonal Coverage Reports                    │
          │  - % games with PBP                           │
          │  - % games with shots                         │
          │  - Data quality metrics                       │
          │  - Missing data identification                │
          └─────────┬────────────────────────────────────┘
                    │
          ┌─────────▼─────────────────────────────────────┐
          │  Normalized Prospects Tables                  │
          │  - LNB_PLAYER_GAME (unified schema)           │
          │  - LNB_TEAM_GAME                              │
          │  - LNB_SHOT_EVENTS                            │
          └───────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Game Index Builder ✅ PRIORITY 1

**File**: `tools/lnb/build_game_index.py`

**Purpose**: Create canonical table linking all data sources

**Input Sources**:
1. `fetch_lnb_schedule(season)` - Gets game list
2. `extract_fixture_uuids_from_schedule.py` - Gets current season UUIDs
3. Optional: LNB API match details for historical UUID mapping

**Output**: `data/raw/lnb/lnb_game_index.parquet`

**Schema**:
```python
{
    'season': str,              # "2024-2025"
    'competition': str,         # "Betclic ELITE", "Leaders Cup", etc.
    'game_id': str,            # Atrium UUID (primary key for fetchers)
    'lnb_match_id': str,       # LNB numeric ID (if available)
    'game_date': date,
    'home_team_id': str,
    'home_team_name': str,
    'away_team_id': str,
    'away_team_name': str,
    'status': str,             # "Final", "Scheduled", etc.
    'has_pbp': bool,           # Track what's been fetched
    'has_shots': bool,
    'has_boxscore': bool,
    'pbp_fetched_at': datetime,
    'shots_fetched_at': datetime,
    'last_updated': datetime
}
```

**Key Functions**:
```python
def build_game_index_for_season(season: str) -> pd.DataFrame:
    """Build game index for a single season"""

def discover_fixture_uuids(season: str) -> List[str]:
    """Get fixture UUIDs for a season (current season via scraping)"""

def merge_and_update_index(new_data: pd.DataFrame, index_path: Path) -> None:
    """Merge new data into existing index"""
```

**Efficiency**:
- Parquet format (fast reads)
- Incremental updates (don't rebuild from scratch)
- Boolean flags for what's fetched (avoid re-fetching)

---

### Step 2: Bulk Ingestion Pipeline ✅ PRIORITY 2

**File**: `tools/lnb/bulk_ingest_pbp_shots.py`

**Purpose**: Fetch PBP and shots for all games in index

**Input**: `data/raw/lnb/lnb_game_index.parquet`

**Output**: Partitioned parquet files
```
data/raw/lnb/
├── pbp/
│   ├── season=2024-2025/
│   │   ├── game_id=<uuid1>.parquet
│   │   └── game_id=<uuid2>.parquet
│   └── season=2023-2024/
│       └── ...
└── shots/
    ├── season=2024-2025/
    │   └── ...
    └── ...
```

**Key Features**:
1. **Checkpointing**: Track what's already fetched
2. **Error Logging**: Separate error CSV
3. **Rate Limiting**: Respect API limits
4. **Resume-able**: Skip already-fetched games

**Pseudo-code**:
```python
def bulk_ingest_pbp_and_shots(
    seasons: List[str],
    max_games_per_season: Optional[int] = None
) -> None:
    # Load game index
    index = load_game_index()

    # Filter to completed games only
    completed = index[index['status'] == 'Final']

    # Filter to requested seasons
    to_fetch = completed[completed['season'].isin(seasons)]

    # Skip already fetched (unless force_refresh)
    to_fetch = to_fetch[~to_fetch['has_pbp']]

    errors = []
    for game in to_fetch.itertuples():
        try:
            # Fetch PBP
            pbp_df = fetch_lnb_play_by_play(game.game_id)
            save_partitioned_parquet(pbp_df, 'pbp', game.season, game.game_id)

            # Fetch shots
            shots_df = fetch_lnb_shots(game.game_id)
            save_partitioned_parquet(shots_df, 'shots', game.season, game.game_id)

            # Update index flags
            update_index_flags(game.game_id, has_pbp=True, has_shots=True)

        except Exception as e:
            errors.append({
                'game_id': game.game_id,
                'error': str(e),
                'timestamp': datetime.now()
            })

    # Save error log
    save_error_log(errors)
```

**Efficiency**:
- Single-threaded initially (can parallelize later)
- Partitioned storage (fast filtering by season)
- Incremental (resume without re-fetching)

---

### Step 3: Cross-Validation ✅ PRIORITY 3

**File**: `tools/lnb/validate_data_consistency.py`

**Purpose**: Verify PBP/shots match boxscore stats

**Input**:
- PBP parquet files
- Shots parquet files
- Boxscore data (via `fetch_lnb_box_score()`)

**Output**: `data/reports/lnb_validation_report.parquet`

**Validation Checks**:
```python
@dataclass
class GameValidation:
    game_id: str
    season: str

    # Shot count validation
    shots_2pt_attempts: int      # From shots table
    shots_2pt_made: int
    shots_3pt_attempts: int
    shots_3pt_made: int

    pbp_2pt_attempts: int        # From PBP events
    pbp_2pt_made: int
    pbp_3pt_attempts: int
    pbp_3pt_made: int

    boxscore_fg_attempts: int    # From boxscore
    boxscore_fg_made: int
    boxscore_3pt_attempts: int
    boxscore_3pt_made: int

    # Deltas (absolute differences)
    delta_fg_attempts: int
    delta_fg_made: int
    delta_3pt_attempts: int
    delta_3pt_made: int

    # Flags
    has_discrepancy: bool        # Any delta > 1
    is_valid: bool               # All sources consistent

    # Coordinate validation
    shots_coords_valid: bool     # All coords in 0-100 range
    shots_has_nulls: bool
```

**Efficiency**:
- Batch validation (not during ingestion)
- Vectorized operations where possible
- Cache boxscore data (don't re-fetch)

---

### Step 4: Seasonal Coverage Reports ✅ PRIORITY 4

**File**: Enhance `tools/lnb/run_lnb_stress_tests.py`

**New Features**:
1. Auto-load games from index (not hard-coded list)
2. Group results by season and competition
3. Generate seasonal summary CSV/JSON

**Output**: `data/reports/lnb_coverage_SEASON.csv`

**Schema**:
```python
{
    'season': str,
    'competition': str,
    'total_games': int,
    'games_with_pbp': int,
    'games_with_shots': int,
    'games_with_both': int,
    'pbp_coverage_pct': float,
    'shots_coverage_pct': float,
    'avg_pbp_events': float,
    'avg_shots_per_game': float,
    'avg_fg_pct': float,
    'issues_count': int,
    'generated_at': datetime
}
```

**Key Changes**:
```python
# OLD (hard-coded)
TEST_GAME_UUIDS = ["uuid1", "uuid2", ...]

# NEW (dynamic from index)
def load_test_games_from_index(
    season: Optional[str] = None,
    max_per_season: int = 10
) -> List[str]:
    index = load_game_index()
    if season:
        index = index[index['season'] == season]
    return index.sample(n=max_per_season)['game_id'].tolist()
```

---

### Step 5: Normalized Prospects Tables ✅ PRIORITY 5

**File**: `tools/lnb/create_prospects_tables.py`

**Purpose**: Create unified schema compatible with forecasting pipeline

**Tables**:

#### 1. LNB_PLAYER_GAME
```python
{
    # Identifiers
    'LEAGUE': 'LNB_PROA',
    'SEASON': str,
    'GAME_ID': str,
    'PLAYER_ID': str,
    'TEAM_ID': str,

    # From Boxscore
    'MIN': float,
    'PTS': int,
    'REB': int,
    'AST': int,
    'STL': int,
    'BLK': int,
    'FGM': int,
    'FGA': int,
    'FG_PCT': float,
    '3PM': int,
    '3PA': int,
    '3P_PCT': float,
    'FTM': int,
    'FTA': int,
    'FT_PCT': float,

    # From PBP Aggregation
    'TOUCHES': int,           # Count of events where player involved
    'TURNOVERS': int,
    'FOULS_DRAWN': int,
    'FOULS_COMMITTED': int,

    # From Shots Aggregation
    'SHOTS_2PT_RIM': int,     # Layups, dunks near rim
    'SHOTS_2PT_MID': int,     # Mid-range jumpers
    'SHOTS_3PT_CORNER': int,  # Corner threes
    'SHOTS_3PT_ATB': int,     # Above the break threes

    # Contextual (from game)
    'PACE': float,
    'GAME_SCORE_DIFF': int,   # Team's final margin
}
```

#### 2. LNB_TEAM_GAME
Similar schema at team level

#### 3. LNB_SHOT_EVENTS
Unified shot table for all leagues
```python
{
    'LEAGUE': str,
    'SEASON': str,
    'GAME_ID': str,
    'SHOT_ID': str,           # event_id
    'PLAYER_ID': str,
    'TEAM_ID': str,
    'SHOT_TYPE': str,         # '2PT', '3PT'
    'SHOT_ZONE': str,         # 'rim', 'midrange', 'corner3', 'atb3'
    'X_COORD': float,         # Normalized 0-100
    'Y_COORD': float,
    'MADE': bool,
    'CLOCK': str,
    'PERIOD': int,
}
```

**Efficiency**:
- Built from saved parquet (not re-fetching)
- DuckDB for fast aggregations
- Compatible with existing NCAA/FIBA schemas

---

### Step 6: CI Monitoring & Future-Proofing ✅ PRIORITY 6

**Enhancement**: Update `tests/fetchers/test_lnb_smoke.py`

**New Tests**:
```python
@pytest.mark.lnb
@pytest.mark.ci
def test_lnb_api_endpoints_alive():
    """Test that Atrium API is still responding"""
    # Use known good UUID
    # Expect non-404 response

@pytest.mark.lnb
@pytest.mark.weekly
def test_lnb_schema_stability():
    """Test that PBP and shots schemas haven't changed"""
    # Fetch fresh data
    # Validate column names and types
    # Fail if schema breaks

@pytest.mark.lnb
def test_game_index_exists():
    """Test that game index is available and valid"""
    # Check file exists
    # Validate schema
    # Check for minimum game count
```

**Monitoring Script**: `tools/lnb/monitor_api_health.py`
- Run weekly via GitHub Actions
- Alert if:
  - API returns 404
  - Schema changes
  - No new games added in 30 days

---

## Data Flow Summary

```
1. Build Game Index
   ├─> fetch_lnb_schedule() for each season
   ├─> extract fixture UUIDs (current season)
   └─> Save to lnb_game_index.parquet

2. Bulk Ingest
   ├─> Read game index
   ├─> For each game:
   │   ├─> fetch_lnb_play_by_play()
   │   ├─> fetch_lnb_shots()
   │   └─> Save partitioned parquet
   └─> Update index flags

3. Cross-Validate
   ├─> Load PBP, shots, boxscore
   ├─> Compare FG counts
   ├─> Flag discrepancies
   └─> Save validation report

4. Coverage Reports
   ├─> Run stress tests by season
   ├─> Aggregate metrics
   └─> Save seasonal reports

5. Prospects Tables
   ├─> Load all raw data
   ├─> Aggregate and normalize
   └─> Save unified schemas

6. CI Tests
   ├─> Smoke tests (every commit)
   ├─> Schema tests (weekly)
   └─> Health monitoring (weekly)
```

---

## File Structure

```
nba_prospects_mcp/
├── data/
│   ├── raw/lnb/
│   │   ├── lnb_game_index.parquet         # Master index
│   │   ├── pbp/season=YYYY-YYYY/*.parquet
│   │   ├── shots/season=YYYY-YYYY/*.parquet
│   │   └── boxscore/season=YYYY-YYYY/*.parquet
│   └── reports/
│       ├── lnb_validation_report.parquet
│       └── lnb_coverage_*.csv
├── tools/lnb/
│   ├── build_game_index.py               # NEW - Step 1
│   ├── bulk_ingest_pbp_shots.py          # NEW - Step 2
│   ├── validate_data_consistency.py      # NEW - Step 3
│   ├── run_lnb_stress_tests.py           # ENHANCED - Step 4
│   ├── create_prospects_tables.py        # NEW - Step 5
│   └── monitor_api_health.py             # NEW - Step 6
└── tests/fetchers/
    └── test_lnb_smoke.py                 # ENHANCED - Step 6
```

---

## Next Actions (In Order)

1. ✅ Create `build_game_index.py` - Foundation for everything
2. ✅ Create `bulk_ingest_pbp_shots.py` - Core data pipeline
3. ✅ Create `validate_data_consistency.py` - Quality assurance
4. ✅ Enhance `run_lnb_stress_tests.py` - Automated reporting
5. ✅ Create `create_prospects_tables.py` - Unified schema
6. ✅ Enhance `test_lnb_smoke.py` - CI/CD integration
7. ✅ Update PROJECT_LOG.md - Documentation

---

## Success Criteria

✅ Game index covers 2015-present (schedule data)
✅ Current season (2024-25) has 100% PBP+shots coverage
✅ Cross-validation passes for 95%+ of games
✅ Seasonal coverage reports auto-generated
✅ Prospects tables follow unified schema
✅ CI tests catch API/schema changes
✅ All code documented and tested
