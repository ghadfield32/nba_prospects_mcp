#!/usr/bin/env python3
"""Programmatic UUID Discovery from LNB Calendar API

This script automatically discovers fixture UUIDs by querying the LNB calendar API.
Eliminates manual URL collection from the LNB website.

**Purpose**: Automated, scalable UUID discovery for all seasons

**Features**:
- Fetches all matches from LNB calendar API
- Filters by competition (Pro A only by default)
- Groups by season based on match_date
- Separates COMPLETE (have data) from SCHEDULED (future) games
- Updates fixture_uuids_by_season.json and fixture_uuids_scheduled.json

**Usage**:
    # Discover all seasons
    uv run python tools/lnb/discover_from_calendar.py

    # Discover specific season only
    uv run python tools/lnb/discover_from_calendar.py --season 2024-2025

    # Dry run (show what would be discovered without saving)
    uv run python tools/lnb/discover_from_calendar.py --dry-run

    # Include all competitions (not just Pro A)
    uv run python tools/lnb/discover_from_calendar.py --all-competitions

**Output**:
    - fixture_uuids_by_season.json: COMPLETE games with PBP data
    - fixture_uuids_scheduled.json: SCHEDULED games (future, no data yet)
    - Discovery report in tools/lnb/reports/

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers.lnb_endpoints import LNB_API

# ==============================================================================
# CONFIG
# ==============================================================================

FIXTURE_FILE = Path(__file__).parent / "fixture_uuids_by_season.json"
SCHEDULED_FILE = Path(__file__).parent / "fixture_uuids_scheduled.json"
REPORTS_DIR = Path(__file__).parent / "reports"

DEFAULT_COMPETITION = "PROA"  # Pro A only
PRO_A_DIVISION_ID = 1  # Division external ID for Pro A

# ==============================================================================
# API FETCHING
# ==============================================================================


def fetch_calendar() -> list[dict]:
    """Fetch all matches from LNB calendar API

    Returns:
        List of match dictionaries with UUID, date, status, competition info
    """
    url = LNB_API.CALENDAR_BY_DIVISION

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    try:
        print("[FETCH] Querying LNB calendar API...")
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            matches = data.get("data", [])
            print(f"  ✅ Retrieved {len(matches)} matches")
            return matches
        else:
            print(f"  ❌ HTTP {response.status_code}")
            return []

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


# ==============================================================================
# UUID PROCESSING
# ==============================================================================


def infer_season_from_date(date_str: str) -> str:
    """Infer season from match date

    Args:
        date_str: Date string (YYYY-MM-DD)

    Returns:
        Season string (e.g., "2024-2025")
    """
    try:
        year = int(date_str.split("-")[0])
        month = int(date_str.split("-")[1])

        # LNB season runs Sept-June
        if month >= 9:  # Sept-Dec
            return f"{year}-{year+1}"
        else:  # Jan-Aug
            return f"{year-1}-{year}"
    except (ValueError, IndexError):
        return "UNKNOWN"


def process_calendar_matches(
    matches: list[dict], filter_competition: str = None, filter_season: str = None
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Process calendar matches into COMPLETE and SCHEDULED groups

    Args:
        matches: List of match dictionaries from API
        filter_competition: If provided, only include this competition (e.g., "PROA")
        filter_season: If provided, only include this season (e.g., "2024-2025")

    Returns:
        Tuple of (complete_mappings, scheduled_mappings)
        Each is a dict mapping season -> list of UUIDs
    """
    print()
    print("=" * 80)
    print("PROCESSING MATCHES")
    print("=" * 80)
    print()

    complete_by_season = defaultdict(list)
    scheduled_by_season = defaultdict(list)

    stats = {
        "total": len(matches),
        "filtered_competition": 0,
        "filtered_season": 0,
        "complete": 0,
        "scheduled": 0,
        "other_status": 0,
        "missing_uuid": 0,
        "missing_date": 0,
    }

    for match in matches:
        uuid = match.get("match_id")
        date = match.get("match_date")
        status = match.get("match_status", "UNKNOWN")
        competition = match.get("competition_abbrev", "")
        division_id = match.get("division_external_id")

        # Skip if missing UUID
        if not uuid:
            stats["missing_uuid"] += 1
            continue

        # Skip if missing date (can't determine season)
        if not date:
            stats["missing_date"] += 1
            continue

        # Filter by competition if specified
        if filter_competition:
            if competition != filter_competition or division_id != PRO_A_DIVISION_ID:
                stats["filtered_competition"] += 1
                continue

        # Infer season from date
        season = infer_season_from_date(date)

        # Filter by season if specified
        if filter_season and season != filter_season:
            stats["filtered_season"] += 1
            continue

        # Group by status
        if status == "COMPLETE":
            complete_by_season[season].append(uuid)
            stats["complete"] += 1
        elif status == "SCHEDULED":
            scheduled_by_season[season].append(uuid)
            stats["scheduled"] += 1
        else:
            stats["other_status"] += 1

    # Print statistics
    print(f"Total matches from API:        {stats['total']}")
    print(f"Filtered (competition):        {stats['filtered_competition']}")
    print(f"Filtered (season):             {stats['filtered_season']}")
    print(f"Missing UUID:                  {stats['missing_uuid']}")
    print(f"Missing date:                  {stats['missing_date']}")
    print()
    print(f"COMPLETE games (have data):    {stats['complete']}")
    print(f"SCHEDULED games (future):      {stats['scheduled']}")
    print(f"Other status:                  {stats['other_status']}")
    print()

    return dict(complete_by_season), dict(scheduled_by_season)


# ==============================================================================
# FILE MANAGEMENT
# ==============================================================================


def load_existing_file(file_path: Path) -> dict[str, list[str]]:
    """Load existing UUID mappings from file

    Args:
        file_path: Path to JSON file

    Returns:
        Dict mapping season -> list of UUIDs
    """
    if not file_path.exists():
        return {}

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("mappings", {})
    except Exception as e:
        print(f"[WARN] Error loading {file_path.name}: {e}")
        return {}


def save_uuid_file(
    file_path: Path, mappings: dict[str, list[str]], note: str, dry_run: bool = False
) -> None:
    """Save UUID mappings to file

    Args:
        file_path: Path to save JSON file
        mappings: Dict mapping season -> list of UUIDs
        note: Description note for metadata
        dry_run: If True, don't actually save
    """
    # Calculate totals
    total_games = sum(len(uuids) for uuids in mappings.values())
    total_seasons = len(mappings)

    # Build JSON structure
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_seasons": total_seasons,
            "total_games": total_games,
            "note": note,
            "source": "LNB Calendar API (CALENDAR_BY_DIVISION)",
            "discovery_method": "Automated via discover_from_calendar.py",
        },
        "mappings": {season: sorted(set(uuids)) for season, uuids in sorted(mappings.items())},
    }

    if dry_run:
        print(f"[DRY RUN] Would save {total_games} games to {file_path.name}")
        return

    # Save to file
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"  ✅ Saved {total_games} games to {file_path.name}")
    except Exception as e:
        print(f"  ❌ Error saving {file_path.name}: {e}")


def generate_discovery_report(
    complete_mappings: dict[str, list[str]],
    scheduled_mappings: dict[str, list[str]],
    dry_run: bool = False,
) -> None:
    """Generate discovery report

    Args:
        complete_mappings: COMPLETE games by season
        scheduled_mappings: SCHEDULED games by season
        dry_run: If True, don't save report
    """
    print()
    print("=" * 80)
    print("DISCOVERY SUMMARY")
    print("=" * 80)
    print()

    print("COMPLETE GAMES (have PBP data):")
    print("-" * 80)
    for season in sorted(complete_mappings.keys()):
        count = len(complete_mappings[season])
        print(f"  {season:15s} {count:4d} games")
    total_complete = sum(len(v) for v in complete_mappings.values())
    print(f"  {'TOTAL':15s} {total_complete:4d} games")
    print()

    print("SCHEDULED GAMES (future, no data yet):")
    print("-" * 80)
    for season in sorted(scheduled_mappings.keys()):
        count = len(scheduled_mappings[season])
        print(f"  {season:15s} {count:4d} games")
    total_scheduled = sum(len(v) for v in scheduled_mappings.values())
    print(f"  {'TOTAL':15s} {total_scheduled:4d} games")
    print()

    # Save detailed report
    if not dry_run:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = (
            REPORTS_DIR / f"uuid_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_complete": total_complete,
            "total_scheduled": total_scheduled,
            "complete_by_season": {s: len(v) for s, v in complete_mappings.items()},
            "scheduled_by_season": {s: len(v) for s, v in scheduled_mappings.items()},
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"[SAVED] {report_file}")
        print()


# ==============================================================================
# MAIN LOGIC
# ==============================================================================


def discover_uuids(
    filter_season: str = None,
    all_competitions: bool = False,
    dry_run: bool = False,
    merge: bool = True,
) -> None:
    """Main UUID discovery logic

    Args:
        filter_season: If provided, only discover this season (e.g., "2024-2025")
        all_competitions: If True, include all competitions (not just Pro A)
        dry_run: If True, show what would be done without saving files
        merge: If True, merge with existing UUIDs (default). If False, replace entirely.
    """
    print("=" * 80)
    print("LNB UUID DISCOVERY FROM CALENDAR API")
    print("=" * 80)
    print()

    if dry_run:
        print("⚠️  DRY RUN MODE - No files will be modified")
        print()

    if filter_season:
        print(f"🔍 Filtering: {filter_season} only")
        print()

    if all_competitions:
        print("🔍 Including: All competitions")
    else:
        print(f"🔍 Filtering: {DEFAULT_COMPETITION} (Pro A) only")
    print()

    # Fetch calendar
    matches = fetch_calendar()

    if not matches:
        print("[ERROR] No matches retrieved from API")
        return

    # Process matches
    complete_mappings, scheduled_mappings = process_calendar_matches(
        matches,
        filter_competition=None if all_competitions else DEFAULT_COMPETITION,
        filter_season=filter_season,
    )

    # Merge with existing if requested
    if merge:
        print("=" * 80)
        print("MERGING WITH EXISTING UUIDS")
        print("=" * 80)
        print()

        existing_complete = load_existing_file(FIXTURE_FILE)
        existing_scheduled = load_existing_file(SCHEDULED_FILE)

        # Merge (new discoveries take precedence)
        for season, uuids in existing_complete.items():
            if season not in complete_mappings:
                complete_mappings[season] = []
            complete_mappings[season].extend(uuids)
            complete_mappings[season] = sorted(set(complete_mappings[season]))

        for season, uuids in existing_scheduled.items():
            if season not in scheduled_mappings:
                scheduled_mappings[season] = []
            scheduled_mappings[season].extend(uuids)
            scheduled_mappings[season] = sorted(set(scheduled_mappings[season]))

        print("✅ Merged with existing UUIDs")
        print()

    # Save files
    print("=" * 80)
    print("SAVING UUID FILES")
    print("=" * 80)
    print()

    save_uuid_file(
        FIXTURE_FILE,
        complete_mappings,
        "Contains only COMPLETE games with confirmed PBP/shot data. SCHEDULED games excluded until played.",
        dry_run=dry_run,
    )

    save_uuid_file(
        SCHEDULED_FILE,
        scheduled_mappings,
        "These are SCHEDULED games (not yet played). Check back after match dates for PBP data.",
        dry_run=dry_run,
    )

    # Generate report
    generate_discovery_report(complete_mappings, scheduled_mappings, dry_run=dry_run)

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. ✅ Run coverage report to verify discovered UUIDs:")
    print("   uv run python tools/lnb/stress_test_coverage.py --report")
    print()
    print("2. 📥 Ingest newly discovered COMPLETE games:")
    print("   uv run python tools/lnb/bulk_ingest_pbp_shots.py")
    print()
    print("3. 🔄 Set up daily automation to check for newly completed games:")
    print("   uv run python tools/lnb/ingest_newly_completed.py")
    print()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Programmatic UUID discovery from LNB Calendar API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--season", type=str, default=None, help='Discover specific season only (e.g., "2024-2025")'
    )

    parser.add_argument(
        "--all-competitions",
        action="store_true",
        help="Include all competitions (default: Pro A only)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be discovered without saving files"
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing UUIDs instead of merging (default: merge)",
    )

    args = parser.parse_args()

    discover_uuids(
        filter_season=args.season,
        all_competitions=args.all_competitions,
        dry_run=args.dry_run,
        merge=not args.replace,
    )


if __name__ == "__main__":
    main()
