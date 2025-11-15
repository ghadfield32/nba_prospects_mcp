# LNB Pro A Integration Plan

## Overview
Implement comprehensive LNB Pro A (France) data integration following the NBL pattern.
Use existing LNB data (8 games, 3,336 PBP events, 973 shots) and create automated fetchers.

## Architecture

### Data Flow
```
LNB Data Source (Calendar API/External)
    ↓
Export Script (Python/manual)
    ↓
Parquet Files (data/lnb_raw/*.parquet)
    ↓
lnb_official.py (loads & normalizes)
    ↓
Unified get_dataset() API
```

### Files to Create/Modify

#### New Files
1. `tools/lnb/export_lnb.py` - Python export script for LNB data
2. `tools/lnb/README.md` - Setup and usage guide
3. `src/cbb_data/fetchers/lnb_official.py` - Main fetcher module
4. `data/lnb_raw/` - Data directory (gitignored)

#### Modified Files
1. `src/cbb_data/catalog/sources.py` - Register LNB endpoints
2. `src/cbb_data/catalog/capabilities.py` - Update LNB capabilities
3. `src/cbb_data/fetchers/__init__.py` - Export lnb_official
4. `PROJECT_LOG.md` - Document integration

## Data Structure

### Parquet Files (data/lnb_raw/)
```
lnb_fixtures.parquet      # Schedule data (8 rows current season)
lnb_pbp_events.parquet    # Play-by-play events (3,336 rows)
lnb_shots.parquet         # Shot chart data (973 rows)
lnb_box_player.parquet    # Player box scores (derived from games)
lnb_box_team.parquet      # Team box scores (derived from games)
```

### Schema Mapping

#### fixtures → schedule
```
game_id → GAME_ID
season → SEASON
game_date → GAME_DATE
home_team → HOME_TEAM
away_team → AWAY_TEAM
home_score → HOME_SCORE
away_score → AWAY_SCORE
venue → VENUE
league → LEAGUE ("LNB_PROA")
```

#### pbp_events → pbp
```
game_id → GAME_ID
event_num → EVENT_NUM
period → PERIOD
clock → CLOCK
team → TEAM
player → PLAYER_NAME
event_type → EVENT_TYPE
description → DESCRIPTION
home_score → HOME_SCORE
away_score → AWAY_SCORE
```

#### shots → shots
```
game_id → GAME_ID
shot_num → SHOT_NUM
period → PERIOD
clock → CLOCK
team → TEAM
player → PLAYER_NAME
shot_type → SHOT_TYPE (2PT/3PT)
made → SHOT_MADE (0/1)
x → SHOT_X
y → SHOT_Y
distance → DISTANCE
```

## Implementation Steps

### Phase 1: Data Export Infrastructure
1. Create tools/lnb/ directory
2. Create export_lnb.py script
3. Create README.md with setup instructions
4. Test export script with sample data

### Phase 2: Python Fetcher Module
1. Create lnb_official.py with load_lnb_table()
2. Implement fetch_lnb_schedule()
3. Implement fetch_lnb_player_season() (aggregate from box_player)
4. Implement fetch_lnb_team_season() (aggregate from box_team)
5. Implement fetch_lnb_player_game()
6. Implement fetch_lnb_team_game()
7. Implement fetch_lnb_pbp()
8. Implement fetch_lnb_shots()

### Phase 3: Catalog Integration
1. Update catalog/sources.py - register all 7 endpoints
2. Update catalog/capabilities.py - set capability levels
3. Update fetchers/__init__.py - export lnb_official

### Phase 4: Testing & Validation
1. Test each fetch function individually
2. Test via get_dataset() API
3. Validate schema compliance
4. Test filters (season, team, player, game_id)

### Phase 5: Documentation
1. Update PROJECT_LOG.md
2. Create tools/lnb/QUICKSTART.md
3. Update LEAGUE_CAPABILITIES_SUMMARY.md (if exists)

## Success Criteria

✅ All 7 fetch functions working
✅ Seamless integration with get_dataset() API
✅ Filters work correctly (season, team, player, date)
✅ Schema matches other leagues
✅ DuckDB caching functional
✅ Documentation complete
✅ PROJECT_LOG updated

## Historical Coverage Plan

Current: 2025-2026 season (8 games)
Future: Extend to 2015-2026 (11 seasons, ~11,000 games)

Data needed:
- fixtures.parquet: All games
- pbp_events.parquet: All PBP events (~400K total)
- shots.parquet: All shots (~120K total)
- box_player/team.parquet: Aggregated stats

## Notes

- Follow NBL pattern exactly for consistency
- Use Parquet for efficient columnar storage
- DuckDB caching for 1000x speedup
- Graceful degradation if data files missing
- UTF-8 encoding for French names (é, à, ç)
- Season format: "2024-25" or "2024"
