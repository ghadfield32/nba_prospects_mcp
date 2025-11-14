# International Basketball Data Testing & Validation Guide

Comprehensive guide for validating and testing international basketball league data fetchers.

## Overview

This guide covers the complete workflow from code validation to production-ready data fetching for:
- **FIBA Leagues**: BCL, BAL, ABA, LKL (using FIBA LiveStats API)
- **ACB**: Spanish Basketball League (with Zenodo historical data)
- **LNB**: French Basketball League (requires API discovery)

## Quick Start

```bash
# 1. Validate code structure (fast, no imports)
python tools/quick_validate_leagues.py

# 2. Test imports and function definitions
python tools/validate_international_data.py --quick

# 3. Prepare FIBA game indexes
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive

# 4. Validate game indexes
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids

# 5. Test complete data flow
python tools/test_league_complete_flow.py --league BCL --season 2023-24

# 6. Run full validation suite
python tools/validate_international_data.py --comprehensive --export results.json
```

## Tools Reference

### 1. Quick Structure Validator

**File**: `tools/quick_validate_leagues.py`

**Purpose**: Fast validation without importing modules (grep-based)

**Features**:
- Checks function definitions exist
- Validates game index files
- Verifies documentation completeness
- Identifies code quality issues (duplicate imports, etc.)

**Usage**:
```bash
# Validate all leagues
python tools/quick_validate_leagues.py

# Validate specific league
python tools/quick_validate_leagues.py --league BCL

# Export results
python tools/quick_validate_leagues.py --export quick_validation.json
```

**Output**:
```
════════════════════════════════════════════════════════════════════════
BCL Quick Validation
════════════════════════════════════════════════════════════════════════

Code Structure:
  ✅ fetch_schedule (line 123)
  ✅ fetch_player_game (line 234)
  ✅ fetch_team_game (line 345)
  ✅ fetch_pbp (line 456)
  ✅ fetch_shots (line 567)
  ✅ fetch_player_season (line 678)
  ✅ fetch_team_season (line 789)

Game Index:
  ⚠️  Only 3 games found (placeholder data?)
  ⚠️  Game IDs end with 234 (suspicious pattern)

Score: 85/100 (PASS)
```

---

### 2. Comprehensive Data Validator

**File**: `tools/validate_international_data.py`

**Purpose**: Full validation with actual imports and data checks

**Features**:
- Tests all fetch functions with real parameters
- Validates data sources, schemas, columns
- League-specific validators (ACB, LNB)
- Exports detailed results to JSON

**Usage**:
```bash
# Quick validation (imports only)
python tools/validate_international_data.py --quick

# Comprehensive validation (with data fetching)
python tools/validate_international_data.py --comprehensive

# Specific league
python tools/validate_international_data.py --league BCL --comprehensive

# Export results
python tools/validate_international_data.py --comprehensive --export validation_results.json
```

**Output**:
```
════════════════════════════════════════════════════════════════════════
Comprehensive Validation Results
════════════════════════════════════════════════════════════════════════

BCL: ✅ PASS (7/7 functions)
  ✅ fetch_schedule
  ✅ fetch_player_game
  ✅ fetch_team_game
  ✅ fetch_pbp
  ✅ fetch_shots
  ✅ fetch_player_season
  ✅ fetch_team_season

BAL: ✅ PASS (7/7 functions)
...
```

---

### 3. Game Index Validator

**File**: `tools/fiba_game_index_validator.py`

**Purpose**: Validate FIBA game index CSV files and verify game IDs

**Features**:
- Structure validation (required columns, duplicates)
- Live game ID verification via HTTP requests to FIBA
- Sample index creation (for testing)
- Placeholder detection (IDs ending in 234/1234)
- Comprehensive reporting

**Usage**:
```bash
# Validate index structure only
python tools/fiba_game_index_validator.py --league BCL --season 2023-24

# Validate + verify game IDs against FIBA (slow)
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids

# Create sample index for testing
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --create-sample

# Comprehensive report
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids --report
```

**Output**:
```
════════════════════════════════════════════════════════════════════════
Game Index Validation: BCL 2023-24
════════════════════════════════════════════════════════════════════════

Structure Validation:
  ✅ File exists: data/game_indexes/BCL_2023_24.csv
  ✅ All required columns present
  ✅ No duplicate game IDs
  ✅ All dates in valid format

Game ID Verification:
  Testing 25 game IDs against FIBA LiveStats...
  ✅ 123456: Valid
  ✅ 123457: Valid
  ❌ 123458: HTTP 404 (not found)
  ...

Summary:
  Total games: 25
  Valid IDs: 24/25 (96%)
  Invalid IDs: 1

Recommendation: ✅ Index ready for use
```

---

### 4. Complete Flow Tester

**File**: `tools/test_league_complete_flow.py`

**Purpose**: Test complete data fetching pipeline for each league

**Features**:
- Tests all fetch functions (schedule, player_game, team_game, pbp, shots, season)
- Data quality checks (duplicates, nulls, coordinates)
- Timing measurements
- Comprehensive reporting with recommendations
- JSON export of results

**Usage**:
```bash
# Test single league
python tools/test_league_complete_flow.py --league BCL --season 2023-24

# Quick mode (schedule + season aggregates only)
python tools/test_league_complete_flow.py --league BCL --season 2023-24 --quick

# Test all leagues
python tools/test_league_complete_flow.py --league ALL --quick

# Export results
python tools/test_league_complete_flow.py --league BCL --season 2023-24 --export bcl_results.json
```

**Output**:
```
════════════════════════════════════════════════════════════════════════
BCL Test Results - 2023-24
════════════════════════════════════════════════════════════════════════

Overall: 7/7 tests passed (100%)

Function                       Status     Rows       Time
──────────────────────────────────────────────────────────────────────
fetch_schedule                 ✅ PASS    25         2.34s
fetch_player_game              ✅ PASS    450        5.67s
  ℹ️  Sources: fiba_json:420, fiba_html:30
fetch_team_game                ✅ PASS    50         3.21s
fetch_pbp                      ✅ PASS    12500      8.90s
fetch_shots                    ✅ PASS    1250       4.56s
  ✅ Shot coordinates present: ['X', 'Y']
fetch_player_season            ✅ PASS    180        1.23s
fetch_team_season              ✅ PASS    18         0.89s

════════════════════════════════════════════════════════════════════════
RECOMMENDATIONS
════════════════════════════════════════════════════════════════════════

✅ All tests passed - league is production ready!

Next steps:
  1. Add to production pipeline
  2. Set up monitoring for data quality
  3. Configure caching/storage
```

---

### 5. Game ID Collection Helper

**File**: `tools/fiba/collect_game_ids.py`

**Purpose**: Interactive helper for manually collecting FIBA game IDs

**Features**:
- League-specific instructions and URLs
- Interactive prompting for game data
- Automatic game ID validation
- CSV export in correct format
- Append mode for adding to existing indexes

**Usage**:
```bash
# Show instructions only
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24

# Interactive collection
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive

# Append to existing index
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive --append
```

**Interactive Session**:
```
════════════════════════════════════════════════════════════════════════
BCL (Basketball Champions League) Game ID Collection:

1. Visit: https://www.championsleague.basketball/schedule
2. Select your season (e.g., "2023-24")
3. For each game, look for "Stats" or "Box Score" link
4. Extract game ID from URL pattern: fibalivestats.../u/BCL/{GAME_ID}/bs.html
...
════════════════════════════════════════════════════════════════════════

Enter game data (or 'done' when finished):

──────────────────────────────────────────────────────────────────────
Game #1
──────────────────────────────────────────────────────────────────────
FIBA LiveStats URL or Game ID (or 'done'): 123456
Validating game ID 123456...
✅ Game ID 123456 validated successfully

Game date (YYYY-MM-DD): 2023-10-15
Home team: Team A
Away team: Team B
Home score (or leave blank): 85
Away score (or leave blank): 72
Round number (or leave blank): 1

✅ Added game 123456 (Team A vs Team B)
Total games collected: 1
```

---

### 6. ACB Zenodo Setup Helper

**File**: `tools/acb/setup_zenodo_data.py`

**Purpose**: Download and validate ACB historical data from Zenodo

**Features**:
- Downloads Zenodo dataset files
- Validates file structure and data quality
- Tests fetcher integration
- Generates summary reports

**Usage**:
```bash
# List available files
python tools/acb/setup_zenodo_data.py --list

# Download all files
python tools/acb/setup_zenodo_data.py --download

# Validate specific season
python tools/acb/setup_zenodo_data.py --validate --season 2022

# Test fetcher integration
python tools/acb/setup_zenodo_data.py --test --season 2022
```

**Output**:
```
════════════════════════════════════════════════════════════════════════
ACB Zenodo Data Summary
════════════════════════════════════════════════════════════════════════

Found 80 CSV files:

Available seasons: 1983, 1984, ..., 2022, 2023
Coverage: 1983 - 2023

════════════════════════════════════════════════════════════════════════

Validating ACB data for season 2022...
  ✅ acb_player_stats_2022.csv: 245 rows, 25 columns
  ✅ acb_team_stats_2022.csv: 18 rows, 20 columns

Testing ACB fetcher integration for season 2022...
  ✅ Player season: 245 players
  ✅ Team season: 18 teams
  ✅ Zenodo fallback working correctly
```

---

### 7. LNB API Discovery Helper

**File**: `tools/lnb/api_discovery_helper.py`

**Purpose**: Guide API endpoint discovery for LNB using browser DevTools

**Features**:
- Detailed step-by-step instructions
- Endpoint testing functionality
- Code skeleton generation
- Response structure analysis

**Usage**:
```bash
# Show discovery instructions
python tools/lnb/api_discovery_helper.py --discover

# Test a discovered endpoint
python tools/lnb/api_discovery_helper.py --test-endpoint "https://lnb.fr/api/stats/players"

# Generate code skeleton from discovered endpoints
python tools/lnb/api_discovery_helper.py --generate-code
```

**Workflow**:
1. Run with `--discover` to see instructions
2. Open https://lnb.fr/stats/ in browser with DevTools
3. Document endpoints in `tools/lnb/discovered_endpoints.json`
4. Test endpoints with `--test-endpoint`
5. Generate code with `--generate-code`
6. Copy generated code to `src/cbb_data/fetchers/lnb.py`

---

## Complete Validation Workflow

### For FIBA Leagues (BCL, BAL, ABA, LKL)

```bash
# Step 1: Validate code structure
python tools/quick_validate_leagues.py --league BCL

# Step 2: Collect real game IDs (manual process)
python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive
# Collect 20-50 games by visiting league website

# Step 3: Validate game index
python tools/fiba_game_index_validator.py --league BCL --season 2023-24 --verify-ids

# Step 4: Test complete flow
python tools/test_league_complete_flow.py --league BCL --season 2023-24

# Step 5: Run comprehensive validation
python tools/validate_international_data.py --league BCL --comprehensive
```

### For ACB (Spanish League)

```bash
# Step 1: Validate code structure
python tools/quick_validate_leagues.py --league ACB

# Step 2: Download Zenodo historical data
python tools/acb/setup_zenodo_data.py --download

# Step 3: Validate historical season
python tools/acb/setup_zenodo_data.py --validate --season 2022
python tools/acb/setup_zenodo_data.py --test --season 2022

# Step 4: Test complete flow (historical season)
python tools/test_league_complete_flow.py --league ACB --season 2022

# Step 5: Try current season (may fail with 403)
python tools/test_league_complete_flow.py --league ACB --season 2024 --quick
```

### For LNB (French League)

```bash
# Step 1: Validate code structure
python tools/quick_validate_leagues.py --league LNB

# Step 2: Discover API endpoints (manual process)
python tools/lnb/api_discovery_helper.py --discover
# Follow instructions to find endpoints using browser DevTools

# Step 3: Test discovered endpoints
python tools/lnb/api_discovery_helper.py --test-endpoint "URL"

# Step 4: Generate code skeleton
python tools/lnb/api_discovery_helper.py --generate-code
# Copy generated code to src/cbb_data/fetchers/lnb.py

# Step 5: Test complete flow
python tools/test_league_complete_flow.py --league LNB --season 2024 --quick
```

---

## Validation Checklist

Use this checklist to ensure each league is production-ready:

### Code Structure ✓
- [ ] All required functions defined
- [ ] No import errors
- [ ] No duplicate code blocks
- [ ] Proper error handling
- [ ] Source metadata tracked

### Data Quality ✓
- [ ] Real game IDs (not placeholders)
- [ ] Schedule returns >10 games
- [ ] Player/team stats have reasonable values
- [ ] No duplicate player records
- [ ] Shot coordinates present (where applicable)
- [ ] Source tracking works (fiba_json, fiba_html, etc.)

### Documentation ✓
- [ ] README exists in tools/{league}/
- [ ] Examples in docs/INTERNATIONAL_LEAGUES_EXAMPLES.md
- [ ] Known issues documented
- [ ] API discovery guide (if needed)

### Testing ✓
- [ ] Quick validation passes (100%)
- [ ] Complete flow test passes (100%)
- [ ] Data quality checks pass
- [ ] Error handling tested (403, timeout, etc.)

### Production Readiness ✓
- [ ] Caching configured
- [ ] Rate limiting in place
- [ ] Storage integration tested
- [ ] Monitoring/logging configured

---

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Problem: ModuleNotFoundError
# Solution: Check relative imports in src/cbb_data/

# Validate imports
python tools/validate_international_data.py --quick
```

#### Game Index Issues
```bash
# Problem: Only 3 placeholder games
# Solution: Collect real game IDs

python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive
```

#### 403 Access Denied (ACB)
```bash
# Problem: ACB website blocks container IP
# Solution 1: Use Zenodo historical data
python tools/acb/setup_zenodo_data.py --download

# Solution 2: Test from local machine (not container)

# Solution 3: Create manual CSV files
# Place in data/manual/acb/schedule_2024-25.csv
```

#### Empty Data Returns (LNB)
```bash
# Problem: LNB returns empty DataFrames
# Solution: API endpoints not discovered yet

python tools/lnb/api_discovery_helper.py --discover
# Follow DevTools workflow
```

---

## Performance Tips

### Minimize API Calls
```python
# Use caching
from src.cbb_data.storage import fetch_with_storage

df = fetch_with_storage(
    fetch_func=fetch_bcl_player_game,
    cache_key="bcl_player_game_2023_24",
    season="2023-24"
)
```

### Quick Testing
```bash
# Use --quick flag for faster testing
python tools/test_league_complete_flow.py --league ALL --quick

# Only tests schedule + season aggregates (skips game-level data)
```

### Parallel Validation
```bash
# Run multiple validations in parallel
python tools/test_league_complete_flow.py --league BCL --season 2023-24 &
python tools/test_league_complete_flow.py --league BAL --season 2023-24 &
python tools/test_league_complete_flow.py --league ABA --season 2023-24 &
wait
```

---

## Next Steps

After validation passes:

1. **Add to Production Pipeline**
   - Update main data pipeline scripts
   - Configure scheduled fetching
   - Set up storage/caching

2. **Set Up Monitoring**
   - Track data quality metrics
   - Alert on fetch failures
   - Monitor API rate limits

3. **Documentation**
   - Update user-facing docs
   - Add usage examples
   - Document known limitations

4. **Testing**
   - Add to CI/CD pipeline
   - Set up automated regression tests
   - Monitor for schema changes

---

## Support

For issues or questions:
- Check league-specific README: `tools/{league}/README.md`
- Review VALIDATION_SUMMARY.md for current status
- See LEAGUE_WEB_SCRAPING_FINDINGS.md for implementation notes

Last Updated: 2025-11-14
