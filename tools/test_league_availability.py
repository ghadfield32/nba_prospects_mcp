"""Test League Data Availability

Comprehensive test to verify what data is actually available for each league.
Tests actual API calls (with small limits) to determine true availability.

Usage:
    python tools/test_league_availability.py
    python tools/test_league_availability.py --league NCAA-MBB
    python tools/test_league_availability.py --quick  # Fast mode, skip slow APIs
"""

import argparse
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources

# Ensure sources are registered
_register_league_sources()


def test_dataset(league: str, dataset: str, timeout: int = 30) -> dict:
    """Test if a dataset can be fetched for a league

    Returns dict with:
        - available: bool
        - rows: int (number of rows returned)
        - error: str (if failed)
        - time: float (seconds to fetch)
    """
    from cbb_data.api.datasets import get_dataset

    start = time.time()
    result = {
        "available": False,
        "rows": 0,
        "error": None,
        "time": 0,
        "columns": [],
    }

    try:
        # Build filters based on dataset type
        if dataset in ["schedule", "player_season", "team_season"]:
            # These don't need game_ids - use relative_days to limit scope
            filters = {"league": league, "season": "2025", "relative_days": 14}
        elif dataset in ["player_game", "team_game", "pbp", "shots"]:
            # Need game_ids - try to get from schedule first
            schedule_df = get_dataset(
                grouping="schedule",
                filters={"league": league, "season": "2025", "relative_days": 14},
                limit=5,
            )
            if schedule_df is None or schedule_df.empty:
                result["error"] = "No schedule data to get game_ids"
                return result

            # Find game ID column
            game_id_col = None
            for col in ["GAME_ID", "game_id", "id", "gameId", "external_id"]:
                if col in schedule_df.columns:
                    game_id_col = col
                    break

            if game_id_col is None:
                result["error"] = f"No game_id column found. Columns: {list(schedule_df.columns)}"
                return result

            game_ids = schedule_df[game_id_col].dropna().astype(str).tolist()[:3]
            if not game_ids:
                result["error"] = "No valid game_ids found"
                return result

            filters = {"league": league, "game_ids": game_ids}
        else:
            filters = {"league": league}

        # Fetch the data
        df = get_dataset(
            grouping=dataset,
            filters=filters,
            limit=20,
        )

        elapsed = time.time() - start

        if df is not None and not df.empty:
            result["available"] = True
            result["rows"] = len(df)
            result["columns"] = list(df.columns)[:10]  # First 10 columns
        else:
            result["error"] = "Empty result"

        result["time"] = round(elapsed, 2)

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
        result["time"] = round(time.time() - start, 2)

    return result


def test_league(league: str, datasets: list[str] = None) -> dict:
    """Test all datasets for a league"""
    if datasets is None:
        datasets = [
            "schedule",
            "player_season",
            "team_season",
            "player_game",
            "team_game",
            "pbp",
            "shots",
        ]

    results = {}
    print(f"\n{'='*60}")
    print(f"Testing {league}")
    print(f"{'='*60}")

    for dataset in datasets:
        print(f"  {dataset}...", end=" ", flush=True)
        result = test_dataset(league, dataset)

        if result["available"]:
            print(f"[Y] {result['rows']} rows ({result['time']}s)")
        else:
            error = result["error"][:50] if result["error"] else "Unknown"
            print(f"[X] {error}")

        results[dataset] = result

    return results


def discover_fetcher_functions(league: str) -> dict:
    """Discover what fetch functions exist for a league's fetcher module"""
    config = LEAGUE_SOURCES.get(league)
    if not config:
        return {}

    functions = {}

    # Check each fetch function
    fetch_attrs = [
        "fetch_schedule",
        "fetch_player_season",
        "fetch_team_season",
        "fetch_player_game",
        "fetch_team_game",
        "fetch_pbp",
        "fetch_shots",
    ]

    for attr in fetch_attrs:
        func = getattr(config, attr, None)
        if func:
            functions[attr] = {
                "wired": True,
                "module": func.__module__ if hasattr(func, "__module__") else "unknown",
                "name": func.__name__ if hasattr(func, "__name__") else str(func),
            }
        else:
            functions[attr] = {"wired": False}

    return functions


def print_summary(all_results: dict):
    """Print summary of test results"""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    # Calculate totals
    league_scores = {}
    dataset_availability = {
        ds: 0
        for ds in [
            "schedule",
            "player_season",
            "team_season",
            "player_game",
            "team_game",
            "pbp",
            "shots",
        ]
    }

    for league, results in all_results.items():
        available = sum(1 for r in results.values() if r.get("available", False))
        total = len(results)
        league_scores[league] = (available, total)

        for ds, result in results.items():
            if result.get("available", False):
                dataset_availability[ds] += 1

    # Print by league
    print("\nBy League:")
    for league in sorted(league_scores.keys(), key=lambda x: league_scores[x][0], reverse=True):
        available, total = league_scores[league]
        status = "[Y]" if available == total else "[P]" if available > 0 else "[X]"
        print(f"  {status} {league}: {available}/{total}")

    # Print by dataset
    print("\nBy Dataset:")
    for ds, count in sorted(dataset_availability.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ds}: {count}/{len(all_results)} leagues")

    # Print issues found
    print("\nIssues Found:")
    for league, results in all_results.items():
        issues = [
            (ds, r["error"])
            for ds, r in results.items()
            if not r.get("available") and r.get("error")
        ]
        if issues:
            print(f"\n  {league}:")
            for ds, error in issues:
                print(f"    - {ds}: {error[:60]}")


def main():
    parser = argparse.ArgumentParser(description="Test league data availability")
    parser.add_argument("--league", help="Test specific league only")
    parser.add_argument("--quick", action="store_true", help="Quick mode - test fewer datasets")
    parser.add_argument(
        "--discover", action="store_true", help="Discover available fetch functions"
    )
    args = parser.parse_args()

    # Leagues to test (ordered by priority)
    priority_leagues = [
        "NCAA-MBB",
        "NCAA-WBB",  # ESPN
        "LNB_PROA",
        "LNB_ELITE2",
        "LNB_ESPOIRS_ELITE",  # LNB
        "EuroLeague",
        "EuroCup",  # EuroLeague API
        "G-League",
        "WNBA",  # NBA Stats
        "NBL",
        "NZ-NBL",  # Australia/NZ
        "OTE",
        "CEBL",
        "ACB",  # Other
    ]

    if args.league:
        leagues = [args.league]
    elif args.quick:
        leagues = ["NCAA-MBB", "LNB_PROA", "EuroLeague", "NBL"]
    else:
        leagues = priority_leagues

    # Discover mode - just show what's wired
    if args.discover:
        print("Discovering fetch functions for each league...")
        print()
        for league in leagues:
            print(f"{league}:")
            funcs = discover_fetcher_functions(league)
            for func_name, info in funcs.items():
                if info.get("wired"):
                    print(f"  [Y] {func_name}: {info['name']}")
                else:
                    print(f"  [X] {func_name}: NOT WIRED")
            print()
        return

    # Test mode
    print("Testing actual data availability...")
    print("This will make real API calls (with small limits)")
    print()

    all_results = {}

    for league in leagues:
        try:
            results = test_league(league)
            all_results[league] = results
        except Exception as e:
            print(f"  ERROR testing {league}: {e}")
            all_results[league] = {"error": str(e)}

    # Print summary
    print_summary(all_results)

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "metadata" / "availability_test.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import json

    # Convert to JSON-serializable format
    json_results = {}
    for league, results in all_results.items():
        json_results[league] = {}
        for ds, r in results.items():
            json_results[league][ds] = {
                "available": r.get("available", False),
                "rows": r.get("rows", 0),
                "error": r.get("error"),
                "time": r.get("time", 0),
            }

    with open(output_path, "w") as f:
        json.dump(json_results, f, indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
