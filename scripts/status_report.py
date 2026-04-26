#!/usr/bin/env python
"""Pipeline Readiness Status Report

Comprehensive status matrix showing readiness of all basketball leagues
in the data pipeline.

Checks:
1. Index - Game indexes present (data/game_indexes/*.csv)
2. Enriched - Enriched metadata available
3. Box Fetch - Can box scores be fetched (fetcher exists)
4. Canonical - Canonical parquet files present (data/canonical/box_player_game/league=X/)
5. Gold Union - Data in gold table (data/gold/player_career_game.parquet)
6. Xwalk - Player crosswalk working (players can be matched)
7. Validation Player - Can find validation player's data

Usage:
    python scripts/status_report.py
    python scripts/status_report.py --verbose
    python scripts/status_report.py --json
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
GOLD_PATH = DATA_DIR / "gold" / "player_career_game.parquet"
XWALK_PATH = DATA_DIR / "player_xwalk.parquet"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
CANONICAL_DIR = DATA_DIR / "canonical" / "box_player_game"

# Fetchers directory
FETCHERS_DIR = BASE_DIR / "src" / "cbb_data" / "fetchers"

# League configuration with validation players
LEAGUES = {
    "NBL": {
        "validation_player": "LaMelo Ball",
        "validation_name_key": "lamelo_ball",
        "expected_seasons": ["2019-20"],
        "description": "Australia NBL",
    },
    "LNB_PROA": {
        "validation_player": "Victor Wembanyama",
        "validation_name_key": "wembanyama",
        "expected_seasons": ["2021-22", "2022-23"],
        "description": "French Pro A",
    },
    "ABA": {
        "validation_player": "Nikola Jokic",
        "validation_name_key": "jokic",
        "expected_seasons": ["2013-14", "2014-15"],
        "description": "Adriatic League",
    },
    "NCAA_MBB": {
        "validation_player": "Paolo Banchero",
        "validation_name_key": "banchero",
        "expected_seasons": ["2021-22"],
        "description": "NCAA Men's Basketball",
    },
    "G_LEAGUE": {
        "validation_player": "Jalen Green",
        "validation_name_key": "jalen_green",
        "expected_seasons": ["2020-21"],
        "description": "NBA G League",
    },
    "EUROLEAGUE": {
        "validation_player": "Luka Doncic",
        "validation_name_key": "doncic_luka",
        "expected_seasons": ["2016-17", "2017-18"],
        "description": "EuroLeague",
    },
    "ACB": {
        "validation_player": "Luka Doncic",
        "validation_name_key": "doncic",  # May need flexible matching
        "expected_seasons": ["2016-17", "2017-18"],
        "description": "Spanish Liga ACB",
    },
    "BCL": {
        "validation_player": "Alperen Sengun",
        "validation_name_key": "sengun",
        "expected_seasons": ["2020-21"],
        "description": "Basketball Champions League",
    },
    "BAL": {
        "validation_player": "TBD",
        "validation_name_key": None,
        "expected_seasons": [],
        "description": "Basketball Africa League",
    },
    "LKL": {
        "validation_player": "Deividas Sirvydis",
        "validation_name_key": "sirvydis",
        "expected_seasons": ["2018-19"],
        "description": "Lithuanian League",
    },
    "CEBL": {
        "validation_player": "TBD",
        "validation_name_key": None,
        "expected_seasons": [],
        "description": "Canadian Elite Basketball League",
    },
    "OTE": {
        "validation_player": "Alex Sarr",
        "validation_name_key": "alex_sarr",
        "expected_seasons": ["2022-23", "2023-24"],
        "description": "Overtime Elite",
    },
}

# Mapping of league to fetcher file
FETCHER_FILES = {
    "NBL": "nbl.py",
    "LNB_PROA": "lnb.py",
    "ABA": "aba.py",
    "NCAA_MBB": "cbbpy_mbb.py",
    "G_LEAGUE": "gleague.py",
    "EUROLEAGUE": "euroleague.py",
    "ACB": "acb.py",
    "BCL": "bcl.py",
    "BAL": "bal.py",
    "LKL": "lkl.py",
    "CEBL": "cebl.py",
    "OTE": "ote.py",
}


# ============================================================================
# Status Check Functions
# ============================================================================


def check_game_indexes(league: str) -> dict[str, Any]:
    """Check if game indexes exist for a league."""
    result = {"status": False, "seasons": 0, "games": 0, "files": []}

    if not GAME_INDEX_DIR.exists():
        return result

    # Look for files matching league pattern
    patterns = [
        f"{league}_*.csv",
        f"{league.lower()}_*.csv",
    ]

    for pattern in patterns:
        for filepath in GAME_INDEX_DIR.glob(pattern):
            try:
                df = pd.read_csv(filepath)
                result["files"].append(filepath.name)
                result["games"] += len(df)
                result["seasons"] += 1
            except Exception:
                pass

    result["status"] = result["seasons"] > 0
    return result


def check_enriched_metadata(league: str) -> dict[str, Any]:
    """Check if enriched metadata is available for a league."""
    result = {"status": False, "details": ""}

    # Check for enriched indexes or metadata files
    DATA_DIR / "metadata"
    enriched_patterns = [
        DATA_DIR / "metadata" / f"{league.lower()}_enriched.parquet",
        DATA_DIR / "metadata" / f"{league.lower()}_metadata.json",
        DATA_DIR / "curated" / f"{league.lower()}" / "metadata.json",
    ]

    for path in enriched_patterns:
        if path.exists():
            result["status"] = True
            result["details"] = path.name
            return result

    # Also check if game indexes have enriched columns (GAME_DATE, scores, etc.)
    if GAME_INDEX_DIR.exists():
        for filepath in GAME_INDEX_DIR.glob(f"{league}_*.csv"):
            try:
                df = pd.read_csv(filepath, nrows=5)
                # Check for enriched columns
                enriched_cols = ["GAME_DATE", "HOME_SCORE", "AWAY_SCORE", "HOME_TEAM", "AWAY_TEAM"]
                present = sum(1 for col in enriched_cols if col in df.columns)
                if present >= 3:
                    result["status"] = True
                    result["details"] = f"{present}/5 enriched cols"
                    return result
            except Exception:
                pass

    return result


def check_fetcher_exists(league: str) -> dict[str, Any]:
    """Check if a box score fetcher exists for a league."""
    result = {"status": False, "fetcher_file": None, "is_functional": False}

    fetcher_file = FETCHER_FILES.get(league)
    if not fetcher_file:
        return result

    fetcher_path = FETCHERS_DIR / fetcher_file
    if fetcher_path.exists():
        result["status"] = True
        result["fetcher_file"] = fetcher_file

        # Check if fetcher has fetch function
        try:
            with open(fetcher_path, encoding="utf-8") as f:
                content = f.read()
            if "def fetch" in content or "def get_box" in content or "class" in content:
                result["is_functional"] = True
        except Exception:
            pass

    return result


def check_canonical_data(league: str) -> dict[str, Any]:
    """Check if canonical parquet files exist for a league."""
    result = {"status": False, "seasons": 0, "rows": 0, "path": None}

    league_dir = CANONICAL_DIR / f"league={league}"
    if not league_dir.exists():
        return result

    # Count season directories and total rows
    for season_dir in league_dir.glob("season=*"):
        data_file = season_dir / "data.parquet"
        if data_file.exists():
            try:
                df = pd.read_parquet(data_file)
                result["seasons"] += 1
                result["rows"] += len(df)
            except Exception:
                pass

    result["status"] = result["seasons"] > 0
    result["path"] = str(league_dir)
    return result


def check_gold_table(league: str, gold_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Check if league data is in the gold table."""
    result = {"status": False, "rows": 0, "players": 0, "seasons": []}

    if gold_df is None:
        if not GOLD_PATH.exists():
            return result
        try:
            gold_df = pd.read_parquet(GOLD_PATH)
        except Exception:
            return result

    league_df = gold_df[gold_df["LEAGUE"] == league]
    if len(league_df) > 0:
        result["status"] = True
        result["rows"] = len(league_df)
        result["players"] = league_df["NAME_KEY"].nunique()
        result["seasons"] = sorted(league_df["SEASON"].dropna().unique().tolist())[:5]

    return result


def check_xwalk(league: str, xwalk_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Check if players in this league can be matched via crosswalk."""
    result = {"status": False, "entries": 0, "match_rate": 0.0}

    if xwalk_df is None:
        if not XWALK_PATH.exists():
            return result
        try:
            xwalk_df = pd.read_parquet(XWALK_PATH)
        except Exception:
            return result

    # Count xwalk entries that include this league
    if "LEAGUES" in xwalk_df.columns:
        # LEAGUES might be a string or list
        league_entries = xwalk_df[xwalk_df["LEAGUES"].astype(str).str.contains(league, na=False)]
        result["entries"] = len(league_entries)
        result["status"] = result["entries"] > 0

        # Calculate match rate based on unique players
        total_unique = xwalk_df["NAME_KEY"].nunique()
        if total_unique > 0:
            result["match_rate"] = round(result["entries"] / total_unique * 100, 1)

    return result


def check_validation_player(
    league: str, validation_name_key: str | None, gold_df: pd.DataFrame | None = None
) -> dict[str, Any]:
    """Check if validation player can be found in the gold table."""
    result = {"status": False, "games": 0, "seasons": [], "found_name_key": None}

    if validation_name_key is None:
        result["status"] = None  # TBD
        return result

    if gold_df is None:
        if not GOLD_PATH.exists():
            return result
        try:
            gold_df = pd.read_parquet(GOLD_PATH)
        except Exception:
            return result

    # Filter to this league first
    league_df = gold_df[gold_df["LEAGUE"] == league]
    if len(league_df) == 0:
        return result

    # Search for validation player (flexible matching)
    matches = league_df[
        league_df["NAME_KEY"].str.contains(validation_name_key, case=False, na=False)
        | league_df["PLAYER_NAME_RAW"].str.contains(
            validation_name_key.replace("_", " "), case=False, na=False
        )
    ]

    if len(matches) > 0:
        result["status"] = True
        result["games"] = len(matches)
        result["seasons"] = sorted(matches["SEASON"].dropna().unique().tolist())
        result["found_name_key"] = matches["NAME_KEY"].iloc[0]

    return result


# ============================================================================
# Report Generation
# ============================================================================


def generate_status_matrix(verbose: bool = False) -> dict[str, dict[str, Any]]:
    """Generate complete status matrix for all leagues."""

    # Load gold and xwalk data once
    gold_df = None
    xwalk_df = None

    if GOLD_PATH.exists():
        try:
            gold_df = pd.read_parquet(GOLD_PATH)
        except Exception as e:
            print(f"Warning: Could not load gold table: {e}")

    if XWALK_PATH.exists():
        try:
            xwalk_df = pd.read_parquet(XWALK_PATH)
        except Exception as e:
            print(f"Warning: Could not load xwalk: {e}")

    matrix = {}

    for league, config in LEAGUES.items():
        if verbose:
            print(f"Checking {league}...")

        league_status = {
            "description": config["description"],
            "validation_player": config["validation_player"],
            "index": check_game_indexes(league),
            "enriched": check_enriched_metadata(league),
            "box_fetch": check_fetcher_exists(league),
            "canonical": check_canonical_data(league),
            "gold_union": check_gold_table(league, gold_df),
            "xwalk": check_xwalk(league, xwalk_df),
            "validation": check_validation_player(league, config["validation_name_key"], gold_df),
        }

        matrix[league] = league_status

    return matrix


def status_to_emoji(status: bool | None) -> str:
    """Convert status to emoji."""
    if status is None:
        return "?"  # TBD
    return "\u2705" if status else "\u274c"  # checkmark or X


def status_to_warning_emoji(status: bool | None, has_partial: bool = False) -> str:
    """Convert status to emoji with warning option."""
    if status is None:
        return "?"
    if status:
        return "\u2705"  # checkmark
    if has_partial:
        return "\u26a0\ufe0f"  # warning
    return "\u274c"  # X


def print_status_report(matrix: dict[str, dict[str, Any]], verbose: bool = False):
    """Print formatted status report."""

    print()
    print("=" * 100)
    print("BASKETBALL PIPELINE READINESS MATRIX")
    print("=" * 100)
    print(f"Generated: {datetime.now(UTC).isoformat()}")
    print()

    # Header
    header_line = f"{'League':<12} {'Index':^7} {'Enrich':^7} {'Fetch':^7} {'Canon':^7} {'Gold':^7} {'Xwalk':^7} {'Val':^7} {'Description':<30}"
    print(header_line)
    print("-" * 100)

    # Calculate totals
    totals = defaultdict(int)

    for league, status in matrix.items():
        # Get status values
        index_ok = status["index"]["status"]
        enriched_ok = status["enriched"]["status"]
        fetch_ok = status["box_fetch"]["status"]
        canonical_ok = status["canonical"]["status"]
        gold_ok = status["gold_union"]["status"]
        xwalk_ok = status["xwalk"]["status"]
        val_ok = status["validation"]["status"]

        # Update totals
        totals["index"] += 1 if index_ok else 0
        totals["enriched"] += 1 if enriched_ok else 0
        totals["fetch"] += 1 if fetch_ok else 0
        totals["canonical"] += 1 if canonical_ok else 0
        totals["gold"] += 1 if gold_ok else 0
        totals["xwalk"] += 1 if xwalk_ok else 0
        totals["validation"] += 1 if val_ok else 0

        # Format row
        row = (
            f"{league:<12} "
            f"{status_to_emoji(index_ok):^7} "
            f"{status_to_emoji(enriched_ok):^7} "
            f"{status_to_emoji(fetch_ok):^7} "
            f"{status_to_emoji(canonical_ok):^7} "
            f"{status_to_emoji(gold_ok):^7} "
            f"{status_to_emoji(xwalk_ok):^7} "
            f"{status_to_emoji(val_ok):^7} "
            f"{status['description']:<30}"
        )
        print(row)

    print("-" * 100)

    # Totals row
    total_leagues = len(matrix)
    print(
        f"{'TOTALS':<12} "
        f"{totals['index']:^7}/{total_leagues} "
        f"{totals['enriched']:^7}/{total_leagues} "
        f"{totals['fetch']:^7}/{total_leagues} "
        f"{totals['canonical']:^7}/{total_leagues} "
        f"{totals['gold']:^7}/{total_leagues} "
        f"{totals['xwalk']:^7}/{total_leagues} "
        f"{totals['validation']:^7}/{total_leagues}"
    )

    print()
    print("Legend: \u2705 = Ready, \u274c = Missing, ? = TBD")
    print()

    # Summary statistics
    print("=" * 100)
    print("SUMMARY STATISTICS")
    print("=" * 100)
    print()

    # Gold table stats
    if GOLD_PATH.exists():
        try:
            gold_df = pd.read_parquet(GOLD_PATH)
            print(
                f"Gold Table: {len(gold_df):,} total rows, {gold_df['NAME_KEY'].nunique():,} unique players"
            )
            print(f"Leagues in Gold: {sorted(gold_df['LEAGUE'].dropna().unique().tolist())}")
            print()
        except Exception:
            pass

    # Validation player details
    print("VALIDATION PLAYER STATUS:")
    print("-" * 60)
    for league, status in matrix.items():
        val = status["validation"]
        player = status["validation_player"]
        if val["status"] is None:
            indicator = "?"
            detail = "TBD"
        elif val["status"]:
            indicator = "\u2705"
            detail = f"{val['games']} games, seasons: {val['seasons'][:3]}{'...' if len(val['seasons']) > 3 else ''}"
        else:
            indicator = "\u274c"
            detail = "NOT FOUND"

        print(f"  {indicator} {league:<12} {player:<25} {detail}")

    print()

    # Detailed breakdown if verbose
    if verbose:
        print("=" * 100)
        print("DETAILED BREAKDOWN")
        print("=" * 100)
        print()

        for league, status in matrix.items():
            print(f"### {league} ({status['description']})")
            print(
                f"  Index:     {status['index']['seasons']} seasons, {status['index']['games']:,} games"
            )
            print(f"  Enriched:  {status['enriched']['details'] or 'None'}")
            print(f"  Fetcher:   {status['box_fetch']['fetcher_file'] or 'None'}")
            print(
                f"  Canonical: {status['canonical']['seasons']} seasons, {status['canonical']['rows']:,} rows"
            )
            print(
                f"  Gold:      {status['gold_union']['rows']:,} rows, {status['gold_union']['players']} players"
            )
            print(f"  Xwalk:     {status['xwalk']['entries']} entries")
            print(f"  Validation: {status['validation']['games']} games found")
            print()


def main():
    parser = argparse.ArgumentParser(description="Pipeline Readiness Status Report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed breakdown")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", type=str, help="Save report to file")
    args = parser.parse_args()

    # Generate status matrix
    matrix = generate_status_matrix(verbose=args.verbose)

    if args.json:
        # Convert to JSON-serializable format
        json_matrix = {}
        for league, status in matrix.items():
            json_status = {}
            for key, value in status.items():
                if isinstance(value, dict):
                    # Convert any non-serializable values
                    json_status[key] = {
                        k: (str(v) if isinstance(v, Path) else v) for k, v in value.items()
                    }
                else:
                    json_status[key] = value
            json_matrix[league] = json_status

        output = json.dumps(json_matrix, indent=2, default=str)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Saved to {args.output}")
        else:
            print(output)
    else:
        # Print formatted report
        print_status_report(matrix, verbose=args.verbose)

        if args.output:
            # Also save to file
            import io
            import sys

            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            print_status_report(matrix, verbose=args.verbose)
            output = buffer.getvalue()
            sys.stdout = old_stdout

            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
