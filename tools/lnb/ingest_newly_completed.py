#!/usr/bin/env python3
"""Automated ingestion of newly completed LNB games

This script:
1. Checks fixture_uuids_scheduled.json for games that have completed
2. Moves COMPLETE games from scheduled → fixture_uuids_by_season.json
3. Ingests only NEW games (not already processed)
4. Tracks state in _last_ingested.json to avoid re-processing

**Purpose**: Enable "set it and forget it" rolling season coverage

**Usage**:
    # Run daily to catch new completed games
    uv run python tools/lnb/ingest_newly_completed.py

    # Dry run (show what would be ingested)
    uv run python tools/lnb/ingest_newly_completed.py --dry-run

    # Force re-ingest specific UUID
    uv run python tools/lnb/ingest_newly_completed.py --force-uuid <UUID>

**Workflow**:
    1. Load fixture_uuids_scheduled.json
    2. Check each UUID's match_status via LNB API
    3. For COMPLETE games:
       - Move to fixture_uuids_by_season.json
       - Check if already ingested (_last_ingested.json)
       - If new: run pipeline (index → ingest → normalize → validate)
       - Update _last_ingested.json
    4. Save updated files

Created: 2025-11-15
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests

from src.cbb_data.fetchers.lnb_endpoints import LNB_API

# ==============================================================================
# CONFIG
# ==============================================================================

FIXTURE_FILE = Path(__file__).parent / "fixture_uuids_by_season.json"
SCHEDULED_FILE = Path(__file__).parent / "fixture_uuids_scheduled.json"
STATE_FILE = Path(__file__).parent / "_last_ingested.json"

PIPELINE_SCRIPTS = {
    "index": project_root / "tools" / "lnb" / "build_game_index.py",
    "ingest": project_root / "tools" / "lnb" / "bulk_ingest_pbp_shots.py",
    "normalize": project_root / "tools" / "lnb" / "create_normalized_tables.py",
    "validate": project_root / "tools" / "lnb" / "validate_data_consistency.py",
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def get_match_status(uuid: str, known_season: str = None) -> tuple[str, str, str]:
    """Get match status, date, and season from LNB API

    Args:
        uuid: Fixture UUID
        known_season: If provided, use this season instead of inferring

    Returns:
        Tuple of (status, date, season) - e.g. ("COMPLETE", "2025-11-15", "2024-2025")
    """
    url = LNB_API.match_details(uuid)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://lnb.fr/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            match_data = data.get("data", {})

            status = match_data.get("match_status", "UNKNOWN")
            date = match_data.get("match_date", "")

            # Use known season if provided, otherwise infer from date
            if known_season:
                season = known_season
            else:
                # Infer season from date
                season = "UNKNOWN"
                if date:
                    try:
                        year = int(date.split("-")[0])
                        month = int(date.split("-")[1])
                        # LNB season typically runs Sept-June
                        # For dates in Sept-Dec: use current year as start
                        # For dates in Jan-Aug: use previous year as start
                        if month >= 9:  # Sept-Dec
                            season = f"{year}-{year+1}"
                        else:  # Jan-Aug
                            season = f"{year-1}-{year}"
                    except (ValueError, IndexError):
                        season = "UNKNOWN"

            return status, date, season
    except Exception as e:
        print(f"  [ERROR] Failed to get status for {uuid}: {e}")

    return "UNKNOWN", "", "UNKNOWN"


def load_json(file_path: Path) -> dict:
    """Load JSON file with error handling"""
    if not file_path.exists():
        return {}

    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load {file_path}: {e}")
        return {}


def save_json(file_path: Path, data: dict) -> None:
    """Save JSON file with error handling"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  [SAVED] {file_path.name}")
    except Exception as e:
        print(f"  [ERROR] Failed to save {file_path}: {e}")


def run_pipeline_step(script_name: str, season: str, uuid: str = None) -> bool:
    """Run a pipeline script for a specific fixture or season

    Args:
        script_name: One of "index", "ingest", "normalize", "validate"
        season: Season string (e.g., "2024-2025")
        uuid: Optional specific UUID to process

    Returns:
        True if successful, False otherwise
    """
    script_path = PIPELINE_SCRIPTS.get(script_name)

    if not script_path or not script_path.exists():
        print(f"    [ERROR] Pipeline script not found: {script_name}")
        return False

    # Build command
    cmd = [sys.executable, str(script_path)]

    if script_name == "index":
        cmd.extend(["--seasons", season])
        if uuid:
            cmd.extend(["--fixtures", uuid])
    elif script_name == "ingest":
        cmd.extend(["--seasons", season])
        if uuid:
            cmd.extend(["--fixtures", uuid])
    elif script_name == "normalize":
        cmd.extend(["--season", season])
        if uuid:
            cmd.extend(["--fixtures", uuid])
    elif script_name == "validate":
        cmd.extend(["--season", season])

    try:
        print(f"    [RUN] {script_name}: {' '.join(cmd[-4:])}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print(f"    [✓] {script_name} completed")
            return True
        else:
            print(f"    [✗] {script_name} failed:")
            print(f"         {result.stderr[:200]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"    [✗] {script_name} timed out")
        return False
    except Exception as e:
        print(f"    [✗] {script_name} error: {e}")
        return False


# ==============================================================================
# MAIN LOGIC
# ==============================================================================


def ingest_newly_completed(dry_run: bool = False, force_uuid: str = None) -> dict[str, any]:
    """Main ingestion logic

    Args:
        dry_run: If True, only show what would be done
        force_uuid: If provided, force re-ingest this specific UUID

    Returns:
        Dict with statistics about what was processed
    """
    print("=" * 80)
    print("LNB NEWLY COMPLETED GAMES INGESTION")
    print("=" * 80)
    print()

    if dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
        print()

    # Load files
    fixture_data = load_json(FIXTURE_FILE)
    scheduled_data = load_json(SCHEDULED_FILE)
    state = load_json(STATE_FILE)

    # Initialize state if empty
    if not state:
        state = {"last_run": None, "ingested_uuids": [], "total_ingested": 0}

    ingested_set = set(state.get("ingested_uuids", []))

    # Stats tracking
    stats = {
        "checked": 0,
        "newly_complete": 0,
        "moved_to_fixtures": 0,
        "already_ingested": 0,
        "newly_ingested": 0,
        "failed": 0,
        "uuids_processed": [],
    }

    # Process scheduled games
    scheduled_mappings = scheduled_data.get("mappings", {})
    fixture_mappings = fixture_data.get("mappings", {})

    if not scheduled_mappings and not force_uuid:
        print("No scheduled games to check.")
        return stats

    print(f"Checking {sum(len(v) for v in scheduled_mappings.values())} scheduled games...")
    print()

    # Process force UUID if provided
    if force_uuid:
        print(f"[FORCE] Processing UUID: {force_uuid}")
        stats["checked"] = 1

        # Check if UUID exists in fixture or scheduled files to get known season
        known_season = None
        for s, uuids in fixture_mappings.items():
            if force_uuid in uuids:
                known_season = s
                break
        if not known_season:
            for s, uuids in scheduled_mappings.items():
                if force_uuid in uuids:
                    known_season = s
                    break

        status, date, season = get_match_status(force_uuid, known_season=known_season)
        print(f"  Status: {status}, Date: {date}, Season: {season}")

        if status == "COMPLETE":
            if (
                force_uuid not in ingested_set or force_uuid == force_uuid
            ):  # Always process if forced
                print(f"  [INGEST] Running pipeline for {force_uuid}")

                if not dry_run:
                    # Run pipeline
                    success = True
                    for step in ["index", "ingest", "normalize"]:
                        if not run_pipeline_step(step, season, force_uuid):
                            success = False
                            break

                    if success:
                        ingested_set.add(force_uuid)
                        stats["newly_ingested"] += 1
                        stats["uuids_processed"].append(force_uuid)
                    else:
                        stats["failed"] += 1
                else:
                    print(f"    [DRY RUN] Would ingest {force_uuid}")

        return stats

    # Check each scheduled game
    newly_complete = {}  # season -> [uuids]

    for season, uuids in scheduled_mappings.items():
        print(f"\n[{season}] Checking {len(uuids)} games...")

        for uuid in uuids:
            stats["checked"] += 1

            # Pass known season from scheduled file to avoid inference errors
            status, date, actual_season = get_match_status(uuid, known_season=season)

            if status == "COMPLETE":
                print(f"  ✅ {uuid[:35]} → COMPLETE ({date})")
                stats["newly_complete"] += 1

                # Add to newly complete list (use season from scheduled file)
                if season not in newly_complete:
                    newly_complete[season] = []
                newly_complete[season].append(uuid)
            else:
                print(f"  ⏳ {uuid[:35]} → {status}")

    # Move newly complete games to fixture file
    if newly_complete and not dry_run:
        print()
        print("=" * 80)
        print("MOVING COMPLETE GAMES TO FIXTURE FILE")
        print("=" * 80)
        print()

        for season, uuids in newly_complete.items():
            if season not in fixture_mappings:
                fixture_mappings[season] = []

            for uuid in uuids:
                if uuid not in fixture_mappings[season]:
                    fixture_mappings[season].append(uuid)
                    stats["moved_to_fixtures"] += 1
                    print(f"  [MOVE] {uuid} → {season}")

                # Remove from scheduled
                for _sched_season, sched_uuids in scheduled_mappings.items():
                    if uuid in sched_uuids:
                        sched_uuids.remove(uuid)

        # Update metadata
        fixture_data["metadata"]["total_games"] = sum(len(v) for v in fixture_mappings.values())
        fixture_data["metadata"]["last_updated"] = datetime.now().isoformat()

        scheduled_data["metadata"]["total_games"] = sum(len(v) for v in scheduled_mappings.values())

        # Save updated files
        save_json(FIXTURE_FILE, fixture_data)
        save_json(SCHEDULED_FILE, scheduled_data)

    # Ingest newly complete games
    if newly_complete:
        print()
        print("=" * 80)
        print("INGESTING NEW GAMES")
        print("=" * 80)
        print()

        for season, uuids in newly_complete.items():
            print(f"\n[{season}] Processing {len(uuids)} new games...")

            for uuid in uuids:
                if uuid in ingested_set:
                    print(f"  [SKIP] {uuid[:35]} - already ingested")
                    stats["already_ingested"] += 1
                    continue

                print(f"  [INGEST] {uuid}")

                if not dry_run:
                    # Run full pipeline for this fixture
                    success = True
                    for step in ["index", "ingest", "normalize"]:
                        if not run_pipeline_step(step, season, uuid):
                            success = False
                            break

                    if success:
                        ingested_set.add(uuid)
                        stats["newly_ingested"] += 1
                        stats["uuids_processed"].append(uuid)
                    else:
                        stats["failed"] += 1
                else:
                    print("    [DRY RUN] Would run pipeline")

    # Update state file
    if not dry_run:
        state["last_run"] = datetime.now().isoformat()
        state["ingested_uuids"] = list(ingested_set)
        state["total_ingested"] = len(ingested_set)
        save_json(STATE_FILE, state)

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Checked:              {stats['checked']} games")
    print(f"Newly complete:       {stats['newly_complete']} games")
    print(f"Moved to fixtures:    {stats['moved_to_fixtures']} games")
    print(f"Already ingested:     {stats['already_ingested']} games")
    print(f"Newly ingested:       {stats['newly_ingested']} games")
    print(f"Failed:               {stats['failed']} games")
    print()

    if stats["uuids_processed"]:
        print("Processed UUIDs:")
        for uuid in stats["uuids_processed"]:
            print(f"  - {uuid}")

    return stats


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Automated ingestion of newly completed LNB games",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--force-uuid", type=str, help="Force re-ingest specific UUID (ignores ingestion state)"
    )

    args = parser.parse_args()

    stats = ingest_newly_completed(dry_run=args.dry_run, force_uuid=args.force_uuid)

    # Exit code based on results
    if stats["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
