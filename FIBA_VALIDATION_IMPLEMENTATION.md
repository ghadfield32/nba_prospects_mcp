# FIBA Validation Layer Implementation

**Date:** 2025-11-16
**Status:** ✅ COMPLETE - Ready for testing with browser scraping
**Related:** FIBA_SHOTS_IMPLEMENTATION.md

---

## Overview

This implementation adds a comprehensive validation and readiness layer for all 4 FIBA cluster leagues (LKL, ABA, BAL, BCL), following the proven LNB production pattern.

**Key Components:**
1. Browser scraping test framework
2. Coverage validation pipeline
3. Season readiness guards
4. Golden fixtures for regression testing
5. MCP tool integration (pending)

---

## Files Created/Modified

### 1. Browser Scraping Test (`tools/fiba/test_browser_scraping.py`)

**Purpose:** Test FIBA shot chart implementation with Playwright browser rendering

**Features:**
- Checks Playwright installation
- Tests all 4 FIBA leagues
- Validates shot data quality
- Provides detailed metrics

**Usage:**
```bash
# Test all leagues
python tools/fiba/test_browser_scraping.py

# Test specific league
python tools/fiba/test_browser_scraping.py --league LKL

# Dry run (check setup only)
python tools/fiba/test_browser_scraping.py --dry-run
```

**Key Function:**
```python
def test_league_shots(
    league_name: str,
    fetch_function,
    season: str = "2023-24",
    max_games: int = 1,
) -> dict:
    """Test shot chart fetching for a single league

    Returns dict with:
    - success: bool
    - shots: int (total count)
    - games: int (unique games)
    - made: int (made shots)
    - pct_made: float (FG%)
    """
```

---

### 2. Coverage Validation (`tools/fiba/validate_and_monitor_coverage.py`)

**Purpose:** Validate data coverage and compute season readiness for FIBA leagues

**Features:**
- Scans game indexes for expected game counts
- Estimates coverage from cache (currently 0, pending persistent storage)
- Computes readiness (>= 95% PBP + shots coverage)
- Generates validation status file

**Usage:**
```bash
python tools/fiba/validate_and_monitor_coverage.py
```

**Output:** `data/raw/fiba/fiba_last_validation.json`
```json
{
  "run_at": "2025-11-16T...",
  "leagues": [
    {
      "league": "LKL",
      "season": "2023-24",
      "ready_for_modeling": false,
      "expected_games": 200,
      "pbp_coverage": 0,
      "pbp_coverage_pct": 0.0,
      "shots_coverage": 0,
      "shots_coverage_pct": 0.0,
      "reason": "PBP coverage 0.0% < 95%; Shots coverage 0.0% < 95%"
    }
  ]
}
```

**Key Functions:**
```python
def load_game_index(league: str, season: str) -> pd.DataFrame:
    """Load game index for FIBA league/season"""

def estimate_coverage_from_cache(league: str, season: str, data_type: str) -> int:
    """Estimate data coverage (TODO: implement when storage added)"""

def check_season_readiness(...) -> dict:
    """Check if season meets readiness criteria (>= 95% coverage)"""

def validate_fiba_cluster() -> dict:
    """Main validation entry point for all 4 FIBA leagues"""
```

---

### 3. Season Readiness Helper (`src/cbb_data/validation/fiba.py`)

**Purpose:** Provide readiness checking for MCP tools and API endpoints

**Features:**
- Validates league/season against validation file
- Enforces >= 95% coverage threshold
- Provides clear error messages
- Supports both raise and return modes

**Usage:**
```python
from cbb_data.validation.fiba import require_fiba_season_ready

# In MCP tool (raises on not ready)
require_fiba_season_ready("LKL", "2023-24")

# In validation script (returns status dict)
status = require_fiba_season_ready("LKL", "2023-24", raise_on_not_ready=False)
if not status["ready_for_modeling"]:
    print(f"Not ready: {status['reason']}")
```

**Key Functions:**
```python
def require_fiba_season_ready(
    league: str,
    season: str,
    raise_on_not_ready: bool = True,
) -> dict | None:
    """Require FIBA season ready for data access

    Checks:
    - >= 95% PBP coverage
    - >= 95% shots coverage
    - No critical errors

    Raises ValueError if not ready (when raise_on_not_ready=True)
    Returns status dict if raise_on_not_ready=False
    """

def get_fiba_validation_status() -> dict:
    """Get current validation status for all FIBA leagues"""

def check_fiba_league_ready(league: str, season: str) -> bool:
    """Quick boolean check if league/season is ready"""
```

---

### 4. Golden Fixtures (`tools/fiba/golden_fixtures_shots.json`)

**Purpose:** Regression testing fixtures to detect schema/quality changes

**Structure:**
```json
{
  "description": "Golden fixtures for FIBA cluster shot chart data",
  "tolerance_pct": 5.0,
  "fixtures": {
    "LKL": {
      "2023-24": {
        "game_id": "301234",
        "home_team": "Žalgiris Kaunas",
        "away_team": "Rytas Vilnius",
        "expected": {
          "total_shots": null,  // Fill after browser scraping test
          "made_shots": null,
          "three_pointers": null,
          "fg_pct": null
        }
      }
    }
    // ... ABA, BAL, BCL
  }
}
```

**Workflow:**
1. Run browser scraping test to get real data
2. Update `expected` values with actual counts
3. Run validation to ensure fixture works
4. Include in CI/CD for ongoing regression detection

---

### 5. Golden Fixtures Validator (`tools/fiba/validate_golden_fixtures.py`)

**Purpose:** Validate actual shot data against golden fixtures

**Features:**
- Fetches current data for fixture games
- Compares against expected values (5% tolerance)
- Detects schema changes, data quality issues
- Provides detailed comparison report

**Usage:**
```bash
# Validate all leagues
python tools/fiba/validate_golden_fixtures.py

# Validate specific league
python tools/fiba/validate_golden_fixtures.py --league LKL
```

**Output:**
```
Testing LKL 2023-24 - Game 301234
================================================================================
Fetching shot chart (use_browser=True)...
✅ VALIDATION PASSED

Comparison:
  Metric               Expected        Actual          Status
  ------------------------------------------------------------
  total_shots          150             148             ✅
  made_shots           75              74              ✅
  three_pointers       45              46              ✅
  fg_pct               0.500           0.500           ✅
```

---

## Integration Points

### MCP Tools (To Be Added)

Add to `src/cbb_data/servers/mcp/tools.py`:

```python
# At top of file
from cbb_data.validation.fiba import require_fiba_season_ready

# Add guard function
def _ensure_fiba_season_ready(league: str, season: str) -> None:
    """Guard function for FIBA season readiness"""
    require_fiba_season_ready(league, season)

# Add MCP tools
def tool_get_fiba_shots(
    league: str,
    season: str,
    team: list[str] | None = None,
    player: list[str] | None = None,
    shot_type: list[str] | None = None,
    limit: int | None = 500,
    compact: bool = True,
) -> dict[str, Any]:
    """Get FIBA cluster shot chart data

    Supported leagues: LKL, ABA, BAL, BCL

    LLM Usage Examples:
        • "LKL made 3-pointers in 2023-24"
          → tool_get_fiba_shots("LKL", "2023-24", shot_type=["3PT"], ...)

        • "Žalgiris shots in 2023-24"
          → tool_get_fiba_shots("LKL", "2023-24", team=["Žalgiris"], ...)
    """
    # Enforce season readiness
    _ensure_fiba_season_ready(league, season)

    # Fetch data based on league
    if league == "LKL":
        from cbb_data.fetchers.lkl import fetch_shot_chart
    elif league == "ABA":
        from cbb_data.fetchers.aba import fetch_shot_chart
    elif league == "BAL":
        from cbb_data.fetchers.bal import fetch_shot_chart
    elif league == "BCL":
        from cbb_data.fetchers.bcl import fetch_shot_chart
    else:
        raise ValueError(f"Invalid FIBA league: {league}")

    shots_df = fetch_shot_chart(season, use_browser=True)

    # Apply filters
    if team:
        shots_df = shots_df[shots_df["TEAM_NAME"].isin(team)]
    if player:
        shots_df = shots_df[shots_df["PLAYER_NAME"].isin(player)]
    if shot_type:
        shots_df = shots_df[shots_df["SHOT_TYPE"].isin(shot_type)]
    if limit:
        shots_df = shots_df.head(limit)

    # Format response
    if compact:
        return {
            "status": "success",
            "count": len(shots_df),
            "data": shots_df.to_dict("records"),
        }
    else:
        return {
            "status": "success",
            "count": len(shots_df),
            "markdown": shots_df.to_markdown(),
        }
```

### REST API Endpoints (To Be Added)

Add to `src/cbb_data/api/rest_api/routes.py`:

```python
from cbb_data.validation.fiba import (
    require_fiba_season_ready,
    get_fiba_validation_status,
)

@router.get("/fiba/readiness")
async def get_fiba_readiness():
    """Get FIBA cluster validation status"""
    try:
        status = get_fiba_validation_status()
        return status
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/fiba/{league}/readiness")
async def get_fiba_league_readiness(league: str):
    """Get readiness for specific FIBA league"""
    try:
        status = get_fiba_validation_status()
        league_data = [l for l in status["leagues"] if l["league"] == league]
        if not league_data:
            raise HTTPException(status_code=404, detail=f"League {league} not found")
        return league_data
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/fiba/{league}/{season}/shots")
async def get_fiba_shots(
    league: str,
    season: str,
    team: Optional[str] = None,
    player: Optional[str] = None,
    shot_type: Optional[str] = None,
    limit: int = 100,
):
    """Get FIBA shot chart data with readiness enforcement"""
    try:
        # Enforce readiness
        require_fiba_season_ready(league, season)

        # Fetch data
        if league == "LKL":
            from cbb_data.fetchers.lkl import fetch_shot_chart
        # ... etc

        shots_df = fetch_shot_chart(season, use_browser=True)

        # Apply filters & return
        # ...

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Testing Workflow

### Step 1: Install Playwright

```bash
uv pip install playwright
playwright install chromium
```

### Step 2: Test Browser Scraping

```bash
# Dry run (check setup)
python tools/fiba/test_browser_scraping.py --dry-run

# Test one league
python tools/fiba/test_browser_scraping.py --league LKL

# Test all leagues
python tools/fiba/test_browser_scraping.py
```

### Step 3: Run Validation

```bash
python tools/fiba/validate_and_monitor_coverage.py
```

**Expected Output (before data fetch):**
```
================================================================================
  FIBA CLUSTER VALIDATION
================================================================================

--------------------------------------------------------------------------------
  Lithuanian Basketball League (LKL)
--------------------------------------------------------------------------------
[INFO] Loaded LKL 2023-24 index: 200 games

⏳ NOT READY
  Expected games: 200
  PBP coverage: 0 (0.0%)
  Shots coverage: 0 (0.0%)
  Reason: PBP coverage 0.0% < 95%; Shots coverage 0.0% < 95%

# ... same for ABA, BAL, BCL
```

### Step 4: Update Golden Fixtures

After successful browser scraping test:

1. Copy actual metrics from test output
2. Update `tools/fiba/golden_fixtures_shots.json`:
   ```json
   {
     "LKL": {
       "2023-24": {
         "expected": {
           "total_shots": 148,  // from test
           "made_shots": 74,
           "three_pointers": 46,
           "fg_pct": 0.500
         }
       }
     }
   }
   ```
3. Run fixture validation:
   ```bash
   python tools/fiba/validate_golden_fixtures.py --league LKL
   ```

### Step 5: Wire into MCP (After Data Validated)

Once seasons are ready:
1. Add FIBA MCP tools to `src/cbb_data/servers/mcp/tools.py`
2. Add FIBA API endpoints to `src/cbb_data/api/rest_api/routes.py`
3. Test MCP integration
4. Deploy

---

## Architecture Patterns

### Pattern 1: Guard Functions

All data access points enforce readiness:
```python
def tool_get_fiba_data(...):
    _ensure_fiba_season_ready(league, season)  # Raises if not ready
    # ... fetch data
```

### Pattern 2: Validation File

Single source of truth for readiness:
```
data/raw/fiba/fiba_last_validation.json
```

All guards read this file - consistency across MCP, API, validation scripts.

### Pattern 3: Coverage Thresholds

Ready when:
- PBP coverage >= 95%
- Shots coverage >= 95%
- 0 critical errors

### Pattern 4: Browser Scraping Fallback

All shot fetching uses `use_browser=True` by default:
```python
shots = fetch_shot_chart(season, use_browser=True)
```

Gracefully handles HTTP 403 blocking.

---

## Known Limitations

1. **No Persistent Storage Yet**
   - FIBA data currently ephemeral (fetched on-demand)
   - Coverage validation shows 0% until storage added
   - **Next:** Add parquet caching or DuckDB storage

2. **Single Season Support**
   - Only validates 2023-24 season currently
   - **Next:** Extend game indexes for historical seasons

3. **Manual Fixture Updates**
   - Golden fixtures need manual population after tests
   - **Next:** Automate fixture generation from test results

4. **Slow Browser Scraping**
   - ~3-5 seconds per game vs <1 second HTTP
   - **Next:** Investigate FIBA API authentication for direct access

---

## Success Metrics

### Completed ✅
- [x] Browser scraping test framework
- [x] Coverage validation script
- [x] Season readiness helpers
- [x] Golden fixtures structure
- [x] Validation documentation

### Pending ⏳
- [ ] Test with real Playwright browser scraping
- [ ] Populate golden fixtures with actual data
- [ ] Wire FIBA into MCP tools
- [ ] Add FIBA REST API endpoints
- [ ] Add persistent storage for FIBA data
- [ ] Extend to historical seasons

---

## Next Steps

**Immediate (Today):**
1. Install Playwright: `uv pip install playwright && playwright install chromium`
2. Test browser scraping: `python tools/fiba/test_browser_scraping.py --league LKL`
3. If successful, update golden fixtures with actual values

**Short Term (This Week):**
4. Run full validation: `python tools/fiba/validate_and_monitor_coverage.py`
5. Add persistent storage (parquet caching)
6. Wire FIBA into MCP tools

**Medium Term (Next 2 Weeks):**
7. Add FIBA REST API endpoints
8. Set up CI/CD for golden fixture validation
9. Extend to historical seasons
10. Complete P0 LNB automation tasks

---

**Implementation Date:** 2025-11-16
**Pattern Source:** LNB production readiness layer
**Status:** Ready for browser scraping tests
