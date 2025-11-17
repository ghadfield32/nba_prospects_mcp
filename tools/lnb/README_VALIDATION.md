# LNB Data Validation & Quality Assurance

Production-grade validation framework for LNB play-by-play and shots datasets.

## Quick Start

### Run Full Validation

```bash
uv run python tools/lnb/validate_and_monitor_coverage.py
```

Performs 9-step validation:
1. Load game index
2. Validate data on disk
3. Validate index accuracy
4. Per-game consistency checks
5. Season readiness assessment
6. Future vs played games analysis
7. Golden fixtures regression testing
8. API spot-check (random sampling)
9. Live data readiness check

### Gate Modeling on Readiness

```python
from tools.lnb.validate_and_monitor_coverage import require_season_ready

# In your Bayesian trainer or MCP tool:
require_season_ready("2023-2024")  # Raises ValueError if not ready
```

### Preflight Check

```bash
# Before any modeling or live ingestion
uv run python tools/lnb/validate_and_monitor_coverage.py && echo "✅ LNB data ready"
```

## Features

### 1. Golden Fixtures Regression Testing
- **Purpose**: Detect silent API changes, schema drift, data corruption
- **Location**: `tools/lnb/golden_fixtures.json`
- **What it checks**:
  - Row counts (PBP, shots)
  - Final scores
  - Number of periods
  - Event type distributions

### 2. API Spot-Check
- **Purpose**: Catch upstream changes and data drift
- **Method**: Randomly samples 5 games from READY seasons
- **Compares**: Disk data vs live API responses
- **Metrics**: Row counts, final scores

### 3. Time-Series Metrics
- **Purpose**: Monitor coverage and quality over time
- **Location**: `data/raw/lnb/lnb_metrics_daily.parquet`
- **Tracks**: Coverage %, errors, warnings, readiness per season

### 4. Provenance Metadata
Every ingested parquet file includes:
- `_source_system`: "LNB"
- `_source_endpoint`: "pbp" or "shots"
- `_fetched_at`: ISO timestamp
- `_ingestion_version`: Git SHA or "dev"

### 5. Season Readiness Gate
Criteria for "READY for modeling":
- ≥95% coverage for both PBP and shots
- Zero critical errors
- Passes per-game consistency checks

## Validation Checks

### PBP Validation
- ✅ Required columns: HOME_SCORE, AWAY_SCORE, PERIOD_ID, EVENT_TYPE
- ✅ Score monotonicity (never decreases)
- ✅ Period progression (monotonic)
- ✅ Schema compliance

### Shots Validation
- ✅ Required columns: SHOT_TYPE, SUCCESS, TEAM_ID
- ✅ Valid SHOT_TYPE values ('2pt', '3pt')
- ✅ Valid SUCCESS flags (True, False, 0, 1)
- ✅ Schema compliance

### Cross-Dataset Validation
- ✅ PBP field goal count = shots table rows
- ✅ Index flags match disk state

## Monitoring

View historical metrics:

```python
import pandas as pd
metrics = pd.read_parquet("data/raw/lnb/lnb_metrics_daily.parquet")
print(metrics.tail(10))  # Last 10 validation runs
```

Plot coverage trends:

```python
import matplotlib.pyplot as plt

metrics["run_date"] = pd.to_datetime(metrics["run_date"])
metrics.plot(x="run_date", y="2023_2024_pbp_pct", label="2023-24 PBP Coverage")
plt.show()
```

## Adding Golden Fixtures

Edit `tools/lnb/golden_fixtures.json`:

```json
{
  "fixtures": [
    {
      "season": "2024-2025",
      "game_id": "YOUR_GAME_UUID",
      "description": "Overtime game",
      "expected": {
        "final_score_home": 95,
        "final_score_away": 92,
        "num_pbp_rows": 650,
        "num_shots": 140,
        "num_periods": 5
      }
    }
  ]
}
```

## Troubleshooting

**"Season not ready for modeling"**
- Run validation to see specific issues
- Check coverage percentages
- Review error/warning counts
- Backfill missing games if needed

**Golden fixtures failing**
- API may have changed schema
- Check if row counts differ significantly
- Update golden fixtures if changes are expected

**API spot-check discrepancies**
- Upstream data may have been corrected
- Re-ingest affected games with `--force-refetch`
- Update golden fixtures if corrections are permanent
