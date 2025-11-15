# LNB Historical UUID Discovery Guide

**Last Updated**: 2025-11-15
**Purpose**: Guide for discovering and extracting fixture UUIDs from LNB match center pages

---

## Overview

To access historical play-by-play (PBP) and shot data for past LNB seasons, we need **Atrium Sports fixture UUIDs**. These UUIDs are embedded in LNB match center URLs but must be extracted manually or semi-automatically for historical seasons.

---

## Quick Start: Extracting UUIDs from URLs

### Option 1: Interactive Mode (Recommended)

The discovery script now accepts both raw UUIDs and full URLs:

```bash
uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 --interactive
```

**Supported input formats**:
- Raw UUID: `0cac6e1b-6715-11f0-a9f3-27e6e78614e1`
- Match center URL: `https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1`
- Pre-match URL: `https://lnb.fr/fr/pre-match-center?mid=0cac6e1b-6715-11f0-a9f3-27e6e78614e1`

The script will automatically extract UUIDs from URLs and deduplicate them.

### Option 2: Batch Processing from File

If you have a file with URLs (one per line):

```bash
# Create a file with URLs
cat > tools/lnb/2023-2024_urls.txt <<EOF
https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1
https://lnb.fr/fr/match-center/0cd1323f-6715-11f0-86f4-27e6e78614e1
https://lnb.fr/fr/pre-match-center?mid=0ce02919-6715-11f0-9d01-27e6e78614e1
EOF

# Extract UUIDs and add to mapping
uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 --from-file tools/lnb/2023-2024_urls.txt
```

### Option 3: Standalone UUID Extraction

If you just want to extract UUIDs from URLs without saving to the mapping file:

```bash
# From file
uv run python tools/lnb/extract_uuids_from_urls.py --from-file urls.txt --verbose

# From command line
uv run python tools/lnb/extract_uuids_from_urls.py \
    "https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1" \
    "https://lnb.fr/fr/pre-match-center?mid=0cd1323f-6715-11f0-86f4-27e6e78614e1"

# Save to file
uv run python tools/lnb/extract_uuids_from_urls.py --from-file urls.txt --output uuids.txt
```

---

## Manual UUID Discovery Workflow

### Step 1: Navigate to LNB Match Center

1. Go to https://www.lnb.fr/pro-a/calendrier
2. Use the date filter to find games from the target season (e.g., 2023-2024)
3. Look for completed games with "PLAY BY PLAY" tabs available

### Step 2: Extract UUIDs from URLs

#### Method A: Copy Match Center URLs

1. Click on a game to open the match details page
2. Copy the URL from your browser address bar
   - Example: `https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1`
3. The UUID is the last segment of the URL (36 characters)

#### Method B: Inspect Network Requests (Advanced)

1. Open browser DevTools (F12)
2. Go to Network tab
3. Click "PLAY BY PLAY" tab on a game
4. Filter network requests by `atriumsports.com`
5. Look for requests to `/stats/basketball/pbp/` or `/stats/basketball/shooting/`
6. Copy the fixture UUID from the request URL

### Step 3: Save URLs to a File

Create a text file with one URL per line:

```text
https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1
https://lnb.fr/fr/match-center/0cd1323f-6715-11f0-86f4-27e6e78614e1
https://lnb.fr/fr/match-center/0ce02919-6715-11f0-9d01-27e6e78614e1
https://lnb.fr/fr/pre-match-center?mid=0d0504a0-6715-11f0-98ab-27e6e78614e1
```

Save to: `tools/lnb/2023-2024_urls.txt`

### Step 4: Extract and Add to Mapping

```bash
# Process URLs and add to fixture_uuids_by_season.json
uv run python tools/lnb/discover_historical_fixture_uuids.py \
    --seasons 2023-2024 \
    --from-file tools/lnb/2023-2024_urls.txt
```

This will:
- Extract UUIDs from all URLs
- Deduplicate them
- Add them to `tools/lnb/fixture_uuids_by_season.json`
- Print a summary of discovered UUIDs

---

## Validation

After discovering UUIDs, validate them against the Atrium API:

```bash
# Validate all UUIDs for a season
uv run python tools/lnb/validate_discovered_uuids.py --season 2023-2024 --verbose

# Validate and remove invalid UUIDs
uv run python tools/lnb/validate_discovered_uuids.py --season 2023-2024 --remove-invalid
```

This checks:
- ✅ UUID format (36-character hex pattern)
- ✅ Atrium API availability (PBP and shots endpoints)

---

## Running the Full Pipeline

Once UUIDs are discovered and validated:

### 1. Build Game Index

```bash
uv run python tools/lnb/build_game_index.py --seasons 2023-2024 --force-rebuild
```

### 2. Bulk Ingest PBP + Shots

```bash
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2023-2024
```

### 3. Create Normalized Tables

```bash
uv run python tools/lnb/create_normalized_tables.py --season 2023-2024
```

### 4. Validate Data Consistency

```bash
uv run python tools/lnb/validate_data_consistency.py --season 2023-2024
```

---

## Troubleshooting

### Issue: URLs Don't Contain UUIDs

**Solution**: The UUID might be in a query parameter. Try:
- Pre-match URL: `https://lnb.fr/fr/pre-match-center?mid={uuid}`
- Check browser DevTools → Network tab for Atrium API requests

### Issue: "Could not extract UUID from URL"

**Possible causes**:
1. URL format not recognized → Add format to `extract_uuid_from_text()` in `discover_historical_fixture_uuids.py`
2. URL doesn't contain a UUID → Use browser DevTools to find the actual UUID

### Issue: Validation Fails (404 Not Found)

**Possible causes**:
1. UUID is for a future game → Atrium API only provides data for completed games
2. UUID is for a very old game → Atrium may have retention limits (test different seasons)
3. UUID is incorrect → Double-check extraction

### Issue: No PBP/Shots Data Available

**Solution**: Check if the game has "PLAY BY PLAY" tab on the LNB website. Some games may not have detailed data available.

---

## Best Practices

### 1. Start Small (10-20 Games)

Don't try to discover UUIDs for an entire season at once. Start with:
- 10-20 representative games
- Games spread throughout the season
- Games from different teams

### 2. Validate Immediately

Always validate UUIDs before running the full pipeline:

```bash
uv run python tools/lnb/validate_discovered_uuids.py --season 2023-2024
```

### 3. Document Sources

If you're manually discovering UUIDs, keep notes on:
- Date ranges covered
- Teams included
- Any games skipped (and why)

### 4. Check Data Availability

Not all historical games have PBP/shots data. Check:
- Does the LNB match center show "PLAY BY PLAY" tab?
- Does the Atrium API return data (not 404)?

---

## Examples

### Example 1: Discover 2023-2024 Season (Interactive)

```bash
uv run python tools/lnb/discover_historical_fixture_uuids.py --seasons 2023-2024 --interactive
```

Output:
```
[INTERACTIVE] Manual UUID entry for 2023-2024
Enter fixture UUIDs or match center URLs, one per line
Supported formats:
  - Raw UUID: 0cac6e1b-6715-11f0-a9f3-27e6e78614e1
  - Match center URL: https://lnb.fr/fr/match-center/0cac6e1b-6715-11f0-a9f3-27e6e78614e1
  - Pre-match URL: https://lnb.fr/fr/pre-match-center?mid=0cac6e1b-6715-11f0-a9f3-27e6e78614e1
Press Enter on empty line to finish.

URL or UUID: https://lnb.fr/fr/match-center/3fcea9a1-1f10-11ee-a687-db190750bdda
URL or UUID: https://lnb.fr/fr/match-center/cc7e470e-11a0-11ed-8ef5-8d12cdc95909
URL or UUID:

[INFO] Entered 2 items, extracted 2 unique UUIDs
[SUCCESS] Extracted UUIDs:
   1. 3fcea9a1-1f10-11ee-a687-db190750bdda
   2. cc7e470e-11a0-11ed-8ef5-8d12cdc95909
```

### Example 2: Discover from File

```bash
# Create URL file
cat > tools/lnb/2023-2024_urls.txt <<EOF
https://lnb.fr/fr/match-center/3fcea9a1-1f10-11ee-a687-db190750bdda
https://lnb.fr/fr/match-center/cc7e470e-11a0-11ed-8ef5-8d12cdc95909
https://lnb.fr/fr/pre-match-center?mid=7d414bce-f5da-11eb-b3fd-a23ac5ab90da
EOF

# Process
uv run python tools/lnb/discover_historical_fixture_uuids.py \
    --seasons 2023-2024 \
    --from-file tools/lnb/2023-2024_urls.txt
```

### Example 3: Extract UUIDs Only (No Mapping)

```bash
# Just extract and print
uv run python tools/lnb/extract_uuids_from_urls.py --from-file tools/lnb/2023-2024_urls.txt

# Save to file
uv run python tools/lnb/extract_uuids_from_urls.py \
    --from-file tools/lnb/2023-2024_urls.txt \
    --output tools/lnb/2023-2024_uuids.txt
```

---

## Summary

**Short-term (15 minutes)**:
1. Navigate to LNB website → Find 10-20 historical games
2. Copy match center URLs
3. Run discovery script with `--interactive` or `--from-file`
4. Validate UUIDs
5. Run full pipeline

**Long-term (future)**:
1. Investigate Atrium API retention policy (how far back does data go?)
2. Test systematic discovery options (API, enhanced automation)
3. Scale to all available historical seasons

---

## Related Files

- **Discovery Script**: [tools/lnb/discover_historical_fixture_uuids.py](discover_historical_fixture_uuids.py)
- **Extraction Utility**: [tools/lnb/extract_uuids_from_urls.py](extract_uuids_from_urls.py)
- **Validation Script**: [tools/lnb/validate_discovered_uuids.py](validate_discovered_uuids.py)
- **UUID Mapping File**: [tools/lnb/fixture_uuids_by_season.json](fixture_uuids_by_season.json)
- **Pipeline Overview**: [HISTORICAL_COVERAGE_IMPLEMENTATION.md](../../HISTORICAL_COVERAGE_IMPLEMENTATION.md)
