#!/usr/bin/env python
"""League Coverage Audit Script (Phase 0)

Comprehensive audit of all basketball league data across both data directories.
Generates coverage matrix showing status of game_indexes, canonical data,
crosswalks, and validation player presence for each league.

Usage:
    python scripts/audit_league_coverage.py
    python scripts/audit_league_coverage.py --output-dir /path/to/reports

Output:
    - data/_reports/league_coverage.parquet (structured data)
    - LEAGUE_COVERAGE_MATRIX.md (human-readable report)
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

# ============================================================================
# Configuration
# ============================================================================

# Data directories to scan
BASE_DIR = Path(__file__).parent.parent.parent  # betts_basketball
DATA_DIRS = [
    BASE_DIR / "nba_prospects_mcp" / "data",
    BASE_DIR / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp" / "data",
    BASE_DIR / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp" / "cache",
]

# All leagues to audit (from plan)
ALL_LEAGUES = [
    "NBL",  # Australia - Most complete (47 seasons)
    "ABA",  # Adriatic League - 24 seasons indexed
    "BCL",  # Basketball Champions League - 10 seasons
    "BAL",  # Basketball Africa League - 5 seasons
    "LKL",  # Lithuanian League - 9 seasons
    "EUROLEAGUE",  # Europe - gaps 2014-17
    "EUROCUP",  # Europe - 3 seasons only
    "OTE",  # Overtime Elite - BROKEN
    "G_LEAGUE",  # G-League
    "NCAA_MBB",  # NCAA Men's Basketball
    "ACB",  # Spanish Liga - cache only
    "LNB",  # French Pro A - most granular
    "LNB_PROA",  # LNB division
    "CEBL",  # Canada
    "WNBA",  # Women's NBA
    "BBL",  # Turkey
    "NZ_NBL",  # New Zealand
]

# League aliases for matching
LEAGUE_ALIASES = {
    "G-LEAGUE": "G_LEAGUE",
    "G-League": "G_LEAGUE",
    "G_League": "G_LEAGUE",
    "NCAA-MBB": "NCAA_MBB",
    "NCAA MBB": "NCAA_MBB",
    "NZ-NBL": "NZ_NBL",
    "LNB ProA": "LNB_PROA",
    "LNB_ProA": "LNB_PROA",
}

# Validation players from plan (PLAYER_UID system)
VALIDATION_PLAYERS = {
    "alex_sarr": {
        "birth_year": 2005,
        "expected_leagues": ["OTE", "NBL", "NBA"],
        "expected_seasons": ["2022-23", "2023-24", "2024-25"],
        "pathway": "OTE -> NBL -> NBA",
    },
    "luka_doncic": {
        "birth_year": 1999,
        "expected_leagues": ["ACB", "EUROLEAGUE", "NBA"],
        "expected_seasons": ["2015-16", "2016-17", "2017-18", "2018+"],
        "pathway": "ACB/EuroLeague -> NBA",
    },
    "ricky_rubio": {
        "birth_year": 1990,
        "expected_leagues": ["ACB", "NBA"],
        "expected_seasons": ["2005-09", "2011+"],
        "pathway": "ACB -> NBA",
    },
    "nikola_jokic": {
        "birth_year": 1995,
        "expected_leagues": ["ABA", "NBA"],
        "expected_seasons": ["2012-15", "2015+"],
        "pathway": "ABA -> NBA",
    },
    "nikola_jovic": {
        "birth_year": 2003,
        "expected_leagues": ["ABA", "NBA"],
        "expected_seasons": ["2020-22", "2022+"],
        "pathway": "ABA -> NBA",
    },
    "lamelo_ball": {
        "birth_year": 2001,
        "expected_leagues": ["NBL", "NBA"],
        "expected_seasons": ["2019-20", "2020+"],
        "pathway": "NBL -> NBA",
    },
    "josh_giddey": {
        "birth_year": 2002,
        "expected_leagues": ["NBL", "NBA"],
        "expected_seasons": ["2020-21", "2021+"],
        "pathway": "NBL -> NBA",
    },
    "jalen_green": {
        "birth_year": 2002,
        "expected_leagues": ["G_LEAGUE", "NBA"],
        "expected_seasons": ["2020-21", "2021+"],
        "pathway": "G-League Ignite -> NBA",
    },
    "paolo_banchero": {
        "birth_year": 2002,
        "expected_leagues": ["NCAA_MBB", "NBA"],
        "expected_seasons": ["2021-22", "2022+"],
        "pathway": "NCAA (Duke) -> NBA",
    },
    "victor_wembanyama": {
        "birth_year": 2004,
        "expected_leagues": ["LNB_PROA", "LNB", "NBA"],
        "expected_seasons": ["2021-23", "2023+"],
        "pathway": "LNB -> NBA",
    },
    "alperen_sengun": {
        "birth_year": 2002,
        "expected_leagues": ["BCL", "NBA"],
        "expected_seasons": ["2020-21", "2021+"],
        "pathway": "BCL (Besiktas) -> NBA",
    },
}


# ============================================================================
# Scanning Functions
# ============================================================================


def normalize_league(league: str) -> str:
    """Normalize league name to standard format."""
    league = league.upper().replace("-", "_").replace(" ", "_")
    return LEAGUE_ALIASES.get(league, league)


def parse_league_season_from_filename(filename: str) -> tuple[str, str]:
    """Parse league and season from game index filename.

    Handles multi-part league names like G_LEAGUE, NCAA_MBB, LNB_PROA.

    Examples:
        NBL_2024_2025 -> ("NBL", "2024-2025")
        G_LEAGUE_2015 -> ("G_LEAGUE", "2015")
        NCAA_MBB_2024 -> ("NCAA_MBB", "2024")
        ABA_2001_02 -> ("ABA", "2001-02")
    """
    # Known multi-part league prefixes
    MULTI_PART_LEAGUES = [
        "G_LEAGUE",
        "NCAA_MBB",
        "NCAA_WBB",
        "LNB_PROA",
        "LNB_ELITE2",
        "LNB_ESPOIRS_ELITE",
        "LNB_ESPOIRS_PRO",
        "NZ_NBL",
    ]

    # Check for multi-part league names first
    for league in MULTI_PART_LEAGUES:
        if filename.upper().startswith(league + "_"):
            season_part = filename[len(league) + 1 :]  # Skip league and underscore
            season = season_part.replace("_", "-")
            return league, season

    # Standard single-part league
    parts = filename.split("_")
    if len(parts) < 2:
        return filename, ""

    league = parts[0]
    season = "_".join(parts[1:]).replace("_", "-")
    return league.upper(), season


def scan_game_indexes() -> dict[str, dict[str, Any]]:
    """Scan all game index files across data directories."""
    indexes = defaultdict(
        lambda: {
            "seasons": [],
            "total_games": 0,
            "files": [],
            "date_coverage_pct": [],
            "score_coverage_pct": [],
            "earliest_date": None,
            "latest_date": None,
        }
    )

    patterns = ["game_indexes/*.csv", "game_indexes/*.parquet"]

    for data_dir in DATA_DIRS:
        if not data_dir.exists():
            continue

        for pattern in patterns:
            for filepath in data_dir.glob(pattern):
                filename = filepath.stem
                # Parse league and season from filename
                league, season = parse_league_season_from_filename(filename)
                league = normalize_league(league)

                if not league or not season:
                    continue

                try:
                    if filepath.suffix == ".csv":
                        df = pd.read_csv(filepath)
                    else:
                        df = pd.read_parquet(filepath)

                    game_count = len(df)

                    # Calculate coverages
                    date_cov = 0.0
                    score_cov = 0.0

                    if "GAME_DATE" in df.columns:
                        date_cov = round(df["GAME_DATE"].notna().mean() * 100, 1)
                        dates = pd.to_datetime(df["GAME_DATE"], errors="coerce")
                        valid_dates = dates.dropna()
                        if len(valid_dates) > 0:
                            if indexes[league]["earliest_date"] is None:
                                indexes[league]["earliest_date"] = valid_dates.min()
                            else:
                                indexes[league]["earliest_date"] = min(
                                    indexes[league]["earliest_date"], valid_dates.min()
                                )
                            if indexes[league]["latest_date"] is None:
                                indexes[league]["latest_date"] = valid_dates.max()
                            else:
                                indexes[league]["latest_date"] = max(
                                    indexes[league]["latest_date"], valid_dates.max()
                                )

                    if "HOME_SCORE" in df.columns and "AWAY_SCORE" in df.columns:
                        score_cov = round(
                            ((df["HOME_SCORE"].notna()) & (df["AWAY_SCORE"].notna())).mean() * 100,
                            1,
                        )

                    indexes[league]["seasons"].append(
                        {
                            "season": season,
                            "games": game_count,
                            "date_coverage": date_cov,
                            "score_coverage": score_cov,
                            "file": str(filepath),
                        }
                    )
                    indexes[league]["total_games"] += game_count
                    indexes[league]["files"].append(str(filepath))
                    indexes[league]["date_coverage_pct"].append(date_cov)
                    indexes[league]["score_coverage_pct"].append(score_cov)

                except Exception as e:
                    indexes[league]["seasons"].append(
                        {
                            "season": season,
                            "error": str(e),
                            "file": str(filepath),
                        }
                    )

    # Calculate averages and status
    for _league, data in indexes.items():
        if data["date_coverage_pct"]:
            data["avg_date_coverage"] = round(
                sum(data["date_coverage_pct"]) / len(data["date_coverage_pct"]), 1
            )
        else:
            data["avg_date_coverage"] = 0.0

        if data["score_coverage_pct"]:
            data["avg_score_coverage"] = round(
                sum(data["score_coverage_pct"]) / len(data["score_coverage_pct"]), 1
            )
        else:
            data["avg_score_coverage"] = 0.0

        # Determine status
        if not data["seasons"]:
            data["status"] = "MISSING"
        elif data["avg_date_coverage"] >= 95 and data["avg_score_coverage"] >= 80:
            data["status"] = "PASS"
        elif data["avg_date_coverage"] >= 80:
            data["status"] = "WARN"
        else:
            data["status"] = "FAIL"

    return dict(indexes)


def scan_canonical_data() -> dict[str, dict[str, Any]]:
    """Scan canonical/silver layer data."""
    canonical = defaultdict(
        lambda: {
            "seasons": [],
            "total_rows": 0,
            "files": [],
            "required_cols_coverage": {},
        }
    )

    patterns = [
        "canonical/box_player_game/league=*/season=*/data.parquet",
        "silver/box_player_game/league=*/season=*/data.parquet",
        "gold/box_player_game/league=*/season=*/data.parquet",
        "canonical/*.parquet",
    ]

    for data_dir in DATA_DIRS:
        if not data_dir.exists():
            continue

        for pattern in patterns:
            for filepath in data_dir.glob(pattern):
                # Extract league from path
                league = "UNKNOWN"
                season = "UNKNOWN"

                for part in filepath.parts:
                    if part.startswith("league="):
                        league = normalize_league(part.replace("league=", ""))
                    if part.startswith("season="):
                        season = part.replace("season=", "")

                # Handle combined files
                if league == "UNKNOWN" and "combined" in filepath.stem:
                    parts = filepath.stem.split("_combined")
                    league = normalize_league(parts[0])
                    season = "combined"

                try:
                    df = pd.read_parquet(filepath)
                    row_count = len(df)

                    # Check required columns
                    required_cols = [
                        "LEAGUE",
                        "SEASON",
                        "GAME_ID",
                        "GAME_DATE",
                        "TEAM_KEY",
                        "SOURCE_PLAYER_ID",
                        "NAME_KEY",
                        "PTS",
                        "FGM",
                        "FGA",
                    ]
                    cols_present = {col: col in df.columns for col in required_cols}

                    canonical[league]["seasons"].append(
                        {
                            "season": season,
                            "rows": row_count,
                            "file": str(filepath),
                            "columns": list(df.columns),
                        }
                    )
                    canonical[league]["total_rows"] += row_count
                    canonical[league]["files"].append(str(filepath))

                    for col, present in cols_present.items():
                        if col not in canonical[league]["required_cols_coverage"]:
                            canonical[league]["required_cols_coverage"][col] = []
                        canonical[league]["required_cols_coverage"][col].append(present)

                except Exception as e:
                    canonical[league]["seasons"].append(
                        {
                            "season": season,
                            "error": str(e),
                            "file": str(filepath),
                        }
                    )

    # Calculate status
    for _league, data in canonical.items():
        if not data["seasons"]:
            data["status"] = "MISSING"
        elif data["total_rows"] > 0:
            # Check required columns coverage
            all_present = True
            for _col, coverage in data["required_cols_coverage"].items():
                if not all(coverage):
                    all_present = False
                    break
            data["status"] = "PASS" if all_present else "WARN"
        else:
            data["status"] = "EMPTY"

    return dict(canonical)


def scan_xwalk_data() -> dict[str, Any]:
    """Scan player crosswalk data."""
    xwalk = {
        "total_entries": 0,
        "unique_players": 0,
        "leagues_covered": set(),
        "entries_by_league": {},
        "files": [],
        "status": "MISSING",
    }

    xwalk_patterns = [
        "player_xwalk.csv",
        "player_xwalk.parquet",
        "identity/player_xwalk.parquet",
        "identity/player_edges.parquet",
    ]

    for data_dir in DATA_DIRS:
        if not data_dir.exists():
            continue

        for pattern in xwalk_patterns:
            filepath = data_dir / pattern
            if filepath.exists():
                try:
                    if filepath.suffix == ".csv":
                        df = pd.read_csv(filepath)
                    else:
                        df = pd.read_parquet(filepath)

                    xwalk["total_entries"] += len(df)
                    xwalk["files"].append(str(filepath))

                    # Count by league
                    league_col = None
                    for col in ["source_league", "SOURCE_LEAGUE", "LEAGUE", "league"]:
                        if col in df.columns:
                            league_col = col
                            break

                    if league_col:
                        for league in df[league_col].unique():
                            norm_league = normalize_league(str(league))
                            xwalk["leagues_covered"].add(norm_league)
                            count = len(df[df[league_col] == league])
                            xwalk["entries_by_league"][norm_league] = (
                                xwalk["entries_by_league"].get(norm_league, 0) + count
                            )

                    # Count unique players
                    player_col = None
                    for col in [
                        "canonical_player_id",
                        "PLAYER_UID",
                        "player_uid",
                        "CANONICAL_PLAYER_ID",
                    ]:
                        if col in df.columns:
                            player_col = col
                            break

                    if player_col:
                        xwalk["unique_players"] = df[player_col].nunique()

                except Exception as e:
                    xwalk["error"] = str(e)

    xwalk["leagues_covered"] = list(xwalk["leagues_covered"])

    if xwalk["total_entries"] > 0:
        xwalk["status"] = "PASS"

    return xwalk


def scan_for_validation_players(canonical_data: dict) -> dict[str, dict[str, Any]]:
    """Check if validation players appear in the data."""
    player_status = {}

    for player_key, player_info in VALIDATION_PLAYERS.items():
        status = {
            "name_key": player_key,
            "birth_year": player_info["birth_year"],
            "expected_leagues": player_info["expected_leagues"],
            "expected_seasons": player_info["expected_seasons"],
            "pathway": player_info["pathway"],
            "found_in_leagues": [],
            "found_seasons": [],
            "status": "NOT_FOUND",
        }

        # Search in canonical data files
        for league, data in canonical_data.items():
            # Check if this is an expected league for this player
            expected = any(
                normalize_league(exp) == league for exp in player_info["expected_leagues"]
            )

            if expected and data.get("total_rows", 0) > 0:
                # We found data for an expected league - mark as potential
                for season_info in data.get("seasons", []):
                    if "file" in season_info:
                        try:
                            df = pd.read_parquet(season_info["file"])
                            # Search for player by name_key
                            name_cols = ["NAME_KEY", "name_key", "PLAYER_NAME", "player_name"]
                            for col in name_cols:
                                if col in df.columns:
                                    # Fuzzy match on name
                                    matches = (
                                        df[col]
                                        .str.lower()
                                        .str.contains(player_key.replace("_", ""), na=False)
                                    )
                                    if matches.any():
                                        status["found_in_leagues"].append(league)
                                        if season_info.get("season"):
                                            status["found_seasons"].append(season_info["season"])
                                        break
                        except Exception:
                            pass

        # Determine status
        status["found_in_leagues"] = list(set(status["found_in_leagues"]))
        status["found_seasons"] = list(set(status["found_seasons"]))

        if status["found_in_leagues"]:
            # Check if we found all expected pre-NBA leagues
            pre_nba_expected = [lg for lg in player_info["expected_leagues"] if lg != "NBA"]
            pre_nba_found = [lg for lg in status["found_in_leagues"] if lg != "NBA"]

            if set(pre_nba_expected) <= set(pre_nba_found):
                status["status"] = "COMPLETE"
            else:
                status["status"] = "PARTIAL"

        player_status[player_key] = status

    return player_status


# ============================================================================
# Report Generation
# ============================================================================


def generate_markdown_report(
    index_data: dict,
    canonical_data: dict,
    xwalk_data: dict,
    player_status: dict,
) -> str:
    """Generate comprehensive markdown report."""
    lines = [
        "# LEAGUE COVERAGE MATRIX",
        "",
        f"**Generated:** {datetime.utcnow().isoformat()}Z",
        "",
        "## Executive Summary",
        "",
    ]

    # Count leagues by status
    index_pass = sum(1 for d in index_data.values() if d.get("status") == "PASS")
    index_total = len([lg for lg in ALL_LEAGUES if lg in index_data])
    canonical_pass = sum(1 for d in canonical_data.values() if d.get("status") == "PASS")

    lines.append(f"- **Game Indexes:** {index_pass}/{index_total} leagues with PASS status")
    lines.append(f"- **Canonical Data:** {canonical_pass} leagues with data")
    lines.append(
        f"- **Crosswalk:** {xwalk_data['total_entries']} entries across {len(xwalk_data['leagues_covered'])} leagues"
    )
    lines.append(
        f"- **Validation Players:** {sum(1 for p in player_status.values() if p['status'] != 'NOT_FOUND')}/11 found"
    )
    lines.append("")

    # League Status Table
    lines.extend(
        [
            "---",
            "",
            "## League Join-Readiness Summary",
            "",
            "| League | Game Index | Seasons | Games | Canonical | Xwalk | Status |",
            "|--------|------------|---------|-------|-----------|-------|--------|",
        ]
    )

    for league in ALL_LEAGUES:
        idx = index_data.get(league, {})
        can = canonical_data.get(league, {})

        idx_status = idx.get("status", "MISSING")
        seasons = len(idx.get("seasons", []))
        games = idx.get("total_games", 0)
        can_status = can.get("status", "MISSING")
        can_rows = can.get("total_rows", 0)
        xwalk_count = xwalk_data.get("entries_by_league", {}).get(league, 0)

        # Determine join readiness
        if idx_status == "PASS" and can_status == "PASS" and xwalk_count > 0:
            join_status = "JOIN READY"
        elif idx_status == "PASS" and can_rows > 0:
            join_status = "NEEDS XWALK"
        elif seasons > 0:
            join_status = "NEEDS CANON"
        else:
            join_status = "NEEDS INDEX"

        lines.append(
            f"| {league} | {idx_status} | {seasons} | {games:,} | "
            f"{can_status} ({can_rows:,}) | {xwalk_count} | {join_status} |"
        )

    # Detailed League Status
    lines.extend(
        [
            "",
            "---",
            "",
            "## Detailed League Status",
            "",
        ]
    )

    for league in ALL_LEAGUES:
        idx = index_data.get(league, {})
        can = canonical_data.get(league, {})

        lines.append(f"### {league}")
        lines.append("")

        # Game Index info
        if idx.get("seasons"):
            lines.append(f"**Game Index:** {idx.get('status', 'UNKNOWN')}")
            lines.append(f"- Seasons: {len(idx['seasons'])}")
            lines.append(f"- Total Games: {idx.get('total_games', 0):,}")
            lines.append(f"- Date Coverage: {idx.get('avg_date_coverage', 0):.1f}%")
            lines.append(f"- Score Coverage: {idx.get('avg_score_coverage', 0):.1f}%")
            if idx.get("earliest_date"):
                lines.append(f"- Date Range: {idx['earliest_date']} to {idx['latest_date']}")
        else:
            lines.append("**Game Index:** MISSING")

        lines.append("")

        # Canonical info
        if can.get("seasons"):
            lines.append(f"**Canonical Data:** {can.get('status', 'UNKNOWN')}")
            lines.append(f"- Files: {len(can['files'])}")
            lines.append(f"- Total Rows: {can.get('total_rows', 0):,}")
        else:
            lines.append("**Canonical Data:** MISSING")

        lines.append("")

    # Validation Players
    lines.extend(
        [
            "---",
            "",
            "## Validation Player Status",
            "",
            "| Player | Pathway | Expected Leagues | Found In | Status |",
            "|--------|---------|------------------|----------|--------|",
        ]
    )

    for player_key, status in player_status.items():
        name = player_key.replace("_", " ").title()
        pathway = status["pathway"]
        expected = ", ".join(status["expected_leagues"])
        found = ", ".join(status["found_in_leagues"]) if status["found_in_leagues"] else "None"
        player_stat = status["status"]

        lines.append(f"| {name} | {pathway} | {expected} | {found} | {player_stat} |")

    # Crosswalk Details
    lines.extend(
        [
            "",
            "---",
            "",
            "## Crosswalk Status",
            "",
            f"- **Total Entries:** {xwalk_data['total_entries']}",
            f"- **Unique Players:** {xwalk_data['unique_players']}",
            f"- **Leagues Covered:** {', '.join(sorted(xwalk_data['leagues_covered']))}",
            "",
            "**Entries by League:**",
            "",
        ]
    )

    for league, count in sorted(xwalk_data.get("entries_by_league", {}).items()):
        lines.append(f"- {league}: {count}")

    # Action Items
    lines.extend(
        [
            "",
            "---",
            "",
            "## Phase 1 Action Items",
            "",
        ]
    )

    # Leagues that need canonicalization (have index but no canonical)
    needs_canon = []
    needs_index = []
    needs_xwalk = []

    for league in ALL_LEAGUES:
        idx = index_data.get(league, {})
        can = canonical_data.get(league, {})
        xwalk_count = xwalk_data.get("entries_by_league", {}).get(league, 0)

        if idx.get("seasons") and not can.get("total_rows"):
            needs_canon.append(league)
        elif not idx.get("seasons"):
            needs_index.append(league)
        elif can.get("total_rows") and xwalk_count == 0:
            needs_xwalk.append(league)

    if needs_canon:
        lines.append("### Leagues Ready for Canonicalization")
        for league in needs_canon:
            idx = index_data.get(league, {})
            lines.append(
                f"- **{league}**: {len(idx.get('seasons', []))} seasons, {idx.get('total_games', 0):,} games indexed"
            )

    if needs_index:
        lines.append("")
        lines.append("### Leagues Needing Game Index")
        for league in needs_index:
            lines.append(f"- **{league}**: No game index found")

    if needs_xwalk:
        lines.append("")
        lines.append("### Leagues Needing Crosswalk Entries")
        for league in needs_xwalk:
            can = canonical_data.get(league, {})
            lines.append(
                f"- **{league}**: {can.get('total_rows', 0):,} canonical rows, 0 xwalk entries"
            )

    return "\n".join(lines)


def generate_parquet_report(
    index_data: dict,
    canonical_data: dict,
    xwalk_data: dict,
    player_status: dict,
) -> pd.DataFrame:
    """Generate structured parquet report."""
    rows = []

    for league in ALL_LEAGUES:
        idx = index_data.get(league, {})
        can = canonical_data.get(league, {})
        xwalk_count = xwalk_data.get("entries_by_league", {}).get(league, 0)

        # Determine join readiness
        idx_status = idx.get("status", "MISSING")
        can_status = can.get("status", "MISSING")

        if idx_status == "PASS" and can_status == "PASS" and xwalk_count > 0:
            join_ready = "READY"
        elif idx_status == "PASS" and can.get("total_rows", 0) > 0:
            join_ready = "NEEDS_XWALK"
        elif idx.get("seasons"):
            join_ready = "NEEDS_CANON"
        else:
            join_ready = "NEEDS_INDEX"

        rows.append(
            {
                "league": league,
                "game_index_status": idx_status,
                "game_index_seasons": len(idx.get("seasons", [])),
                "game_index_games": idx.get("total_games", 0),
                "game_index_date_coverage_pct": idx.get("avg_date_coverage", 0),
                "game_index_score_coverage_pct": idx.get("avg_score_coverage", 0),
                "canonical_status": can_status,
                "canonical_rows": can.get("total_rows", 0),
                "canonical_files": len(can.get("files", [])),
                "xwalk_entries": xwalk_count,
                "join_readiness": join_ready,
                "audit_timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    return pd.DataFrame(rows)


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="Audit League Coverage (Phase 0)")
    parser.add_argument(
        "--output-dir",
        default="data/_reports",
        help="Output directory for reports",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("LEAGUE COVERAGE AUDIT (Phase 0)")
    print("=" * 70)
    print()

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent.parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run scans
    print("Scanning game indexes...")
    index_data = scan_game_indexes()
    print(f"  Found {len(index_data)} leagues with game indexes")

    print("Scanning canonical data...")
    canonical_data = scan_canonical_data()
    print(f"  Found {len(canonical_data)} leagues with canonical data")

    print("Scanning crosswalk data...")
    xwalk_data = scan_xwalk_data()
    print(f"  Found {xwalk_data['total_entries']} crosswalk entries")

    print("Checking validation players...")
    player_status = scan_for_validation_players(canonical_data)
    found_count = sum(1 for p in player_status.values() if p["status"] != "NOT_FOUND")
    print(f"  Found {found_count}/11 validation players")

    # Generate reports
    print()
    print("Generating reports...")

    # Markdown report
    md_report = generate_markdown_report(index_data, canonical_data, xwalk_data, player_status)
    md_path = output_dir / "LEAGUE_COVERAGE_MATRIX.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"  Saved: {md_path}")

    # Also save to project root
    root_md_path = Path(__file__).parent.parent.parent / "LEAGUE_COVERAGE_MATRIX.md"
    with open(root_md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"  Saved: {root_md_path}")

    # Parquet report
    df_report = generate_parquet_report(index_data, canonical_data, xwalk_data, player_status)
    parquet_path = output_dir / "league_coverage.parquet"
    df_report.to_parquet(parquet_path, index=False)
    print(f"  Saved: {parquet_path}")

    # JSON report (for debugging)
    json_report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "game_indexes": {
            k: {
                **v,
                "earliest_date": str(v.get("earliest_date")),
                "latest_date": str(v.get("latest_date")),
            }
            for k, v in index_data.items()
        },
        "canonical": canonical_data,
        "xwalk": xwalk_data,
        "validation_players": player_status,
    }
    json_path = output_dir / "league_coverage.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, default=str)
    print(f"  Saved: {json_path}")

    # Print summary
    print()
    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    print()

    # Count by status
    ready_count = sum(1 for r in df_report["join_readiness"] if r == "READY")
    needs_xwalk = sum(1 for r in df_report["join_readiness"] if r == "NEEDS_XWALK")
    needs_canon = sum(1 for r in df_report["join_readiness"] if r == "NEEDS_CANON")
    needs_index = sum(1 for r in df_report["join_readiness"] if r == "NEEDS_INDEX")

    print(f"Join Ready:       {ready_count}")
    print(f"Needs Xwalk:      {needs_xwalk}")
    print(f"Needs Canon:      {needs_canon}")
    print(f"Needs Index:      {needs_index}")
    print()

    # Top priority leagues for Phase 1
    print("Phase 1 Priority (indexed, needs canonicalization):")
    for _, row in df_report[df_report["join_readiness"] == "NEEDS_CANON"].iterrows():
        print(
            f"  {row['league']}: {row['game_index_seasons']} seasons, {row['game_index_games']:,} games"
        )

    print()
    print(f"Full report saved to: {md_path}")


if __name__ == "__main__":
    main()
