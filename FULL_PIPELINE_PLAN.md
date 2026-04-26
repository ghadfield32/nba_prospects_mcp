# Full Pipeline Plan: Career Continuity Across League Hops

**Goal:** Enable deterministic career stitching for players like Alex Sarr (OTE → NBL → NBA) and Amen/Ausar Thompson (OTE → NBA) with NO fuzzy matching required.

---

## Current State Assessment

### Game Index Coverage (Layer A)

| League | Status | Seasons | Games | Issues |
|--------|--------|---------|-------|--------|
| ABA | SAMPLE | 1 (2023-24) | 3 | Only sample data |
| BAL | SAMPLE | 1 (2023-24) | 3 | Only sample data |
| BCL | SAMPLE | 1 (2023-24) | 3 | Only sample data |
| LKL | SAMPLE | 1 (2023-24) | 3 | Only sample data |
| **OTE** | **MISSING** | 0 | 0 | **Critical: No data at all** |
| NBL | RAW DATA EXISTS | ? | ? | Parquet files exist in data/nbl_raw/ |
| LNB | BACKUP EXISTS | 2-3 | ~50+ | Backup parquet files exist |

### Raw Data Available (Not Yet Indexed)

1. **NBL (Australia)** - Full parquet datasets:
   - `nbl_results.parquet` - Game results
   - `nbl_box_player.parquet` - Player box scores
   - `nbl_box_team.parquet` - Team box scores
   - `nbl_pbp.parquet` - Play-by-play
   - `nbl_shots.parquet` - Shot chart data

2. **LNB (France)** - Backup parquet files:
   - Game indexes with ~50+ games per season
   - Play-by-play data for 2023-24, 2024-25
   - Shot data for 2023-24, 2024-25

### Pipeline Status

| Phase | Status | Blocker |
|-------|--------|---------|
| Layer A (Game Index) | PARTIAL | Need full data, OTE missing |
| Layer B (Raw Box) | NOT STARTED | Depends on A |
| Layer C (Canonical) | NOT STARTED | Depends on B |
| Layer D (Crosswalk) | NOT STARTED | Depends on C |
| Layer E (Gold) | NOT STARTED | Depends on D |

---

## Execution Plan

### Phase 0: Quick Wins (Parallel Execution)

These can run immediately without external dependencies:

```bash
# Terminal 1: Process existing NBL parquet into game index
python scripts/nbl_parquet_to_index.py  # CREATE THIS

# Terminal 2: Process existing LNB backups into game index
python scripts/lnb_backup_to_index.py   # CREATE THIS
```

### Phase 1A: BCL Historical Enrichment (5 seasons)

**Seasons:** 2020-21, 2021-22, 2022-23, 2023-24, 2024-25

**Method:** FIBA Basketball Champions League website scraping

```bash
cd nba_prospects_mcp
.venv/Scripts/python scripts/enrich_game_indexes.py --league BCL --dry-run
.venv/Scripts/python scripts/enrich_game_indexes.py --league BCL
```

**Validation after each season:**
```bash
.venv/Scripts/python scripts/validate_game_indexes.py --league BCL
```

**Expected Output:**
- `data/game_indexes/BCL_2020_21.csv`
- `data/game_indexes/BCL_2021_22.csv`
- `data/game_indexes/BCL_2022_23.csv`
- `data/game_indexes/BCL_2023_24.csv` (replace sample)
- `data/game_indexes/BCL_2024_25.csv`

### Phase 1C: BAL Enrichment (5 seasons)

**Seasons:** 2020-21, 2021-22, 2022-23, 2023-24, 2024-25

**Method:** FIBA LiveStats + thebal.com scraping

```bash
.venv/Scripts/python scripts/enrich_game_indexes.py --league BAL
```

### Phase 1D: OTE Enrichment (CRITICAL)

**Seasons:** 2022-23, 2023-24, 2024-25

**Why Critical:** OTE is the pipeline for Amen Thompson, Ausar Thompson, and other top prospects who went directly to NBA.

**Method:** overtimeelite.com schedule/box score scraping

```bash
.venv/Scripts/python scripts/enrich_game_indexes.py --league OTE
```

**OTE Heartbeat Checks (add to monitoring):**
- Source reachable (HTTP 200)
- Season page has games
- Latest game has date + score
- GAME_ID stability

### Phase 2: Layer A Validation Gate

```bash
.venv/Scripts/python scripts/validate_game_indexes.py
```

**Gate Requirements (ALL must pass):**
- [ ] GAME_ID unique within (league, season)
- [ ] GAME_DATE parseable for 100% of completed games
- [ ] HOME_SCORE/AWAY_SCORE present for 100% of completed games
- [ ] HOME_TEAM/AWAY_TEAM non-null
- [ ] No duplicate entries

**Output:** `data/_reports/index_quality_summary.json`

### Phase 3: Canonicalize box_player_game

For each league-season that passes Phase 2:

```bash
.venv/Scripts/python scripts/canonicalize_player_game.py  # CREATE THIS
```

**Canonical Schema:**
```
LEAGUE, SEASON, GAME_ID, GAME_DATE, TEAM_ID, TEAM,
PLAYER_ID, PLAYER_NAME, MIN, PTS, REB, AST, STL, BLK, TOV, PF,
FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT,
OREB, DREB, PLUS_MINUS
```

**Layer B/C Gates:**
- No duplicate (LEAGUE, SEASON, GAME_ID, TEAM_ID, PLAYER_ID) keys
- Numeric columns are actually numeric
- made ≤ attempted for all shooting stats

### Phase 4: Build Player Crosswalk

```bash
.venv/Scripts/python scripts/build_player_xwalk.py
```

**Deterministic Match Rules (NO fuzzy matching):**
1. Exact: `(name_key, birth_date)`
2. Exact: `(name_key, birth_year, height_cm)`
3. Exact: `(name_key, birth_year, nationality)`
4. Exact: `(name_key + source_player_id)` for same-league

**Any ambiguity → UNRESOLVED (explicit, not guessed)**

**Output:**
- `data/player_xwalk.parquet`
- `data/_reports/xwalk_unresolved.json`
- `data/_reports/xwalk_collisions.json`

### Phase 5: Create Gold Career Table

```bash
.venv/Scripts/python scripts/build_gold_career.py
```

**Gold Table Requirements:**
- Union of all canonical box_player_game
- Attached CANONICAL_PLAYER_ID via crosswalk
- Unique key: `(CANONICAL_PLAYER_ID, LEAGUE, SEASON, GAME_ID)`
- GAME_DATE present for all rows (sortable)

**Pathway Validation Tests:**
- Alex Sarr: OTE + NBL records under single canonical ID
- Amen Thompson: OTE records linked correctly
- Ausar Thompson: OTE records linked correctly

### Phase 6: Parquet + DuckDB Setup

```bash
.venv/Scripts/python scripts/setup_duckdb.py  # CREATE THIS
```

**DuckDB Views:**
```sql
CREATE VIEW v_gold_player_career_game AS ...
CREATE VIEW v_player_xwalk AS ...
CREATE VIEW v_game_index AS ...
```

**Parity Checks:**
- Row counts match source CSVs/parquets
- Key uniqueness preserved

### Phase 7: Generate Coverage Report

```bash
.venv/Scripts/python scripts/generate_coverage_report.py
```

**Output:** `LEAGUE_COVERAGE_REPORT.md`

**Join Readiness = READY only if:**
- Layer A: PASS
- Canonical: PASS
- Xwalk collisions: 0
- Unresolved: 0 (or explicitly waived)

---

## Monitoring During Long Runs

### Real-time Progress

Each script writes progress to `data/_reports/`:
- `enrichment_progress_{timestamp}.json`
- `validation_progress_{timestamp}.json`

**Watch command:**
```bash
# PowerShell
Get-Content data/_reports/enrichment_progress_*.json -Wait | ConvertFrom-Json

# Bash
tail -f data/_reports/*.json
```

### Parallel Execution Strategy

**Safe to parallelize:**
- BCL enrichment + BAL enrichment + OTE enrichment (different leagues)
- NBL parquet processing (different data source)
- LNB backup processing (different data source)

**Must run sequentially:**
- Enrichment → Validation (within same league)
- All Layer A → Canonicalization
- Canonicalization → Crosswalk
- Crosswalk → Gold Table

---

## Scripts Created

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/validate_game_indexes.py` | Layer A validation | ✅ Created |
| `scripts/enrich_game_indexes.py` | BCL/BAL/OTE enrichment | ✅ Created |
| `scripts/build_player_xwalk.py` | Player identity crosswalk | ✅ Created |
| `scripts/build_gold_career.py` | Gold career table | ✅ Created |
| `scripts/generate_coverage_report.py` | Coverage report | ✅ Created |
| `scripts/nbl_parquet_to_index.py` | NBL raw → index | 📝 To create |
| `scripts/lnb_backup_to_index.py` | LNB backup → index | 📝 To create |
| `scripts/canonicalize_player_game.py` | Box score canonicalization | 📝 To create |
| `scripts/setup_duckdb.py` | DuckDB setup | 📝 To create |

---

## Success Criteria

### Must Have
1. ✅ OTE game index with dates/scores for all available seasons
2. ✅ All leagues pass Layer A validation
3. ✅ Player crosswalk with 0 collisions
4. ✅ Gold table sortable by date
5. ✅ Alex Sarr appears in OTE + NBL under single canonical ID

### Nice to Have
1. Play-by-play data for all leagues
2. Shot chart data with coordinates
3. Player bio data (birth date, height) for disambiguation

---

## Next Immediate Actions

1. **Run enrichment for OTE** (highest priority - currently missing entirely)
2. **Process NBL parquet files** into game index (data already exists)
3. **Process LNB backups** into game index (data already exists)
4. **Expand BCL/BAL** from samples to full seasons
