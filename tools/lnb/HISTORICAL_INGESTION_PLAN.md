# LNB Pro A Historical Data Ingestion Plan

**Created:** 2025-11-16
**Status:** Ready to Execute
**Goal:** Maximize historical coverage back to 2021 (or earliest available data)

---

## Executive Summary

This plan provides a systematic approach to discover, validate, ingest, and normalize all available LNB Pro A historical data while avoiding duplicates and ensuring data integrity.

**Current State:**
- Normalized data: 30 unique games (4 duplicates across seasons)
- Historical PBP/shots: 2025-2026 season only
- Coverage gaps: 2021-2025 need historical PBP/shots ingestion

**Target State:**
- Complete historical coverage 2021-2025 from Atrium API
- Zero duplicate games across all seasons
- Full validation with fixture-level coverage tracking
- Clean, normalized box scores for all available games

---

## Phase 1: Pre-Ingestion Cleanup (CRITICAL - Do First)

### 1.1. Execute UUID Corruption Fix

**Why:** Must clean up existing corruption before ingesting more data.

**Steps:**
```bash
# 1. Review cleanup plan (already completed in dry-run)
cat tools/lnb/uuid_fix_report_dryrun_*.json

# 2. Execute cleanup
# Edit tools/lnb/fix_uuid_corruption.py: DRY_RUN = False
.venv/Scripts/python tools/lnb/fix_uuid_corruption.py

# Expected deletions:
#   - 4 raw PBP files (2023-2024 with wrong filenames)
#   - 4 raw shots files (corresponding)
#   - 30 normalized files (duplicates)
```

**Verification:**
```bash
# Should show 7 unique games, 0 duplicates
.venv/Scripts/python tools/lnb/validate_existing_coverage.py
```

**Reference:** [ROOT_CAUSE_AND_SOLUTION.md](ROOT_CAUSE_AND_SOLUTION.md)

---

## Phase 2: Fixture UUID Discovery (Manual + Automated)

### 2.1. Understand API Limitations

**LNB Schedule API:**
- Only returns **current season** fixtures
- Cannot query historical seasons directly
- Endpoint: `https://www.lnb.fr/api/v1/schedule?championship=proa&season=2024-2025`

**Atrium PBP/Shots API:**
- **CAN** retrieve historical data if you have the fixture UUID
- Endpoint: `https://www.eurobasket.com/game-stats-api/v1/matches/{uuid}/play-by-play`
- Challenge: How to discover historical fixture UUIDs?

### 2.2. Fixture UUID Discovery Methods

**Method 1: Manual Scraping from LNB Website (Recommended for thoroughness)**

For each target season (2021-2022, 2022-2023, 2023-2024, 2024-2025):

1. **Visit season archive page:**
   - Example: `https://www.lnb.fr/fr/proa/calendrier-resultats?season=2023-2024`
   - Browse completed games for the season

2. **Open each game's match centre:**
   - Click on game → opens match centre page
   - URL format: `https://www.lnb.fr/fr/proa/matchs/{UUID}/...`
   - Example: `https://www.lnb.fr/fr/proa/matchs/3fcea9a1-1f10-11ee-a687-db190750bdda/...`

3. **Extract UUID from URL:**
   - Copy the UUID portion: `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - Save to `tools/lnb/lnb_match_urls_{season}.txt`

**Method 2: Automated Scraping (Requires scraper)**

Create a scraper to:
1. Fetch LNB season archive pages
2. Parse game links from schedule tables
3. Extract UUIDs from match centre URLs
4. Save to `tools/lnb/fixture_uuids_by_season.json`

**Tool:** `tools/lnb/discover_historical_fixture_uuids.py`

```bash
# Option A: From file of URLs
uv run python tools/lnb/discover_historical_fixture_uuids.py \
  --seasons 2021-2022 2022-2023 2023-2024 2024-2025 \
  --from-file tools/lnb/lnb_match_urls_2021_2025.txt

# Option B: Automated scraping (if scraper is implemented)
uv run python tools/lnb/discover_historical_fixture_uuids.py \
  --seasons 2021-2022 2022-2023 2023-2024 2024-2025 \
  --scrape-lnb-site
```

**Output:** `tools/lnb/fixture_uuids_by_season.json`

### 2.3. Validate Discovered UUIDs

**Before ingesting PBP/shots, verify the UUIDs are valid:**

```bash
uv run python tools/lnb/validate_discovered_uuids.py

# Should check:
#   - Each UUID returns HTTP 200 from Atrium API
#   - Fixture metadata exists
#   - PBP endpoint exists (even if empty)
#   - Shots endpoint exists (even if empty)
```

**Expected gaps:**
- Some games may have fixtures but **no PBP/shots** (game wasn't tracked)
- **Document these gaps** - don't try to "fill" them

---

## Phase 3: Bulk PBP/Shots Ingestion

### 3.1. Update Ingestion Scripts (Fix UUID Corruption Source)

**BEFORE running ingestion, fix the bug that caused corruption:**

**File:** `tools/lnb/bulk_ingest_pbp_shots.py` (around line 224)

**Add validation:**
```python
def save_partitioned_parquet(df, dataset_type, season, game_id):
    """Save parquet with UUID validation"""
    # VALIDATE before saving
    if 'GAME_ID' in df.columns:
        data_game_id = df['GAME_ID'].iloc[0]
        if data_game_id != game_id:
            raise ValueError(
                f"UUID mismatch when saving {dataset_type}:\n"
                f"  Parameter game_id: {game_id}\n"
                f"  Data GAME_ID:      {data_game_id}"
            )

    # Save with validated UUID
    output_file = season_dir / f"game_id={game_id}.parquet"
    df.to_parquet(output_file)
    logger.info(f"Saved {dataset_type}: {output_file.name}")
```

### 3.2. Run Ingestion Per Season

**For each historical season:**

```bash
# 2021-2022
uv run python tools/lnb/bulk_ingest_pbp_shots.py --season 2021-2022

# 2022-2023
uv run python tools/lnb/bulk_ingest_pbp_shots.py --season 2022-2023

# 2023-2024
uv run python tools/lnb/bulk_ingest_pbp_shots.py --season 2023-2024

# 2024-2025
uv run python tools/lnb/bulk_ingest_pbp_shots.py --season 2024-2025
```

**What this does:**
- Reads fixture UUIDs from `fixture_uuids_by_season.json`
- For each UUID:
  - Fetches PBP events from Atrium API
  - Fetches shots from Atrium API
  - Saves to `data/raw/lnb/pbp/season={season}/game_id={uuid}.parquet`
  - Saves to `data/raw/lnb/shots/season={season}/game_id={uuid}.parquet`

**Expected gaps:**
- Some UUIDs will return **empty PBP** (API returns HTTP 200 but no events)
- Some UUIDs will return **empty shots**
- **This is normal** - not all historical games have full tracking

### 3.3. Build Game Index

**Create master index of all ingested games:**

```bash
uv run python tools/lnb/build_game_index.py

# Outputs: data/raw/lnb/lnb_game_index.parquet
```

**What it does:**
- Scans all raw PBP/shots files
- Consolidates metadata: season, competition, status, has_pbp, has_shots
- Creates index for normalization step

### 3.4. Validate Raw Data

**After ingestion, validate what was actually retrieved:**

```bash
# Check for filename vs data UUID mismatches
uv run python -c "
import pandas as pd
from pathlib import Path

pbp_files = sorted(Path('data/raw/lnb/pbp').rglob('*.parquet'))
print(f'Total raw PBP files: {len(pbp_files)}')

mismatches = []
for f in pbp_files:
    df = pd.read_parquet(f)
    if len(df) == 0:
        continue
    filename_uuid = f.stem.replace('game_id=', '')
    data_uuid = df['GAME_ID'].iloc[0]
    if filename_uuid != data_uuid:
        mismatches.append((f.name, filename_uuid, data_uuid))

if mismatches:
    print(f'\n⚠️ Found {len(mismatches)} UUID mismatches:')
    for fname, file_id, data_id in mismatches:
        print(f'  {fname}: {file_id} != {data_id}')
else:
    print('\n✅ All files have matching UUIDs')
"
```

---

## Phase 4: Normalization

### 4.1. Fix Normalization Script (Prevent Future Corruption)

**File:** `tools/lnb/create_normalized_tables.py` (lines 558-559)

**REPLACE:**
```python
# OLD (WRONG)
pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
game_ids = [f.stem.replace("game_id=", "") for f in pbp_files]
```

**WITH:**
```python
# NEW (CORRECT): Read UUID from data, validate filename
pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
game_ids = []

for pbp_file in pbp_files:
    # Read game_id from data, not filename
    df = pd.read_parquet(pbp_file)
    if len(df) == 0:
        logger.warning(f"Empty file: {pbp_file}")
        continue

    data_game_id = df['GAME_ID'].iloc[0]
    filename_game_id = pbp_file.stem.replace("game_id=", "")

    # Validate filename matches data
    if data_game_id != filename_game_id:
        logger.error(
            f"UUID MISMATCH in {pbp_file.name}:\n"
            f"  Filename: {filename_game_id}\n"
            f"  Data:     {data_game_id}\n"
            f"  SKIPPING FILE - clean up raw data first!"
        )
        continue

    game_ids.append(data_game_id)
```

### 4.2. Run Normalization Per Season

**Generate normalized box scores from PBP:**

```bash
# 2021-2022
uv run python tools/lnb/create_normalized_tables.py --season 2021-2022

# 2022-2023
uv run python tools/lnb/create_normalized_tables.py --season 2022-2023

# 2023-2024
uv run python tools/lnb/create_normalized_tables.py --season 2023-2024

# 2024-2025
uv run python tools/lnb/create_normalized_tables.py --season 2024-2025
```

**What this does:**
- Reads raw PBP from `data/raw/lnb/pbp/season={season}/`
- Aggregates to player-game and team-game box scores
- Saves to:
  - `data/normalized/lnb/player_game/season={season}/game_id={uuid}.parquet`
  - `data/normalized/lnb/team_game/season={season}/game_id={uuid}.parquet`

**Important:**
- **One file per game per dataset** (no duplicates across seasons)
- Preserves `SEASON` column
- Preserves `GAME_DATE` if available in raw data
- **Validates UUID consistency** (thanks to fix in 4.1)

### 4.3. Prevent Duplicate Games Across Seasons

**Add guard to normalizer (optional but recommended):**

Before writing normalized file, check if game already exists in a different season:

```python
def check_for_existing_game(game_id: str, current_season: str) -> bool:
    """Check if game_id exists in a different season partition"""
    for dataset in ["player_game", "team_game"]:
        for season in SEASONS_TO_VALIDATE:
            if season == current_season:
                continue
            season_dir = NORMALIZED_ROOT / dataset / f"season={season}"
            if not season_dir.exists():
                continue
            game_file = season_dir / f"game_id={game_id}.parquet"
            if game_file.exists():
                logger.warning(
                    f"Game {game_id} already exists in {dataset} {season}!"
                )
                return True
    return False
```

---

## Phase 5: Validation & Quality Checks

### 5.1. Run Enhanced Validator

**After normalization, validate complete coverage:**

```bash
uv run python tools/lnb/validate_existing_coverage.py

# Should show:
#   - Unique games per dataset (no duplicates)
#   - Per-season row counts
#   - Fixture-level coverage (fixtures with/without PBP/shots)
#   - Any remaining data quality issues
```

### 5.2. Expected Gaps & How to Document Them

**Gaps you WILL encounter:**

1. **Fixtures without PBP:**
   - Some games have fixtures but Atrium has no PBP tracking
   - **Document in report, don't fill**

2. **Fixtures without shots:**
   - Some games have PBP but no shot tracking
   - **Document in report, don't fill**

3. **Partial seasons:**
   - Early seasons (2021-2022, 2022-2023) may have limited games
   - LNB may not have tracked all games initially
   - **Document coverage gaps honestly**

**How the validator shows this:**
```
Season: 2023-2024
  Fixtures:   ✅ 240 rows
  PBP Events: ✅ 180,000 events
  Shots:      ✅ 45,000 shots
  Coverage: 240 fixtures | 220 with PBP | 215 with shots | 20 without PBP | 25 without shots
```

### 5.3. Generate Coverage Matrix

**Create human-readable coverage summary:**

```bash
uv run python tools/lnb/generate_league_coverage_matrix.py

# Outputs: tools/lnb/lnb_coverage_matrix.md
```

**Should show:**
- Games per season
- PBP coverage %
- Shots coverage %
- Missing data explicitly stated

---

## Phase 6: Documentation & Maintenance

### 6.1. Update Documentation

**Files to update:**

1. **docs/LNB_COVERAGE.md**
   - Actual coverage by season
   - Known gaps
   - Data sources

2. **README.md**
   - Update "Available Data" section
   - Add coverage table

3. **tools/lnb/HISTORICAL_INGESTION_PLAN.md** (this file)
   - Mark phases as completed
   - Document any deviations

### 6.2. Add to PROJECT_LOG.md

**Compact entry:**
```markdown
## 2025-11-16: LNB Historical Data Ingestion - Complete Coverage 2021-2025

- Discovered fixture UUIDs for seasons 2021-2025 (manual scraping from LNB site)
- Fixed UUID corruption bug in ingestion pipeline (validation before save)
- Fixed normalization pipeline (reads UUID from data, not filename)
- Ingested historical PBP/shots for all discovered fixtures
- Generated normalized box scores with UUID validation
- Validated coverage: X unique games, Y fixtures with PBP, Z fixtures with shots
- Documented gaps: A fixtures without PBP, B fixtures without shots
- Tools used: bulk_ingest_pbp_shots.py, create_normalized_tables.py, validate_existing_coverage.py
```

### 6.3. Create Maintenance Checklist

**For future data updates:**

- [ ] Discover new fixture UUIDs (end of season)
- [ ] Run ingestion for new season
- [ ] Validate no UUID collisions
- [ ] Run normalization
- [ ] Update coverage validator
- [ ] Regenerate coverage matrix
- [ ] Update documentation

---

## Execution Checklist

Use this to track progress through the plan:

### Pre-Ingestion
- [ ] **Phase 1.1:** Execute UUID corruption fix (`DRY_RUN = False`)
- [ ] **Phase 1.1:** Verify cleanup (should show 7 unique games, 0 duplicates)

### Discovery
- [ ] **Phase 2.2:** Discover fixture UUIDs for 2021-2022
- [ ] **Phase 2.2:** Discover fixture UUIDs for 2022-2023
- [ ] **Phase 2.2:** Discover fixture UUIDs for 2023-2024
- [ ] **Phase 2.2:** Discover fixture UUIDs for 2024-2025
- [ ] **Phase 2.3:** Validate discovered UUIDs

### Ingestion
- [ ] **Phase 3.1:** Add UUID validation to `bulk_ingest_pbp_shots.py`
- [ ] **Phase 3.2:** Ingest PBP/shots for 2021-2022
- [ ] **Phase 3.2:** Ingest PBP/shots for 2022-2023
- [ ] **Phase 3.2:** Ingest PBP/shots for 2023-2024
- [ ] **Phase 3.2:** Ingest PBP/shots for 2024-2025
- [ ] **Phase 3.3:** Build game index
- [ ] **Phase 3.4:** Validate raw data (check UUID mismatches)

### Normalization
- [ ] **Phase 4.1:** Fix normalization script (read UUID from data)
- [ ] **Phase 4.2:** Normalize 2021-2022
- [ ] **Phase 4.2:** Normalize 2022-2023
- [ ] **Phase 4.2:** Normalize 2023-2024
- [ ] **Phase 4.2:** Normalize 2024-2025

### Validation
- [ ] **Phase 5.1:** Run enhanced validator
- [ ] **Phase 5.2:** Document gaps (fixtures without PBP/shots)
- [ ] **Phase 5.3:** Generate coverage matrix

### Documentation
- [ ] **Phase 6.1:** Update docs/LNB_COVERAGE.md
- [ ] **Phase 6.1:** Update README.md
- [ ] **Phase 6.2:** Add entry to PROJECT_LOG.md
- [ ] **Phase 6.3:** Create maintenance checklist

---

## Troubleshooting

### Problem: "UUID mismatch when saving"

**Cause:** Ingestion script received wrong UUID parameter

**Fix:**
1. Check `fixture_uuids_by_season.json` - is the UUID correct?
2. Check API response - does `GAME_ID` field match the UUID?
3. If mismatch persists, log details and investigate source

### Problem: "Many fixtures have no PBP"

**Cause:** Atrium API doesn't have PBP for older games

**Fix:**
- **This is normal** for historical data
- Document the gap percentage
- Don't try to "fill" missing data

### Problem: "Duplicate games across seasons after normalization"

**Cause:** Normalization script didn't validate season partitioning

**Fix:**
1. Delete corrupted normalized files
2. Ensure normalization reads UUID from data (Phase 4.1)
3. Add duplicate check before writing (Phase 4.3)
4. Re-run normalization

---

## Success Criteria

**You'll know the ingestion was successful when:**

1. ✅ Validator shows **0 duplicate games** across seasons
2. ✅ Each season has **N unique games** (player_game and team_game match)
3. ✅ Coverage report shows **X% of fixtures have PBP**
4. ✅ All remaining "issues" are **documented gaps** (not data errors)
5. ✅ Raw data audit shows **0 UUID filename mismatches**
6. ✅ Coverage matrix matches reality (no inflated counts)

---

## References

- **UUID Corruption Fix:** [ROOT_CAUSE_AND_SOLUTION.md](ROOT_CAUSE_AND_SOLUTION.md)
- **Investigation Findings:** [DATA_INTEGRITY_FINDINGS.md](DATA_INTEGRITY_FINDINGS.md)
- **Coverage Validator:** [validate_existing_coverage.py](validate_existing_coverage.py)
- **Ingestion Script:** [bulk_ingest_pbp_shots.py](bulk_ingest_pbp_shots.py)
- **Normalization Script:** [create_normalized_tables.py](create_normalized_tables.py)

---

**Last Updated:** 2025-11-16
**Status:** Ready to execute (pending UUID discovery for 2021-2025)
