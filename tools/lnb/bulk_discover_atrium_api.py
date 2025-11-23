#!/usr/bin/env python3
"""Bulk Fixture UUID Discovery via Atrium Sports API

This script uses the Atrium Sports API fixtures endpoint to automatically
discover ALL fixture UUIDs for historical LNB Pro A seasons.

Discovery: Endpoint found via systematic probe (probe_atrium_endpoints.py)
Endpoint: /v1/embed/12/fixtures?competitionId=...&seasonId=...
Auth: NOT REQUIRED (Atrium API is public!)

This is the FASTEST method for bulk discovery:
- 300+ fixtures discovered in <1 second per season
- No browser cookies needed
- No manual URL collection
- Returns actual fixture UUIDs (not external IDs)

Workflow:
    1. Get competitionId + seasonId for target season
    2. Call Atrium fixtures endpoint
    3. Extract all fixtureId values
    4. Save to fixture_uuids_by_season.json
    5. Feed to existing pipeline (build_game_index.py, etc.)

Usage:
    # Discover all 2022-23 fixtures
    uv run python tools/lnb/bulk_discover_atrium_api.py --seasons 2022-2023

    # Discover multiple seasons
    uv run python tools/lnb/bulk_discover_atrium_api.py \
        --seasons 2022-2023 2023-2024 2024-2025

    # Dry run (don't save)
    uv run python tools/lnb/bulk_discover_atrium_api.py \
        --seasons 2022-2023 --dry-run

Prerequisite:
    - Seed fixture from target season to get competitionId/seasonId
    - OR: Use known IDs from SEASON_METADATA dict below

Created: 2025-11-16
Endpoint discovered: 2025-11-16 via probe_atrium_endpoints.py
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIG
# ==============================================================================

TOOLS_DIR = Path("tools/lnb")
UUID_MAPPING_FILE = TOOLS_DIR / "fixture_uuids_by_season.json"

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
ATRIUM_FIXTURES_ENDPOINT = "/v1/embed/12/fixtures"
ATRIUM_FIXTURE_DETAIL_ENDPOINT = "/v1/embed/12/fixture_detail"

TIMEOUT = 15  # seconds

# ==============================================================================
# SEASON METADATA
# ==============================================================================

# UPDATED 2025-11-18: Import centralized league configuration
# Now supports all 4 LNB leagues via lnb_league_config module
#
# Leagues available:
# - Betclic ELITE (formerly Pro A) - Top-tier professional, 16 teams
# - ELITE 2 (formerly Pro B) - Second-tier professional, 20 teams
# - Espoirs ELITE - U21 top-tier youth league
# - Espoirs PROB - U21 second-tier youth league

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers.lnb_league_config import (
    BETCLIC_ELITE_SEASONS,
    ELITE_2_SEASONS,
    ESPOIRS_ELITE_SEASONS,
    ESPOIRS_PROB_SEASONS,  # Default to Betclic ELITE for backward compat
)

# Combine all league seasons into unified lookup dict
# This allows discovery for any season from any league
SEASON_METADATA = {}
for seasons_dict in [
    BETCLIC_ELITE_SEASONS,
    ELITE_2_SEASONS,
    ESPOIRS_ELITE_SEASONS,
    ESPOIRS_PROB_SEASONS,
]:
    for season_key, meta in seasons_dict.items():
        # Preserve competition_name from config, add "season_name" alias for compatibility
        if season_key not in SEASON_METADATA:
            meta_copy = dict(meta)  # Create copy to avoid modifying source
            meta_copy["season_name"] = meta.get("competition_name", "Unknown")
            SEASON_METADATA[season_key] = meta_copy


# ==============================================================================
# ATRIUM API FUNCTIONS
# ==============================================================================


def get_season_metadata_from_seed_fixture(fixture_uuid: str) -> dict:
    """Extract competitionId and seasonId from a seed fixture.

    Args:
        fixture_uuid: Any fixture UUID from the target season

    Returns:
        Dict with competition_id, season_id, season_name

    Raises:
        Exception: If API call fails or response invalid
    """
    print(f"  [SEED] Fetching metadata from fixture {fixture_uuid[:8]}...")

    url = f"{ATRIUM_API_BASE}{ATRIUM_FIXTURE_DETAIL_ENDPOINT}"
    params = {"fixtureId": fixture_uuid}

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        # Extract IDs from response
        # Structure: {data: {banner: {competition: {id: ...}, season: {id: ..., name: ...}}}}
        banner = data.get("data", {}).get("banner", {})
        competition = banner.get("competition", {})
        season = banner.get("season", {})

        competition_id = competition.get("id")
        season_id = season.get("id")
        season_name = season.get("name")

        if not competition_id or not season_id:
            raise ValueError("Could not extract competitionId or seasonId from fixture response")

        print(f"  [OK] Competition: {competition.get('name')} ({competition_id[:8]}...)")
        print(f"  [OK] Season: {season_name} ({season_id[:8]}...)")

        return {
            "competition_id": competition_id,
            "season_id": season_id,
            "season_name": season_name,
        }

    except Exception as e:
        print(f"  [ERROR] Failed to fetch seed fixture: {e}")
        raise


def discover_fixtures_via_atrium(
    competition_id: str,
    season_id: str,
    season_name: str | None = None,
) -> list[str]:
    """Discover all fixture UUIDs for a season using Atrium API.

    Args:
        competition_id: Competition UUID (from fixture_detail)
        season_id: Season UUID (from fixture_detail)
        season_name: Optional season name for logging

    Returns:
        List of fixture UUIDs

    Raises:
        Exception: If API call fails or response invalid
    """
    season_label = season_name if season_name else season_id[:8]
    print(f"\n[DISCOVERING] {season_label} via Atrium API...")

    url = f"{ATRIUM_API_BASE}{ATRIUM_FIXTURES_ENDPOINT}"
    params = {
        "competitionId": competition_id,
        "seasonId": season_id,
    }

    try:
        print(f"  [API] GET {url}")
        print(f"        competitionId={competition_id[:8]}...")
        print(f"        seasonId={season_id[:8]}...")

        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        # Extract fixtures array
        # Structure: {data: {fixtures: [{fixtureId: ..., name: ..., ...}, ...]}}
        fixtures = data.get("data", {}).get("fixtures", [])

        if not isinstance(fixtures, list):
            raise ValueError(f"Expected fixtures array, got {type(fixtures)}")

        # Extract fixtureId from each fixture, filtering out placeholders
        fixture_uuids = []
        filtered_count = 0

        for fixture in fixtures:
            fixture_id = fixture.get("fixtureId")
            if not fixture_id:
                continue

            # Quality filter: Skip obvious placeholder/test fixtures
            # Criteria based on debugging ÉLITE 2 historical seasons:
            # 1. Both competitors are "Unknown"
            # 2. Status is "IF_NEEDED" AND no fixture name/date
            # 3. Fixture name contains "Test"
            competitors = fixture.get("competitors", [])
            status_value = fixture.get("status", {}).get("value")
            fixture_name = fixture.get("name")

            # Check if both competitors are unknown
            if len(competitors) == 2:
                comp1_name = competitors[0].get("name", "")
                comp2_name = competitors[1].get("name", "")
                if comp1_name == "Unknown" and comp2_name == "Unknown":
                    filtered_count += 1
                    continue

            # Check for conditional playoff game without proper data
            if status_value == "IF_NEEDED" and not fixture_name:
                filtered_count += 1
                continue

            # Check for test fixtures
            if fixture_name and "test" in fixture_name.lower():
                filtered_count += 1
                continue

            fixture_uuids.append(fixture_id)

        print(f"  [SUCCESS] Discovered {len(fixture_uuids)} fixtures")
        if filtered_count > 0:
            print(f"  [FILTERED] Skipped {filtered_count} placeholder/test fixtures")

        if len(fixture_uuids) > 0:
            print(f"  [SAMPLE] First: {fixture_uuids[0]}")
            print(f"  [SAMPLE] Last:  {fixture_uuids[-1]}")

        return fixture_uuids

    except requests.Timeout:
        print(f"  [ERROR] Request timeout after {TIMEOUT}s")
        raise

    except requests.RequestException as e:
        print(f"  [ERROR] API request failed: {e}")
        raise

    except (KeyError, ValueError) as e:
        print(f"  [ERROR] Failed to parse response: {e}")
        raise


def discover_season_fixtures(
    season_str: str,
    seed_fixture_uuid: str | None = None,
) -> list[str]:
    """Discover all fixtures for a season.

    Args:
        season_str: Season in format "YYYY-YYYY" (e.g., "2022-2023")
        seed_fixture_uuid: Optional seed fixture to extract metadata from
                          If not provided, uses SEASON_METADATA dict

    Returns:
        List of fixture UUIDs

    Raises:
        Exception: If season metadata not found and no seed provided
    """
    print(f"\n{'='*80}")
    print(f"  SEASON: {season_str}")
    print(f"{'='*80}")

    # Get season metadata
    if seed_fixture_uuid:
        print("[MODE] Seed fixture discovery")
        metadata = get_season_metadata_from_seed_fixture(seed_fixture_uuid)
    elif season_str in SEASON_METADATA:
        print("[MODE] Using known metadata")
        metadata = SEASON_METADATA[season_str]
        print(f"  [INFO] Source: {metadata.get('source', 'Unknown')}")
    else:
        raise ValueError(
            f"Season {season_str} not found in SEASON_METADATA.\n"
            f"Either:\n"
            f"  1. Add metadata to SEASON_METADATA dict in this script\n"
            f"  2. Provide --seed-fixture UUID from that season\n"
            f"\nAvailable seasons: {list(SEASON_METADATA.keys())}"
        )

    # Discover fixtures
    fixtures = discover_fixtures_via_atrium(
        competition_id=metadata["competition_id"],
        season_id=metadata["season_id"],
        season_name=metadata.get("season_name"),
    )

    return fixtures


# ==============================================================================
# UUID MAPPING PERSISTENCE
# ==============================================================================


def load_existing_mappings() -> dict:
    """Load existing UUID mappings from JSON file."""
    if not UUID_MAPPING_FILE.exists():
        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_seasons": 0,
                "total_games": 0,
                "discovery_method": "atrium_api",
            },
            "mappings": {},
        }

    with open(UUID_MAPPING_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_uuid_mappings(data: dict) -> None:
    """Save UUID mappings to JSON file."""
    # Update metadata
    data["metadata"]["generated_at"] = datetime.now().isoformat()
    data["metadata"]["total_seasons"] = len([k for k in data["mappings"] if k != "current_round"])
    data["metadata"]["total_games"] = sum(
        len(v) for k, v in data["mappings"].items() if k != "current_round"
    )
    data["metadata"]["discovery_method"] = "atrium_api"

    # Ensure directory exists
    UUID_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically
    with open(UUID_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n[SAVED] {UUID_MAPPING_FILE}")
    print(f"        Seasons: {data['metadata']['total_seasons']}")
    print(f"        Total games: {data['metadata']['total_games']}")


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Bulk discover fixture UUIDs using Atrium Sports API for all LNB leagues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover 2022-23 season (all leagues with that season)
    python tools/lnb/bulk_discover_atrium_api.py --seasons 2022-2023

    # Discover specific league only
    python tools/lnb/bulk_discover_atrium_api.py --leagues elite_2 --seasons 2024-2025

    # Discover multiple leagues
    python tools/lnb/bulk_discover_atrium_api.py \
        --leagues betclic_elite elite_2 espoirs_elite \
        --seasons 2024-2025 2023-2024

    # Discover using seed fixture (for unknown league/season)
    python tools/lnb/bulk_discover_atrium_api.py \
        --seasons 2023-2024 \
        --seed-fixture 3fcea9a1-1f10-11ee-a687-db190750bdda

    # Dry run (preview only)
    python tools/lnb/bulk_discover_atrium_api.py \
        --seasons 2022-2023 --dry-run

Available leagues:
    betclic_elite    - Top-tier professional (formerly Pro A), 16 teams
    elite_2          - Second-tier professional (formerly Pro B), 20 teams
    espoirs_elite    - U21 top-tier youth development
    espoirs_prob     - U21 second-tier youth development

Output:
    - Saves to tools/lnb/fixture_uuids_by_season.json
    - Ready for build_game_index.py and pipeline

Performance:
    - ~1 second per season per league
    - No authentication required
    - Returns actual fixture UUIDs
        """,
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        required=True,
        help="Seasons to discover (format: YYYY-YYYY)",
    )

    parser.add_argument(
        "--leagues",
        nargs="+",
        default=None,
        help="Leagues to discover (default: all leagues with data for specified seasons). "
        "Options: betclic_elite, elite_2, espoirs_elite, espoirs_prob",
    )

    parser.add_argument(
        "--seed-fixture",
        type=str,
        help="Seed fixture UUID to extract season metadata (if season not in SEASON_METADATA)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview discovery without saving to file",
    )

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print("  BULK FIXTURE UUID DISCOVERY (Atrium API)")
    print(f"{'='*80}\n")

    print(f"Seasons: {args.seasons}")
    print(f"Leagues: {args.leagues or 'All'}")
    print(f"Dry run: {args.dry_run}")
    if args.seed_fixture:
        print(f"Seed fixture: {args.seed_fixture}")
    print()

    # Load existing mappings
    all_mappings = load_existing_mappings()

    # ENHANCEMENT (2025-11-20): Multi-league discovery support
    # If leagues specified, discover for each league/season combination
    # If no leagues specified, discover using SEASON_METADATA (all leagues)
    newly_discovered = {}

    if args.leagues and not args.seed_fixture:
        # Multi-league mode: discover for each league explicitly
        from src.cbb_data.fetchers.lnb_league_config import get_season_metadata

        for league in args.leagues:
            for season in args.seasons:
                # Get metadata for this specific league/season
                meta = get_season_metadata(league, season)
                if not meta:
                    print(f"  [SKIP] {league} - {season}: No metadata available")
                    continue

                try:
                    # Discover fixtures for this league/season
                    fixtures = discover_fixtures_via_atrium(
                        competition_id=meta["competition_id"],
                        season_id=meta["season_id"],
                        season_name=f"{league} {season}",
                    )

                    if fixtures:
                        # Store with unique key: league_season
                        key = f"{season}_{league}"
                        newly_discovered[key] = fixtures
                        print(f"  [OK] {league} - {season}: {len(fixtures)} fixtures")
                    else:
                        print(f"  [WARN] {league} - {season}: No fixtures found")

                except Exception as e:
                    print(f"  [ERROR] {league} - {season}: {e}")
                    continue
    else:
        # Legacy mode: discover each season (any league in SEASON_METADATA)
        for season in args.seasons:
            try:
                fixtures = discover_season_fixtures(
                    season_str=season,
                    seed_fixture_uuid=args.seed_fixture,
                )

                if fixtures:
                    newly_discovered[season] = fixtures
                    print(f"  [OK] {season}: {len(fixtures)} fixtures")
                else:
                    print(f"  [WARN] {season}: No fixtures found")

            except Exception as e:
                print(f"  [ERROR] {season}: {e}")
                continue

    # Merge and save
    if newly_discovered and not args.dry_run:
        all_mappings["mappings"].update(newly_discovered)
        save_uuid_mappings(all_mappings)
        print("\n✅ Discovery complete!")
    elif newly_discovered and args.dry_run:
        print(f"\n[DRY RUN] Would save {len(newly_discovered)} season(s):")
        for season, fixtures in newly_discovered.items():
            print(f"  - {season}: {len(fixtures)} fixtures")
    else:
        print("\n[WARN] No fixtures discovered")

    print()


if __name__ == "__main__":
    main()
