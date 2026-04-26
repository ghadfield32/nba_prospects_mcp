#!/usr/bin/env python3
# ruff: noqa: E402
"""Verify Canonical Data Has Normalization Columns

Checks that all canonical parquet files have:
- 5 season columns
- 6 name columns (if they exist in original data)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

CANON_DIR = PROJECT_ROOT / "data" / "canonical" / "box_player_game"


def verify_all_canonical_files():
    """Verify all canonical files have normalization columns"""

    print("=" * 80)
    print("VERIFYING CANONICAL DATA NORMALIZATION")
    print("=" * 80)
    print(f"Source: {CANON_DIR}\n")

    required_season_cols = [
        "SEASON_RAW",
        "SEASON",
        "SEASON_START_YEAR",
        "SEASON_END_YEAR",
        "SEASON_TYPE",
    ]
    required_name_cols = [
        "PLAYER_NAME_RAW",
        "PLAYER_NAME_CANONICAL",
        "FIRST_NAME",
        "LAST_NAME",
        "FIRST_INITIAL",
        "NAME_KEY_CANONICAL",
        "NAME_KEY_INITIAL",
    ]

    results = {}
    total_files = 0
    total_records = 0

    for league_dir in sorted(CANON_DIR.glob("league=*")):
        league = league_dir.name.split("=", 1)[1]

        league_results = {
            "files": 0,
            "records": 0,
            "season_cols_ok": 0,
            "name_cols_ok": 0,
            "sample_season": None,
            "sample_names": [],
        }

        for season_dir in sorted(league_dir.glob("season=*")):
            season_raw = season_dir.name.split("=", 1)[1]
            data_file = season_dir / "data.parquet"

            if not data_file.exists():
                continue

            try:
                df = pd.read_parquet(data_file)
                league_results["files"] += 1
                league_results["records"] += len(df)
                total_files += 1
                total_records += len(df)

                # Check season columns
                season_cols_present = all(col in df.columns for col in required_season_cols)
                if season_cols_present:
                    league_results["season_cols_ok"] += 1
                    if league_results["sample_season"] is None and "SEASON" in df.columns:
                        league_results["sample_season"] = (
                            df["SEASON"].iloc[0] if len(df) > 0 else None
                        )

                # Check name columns
                name_cols_present = all(col in df.columns for col in required_name_cols)
                if name_cols_present:
                    league_results["name_cols_ok"] += 1
                    if len(league_results["sample_names"]) == 0 and "PLAYER_NAME_RAW" in df.columns:
                        league_results["sample_names"] = df["PLAYER_NAME_RAW"].head(2).tolist()

            except Exception as e:
                print(f"  ✗ Error reading {league}/{season_raw}: {str(e)[:60]}")

        results[league] = league_results

    # Print results by league
    print("\nBy League:")
    print("-" * 80)
    for league, data in sorted(results.items()):
        season_pct = (data["season_cols_ok"] / data["files"] * 100) if data["files"] > 0 else 0
        name_pct = (data["name_cols_ok"] / data["files"] * 100) if data["files"] > 0 else 0

        symbol = "✓" if season_pct == 100 and name_pct == 100 else "⚠️" if season_pct >= 50 else "✗"

        print(f"\n{symbol} {league:12}")
        print(f"  Files: {data['files']:3}  Records: {data['records']:8,}")
        print(f"  Season cols: {data['season_cols_ok']:3}/{data['files']:3} ({season_pct:5.1f}%)")
        print(f"  Name cols:   {data['name_cols_ok']:3}/{data['files']:3} ({name_pct:5.1f}%)")
        if data["sample_season"]:
            print(f"  Sample SEASON: {data['sample_season']}")
        if data["sample_names"]:
            print(f"  Sample names: {data['sample_names']}")

    # Summary
    total_season_ok = sum(d["season_cols_ok"] for d in results.values())
    total_name_ok = sum(d["name_cols_ok"] for d in results.values())

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files: {total_files}")
    print(f"Total records: {total_records:,}")
    print(f"Leagues: {len(results)}")
    print("\nNormalization coverage:")
    print(
        f"  Season columns: {total_season_ok}/{total_files} ({total_season_ok/total_files*100:.1f}%)"
    )
    print(f"  Name columns: {total_name_ok}/{total_files} ({total_name_ok/total_files*100:.1f}%)")

    if total_season_ok == total_files and total_name_ok == total_files:
        print("\n✓✓✓ ALL FILES NORMALIZED - Ready for unified dataset build!")
        return 0
    elif total_season_ok / total_files >= 0.9:
        print("\n⚠️  MOSTLY NORMALIZED - Some files may need attention")
        return 0
    else:
        print("\n✗ INCOMPLETE NORMALIZATION - Run backfill_season_normalization.py")
        return 1


if __name__ == "__main__":
    sys.exit(verify_all_canonical_files())
