# League Completeness Audit & Action Plan

**Date:** 2025-11-16
**Status:** Comprehensive audit of all 20 leagues
**Purpose:** Identify gaps and prioritize work to achieve complete, production-ready coverage

---

## Executive Summary

**Current State:**
- **20 leagues total**: 6 college + 13 prepro + 1 pro (WNBA)
- **Fully Functional:** 16 leagues with all or most datasets
- **LNB Production-Ready:** First international league with complete validation/ops infrastructure
- **Major Gaps:** 4 leagues (ACB scaffold, NZ-NBL scaffold, LNB limited historical, FIBA cluster missing shots)

**Priority Actions:**
1. ✅ Complete LNB historical backfill (2024-2025 to 100%)
2. 🔄 Replicate LNB production pattern to other leagues
3. 🆕 Enable ACB & NZ-NBL (scaffold → functional)
4. 🆕 Add shots data for FIBA cluster
5. 🆕 Add PBP/shots for college cluster (if sources exist)

---

## Detailed League Audit

### Tier 1: Production-Ready (1 league)

#### ✅ LNB Pro A (France)
**Status:** Production-ready with validation/ops infrastructure

**Datasets:** 7/7 complete
- ✅ schedule, player_game, team_game, pbp, shots, player_season, team_season

**Infrastructure:**
- ✅ Incremental ingestion with disk-aware skipping
- ✅ Golden fixtures regression testing
- ✅ API spot-check validation
- ✅ Per-game consistency checks
- ✅ Season readiness gates (≥95% coverage + 0 errors)
- ✅ API readiness endpoints (`/lnb/readiness`, `/lnb/validation-status`)
- ✅ MCP tool guards (4/4 tools protected)
- ✅ Comprehensive test suite (15 tests)
- ✅ Operational runbook

**Historical Coverage Gaps:**
- ❌ 2022-2023: 100% (306/306 games) ✅
- ❌ 2023-2024: 100% (306/306 games) ✅
- ⚠️ 2024-2025: 50% (120/240 games) - **NEEDS BACKFILL**
- ⚠️ 2025-2026: 0% (0/176 games) - Future season

**Action Items:**
1. **Backfill 2024-2025** to 100% coverage
   ```bash
   uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2024-2025
   ```
2. **Set up daily automation** (cron/GitHub Action)
3. **Monitor metrics** via lnb_metrics_daily.parquet

---

### Tier 2: Fully Functional (15 leagues)

These leagues have comprehensive dataset support but lack LNB-style production infrastructure.

#### 🟢 NCAA-MBB & NCAA-WBB
**Datasets:** 7/7 complete
**Historical:** 2002-present (MBB), 2005-present (WBB)
**Source:** ESPN API + CBBpy
**Status:** Mature, real-time (15-min delay)

**Gaps:**
- ⚠️ No validation pipeline like LNB
- ⚠️ No season readiness gates
- ⚠️ No golden fixtures regression testing

**Recommended Actions:**
- [ ] Create NCAA validation pipeline (mirror LNB pattern)
- [ ] Add season readiness checks
- [ ] Add MCP tool guards
- [ ] Create operational runbook

---

#### 🟢 EuroLeague & EuroCup
**Datasets:** 7/7 complete
**Historical:** 2001-present
**Source:** Official EuroLeague API
**Status:** Mature, real-time

**Gaps:**
- ⚠️ No validation pipeline
- ⚠️ No season readiness gates
- ⚠️ No operational docs

**Recommended Actions:**
- [ ] Create EuroLeague validation pipeline
- [ ] Add season readiness checks
- [ ] Add MCP tool guards
- [ ] Create operational runbook

---

#### 🟢 G-League
**Datasets:** 7/7 complete
**Historical:** 2001-present
**Source:** NBA Stats API
**Status:** Mature, real-time (15-min delay)

**Gaps:**
- ⚠️ No validation pipeline
- ⚠️ No season readiness gates

**Recommended Actions:**
- [ ] Create G-League validation pipeline
- [ ] Add season readiness checks

---

#### 🟢 WNBA
**Datasets:** 7/7 complete
**Historical:** 1997-present
**Source:** NBA Stats API
**Status:** Mature, real-time (15-min delay)
**Scope:** Excluded by default (pre_only=True), included when pre_only=False

**Gaps:**
- ⚠️ No validation pipeline
- ⚠️ Excluded from default scope (intentional)

**Recommended Actions:**
- [ ] Create WNBA validation pipeline (if adding to default scope)

---

#### 🟡 NBL (Australia)
**Datasets:** 7/7 complete
**Historical:** 1979-present (schedule), 2015-present (detailed)
**Source:** nblR R Package
**Status:** Functional via R bridge

**Gaps:**
- ⚠️ No validation pipeline
- ⚠️ Depends on R installation
- ⚠️ Tools directory exists but minimal infrastructure

**Recommended Actions:**
- [ ] Add NBL validation pipeline
- [ ] Document R dependency clearly
- [ ] Create setup guide (similar to tools/nbl/README.md)
- [ ] Consider pure Python alternative (if R dependency is problematic)

---

#### 🟡 FIBA Cluster (LKL, ABA, BAL, BCL)
**Datasets:** 6/7 (missing shots)
**Historical:** Current season only
**Source:** FIBA LiveStats HTML

**Gaps:**
- ❌ **No shots data** (4 leagues)
- ⚠️ Limited to current season
- ⚠️ No validation pipeline

**Recommended Actions:**
- [ ] **Investigate FIBA shots data availability** (highest value)
  - Check if FIBA LiveStats provides shot coordinates
  - Check if FIBA API has shot data endpoints
  - If available, implement shots parser
- [ ] Add FIBA cluster validation pipeline
- [ ] Document FIBA cluster setup/usage

---

#### 🟡 College Cluster (NJCAA, NAIA, USPORTS, CCAA)
**Datasets:** 5/7 (missing pbp, shots)
**Historical:** Current season only
**Source:** PrestoSports Scraping

**Gaps:**
- ❌ **No PBP data** (4 leagues)
- ❌ **No shots data** (4 leagues)
- ⚠️ Limited to current season
- ⚠️ No validation pipeline

**Recommended Actions:**
- [ ] **Investigate PrestoSports PBP/shots availability**
  - Check if PrestoSports provides play-by-play
  - Check if PrestoSports provides shot charts
  - If available, implement parsers
- [ ] Add college cluster validation pipeline
- [ ] Document PrestoSports scraping requirements

---

#### 🟡 Development Leagues (CEBL, OTE)
**Datasets:** 5/7 (missing pbp, shots)
**Historical:** 2019-present (CEBL), 2021-present (OTE)
**Source:** FIBA LiveStats (CEBL), HTML Scraping (OTE)

**Gaps:**
- ❌ **No PBP data** (2 leagues)
- ❌ **No shots data** (2 leagues)
- ⚠️ No validation pipeline

**Recommended Actions:**
- [ ] **Investigate CEBL/OTE PBP/shots availability**
  - Check FIBA LiveStats for CEBL play-by-play
  - Check OTE website for detailed event data
- [ ] Add validation pipeline

---

### Tier 3: Scaffold/Blocked (2 leagues)

#### 🔴 ACB (Spain)
**Datasets:** 0/7 (scaffold only for player_season, team_season)
**Historical:** N/A
**Source:** HTML Scraping (JavaScript-rendered)

**Blockers:**
- ❌ **JavaScript-rendered website** (requires Selenium/Playwright)
- ❌ No fetcher implementation
- ❌ Scaffold returns empty DataFrames

**Recommended Actions:**
1. **Enable browser-based scraping** (HIGH PRIORITY)
   ```python
   # Use existing browser_scraper.py infrastructure
   from cbb_data.fetchers.browser_scraper import fetch_with_browser
   ```
2. **Implement ACB scraper**
   - Create `src/cbb_data/fetchers/acb_browser.py`
   - Use Selenium/Playwright for JS rendering
   - Parse schedule, box scores, player stats
3. **Add ACB to dataset registry**
4. **Create ACB validation pipeline**
5. **Add ACB MCP tools**

**Estimated Effort:** 2-3 days (scraper + tests + docs)

---

#### 🔴 NZ-NBL (New Zealand)
**Datasets:** 2/7 (scaffold for schedule, player_game, team_game, pbp; functional player_season, team_season)
**Historical:** Current season (requires manual game index)
**Source:** FIBA LiveStats HTML

**Blockers:**
- ❌ **Requires manual game index creation**
- ❌ No automated game discovery
- ❌ Scaffold returns empty DataFrames

**Recommended Actions:**
1. **Create NZ-NBL game index** (MEDIUM PRIORITY)
   - Manual URL collection (similar to LNB early approach)
   - Or investigate NZ-NBL official site for game listings
2. **Implement index-based fetching**
   ```python
   # Similar to LNB bulk ingestion
   nz_nbl_index = load_nz_nbl_game_index()
   for game in nz_nbl_index:
       fetch_nz_nbl_game(game['id'])
   ```
3. **Add NZ-NBL validation pipeline**
4. **Document manual index creation process**

**Estimated Effort:** 1-2 days (index creation + fetcher updates)

---

## Priority Matrix

### Highest Value (Do First)

| Priority | Task | Impact | Effort | Leagues Affected |
|----------|------|--------|--------|------------------|
| 🔥 **P0** | Complete LNB 2024-2025 backfill | Production-ready current season | 1 hour | LNB |
| 🔥 **P0** | Set up LNB daily automation | Continuous data quality | 2 hours | LNB |
| 🔥 **P1** | Add FIBA shots data | Unlocks shots for 4 leagues | 2-3 days | LKL, ABA, BAL, BCL |
| 🔥 **P1** | Enable ACB scraper | Unlocks 7/7 datasets for major EU league | 2-3 days | ACB |
| 🟡 **P2** | Enable NZ-NBL | Unlocks full dataset for Pacific league | 1-2 days | NZ-NBL |
| 🟡 **P2** | Add NCAA validation pipeline | Production-ready for largest leagues | 3-4 days | NCAA-MBB, NCAA-WBB |
| 🟢 **P3** | Add EuroLeague validation | Production-ready for major EU leagues | 2-3 days | EuroLeague, EuroCup |
| 🟢 **P3** | Investigate PrestoSports PBP/shots | Potential unlock for 4 college leagues | 3-5 days | NJCAA, NAIA, USPORTS, CCAA |

---

## Standardization Roadmap

### Phase 1: LNB Pattern Replication (Weeks 1-2)

**Goal:** Apply LNB production infrastructure to high-value leagues

**Tasks:**
1. ✅ LNB complete (DONE)
2. [ ] NCAA-MBB/WBB validation pipeline
   - Copy LNB validation pattern
   - Adapt for ESPN data source
   - Add NCAA-specific checks
3. [ ] EuroLeague/EuroCup validation pipeline
   - Copy LNB validation pattern
   - Adapt for EuroLeague API
   - Add competition-specific checks

**Deliverables per league:**
- Validation script (validate_and_monitor_coverage.py)
- Golden fixtures (golden_fixtures.json)
- API spot-check function
- Season readiness checks
- Operational runbook
- Test suite

---

### Phase 2: Data Gaps (Weeks 3-4)

**Goal:** Unlock missing datasets for existing leagues

**Tasks:**
1. [ ] FIBA shots data investigation
   - Check FIBA LiveStats for shot coordinates
   - Implement shots parser if available
   - Add to LKL, ABA, BAL, BCL
2. [ ] ACB browser scraper
   - Set up Selenium/Playwright
   - Implement ACB scraper
   - Add all 7 datasets
3. [ ] NZ-NBL game index
   - Create manual game index
   - Wire into fetcher
   - Enable all datasets

**Deliverables:**
- Shots data for FIBA cluster (4 leagues)
- Full ACB support (7/7 datasets)
- Full NZ-NBL support (7/7 datasets)

---

### Phase 3: College PBP/Shots (Weeks 5-6)

**Goal:** Investigate and enable detailed event data for college leagues

**Tasks:**
1. [ ] PrestoSports detailed data investigation
   - Check if PBP available
   - Check if shots available
   - Assess scraping complexity
2. [ ] CEBL/OTE detailed data
   - Check FIBA LiveStats for CEBL PBP
   - Check OTE website for event data
3. [ ] Implement parsers if sources exist

**Deliverables:**
- PBP/shots for college cluster (if available)
- PBP/shots for CEBL/OTE (if available)
- Documentation of limitations if not available

---

### Phase 4: Universal Standards (Weeks 7-8)

**Goal:** Standardize all leagues to same quality level

**Tasks:**
1. [ ] Create universal validation framework
   - Abstract LNB validation pattern
   - Make configurable per league
   - Support different data sources
2. [ ] Add validation for all 20 leagues
3. [ ] Create universal operational runbook
4. [ ] Add comprehensive test coverage

**Deliverables:**
- Validation framework (tools/validation/)
- Per-league validation configs
- Universal operational runbook
- 100% test coverage

---

## Immediate Next Steps (This Week)

### Day 1: Complete LNB
- [x] Add MCP guards ✅
- [x] Add tests ✅
- [x] Create runbook ✅
- [ ] **Backfill 2024-2025 to 100%**
- [ ] **Set up daily automation**

### Day 2-3: Enable ACB
- [ ] Set up browser scraper infrastructure
- [ ] Implement ACB fetcher with Selenium
- [ ] Test schedule, box scores, player stats
- [ ] Add to dataset registry

### Day 4-5: FIBA Shots Investigation
- [ ] Check FIBA LiveStats API for shot data
- [ ] Check FIBA HTML pages for shot coordinates
- [ ] Implement shots parser if available
- [ ] Test with LKL, ABA, BAL, BCL

---

## Long-Term Vision

**End State (3 months):**
- ✅ All 20 leagues fully functional
- ✅ 18/20 with 7/7 datasets (ACB, NZ-NBL: 7/7; FIBA cluster: 7/7 with shots)
- ✅ All leagues with validation pipelines
- ✅ All leagues with season readiness gates
- ✅ All leagues with MCP tool guards
- ✅ All leagues with comprehensive tests
- ✅ Universal operational runbook
- ✅ Daily automation for all leagues
- ✅ Monitoring dashboards

**Quality Standard (LNB Pattern):**
Every league should have:
1. Validation pipeline with golden fixtures
2. API spot-check against live sources
3. Per-game consistency checks
4. Season readiness gates (≥95% coverage + 0 errors)
5. API readiness endpoints
6. MCP tool guards
7. Comprehensive test suite (15+ tests)
8. Operational runbook
9. Daily automation
10. Metrics tracking

---

## Files to Create/Update

### For Each New League Validation:
```
tools/{league}/
├── validate_and_monitor_coverage.py
├── bulk_ingest_{datasets}.py
├── golden_fixtures.json
├── README_VALIDATION.md
├── {LEAGUE}_OPERATIONAL_RUNBOOK.md
└── scripts/
    └── daily_pipeline.sh

tests/
└── test_{league}_production_readiness.py

data/raw/{league}/
├── {league}_last_validation.json
└── {league}_metrics_daily.parquet

src/cbb_data/api/rest_api/
├── routes.py (add /{league}/readiness, /{league}/validation-status)
└── models.py (add {League}ReadinessResponse, etc.)
```

---

## Success Metrics

**Coverage Metrics:**
- [ ] 20/20 leagues fully functional (up from 18/20)
- [ ] 18/20 leagues with 7/7 datasets (up from 16/20)
- [ ] 20/20 leagues with validation pipelines (up from 1/20)
- [ ] 20/20 leagues with season readiness gates (up from 1/20)

**Quality Metrics:**
- [ ] 100% of data access points protected by guards
- [ ] 100% of leagues with comprehensive tests
- [ ] 100% of leagues with operational documentation
- [ ] <1% data quality issues (golden fixtures + spot-checks)

**Operational Metrics:**
- [ ] Daily automation for all leagues
- [ ] <5 minute validation run time per league
- [ ] 95%+ uptime for all data sources
- [ ] <24 hour data freshness for all leagues

---

**Next Update:** After completing LNB backfill and enabling ACB
