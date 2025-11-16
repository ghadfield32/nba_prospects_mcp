# LNB Data Pipeline - Operational Runbook

**Version:** 1.0
**Last Updated:** 2025-11-16
**Owner:** Data Engineering Team

## 📋 Table of Contents

1. [Overview](#overview)
2. [Daily Operations](#daily-operations)
3. [Health Checks](#health-checks)
4. [Troubleshooting](#troubleshooting)
5. [Emergency Procedures](#emergency-procedures)
6. [Maintenance Windows](#maintenance-windows)

---

## Overview

The LNB (French Pro A Basketball) data pipeline ingests play-by-play and shots data for 4 historical seasons (2022-2026). The pipeline includes automated quality assurance, regression testing, and API readiness gates.

### Key Components

- **Ingestion:** `tools/lnb/bulk_ingest_pbp_shots.py`
- **Validation:** `tools/lnb/validate_and_monitor_coverage.py`
- **Data Storage:** `data/raw/lnb/{pbp|shots}/season=YYYY-YYYY/`
- **Quality Metrics:** `data/raw/lnb/lnb_metrics_daily.parquet`
- **API Status:** `data/raw/lnb/lnb_last_validation.json`
- **API Endpoints:** `/lnb/readiness`, `/lnb/validation-status`

### Data Flow

```
LNB API → Bulk Ingestion → Parquet Storage → Validation → API Readiness
             ↓                                     ↓
        Provenance Metadata            Golden Fixtures + Spot-Checks
```

---

## Daily Operations

### Standard Daily Workflow

Run these commands **in order** every day:

```bash
# 1. Activate environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate  # Windows

# 2. Ingest latest data for current season
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025

# 3. Run full validation pipeline
uv run python tools/lnb/validate_and_monitor_coverage.py

# 4. Check API readiness
curl http://localhost:8000/lnb/readiness
```

**Expected Time:** 2-5 minutes total

### Seasonal Backfill (As Needed)

To complete historical seasons:

```bash
# Backfill all incomplete seasons
uv run python tools/lnb/bulk_ingest_pbp_shots.py \
  --seasons 2024-2025 2025-2026 \
  --force-refetch

# Validate after backfill
uv run python tools/lnb/validate_and_monitor_coverage.py
```

---

## Health Checks

### 1. Quick Health Check

```bash
# Check validation status file exists
ls -lh data/raw/lnb/lnb_last_validation.json

# View readiness summary
cat data/raw/lnb/lnb_last_validation.json | jq '.seasons[] | {season, ready: .ready_for_modeling}'
```

**Expected Output:**
```json
{"season": "2022-2023", "ready": true}
{"season": "2023-2024", "ready": true}
{"season": "2024-2025", "ready": false}  # Current season in progress
{"season": "2025-2026", "ready": false}  # Future season
```

### 2. Detailed Health Check

```bash
# Run validation in verbose mode
uv run python tools/lnb/validate_and_monitor_coverage.py
```

**What to Look For:**

✅ **HEALTHY:**
- Golden fixtures: `[PASS]`
- API spot-check: `[PASS]` or `[WARN]` with <3 discrepancies
- Ready seasons: ≥2 seasons marked READY
- Consistency errors: 0
- Coverage trending upward in `lnb_metrics_daily.parquet`

⚠️ **WARNING:**
- API spot-check: 3-10 discrepancies (investigate but not urgent)
- Consistency warnings: <5 warnings (review but not blocking)
- Future season coverage: <80% (normal if season hasn't started)

❌ **UNHEALTHY:**
- Golden fixtures: `[FAIL]` → **API schema changed** (urgent)
- API spot-check: >10 discrepancies → **Data drift** (urgent)
- Consistency errors: >0 → **Data corruption** (urgent)
- No seasons READY → **Pipeline broken** (urgent)

### 3. API Endpoint Checks

```bash
# Check API readiness endpoint
curl -s http://localhost:8000/lnb/readiness | jq '.'

# Check validation status
curl -s http://localhost:8000/lnb/validation-status | jq '.'

# Test season guard (should return 409 for unready season)
curl -s http://localhost:8000/lnb/2025-2026/schedule || echo "Expected 409 Conflict"
```

---

## Troubleshooting

### Problem: Golden Fixtures Failing

**Symptoms:**
```
[7/9] Validating golden fixtures (regression testing)...
      Found 5 regression failures:
        - num_pbp_rows: expected=547, actual=550
```

**Diagnosis:**
- LNB changed their API schema or data structure
- Historical data was retro-corrected

**Solution:**
1. **Investigate API changes:**
   ```bash
   # Fetch raw API data for failing game
   curl "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture/42a5eccb-1f10-11ee-b375-e5b34c9599b5/pbp" > temp_pbp.json

   # Compare to expected structure in tools/lnb/golden_fixtures.json
   cat tools/lnb/golden_fixtures.json | jq '.fixtures[0].expected'
   ```

2. **If legitimate API change:**
   - Update golden fixtures with new expected values
   - Document the change in PROJECT_LOG.md
   - Commit updated golden_fixtures.json

3. **If data corruption:**
   - Re-ingest affected games with `--force-refetch`
   - Re-run validation

**Prevention:** Monitor LNB API changelog

### Problem: API Spot-Check Discrepancies

**Symptoms:**
```
[8/9] Running API spot-check...
      Found 15 API discrepancies:
        - final_score: disk=70, api=71
```

**Diagnosis:**
- Live API was updated with final score corrections
- Disk data is stale

**Solution:**
```bash
# Re-ingest affected games
uv run python tools/lnb/bulk_ingest_pbp_shots.py \
  --seasons 2023-2024 \
  --force-refetch

# Re-validate
uv run python tools/lnb/validate_and_monitor_coverage.py
```

**When to Ignore:** <3 discrepancies in non-critical fields (e.g., player names with accents)

### Problem: Consistency Errors

**Symptoms:**
```
[4/7] Running per-game consistency checks...
      Found 10 errors, 0 warnings
      [ERROR] 2023-2024 abc-123: SCORE_MONOTONICITY_VIOLATION
```

**Diagnosis:**
- Score decreased within a game (data corruption)
- Invalid event types in PBP

**Solution:**
1. **Check specific game:**
   ```bash
   # Load game PBP
   import pandas as pd
   df = pd.read_parquet("data/raw/lnb/pbp/season=2023-2024/game_id=abc-123.parquet")
   print(df[["PERIOD_ID", "HOME_SCORE", "AWAY_SCORE"]])
   ```

2. **Re-ingest corrupted game:**
   ```bash
   # Delete corrupted file
   rm data/raw/lnb/pbp/season=2023-2024/game_id=abc-123.parquet
   rm data/raw/lnb/shots/season=2023-2024/game_id=abc-123.parquet

   # Re-fetch
   uv run python tools/lnb/bulk_ingest_pbp_shots.py \
     --seasons 2023-2024 \
     --force-refetch
   ```

### Problem: Season Not Ready for API Access

**Symptoms:**
```
curl http://localhost:8000/lnb/2024-2025/schedule
{"error_code": "SEASON_NOT_READY", "message": "Coverage: 45.2%/42.8%, Errors: 0"}
```

**Diagnosis:**
- Season coverage <95%
- Season has critical errors

**Solution:**
```bash
# Check current coverage
uv run python tools/lnb/validate_and_monitor_coverage.py | grep "2024-2025"

# Run backfill
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025

# Verify readiness
curl http://localhost:8000/lnb/readiness | jq '.seasons[] | select(.season=="2024-2025")'
```

---

## Emergency Procedures

### Critical: All Seasons Marked Not Ready

**Impact:** API will reject all LNB data requests

**Immediate Actions:**
1. Check if validation status file exists:
   ```bash
   cat data/raw/lnb/lnb_last_validation.json
   ```

2. If missing, run validation:
   ```bash
   uv run python tools/lnb/validate_and_monitor_coverage.py
   ```

3. If validation fails, check disk data:
   ```bash
   ls -R data/raw/lnb/pbp/
   ls -R data/raw/lnb/shots/
   ```

4. If disk data missing, restore from backup or re-ingest:
   ```bash
   uv run python tools/lnb/bulk_ingest_pbp_shots.py \
     --seasons 2022-2023 2023-2024 2024-2025 \
     --force-refetch
   ```

### Critical: Validation Pipeline Broken

**Impact:** Cannot verify data quality

**Immediate Actions:**
1. Check Python environment:
   ```bash
   python --version
   uv pip list | grep pandas
   ```

2. Reinstall dependencies:
   ```bash
   uv pip install -e .
   ```

3. Test validation components individually:
   ```bash
   python -c "from tools.lnb.validate_and_monitor_coverage import check_season_readiness; print('OK')"
   ```

---

## Maintenance Windows

### Weekly Maintenance (Sunday 2 AM UTC)

**Tasks:**
1. Backfill any missed games
2. Review `lnb_metrics_daily.parquet` for trends
3. Update golden fixtures if API schema changed
4. Archive old metrics (keep last 90 days)

**Commands:**
```bash
# Full backfill with forced refresh
uv run python tools/lnb/bulk_ingest_pbp_shots.py \
  --seasons 2024-2025 2025-2026 \
  --force-refetch

# Full validation
uv run python tools/lnb/validate_and_monitor_coverage.py

# Archive old metrics (if needed)
python tools/lnb/archive_old_metrics.py --days=90
```

### Monthly Maintenance (1st of Month)

**Tasks:**
1. Review PROJECT_LOG.md for any operational changes
2. Update LNB_OPERATIONAL_RUNBOOK.md if procedures changed
3. Run comprehensive tests:
   ```bash
   uv run python -m pytest tests/test_lnb_production_readiness.py -v
   ```

---

## Monitoring & Alerts

### Key Metrics to Track

| Metric | Normal Range | Alert Threshold | Severity |
|--------|--------------|-----------------|----------|
| Coverage % (historical seasons) | 95-100% | <90% | High |
| Coverage % (current season) | 70-100% | <50% | Medium |
| Consistency errors | 0 | >0 | Critical |
| Golden fixture failures | 0 | >0 | High |
| API discrepancies | 0-2 | >10 | Medium |
| Validation run time | 1-5 min | >10 min | Low |

### Automated Alerts (Future Setup)

**Recommended Alert Configuration:**

```yaml
# Example Prometheus/Alertmanager config
- alert: LNBSeasonNotReady
  expr: lnb_season_ready{season="2023-2024"} == 0
  for: 1h
  annotations:
    summary: "LNB season {{ $labels.season }} is not ready for API access"

- alert: LNBConsistencyErrors
  expr: lnb_consistency_errors > 0
  for: 5m
  annotations:
    summary: "LNB data has {{ $value }} consistency errors"
```

---

## Appendix

### Useful Commands

```bash
# Quick coverage check
cat data/raw/lnb/lnb_last_validation.json | jq '.seasons'

# Count PBP files per season
find data/raw/lnb/pbp/ -name "*.parquet" | cut -d'=' -f2 | cut -d'/' -f1 | sort | uniq -c

# Check latest validation run time
stat -c '%y' data/raw/lnb/lnb_last_validation.json

# Test API endpoints
curl http://localhost:8000/lnb/readiness | jq '.ready_seasons'

# View metrics history
python -c "import pandas as pd; df = pd.read_parquet('data/raw/lnb/lnb_metrics_daily.parquet'); print(df.tail(10))"
```

### Contact Information

- **Data Engineering:** data-eng@example.com
- **On-Call:** oncall@example.com
- **Escalation:** engineering-lead@example.com

### References

- **Validation README:** `tools/lnb/README_VALIDATION.md`
- **API Documentation:** `/docs` (FastAPI auto-docs)
- **Project Log:** `PROJECT_LOG.md`
- **GitHub Repository:** [nba_prospects_mcp](https://github.com/ghadfield32/nba_prospects_mcp)

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-16 | Claude | Initial runbook creation |
