#!/usr/bin/env python
"""League Data Health Dashboard

One-command health report for all basketball data sources.
Tests endpoints, reports coverage, identifies issues.

Usage:
    python scripts/league_data_health.py
    python scripts/league_data_health.py --league acb
    python scripts/league_data_health.py --format json
    python scripts/league_data_health.py --output health_report.json

Output:
    - Console summary with color-coded status
    - Optional JSON export for automation
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")


from cbb_data.fetchers import DataUnavailableError


def check_acb_health() -> dict[str, Any]:
    """Check ACB (Spanish Liga Endesa) data health."""
    from cbb_data.fetchers import acb

    result = {
        "league": "ACB",
        "region": "Spain",
        "status": "OK",
        "endpoints": {},
        "coverage": {},
        "issues": [],
    }

    # Check schedule endpoint
    try:
        df = acb.fetch_acb_schedule(season="2024")
        games = len(df) if not df.empty else 0
        result["endpoints"]["schedule"] = {"status": "OK", "count": games}
        result["coverage"]["2024_games"] = games
    except Exception as e:
        result["endpoints"]["schedule"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Schedule: {type(e).__name__}")

    # Check player season stats
    try:
        df = acb.fetch_acb_player_season(season="2024")
        players = len(df) if not df.empty else 0
        result["endpoints"]["player_season"] = {"status": "OK", "count": players}
        result["coverage"]["2024_players"] = players
    except Exception as e:
        result["endpoints"]["player_season"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Player season: {type(e).__name__}")

    # Check team season stats
    try:
        df = acb.fetch_acb_team_season(season="2024")
        teams = len(df) if not df.empty else 0
        result["endpoints"]["team_season"] = {"status": "OK", "count": teams}
        result["coverage"]["2024_teams"] = teams
    except Exception as e:
        result["endpoints"]["team_season"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Team season: {type(e).__name__}")

    # Check BAwiR availability (PBP/shots)
    rpy2_available = getattr(acb, "RPY2_AVAILABLE", False)
    result["endpoints"]["pbp_shots"] = {
        "status": "OK" if rpy2_available else "UNAVAILABLE",
        "note": "BAwiR via rpy2" if rpy2_available else "rpy2 not installed",
    }

    # Overall status
    if result["issues"]:
        result["status"] = "DEGRADED"

    return result


def check_lnb_health() -> dict[str, Any]:
    """Check LNB (French Pro A) data health."""
    from cbb_data.fetchers import lnb

    result = {
        "league": "LNB",
        "region": "France",
        "status": "OK",
        "endpoints": {},
        "coverage": {},
        "issues": [],
    }

    # Check schedule v2 (API)
    try:
        df = lnb.fetch_lnb_schedule_v2(season=2025)
        games = len(df) if not df.empty else 0
        result["endpoints"]["schedule"] = {"status": "OK", "count": games}
        result["coverage"]["2024-25_games"] = games
    except Exception as e:
        result["endpoints"]["schedule"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Schedule: {type(e).__name__}")

    # Check player season
    try:
        df = lnb.fetch_lnb_player_season(season="2024")
        players = len(df) if not df.empty else 0
        result["endpoints"]["player_season"] = {"status": "OK", "count": players}
        result["coverage"]["2024_players"] = players
    except Exception as e:
        result["endpoints"]["player_season"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Player season: {type(e).__name__}")

    # Check team season
    try:
        df = lnb.fetch_lnb_team_season(season="2024")
        teams = len(df) if not df.empty else 0
        result["endpoints"]["team_season"] = {"status": "OK", "count": teams}
        result["coverage"]["2024_teams"] = teams
    except Exception as e:
        result["endpoints"]["team_season"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Team season: {type(e).__name__}")

    # Check PBP historical
    try:
        df = lnb.fetch_lnb_pbp_historical(season="2024")
        events = len(df) if not df.empty else 0
        result["endpoints"]["pbp_historical"] = {"status": "OK", "count": events}
    except Exception as e:
        result["endpoints"]["pbp_historical"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"PBP historical: {type(e).__name__}")

    # Overall status
    if result["issues"]:
        result["status"] = "DEGRADED"

    return result


def check_nz_nbl_health() -> dict[str, Any]:
    """Check NZ-NBL (New Zealand NBL) data health."""
    from cbb_data.fetchers import nz_nbl_fiba

    result = {
        "league": "NZ-NBL",
        "region": "New Zealand",
        "status": "OK",
        "endpoints": {},
        "coverage": {},
        "issues": [],
        "notes": [],
    }

    # Check Playwright availability
    playwright_available = getattr(nz_nbl_fiba, "PLAYWRIGHT_AVAILABLE", False)
    result["endpoints"]["schedule_discovery"] = {
        "status": "OK" if playwright_available else "LIMITED",
        "note": "Playwright available"
        if playwright_available
        else "Install playwright for full discovery",
    }

    # Try schedule for available seasons
    for season in ["2024", "2023"]:
        try:
            df = nz_nbl_fiba.fetch_nz_nbl_schedule_full(season=season)
            games = len(df) if not df.empty else 0
            if games > 0:
                result["coverage"][f"{season}_games"] = games
                result["endpoints"]["schedule"] = {"status": "OK", "count": games, "season": season}
                break
        except DataUnavailableError as e:
            if e.kind == "access_forbidden":
                result["endpoints"]["schedule"] = {"status": "FORBIDDEN", "error": "403 from FIBA"}
                result["issues"].append("FIBA LiveStats access restricted")
            elif e.kind == "no_games_for_season":
                result["notes"].append(f"{season}: No games (off-season)")
        except Exception as e:
            result["endpoints"]["schedule"] = {"status": "ERROR", "error": str(e)[:100]}
            result["issues"].append(f"Schedule: {type(e).__name__}")
            break
    else:
        if "schedule" not in result["endpoints"]:
            result["endpoints"]["schedule"] = {
                "status": "NO_DATA",
                "note": "No games found for 2024/2023",
            }
            result["notes"].append("NZ-NBL season runs May-August")

    # Check player season (faster than schedule)
    for season in ["2024", "2023"]:
        try:
            df = nz_nbl_fiba.fetch_nz_nbl_player_season(season=season)
            players = len(df) if not df.empty else 0
            if players > 0:
                result["coverage"][f"{season}_players"] = players
                result["endpoints"]["player_season"] = {"status": "OK", "count": players}
                break
        except Exception:
            pass

    # Overall status
    if result["issues"]:
        result["status"] = "DEGRADED"
    elif not result["coverage"]:
        result["status"] = "NO_DATA"

    return result


def check_euroleague_health() -> dict[str, Any]:
    """Check Euroleague data health."""
    from cbb_data.fetchers import euroleague

    result = {
        "league": "Euroleague",
        "region": "Europe",
        "status": "OK",
        "endpoints": {},
        "coverage": {},
        "issues": [],
    }

    # Check schedule
    try:
        df = euroleague.fetch_euroleague_schedule(season="2024")
        games = len(df) if not df.empty else 0
        result["endpoints"]["schedule"] = {"status": "OK", "count": games}
        result["coverage"]["2024_games"] = games
    except Exception as e:
        result["endpoints"]["schedule"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Schedule: {type(e).__name__}")

    # Check player game
    try:
        df = euroleague.fetch_euroleague_player_game(season="2024")
        records = len(df) if not df.empty else 0
        result["endpoints"]["player_game"] = {"status": "OK", "count": records}
        result["coverage"]["2024_player_games"] = records
    except Exception as e:
        result["endpoints"]["player_game"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Player game: {type(e).__name__}")

    # Overall status
    if result["issues"]:
        result["status"] = "DEGRADED"

    return result


def check_nbl_health() -> dict[str, Any]:
    """Check NBL (Australia) data health."""
    from cbb_data.fetchers import nbl

    result = {
        "league": "NBL",
        "region": "Australia",
        "status": "OK",
        "endpoints": {},
        "coverage": {},
        "issues": [],
    }

    # Check schedule
    try:
        df = nbl.fetch_nbl_schedule(season="2024")
        games = len(df) if not df.empty else 0
        result["endpoints"]["schedule"] = {"status": "OK", "count": games}
        result["coverage"]["2024_games"] = games
    except Exception as e:
        result["endpoints"]["schedule"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Schedule: {type(e).__name__}")

    # Check player game
    try:
        df = nbl.fetch_nbl_player_game(season="2024")
        records = len(df) if not df.empty else 0
        result["endpoints"]["player_game"] = {"status": "OK", "count": records}
        result["coverage"]["2024_player_games"] = records
    except Exception as e:
        result["endpoints"]["player_game"] = {"status": "ERROR", "error": str(e)[:100]}
        result["issues"].append(f"Player game: {type(e).__name__}")

    # Overall status
    if result["issues"]:
        result["status"] = "DEGRADED"

    return result


def run_health_checks(leagues: list[str] | None = None) -> dict[str, Any]:
    """Run health checks for specified leagues.

    Args:
        leagues: List of league codes to check (None = all)

    Returns:
        Health report dictionary
    """
    all_checkers = {
        "acb": check_acb_health,
        "lnb": check_lnb_health,
        "nz-nbl": check_nz_nbl_health,
        "euroleague": check_euroleague_health,
        "nbl": check_nbl_health,
    }

    if leagues:
        checkers = {k: v for k, v in all_checkers.items() if k in leagues}
    else:
        checkers = all_checkers

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "leagues": {},
        "summary": {
            "total": len(checkers),
            "healthy": 0,
            "degraded": 0,
            "no_data": 0,
        },
    }

    for code, checker in checkers.items():
        print(f"  Checking {code.upper()}...", end=" ", flush=True)
        start = time.time()

        try:
            result = checker()
            elapsed = time.time() - start
            result["check_time_seconds"] = round(elapsed, 2)
            report["leagues"][code] = result

            # Update summary
            if result["status"] == "OK":
                report["summary"]["healthy"] += 1
                status_icon = "OK"
            elif result["status"] == "DEGRADED":
                report["summary"]["degraded"] += 1
                status_icon = "DEGRADED"
            else:
                report["summary"]["no_data"] += 1
                status_icon = "NO_DATA"

            print(f"{status_icon} ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - start
            report["leagues"][code] = {
                "league": code.upper(),
                "status": "ERROR",
                "error": str(e),
                "check_time_seconds": round(elapsed, 2),
            }
            report["summary"]["degraded"] += 1
            print(f"ERROR ({elapsed:.1f}s)")

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print formatted health report to console."""
    print()
    print("=" * 70)
    print("LEAGUE DATA HEALTH REPORT")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print()

    summary = report["summary"]
    print(
        f"Summary: {summary['healthy']}/{summary['total']} healthy, "
        f"{summary['degraded']} degraded, {summary['no_data']} no data"
    )
    print()

    for _code, data in report["leagues"].items():
        print(f"{data['league']} ({data.get('region', 'Unknown')}):")
        print(f"  Status: {data['status']}")

        if "coverage" in data and data["coverage"]:
            print(f"  Coverage: {data['coverage']}")

        if "issues" in data and data["issues"]:
            print(f"  Issues: {', '.join(data['issues'])}")

        if "notes" in data and data["notes"]:
            for note in data["notes"]:
                print(f"  Note: {note}")

        print(f"  Check time: {data.get('check_time_seconds', 0):.1f}s")
        print()


def main():
    parser = argparse.ArgumentParser(description="League Data Health Dashboard")
    parser.add_argument(
        "--league", help="Specific league to check (acb, lnb, nz-nbl, euroleague, nbl)"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", help="Output file path (optional)")
    args = parser.parse_args()

    print("=" * 70)
    print("LEAGUE DATA HEALTH CHECK")
    print("=" * 70)
    print()

    start = time.time()

    leagues = [args.league.lower()] if args.league else None
    report = run_health_checks(leagues)

    elapsed = time.time() - start
    report["total_time_seconds"] = round(elapsed, 2)

    if args.format == "json":
        output = json.dumps(report, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"\nSaved to: {args.output}")
        else:
            print(output)
    else:
        print_report(report)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Saved JSON to: {args.output}")

    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
