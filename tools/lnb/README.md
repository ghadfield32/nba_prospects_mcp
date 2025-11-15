# LNB Pro A Data Export Tools

This directory contains tools for exporting LNB Pro A (France) basketball data to Parquet files for integration with the `cbb_data` package.

## Quick Start

```bash
# Create sample data for testing (recommended first step)
python tools/lnb/export_lnb.py --sample

# This creates:
# - data/lnb_raw/lnb_fixtures.parquet (8 games)
# - data/lnb_raw/lnb_pbp_events.parquet (~3,336 events)
# - data/lnb_raw/lnb_shots.parquet (~973 shots)
```

## Files

- **export_lnb.py**: Python script to export LNB data to Parquet files
- **README.md**: This file

## Data Structure

### Output Files (data/lnb_raw/)

| File | Description | Rows (Sample) | Coverage |
|------|-------------|---------------|----------|
| `lnb_fixtures.parquet` | Game schedule/results | 8 | Current season |
| `lnb_pbp_events.parquet` | Play-by-play events | ~3,336 | Event-level |
| `lnb_shots.parquet` | Shot chart data (x,y coords) | ~973 | Shot-level |
| `lnb_box_player.parquet` | Player box scores | TBD | Per-game |
| `lnb_box_team.parquet` | Team box scores | TBD | Per-game |

### Schema

#### lnb_fixtures.parquet
```python
{
    "game_id": int,           # Unique game identifier
    "season": str,            # "2025-26"
    "game_date": datetime,    # Game date/time
    "home_team": str,         # Home team name
    "away_team": str,         # Away team name
    "home_score": int,        # Final home score
    "away_score": int,        # Final away score
    "venue": str,             # Arena name
    "league": str,            # "LNB_PROA"
    "competition": str,       # "LNB Pro A"
}
```

#### lnb_pbp_events.parquet
```python
{
    "game_id": int,           # Links to fixtures
    "event_num": int,         # Event sequence number
    "period": int,            # Quarter (1-4)
    "clock": str,             # Game clock "MM:SS"
    "team": str,              # Team name
    "player": str,            # Player name
    "event_type": str,        # shot/rebound/assist/foul/turnover
    "description": str,       # Event description
    "home_score": int,        # Score after event
    "away_score": int,        # Score after event
    "league": str,            # "LNB_PROA"
    "competition": str,       # "LNB Pro A"
}
```

#### lnb_shots.parquet
```python
{
    "game_id": int,           # Links to fixtures
    "shot_num": int,          # Shot sequence number
    "period": int,            # Quarter (1-4)
    "clock": str,             # Game clock "MM:SS"
    "team": str,              # Team name
    "player": str,            # Player name
    "shot_type": str,         # "2PT" or "3PT"
    "made": int,              # 1=made, 0=missed
    "x": float,               # X coordinate
    "y": float,               # Y coordinate
    "distance": float,        # Shot distance (feet)
    "league": str,            # "LNB_PROA"
    "competition": str,       # "LNB Pro A"
}
```

## Usage

### Option 1: Sample Data (Testing)

```bash
# Create sample data
python tools/lnb/export_lnb.py --sample

# Verify files created
ls -lh data/lnb_raw/

# Test in Python
python -c "
from cbb_data import get_dataset
df = get_dataset('schedule', {'league': 'LNB_PROA', 'season': '2025-26'}, pre_only=False)
print(f'Loaded {len(df)} games')
"
```

### Option 2: Real Data Export (Future)

```bash
# Export current season
python tools/lnb/export_lnb.py --season 2025-26

# Export historical data
python tools/lnb/export_lnb.py --historical --start-season 2015 --end-season 2025

# Custom output directory
python tools/lnb/export_lnb.py --output data/lnb_custom/
```

### Option 3: Manual Data Import

If you have LNB data from other sources:

```python
import pandas as pd

# Load your data
fixtures_df = pd.read_csv("your_lnb_fixtures.csv")

# Ensure required columns exist
required_columns = ["game_id", "season", "game_date", "home_team", "away_team",
                   "home_score", "away_score", "league"]

# Convert and save
fixtures_df.to_parquet("data/lnb_raw/lnb_fixtures.parquet", index=False)
```

## Integration with cbb_data

Once Parquet files are created, use the unified API:

```python
from cbb_data import get_dataset

# Get schedule
schedule = get_dataset("schedule", {
    "league": "LNB_PROA",
    "season": "2025-26"
}, pre_only=False)

# Get play-by-play
pbp = get_dataset("pbp", {
    "league": "LNB_PROA",
    "game_ids": [1, 2, 3]
}, pre_only=False)

# Get shots
shots = get_dataset("shots", {
    "league": "LNB_PROA",
    "season": "2025-26"
}, pre_only=False)

# Get player season stats (aggregated from box scores)
players = get_dataset("player_season", {
    "league": "LNB_PROA",
    "season": "2025-26"
}, pre_only=False)
```

## Data Sources

Current sources for LNB data:

1. **Calendar API**: Schedule/fixtures data
2. **Game APIs**: Play-by-play and shot data
3. **Manual Collection**: Historical data compilation

Future sources (planned):

- API-Basketball (comprehensive coverage)
- LNB Official API (if available)
- Web scraping (stats.lnb.fr)

## Historical Coverage

### Current (Sample Data)
- **Season**: 2025-26
- **Games**: 8 fixtures
- **PBP Events**: ~3,336
- **Shots**: ~973

### Target (Full Historical)
- **Seasons**: 2015-2026 (11 seasons)
- **Games**: ~11,000 total (~1,000 per season)
- **PBP Events**: ~400,000 total
- **Shots**: ~120,000 total

## Troubleshooting

### Missing Data Files

If you see errors about missing Parquet files:

```
FileNotFoundError: LNB data file not found: data/lnb_raw/lnb_fixtures.parquet
```

**Solution**: Run the export script first:
```bash
python tools/lnb/export_lnb.py --sample
```

### Empty DataFrames

If fetchers return empty DataFrames, check:

1. Parquet files exist: `ls data/lnb_raw/`
2. Files contain data: `python -c "import pandas as pd; print(len(pd.read_parquet('data/lnb_raw/lnb_fixtures.parquet')))"`
3. Season filter matches: Ensure season format is "2025-26" not "2025"

### UTF-8 Encoding Issues

LNB uses French names with accents (é, à, ç). Ensure:

1. Python 3.8+ (UTF-8 default)
2. Parquet files saved with UTF-8 encoding
3. Terminal supports UTF-8

## Comparison with NBL

### Similarities
- Parquet-based data storage
- Python fetcher module (lnb_official.py)
- 7 fetch functions for all granularities
- DuckDB caching integration
- Unified get_dataset() API

### Differences
- NBL uses R (nblR package), LNB uses Python export script
- NBL has 45+ years of data, LNB has 11 years (2015+)
- NBL has official R package, LNB uses custom export

## See Also

- `src/cbb_data/fetchers/lnb_official.py`: Python fetcher module
- `tools/nbl/export_nbl.R`: Similar pattern for NBL (R version)
- `PROJECT_LOG.md`: Implementation history

## Contributing

To add new LNB data sources:

1. Update `export_lnb.py` with new fetch functions
2. Test export: `python tools/lnb/export_lnb.py --sample`
3. Verify schema compliance
4. Update this README
5. Submit PR with test data

## License

LNB data is factual sports statistics (public information).
Export tools are part of the cbb_data project (see root LICENSE).
