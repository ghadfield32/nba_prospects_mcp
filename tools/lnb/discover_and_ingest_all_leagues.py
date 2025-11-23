#!/usr/bin/env python3
"""Unified Multi-League Discovery and Ingestion Script

This convenience script orchestrates the complete pipeline for all 4 LNB leagues:
1. Betclic ELITE (formerly Pro A) - Top-tier professional, 16 teams
2. ELITE 2 (formerly Pro B) - Second-tier professional, 20 teams
3. Espoirs ELITE - U21 top-tier youth development
4. Espoirs PROB - U21 second-tier youth development

Workflow:
    1. Discover fixture UUIDs via Atrium API for each league/season
    2. Build game index with metadata (dates, teams, status)
    3. Ingest play-by-play and shot chart data for completed games
    4. Validate and report coverage

Created: 2025-11-20
Purpose: Simplify multi-league data pipeline orchestration

Usage:
    # Discover and ingest all leagues for current season
    python tools/lnb/discover_and_ingest_all_leagues.py

    # Specific leagues only
    python tools/lnb/discover_and_ingest_all_leagues.py \
        --leagues betclic_elite elite_2

    # Specific seasons
    python tools/lnb/discover_and_ingest_all_leagues.py \
        --seasons 2024-2025 2023-2024

    # Dry run (discovery only, no ingestion)
    python tools/lnb/discover_and_ingest_all_leagues.py --dry-run

    # Skip discovery (use existing index)
    python tools/lnb/discover_and_ingest_all_leagues.py --skip-discovery
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cbb_data.fetchers.lnb_league_config import (
    ALL_LEAGUES,
    LEAGUE_METADATA_REGISTRY,
    get_all_seasons_for_league,
)

# ==============================================================================
# CONFIG
# ==============================================================================

DEFAULT_LEAGUES = ALL_LEAGUES  # All 4 LNB leagues
DEFAULT_SEASONS = ["2024-2025"]  # Current season

PYTHON_CMD = sys.executable  # Use same Python as current process

# Script paths
TOOLS_DIR = Path(__file__).parent
DISCOVER_SCRIPT = TOOLS_DIR / "bulk_discover_atrium_api.py"
INDEX_SCRIPT = TOOLS_DIR / "build_game_index.py"
INGEST_SCRIPT = TOOLS_DIR / "bulk_ingest_pbp_shots.py"

# ==============================================================================
# PIPELINE ORCHESTRATION
# ==============================================================================


def run_command(cmd: list[str], description: str) -> bool:
    """Run a subprocess command and return success status

    Args:
        cmd: Command and arguments as list
        description: Human-readable description for logging

    Returns:
        True if command succeeded (exit code 0), False otherwise
    """
    print(f"\n{'='*80}")
    print(f"  {description}")
    print(f"{'='*80}\n")

    print(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True, text=True)
        print(f"\n✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} - FAILED (exit code {e.returncode})")
        return False
    except Exception as e:
        print(f"\n❌ {description} - ERROR: {e}")
        return False


def discover_fixtures(
    leagues: list[str],
    seasons: list[str],
    dry_run: bool = False,
) -> bool:
    """Step 1: Discover fixture UUIDs via Atrium API

    Args:
        leagues: List of league identifiers
        seasons: List of season strings
        dry_run: If True, don't save discovered fixtures

    Returns:
        True if discovery succeeded
    """
    cmd = [
        PYTHON_CMD,
        str(DISCOVER_SCRIPT),
        "--seasons",
        *seasons,
        "--leagues",
        *leagues,
    ]

    if dry_run:
        cmd.append("--dry-run")

    return run_command(cmd, "STEP 1: Fixture Discovery")


def build_game_index(
    leagues: list[str],
    seasons: list[str],
    force_rebuild: bool = False,
) -> bool:
    """Step 2: Build game index with metadata

    Args:
        leagues: List of league identifiers
        seasons: List of season strings
        force_rebuild: If True, rebuild index from scratch

    Returns:
        True if index build succeeded
    """
    cmd = [
        PYTHON_CMD,
        str(INDEX_SCRIPT),
        "--seasons",
        *seasons,
        "--leagues",
        *leagues,
    ]

    if force_rebuild:
        cmd.append("--force-rebuild")

    return run_command(cmd, "STEP 2: Game Index Build")


def ingest_data(
    leagues: list[str],
    seasons: list[str],
    max_games: int | None = None,
    force_refetch: bool = False,
) -> bool:
    """Step 3: Ingest play-by-play and shot chart data

    Args:
        leagues: List of league identifiers
        seasons: List of season strings
        max_games: Optional limit on games per season (for testing)
        force_refetch: If True, re-fetch even if already fetched

    Returns:
        True if ingestion succeeded
    """
    cmd = [
        PYTHON_CMD,
        str(INGEST_SCRIPT),
        "--seasons",
        *seasons,
        "--leagues",
        *leagues,
    ]

    if max_games:
        cmd.extend(["--max-games", str(max_games)])

    if force_refetch:
        cmd.append("--force-refetch")

    return run_command(cmd, "STEP 3: Data Ingestion")


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================


def run_pipeline(
    leagues: list[str],
    seasons: list[str],
    skip_discovery: bool = False,
    dry_run: bool = False,
    max_games: int | None = None,
    force_rebuild: bool = False,
    force_refetch: bool = False,
) -> None:
    """Run complete multi-league data pipeline

    Args:
        leagues: List of league identifiers to process
        seasons: List of season strings to process
        skip_discovery: If True, skip fixture discovery step
        dry_run: If True, run discovery but skip index build and ingestion
        max_games: Optional limit on games per season (for testing)
        force_rebuild: If True, rebuild game index from scratch
        force_refetch: If True, re-fetch data even if already fetched
    """
    print(f"\n{'='*80}")
    print("  LNB MULTI-LEAGUE DATA PIPELINE")
    print(f"{'='*80}\n")

    print("Configuration:")
    print(f"  Leagues: {', '.join(leagues)}")
    print(f"  Seasons: {', '.join(seasons)}")
    print(f"  Skip discovery: {skip_discovery}")
    print(f"  Dry run: {dry_run}")
    if max_games:
        print(f"  Max games per season: {max_games}")
    print()

    # Print league details
    print("League Details:")
    for league in leagues:
        if league in LEAGUE_METADATA_REGISTRY:
            info = LEAGUE_METADATA_REGISTRY[league]
            print(f"  {league}:")
            print(f"    Name: {info['display_name']}")
            print(f"    Description: {info['description']}")
            available_seasons = get_all_seasons_for_league(league)
            requested_available = [s for s in seasons if s in available_seasons]
            if requested_available:
                print(f"    Available seasons: {', '.join(requested_available)}")
            else:
                print("    ⚠️  No data available for requested seasons")
    print()

    # Step 1: Discover fixtures
    if not skip_discovery:
        success = discover_fixtures(leagues, seasons, dry_run=dry_run)
        if not success:
            print("\n❌ Pipeline failed at discovery step")
            sys.exit(1)
    else:
        print("\n⏩ Skipping fixture discovery (using existing data)")

    # Stop here if dry run
    if dry_run:
        print("\n🔍 Dry run complete - skipping index build and ingestion")
        print("   Remove --dry-run to proceed with full pipeline")
        return

    # Step 2: Build game index
    success = build_game_index(leagues, seasons, force_rebuild=force_rebuild)
    if not success:
        print("\n❌ Pipeline failed at index build step")
        sys.exit(1)

    # Step 3: Ingest data
    success = ingest_data(
        leagues,
        seasons,
        max_games=max_games,
        force_refetch=force_refetch,
    )
    if not success:
        print("\n❌ Pipeline failed at ingestion step")
        sys.exit(1)

    # Success summary
    print(f"\n{'='*80}")
    print("  ✅ PIPELINE COMPLETE")
    print(f"{'='*80}\n")

    print("Next steps:")
    print("  1. Validate data consistency:")
    print("     python tools/lnb/validate_data_consistency.py")
    print()
    print("  2. Generate coverage reports:")
    print("     python tools/lnb/validate_and_monitor_coverage.py")
    print()


# ==============================================================================
# CLI
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Unified multi-league discovery and ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run complete pipeline for all leagues (current season)
    python tools/lnb/discover_and_ingest_all_leagues.py

    # Specific leagues only
    python tools/lnb/discover_and_ingest_all_leagues.py \
        --leagues betclic_elite elite_2

    # Multiple seasons
    python tools/lnb/discover_and_ingest_all_leagues.py \
        --seasons 2024-2025 2023-2024

    # Dry run (discovery only, preview results)
    python tools/lnb/discover_and_ingest_all_leagues.py --dry-run

    # Skip discovery (use existing fixture data)
    python tools/lnb/discover_and_ingest_all_leagues.py --skip-discovery

    # Test mode (limit to 5 games per season)
    python tools/lnb/discover_and_ingest_all_leagues.py --max-games 5

Available leagues:
    betclic_elite    - Top-tier professional (formerly Pro A), 16 teams
    elite_2          - Second-tier professional (formerly Pro B), 20 teams
    espoirs_elite    - U21 top-tier youth development
    espoirs_prob     - U21 second-tier youth development
        """,
    )

    parser.add_argument(
        "--leagues",
        nargs="+",
        default=DEFAULT_LEAGUES,
        help="Leagues to process (default: all leagues)",
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="Seasons to process (default: current season)",
    )

    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip fixture discovery (use existing data)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery only, skip index build and ingestion",
    )

    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Max games per season (for testing)",
    )

    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Rebuild game index from scratch",
    )

    parser.add_argument(
        "--force-refetch",
        action="store_true",
        help="Re-fetch data even if already fetched",
    )

    args = parser.parse_args()

    # Run pipeline
    run_pipeline(
        leagues=args.leagues,
        seasons=args.seasons,
        skip_discovery=args.skip_discovery,
        dry_run=args.dry_run,
        max_games=args.max_games,
        force_rebuild=args.force_rebuild,
        force_refetch=args.force_refetch,
    )


if __name__ == "__main__":
    main()
