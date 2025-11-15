# LNB Data Pipeline - Onboarding Guide

**Last Updated**: 2025-11-15
**Maintainer**: nba_prospects_mcp team

---

## Overview

The LNB (Ligue Nationale de Basketball) data pipeline provides comprehensive coverage of French professional basketball data including:

- **Play-by-Play (PBP)**: Detailed event-by-event game data (~400-600 events per game)
- **Shot Charts**: Court coordinates for all shot attempts (~120-160 shots per game)
- **Match Details**: Game metadata, venue info, competition context
- **Schedule Data**: Full season calendars
- **Player/Team Stats**: Season aggregates

**Data Sources**:
- **Primary**: Atrium Sports API (third-party stats provider for LNB)
- **Secondary**: LNB Official API (`api-prod.lnb.fr`) - partially operational
- **Fallback**: Web scraping via Playwright

---

## Quick Start (15 Minutes)

### 1. Discover Current Season UUIDs (Automated)

```bash
# Automatically discover UUIDs for current season
uv run python tools/lnb/discover_historical_fixture_uuids.py \
    --seasons 2024-2025 \
    --interactive

# Or use automated click-through (if Playwright installed)
uv run python -c "
from tools.lnb.discover_historical_fixture_uuids import discover_uuids_automated
uuids = discover_uuids_automated('2024-2025', max_games=20)
print(f'Discovered {len(uuids)} UUIDs')
"
```

### 2. Discover Historical Season UUIDs (Manual)

```bash
# Step 1: Manually collect match-center URLs from https://www.lnb.fr/pro-a/calendrier
# Example URLs:
#   https://lnb.fr/fr/match-center/3fcea9a1-1f10-11ee-a687-db190750bdda
#   https://lnb.fr/fr/pre-match-center?mid=cc7e470e-11a0-11ed-8ef5-8d12cdc95909

# Step 2: Save URLs to file
cat > tools/lnb/2023-2024_urls.txt <<EOF
https://lnb.fr/fr/match-center/3fcea9a1-1f10-11ee-a687-db190750bdda
https://lnb.fr/fr/match-center/cc7e470e-11a0-11ed-8ef5-8d12cdc95909
EOF

# Step 3: Extract and validate UUIDs
uv run python tools/lnb/discover_historical_fixture_uuids.py \
    --seasons 2023-2024 \
    --from-file tools/lnb/2023-2024_urls.txt

uv run python tools/lnb/validate_discovered_uuids.py --season 2023-2024
```

### 3. Run Full Pipeline for Season

```bash
# Complete end-to-end pipeline
uv run python tools/lnb/build_game_index.py --seasons 2023-2024 --force-rebuild
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2023-2024
uv run python tools/lnb/create_normalized_tables.py --season 2023-2024
uv run python tools/lnb/validate_data_consistency.py --season 2023-2024
```

---

## Architecture

### Data Flow

```
┌─────────────────┐
│ LNB Website     │ → Manual URL Collection → fixture_uuids_by_season.json
│ (match-center)  │
└─────────────────┘

┌─────────────────┐
│ Atrium API      │ → PBP/Shots Data → Raw JSON → DuckDB (normalized tables)
│ (third-party)   │
└─────────────────┘

┌─────────────────┐
│ LNB API         │ → Match Details → Metadata → Coverage Reports
│ (api-prod.lnb.fr│
└─────────────────┘
```

### Directory Structure

```
tools/lnb/
├── discover_historical_fixture_uuids.py  # UUID discovery (manual + automated)
├── validate_discovered_uuids.py           # UUID validation against Atrium API
├── build_game_index.py                    # Build game index from UUIDs
├── bulk_ingest_pbp_shots.py               # Bulk PBP + shots ingestion
├── create_normalized_tables.py            # Transform to normalized schema
├── validate_data_consistency.py           # Data quality validation
├── smoke_test_endpoints.py                # Endpoint smoke tests
├── stress_test_coverage.py                # Coverage reporting + stress tests
├── fixture_uuids_by_season.json           # UUID mapping file
└── sample_responses/                      # Frozen JSON snapshots

src/cbb_data/fetchers/
├── lnb.py                                 # High-level fetchers
├── lnb_api.py                             # LNB API client
├── lnb_endpoints.py                       # Centralized endpoint config
├── lnb_parsers.py                         # JSON → DataFrame parsers
└── browser_scraper.py                     # Playwright automation

docs/
└── lnb_onboarding.md                      # This guide
```

---

## Common Workflows

### Workflow 1: Add New Historical Season

```bash
# 1. Collect 10-20 representative game URLs from LNB website
cat > tools/lnb/2022-2023_urls.txt <<EOF
https://lnb.fr/fr/match-center/{UUID1}
https://lnb.fr/fr/match-center/{UUID2}
# ... 8-18 more URLs
EOF

# 2. Extract and validate UUIDs
uv run python tools/lnb/discover_historical_fixture_uuids.py \
    --seasons 2022-2023 \
    --from-file tools/lnb/2022-2023_urls.txt

uv run python tools/lnb/validate_discovered_uuids.py \
    --season 2022-2023

# 3. Run full pipeline
uv run python tools/lnb/build_game_index.py --seasons 2022-2023 --force-rebuild
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2022-2023
uv run python tools/lnb/create_normalized_tables.py --season 2022-2023
uv run python tools/lnb/validate_data_consistency.py --season 2022-2023

# 4. Generate coverage report
uv run python tools/lnb/stress_test_coverage.py --report --season 2022-2023
```

### Workflow 2: Validate Endpoints

```bash
# Test all discovered endpoints with known UUIDs
uv run python tools/lnb/smoke_test_endpoints.py

# Test specific UUID
uv run python tools/lnb/smoke_test_endpoints.py \
    --uuid 3fcea9a1-1f10-11ee-a687-db190750bdda

# Save to custom directory
uv run python tools/lnb/smoke_test_endpoints.py \
    --output-dir tools/lnb/test_responses
```

### Workflow 3: Coverage Reporting

```bash
# Generate coverage report for all seasons
uv run python tools/lnb/stress_test_coverage.py --report

# Stress test with 20 concurrent requests
uv run python tools/lnb/stress_test_coverage.py --stress --concurrent 20

# Full suite (coverage + stress + memory)
uv run python tools/lnb/stress_test_coverage.py --full

# Test specific season only
uv run python tools/lnb/stress_test_coverage.py --report --season 2023-2024
```

---

## Troubleshooting

### Issue: UUID Validation Fails (404 Not Found)

**Possible Causes**:
1. UUID is for a future game → Atrium API only provides data for completed games
2. UUID is for a very old game → Atrium may have retention limits
3. UUID is incorrect → Double-check extraction

**Solution**:
```bash
# Re-validate specific UUID
uv run python -c "
from src.cbb_data.fetchers.lnb import fetch_lnb_play_by_play
df = fetch_lnb_play_by_play('{UUID}')
print(f'PBP events: {len(df)}')
"
```

### Issue: No PBP/Shots Data Available

**Possible Causes**:
1. Game hasn't been played yet
2. LNB match-center doesn't show "PLAY BY PLAY" tab
3. Atrium API endpoint changed

**Solution**:
```bash
# Check if game is completed and has PBP tab on LNB website
# Navigate to: https://lnb.fr/fr/match-center/{UUID}

# If game is complete but no data:
# 1. Report issue to maintainers
# 2. Check Atrium API status
# 3. Try web scraping fallback
```

### Issue: LNB API Endpoints Return 404

**Expected Behavior**: Some LNB API endpoints (`main_competitions`, `live_matches`) are currently down.

**Workaround**: Use Atrium Sports API for PBP/shots data, which is fully operational.

### Issue: Pipeline Script Fails

**Debug Steps**:
```bash
# 1. Check Python/uv environment
uv pip list | grep -E "pandas|requests|playwright"

# 2. Check fixture UUID file exists
cat tools/lnb/fixture_uuids_by_season.json | head -20

# 3. Run with verbose logging
PYTHONPATH=. python tools/lnb/{script_name}.py --help

# 4. Check error traceback for specific failure point
```

---

## Best Practices

### 1. Start Small (10-20 Games Per Season)

- Don't try to discover UUIDs for an entire season at once
- Start with 10-20 representative games spread throughout the season
- Validate before scaling up

### 2. Validate Immediately

Always validate UUIDs before running full pipeline:

```bash
uv run python tools/lnb/validate_discovered_uuids.py --season {SEASON}
```

### 3. Rate Limiting

- Atrium API: 500ms between requests (built into fetchers)
- LNB API: 1 req/sec (via rate_limiter)
- Web scraping: 1-2s between page loads

### 4. Check Data Availability

Not all historical games have PBP/shots data:
- ✅ Check: LNB match center shows "PLAY BY PLAY" tab
- ✅ Check: Atrium API returns data (not 404)
- ✅ Check: Validation script confirms availability

### 5. Document Sources

Keep notes on:
- Date ranges covered per season
- Teams included
- Any games skipped (and why)
- Data quality issues encountered

---

## Endpoint Reference

### Centralized Endpoints

All endpoints are defined in `src/cbb_data/fetchers/lnb_endpoints.py`:

```python
from src.cbb_data.fetchers.lnb_endpoints import LNB_API, ATRIUM_API, LNB_WEB

# LNB API
url = LNB_API.match_details(uuid="...")
url = LNB_API.EVENT_LIST

# Atrium API
url = ATRIUM_API.FIXTURE_DETAIL

# LNB Web
url = LNB_WEB.match_center(uuid="...")
url = LNB_WEB.CALENDAR
```

### Endpoint Status

| Endpoint | Status | Notes |
|----------|--------|-------|
| **Atrium PBP** | ✅ Confirmed | ~400-600 events per game |
| **Atrium Shots** | ✅ Confirmed | ~120-160 shots per game |
| **LNB Match Details** | ✅ Confirmed | Metadata, venue, competition info |
| **LNB Event List** | ✅ Confirmed | Event listings |
| **LNB Main Competitions** | ❌ Down (404) | Use manual season selection |
| **LNB Live Matches** | ❌ Down (404) | Use manual game discovery |
| **LNB Box Score** | ⚠️ Placeholder | Path unknown, needs DevTools discovery |

---

## Data Schemas

### Play-by-Play (PBP)

**Columns**: `GAME_ID`, `EVENT_ID`, `PERIOD_ID`, `CLOCK`, `EVENT_TYPE`, `EVENT_SUBTYPE`, `PLAYER_ID`, `PLAYER_NAME`, `PLAYER_JERSEY`, `TEAM_ID`, `DESCRIPTION`, `SUCCESS`, `X_COORD`, `Y_COORD`, `HOME_SCORE`, `AWAY_SCORE`, `LEAGUE`

**Example**:
```python
df = fetch_lnb_play_by_play("3fcea9a1-1f10-11ee-a687-db190750bdda")
# Returns ~474 events with detailed play-by-play data
```

### Shot Chart

**Columns**: `GAME_ID`, `EVENT_ID`, `PERIOD_ID`, `CLOCK`, `SHOT_TYPE`, `SHOT_SUBTYPE`, `PLAYER_ID`, `PLAYER_NAME`, `PLAYER_JERSEY`, `TEAM_ID`, `DESCRIPTION`, `SUCCESS`, `SUCCESS_STRING`, `X_COORD`, `Y_COORD`, `LEAGUE`

**Example**:
```python
df = fetch_lnb_shots("3fcea9a1-1f10-11ee-a687-db190750bdda")
# Returns ~122 shots with x/y coordinates (0-100 scale)
```

---

## Error Handling Guards

### Assertions in Fetchers

```python
# Example from lnb.py
def fetch_lnb_play_by_play(game_id: str) -> pd.DataFrame:
    # Guard: Validate UUID format
    if not validate_uuid_format(game_id):
        logger.error(f"Invalid UUID format: {game_id}")
        return pd.DataFrame(columns=[...])

    # Guard: Check for unexpected keys in response
    pbp_data = data.get('data', {}).get('pbp', {})
    if not pbp_data:
        logger.warning(f"No play-by-play data found for game {game_id}")
        return pd.DataFrame(columns=[...])

    # Guard: Handle missing fields gracefully
    for event in events:
        event_id = event.get('eventId', f'unknown_{i}')  # Fallback ID
        clock = event.get('clock', 'PT0M0S')  # Fallback clock
```

### Retry Logic

All fetchers include automatic retry with exponential backoff:
- Max retries: 3
- Backoff: 2 seconds (doubles each retry)
- Rate limiting: Built-in delays between requests

---

## Performance Expectations

### Typical Pipeline Timings (for 16 games)

| Step | Duration | Notes |
|------|----------|-------|
| UUID Discovery (manual) | ~5 min | Copy URLs from browser |
| UUID Validation | ~30 sec | 2s per UUID (API calls) |
| Game Index Build | ~20 sec | Playwright scraping |
| Bulk Ingestion (PBP+Shots) | ~80 sec | ~5s per game |
| Normalization | ~15 sec | ~1s per game |
| Validation | ~8 sec | ~0.5s per game |
| **Total** | **~3 min** | Excluding manual UUID collection |

### Memory Usage

- **Per Game**: ~2-5 MB (PBP + shots combined)
- **20 Games**: ~50-100 MB total memory increase
- **DuckDB Storage**: ~500 KB per game (compressed)

---

## Support & Maintenance

### Reporting Issues

1. Check existing issues: `docs/known_issues.md`
2. Capture error traceback and context
3. Include:
   - Season/UUID causing issue
   - Command run
   - Full error message
   - System info (OS, Python version)

### Contributing

1. Follow 10-step implementation process (see repository guidelines)
2. Update `PROJECT_LOG.md` with changes
3. Add tests for new functionality
4. Document in this guide

### Related Documentation

- **Endpoint Config**: `src/cbb_data/fetchers/lnb_endpoints.py`
- **Pipeline Scripts**: `tools/lnb/*.py`
- **Historical Discovery Guide**: `tools/lnb/HISTORICAL_UUID_DISCOVERY_GUIDE.md`
- **Project Log**: `PROJECT_LOG.md`

---

## Next Steps

1. ✅ **Quick Win**: Run coverage report for existing seasons
   ```bash
   uv run python tools/lnb/stress_test_coverage.py --report
   ```

2. 📋 **Expand Coverage**: Add 2022-2023 season (10-20 games)
   ```bash
   # Follow Workflow 1 above
   ```

3. 📋 **Stress Test**: Validate endpoint performance
   ```bash
   uv run python tools/lnb/stress_test_coverage.py --stress --concurrent 20
   ```

4. 📋 **Long-term**: Systematically add all available historical seasons
   ```bash
   # Test Atrium API retention (how far back does data go?)
   # Scale to all available seasons
   ```

---

**Questions?** Check `PROJECT_LOG.md` for recent changes or open an issue.
