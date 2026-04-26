#!/usr/bin/env python
"""Gold Player Career Game Builder (Phase 5)

Creates unified gold_player_career_game table by:
1. Union all canonical box_player_game across leagues
2. Attach CANONICAL_PLAYER_ID via player crosswalk
3. Enforce strict uniqueness: (CANONICAL_PLAYER_ID, LEAGUE, SEASON, GAME_ID)
4. Ensure every row has GAME_DATE for sortability

This is the foundation for career stitching across leagues like:
- Alex Sarr: OTE -> NBL -> NBA
- Amen/Ausar Thompson: OTE -> NBA

Usage:
    python scripts/build_gold_career.py
    python scripts/build_gold_career.py --output data/gold/player_career_game.parquet
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
CANONICAL_DIR = DATA_DIR / "canonical"
GOLD_DIR = DATA_DIR / "gold"
REPORTS_DIR = DATA_DIR / "_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GOLD_DIR.mkdir(parents=True, exist_ok=True)


def load_canonical_data() -> pd.DataFrame:
    """Load canonical box_player_game data.

    First tries combined file, falls back to Hive-style partitions.
    """
    # Try combined file first (faster)
    combined_file = CANONICAL_DIR / "all_leagues_combined.parquet"
    if combined_file.exists():
        print(f"Loading combined file: {combined_file}")
        df = pd.read_parquet(combined_file)
        print(f"  Loaded {len(df):,} rows")
        return df

    # Fall back to Hive-style partitions
    all_data = []
    box_player_game_dir = CANONICAL_DIR / "box_player_game"

    for filepath in box_player_game_dir.glob("**/*.parquet"):
        league = "UNKNOWN"
        season = "UNKNOWN"
        for part in filepath.parts:
            if part.startswith("league="):
                league = part.replace("league=", "")
            elif part.startswith("season="):
                season = part.replace("season=", "")

        print(f"Loading: {filepath.name} ({league} {season})")
        try:
            df = pd.read_parquet(filepath)
            if "LEAGUE" not in df.columns:
                df["LEAGUE"] = league
            if "SEASON" not in df.columns:
                df["SEASON"] = season
            all_data.append(df)
        except Exception as e:
            print(f"  ERROR: {e}")

    if not all_data:
        print("No canonical player_game files found.")
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)


def load_player_edges() -> pd.DataFrame:
    """Load player identity edge table for deterministic joins."""
    edges_path = DATA_DIR / "identity" / "player_edges.parquet"
    if edges_path.exists():
        edges = pd.read_parquet(edges_path)
        print(f"  Loaded {len(edges):,} player edges")
        return edges

    # Fall back to crosswalk
    xwalk_path = DATA_DIR / "player_xwalk.parquet"
    if xwalk_path.exists():
        xwalk = pd.read_parquet(xwalk_path)
        print(f"  Loaded crosswalk with {len(xwalk)} entries (converting to edges)")
        # Old format had different columns - adapt
        return xwalk

    print("  Warning: No player edges/crosswalk found. Using source player IDs.")
    return pd.DataFrame()


def fix_null_source_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Fix null-like SOURCE_PLAYER_IDs using NAME_KEY."""
    df = df.copy()
    if "SOURCE_PLAYER_ID" not in df.columns:
        return df

    null_like = df["SOURCE_PLAYER_ID"].isin(["None", "none", "", "null", "NULL"])
    null_like |= df["SOURCE_PLAYER_ID"].isna()

    if "NAME_KEY" in df.columns:
        df.loc[null_like, "SOURCE_PLAYER_ID"] = df.loc[null_like, "NAME_KEY"]
        fixed = null_like.sum()
        if fixed > 0:
            print(f"  Fixed {fixed:,} null-like SOURCE_PLAYER_IDs")

    return df


def build_gold_career(canonical_df: pd.DataFrame, edges_df: pd.DataFrame) -> pd.DataFrame:
    """Build gold_player_career_game table.

    Args:
        canonical_df: Canonical box_player_game data
        edges_df: Player identity edge table (PLAYER_UID, SOURCE_LEAGUE, SOURCE_PLAYER_ID)

    Returns:
        Gold player career game DataFrame
    """
    if canonical_df.empty:
        return pd.DataFrame()

    gold_df = canonical_df.copy()

    # Fix null-like SOURCE_PLAYER_IDs first
    gold_df = fix_null_source_ids(gold_df)

    # Determine source player ID column
    source_id_col = "SOURCE_PLAYER_ID" if "SOURCE_PLAYER_ID" in gold_df.columns else "PLAYER_ID"

    # Attach PLAYER_UID via edge table
    if not edges_df.empty and "PLAYER_UID" in edges_df.columns:
        # Prepare edges for join
        if "SOURCE_LEAGUE" in edges_df.columns:
            # New edge format
            edges_for_join = edges_df[["PLAYER_UID", "SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]].copy()
            edges_for_join = edges_for_join.rename(columns={"SOURCE_LEAGUE": "LEAGUE"})
        else:
            # Old crosswalk format
            edges_for_join = edges_df[["PLAYER_UID", "LEAGUE", "SOURCE_PLAYER_ID"]].copy()

        # Deduplicate edges
        edges_for_join = edges_for_join.drop_duplicates(
            subset=["LEAGUE", "SOURCE_PLAYER_ID"], keep="first"
        )

        # Merge
        gold_df = gold_df.merge(
            edges_for_join,
            left_on=["LEAGUE", source_id_col],
            right_on=["LEAGUE", "SOURCE_PLAYER_ID"],
            how="left",
            suffixes=("", "_edge"),
        )

        # Drop duplicate columns from merge
        gold_df = gold_df.drop(columns=["SOURCE_PLAYER_ID_edge"], errors="ignore")

        # Fill missing UIDs with league-prefixed source IDs
        gold_df["PLAYER_UID"] = gold_df["PLAYER_UID"].fillna(
            gold_df["LEAGUE"] + "_" + gold_df[source_id_col].astype(str)
        )

        matched = (gold_df["PLAYER_UID"].str.startswith("P_")).sum()
        print(
            f"  Matched PLAYER_UID: {matched:,}/{len(gold_df):,} ({100*matched/len(gold_df):.1f}%)"
        )
    else:
        # No edges - use league-prefixed source IDs
        gold_df["PLAYER_UID"] = gold_df["LEAGUE"] + "_" + gold_df[source_id_col].astype(str)

    # Also create CANONICAL_PLAYER_ID as alias for backwards compatibility
    gold_df["CANONICAL_PLAYER_ID"] = gold_df["PLAYER_UID"]

    # Ensure GAME_DATE is present and valid
    if "GAME_DATE" not in gold_df.columns:
        print("WARNING: GAME_DATE column missing - career sorting will be unreliable!")
        gold_df["GAME_DATE"] = None
    else:
        # Parse dates
        gold_df["GAME_DATE"] = pd.to_datetime(gold_df["GAME_DATE"], errors="coerce")
        missing_dates = gold_df["GAME_DATE"].isna().sum()
        if missing_dates > 0:
            print(f"WARNING: {missing_dates} rows missing GAME_DATE")

    # Enforce uniqueness constraint
    key_cols = ["CANONICAL_PLAYER_ID", "LEAGUE", "SEASON", "GAME_ID"]
    duplicates = gold_df.duplicated(subset=key_cols, keep=False)
    if duplicates.any():
        dup_count = duplicates.sum()
        print(f"WARNING: {dup_count} duplicate rows detected")
        print("Keeping first occurrence of each duplicate")
        gold_df = gold_df.drop_duplicates(subset=key_cols, keep="first")

    # Sort by player then date for career ordering
    if gold_df["GAME_DATE"].notna().any():
        gold_df = gold_df.sort_values(["CANONICAL_PLAYER_ID", "GAME_DATE"])

    # Reorder columns - handle both old and new schema
    priority_cols = [
        "PLAYER_UID",
        "CANONICAL_PLAYER_ID",
        "SOURCE_PLAYER_ID",
        "PLAYER_ID",
        "PLAYER_NAME_RAW",
        "PLAYER_NAME",
        "NAME_KEY",
        "LEAGUE",
        "SEASON",
        "GAME_ID",
        "GAME_DATE",
        "TEAM_KEY",
        "TEAM_NAME_RAW",
        "TEAM",
        "TEAM_ID",
    ]

    ordered_cols = [c for c in priority_cols if c in gold_df.columns]
    other_cols = [c for c in gold_df.columns if c not in priority_cols]
    gold_df = gold_df[ordered_cols + other_cols]

    return gold_df


def validate_gold_career(gold_df: pd.DataFrame) -> dict:
    """Validate gold_player_career_game table."""
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_records": len(gold_df),
        "unique_players": 0,
        "leagues": [],
        "seasons": [],
        "date_coverage": 0.0,
        "uniqueness_check": "UNKNOWN",
        "issues": [],
    }

    if gold_df.empty:
        report["issues"].append("Empty DataFrame")
        return report

    # Unique players
    if "CANONICAL_PLAYER_ID" in gold_df.columns:
        report["unique_players"] = gold_df["CANONICAL_PLAYER_ID"].nunique()

    # Leagues
    if "LEAGUE" in gold_df.columns:
        report["leagues"] = gold_df["LEAGUE"].unique().tolist()

    # Seasons
    if "SEASON" in gold_df.columns:
        report["seasons"] = sorted(gold_df["SEASON"].unique().tolist())

    # Date coverage
    if "GAME_DATE" in gold_df.columns:
        non_null = gold_df["GAME_DATE"].notna().sum()
        report["date_coverage"] = round(non_null / len(gold_df) * 100, 1)
        if report["date_coverage"] < 100:
            report["issues"].append(f"Only {report['date_coverage']}% date coverage")

    # Uniqueness check
    key_cols = ["CANONICAL_PLAYER_ID", "LEAGUE", "SEASON", "GAME_ID"]
    if all(c in gold_df.columns for c in key_cols):
        duplicates = gold_df.duplicated(subset=key_cols).sum()
        if duplicates == 0:
            report["uniqueness_check"] = "PASS"
        else:
            report["uniqueness_check"] = "FAIL"
            report["issues"].append(f"{duplicates} duplicate key combinations")

    return report


def find_multi_league_players(gold_df: pd.DataFrame) -> pd.DataFrame:
    """Find players who appear in multiple leagues (career hoppers)."""
    if gold_df.empty or "CANONICAL_PLAYER_ID" not in gold_df.columns:
        return pd.DataFrame()

    # Group by player and count leagues
    player_leagues = (
        gold_df.groupby("CANONICAL_PLAYER_ID")["LEAGUE"]
        .agg(["nunique", lambda x: list(x.unique())])
        .reset_index()
    )
    player_leagues.columns = ["CANONICAL_PLAYER_ID", "league_count", "leagues"]

    # Filter to multi-league players
    multi_league = player_leagues[player_leagues["league_count"] > 1].copy()

    # Add player name (from most recent record) - handle both old and new schema
    name_col = "PLAYER_NAME_RAW" if "PLAYER_NAME_RAW" in gold_df.columns else "PLAYER_NAME"
    if name_col in gold_df.columns:
        player_names = gold_df.groupby("CANONICAL_PLAYER_ID")[name_col].first()
        player_names.name = "PLAYER_NAME"
        multi_league = multi_league.merge(
            player_names.reset_index(), on="CANONICAL_PLAYER_ID", how="left"
        )

    return multi_league.sort_values("league_count", ascending=False)


def main():
    parser = argparse.ArgumentParser(description="Build gold_player_career_game table")
    parser.add_argument(
        "--output", default="data/gold/player_career_game.parquet", help="Output path"
    )
    parser.add_argument("--csv", action="store_true", help="Also save as CSV")
    args = parser.parse_args()

    print("=" * 70)
    print("GOLD PLAYER CAREER GAME BUILDER (Phase 5)")
    print("=" * 70)
    print()

    # Load canonical data
    print("Loading canonical box_player_game data...")
    canonical_df = load_canonical_data()

    if canonical_df.empty:
        print("No canonical data found. Run Phase 3 (canonicalization) first.")
        return

    print(f"Loaded {len(canonical_df)} canonical records")
    print()

    # Load player edges
    print("Loading player identity edges...")
    edges_df = load_player_edges()
    print()

    # Build gold table
    print("Building gold_player_career_game...")
    gold_df = build_gold_career(canonical_df, edges_df)

    if gold_df.empty:
        print("Failed to build gold table")
        return

    # Validate
    print("Validating gold table...")
    validation = validate_gold_career(gold_df)

    # Save outputs
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gold_df.to_parquet(output_path, index=False)
    print(f"Saved {len(gold_df)} records to {output_path}")

    if args.csv:
        csv_path = output_path.with_suffix(".csv")
        gold_df.to_csv(csv_path, index=False)
        print(f"Saved CSV to {csv_path}")

    # Save validation report
    with open(REPORTS_DIR / "gold_career_validation.json", "w") as f:
        json.dump(validation, f, indent=2)

    # Find multi-league players
    multi_league = find_multi_league_players(gold_df)
    if not multi_league.empty:
        multi_league.to_csv(REPORTS_DIR / "multi_league_players.csv", index=False)
        print(f"Found {len(multi_league)} multi-league players")

    # Print summary
    print()
    print("=" * 70)
    print("GOLD TABLE SUMMARY")
    print("=" * 70)
    print(f"Total records: {validation['total_records']}")
    print(f"Unique players: {validation['unique_players']}")
    print(f"Leagues: {', '.join(validation['leagues'])}")
    print(f"Seasons: {', '.join(map(str, validation['seasons']))}")
    print(f"Date coverage: {validation['date_coverage']}%")
    print(f"Uniqueness: {validation['uniqueness_check']}")

    if validation["issues"]:
        print()
        print("ISSUES:")
        for issue in validation["issues"]:
            print(f"  - {issue}")


if __name__ == "__main__":
    main()
