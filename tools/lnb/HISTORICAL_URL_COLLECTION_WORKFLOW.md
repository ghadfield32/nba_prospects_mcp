# LNB Historical UUID Collection Workflow

**Last Updated:** 2025-11-16
**Status:** Ready for URL collection
**Purpose:** Systematic manual collection of match-center URLs for historical seasons

---

## Overview

This workflow guides you through collecting all fixture UUIDs for LNB Pro A historical seasons (2022-2026) using the manual file-based approach.

**Why Manual Collection?**
- LNB calendar page does not expose season navigation controls
- Automated scraping only works for current round
- Manual collection is deterministic and 100% accurate

**Time Estimate:** ~30-60 minutes per season (depending on number of games)

---

## Prerequisites

✅ URL template files created:
- `tools/lnb/urls_2025_2026.txt`
- `tools/lnb/urls_2024_2025.txt`
- `tools/lnb/urls_2023_2024.txt`
- `tools/lnb/urls_2022_2023.txt`

✅ Discovery script with `--from-file` support ready

✅ Pipeline scripts ready:
- `build_game_index.py`
- `bulk_ingest_pbp_shots.py`
- `create_normalized_tables.py`
- `validate_existing_coverage.py`

---

## Workflow Per Season

For each season, follow this 6-step process:

### Step 1: URL Collection (Manual Browser Work)

**Goal:** Populate `tools/lnb/urls_YYYY_YYYY.txt` with all match-center URLs

**Process:**

1. Open the season's URL file in a text editor (e.g., `urls_2024_2025.txt`)

2. For each calendar anchor listed in the file:
   - Copy the calendar URL (e.g., `https://lnb.fr/fr/calendar#2024-11-16`)
   - Paste into browser and navigate to it
   - The page should scroll to that date in the calendar

3. For each game visible on that date:
   - Click the game to open match-center
   - Copy the full URL from the address bar
   - Format: `https://lnb.fr/fr/match-center/<UUID>`
   - Paste it into the URL file under the corresponding date section

4. Continue for all calendar anchors in the file

5. **Optional but recommended:** Browse the full season on the LNB website
   - Look for additional rounds/journées not covered by the calendar anchors
   - Add more date sections as needed
   - Collect match-center URLs for those games too

6. Save the URL file

**Tips:**
- Open calendar in one tab, match-centers in new tabs
- Use a markdown checklist to track which dates you've completed
- The UUID is the long alphanumeric string at the end of the URL
- Blank lines and comments (lines starting with `#`) are ignored by the script

**Result:** `urls_YYYY_YYYY.txt` file populated with all match-center URLs for that season

---

### Step 2: Validate URL File (Optional but Recommended)

**Goal:** Catch formatting errors before running discovery

```bash
uv run python tools/lnb/validate_url_file.py tools/lnb/urls_2024_2025.txt
```

**What it checks:**
- Valid UUID format in each URL
- No duplicate UUIDs
- Proper URL format
- Counts total valid URLs

**Result:** Confirmation that URL file is ready for processing

---

### Step 3: Discover Fixture UUIDs

**Goal:** Extract UUIDs from URLs and store in `fixture_uuids_by_season.json`

```bash
uv run python tools/lnb/discover_historical_fixture_uuids.py \
  --seasons 2024-2025 \
  --from-file tools/lnb/urls_2024_2025.txt
```

**Expected Output:**
```
================================================================================
  FIXTURE UUID DISCOVERY
================================================================================

Seasons to process: ['2024-2025']
Interactive mode: False
Loading from file: tools/lnb/urls_2024_2025.txt

[DISCOVERING] Season 2024-2025...
  [FILE] Loading UUIDs from tools/lnb/urls_2024_2025.txt
  [SUCCESS] Loaded X lines, extracted Y unique UUIDs
  [INFO] Extracted UUIDs:
    1. 0cac6e1b-6715-11f0-a9f3-27e6e78614e1
    2. 0cd1323f-6715-11f0-86f4-27e6e78614e1
    ...

[SAVED] UUID mappings: tools\lnb\fixture_uuids_by_season.json
        Seasons: 1, Total games: Y
```

**Result:** `fixture_uuids_by_season.json` updated with discovered UUIDs

---

### Step 4: Build Game Index

**Goal:** Merge fixture UUIDs into central game index with metadata flags

```bash
uv run python tools/lnb/build_game_index.py --seasons 2024-2025
```

**What it does:**
- Reads UUIDs from `fixture_uuids_by_season.json`
- Creates/updates `data/raw/lnb/lnb_game_index.parquet`
- Adds flags: `has_pbp`, `has_shots`, `has_boxscore`, etc.
- Marks new games as "pending fetch"

**Result:** Game index updated with all discovered fixtures

---

### Step 5: Bulk Ingest PBP + Shots

**Goal:** Fetch play-by-play and shots data for all games in the season

```bash
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025
```

**What it does:**
- Reads game index
- Filters to games needing PBP/shots (where `has_pbp=False` or `has_shots=False`)
- Calls `fetch_lnb_play_by_play()` and `fetch_lnb_shots()` for each game
- Saves to partitioned Parquet: `data/raw/lnb/pbp/season=2024-2025/game_id=<UUID>.parquet`
- Updates game index flags when successful
- Logs errors to `data/raw/lnb/ingestion_errors.csv`

**Expected Output:**
```
[INFO] Loaded game index: N games
[INFO] Filtered to M games in selected seasons
[INFO] X games need fetching

[1/X] 2024-2025 - 0cac6e1b-6715-11...
  Home: Team A
  Away: Team B
    [PBP] ✅ 245 events saved
    [SHOTS] ✅ 58 shots saved
...

[SUMMARY]
Total games processed:    X
PBP success:              Y/X (95.0%)
Shots success:            Y/X (95.0%)
Both PBP + Shots:         Z/X (90.0%)
```

**Result:** Raw PBP and shots data ingested for all games

---

### Step 6: Normalize Data

**Goal:** Transform raw PBP into standardized player_game and team_game tables

```bash
uv run python tools/lnb/create_normalized_tables.py
```

**What it does:**
- Reads all raw PBP files
- Validates UUID matches between filename and data (catches corruption)
- Aggregates events into box score stats
- Saves normalized tables:
  - `data/normalized/lnb/player_game/season=2024-2025/game_id=<UUID>.parquet`
  - `data/normalized/lnb/team_game/season=2024-2025/game_id=<UUID>.parquet`

**Expected Output:**
```
[TRANSFORMING] Season 2024-2025...
  Found Y games to transform
  [1/Y] 0cac6e1b-6715-11...
    ✅ Player game (18 players)
    ✅ Team game (2 teams)
  ...

[SUMMARY]
Total games processed: Y
Player game success:   Y/Y
Team game success:     Y/Y
```

**Result:** Normalized tables ready for analysis

---

### Step 7: Validate Coverage (Final Check)

**Goal:** Verify data integrity and coverage

```bash
uv run python tools/lnb/validate_existing_coverage.py
```

**What it checks:**
- Unique game counts per season
- Duplicate detection across seasons
- Missing PBP/shots flags
- UUID consistency
- Data quality metrics

**Expected Output:**
```
========================================
  COVERAGE VALIDATION SUMMARY
========================================

Per-Season Coverage:
  2024-2025: Y unique games
    - Fixtures with PBP: Y
    - Fixtures with shots: Y
    - Complete: Y/Y (100%)

Data Quality:
  ✅ No duplicate games across seasons
  ✅ All filenames match data UUIDs
  ✅ No corrupted files detected
```

**Result:** Confirmation that season data is complete and valid

---

## Season-by-Season Checklist

### 2025-2026 (Current Season)

**Status:** 🟡 IN PROGRESS

- [x] URL template created
- [ ] Step 1: Collect match-center URLs (1/? collected)
- [ ] Step 2: Validate URL file
- [ ] Step 3: Discover UUIDs
- [ ] Step 4: Build game index
- [ ] Step 5: Bulk ingest
- [ ] Step 6: Normalize
- [ ] Step 7: Validate coverage

**Calendar Anchors to Process:**
- [ ] 2025-11-07
- [ ] 2025-11-11
- [ ] 2025-11-15 (1 game collected)
- [ ] Additional dates TBD

**Current Coverage:** 1/? games

---

### 2024-2025

**Status:** 🟡 PARTIAL - 4 games already ingested

- [x] URL template created
- [ ] Step 1: Collect match-center URLs (0 new)
- [ ] Step 2: Validate URL file
- [ ] Step 3: Discover UUIDs
- [ ] Step 4: Build game index
- [ ] Step 5: Bulk ingest
- [ ] Step 6: Normalize
- [ ] Step 7: Validate coverage

**Calendar Anchors to Process:**
- [ ] 2024-11-16
- [ ] 2024-11-29
- [ ] Additional dates TBD

**Current Coverage:** 4/? games (already in index)

**Known UUIDs:**
- 0cac6e1b-6715-11f0-a9f3-27e6e78614e1 ✅
- 0cd1323f-6715-11f0-86f4-27e6e78614e1 ✅
- 0ce02919-6715-11f0-9d01-27e6e78614e1 ✅
- 0d0504a0-6715-11f0-98ab-27e6e78614e1 ✅

---

### 2023-2024

**Status:** 🔴 MINIMAL - Only 1 game ingested

- [x] URL template created
- [ ] Step 1: Collect match-center URLs (0 new)
- [ ] Step 2: Validate URL file
- [ ] Step 3: Discover UUIDs
- [ ] Step 4: Build game index
- [ ] Step 5: Bulk ingest
- [ ] Step 6: Normalize
- [ ] Step 7: Validate coverage

**Calendar Anchors to Process:**
- [ ] 2023-11-18
- [ ] 2023-11-28
- [ ] Additional dates TBD

**Current Coverage:** 1/? games

**Known UUIDs:**
- 3fcea9a1-1f10-11ee-a687-db190750bdda ✅

---

### 2022-2023

**Status:** 🟡 IN PROGRESS - September 2022 collected (22 games)

- [x] URL template created
- [x] Step 1: Collect match-center URLs (22 September URLs added)
- [x] Step 2: Validate URL file (✅ all valid)
- [ ] Step 3: Discover UUIDs (ready to run)
- [ ] Step 4: Build game index
- [ ] Step 5: Bulk ingest
- [ ] Step 6: Normalize
- [ ] Step 7: Validate coverage

**Calendar Anchors to Process:**
- [x] September 2022 (22 games collected)
- [ ] 2022-10-15
- [ ] 2022-10-29
- [ ] 2022-11-18
- [ ] 2022-11-29
- [ ] 2022-12-10
- [ ] 2022-12-20
- [ ] 2023-01-14
- [ ] 2023-01-28
- [ ] 2023-02-11
- [ ] 2023-02-25
- [ ] 2023-03-11
- [ ] 2023-03-25
- [ ] 2023-04-08
- [ ] 2023-04-22
- [ ] 2023-05-06
- [ ] 2023-05-20
- [ ] Playoffs (May/June 2023 - dates TBD)

**Current Coverage:** 23/~300-350 games (~7-8%)

**Known UUIDs:**
- cc7e470e-11a0-11ed-8ef5-8d12cdc95909 ✅ (previously ingested)
- 22 September 2022 UUIDs ✅ (validated, ready for discovery)

---

## Pro Tips

### Efficient URL Collection

1. **Use browser bookmarks:**
   - Bookmark the calendar with each date anchor
   - Open all bookmarks in tabs at once
   - Click through each tab to collect URLs

2. **Use a URL capture tool:**
   - Copy.ai or similar browser extensions
   - Automatically capture opened URLs
   - Export to text file

3. **Work in batches:**
   - Focus on one calendar date at a time
   - Collect all games for that date before moving to next
   - Update the URL file incrementally

4. **Verify as you go:**
   - Run the validator after each batch
   - Catch errors early
   - Fix duplicates immediately

### Error Handling

**Problem:** URL validation fails
- **Solution:** Check URL format, ensure UUID is complete

**Problem:** Discovery finds duplicate UUIDs
- **Solution:** Remove duplicates from URL file, re-run

**Problem:** Ingestion fails for some games
- **Solution:** Check `data/raw/lnb/ingestion_errors.csv` for details

**Problem:** Normalization skips games
- **Solution:** Check for UUID mismatches in raw data, clean up if needed

---

## Post-Collection Maintenance

After completing all 4 seasons:

1. **Periodic updates:**
   - Run bulk ingestion weekly to catch new games
   - Update URL files with new calendar dates
   - Re-run validation to ensure consistency

2. **Data backups:**
   - Back up `fixture_uuids_by_season.json`
   - Back up `lnb_game_index.parquet`
   - Keep versioned copies of URL files

3. **Documentation:**
   - Update `PROJECT_LOG.md` with final coverage stats
   - Note any gaps or missing data
   - Document lessons learned

---

## Quick Reference Commands

```bash
# Validate URL file
uv run python tools/lnb/validate_url_file.py tools/lnb/urls_<SEASON>.txt

# Discover UUIDs
uv run python tools/lnb/discover_historical_fixture_uuids.py \
  --seasons <SEASON> \
  --from-file tools/lnb/urls_<SEASON>.txt

# Build index
uv run python tools/lnb/build_game_index.py --seasons <SEASON>

# Ingest data
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons <SEASON>

# Normalize
uv run python tools/lnb/create_normalized_tables.py

# Validate
uv run python tools/lnb/validate_existing_coverage.py

# Full pipeline (one season)
uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons <SEASON> --from-file tools/lnb/urls_<SEASON>.txt && \
uv run python tools/lnb/build_game_index.py --seasons <SEASON> && \
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons <SEASON> && \
uv run python tools/lnb/create_normalized_tables.py && \
uv run python tools/lnb/validate_existing_coverage.py
```

---

## Success Criteria

### Per Season

- ✅ URL file contains >80% of season's games
- ✅ No UUID validation errors
- ✅ Discovery succeeds without duplicates
- ✅ Ingestion success rate >90%
- ✅ Normalization success rate >95%
- ✅ Validation shows no data integrity issues

### Overall

- ✅ All 4 seasons have URLs collected
- ✅ `fixture_uuids_by_season.json` has 4 season keys
- ✅ Game index has 100+ total games
- ✅ Coverage validator shows no cross-season duplicates
- ✅ Pipeline runs end-to-end without errors

---

## Next Steps After Completion

1. **Historical analysis:**
   - Run forecasting models on complete historical data
   - Build player/team trend analysis
   - Generate coverage reports

2. **Automated monitoring:**
   - Set up weekly ingestion for new games
   - Alert on validation failures
   - Track coverage gaps

3. **API discovery (optional):**
   - Continue searching for JSON schedule endpoint
   - If found, migrate from manual to automated discovery
   - Maintain URL files as backup/validation

---

**Questions or Issues?**

- Check `PROJECT_LOG.md` for troubleshooting guide
- Review `INVESTIGATION_COMPLETE_SUMMARY.md` for UUID corruption context
- Consult `HISTORICAL_INGESTION_PLAN.md` for original coverage plan
