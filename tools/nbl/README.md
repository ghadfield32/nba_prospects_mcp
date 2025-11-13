# NBL Data Export Tools

R-based data export bridge for NBL Australia using the **nblR** CRAN package.

## Overview

This directory contains tools to extract official NBL statistics via the nblR package
and convert them to Parquet files for ingestion into the Python `cbb_data` pipeline.

**Why R?** The nblR package (GPL-3) provides the cleanest access to NBL's official stats backend,
with historical data back to 1979 and detailed stats (including shot locations) since 2015-16.

## Data Coverage

Via nblR package:
- **Match results**: All NBL games since **1979** (45+ years!)
- **Player box scores**: Since **2015-16 season** (PTS, REB, AST, FG%, 3P%, FT%, etc.)
- **Team box scores**: Since **2015-16 season**
- **Play-by-play**: Event-level data since **2015-16**
- **Shot locations**: **(x, y) coordinates** since **2015-16** ✨ (This is what SpatialJam charges for!)

## Setup

### Install R and Dependencies

```bash
# Install R (if not already installed)
# Ubuntu/Debian:
sudo apt-get install r-base

# macOS (via Homebrew):
brew install r

# Install required R packages
R -e 'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")'
```

### Verify Installation

```bash
# Test that nblR is installed
R -e 'library(nblR); print(packageVersion("nblR"))'
```

## Usage

### 1. Export NBL Data from R

```bash
# Export to default location (data/nbl_raw/)
Rscript tools/nbl/export_nbl.R

# Or specify custom output directory
NBL_EXPORT_DIR=/path/to/output Rscript tools/nbl/export_nbl.R
```

This creates 5 Parquet files:
- `nbl_results.parquet` - Match results (1979+)
- `nbl_box_player.parquet` - Player box scores (2015-16+)
- `nbl_box_team.parquet` - Team box scores (2015-16+)
- `nbl_pbp.parquet` - Play-by-play events (2015-16+)
- `nbl_shots.parquet` - Shot locations with (x,y) (2015-16+)

### 2. Ingest into Python/DuckDB

```bash
# From project root
python -c "from src.cbb_data.fetchers.nbl_official import ingest_nbl_into_duckdb; ingest_nbl_into_duckdb()"

# Or use the high-level API
python -c "from src.cbb_data.api.datasets import get_dataset; df = get_dataset('shots', filters={'league': 'NBL'})"
```

### 3. Use in Python Code

```python
from cbb_data.fetchers.nbl_official import load_nbl_table, run_nblr_export

# Option A: Load existing export
shots_df = load_nbl_table("nbl_shots")
print(f"Loaded {len(shots_df)} shots with x,y coordinates")

# Option B: Refresh data from R
run_nblr_export()  # Runs export_nbl.R
shots_df = load_nbl_table("nbl_shots")
```

## Data Schema

### nbl_results
- game_id, season, date, home_team, away_team, home_score, away_score

### nbl_box_player
- game_id, player_id, player_name, team, minutes, points, rebounds, assists, steals, blocks, fg%, 3p%, ft%

### nbl_box_team
- game_id, team, minutes, points, rebounds, assists, fg%, 3p%, ft%, offensive_rating, defensive_rating

### nbl_pbp
- game_id, event_num, period, clock, team, player, event_type, description, score_home, score_away

### nbl_shots ✨ (SpatialJam's "Shot Machine" equivalent)
- game_id, player_id, player_name, team, period, clock, x, y, shot_type, is_make, points_value

## License

**nblR package**: GPL-3 (CRAN)
- We **call** the package (legal under GPL-3)
- We do **not** copy or redistribute nblR's code
- Output data is from NBL's official stats (public information)

**This bridge code**: Same license as cbb_data project

## Troubleshooting

### "nblR package not found"
```bash
R -e 'install.packages("nblR", repos="https://cloud.r-project.org")'
```

### "arrow package not found"
```bash
R -e 'install.packages("arrow", repos="https://cloud.r-project.org")'
```

### "Permission denied" when running export_nbl.R
```bash
chmod +x tools/nbl/export_nbl.R
```

### Empty Parquet files
- Check internet connection (nblR fetches from NBL's API)
- Check nblR package is up to date: `R -e 'update.packages("nblR")'`
- Check NBL's API is accessible: Visit https://www.nbl.com.au/

## Performance

**Initial export** (full historical data):
- Results (1979+): ~2-3 minutes (~10k games)
- Player/team box (2015-16+): ~5-10 minutes (~150k player-games)
- Play-by-play (2015-16+): ~10-15 minutes (~2M events)
- Shots (2015-16+): ~10-15 minutes (~500k shots)

**Incremental updates** (new season):
- Just run export_nbl.R again (nblR handles incremental fetching)
- Only new data is downloaded

**Total storage**: ~500MB for full historical dataset (compressed Parquet)

## Comparison to SpatialJam

| Feature | SpatialJam+ ($20/mo) | This (Free) |
|---------|----------------------|-------------|
| Match results | ✅ 1979+ | ✅ 1979+ (via nblR) |
| Player/team box scores | ✅ 2015+ | ✅ 2015+ (via nblR) |
| Play-by-play | ✅ 2015+ | ✅ 2015+ (via nblR) |
| Shot charts (x,y) | ✅ 2015+ | ✅ 2015+ (via nblR) ✨ |
| BPM | ✅ | ⚠️ Compute yourself |
| Lineup combos | ✅ | ⚠️ Compute from PBP |
| Game flow | ✅ | ⚠️ Compute from PBP |

**Bottom line**: You get the **raw data** for free (same source SpatialJam uses),
but need to compute advanced metrics yourself.

## Next Steps

See `NBL_NZ_NBL_IMPLEMENTATION_SUMMARY.md` for:
- Python fetcher implementation (`nbl_official.py`)
- Validation tests
- Advanced metrics computation (BPM, lineups, game flow)
