#!/usr/bin/env python3
"""Extract Season Metadata from Atrium Standings API

DISCOVERY SUCCESS! The standings API returns all available seasons with their seasonIds.

This script:
1. Fetches the standings API response
2. Extracts all "Betclic ÉLITE" seasons
3. Maps them to our season format (YYYY-YYYY)
4. Generates updated SEASON_METADATA dict
5. Optionally updates bulk_discover_atrium_api.py

Usage:
    uv run python tools/lnb/extract_season_metadata.py
    uv run python tools/lnb/extract_season_metadata.py --update-file

Created: 2025-11-16
Discovery method: Standings API endpoint probe
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import requests

# ==============================================================================
# CONFIG
# ==============================================================================

STANDINGS_API = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/standings"
COMPETITION_ID = "5b7857d9-0cbc-11ed-96a7-458862b58368"

BULK_DISCOVER_FILE = Path("tools/lnb/bulk_discover_atrium_api.py")
TIMEOUT = 10

# ==============================================================================
# SEASON EXTRACTION
# ==============================================================================


def extract_seasons_from_standings_api() -> dict[str, dict]:
    """Extract all Betclic ÉLITE seasons from standings API

    Returns:
        Dict mapping season string (YYYY-YYYY) to season metadata
    """
    print(f"\n{'='*80}")
    print("  EXTRACTING SEASON METADATA FROM STANDINGS API")
    print(f"{'='*80}\n")

    # Fetch standings data
    url = f"{STANDINGS_API}?competitionId={COMPETITION_ID}"
    print(f"Fetching: {url}")

    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch standings API: {response.status_code}")

    data = response.json()
    seasons_data = data.get("data", {}).get("seasons", {})

    # The seasons data is a dict with "competitions" and "seasons" keys
    if isinstance(seasons_data, dict):
        seasons_array = seasons_data.get("seasons", [])
    else:
        seasons_array = seasons_data if isinstance(seasons_data, list) else []

    print(f"Total seasons in API: {len(seasons_array)}\n")

    # Filter for main Betclic ÉLITE seasons (not playoffs, espoirs, etc.)
    elite_seasons = []
    for season in seasons_array:
        if not isinstance(season, dict):
            continue
        name = season.get("nameLocal", "")
        # Match "Betclic ÉLITE YYYY" format (not playoffs, play-in, etc.)
        if re.match(r"^Betclic [ÉE]LITE \d{4}$", name):
            elite_seasons.append(season)

    print(f"Betclic ÉLITE main seasons found: {len(elite_seasons)}\n")

    # Map to our season format
    season_metadata = {}

    for season in elite_seasons:
        year = season["year"]
        season_id = season["seasonId"]
        comp_id = season["competitionId"]
        name = season["nameLocal"]

        # Map year to season string
        # "Betclic ÉLITE 2023" = 2023-2024 season
        # "Betclic ÉLITE 2024" = 2024-2025 season
        # "Betclic ÉLITE 2025" = 2025-2026 season
        season_str = f"{year}-{year+1}"

        season_metadata[season_str] = {
            "competition_id": comp_id,
            "season_id": season_id,
            "season_name": name,
            "source": "Extracted from standings API",
        }

        print(f"  {season_str}:")
        print(f"    name: {name}")
        print(f"    seasonId: {season_id}")
        print(f"    competitionId: {comp_id}")
        print()

    return season_metadata


def generate_season_metadata_code(metadata: dict[str, dict]) -> str:
    """Generate Python code for SEASON_METADATA dict

    Args:
        metadata: Dict mapping season -> metadata

    Returns:
        Python code string
    """
    lines = ["SEASON_METADATA = {"]

    for season_str in sorted(metadata.keys()):
        meta = metadata[season_str]
        lines.append(f'    "{season_str}": {{')
        lines.append(f'        "competition_id": "{meta["competition_id"]}",')
        lines.append(f'        "season_id": "{meta["season_id"]}",')
        lines.append(f'        "season_name": "{meta["season_name"]}",')
        lines.append(f'        "source": "{meta["source"]}",')
        lines.append("    },")

    lines.append("}")

    return "\n".join(lines)


def update_bulk_discover_file(metadata: dict[str, dict], dry_run: bool = True) -> None:
    """Update SEASON_METADATA in bulk_discover_atrium_api.py

    Args:
        metadata: New season metadata
        dry_run: If True, only show what would be changed
    """
    if not BULK_DISCOVER_FILE.exists():
        print(f"ERROR: File not found: {BULK_DISCOVER_FILE}")
        return

    # Read current file
    with open(BULK_DISCOVER_FILE, encoding="utf-8") as f:
        content = f.read()

    # Find SEASON_METADATA section
    # Look for pattern: SEASON_METADATA = { ... }
    pattern = r"SEASON_METADATA = \{[^}]*\}"

    # Generate new code
    new_code = generate_season_metadata_code(metadata)

    # Check if pattern exists
    if not re.search(pattern, content, re.DOTALL):
        print("ERROR: Could not find SEASON_METADATA dict in file")
        print("Looking for pattern: SEASON_METADATA = { ... }")
        return

    # Replace
    new_content = re.sub(pattern, new_code, content, flags=re.DOTALL)

    if dry_run:
        print(f"\n{'='*80}")
        print("  DRY RUN - Would update bulk_discover_atrium_api.py")
        print(f"{'='*80}\n")
        print("New SEASON_METADATA:")
        print(new_code)
        print("\nTo apply changes, run with --update-file")
    else:
        # Write back
        with open(BULK_DISCOVER_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"\n{'='*80}")
        print(f"  SUCCESS - Updated {BULK_DISCOVER_FILE}")
        print(f"{'='*80}\n")
        print(f"Added {len(metadata)} seasons to SEASON_METADATA")


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Extract season metadata from Atrium standings API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--update-file",
        action="store_true",
        help="Update bulk_discover_atrium_api.py with extracted metadata",
    )
    args = parser.parse_args()

    try:
        # Extract seasons
        metadata = extract_seasons_from_standings_api()

        if not metadata:
            print("ERROR: No seasons found!")
            return

        # Generate code
        print(f"\n{'='*80}")
        print("  GENERATED SEASON_METADATA")
        print(f"{'='*80}\n")
        code = generate_season_metadata_code(metadata)
        print(code)

        # Update file
        if args.update_file:
            update_bulk_discover_file(metadata, dry_run=False)
        else:
            update_bulk_discover_file(metadata, dry_run=True)

        print(f"\n{'='*80}")
        print("  NEXT STEPS")
        print(f"{'='*80}\n")
        print("1. Review the generated SEASON_METADATA above")
        print("2. Run with --update-file to apply changes")
        print("3. Test discovery:")
        print(
            "   uv run python tools/lnb/bulk_discover_atrium_api.py --seasons 2023-2024 2024-2025"
        )
        print()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
