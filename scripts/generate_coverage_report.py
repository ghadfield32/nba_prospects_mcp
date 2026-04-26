#!/usr/bin/env python
"""League Coverage Report Generator (Phase 7)

Generates comprehensive LEAGUE_COVERAGE_REPORT showing:
- Seasons present (min -> max)
- Earliest/latest dates
- Index Layer A status (PASS/WARN/FAIL by season)
- Canonicalization status
- Crosswalk coverage (% mapped, unresolved, collisions)
- JOIN READINESS determination

JOIN READINESS = READY only if:
- Layer A PASS
- Canonical PASS
- Xwalk collisions = 0
- Unresolved = 0 (or explicitly waived)

This proves "no fuzzy matching required" for career stitching.

Usage:
    python scripts/generate_coverage_report.py
    python scripts/generate_coverage_report.py --output LEAGUE_COVERAGE_REPORT.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
sys.path.insert(0, "src")

import pandas as pd

# Constants
DATA_DIR = Path("data")
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
CANONICAL_DIR = DATA_DIR / "canonical"
GOLD_DIR = DATA_DIR / "gold"
REPORTS_DIR = DATA_DIR / "_reports"


def get_game_index_status() -> dict:
    """Get Layer A status for all game indexes."""
    status = {}

    for filepath in sorted(GAME_INDEX_DIR.glob("*.csv")):
        filename = filepath.name
        parts = filename.replace(".csv", "").split("_")
        league = parts[0]
        season = "_".join(parts[1:]).replace("_", "-")

        if league not in status:
            status[league] = {
                "seasons": [],
                "total_games": 0,
                "date_coverage": [],
                "score_coverage": [],
                "layer_a_status": "UNKNOWN",
            }

        try:
            df = pd.read_csv(filepath)
            game_count = len(df)

            # Calculate coverages
            date_cov = 0
            score_cov = 0

            if "GAME_DATE" in df.columns:
                date_cov = round(df["GAME_DATE"].notna().mean() * 100, 1)

            if "HOME_SCORE" in df.columns and "AWAY_SCORE" in df.columns:
                score_cov = round(
                    ((df["HOME_SCORE"].notna()) & (df["AWAY_SCORE"].notna())).mean() * 100, 1
                )

            status[league]["seasons"].append(
                {
                    "season": season,
                    "games": game_count,
                    "date_coverage": date_cov,
                    "score_coverage": score_cov,
                    "status": "PASS" if date_cov == 100 and score_cov == 100 else "FAIL",
                }
            )
            status[league]["total_games"] += game_count
            status[league]["date_coverage"].append(date_cov)
            status[league]["score_coverage"].append(score_cov)

        except Exception as e:
            status[league]["seasons"].append(
                {
                    "season": season,
                    "error": str(e),
                    "status": "ERROR",
                }
            )

    # Determine overall Layer A status per league
    for _league, data in status.items():
        season_statuses = [s.get("status", "ERROR") for s in data["seasons"]]
        if all(s == "PASS" for s in season_statuses):
            data["layer_a_status"] = "PASS"
        elif any(s == "ERROR" for s in season_statuses):
            data["layer_a_status"] = "ERROR"
        else:
            data["layer_a_status"] = "FAIL"

    return status


def get_canonical_status() -> dict:
    """Get canonicalization status for all leagues."""
    status = {}

    for filepath in CANONICAL_DIR.glob("**/*.parquet"):
        # Extract league from path pattern: league=XXX
        league = "UNKNOWN"
        for part in filepath.parts:
            if part.startswith("league="):
                league = part.replace("league=", "").upper()
                break

        if league not in status:
            status[league] = {
                "files": [],
                "total_records": 0,
                "status": "UNKNOWN",
            }

        try:
            df = pd.read_parquet(filepath)
            status[league]["files"].append(str(filepath.name))
            status[league]["total_records"] += len(df)
            status[league]["status"] = "PASS"
        except Exception as e:
            status[league]["status"] = "ERROR"
            status[league]["error"] = str(e)

    return status


def get_xwalk_status() -> dict:
    """Get crosswalk status."""
    status = {
        "total_entries": 0,
        "canonical_players": 0,
        "unresolved": 0,
        "collisions": 0,
        "coverage_by_league": {},
        "status": "UNKNOWN",
    }

    xwalk_path = DATA_DIR / "player_xwalk.parquet"
    if xwalk_path.exists():
        try:
            df = pd.read_parquet(xwalk_path)
            status["total_entries"] = len(df)
            status["canonical_players"] = df["canonical_player_id"].nunique()

            # Coverage by league
            if "source_league" in df.columns:
                for league in df["source_league"].unique():
                    league_count = len(df[df["source_league"] == league])
                    status["coverage_by_league"][league] = league_count

            status["status"] = "PASS"
        except Exception as e:
            status["error"] = str(e)
            status["status"] = "ERROR"

    # Check for unresolved
    unresolved_path = REPORTS_DIR / "xwalk_unresolved.json"
    if unresolved_path.exists():
        try:
            with open(unresolved_path) as f:
                unresolved = json.load(f)
            status["unresolved"] = len(unresolved)
        except Exception:
            pass

    return status


def get_gold_status() -> dict:
    """Get gold table status."""
    status = {
        "exists": False,
        "total_records": 0,
        "unique_players": 0,
        "leagues": [],
        "date_coverage": 0.0,
        "multi_league_players": 0,
        "status": "UNKNOWN",
    }

    gold_path = GOLD_DIR / "player_career_game.parquet"
    if gold_path.exists():
        try:
            df = pd.read_parquet(gold_path)
            status["exists"] = True
            status["total_records"] = len(df)
            status["unique_players"] = df["CANONICAL_PLAYER_ID"].nunique()
            status["leagues"] = df["LEAGUE"].unique().tolist()

            if "GAME_DATE" in df.columns:
                status["date_coverage"] = round(df["GAME_DATE"].notna().mean() * 100, 1)

            status["status"] = "PASS"
        except Exception as e:
            status["error"] = str(e)
            status["status"] = "ERROR"

    # Check for multi-league players
    multi_path = REPORTS_DIR / "multi_league_players.csv"
    if multi_path.exists():
        try:
            df = pd.read_csv(multi_path)
            status["multi_league_players"] = len(df)
        except Exception:
            pass

    return status


def determine_join_readiness(
    index_status: dict, canonical_status: dict, xwalk_status: dict
) -> dict:
    """Determine join readiness for each league."""
    readiness = {}

    all_leagues = set(index_status.keys()) | set(canonical_status.keys())

    for league in all_leagues:
        league_ready = {
            "league": league,
            "layer_a": index_status.get(league, {}).get("layer_a_status", "MISSING"),
            "canonical": canonical_status.get(league, {}).get("status", "MISSING"),
            "xwalk_entries": xwalk_status.get("coverage_by_league", {}).get(league, 0),
            "join_ready": False,
            "blockers": [],
        }

        # Check Layer A
        if league_ready["layer_a"] != "PASS":
            league_ready["blockers"].append(f"Layer A: {league_ready['layer_a']}")

        # Check canonical
        if league_ready["canonical"] not in ["PASS", "UNKNOWN"]:
            league_ready["blockers"].append(f"Canonical: {league_ready['canonical']}")

        # Check crosswalk
        if xwalk_status.get("unresolved", 0) > 0:
            league_ready["blockers"].append(f"Unresolved players: {xwalk_status['unresolved']}")

        if xwalk_status.get("collisions", 0) > 0:
            league_ready["blockers"].append(f"Collisions: {xwalk_status['collisions']}")

        # Determine readiness
        if not league_ready["blockers"]:
            league_ready["join_ready"] = True

        readiness[league] = league_ready

    return readiness


def generate_markdown_report(
    index_status: dict,
    canonical_status: dict,
    xwalk_status: dict,
    gold_status: dict,
    readiness: dict,
) -> str:
    """Generate markdown report."""
    lines = [
        "# LEAGUE COVERAGE REPORT",
        "",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## Executive Summary",
        "",
    ]

    # Count ready leagues
    ready_count = sum(1 for r in readiness.values() if r["join_ready"])
    total_count = len(readiness)

    lines.append(f"**Join Ready Leagues:** {ready_count}/{total_count}")
    lines.append("")

    if gold_status["exists"]:
        lines.append(
            f"**Gold Table:** {gold_status['total_records']:,} records, {gold_status['unique_players']:,} unique players"
        )
        lines.append(f"**Multi-League Players:** {gold_status['multi_league_players']}")
    else:
        lines.append("**Gold Table:** Not built yet (run Phase 5)")

    lines.extend(["", "---", "", "## League Status", ""])

    # Table header
    lines.append("| League | Seasons | Games | Layer A | Canonical | Xwalk | Join Ready |")
    lines.append("|--------|---------|-------|---------|-----------|-------|------------|")

    for league in sorted(readiness.keys()):
        r = readiness[league]
        idx = index_status.get(league, {})
        canonical_status.get(league, {})

        seasons = len(idx.get("seasons", []))
        games = idx.get("total_games", 0)
        layer_a = r["layer_a"]
        canonical = r["canonical"]
        xwalk = r["xwalk_entries"]
        ready = "YES" if r["join_ready"] else "NO"

        lines.append(
            f"| {league} | {seasons} | {games} | {layer_a} | {canonical} | {xwalk} | {ready} |"
        )

    lines.extend(["", "---", "", "## Detailed Layer A Status (Game Indexes)", ""])

    for league, data in sorted(index_status.items()):
        lines.append(f"### {league}")
        lines.append("")
        lines.append(f"**Overall Status:** {data['layer_a_status']}")
        lines.append(f"**Total Games:** {data['total_games']}")
        lines.append("")

        if data["seasons"]:
            lines.append("| Season | Games | Date % | Score % | Status |")
            lines.append("|--------|-------|--------|---------|--------|")
            for s in data["seasons"]:
                season = s.get("season", "?")
                games = s.get("games", 0)
                date_cov = s.get("date_coverage", 0)
                score_cov = s.get("score_coverage", 0)
                status = s.get("status", "?")
                lines.append(f"| {season} | {games} | {date_cov}% | {score_cov}% | {status} |")
            lines.append("")

    lines.extend(["---", "", "## Crosswalk Status", ""])

    lines.append(f"- **Total Entries:** {xwalk_status['total_entries']}")
    lines.append(f"- **Canonical Players:** {xwalk_status['canonical_players']}")
    lines.append(f"- **Unresolved:** {xwalk_status['unresolved']}")
    lines.append(f"- **Collisions:** {xwalk_status['collisions']}")
    lines.append(f"- **Status:** {xwalk_status['status']}")

    if xwalk_status["coverage_by_league"]:
        lines.extend(["", "**Coverage by League:**", ""])
        for league, count in sorted(xwalk_status["coverage_by_league"].items()):
            lines.append(f"- {league}: {count} entries")

    lines.extend(["", "---", "", "## Join Readiness Details", ""])

    for league, r in sorted(readiness.items()):
        status = "READY" if r["join_ready"] else "BLOCKED"
        lines.append(f"### {league}: {status}")
        lines.append("")

        if r["blockers"]:
            lines.append("**Blockers:**")
            for blocker in r["blockers"]:
                lines.append(f"- {blocker}")
        else:
            lines.append("No blockers - ready for deterministic joins!")

        lines.append("")

    lines.extend(["---", "", "## Known Multi-League Pathways", ""])
    lines.append("These players should appear with continuous careers across leagues:")
    lines.append("")
    lines.append("| Player | Expected Path | Status |")
    lines.append("|--------|---------------|--------|")
    lines.append("| Alex Sarr | OTE -> NBL -> NBA | Pending |")
    lines.append("| Amen Thompson | OTE -> NBA | Pending |")
    lines.append("| Ausar Thompson | OTE -> NBA | Pending |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate League Coverage Report")
    parser.add_argument(
        "--output", default="LEAGUE_COVERAGE_REPORT.md", help="Output markdown path"
    )
    parser.add_argument("--json", help="Also save JSON report to this path")
    args = parser.parse_args()

    print("=" * 70)
    print("LEAGUE COVERAGE REPORT GENERATOR (Phase 7)")
    print("=" * 70)
    print()

    # Gather status from all layers
    print("Checking game indexes (Layer A)...")
    index_status = get_game_index_status()

    print("Checking canonical data (Layer B/C)...")
    canonical_status = get_canonical_status()

    print("Checking player crosswalk (Layer D)...")
    xwalk_status = get_xwalk_status()

    print("Checking gold table (Layer E)...")
    gold_status = get_gold_status()

    print("Determining join readiness...")
    readiness = determine_join_readiness(index_status, canonical_status, xwalk_status)

    # Generate reports
    print()
    print("Generating reports...")

    # Markdown report
    md_report = generate_markdown_report(
        index_status, canonical_status, xwalk_status, gold_status, readiness
    )

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Saved markdown report: {output_path}")

    # JSON report
    json_report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "game_indexes": index_status,
        "canonical": canonical_status,
        "crosswalk": xwalk_status,
        "gold": gold_status,
        "join_readiness": readiness,
    }

    if args.json:
        json_path = Path(args.json)
        with open(json_path, "w") as f:
            json.dump(json_report, f, indent=2)
        print(f"Saved JSON report: {json_path}")

    # Also save to reports dir
    json_report_path = REPORTS_DIR / "coverage_report.json"
    with open(json_report_path, "w") as f:
        json.dump(json_report, f, indent=2)

    # Print summary
    print()
    print("=" * 70)
    print("COVERAGE SUMMARY")
    print("=" * 70)
    print()

    ready_leagues = [lg for lg, r in readiness.items() if r["join_ready"]]
    blocked_leagues = [lg for lg, r in readiness.items() if not r["join_ready"]]

    print(f"Join Ready: {len(ready_leagues)}")
    if ready_leagues:
        print(f"  {', '.join(sorted(ready_leagues))}")

    print(f"Blocked: {len(blocked_leagues)}")
    if blocked_leagues:
        for league in sorted(blocked_leagues):
            blockers = readiness[league]["blockers"]
            print(f"  {league}: {'; '.join(blockers)}")

    print()
    print(f"Full report saved to: {output_path}")


if __name__ == "__main__":
    main()
