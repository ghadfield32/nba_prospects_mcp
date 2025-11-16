# LNB Data Corruption - Root Cause Analysis & Solution

**Date:** 2025-11-16
**Severity:** CRITICAL - Data Integrity Failure
**Status:** Root cause identified, solution proposed

---

## Executive Summary

Investigation traced UUID corruption through the entire pipeline and identified the **exact point of failure**: raw PBP files were saved with incorrect filenames during ingestion, then the normalization script blindly used those filenames as game IDs.

**Impact:**
- 68 normalized files (34 player_game + 34 team_game) represent only **8 unique games**
- 2023-2024 season: 16 files ALL contain the SAME game data
- 2024-2025 season: Similar duplication pattern
- UUID corruption propagated from raw data ingestion through normalization

---

## Root Cause Identification

### The Corruption Chain

```
1. RAW DATA INGESTION (bulk_ingest_pbp_shots.py)
   ↓ BUG: Saved files with WRONG filenames
   ↓ Correct UUID in data: 3fcea9a1-1f10-11ee-a687-db190750bdda
   ↓ Wrong filename: game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet
   ↓
2. RAW PBP FILES
   ↓ 4 files with different filenames containing SAME game data
   ↓
3. NORMALIZATION (create_normalized_tables.py)
   ↓ BUG: Line 558-559 uses FILENAME as game_id
   ↓ pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
   ↓ game_ids = [f.stem.replace("game_id=", "") for f in pbp_files]
   ↓
4. NORMALIZED DATA
   ↓ 34 files per dataset with corrupted UUIDs
   ↓
5. CORRUPTION COMPLETE
```

### Evidence: Filename vs Data UUID Audit

**All 11 raw PBP files audited:**

| Season | Filename UUID | Data UUID (inside parquet) | Match? |
|--------|--------------|---------------------------|--------|
| 2021-2022 | `7d414bce...` | `7d414bce...` | ✅ CORRECT |
| 2022-2023 | `cc7e470e...` | `cc7e470e...` | ✅ CORRECT |
| 2023-2024 | `0cac6e1b...` | `3fcea9a1...` | ❌ **WRONG** |
| 2023-2024 | `0cd1323f...` | `3fcea9a1...` | ❌ **WRONG** |
| 2023-2024 | `3fcea9a1...` | `3fcea9a1...` | ✅ CORRECT |
| 2023-2024 | `7d414bce...` | `3fcea9a1...` | ❌ **WRONG** |
| 2023-2024 | `cc7e470e...` | `3fcea9a1...` | ❌ **WRONG** |
| 2024-2025 | `0cac6e1b...` | `0cac6e1b...` | ✅ CORRECT |
| 2024-2025 | `0cd1323f...` | `0cd1323f...` | ✅ CORRECT |
| 2024-2025 | `0ce02919...` | `0ce02919...` | ✅ CORRECT |
| 2024-2025 | `0d0504a0...` | `0d0504a0...` | ✅ CORRECT |

**Summary:**
- **Total files:** 11
- **Correct:** 7 (63.6%)
- **Corrupted:** 4 (36.4%)
- **All 4 corrupted files** are in 2023-2024 and contain the **SAME game** (`3fcea9a1...`)

---

## Detailed Findings

### Finding 1: 2023-2024 Corruption Pattern

**2023-2024 raw PBP has 5 files:**
1. `game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet`
   - **Actual game inside:** `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - **Result:** Filename WRONG ❌

2. `game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet`
   - **Actual game inside:** `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - **Result:** Filename WRONG ❌

3. `game_id=3fcea9a1-1f10-11ee-a687-db190750bdda.parquet`
   - **Actual game inside:** `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - **Result:** Filename CORRECT ✅

4. `game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet`
   - **Actual game inside:** `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - **Result:** Filename WRONG ❌ (UUID from 2021-2022 season!)

5. `game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet`
   - **Actual game inside:** `3fcea9a1-1f10-11ee-a687-db190750bdda`
   - **Result:** Filename WRONG ❌ (UUID from 2022-2023 season!)

**Conclusion:** 2023-2024 has only **1 unique game** saved **5 times** with different filenames.

### Finding 2: UUID Reuse Across Seasons

**UUID `7d414bce-f5da-11eb-b3fd-a23ac5ab90da`:**
- **2021-2022 (CORRECT):**
  - Filename: `game_id=7d414bce...`
  - Data UUID: `7d414bce...` ✅
  - Teams: `d65120e6...` vs `c35f6b14...`, Score: 80-69

- **2023-2024 (WRONG):**
  - Filename: `game_id=7d414bce...` (reused from 2021!)
  - Data UUID: `3fcea9a1...` ❌
  - Teams: `4b442c8e...` vs `63b76e03...`, Score: 76-67

**UUID `cc7e470e-11a0-11ed-8ef5-8d12cdc95909`:**
- **2022-2023 (CORRECT):**
  - Filename: `game_id=cc7e470e...`
  - Data UUID: `cc7e470e...` ✅
  - Teams: `caa1358f...` vs `74ecde61...`, Score: 84-80

- **2023-2024 (WRONG):**
  - Filename: `game_id=cc7e470e...` (reused from 2022!)
  - Data UUID: `3fcea9a1...` ❌
  - Teams: `4b442c8e...` vs `63b76e03...`, Score: 76-67

### Finding 3: Game Index vs Raw Data Mismatch

**Game Index (`lnb_game_index.parquet`):**
- Contains only **6 games**
- All with correct UUIDs
- Does NOT contain the corrupted filename UUIDs

**Raw PBP Data:**
- Contains **11 files**
- 5 more files than game index entries
- Suggests files were created/duplicated outside of index

**Implication:** Either:
1. Someone manually created/copied files with wrong names
2. The ingestion script has a bug that duplicates/renames files
3. There was a failed batch operation that corrupted filenames

---

## Bug Analysis

### Bug 1: Normalization Script (create_normalized_tables.py)

**Location:** [Lines 558-559](../../tools/lnb/create_normalized_tables.py#L558-L559)

```python
pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
game_ids = [f.stem.replace("game_id=", "") for f in pbp_files]
```

**Problem:**
- Extracts game_id from **filename** instead of reading from data
- If filename is wrong, corruption propagates to normalized data

**Correct Approach:**
```python
# Read game_id from inside the parquet file, not filename
for pbp_file in pbp_files:
    df = pd.read_parquet(pbp_file)
    game_id = df['GAME_ID'].iloc[0]  # Read from data
    # Validate that filename matches
    expected_filename = f"game_id={game_id}.parquet"
    if pbp_file.name != expected_filename:
        logger.warning(f"Filename mismatch: {pbp_file.name} should be {expected_filename}")
```

### Bug 2: Raw Data Ingestion (bulk_ingest_pbp_shots.py)

**Location:** [Line 224](../../tools/lnb/bulk_ingest_pbp_shots.py#L224)

```python
save_partitioned_parquet(pbp_df, "pbp", season, game_id)
# Saves as: season_dir / f"game_id={game_id}.parquet"
```

**Problem:**
- Saves file with `game_id` from function parameter
- Parameter may not match actual GAME_ID in DataFrame
- No validation that parameter matches data

**Need to investigate:** Where does `game_id` parameter come from?

---

## Corrected Game Count

| Season | Raw PBP Files | Unique Games (Verified) | Normalized Files | Status |
|--------|---------------|------------------------|------------------|--------|
| 2021-2022 | 1 | 1 ✅ | 2 (player + team) | CORRECT |
| 2022-2023 | 1 | 1 ✅ | 2 (player + team) | CORRECT |
| 2023-2024 | 5 | 1 ⚠️ | 32 (16 player + 16 team) | **CORRUPTED** |
| 2024-2025 | 4 | 4 ✅ | 8 (4 player + 4 team) | CORRECT |
| **TOTAL** | **11** | **7 unique games** | **44 files** | **Need cleanup** |

**Note:** Expected 68 normalized files (34 per dataset), but audit found only 44 files processed correctly.

---

## Solution Plan

### Phase 1: Immediate Cleanup (Delete Corrupted Raw Files)

**Delete 4 corrupted raw PBP files in 2023-2024:**

```bash
# These files have wrong filenames but contain game 3fcea9a1...
rm data/raw/lnb/pbp/season=2023-2024/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet
rm data/raw/lnb/pbp/season=2023-2024/game_id=0cd1323f-6715-11f0-86f4-27e6e78614e1.parquet
rm data/raw/lnb/pbp/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet
rm data/raw/lnb/pbp/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet
```

**Keep only:**
- `data/raw/lnb/pbp/season=2023-2024/game_id=3fcea9a1-1f10-11ee-a687-db190750bdda.parquet` (CORRECT)

**Also delete corresponding shots files** (if they exist and are corrupted)

### Phase 2: Fix Normalization Script

**Edit `tools/lnb/create_normalized_tables.py`:**

```python
# OLD (WRONG) - Lines 558-559
pbp_files = list(season_pbp_dir.glob("game_id=*.parquet"))
game_ids = [f.stem.replace("game_id=", "") for f in pbp_files]

# NEW (CORRECT)
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
            f"  Using data UUID and skipping this file."
        )
        # Don't process corrupted files - they should be cleaned up first
        continue

    game_ids.append(data_game_id)
```

### Phase 3: Delete Corrupted Normalized Files

**Delete ALL 2023-2024 normalized files except the correct one:**

```bash
# Keep only the file for game 3fcea9a1...
# Delete all others in 2023-2024 folder
```

**Script to identify files to delete:**

```python
import pandas as pd
from pathlib import Path

# Read audit results
with open('tools/lnb/complete_uuid_audit.json') as f:
    audit = json.load(f)

# Find all files in 2023-2024 that DON'T have game_hash=10e4ee163369b9fa
# (which is the hash for the ONE real game)
files_to_delete = []

for uuid, games in audit['uuid_to_games_mapping'].items():
    for game in games:
        if game['folder_season'] == '2023-2024':
            # Check if this is a duplicate or wrong UUID
            if game.get('game_hash') != '10e4ee163369b9fa' and game['dataset_type'] == 'team_game':
                files_to_delete.append(game['file_path'])

print(f"Files to delete: {len(files_to_delete)}")
```

### Phase 4: Investigate Ingestion Bug

**Find where the filename corruption originated:**

1. Review `bulk_ingest_pbp_shots.py` line 224
2. Trace where `game_id` parameter comes from
3. Check if there's a loop bug that reuses wrong game_ids
4. Add validation: `assert game_id == pbp_df['GAME_ID'].iloc[0]`

### Phase 5: Re-run Normalization

```bash
# After cleanup and fixes:
uv run python tools/lnb/create_normalized_tables.py
```

**Expected result:**
- Only 7 games normalized
- 14 total files (7 player_game + 7 team_game)
- All UUIDs validated

### Phase 6: Add Data Quality Checks

**Create validation script:** `tools/lnb/validate_data_integrity.py`

```python
def validate_uuid_consistency():
    """Ensure UUID → game mapping is 1:1"""
    # Check that same UUID always has same teams/score
    # Check that filename matches data UUID
    # Check that game_hash is unique per game
    pass

def validate_no_duplicates():
    """Ensure no duplicate games in normalized data"""
    # Use game_hash to detect duplicates
    # Verify each game appears only once per dataset
    pass
```

---

## Prevention Measures

### 1. Add UUID Validation to Ingestion

```python
def save_partitioned_parquet(df, dataset_type, season, game_id):
    # VALIDATE before saving
    if 'GAME_ID' in df.columns:
        data_game_id = df['GAME_ID'].iloc[0]
        if data_game_id != game_id:
            raise ValueError(
                f"UUID mismatch: parameter={game_id}, data={data_game_id}"
            )

    # Save with validated UUID
    output_file = season_dir / f"game_id={game_id}.parquet"
    df.to_parquet(output_file)
```

### 2. Add Pre-Normalization Checks

```python
def pre_normalization_checks(pbp_dir):
    """Validate raw data before normalization"""
    issues = []

    for pbp_file in pbp_dir.rglob("*.parquet"):
        df = pd.read_parquet(pbp_file)
        filename_uuid = pbp_file.stem.replace("game_id=", "")
        data_uuid = df['GAME_ID'].iloc[0]

        if filename_uuid != data_uuid:
            issues.append({
                'file': pbp_file,
                'filename_uuid': filename_uuid,
                'data_uuid': data_uuid
            })

    if issues:
        raise ValueError(f"Found {len(issues)} files with UUID mismatches")

    return True
```

### 3. Add Post-Normalization Validation

```python
def post_normalization_checks(normalized_dir):
    """Validate normalized data"""
    # Check UUID uniqueness
    # Check game_hash uniqueness
    # Verify row counts make sense
    # Ensure GAME_DATE is populated
    pass
```

---

## Testing Plan

1. **Unit Test:** Validate UUID matching logic
2. **Integration Test:** Run full ingestion → normalization pipeline
3. **Data Quality Test:** Verify no UUID collisions
4. **Regression Test:** Ensure fix doesn't break existing correct data

---

## Estimated Impact

### Before Fix
- 68 normalized files
- 8 unique games
- 60 duplicate/corrupted files (88.2% waste)
- Cannot trust GAME_ID as unique identifier

### After Fix
- 14 normalized files (7 player_game + 7 team_game)
- 7 unique games
- 0 duplicates
- GAME_ID validated and trustworthy
- 79.4% reduction in file count
- 100% data quality

---

## Next Steps

1. ✅ **Root cause identified** - Filename corruption in raw data
2. ✅ **Audit complete** - All 11 raw files checked
3. ⬜ **Delete corrupted raw files** - Clean up 4 bad files
4. ⬜ **Fix normalization script** - Read UUID from data, not filename
5. ⬜ **Delete corrupted normalized files** - Remove duplicates
6. ⬜ **Investigate ingestion bug** - Find where filenames got corrupted
7. ⬜ **Add validation** - Prevent future corruption
8. ⬜ **Re-run pipeline** - Generate clean normalized data
9. ⬜ **Update documentation** - Document data quality measures

---

## Files Referenced

- **Investigation Tools:**
  - [tools/lnb/audit_all_uuid_collisions.py](audit_all_uuid_collisions.py) - Complete UUID audit (415 lines)
  - [tools/lnb/complete_uuid_audit.json](complete_uuid_audit.json) - Audit results
  - [tools/lnb/DATA_INTEGRITY_FINDINGS.md](DATA_INTEGRITY_FINDINGS.md) - Initial findings

- **Pipeline Files:**
  - [tools/lnb/create_normalized_tables.py](create_normalized_tables.py#L558-L559) - BUG: Uses filename as UUID
  - [tools/lnb/bulk_ingest_pbp_shots.py](bulk_ingest_pbp_shots.py#L224) - Saves with parameter UUID
  - [tools/lnb/build_game_index.py](build_game_index.py) - Creates game index

- **Data Files:**
  - `data/raw/lnb/lnb_game_index.parquet` - Game index (6 games)
  - `data/raw/lnb/pbp/season=2023-2024/*.parquet` - 4 corrupted, 1 correct
  - `data/normalized/lnb/{player_game,team_game}/` - 68 files, need cleanup

---

## Conclusion

The UUID corruption was caused by a **two-stage failure**:

1. **Stage 1 (Ingestion):** Raw PBP files saved with incorrect filenames that don't match the GAME_ID column inside the data
2. **Stage 2 (Normalization):** Script used filenames as source of truth instead of reading GAME_ID from data

The fix requires:
- **Immediate:** Delete 4 corrupted raw files
- **Code Fix:** Modify normalization to read UUID from data with filename validation
- **Cleanup:** Delete 60+ duplicate normalized files
- **Prevention:** Add UUID validation at ingestion and normalization steps

**Current Status:** Only **7 unique games** in dataset, not 34 as filenames suggest.
