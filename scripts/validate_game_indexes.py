#!/usr/bin/env python
"""Game Index Validator (Layer A Gates)

Validates all game index CSVs against strict quality gates for career stitching.
Run this before canonicalization to ensure deterministic joins are possible.

LAYER A GATES (Index Quality):
- GAME_ID: unique within (league, season)
- GAME_DATE: parseable ISO format, present for completed games
- HOME_SCORE/AWAY_SCORE: present for completed games
- HOME_TEAM/AWAY_TEAM: non-null
- No duplicate game entries

Usage:
    python scripts/validate_game_indexes.py
    python scripts/validate_game_indexes.py --league BCL
    python scripts/validate_game_indexes.py --output reports/index_validation.json
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

# Game index directory
GAME_INDEX_DIR = Path("data/game_indexes")


def validate_game_index(filepath: Path) -> dict:
    """Validate a single game index CSV against Layer A gates.

    Args:
        filepath: Path to game index CSV

    Returns:
        Validation report dictionary
    """
    filename = filepath.name
    parts = filename.replace(".csv", "").split("_")

    if len(parts) >= 2:
        league = parts[0]
        season = "_".join(parts[1:]).replace("_", "-")
    else:
        league = "UNKNOWN"
        season = "UNKNOWN"

    report = {
        "file": filename,
        "league": league,
        "season": season,
        "status": "PASS",
        "total_games": 0,
        "gates": {},
        "issues": [],
        "warnings": [],
    }

    try:
        df = pd.read_csv(filepath)
        report["total_games"] = len(df)

        if df.empty:
            report["status"] = "FAIL"
            report["issues"].append("Empty game index file")
            return report

        # Gate 1: GAME_ID uniqueness
        if "GAME_ID" in df.columns:
            duplicates = df["GAME_ID"].duplicated().sum()
            unique_ids = df["GAME_ID"].nunique()
            report["gates"]["game_id_unique"] = {
                "status": "PASS" if duplicates == 0 else "FAIL",
                "unique_count": int(unique_ids),
                "duplicate_count": int(duplicates),
            }
            if duplicates > 0:
                report["status"] = "FAIL"
                report["issues"].append(f"{duplicates} duplicate GAME_IDs")
        else:
            report["gates"]["game_id_unique"] = {
                "status": "FAIL",
                "error": "GAME_ID column missing",
            }
            report["status"] = "FAIL"
            report["issues"].append("GAME_ID column missing")

        # Gate 2: GAME_DATE presence and validity
        if "GAME_DATE" in df.columns:
            non_null = df["GAME_DATE"].notna().sum()
            total = len(df)
            pct = round(non_null / total * 100, 1) if total > 0 else 0

            # Try to parse dates
            valid_dates = 0
            for date_val in df["GAME_DATE"].dropna():
                try:
                    pd.to_datetime(date_val)
                    valid_dates += 1
                except Exception:
                    pass

            valid_pct = round(valid_dates / total * 100, 1) if total > 0 else 0

            report["gates"]["game_date"] = {
                "status": "PASS" if pct == 100 else ("WARN" if pct >= 50 else "FAIL"),
                "present_count": int(non_null),
                "present_pct": pct,
                "valid_parseable_count": valid_dates,
                "valid_parseable_pct": valid_pct,
            }

            if pct < 100:
                if pct == 0:
                    report["status"] = "FAIL"
                    report["issues"].append(f"0% dates present ({non_null}/{total})")
                else:
                    report["warnings"].append(f"{pct}% dates present ({non_null}/{total})")
        else:
            report["gates"]["game_date"] = {"status": "FAIL", "error": "GAME_DATE column missing"}
            report["status"] = "FAIL"
            report["issues"].append("GAME_DATE column missing")

        # Gate 3: Scores presence (for past seasons)
        for score_col in ["HOME_SCORE", "AWAY_SCORE"]:
            if score_col in df.columns:
                non_null = df[score_col].notna().sum()
                total = len(df)
                pct = round(non_null / total * 100, 1) if total > 0 else 0

                # Check if scores are valid numbers
                valid_scores = 0
                for score in df[score_col].dropna():
                    try:
                        val = int(float(score))
                        if 0 <= val <= 300:  # Reasonable basketball score range
                            valid_scores += 1
                    except Exception:
                        pass

                valid_pct = round(valid_scores / total * 100, 1) if total > 0 else 0

                report["gates"][score_col.lower()] = {
                    "status": "PASS" if pct == 100 else ("WARN" if pct >= 50 else "FAIL"),
                    "present_count": int(non_null),
                    "present_pct": pct,
                    "valid_count": valid_scores,
                    "valid_pct": valid_pct,
                }

                if pct < 100 and pct == 0:
                    report["status"] = "FAIL" if report["status"] != "FAIL" else "FAIL"
                    report["issues"].append(f"0% {score_col} present")
            else:
                report["gates"][score_col.lower()] = {
                    "status": "FAIL",
                    "error": f"{score_col} column missing",
                }
                report["warnings"].append(f"{score_col} column missing")

        # Gate 4: Team columns non-null
        for team_col in ["HOME_TEAM", "AWAY_TEAM"]:
            if team_col in df.columns:
                non_null = df[team_col].notna().sum()
                total = len(df)
                pct = round(non_null / total * 100, 1) if total > 0 else 0

                report["gates"][team_col.lower()] = {
                    "status": "PASS" if pct == 100 else "FAIL",
                    "present_count": int(non_null),
                    "present_pct": pct,
                }

                if pct < 100:
                    report["status"] = "FAIL"
                    report["issues"].append(f"{team_col} has {total - non_null} null values")
            else:
                report["gates"][team_col.lower()] = {
                    "status": "FAIL",
                    "error": f"{team_col} column missing",
                }
                report["status"] = "FAIL"
                report["issues"].append(f"{team_col} column missing")

        # Gate 5: Date range analysis
        if "GAME_DATE" in df.columns and df["GAME_DATE"].notna().any():
            try:
                dates = pd.to_datetime(df["GAME_DATE"].dropna(), errors="coerce")
                valid_dates = dates.dropna()
                if len(valid_dates) > 0:
                    report["gates"]["date_range"] = {
                        "status": "INFO",
                        "earliest": str(valid_dates.min().date()),
                        "latest": str(valid_dates.max().date()),
                        "span_days": (valid_dates.max() - valid_dates.min()).days,
                    }
            except Exception as e:
                report["gates"]["date_range"] = {"status": "ERROR", "error": str(e)}

    except Exception as e:
        report["status"] = "ERROR"
        report["issues"].append(f"Failed to parse CSV: {str(e)}")

    return report


def validate_all_indexes(league_filter: str | None = None) -> dict:
    """Validate all game index files.

    Args:
        league_filter: Optional league code to filter (e.g., "BCL")

    Returns:
        Complete validation report
    """
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_files": 0,
            "pass": 0,
            "warn": 0,
            "fail": 0,
            "error": 0,
        },
        "leagues": {},
        "files": [],
    }

    # Find all game index files
    if not GAME_INDEX_DIR.exists():
        report["error"] = f"Game index directory not found: {GAME_INDEX_DIR}"
        return report

    csv_files = sorted(GAME_INDEX_DIR.glob("*.csv"))

    if league_filter:
        csv_files = [f for f in csv_files if f.name.startswith(league_filter.upper())]

    report["summary"]["total_files"] = len(csv_files)

    for filepath in csv_files:
        file_report = validate_game_index(filepath)
        report["files"].append(file_report)

        # Update league summary
        league = file_report["league"]
        if league not in report["leagues"]:
            report["leagues"][league] = {
                "seasons": [],
                "total_games": 0,
                "status": "PASS",
                "issues": [],
            }

        report["leagues"][league]["seasons"].append(file_report["season"])
        report["leagues"][league]["total_games"] += file_report["total_games"]

        if file_report["status"] == "FAIL":
            report["leagues"][league]["status"] = "FAIL"
            report["leagues"][league]["issues"].extend(
                [f"{file_report['season']}: {issue}" for issue in file_report["issues"]]
            )

        # Update summary counts
        status = file_report["status"]
        if status == "PASS":
            report["summary"]["pass"] += 1
        elif status == "WARN":
            report["summary"]["warn"] += 1
        elif status == "FAIL":
            report["summary"]["fail"] += 1
        else:
            report["summary"]["error"] += 1

    return report


def print_report(report: dict) -> None:
    """Print formatted validation report to console."""
    print()
    print("=" * 70)
    print("GAME INDEX VALIDATION REPORT (Layer A Gates)")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print()

    summary = report["summary"]
    print(f"Files checked: {summary['total_files']}")
    print(f"  PASS: {summary['pass']}")
    print(f"  WARN: {summary['warn']}")
    print(f"  FAIL: {summary['fail']}")
    print(f"  ERROR: {summary['error']}")
    print()

    # League summary
    print("=" * 70)
    print("LEAGUE SUMMARY")
    print("=" * 70)

    for league, data in sorted(report["leagues"].items()):
        status_icon = "PASS" if data["status"] == "PASS" else "FAIL"
        print(f"\n{league}: {status_icon}")
        print(f"  Seasons: {', '.join(sorted(data['seasons']))}")
        print(f"  Total games: {data['total_games']}")
        if data["issues"]:
            print("  Issues:")
            for issue in data["issues"][:5]:  # Show first 5 issues
                print(f"    - {issue}")
            if len(data["issues"]) > 5:
                print(f"    ... and {len(data['issues']) - 5} more")

    # Detailed file reports
    print()
    print("=" * 70)
    print("DETAILED FILE VALIDATION")
    print("=" * 70)

    for file_report in report["files"]:
        status_icon = {
            "PASS": "[PASS]",
            "WARN": "[WARN]",
            "FAIL": "[FAIL]",
            "ERROR": "[ERR!]",
        }.get(file_report["status"], "[????]")

        print(f"\n{status_icon} {file_report['file']}")
        print(f"  League: {file_report['league']}, Season: {file_report['season']}")
        print(f"  Games: {file_report['total_games']}")

        # Print gate details
        for gate_name, gate_data in file_report.get("gates", {}).items():
            gate_status = gate_data.get("status", "UNKNOWN")
            if gate_status == "PASS":
                continue  # Skip passing gates for brevity

            if "error" in gate_data:
                print(f"    {gate_name}: {gate_status} - {gate_data['error']}")
            elif "present_pct" in gate_data:
                print(f"    {gate_name}: {gate_status} ({gate_data['present_pct']}% present)")

        if file_report["issues"]:
            print(f"  Issues: {', '.join(file_report['issues'])}")
        if file_report["warnings"]:
            print(f"  Warnings: {', '.join(file_report['warnings'])}")


def main():
    parser = argparse.ArgumentParser(description="Validate game index CSVs (Layer A Gates)")
    parser.add_argument("--league", help="Filter to specific league (e.g., BCL, BAL, OTE)")
    parser.add_argument("--output", help="Output JSON report path")
    parser.add_argument("--json", action="store_true", help="Output as JSON only")
    args = parser.parse_args()

    print("Validating game indexes...")
    report = validate_all_indexes(args.league)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved report to: {output_path}")

    # Exit with error if any failures
    if report["summary"]["fail"] > 0 or report["summary"]["error"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
