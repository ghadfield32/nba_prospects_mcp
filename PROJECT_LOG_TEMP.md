

## 2025-11-19: LNB Historical Data Normalization Discovery

### Issue Summary
Investigation into why LNB sub-leagues showed limited data revealed a critical gap: 610 games of historical data were never normalized.

### Root Cause Analysis
**Problem:** Raw PBP data existed for 2022-2023 and 2023-2024 seasons but normalized player_game tables were nearly empty.

| Season | Raw Games | Normalized Before | Normalized After |
|--------|-----------|-------------------|------------------|
| 2022-2023 | 306 | 1 file (17 rows) | 306 files (5,943 rows) |
| 2023-2024 | 306 | 1 file (18 rows) | 306 files (6,019 rows) |
| 2024-2025 | 249 | 249 files (5,016 rows) | 249 files (5,016 rows) |
| 2025-2026 | 6 | 6 files (24 rows) | 6 files (24 rows) |

**Why it happened:** The normalization pipeline was never run for the 2022-2023 and 2023-2024 seasons after the raw data was ingested.

### Fix Applied
Executed normalization pipeline for both historical seasons:

```bash
python tools/lnb/create_normalized_tables.py --season 2022-2023 --force
python tools/lnb/create_normalized_tables.py --season 2023-2024 --force
```

### Results After Fix

**Total LNB player_game Data: 17,002 rows**

Breakdown by season:
- 2022-2023: 5,943 rows (all LNB_PROA)
- 2023-2024: 6,019 rows (all LNB_PROA)
- 2024-2025: 5,016 rows
  - LNB_PROA: 4,958 rows
  - LNB_ELITE2: 40 rows (2 games)
  - LNB_ESPOIRS_ELITE: 18 rows (1 game)
  - LNB_ESPOIRS_PROB: 0 rows (0 games)
- 2025-2026: 24 rows (all LNB_PROA, 6 games)

### Sub-League Data Status (2024-2025)
The sub-league game counts (2/1/0) are CORRECT - they reflect the actual number of games played as of November 2025:

| League | Fixtures | Games Played | player_game Rows |
|--------|----------|--------------|------------------|
| LNB_PROA | 7 | 246 | 4,958 |
| LNB_ELITE2 | 12 | 2 | 40 |
| LNB_ESPOIRS_ELITE | 8 | 1 | 18 |
| LNB_ESPOIRS_PROB | 8 | 0 | 0 |

### Data Locations
- Raw PBP: `data/raw/lnb/pbp/season=YYYY-YYYY/game_id=<uuid>.parquet`
- Normalized: `data/normalized/lnb/player_game/season=YYYY-YYYY/`
- Historical fixtures: `data/lnb/historical/YYYY-YYYY/fixtures_div*.parquet`

### Status
- [x] Identified missing normalizations for historical seasons
- [x] Ran normalization for 2022-2023 (306 games -> 5,943 rows)
- [x] Ran normalization for 2023-2024 (306 games -> 6,019 rows)
- [x] Verified final totals: 17,002 player_game rows

---
