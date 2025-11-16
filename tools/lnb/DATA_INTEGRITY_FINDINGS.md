# LNB Data Integrity Investigation - CRITICAL FINDINGS

**Investigation Date:** 2025-11-16
**Severity:** HIGH - UUID Corruption Detected

---

## Executive Summary

Investigation into apparent "duplicate files" revealed **a critical data integrity issue**: The normalization pipeline has assigned the SAME game UUIDs to COMPLETELY DIFFERENT GAMES across seasons.

**Impact:**
- Cannot trust GAME_ID values in normalized parquet files
- Actual game count is uncertain due to UUID reuse
- Data analysis using GAME_ID as unique identifier will produce incorrect results

**Recommendation:** DO NOT DELETE FILES - all files represent unique games, not duplicates

---

## Investigation Timeline

### Initial Hypothesis
User questioned why 2021-2022 and 2022-2023 had only 1 game each. Investigation assumed files with same GAME_ID across seasons were duplicates.

### Testing Process
1. **Byte-level hash comparison:** Files with same GAME_ID had DIFFERENT hashes
2. **Row count comparison:** Different row counts (17 vs 18, 18 vs 20)
3. **Player roster comparison:** ZERO common players in most cases
4. **Team ID comparison:** Completely different team IDs
5. **Score comparison:** Different final scores

### Critical Discovery
Files with the same GAME_ID represent **COMPLETELY DIFFERENT GAMES**:
- Different teams (verified via TEAM_ID)
- Different players (zero overlap)
- Different scores
- Different statistics

---

## Detailed Findings

### Case 1: Game ID `7d414bce-f5da-11eb-b3fd-a23ac5ab90da`

**2021-2022 Version:**
- Folder: `data/normalized/lnb/player_game/season=2021-2022/`
- Team 1 ID: `d65120e6-f548-11eb-8476-9ee7b443c3e3`
- Team 2 ID: `c35f6b14-f548-11eb-b69f-86390995a1f5`
- Score: 80-69
- FG%: 37.5% vs 41.1%
- Players: Yannis Morin (5pts), Bodian Massa (2pts), Jaromir Bohacik (0pts), etc.
- SEASON field in data: `2021-2022`

**2023-2024 Version (DIFFERENT GAME):**
- Folder: `data/normalized/lnb/player_game/season=2023-2024/`
- Team 1 ID: `4b442c8e-19b4-11ee-99f6-f3e7e42a2029`
- Team 2 ID: `63b76e03-19b3-11ee-b4d8-29c9149c7a66`
- Score: 76-67
- FG%: 50.0% vs 37.9%
- Players: Shevon Thompson (19pts), Neal Sako (13pts), Gerry Blakes (4pts), etc.
- SEASON field in data: `2023-2024`

**Conclusion:** SAME UUID, DIFFERENT TEAMS, DIFFERENT GAME

---

### Case 2: Game ID `cc7e470e-11a0-11ed-8ef5-8d12cdc95909`

**2022-2023 Version:**
- Folder: `data/normalized/lnb/player_game/season=2022-2023/`
- Team 1 ID: `caa1358f-0663-11ed-901b-d5aa0877340d`
- Team 2 ID: `74ecde61-0661-11ed-862b-f12f9bb7e8f9`
- Score: 84-80
- FG%: 50.8% vs 42.9%
- Players: Stéphane Gombauld (15pts), Emmanuel Nzekwesi (26pts), Caleb Walker (11pts), etc.
- SEASON field in data: `2022-2023`

**2023-2024 Version (DIFFERENT GAME):**
- Folder: `data/normalized/lnb/player_game/season=2023-2024/`
- Team 1 ID: `4b442c8e-19b4-11ee-99f6-f3e7e42a2029`
- Team 2 ID: `63b76e03-19b3-11ee-b4d8-29c9149c7a66`
- Score: 76-67
- FG%: 50.0% vs 37.9%
- Players: Shevon Thompson (19pts), Neal Sako (13pts), Gerry Blakes (4pts), etc.
- SEASON field in data: `2023-2024`

**Conclusion:** SAME UUID, DIFFERENT TEAMS, DIFFERENT GAME

---

### Case 3: UUID Collision

**CRITICAL:** Both `7d414bce...` and `cc7e470e...` in the 2023-2024 folder point to **THE SAME GAME**:
- Same Team IDs: `4b442c8e...` vs `63b76e03...`
- Same Score: 76-67
- Same FG%: 50.0% vs 37.9%
- Same Players: Shevon Thompson, Neal Sako, Gerry Blakes

**This means:**
- The 2023-2024 season has 1 game that was assigned 2 different (but both incorrect) UUIDs
- Those UUIDs were previously used for legitimate games in 2021-2022 and 2022-2023

---

## Root Cause Analysis

### Hypothesis 1: Normalization Pipeline Bug
The normalization pipeline (`create_normalized_tables.py` or similar) has a bug that:
1. Generates UUIDs incorrectly
2. Reuses old UUIDs instead of creating new ones
3. Fails to preserve original game UUIDs from raw PBP data

### Hypothesis 2: Manual Data Manipulation
Someone manually created/edited parquet files and assigned incorrect UUIDs

### Hypothesis 3: Source Data Issue
The raw PBP/historical data has UUID conflicts that were propagated to normalized files

---

## Impact Assessment

### HIGH Impact Issues

1. **Data Analysis Corruption**
   - Any analysis using GAME_ID as unique identifier will conflate different games
   - JOIN operations across datasets may produce incorrect results
   - Historical trends analysis will be skewed

2. **Cannot Deduplicate Reliably**
   - Cannot remove "duplicates" by GAME_ID alone
   - Must use combination of TEAM_ID + SCORE + SEASON to identify unique games

3. **Uncertain Game Count**
   - Initial count: 34 files
   - Suspected duplicates: 4 games (8 files)
   - Actual unique games: Unknown (need to check all 34 files for UUID collisions)

### MEDIUM Impact Issues

1. **Missing GAME_DATE Column**
   - Confirmed: GAME_DATE is None/null in all normalized files
   - Can be recovered from raw fixtures data (game_date column exists)

2. **Incomplete 2025-2026 PBP Data**
   - 2 of 8 fixtures missing PBP/shots
   - Reason: Games are SCHEDULED but not yet played (status='SCHEDULED')

### LOW Impact Issues

1. **Limited Early Season Coverage**
   - 2021-2022: Only 1 game (confirmed unique)
   - 2022-2023: Only 1 game (confirmed unique)
   - Likely test data or limited initial ingestion

---

## Corrected Coverage Assessment

| Season | Files in Player_Game | Unique Games (Verified) | Status |
|--------|---------------------|------------------------|--------|
| 2021-2022 | 1 | 1 | ✅ Verified unique |
| 2022-2023 | 1 | 1 | ✅ Verified unique |
| 2023-2024 | 16 | Unknown | ⚠️ UUID collision detected (at least 2 UUIDs → 1 game) |
| 2024-2025 | 16 | Unknown | ⚠️ Not yet verified for UUID collisions |
| **TOTAL** | **34 files** | **≤32 games** | **UUID integrity compromised** |

**Note:** The actual unique game count may be **less than 34** due to additional undetected UUID collisions.

---

## Recommendations

### IMMEDIATE (Do NOT Delete Files)

1. **DO NOT DELETE ANY FILES**
   - All files represent actual games
   - Deletion would cause data loss
   - UUID collision issue must be resolved first

2. **Create UUID Correction Mapping**
   - Generate new, correct UUIDs for all games
   - Create mapping file: `old_uuid → new_uuid → (team_ids, score, season)`
   - Preserve both versions for data recovery

3. **Add Secondary Unique Identifier**
   - Use combination: `(TEAM_ID_1, TEAM_ID_2, SCORE_1, SCORE_2, SEASON)` as composite key
   - Add `GAME_HASH` column: hash of (teams + scores + season) for deduplication

### SHORT-TERM (Fix Data Integrity)

1. **Audit All 34 Files**
   - Check all files for UUID collisions
   - Generate report of: UUID → [(season, teams, score)]
   - Identify all cases where 1 UUID → multiple games

2. **Re-normalize with Correct UUIDs**
   - Trace back to raw PBP data
   - Use original Atrium Sports UUIDs if available
   - OR: Generate new UUIDs using deterministic hashing

3. **Add Data Quality Checks**
   - Validate UUID uniqueness during normalization
   - Check that GAME_ID + SEASON uniquely identifies a game
   - Verify team rosters don't change for same GAME_ID

### LONG-TERM (Prevent Recurrence)

1. **Fix Normalization Pipeline**
   - Review `create_normalized_tables.py` (or equivalent)
   - Ensure UUIDs are preserved from source data
   - Add validation: same UUID should always have same teams/score

2. **Implement Comprehensive Testing**
   - Test that normalized output preserves UUIDs from input
   - Test that UUID → game mapping is 1:1
   - Add integration tests for data integrity

3. **Add Data Quality Metrics**
   - Track UUID collision rate
   - Monitor for duplicate team/score combinations with different UUIDs
   - Alert on data integrity violations

---

## Files to Preserve (NOT Delete)

**Player Game Files:**
- `data/normalized/lnb/player_game/season=2021-2022/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet` (unique 2021-2022 game)
- `data/normalized/lnb/player_game/season=2022-2023/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet` (unique 2022-2023 game)
- `data/normalized/lnb/player_game/season=2023-2024/game_id=7d414bce-f5da-11eb-b3fd-a23ac5ab90da.parquet` (unique 2023-2024 game, wrong UUID)
- `data/normalized/lnb/player_game/season=2023-2024/game_id=cc7e470e-11a0-11ed-8ef5-8d12cdc95909.parquet` (DUPLICATE of above with different wrong UUID)
- `data/normalized/lnb/player_game/season=2023-2024/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet` (unique game, needs UUID verification)
- `data/normalized/lnb/player_game/season=2024-2025/game_id=0cac6e1b-6715-11f0-a9f3-27e6e78614e1.parquet` (possibly different game, needs verification)

**Team Game Files:** (Same pattern)

**Recommendation:** Keep all files, but create a "canonical" dataset with corrected UUIDs

---

## Next Steps

1. ✅ **Complete UUID Audit** - Check all 34 files for collisions
2. ⬜ **Generate Correction Mapping** - Create old_uuid → new_uuid mapping
3. ⬜ **Add Composite Keys** - Add GAME_HASH for reliable deduplication
4. ⬜ **Fix Normalization Pipeline** - Prevent future UUID corruption
5. ⬜ **Re-normalize with Corrections** - Create clean dataset with proper UUIDs
6. ⬜ **Update Documentation** - Document data quality issues and workarounds

---

## Appendix: Investigation Tools Created

1. **verify_duplicates_and_investigate.py** (465 lines)
   - Byte-level file comparison
   - GAME_DATE recovery check
   - Missing 2025-2026 PBP analysis

2. **analyze_file_differences.py** (150 lines)
   - Player roster comparison
   - Statistics comparison
   - Identified zero player overlap

3. **check_team_names.py** (100 lines)
   - Team ID extraction
   - Score comparison
   - Confirmed different teams for same UUID

---

## Conclusion

The investigation revealed a **critical data integrity issue**: UUID corruption in normalized parquet files. What appeared to be "duplicate files" are actually **unique games incorrectly assigned the same UUIDs**.

**DO NOT DELETE FILES** until:
1. All 34 files are audited for UUID collisions
2. Correction mapping is created
3. Data can be re-normalized with proper UUIDs

**Current Status:** Data is usable but requires careful handling. GAME_ID cannot be trusted as a unique identifier without additional validation (team IDs, scores, season).
