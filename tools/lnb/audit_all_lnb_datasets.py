#!/usr/bin/env python3
"""Comprehensive audit of all LNB datasets

This script audits EVERY available LNB dataset to document:
1. What data types are currently implemented
2. Historical coverage for each dataset
3. Data granularities available
4. Schema details
5. What's missing

Usage:
    uv run python tools/lnb/audit_all_lnb_datasets.py

Output:
    - Comprehensive console report
    - tools/lnb/lnb_dataset_catalog.md
    - tools/lnb/lnb_dataset_catalog.json
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# Import all LNB fetchers
try:
    from src.cbb_data.fetchers.lnb import (
        fetch_lnb_play_by_play,
        fetch_lnb_schedule,
        fetch_lnb_shots,
    )
    from src.cbb_data.fetchers.lnb_api import LNBClient
except ImportError as e:
    print(f"[ERROR] Failed to import LNB modules: {e}")
    sys.exit(1)

# ==============================================================================
# CONFIG
# ==============================================================================

OUTPUT_DIR = Path("tools/lnb")

# Test parameters
TEST_SEASON = "2024-2025"
TEST_FIXTURE_UUID = "3522345e-3362-11f0-b97d-7be2bdc7a840"  # Confirmed working

# LNB API test parameters
TEST_YEAR = 2025  # For 2024-25 season
TEST_DIVISION = 1  # Betclic ÉLITE
TEST_COMPETITION = 302  # Betclic ÉLITE competition ID
TEST_MATCH_ID = 28910  # Sample match ID

# ==============================================================================
# DATA MODELS
# ==============================================================================


@dataclass
class DatasetInfo:
    """Information about a single dataset"""

    name: str
    category: str  # schedule, game_detail, season_stats, structure
    source: str  # lnb_api, atrium_api, web_scraper
    status: str  # implemented, partial, missing

    # Coverage
    historical_coverage: str  # "2015-present", "current season only", etc.
    granularity: str  # game, season, player-game, etc.

    # Schema
    columns: list[str] | None = None
    sample_row_count: int = 0

    # Testing
    tested: bool = False
    test_result: str = ""  # success, error, empty
    test_error: str | None = None

    # Notes
    notes: str = ""


# ==============================================================================
# DATASET TESTING
# ==============================================================================


def test_schedule() -> DatasetInfo:
    """Test schedule dataset"""
    print("\n[TESTING] Schedule (fetch_lnb_schedule)...")

    dataset = DatasetInfo(
        name="Schedule",
        category="schedule",
        source="web_scraper",
        status="implemented",
        historical_coverage="2015-present (via web scraping)",
        granularity="game",
        notes="Scraped from lnb.fr/pro-a/calendrier using Playwright. Returns placeholder IDs, not fixture UUIDs.",
    )

    try:
        df = fetch_lnb_schedule(season=TEST_SEASON)
        dataset.tested = True

        if not df.empty:
            dataset.test_result = "success"
            dataset.columns = list(df.columns)
            dataset.sample_row_count = len(df)
            print(f"  ✅ SUCCESS: {len(df)} games, {len(df.columns)} columns")
        else:
            dataset.test_result = "empty"
            print("  ⚠️  EMPTY: No data returned")

    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"  ❌ ERROR: {str(e)[:100]}")

    return dataset


def test_play_by_play() -> DatasetInfo:
    """Test play-by-play dataset"""
    print("\n[TESTING] Play-by-Play (fetch_lnb_play_by_play)...")

    dataset = DatasetInfo(
        name="Play-by-Play",
        category="game_detail",
        source="atrium_api",
        status="implemented",
        historical_coverage="Current season only (2024-25)",
        granularity="event",
        notes="Fetched from Atrium Sports API. Requires fixture UUID from match-center URLs. ~629 events/game, 12 event types.",
    )

    try:
        df = fetch_lnb_play_by_play(TEST_FIXTURE_UUID)
        dataset.tested = True

        if not df.empty:
            dataset.test_result = "success"
            dataset.columns = list(df.columns)
            dataset.sample_row_count = len(df)
            print(f"  ✅ SUCCESS: {len(df)} events, {len(df.columns)} columns")
        else:
            dataset.test_result = "empty"
            print("  ⚠️  EMPTY: No data returned")

    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"  ❌ ERROR: {str(e)[:100]}")

    return dataset


def test_shots() -> DatasetInfo:
    """Test shot chart dataset"""
    print("\n[TESTING] Shot Chart (fetch_lnb_shots)...")

    dataset = DatasetInfo(
        name="Shot Chart",
        category="game_detail",
        source="atrium_api",
        status="implemented",
        historical_coverage="Current season only (2024-25)",
        granularity="shot_attempt",
        notes="Fetched from Atrium Sports API. Requires fixture UUID. ~123 shots/game, coordinates on 0-100 scale.",
    )

    try:
        df = fetch_lnb_shots(TEST_FIXTURE_UUID)
        dataset.tested = True

        if not df.empty:
            dataset.test_result = "success"
            dataset.columns = list(df.columns)
            dataset.sample_row_count = len(df)
            print(f"  ✅ SUCCESS: {len(df)} shots, {len(df.columns)} columns")
        else:
            dataset.test_result = "empty"
            print("  ⚠️  EMPTY: No data returned")

    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"  ❌ ERROR: {str(e)[:100]}")

    return dataset


def test_lnb_api_endpoints() -> list[DatasetInfo]:
    """Test all LNB API client endpoints"""
    print("\n[TESTING] LNB API Client Endpoints...")

    client = LNBClient()
    datasets = []

    # 1. Calendar by Division
    print("\n  Testing: get_calendar_by_division...")
    dataset = DatasetInfo(
        name="Calendar by Division",
        category="schedule",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown (API endpoint exists)",
        granularity="game",
        notes="Endpoint: GET /match/getCalenderByDivision. Returns full season schedule for a division.",
    )
    try:
        games = client.get_calendar_by_division(division_external_id=TEST_DIVISION, year=TEST_YEAR)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.sample_row_count = len(games)
        print(f"    ✅ {len(games)} games")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 2. Team Comparison
    print("\n  Testing: get_team_comparison...")
    dataset = DatasetInfo(
        name="Team Comparison",
        category="game_detail",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown",
        granularity="game",
        notes="Endpoint: GET /stats/getTeamComparison. Pre-match team stats comparison.",
    )
    try:
        data = client.get_team_comparison(match_external_id=TEST_MATCH_ID)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.columns = list(data.keys()) if isinstance(data, dict) else None
        print(f"    ✅ Data keys: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 3. Last Five Home/Away
    print("\n  Testing: get_last_five_home_away...")
    dataset = DatasetInfo(
        name="Last 5 Home/Away",
        category="game_detail",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown",
        granularity="game",
        notes="Endpoint: GET /stats/getLastFiveMatchesHomeAway. Recent form for each team.",
    )
    try:
        data = client.get_last_five_home_away(match_external_id=TEST_MATCH_ID)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.columns = list(data.keys()) if isinstance(data, dict) else None
        print(f"    ✅ Data keys: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 4. Head to Head
    print("\n  Testing: get_head_to_head...")
    dataset = DatasetInfo(
        name="Head to Head",
        category="game_detail",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown",
        granularity="matchup",
        notes="Endpoint: GET /stats/getLastFiveMatchesHeadToHead. Recent head-to-head results.",
    )
    try:
        data = client.get_head_to_head(match_external_id=TEST_MATCH_ID)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.columns = list(data.keys()) if isinstance(data, dict) else None
        print(f"    ✅ Data keys: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 5. Match Officials
    print("\n  Testing: get_match_officials_pregame...")
    dataset = DatasetInfo(
        name="Match Officials",
        category="game_detail",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown",
        granularity="game",
        notes="Endpoint: GET /stats/getMatchOfficialsPreGame. Referee assignments.",
    )
    try:
        data = client.get_match_officials_pregame(match_external_id=TEST_MATCH_ID)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.columns = list(data.keys()) if isinstance(data, dict) else None
        print(f"    ✅ Data keys: {list(data.keys())[:5] if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 6. Competition Teams
    print("\n  Testing: get_competition_teams...")
    dataset = DatasetInfo(
        name="Competition Teams",
        category="structure",
        source="lnb_api",
        status="implemented",
        historical_coverage="Unknown",
        granularity="team",
        notes="Endpoint: GET /stats/getCompetitionTeams. Teams in a competition.",
    )
    try:
        teams = client.get_competition_teams(competition_external_id=TEST_COMPETITION)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.sample_row_count = len(teams) if isinstance(teams, list) else 0
        print(f"    ✅ {len(teams) if isinstance(teams, list) else 'N/A'} teams")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 7. Live Match
    print("\n  Testing: get_live_match...")
    dataset = DatasetInfo(
        name="Live Match",
        category="game_detail",
        source="lnb_api",
        status="implemented",
        historical_coverage="Live games only",
        granularity="game",
        notes="Endpoint: GET /match/getLiveMatch. Currently live games.",
    )
    try:
        data = client.get_live_match()
        dataset.tested = True
        dataset.test_result = "success"
        dataset.sample_row_count = len(data) if isinstance(data, list) else 0
        print(f"    ✅ {len(data) if isinstance(data, list) else 0} live games")
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    # 8. Division Competitions (replaces deprecated get_main_competitions)
    print("\n  Testing: get_division_competitions_by_year...")
    dataset = DatasetInfo(
        name="Division Competitions",
        category="structure",
        source="lnb_api",
        status="implemented",
        historical_coverage="By year",
        granularity="competition",
        notes="Endpoint: GET /common/getDivisionCompetitionByYear. Replaces deprecated getMainCompetition (2025-11-15).",
    )
    try:
        # Use the working replacement endpoint
        comps = client.get_division_competitions_by_year(year=TEST_YEAR, division_external_id=1)
        dataset.tested = True
        dataset.test_result = "success"
        dataset.sample_row_count = len(comps) if isinstance(comps, list) else 0
        print(
            f"    ✅ {len(comps) if isinstance(comps, list) else 'N/A'} competitions (Betclic ÉLITE)"
        )
    except Exception as e:
        dataset.tested = True
        dataset.test_result = "error"
        dataset.test_error = str(e)[:200]
        print(f"    ❌ {str(e)[:100]}")
    datasets.append(dataset)

    return datasets


def document_missing_datasets() -> list[DatasetInfo]:
    """Document datasets that are known to be missing"""
    print("\n[DOCUMENTING] Missing/Placeholder Datasets...")

    missing = []

    # Boxscore (player-game stats)
    missing.append(
        DatasetInfo(
            name="Boxscore (Player-Game Stats)",
            category="game_detail",
            source="lnb_api",
            status="missing",
            historical_coverage="Unknown",
            granularity="player-game",
            tested=False,
            notes="Placeholder in LNB API client. Endpoint path unknown. Needs DevTools discovery.",
        )
    )

    # Season aggregates (player season stats)
    missing.append(
        DatasetInfo(
            name="Player Season Stats",
            category="season_stats",
            source="lnb_api",
            status="partial",
            historical_coverage="Unknown",
            granularity="player-season",
            tested=False,
            notes="get_persons_leaders endpoint exists but returns leaders only, not all players.",
        )
    )

    # Team season stats
    missing.append(
        DatasetInfo(
            name="Team Season Stats",
            category="season_stats",
            source="lnb_api",
            status="missing",
            historical_coverage="Unknown",
            granularity="team-season",
            tested=False,
            notes="No endpoint discovered yet.",
        )
    )

    # Standings
    missing.append(
        DatasetInfo(
            name="Standings",
            category="season_stats",
            source="lnb_api",
            status="partial",
            historical_coverage="Unknown",
            granularity="team-season",
            tested=False,
            notes="get_standing endpoint exists (POST /altrstats/getStanding) but needs testing.",
        )
    )

    # Rosters
    missing.append(
        DatasetInfo(
            name="Team Rosters",
            category="structure",
            source="lnb_api",
            status="missing",
            historical_coverage="Unknown",
            granularity="player-team-season",
            tested=False,
            notes="No endpoint discovered yet.",
        )
    )

    print(f"  Documented {len(missing)} missing/partial datasets")
    return missing


# ==============================================================================
# REPORTING
# ==============================================================================


def generate_markdown_report(datasets: list[DatasetInfo]) -> str:
    """Generate Markdown catalog of all datasets"""

    md = "# LNB Pro A Dataset Catalog\n\n"
    md += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md += "This document catalogs all available and missing datasets for LNB Pro A (French professional basketball).\n\n"

    md += "---\n\n"
    md += "## Summary\n\n"

    # Count by status
    implemented = [d for d in datasets if d.status == "implemented"]
    partial = [d for d in datasets if d.status == "partial"]
    missing = [d for d in datasets if d.status == "missing"]

    md += f"- **Implemented**: {len(implemented)} datasets\n"
    md += f"- **Partial**: {len(partial)} datasets\n"
    md += f"- **Missing**: {len(missing)} datasets\n"
    md += f"- **Total**: {len(datasets)} datasets\n\n"

    # Group by category
    categories = {}
    for d in datasets:
        if d.category not in categories:
            categories[d.category] = []
        categories[d.category].append(d)

    md += "### By Category\n\n"
    for cat, ds_list in sorted(categories.items()):
        md += f"- **{cat.replace('_', ' ').title()}**: {len(ds_list)} datasets\n"

    md += "\n---\n\n"

    # Detailed catalog
    md += "## Implemented Datasets\n\n"
    for dataset in implemented:
        md += f"### {dataset.name}\n\n"
        md += f"- **Category**: {dataset.category}\n"
        md += f"- **Source**: {dataset.source}\n"
        md += f"- **Granularity**: {dataset.granularity}\n"
        md += f"- **Historical Coverage**: {dataset.historical_coverage}\n"
        if dataset.tested:
            md += f"- **Test Result**: {dataset.test_result}\n"
            if dataset.sample_row_count:
                md += f"- **Sample Size**: {dataset.sample_row_count} rows\n"
            if dataset.columns:
                md += f"- **Columns** ({len(dataset.columns)}): {', '.join(dataset.columns[:10])}"
                if len(dataset.columns) > 10:
                    md += f", ... (+{len(dataset.columns) - 10} more)"
                md += "\n"
        if dataset.notes:
            md += f"- **Notes**: {dataset.notes}\n"
        md += "\n"

    md += "---\n\n"
    md += "## Partial Datasets\n\n"
    for dataset in partial:
        md += f"### {dataset.name}\n\n"
        md += f"- **Category**: {dataset.category}\n"
        md += f"- **Source**: {dataset.source}\n"
        md += "- **Status**: Partially implemented\n"
        md += f"- **Notes**: {dataset.notes}\n\n"

    md += "---\n\n"
    md += "## Missing Datasets\n\n"
    for dataset in missing:
        md += f"### {dataset.name}\n\n"
        md += f"- **Category**: {dataset.category}\n"
        md += f"- **Expected Source**: {dataset.source}\n"
        md += f"- **Expected Granularity**: {dataset.granularity}\n"
        md += f"- **Notes**: {dataset.notes}\n\n"

    md += "---\n\n"
    md += "## Data Source Legend\n\n"
    md += "- **lnb_api**: Official LNB API (api-prod.lnb.fr)\n"
    md += "- **atrium_api**: Atrium Sports API (third-party stats provider)\n"
    md += "- **web_scraper**: Playwright-based web scraping from lnb.fr\n\n"

    return md


def print_console_report(datasets: list[DatasetInfo]) -> None:
    """Print summary to console"""
    print(f"\n\n{'='*80}")
    print("  LNB DATASET CATALOG - SUMMARY")
    print(f"{'='*80}\n")

    # Status summary
    implemented = [d for d in datasets if d.status == "implemented"]
    partial = [d for d in datasets if d.status == "partial"]
    missing = [d for d in datasets if d.status == "missing"]

    print("STATUS SUMMARY:")
    print(f"  Implemented: {len(implemented)}/{len(datasets)}")
    print(f"  Partial:     {len(partial)}/{len(datasets)}")
    print(f"  Missing:     {len(missing)}/{len(datasets)}")

    # Category summary
    categories = {}
    for d in datasets:
        if d.category not in categories:
            categories[d.category] = []
        categories[d.category].append(d)

    print("\nBY CATEGORY:")
    for cat, ds_list in sorted(categories.items()):
        impl = len([d for d in ds_list if d.status == "implemented"])
        print(f"  {cat.replace('_', ' ').title():<20} {impl}/{len(ds_list)} implemented")

    # Test results
    tested = [d for d in datasets if d.tested]
    success = [d for d in tested if d.test_result == "success"]

    print("\nTEST RESULTS:")
    print(f"  Tested:      {len(tested)}/{len(datasets)}")
    print(f"  Success:     {len(success)}/{len(tested) if tested else 0}")

    print()


# ==============================================================================
# MAIN
# ==============================================================================


def main() -> None:
    print("=" * 80)
    print("  LNB DATASET CATALOG GENERATOR")
    print("=" * 80)

    all_datasets = []

    # Test implemented datasets
    print("\n" + "=" * 80)
    print("  TESTING IMPLEMENTED DATASETS")
    print("=" * 80)

    all_datasets.append(test_schedule())
    all_datasets.append(test_play_by_play())
    all_datasets.append(test_shots())
    all_datasets.extend(test_lnb_api_endpoints())

    # Document missing datasets
    print("\n" + "=" * 80)
    print("  DOCUMENTING MISSING DATASETS")
    print("=" * 80)
    all_datasets.extend(document_missing_datasets())

    # Generate reports
    print("\n" + "=" * 80)
    print("  GENERATING REPORTS")
    print("=" * 80)

    # Console report
    print_console_report(all_datasets)

    # Markdown report
    md_path = OUTPUT_DIR / "lnb_dataset_catalog.md"
    markdown = generate_markdown_report(all_datasets)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"[SAVED] Markdown catalog: {md_path}")

    # JSON report
    json_path = OUTPUT_DIR / "lnb_dataset_catalog.json"
    catalog = {
        "generated_at": datetime.now().isoformat(),
        "total_datasets": len(all_datasets),
        "by_status": {
            "implemented": len([d for d in all_datasets if d.status == "implemented"]),
            "partial": len([d for d in all_datasets if d.status == "partial"]),
            "missing": len([d for d in all_datasets if d.status == "missing"]),
        },
        "datasets": [asdict(d) for d in all_datasets],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] JSON catalog: {json_path}")

    print("\n" + "=" * 80)
    print("  CATALOG COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
