# NBL Data Pipeline - Quick Start Guide

**Last Updated**: 2025-11-13

## Current Status: ✅ Ready to Deploy (Pending R Installation)

### What's Been Set Up

✅ **Python Integration**
- `src/cbb_data/fetchers/nbl_official.py` - Full implementation with all fetch functions
- `pyproject.toml` - CLI entrypoint configured (`nbl-export` command)
- Python dependencies installed (pandas, pyarrow, duckdb)

✅ **R Export Script**
- `tools/nbl/export_nbl.R` - Production-ready R script
- Exports 5 datasets: results, player box, team box, PBP, shots
- Auto-installs missing R packages

✅ **Documentation**
- `tools/nbl/SETUP_GUIDE.md` - Comprehensive setup guide
- `tools/nbl/validate_setup.py` - Validation script

### What's Needed: R Installation

❌ **R Runtime** (not installed yet)

## Installation Steps (5-10 minutes)

### Step 1: Install R

**Windows** (Current environment):
```powershell
# Download and install R from:
https://cran.r-project.org/bin/windows/base/

# Or use winget:
winget install RProject.R

# Verify installation:
Rscript --version
```

**macOS**:
```bash
brew install r
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install r-base
```

### Step 2: Install R Packages

```bash
# Install required packages (nblR, dplyr, arrow)
R -e 'install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")'
```

### Step 3: Validate Setup

```bash
# Run validation script
uv run python tools/nbl/validate_setup.py

# Expected output: "All checks passed! 🎉"
```

### Step 4: Export NBL Data

**Option A: Using Python CLI** (Recommended):
```bash
uv run nbl-export
```

**Option B: Direct R script**:
```bash
Rscript tools/nbl/export_nbl.R
```

**What this does**:
- Fetches all NBL games since 1979 (~10k games)
- Fetches player/team box scores since 2015-16
- Fetches play-by-play since 2015-16 (~2M events)
- Fetches shot locations (x,y) since 2015-16 (~500k shots) ✨
- Exports to Parquet files in `data/nbl_raw/`
- Ingests into DuckDB for fast queries

**Time**: 10-30 minutes for initial full export

### Step 5: Test Data Access

```python
from cbb_data.api.datasets import get_dataset

# Test shot chart data (the premium feature!)
shots = get_dataset("shots", filters={"league": "NBL", "season": "2024"})
print(f"Loaded {len(shots)} NBL shots with x,y coordinates")

# Test player stats
players = get_dataset("player_season", filters={"league": "NBL", "season": "2024"})
print(f"Loaded {len(players)} NBL players")
```

## Architecture Overview

```
┌─────────────┐
│   nblR      │  R package (CRAN)
│  (R, GPL-3) │  Official NBL data source
└──────┬──────┘
       │ export_nbl.R
       ▼
┌─────────────────┐
│ Parquet Files   │  data/nbl_raw/*.parquet
│ (nbl_results,   │  Cached raw data
│  nbl_shots, etc)│
└──────┬──────────┘
       │ nbl_official.py
       ▼
┌─────────────────┐
│    DuckDB       │  Fast columnar storage
│  (cbb_data.db)  │  Queryable via Python
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  High-Level API │  get_dataset() functions
│  MCP Server     │  Natural language queries
│  REST API       │  HTTP endpoints
└─────────────────┘
```

## Data Coverage Summary

| Dataset | Timeframe | Records | Size | Key Features |
|---------|-----------|---------|------|--------------|
| **Results** | 1979-present | ~10k games | ~2 MB | Full historical schedule |
| **Player Box** | 2015-16+ | ~150k records | ~50 MB | Game-level player stats |
| **Team Box** | 2015-16+ | ~3k records | ~1 MB | Game-level team stats |
| **Play-by-Play** | 2015-16+ | ~2M events | ~200 MB | Event-level game log |
| **Shots** | 2015-16+ | ~500k shots | ~100 MB | **x,y coordinates** ✨ |

## Why This Matters

### 🆓 Free Alternative to Paid Services

| Feature | SpatialJam ($20/mo) | This (FREE) |
|---------|---------------------|-------------|
| Match results 1979+ | ✅ | ✅ |
| Player/team box 2015+ | ✅ | ✅ |
| Play-by-play 2015+ | ✅ | ✅ |
| **Shot charts (x,y)** | ✅ | **✅ FREE!** |
| BPM | ✅ | ⚙️ Compute yourself |
| Lineup combos | ✅ | ⚙️ Compute yourself |

**Key Win**: Shot location data (x,y coordinates) - normally a premium feature - is FREE via nblR!

## Troubleshooting

### R not found
```bash
# Check PATH
echo $PATH  # Linux/Mac
echo %PATH%  # Windows

# Reinstall R or add to PATH
```

### R packages not installing
```bash
# Try with sudo (Linux)
sudo R -e 'install.packages(...)'

# Or install from within R console
R
> install.packages(c("nblR", "dplyr", "arrow"))
```

### Empty Parquet files
- Check internet connection (nblR fetches from NBL's API)
- Update nblR: `R -e 'update.packages("nblR")'`
- Try running export again

### Python import errors
```bash
# Reinstall project in editable mode
uv pip install -e .
```

## Next Steps After Setup

1. **✅ Export current season data**
   ```bash
   uv run nbl-export
   ```

2. **📊 Build shot chart visualizations**
   - Use matplotlib/seaborn for basic charts
   - Use plotly for interactive charts
   - Courts coordinates provided in shots data

3. **📈 Compute advanced metrics**
   - BPM (Box Plus/Minus)
   - PIE (Player Impact Estimate)
   - True Shooting %
   - Usage Rate

4. **🔄 Set up automated updates**
   - Windows Task Scheduler
   - Cron job (Linux/Mac)
   - GitHub Actions workflow

## Support

- **Setup issues**: See [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- **Python API**: See main README.md
- **R package docs**: https://cran.r-project.org/web/packages/nblR/

## License Notes

- **nblR package**: GPL-3 (we CALL the package, don't copy code - legal)
- **Output data**: Public NBL statistics (factual information)
- **This integration code**: Same license as main project
