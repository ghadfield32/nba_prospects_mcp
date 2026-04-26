#!/usr/bin/env python
"""Lane 0: Initialize Observability Infrastructure

Creates the directory structure and manifest files needed for
tracking all data pipeline jobs across leagues.

Directories:
- data/_logs/html_snapshots/   - Raw HTML for debugging scrapers
- data/_logs/discovery/        - Discovery script outputs
- data/_manifests/             - Append-only job manifests
- data/_validation/            - Validation reports per run

Usage:
    python scripts/init_observability.py
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Constants
DATA_DIR = Path("data")

# Directories to create
OBSERVABILITY_DIRS = [
    DATA_DIR / "_logs" / "html_snapshots",
    DATA_DIR / "_logs" / "discovery",
    DATA_DIR / "_manifests",
    DATA_DIR / "_validation",
    DATA_DIR / "_reports",
]

# Manifest schemas
MANIFEST_SCHEMAS = {
    "game_indexes": [
        "timestamp",
        "league",
        "season",
        "artifact_type",
        "row_count",
        "status",
        "source_file",
        "job_id",
    ],
    "canonical": [
        "timestamp",
        "league",
        "season",
        "artifact_type",
        "row_count",
        "status",
        "source_file",
        "job_id",
    ],
    "player_metadata": [
        "timestamp",
        "source",
        "players_added",
        "players_updated",
        "status",
        "job_id",
    ],
    "crosswalk": [
        "timestamp",
        "entries_added",
        "entries_resolved",
        "collisions",
        "status",
        "job_id",
    ],
}


def create_directories() -> None:
    """Create all observability directories."""
    print("Creating observability directories...")
    for dir_path in OBSERVABILITY_DIRS:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {dir_path}")


def create_manifest_files() -> None:
    """Create manifest CSV files with headers."""
    print("\nCreating manifest files...")
    manifests_dir = DATA_DIR / "_manifests"

    for manifest_name, columns in MANIFEST_SCHEMAS.items():
        manifest_path = manifests_dir / f"{manifest_name}_manifest.csv"
        if not manifest_path.exists():
            with open(manifest_path, "w") as f:
                f.write(",".join(columns) + "\n")
            print(f"  Created: {manifest_path}")
        else:
            print(f"  Exists: {manifest_path}")


def create_league_status_file() -> None:
    """Create initial league status tracking file."""
    print("\nCreating league status file...")
    status_path = DATA_DIR / "_reports" / "league_status.json"

    if not status_path.exists():
        # Define all 23 leagues with their current status
        league_status = {
            "timestamp": datetime.now(UTC).isoformat(),
            "leagues": {
                # TIER 0: Core Feeders
                "NCAA-MBB": {
                    "tier": 0,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "NCAA-WBB": {
                    "tier": 0,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "G-League": {
                    "tier": 0,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "WNBA": {"tier": 0, "status": "WIRED", "game_index": "API", "canonical": "MISSING"},
                "EuroLeague": {
                    "tier": 0,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "EuroCup": {
                    "tier": 0,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                # TIER 1: Secondary Feeders
                "NBL": {"tier": 1, "status": "ACTIVE", "game_index": 7900, "canonical": 34124},
                "LNB_PROA": {
                    "tier": 1,
                    "status": "WIRED",
                    "game_index": 254,
                    "canonical": "MISSING",
                },
                "ACB": {
                    "tier": 1,
                    "status": "WIRED",
                    "game_index": "MISSING",
                    "canonical": "MISSING",
                },
                "OTE": {
                    "tier": 1,
                    "status": "BROKEN",
                    "game_index": 75,
                    "canonical": "MISSING",
                    "note": "Placeholder data",
                },
                "CEBL": {
                    "tier": 1,
                    "status": "WIRED",
                    "game_index": "MISSING",
                    "canonical": "MISSING",
                },
                "NZ-NBL": {
                    "tier": 1,
                    "status": "WIRED",
                    "game_index": "MISSING",
                    "canonical": "MISSING",
                },
                # TIER 2: FIBA HTML Cluster
                "BCL": {
                    "tier": 2,
                    "status": "PLACEHOLDER",
                    "game_index": 3,
                    "canonical": "MISSING",
                },
                "BAL": {
                    "tier": 2,
                    "status": "PLACEHOLDER",
                    "game_index": 3,
                    "canonical": "MISSING",
                },
                "LKL": {"tier": 2, "status": "WIRED", "game_index": 3, "canonical": "MISSING"},
                "ABA": {"tier": 2, "status": "WIRED", "game_index": 3, "canonical": "MISSING"},
                # TIER 3: Development Leagues
                "NJCAA": {
                    "tier": 3,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "NAIA": {"tier": 3, "status": "WIRED", "game_index": "API", "canonical": "MISSING"},
                "U-SPORTS": {
                    "tier": 3,
                    "status": "WIRED",
                    "game_index": "API",
                    "canonical": "MISSING",
                },
                "CCAA": {"tier": 3, "status": "WIRED", "game_index": "API", "canonical": "MISSING"},
                # TIER 4: LNB France Multi-League
                "LNB_ELITE2": {
                    "tier": 4,
                    "status": "WIRED",
                    "game_index": 2,
                    "canonical": "MISSING",
                },
                "LNB_ESPOIRS_ELITE": {
                    "tier": 4,
                    "status": "WIRED",
                    "game_index": 1,
                    "canonical": "MISSING",
                },
                "LNB_ESPOIRS_PROB": {
                    "tier": 4,
                    "status": "WIRED",
                    "game_index": 0,
                    "canonical": "MISSING",
                },
            },
            "validation_players": {
                "NBL": ["Alex Sarr", "Josh Giddey", "LaMelo Ball", "Dyson Daniels"],
                "OTE": ["Amen Thompson", "Ausar Thompson", "Scoot Henderson"],
                "G-League": ["Jalen Green", "Jonathan Kuminga", "MarJon Beauchamp"],
                "NCAA-MBB": ["Chet Holmgren", "Paolo Banchero", "Zach Edey"],
                "EuroLeague": ["Luka Doncic", "Nikola Jokic"],
            },
        }

        with open(status_path, "w") as f:
            json.dump(league_status, f, indent=2)
        print(f"  Created: {status_path}")
    else:
        print(f"  Exists: {status_path}")


def append_manifest_entry(
    manifest_name: str,
    entry: dict,
) -> None:
    """Append an entry to a manifest file."""
    manifest_path = DATA_DIR / "_manifests" / f"{manifest_name}_manifest.csv"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    columns = MANIFEST_SCHEMAS.get(manifest_name)
    if not columns:
        raise ValueError(f"Unknown manifest: {manifest_name}")

    # Build row from entry
    row_values = [str(entry.get(col, "")) for col in columns]
    row = ",".join(row_values) + "\n"

    with open(manifest_path, "a") as f:
        f.write(row)


def main():
    print("=" * 70)
    print("LANE 0: OBSERVABILITY INFRASTRUCTURE SETUP")
    print("=" * 70)
    print()

    create_directories()
    create_manifest_files()
    create_league_status_file()

    print()
    print("=" * 70)
    print("OBSERVABILITY SETUP COMPLETE")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Run Lane 1: python scripts/enrich_game_indexes.py --league OTE --debug")
    print("  2. Run Lane 2: python scripts/discover_fiba_games.py --league BCL")
    print("  3. Run Lane 3: python scripts/validate_game_indexes.py --league NBL")
    print("  4. Run Lane 4: python scripts/enrich_player_metadata.py --league NBL")
    print("  5. Run Lane 5: python scripts/materialize_api_leagues.py --league G-League")


if __name__ == "__main__":
    main()
