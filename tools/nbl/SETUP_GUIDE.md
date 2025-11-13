# NBL/NZ-NBL Data Pipeline Setup Guide

Complete guide for setting up and running the NBL/NZ-NBL free data pipeline.

## Quick Start (5 minutes)

```bash
# 1. Install R (if not already installed)
# Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y r-base

# macOS (via Homebrew):
brew install r

# 2. Install R packages (one-time setup)
R -e 'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")'

# 3. Verify installation
R -e 'library(nblR); packageVersion("nblR")'

# 4. Run NBL data export (takes 10-30 minutes for full historical data)
Rscript tools/nbl/export_nbl.R

# 5. Ingest into DuckDB (from Python)
python -c "from cbb_data.fetchers.nbl_official import ingest_nbl_into_duckdb; ingest_nbl_into_duckdb()"

# 6. Test the data
python -c "from cbb_data.api.datasets import get_dataset; print(get_dataset('shots', filters={'league': 'NBL', 'season': '2023'}).head())"
```

## Detailed Setup

### Step 1: R Installation

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y r-base
```

**macOS:**
```bash
brew install r
```

**Windows:**
Download installer from https://cran.r-project.org/bin/windows/base/

**Docker/Devcontainer:**
Add to your Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y r-base
RUN R -e 'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")'
```

### Step 2: Install R Dependencies

Run this once after R is installed:

```bash
R -e 'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")'
```

**Verify installation:**
```bash
R -e 'library(nblR); library(arrow); library(dplyr)'
```

### Step 3: Export NBL Data from R

```bash
# From repository root
Rscript tools/nbl/export_nbl.R
```

**What this does:**
- Fetches ALL NBL games since 1979 (~10k games)
- Fetches player/team box scores since 2015-16 (~150k records)
- Fetches play-by-play since 2015-16 (~2M events)
- Fetches shot locations (x,y) since 2015-16 (~500k shots) ✨
- Exports to Parquet files in `data/nbl_raw/`

**Expected output:**
```
NBL Export Tool
===============
Output directory: data/nbl_raw

[1/5] Fetching match results since 1979...
[nbl_results] Exporting match results... OK (10234 rows, 12 cols)

[2/5] Fetching player box scores (2015-16+)...
[nbl_box_player] Exporting player box scores... OK (152847 rows, 28 cols)

[3/5] Fetching team box scores (2015-16+)...
[nbl_box_team] Exporting team box scores... OK (3284 rows, 24 cols)

[4/5] Fetching play-by-play data (2015-16+)...
[nbl_pbp] Exporting play-by-play events... OK (2145623 rows, 18 cols)

[5/5] Fetching shot location data (2015-16+)...
[nbl_shots] Exporting shot locations (x,y)... OK (523847 rows, 16 cols)

===============
Export complete!
```

**Time estimate:**
- Initial full export: 10-30 minutes
- Subsequent updates: 2-5 minutes (only new data)

### Step 4: Ingest into Python/DuckDB

```python
from cbb_data.fetchers.nbl_official import ingest_nbl_into_duckdb

# Ingest all NBL data into DuckDB
ingest_nbl_into_duckdb()
```

**What this does:**
- Loads all 5 Parquet files
- Normalizes column names to standard schema
- Saves to DuckDB for fast querying
- Enables access via high-level API

### Step 5: Verify Data Access

Test each dataset type:

```python
from cbb_data.api.datasets import get_dataset

# 1. Schedule (1979+)
games = get_dataset("games", filters={"league": "NBL", "season": "2023"})
print(f"NBL 2023 games: {len(games)}")

# 2. Player season stats
players = get_dataset("player_season", filters={"league": "NBL", "season": "2023"})
print(f"NBL 2023 players: {len(players)}")
print(players[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]].head())

# 3. Shot charts (x,y coordinates) - SpatialJam's $20/mo feature!
shots = get_dataset("shots", filters={"league": "NBL", "season": "2023"})
print(f"NBL 2023 shots: {len(shots)}")
print(shots[["PLAYER_NAME", "LOC_X", "LOC_Y", "IS_MAKE"]].head())

# 4. Play-by-play
pbp = get_dataset("pbp", filters={"league": "NBL", "season": "2023"})
print(f"NBL 2023 pbp events: {len(pbp)}")
```

### Step 6: Run Health Tests

```bash
# Run NBL-specific tests
pytest tests/test_nbl_official_consistency.py -v

# Run all tests
pytest tests/ -v
```

## NZ-NBL Setup (Optional)

NZ-NBL uses FIBA LiveStats HTML scraping. The infrastructure is in place but requires:

1. **Game ID collection** - Manual/scripted collection of FIBA game IDs from nznbl.basketball
2. **HTML parsing implementation** - Complete the TODO sections in `nz_nbl_fiba.py`

Current status: Scaffold complete, HTML parsing TODOs remain.

## Troubleshooting

### "R not found"
```bash
# Verify R is in PATH
which R
R --version

# If not found, reinstall R or add to PATH
```

### "nblR package not found"
```bash
# Reinstall R packages
R -e 'install.packages("nblR", repos="https://cloud.r-project.org")'
```

### "arrow package not found"
```bash
# Install arrow for Parquet support
R -e 'install.packages("arrow", repos="https://cloud.r-project.org")'
```

### "Empty Parquet files"
- Check internet connection (nblR fetches from NBL's API)
- Check nblR is up to date: `R -e 'update.packages("nblR")'`
- Try running export script again

### "403 Forbidden errors"
- NBL's API may be temporarily down
- Wait a few minutes and try again
- Check https://www.nbl.com.au/ is accessible

## Data Update Schedule

**Recommended:**
- Run `export_nbl.R` weekly during NBL season (Oct-Mar)
- Run after each playoff round
- nblR automatically handles incremental updates

**Automation options:**
- Cron job (Linux/Mac)
- Task Scheduler (Windows)
- Airflow DAG
- GitHub Actions

Example cron (weekly on Sunday 3am):
```cron
0 3 * * 0 cd /path/to/repo && Rscript tools/nbl/export_nbl.R
```

## Storage Requirements

**Disk space:**
- NBL raw Parquet files: ~500 MB (full historical dataset)
- DuckDB storage: ~400 MB (compressed)
- Total: ~1 GB

## Performance

**Query speed (DuckDB):**
- Schedule query: <10ms
- Player season stats: <50ms
- Shot chart (full season): <200ms
- Play-by-play (full season): <500ms

**Export time (nblR):**
- Results (1979+): 2-3 minutes (~10k games)
- Player box (2015-16+): 5-10 minutes (~150k records)
- Team box (2015-16+): 2-3 minutes (~3k records)
- Play-by-play (2015-16+): 10-15 minutes (~2M events)
- Shots (2015-16+): 10-15 minutes (~500k shots)
- **Total: 20-40 minutes** for initial full export

## Next Steps

1. ✅ Set up R and nblR
2. ✅ Run initial data export
3. ✅ Ingest into DuckDB
4. ✅ Verify data access
5. 🔨 Build shot chart visualizations
6. 🔨 Compute advanced metrics (BPM, PIE, etc.)
7. 🔨 Add lineup analysis
8. 🔨 Implement NZ-NBL HTML parsing

## Support

- NBL data issues: Check nblR documentation or NBL official site
- Code issues: See main README.md or open GitHub issue
- FIBA LiveStats: See `src/cbb_data/fetchers/fiba_livestats.py` documentation

## License Notes

**nblR package:** GPL-3 (CRAN)
- We CALL the package (legal under GPL-3)
- We do NOT copy or redistribute nblR's code
- Output data is from NBL's official stats (public information)

**This integration code:** Same license as cbb_data project
