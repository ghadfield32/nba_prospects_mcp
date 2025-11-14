# Golden Season Scripts

Per-league "golden season" scripts that pull complete datasets, run QA checks, and save to Parquet/CSV/DuckDB in a single command.

## Quick Start

### FIBA Leagues (BCL, BAL, ABA, LKL)

**Prerequisites:**
- Real game IDs collected (not placeholders)
- Game index CSV files validated

```bash
# Pull complete BCL 2023-24 season
python scripts/golden_fiba.py --league BCL --season 2023-24

# Pull BAL 2024 season
python scripts/golden_fiba.py --league BAL --season 2024

# Pull without QA checks (faster)
python scripts/golden_fiba.py --league ABA --season 2023-24 --no-qa

# Save as CSV instead of Parquet
python scripts/golden_fiba.py --league LKL --season 2023-24 --format csv
```

**What it does:**
1. Fetches schedule from game index
2. For each game:
   - Player stats (JSON → HTML fallback)
   - Team stats
   - Play-by-play events
   - Shot chart with X/Y coordinates
3. Aggregates to player_season/team_season
4. Runs QA checks:
   - No duplicate players/teams per game
   - Team totals = sum of player stats
   - PBP final score = boxscore
   - Shot coords within bounds
   - No nulls in key columns
5. Saves to `data/golden/{league}/{season}/`

**Expected output:**
```
data/golden/bcl/2023_24/
├── schedule.parquet         (25-50 games)
├── player_game.parquet      (200-400 player-games)
├── team_game.parquet        (50-100 team-games)
├── pbp.parquet             (10,000+ events)
├── shots.parquet           (1,000+ shots with X/Y)
├── player_season.parquet   (150-200 players)
├── team_season.parquet     (18-20 teams)
└── SUMMARY.txt             (QA results)
```

---

### ACB (Spanish League)

**Prerequisites:**
- None for season-level data
- For game-level: Check if accessible (not blocked by 403)

```bash
# Pull season-level data only (RECOMMENDED)
python scripts/golden_acb.py --season 2023-24

# Include game-level if available
python scripts/golden_acb.py --season 2023-24 --include-games

# Use Zenodo historical data
python scripts/golden_acb.py --season 2022 --use-zenodo
```

**What it does:**
1. Fetches player_season stats (HTML or Zenodo)
2. Fetches team_season stats
3. If `--include-games`:
   - Attempts to fetch schedule
   - Attempts to fetch player_game/team_game
4. Runs QA checks
5. Saves to `data/golden/acb/{season}/`

**Expected output (season-level only):**
```
data/golden/acb/2023_24/
├── player_season.parquet   (150-200 players) ← PRIMARY
├── team_season.parquet     (12 teams) ← PRIMARY
└── SUMMARY.txt
```

**Expected output (with --include-games):**
```
data/golden/acb/2023_24/
├── schedule.parquet         (if available)
├── player_game.parquet      (if available)
├── team_game.parquet        (if available)
├── player_season.parquet   ← PRIMARY
├── team_season.parquet     ← PRIMARY
└── SUMMARY.txt
```

**Known limitations:**
- PBP and shots NOT available
- Game-level data may fail (403 errors common)
- Best run from local machine, not container

---

### LNB Pro A (French League)

**Prerequisites:**
- API endpoints discovered via DevTools
- `lnb.py` fetchers updated with endpoints

```bash
# Pull season-level data
python scripts/golden_lnb.py --season 2023-24
```

**What it does:**
1. Fetches player_season stats (Stats Centre API)
2. Fetches team_season stats
3. Runs QA checks
4. Saves to `data/golden/lnb/{season}/`

**Expected output:**
```
data/golden/lnb/2023_24/
├── player_season.parquet   (150-200 players) ← PRIMARY
├── team_season.parquet     (18 teams) ← PRIMARY
└── SUMMARY.txt
```

**Known limitations:**
- Game-level, PBP, shots NOT implemented
- Focus: Season-level scouting data only

**If data is empty:**
API discovery required. Follow steps in SUMMARY.txt.

---

## Script Architecture

### Base Class

**`base_golden_season.py`**: Abstract base class with common workflow

```
┌─────────────────────────────────────┐
│ GoldenSeasonScript (Base)           │
├─────────────────────────────────────┤
│ + fetch_schedule() [abstract]        │
│ + fetch_player_game() [abstract]     │
│ + fetch_team_game() [abstract]       │
│ + fetch_pbp() [optional]             │
│ + fetch_shots() [optional]           │
│ + fetch_player_season() [optional]   │
│ + fetch_team_season() [optional]     │
│                                      │
│ + fetch_all_data()                   │
│ + run_qa_checks()                    │
│ + save_all_data()                    │
│ + generate_summary_report()          │
│ + run()                              │
└─────────────────────────────────────┘
```

### League Scripts

Each league extends the base class:

- **`golden_fiba.py`**: FIBA cluster (BCL/BAL/ABA/LKL)
- **`golden_acb.py`**: ACB (Spanish League)
- **`golden_lnb.py`**: LNB Pro A (French League)

### Shared Utilities

**`src/cbb_data/utils/data_qa.py`**: QA check functions

```python
from src.cbb_data.utils.data_qa import (
    check_no_duplicates,
    check_required_columns,
    check_team_totals_match_player_sums,
    check_shot_coordinates,
    run_schedule_qa,
    run_player_game_qa,
    run_team_game_qa,
    run_cross_granularity_qa
)
```

---

## Data Quality Standards

All scripts implement these QA checks:

### Schedule
- ✅ No duplicate GAME_IDs
- ✅ All required columns present
- ✅ No nulls in GAME_ID, GAME_DATE
- ✅ LEAGUE and SEASON values correct
- ✅ Row count >= minimum threshold

### Player Game
- ✅ No duplicates on (GAME_ID, TEAM_ID, PLAYER_ID)
- ✅ All required columns present
- ✅ No nulls in key columns
- ✅ PTS in range [0, 100]
- ✅ MIN in range [0, 60]

### Team Game
- ✅ No duplicates on (GAME_ID, TEAM_ID)
- ✅ Exactly 2 teams per game
- ✅ PTS in range [0, 200]

### Cross-Granularity
- ✅ Team totals = sum of player stats (tolerance ±1)
- ✅ All games in player_game exist in schedule
- ✅ PBP final score = boxscore (sample of 10 games)

### Shots (FIBA only)
- ✅ X/Y coordinates within court bounds
- ✅ Shot type breakdown present

---

## Common Usage Patterns

### Run for Multiple Seasons

```bash
# FIBA backfill
for season in 2023-24 2022-23 2021-22; do
    python scripts/golden_fiba.py --league BCL --season $season
done
```

### Parallel Execution

```bash
# Run all FIBA leagues in parallel
python scripts/golden_fiba.py --league BCL --season 2023-24 &
python scripts/golden_fiba.py --league BAL --season 2024 &
python scripts/golden_fiba.py --league ABA --season 2023-24 &
python scripts/golden_fiba.py --league LKL --season 2023-24 &
wait
```

### CI/CD Integration

```bash
# Run all leagues, fail if any unhealthy
python scripts/golden_fiba.py --league BCL --season 2023-24 || exit 1
python scripts/golden_fiba.py --league BAL --season 2024 || exit 1
python scripts/golden_acb.py --season 2023-24 || exit 1
python scripts/golden_lnb.py --season 2023-24 || exit 1
```

### Custom Output Location

```bash
# Save to custom directory
python scripts/golden_fiba.py --league BCL --season 2023-24 \
    --output-dir /mnt/basketball_data/golden
```

---

## Troubleshooting

### FIBA: "Only 3 games in schedule"

**Problem:** Game index has placeholder data

**Solution:**
```bash
# Collect real game IDs
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive

# Validate
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids

# Re-run script
python scripts/golden_fiba.py --league BCL --season 2023-24
```

### FIBA: "SOURCE shows all fiba_html, no fiba_json"

**Possible causes:**
- FIBA LiveStats JSON API down/changed
- Rate limiting kicked in
- Network issues

**Check:**
```bash
# Test JSON client directly
python -c "
from src.cbb_data.fetchers.fiba_livestats_json import FibaLiveStatsClient
client = FibaLiveStatsClient()
df = client.fetch_player_game('BCL', 123456)  # Use real game ID
print(df.head())
"
```

### ACB: "Player season empty (403)"

**Problem:** ACB blocks container/cloud IPs

**Solutions:**
1. Run from local machine (not container)
2. Use Zenodo historical data:
   ```bash
   python tools/acb/setup_zenodo_data.py --download
   python scripts/golden_acb.py --season 2022 --use-zenodo
   ```
3. Use manual CSV files (see tools/acb/README.md)

### LNB: "Player season empty"

**Problem:** API endpoints not discovered yet

**Solution:**
```bash
# Run API discovery
python tools/lnb/api_discovery_helper.py --discover

# Follow instructions to:
# 1. Open lnb.fr in browser
# 2. Use DevTools to find JSON endpoints
# 3. Document in tools/lnb/discovered_endpoints.json
# 4. Update src/cbb_data/fetchers/lnb.py
# 5. Re-run script
```

### QA Checks Failing

**Check SUMMARY.txt in output directory:**
```bash
cat data/golden/bcl/2023_24/SUMMARY.txt
```

**Common issues:**
- Duplicate player records → Check game index for duplicate game IDs
- Team totals mismatch → May indicate data quality issue from source
- PBP score mismatch → Sample a few games, may be expected for DNP games

---

## Integration with Storage

Scripts use `src.cbb_data.storage` utilities:

```python
from src.cbb_data.storage import save_to_disk, get_storage

# Saves with metadata
save_to_disk(
    df,
    "data/golden/bcl/2023_24/player_game.parquet",
    format="parquet",
    league="BCL",
    season="2023-24",
    data_type="player_game"
)
```

**DuckDB integration:**
```bash
# Save to DuckDB instead
python scripts/golden_fiba.py --league BCL --season 2023-24 --format duckdb
```

---

## Next Steps After Running Scripts

1. **Verify data quality**
   - Check SUMMARY.txt for all leagues
   - All QA checks passing?
   - Row counts reasonable?

2. **Load and explore**
   ```python
   import pandas as pd

   # Load BCL player game data
   df = pd.read_parquet("data/golden/bcl/2023_24/player_game.parquet")

   # Top scorers
   print(df.groupby('PLAYER_NAME')['PTS'].sum().nlargest(10))
   ```

3. **Build analytics**
   - Shot charts (FIBA leagues have X/Y coords)
   - Player efficiency ratings
   - Team four factors
   - Historical trends (if multi-season)

4. **Backfill historical seasons**
   - Once current season works, repeat for older seasons
   - Build time-series datasets

5. **Automate refreshes**
   - Add scripts to cron/scheduler
   - Run weekly during season
   - Monitor for data quality regressions

---

## Performance Notes

**Typical runtimes** (with real data):

- **FIBA (30 games):** 3-5 minutes
  - Schedule: instant (from CSV)
  - Player/team game: 2-3 mins (rate limited)
  - PBP: 1-2 mins
  - Shots: 1 min
  - QA: 10-20 seconds

- **ACB (season-level):** 30-60 seconds
  - Player/team season: 20-40 seconds (HTML parsing)
  - QA: 5-10 seconds

- **LNB (season-level):** 20-40 seconds
  - Player/team season: 15-30 seconds (API call)
  - QA: 5-10 seconds

**Optimization tips:**
- Use `--no-qa` to skip QA checks (development only)
- Run leagues in parallel
- Use Parquet (faster than CSV)

---

## Support

**Issues?**
1. Check league-specific README:
   - `tools/fiba/README.md`
   - `tools/acb/README.md`
   - `tools/lnb/README.md`

2. Review validation guides:
   - `docs/TESTING_VALIDATION_GUIDE.md`
   - `docs/DATA_SOURCE_INTEGRATION_PLAN.md`

3. Check PROJECT_LOG.md for known issues

Last Updated: 2025-11-14
