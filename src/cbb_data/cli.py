#!/usr/bin/env python3
"""
Command-line interface for basketball data API.

Provides easy command-line access to all basketball datasets with
natural language support.

Usage:
    cbb datasets                           # List all available datasets
    cbb get schedule --league NCAA-MBB     # Get schedule data
    cbb recent NCAA-MBB --days "last week" # Get recent games
    cbb schema                             # Show API schemas
"""

import argparse
import json
import sys
from typing import Any

# Import basketball data functions
from cbb_data.api.datasets import get_dataset, get_recent_games, list_datasets
from cbb_data.catalog.levels import LEAGUE_LEVELS

# ============================================================================
# Helper Functions
# ============================================================================


def print_json(data: Any, indent: int = 2) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=indent, default=str))


def print_table(data: dict[str, Any]) -> None:
    """Print data as a simple table."""
    # Handle compact mode format
    if isinstance(data, dict) and "columns" in data and "rows" in data:
        columns = data["columns"]
        rows = data["rows"]

        # Print header
        header = " | ".join(str(c) for c in columns)
        print(header)
        print("-" * len(header))

        # Print rows
        for row in rows[:50]:  # Limit to first 50 rows
            print(" | ".join(str(v) for v in row))

        if len(rows) > 50:
            print(f"\n... ({len(rows)} total rows, showing first 50)")
    else:
        print(data)


# ============================================================================
# Command: List Datasets
# ============================================================================


def cmd_list_datasets(args: argparse.Namespace) -> None:
    """List all available datasets."""
    print("Available Datasets:\n")

    datasets = list_datasets()

    for ds in datasets:
        print(f"  {ds['id']}")
        print(f"    Description: {ds.get('description', 'N/A')}")
        print(f"    Leagues: {', '.join(ds.get('leagues', []))}")
        print(f"    Filters: {', '.join(ds.get('supports', []))}")
        print()


# ============================================================================
# Command: Get Dataset
# ============================================================================


def cmd_get_dataset(args: argparse.Namespace) -> None:
    """Query a dataset with filters."""
    # Build filters dict
    filters = {"league": args.league}

    if args.season:
        filters["season"] = args.season
    if args.team:
        filters["team"] = args.team
    if args.player:
        filters["player"] = args.player
    if args.date_from:
        filters["date_from"] = args.date_from
    if args.date_to:
        filters["date_to"] = args.date_to
    if args.per_mode:
        filters["per_mode"] = args.per_mode

    # Query dataset
    try:
        df = get_dataset(grouping=args.dataset, filters=filters, limit=args.limit)

        # Format output
        if args.output == "json":
            result = {
                "columns": df.columns.tolist(),
                "rows": df.values.tolist(),
                "row_count": len(df),
            }
            print_json(result)
        elif args.output == "csv":
            print(df.to_csv(index=False))
        elif args.output == "table":
            result = {"columns": df.columns.tolist(), "rows": df.values.tolist()}
            print_table(result)
        else:
            print(df)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Command: Get Recent Games
# ============================================================================


def cmd_recent_games(args: argparse.Namespace) -> None:
    """Get recent games for a league."""
    try:
        # Import natural language parser
        from cbb_data.utils.natural_language import parse_days_parameter

        # Parse days parameter (supports natural language)
        days = parse_days_parameter(args.days) if isinstance(args.days, str) else int(args.days)
        if days is None:
            days = 2  # Default

        # Get recent games
        df = get_recent_games(league=args.league, days=days, teams=args.teams)

        # Format output
        if args.output == "json":
            result = {
                "columns": df.columns.tolist(),
                "rows": df.values.tolist(),
                "row_count": len(df),
            }
            print_json(result)
        elif args.output == "csv":
            print(df.to_csv(index=False))
        elif args.output == "table":
            result = {"columns": df.columns.tolist(), "rows": df.values.tolist()}
            print_table(result)
        else:
            print(df)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Command: Show Schema
# ============================================================================


def cmd_show_schema(args: argparse.Namespace) -> None:
    """Show API schemas."""
    print("Basketball Data API Schemas\n")
    print("=" * 60)

    # Show datasets
    if args.type in ["all", "datasets"]:
        print("\nDATASETS:")
        print("-" * 60)
        datasets = list_datasets()
        for ds in datasets:
            print(f"\n  {ds['id']}")
            print(f"    Leagues: {', '.join(ds.get('leagues', []))}")
            print(f"    Filters: {', '.join(ds.get('supports', []))}")

    # Show filters
    if args.type in ["all", "filters"]:
        print("\n\nFILTERS:")
        print("-" * 60)
        filters = {
            "league": "League identifier (e.g., NCAA-MBB, EuroLeague, NBL, ACB)",
            "season": "Season year OR 'this season', 'last season', '2024-25'",
            "team": "List of team names",
            "player": "List of player names",
            "date": "Date OR 'yesterday', 'today', '3 days ago'",
            "date_from": "Start date OR 'yesterday', 'last week'",
            "date_to": "End date OR 'today'",
            "per_mode": "Aggregation mode: Totals, PerGame, Per40",
            "limit": "Maximum rows to return (1-10000)",
            "compact": "Use compact mode for token efficiency",
        }
        for name, desc in filters.items():
            print(f"\n  {name}")
            print(f"    {desc}")

    # Show natural language support
    if args.type in ["all", "natural-language"]:
        print("\n\nNATURAL LANGUAGE SUPPORT:")
        print("-" * 60)
        print("\n  Dates:")
        print("    'today', 'yesterday', 'last week', '3 days ago', 'last month'")
        print("\n  Seasons:")
        print("    'this season', 'last season', 'current season', '2024-25'")
        print("\n  Days:")
        print("    'today', 'yesterday', 'last week', 'last 5 days'")


# ============================================================================
# Command: Cache Warmer
# ============================================================================


def cmd_warm_cache(args: argparse.Namespace) -> None:
    """
    Warm the cache with popular queries.

    Pre-fetches commonly requested data to improve response times for
    subsequent queries. Useful for running before peak usage times or
    after cache clears.
    """
    print("Cache Warmer - Pre-fetching popular queries...\n")
    print("=" * 60)

    # Define popular queries to warm
    warming_plans: list[dict[str, Any]] = [
        {
            "name": "NCAA-MBB Today's Schedule",
            "dataset": "schedule",
            "filters": {"league": "NCAA-MBB", "season": "2025"},
            "limit": 200,
        },
        {
            "name": "NCAA-MBB Recent Games (Last 2 Days)",
            "dataset": "schedule",
            "filters": {"league": "NCAA-MBB", "date_from": "2 days ago"},
            "limit": 200,
        },
        {
            "name": "NCAA-MBB Top Teams (Season Stats)",
            "dataset": "team_season",
            "filters": {"league": "NCAA-MBB", "season": "2025", "per_mode": "PerGame"},
            "limit": 100,
        },
        {
            "name": "NCAA-WBB Today's Schedule",
            "dataset": "schedule",
            "filters": {"league": "NCAA-WBB", "season": "2025"},
            "limit": 200,
        },
        {
            "name": "EuroLeague Current Season Schedule",
            "dataset": "schedule",
            "filters": {"league": "EuroLeague", "season": "2024"},
            "limit": 200,
        },
        {
            "name": "EuroLeague Player Leaders",
            "dataset": "player_season",
            "filters": {"league": "EuroLeague", "season": "2024", "per_mode": "PerGame"},
            "limit": 100,
        },
    ]

    # Add custom teams if specified
    if args.teams:
        for team in args.teams:
            warming_plans.append(
                {
                    "name": f"{team} Recent Games",
                    "dataset": "schedule",
                    "filters": {"league": "NCAA-MBB", "season": "2025", "team": [team]},
                    "limit": 50,
                }
            )

    # Execute warming plans
    successes = 0
    failures = 0
    total_rows = 0

    for plan in warming_plans:
        try:
            print(f"\n[{successes + failures + 1}/{len(warming_plans)}] {plan['name']}...")

            df = get_dataset(
                grouping=plan["dataset"], filters=plan["filters"], limit=plan.get("limit", 100)
            )

            rows = len(df)
            total_rows += rows
            successes += 1

            print(f"  [OK] Cached {rows} rows")

        except Exception as e:
            failures += 1
            print(f"  [FAIL] Failed: {str(e)}")

    # Summary
    print("\n" + "=" * 60)
    print("\nCache Warming Complete!")
    print(f"  Successful: {successes}/{len(warming_plans)}")
    print(f"  Failed: {failures}/{len(warming_plans)}")
    print(f"  Total Rows Cached: {total_rows:,}")

    if failures > 0:
        print(f"\n[WARN] {failures} queries failed - check logs for details")
        sys.exit(1)


# ============================================================================
# Main CLI
# ============================================================================


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cbb",
        description="Basketball Data CLI - Query college basketball data from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all datasets
  cbb datasets

  # Get schedule for NCAA Men's Basketball
  cbb get schedule --league NCAA-MBB --season "this season" --limit 20

  # Get recent games with natural language
  cbb recent NCAA-MBB --days "last week"

  # Get player stats for Duke this season
  cbb get player_season --league NCAA-MBB --season "this season" --team Duke --per-mode PerGame

  # Get recent games as JSON
  cbb recent NCAA-MBB --days 7 --output json

  # Show API schemas
  cbb schema
  cbb schema --type filters
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ========================================
    # Command: datasets
    # ========================================
    parser_datasets = subparsers.add_parser("datasets", help="List all available datasets")
    parser_datasets.set_defaults(func=cmd_list_datasets)

    # ========================================
    # Command: get
    # ========================================
    parser_get = subparsers.add_parser("get", help="Query a dataset with filters")
    parser_get.add_argument(
        "dataset", help="Dataset ID (e.g., schedule, player_game, player_season)"
    )
    parser_get.add_argument(
        "--league",
        required=True,
        choices=list(LEAGUE_LEVELS.keys()),
        help="League identifier",
    )
    parser_get.add_argument("--season", help="Season year OR 'this season', 'last season'")
    parser_get.add_argument("--team", nargs="+", help="Team names to filter")
    parser_get.add_argument("--player", nargs="+", help="Player names to filter")
    parser_get.add_argument("--date-from", help="Start date OR 'yesterday', 'last week'")
    parser_get.add_argument("--date-to", help="End date OR 'today'")
    parser_get.add_argument(
        "--per-mode",
        choices=["Totals", "PerGame", "Per40"],
        help="Aggregation mode for season stats",
    )
    parser_get.add_argument(
        "--limit", type=int, default=100, help="Maximum rows to return (default: 100)"
    )
    parser_get.add_argument(
        "--output",
        choices=["table", "json", "csv", "dataframe"],
        default="table",
        help="Output format (default: table)",
    )
    parser_get.set_defaults(func=cmd_get_dataset)

    # ========================================
    # Command: recent
    # ========================================
    parser_recent = subparsers.add_parser("recent", help="Get recent games for a league")
    parser_recent.add_argument(
        "league", choices=list(LEAGUE_LEVELS.keys()), help="League identifier"
    )
    parser_recent.add_argument(
        "--days",
        default="2",
        help="Number of days OR 'today', 'last week', 'last 5 days' (default: 2)",
    )
    parser_recent.add_argument("--teams", nargs="+", help="Team names to filter")
    parser_recent.add_argument(
        "--output",
        choices=["table", "json", "csv", "dataframe"],
        default="table",
        help="Output format (default: table)",
    )
    parser_recent.set_defaults(func=cmd_recent_games)

    # ========================================
    # Command: schema
    # ========================================
    parser_schema = subparsers.add_parser("schema", help="Show API schemas and documentation")
    parser_schema.add_argument(
        "--type",
        choices=["all", "datasets", "filters", "natural-language"],
        default="all",
        help="Schema type to display (default: all)",
    )
    parser_schema.set_defaults(func=cmd_show_schema)

    # ========================================
    # Command: warm-cache
    # ========================================
    parser_warm = subparsers.add_parser("warm-cache", help="Warm the cache with popular queries")
    parser_warm.add_argument(
        "--teams", nargs="+", help="Additional teams to warm (e.g., Duke UNC Kansas)"
    )
    parser_warm.set_defaults(func=cmd_warm_cache)

    # Parse args and execute command
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
