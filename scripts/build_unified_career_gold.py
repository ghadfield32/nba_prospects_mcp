#!/usr/bin/env python3
"""Build Gold Layer Unified Player Career Dataset

Combines canonical player-game data with multi-gate player matching to create
a unified career dataset with deterministic player identities.

Features:
- PLAYER_UID: Universal player identity across all leagues
- Career sequence tracking: CAREER_GAME_NUMBER, LEAGUE_GAME_NUMBER
- Temporal validation: GAME_DATE, DAYS_SINCE_FIRST_GAME
- Full statistical history: All game-level stats preserved

Usage:
    python scripts/build_unified_career_gold.py
    python scripts/build_unified_career_gold.py --output data/gold/player_career_unified_tier1.parquet
    python scripts/build_unified_career_gold.py --confidence-threshold 0.90
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_canonical_data_all_leagues(leagues: list[str] = None) -> pd.DataFrame:
    """Load all canonical player-game data from Tier 1 leagues.

    Args:
        leagues: List of league codes. If None, loads all Tier 1 leagues.

    Returns:
        Combined DataFrame with all player-game records
    """
    if leagues is None:
        leagues = ["NCAA_MBB", "GLEAGUE", "ABA", "NBL", "CEBL", "OTE"]

    print("\n" + "=" * 80)
    print("LOADING CANONICAL DATA")
    print("=" * 80)

    all_data = []

    # League code mapping
    league_code_map = {
        "GLEAGUE": "G_LEAGUE",
        "G_LEAGUE": "G_LEAGUE",
    }

    base_path = Path("data/canonical/box_player_game")

    for league in leagues:
        league_normalized = league_code_map.get(league, league)
        league_dir = base_path / f"league={league_normalized}"

        if not league_dir.exists():
            print(f"  WARNING: {league} directory not found, skipping")
            continue

        # Find all season subdirectories
        season_dirs = sorted([d for d in league_dir.iterdir() if d.is_dir()])

        for season_dir in season_dirs:
            data_file = season_dir / "data.parquet"

            if data_file.exists():
                try:
                    df = pd.read_parquet(data_file)

                    # Add league column if missing
                    if "LEAGUE" not in df.columns or df["LEAGUE"].isna().all():
                        df["LEAGUE"] = league_normalized

                    # Rename to standard column names
                    df.rename(columns={"LEAGUE": "SOURCE_LEAGUE"}, inplace=True)

                    all_data.append(df)
                    print(f"  ✓ Loaded {league_normalized} {season_dir.name}: {len(df):,} records")
                except Exception as e:
                    print(f"  ✗ Error loading {data_file}: {e}")

    if not all_data:
        raise ValueError("No data loaded from any league")

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    print(f"\nTotal records loaded: {len(combined_df):,}")
    print(f"Leagues: {combined_df['SOURCE_LEAGUE'].unique().tolist()}")

    return combined_df


def build_unified_career_dataset(
    canonical_df: pd.DataFrame, edges_df: pd.DataFrame, confidence_threshold: float = 0.0
) -> pd.DataFrame:
    """Join canonical data with player edges to create unified career dataset.

    Args:
        canonical_df: Canonical player-game data
        edges_df: Player edges from multi-gate matcher
        confidence_threshold: Minimum confidence for inclusion (default: 0.0 = all)

    Returns:
        Unified career dataset with PLAYER_UID and sequence numbers
    """
    print("\n" + "=" * 80)
    print("BUILDING UNIFIED CAREER DATASET")
    print("=" * 80)

    # Filter edges by confidence threshold
    if confidence_threshold > 0:
        edges_filtered = edges_df[edges_df["CONFIDENCE"] >= confidence_threshold].copy()
        print(f"Confidence threshold: {confidence_threshold:.2f}")
        print(f"  Edges before filter: {len(edges_df):,}")
        print(f"  Edges after filter: {len(edges_filtered):,}")
        print(
            f"  Excluded: {len(edges_df) - len(edges_filtered):,} ({(len(edges_df) - len(edges_filtered))/len(edges_df)*100:.1f}%)"
        )
    else:
        edges_filtered = edges_df.copy()
        print(f"Confidence threshold: {confidence_threshold:.2f} (include all)")

    # Optimize datatypes for memory efficiency
    print("\nOptimizing datatypes for memory efficiency...")
    canonical_df["SOURCE_LEAGUE"] = canonical_df["SOURCE_LEAGUE"].astype("category")
    canonical_df["SOURCE_PLAYER_ID"] = canonical_df["SOURCE_PLAYER_ID"].astype(str)
    edges_filtered["SOURCE_LEAGUE"] = edges_filtered["SOURCE_LEAGUE"].astype("category")
    edges_filtered["SOURCE_PLAYER_ID"] = edges_filtered["SOURCE_PLAYER_ID"].astype(str)

    # Merge on both columns directly (more efficient than creating join key)
    print("\nJoining canonical data with player edges...")
    print(f"  Canonical records: {len(canonical_df):,}")

    gold_df = canonical_df.merge(
        edges_filtered[
            [
                "SOURCE_LEAGUE",
                "SOURCE_PLAYER_ID",
                "PLAYER_UID",
                "NAME_KEY",
                "MATCH_RULE",
                "CONFIDENCE",
            ]
        ],
        on=["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"],
        how="inner",  # INNER join = only keep matched players
    )

    print(
        f"  After join: {len(gold_df):,} records ({len(gold_df)/len(canonical_df)*100:.1f}% of original)"
    )
    print(f"  Unique players: {gold_df['PLAYER_UID'].nunique():,}")

    # Add CANONICAL_PLAYER_ID alias
    gold_df["CANONICAL_PLAYER_ID"] = gold_df["PLAYER_UID"]

    # Convert game dates
    print("\nProcessing game dates...")
    gold_df["GAME_DATE"] = pd.to_datetime(gold_df["GAME_DATE"], errors="coerce")

    # Check date coverage
    date_coverage = gold_df["GAME_DATE"].notna().sum() / len(gold_df) * 100
    print(f"  Date coverage: {date_coverage:.1f}%")

    if date_coverage < 95:
        print(f"  WARNING: Low date coverage ({date_coverage:.1f}%)")

    # Sort by player and date
    print("\nSorting by PLAYER_UID and GAME_DATE...")
    gold_df = gold_df.sort_values(["PLAYER_UID", "GAME_DATE", "SOURCE_LEAGUE"])

    # Calculate career sequence numbers
    print("\nCalculating career sequence numbers...")

    # Career game number (across all leagues)
    gold_df["CAREER_GAME_NUMBER"] = gold_df.groupby("PLAYER_UID").cumcount() + 1

    # League game number (within each league)
    gold_df["LEAGUE_GAME_NUMBER"] = gold_df.groupby(["PLAYER_UID", "SOURCE_LEAGUE"]).cumcount() + 1

    # Season game number (within each season)
    gold_df["SEASON_GAME_NUMBER"] = (
        gold_df.groupby(["PLAYER_UID", "SOURCE_LEAGUE", "SEASON"]).cumcount() + 1
    )

    # Days since first game
    first_game = gold_df.groupby("PLAYER_UID")["GAME_DATE"].transform("first")
    gold_df["DAYS_SINCE_FIRST_GAME"] = (gold_df["GAME_DATE"] - first_game).dt.days

    # Unix timestamp
    gold_df["GAME_DATE_UNIX"] = gold_df["GAME_DATE"].astype(int) // 10**9

    print(
        f"  ✓ CAREER_GAME_NUMBER: Range {gold_df['CAREER_GAME_NUMBER'].min()}-{gold_df['CAREER_GAME_NUMBER'].max()}"
    )
    print(
        f"  ✓ LEAGUE_GAME_NUMBER: Range {gold_df['LEAGUE_GAME_NUMBER'].min()}-{gold_df['LEAGUE_GAME_NUMBER'].max()}"
    )
    print(
        f"  ✓ DAYS_SINCE_FIRST_GAME: Range {gold_df['DAYS_SINCE_FIRST_GAME'].min()}-{gold_df['DAYS_SINCE_FIRST_GAME'].max()}"
    )

    # Validate dataset
    print("\nValidating dataset...")

    # Check for duplicates
    dup_mask = gold_df.duplicated(
        subset=["CANONICAL_PLAYER_ID", "SOURCE_LEAGUE", "SEASON", "GAME_ID"]
    )
    if dup_mask.any():
        print(f"  WARNING: Found {dup_mask.sum():,} duplicate records, removing...")
        gold_df = gold_df[~dup_mask]
    else:
        print("  ✓ No duplicate records")

    # Check career sequence monotonicity
    non_monotonic = 0
    for _player_uid, group in gold_df.groupby("PLAYER_UID"):
        if len(group) > 1:
            # Check if CAREER_GAME_NUMBER is monotonically increasing
            if not (group["CAREER_GAME_NUMBER"].diff().dropna() >= 0).all():
                non_monotonic += 1

    if non_monotonic > 0:
        print(f"  WARNING: {non_monotonic} players have non-monotonic career sequences")
    else:
        print("  ✓ All career sequences are monotonic")

    return gold_df


def save_gold_dataset(gold_df: pd.DataFrame, output_path: Path):
    """Save unified career dataset to gold layer.

    Args:
        gold_df: Unified career dataset
        output_path: Output file path
    """
    print("\n" + "=" * 80)
    print("SAVING GOLD DATASET")
    print("=" * 80)

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to parquet
    print(f"Saving to {output_path}...")
    gold_df.to_parquet(output_path, index=False, compression="snappy")

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  ✓ Saved {len(gold_df):,} rows")
    print(f"  ✓ File size: {file_size_mb:.1f} MB")
    print(f"  ✓ Unique players: {gold_df['PLAYER_UID'].nunique():,}")

    # Also save CSV sample for review
    csv_path = output_path.with_suffix(".sample.csv")
    sample_size = min(10000, len(gold_df))
    gold_df.sample(n=sample_size, random_state=42).to_csv(csv_path, index=False)
    print(f"  ✓ Saved {sample_size:,} row sample to {csv_path}")

    # Save schema
    schema_path = output_path.parent / "schema.txt"
    with open(schema_path, "w") as f:
        f.write("Unified Career Dataset Schema\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total rows: {len(gold_df):,}\n")
        f.write(f"Unique players: {gold_df['PLAYER_UID'].nunique():,}\n\n")
        f.write("Columns:\n")
        for i, col in enumerate(gold_df.columns, 1):
            dtype = gold_df[col].dtype
            non_null = gold_df[col].notna().sum()
            coverage = non_null / len(gold_df) * 100
            f.write(f"  {i}. {col}: {dtype} ({coverage:.1f}% coverage)\n")

    print(f"  ✓ Saved schema to {schema_path}")


def generate_summary_stats(gold_df: pd.DataFrame) -> dict:
    """Generate summary statistics for the unified dataset.

    Args:
        gold_df: Unified career dataset

    Returns:
        Dictionary of summary statistics
    """
    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_records": len(gold_df),
        "unique_players": gold_df["PLAYER_UID"].nunique(),
        "leagues": gold_df["SOURCE_LEAGUE"].unique().tolist(),
        "date_range": {
            "min": gold_df["GAME_DATE"].min().isoformat()
            if pd.notna(gold_df["GAME_DATE"].min())
            else None,
            "max": gold_df["GAME_DATE"].max().isoformat()
            if pd.notna(gold_df["GAME_DATE"].max())
            else None,
        },
        "league_distribution": gold_df["SOURCE_LEAGUE"].value_counts().to_dict(),
        "confidence_distribution": gold_df["CONFIDENCE"].value_counts().to_dict(),
        "match_rule_distribution": gold_df["MATCH_RULE"].value_counts().to_dict(),
        "avg_games_per_player": len(gold_df) / gold_df["PLAYER_UID"].nunique(),
        "multi_league_players": gold_df.groupby("PLAYER_UID")["SOURCE_LEAGUE"]
        .nunique()
        .gt(1)
        .sum(),
    }

    return stats


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Build unified player career dataset from Tier 1 leagues"
    )
    parser.add_argument(
        "--output",
        default="data/gold/player_career_unified_tier1.parquet",
        help="Output file path (default: data/gold/player_career_unified_tier1.parquet)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.0,
        help="Minimum confidence for player edges (default: 0.0 = include all)",
    )
    parser.add_argument(
        "--leagues",
        nargs="+",
        help="Specific leagues to include (default: all Tier 1)",
        default=None,
    )

    args = parser.parse_args()

    print("=" * 80)
    print("UNIFIED PLAYER CAREER DATASET BUILDER")
    print("=" * 80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"Confidence threshold: {args.confidence_threshold:.2f}")

    # Load canonical data
    canonical_df = load_canonical_data_all_leagues(leagues=args.leagues)

    # Load player edges
    print("\n" + "=" * 80)
    print("LOADING PLAYER EDGES")
    print("=" * 80)

    edges_path = Path("data/identity/player_edges_multigate.parquet")
    if not edges_path.exists():
        print(f"ERROR: Player edges not found at {edges_path}")
        print("Run multi_gate_player_matcher.py first!")
        return 1

    edges_df = pd.read_parquet(edges_path)
    print(f"  ✓ Loaded {len(edges_df):,} player edges")
    print(f"  ✓ Unique players: {edges_df['PLAYER_UID'].nunique():,}")
    print("\n  Confidence distribution:")
    for conf, count in sorted(edges_df["CONFIDENCE"].value_counts().items(), reverse=True):
        pct = count / len(edges_df) * 100
        print(f"    {conf:.2f}: {count:,} ({pct:.1f}%)")

    # Build unified dataset
    gold_df = build_unified_career_dataset(
        canonical_df, edges_df, confidence_threshold=args.confidence_threshold
    )

    # Save dataset
    output_path = Path(args.output)
    save_gold_dataset(gold_df, output_path)

    # Generate and save summary stats
    print("\n" + "=" * 80)
    print("GENERATING SUMMARY STATISTICS")
    print("=" * 80)

    stats = generate_summary_stats(gold_df)

    stats_path = Path("data/_reports/unified_career_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    import json

    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"  ✓ Saved statistics to {stats_path}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total records: {stats['total_records']:,}")
    print(f"Unique players: {stats['unique_players']:,}")
    print(f"Avg games per player: {stats['avg_games_per_player']:.1f}")
    print(f"Multi-league players: {stats['multi_league_players']:,}")
    print(f"\nDate range: {stats['date_range']['min']} to {stats['date_range']['max']}")
    print("\nLeague distribution:")
    for league, count in sorted(
        stats["league_distribution"].items(), key=lambda x: x[1], reverse=True
    ):
        pct = count / stats["total_records"] * 100
        print(f"  {league}: {count:,} ({pct:.1f}%)")

    print("\n" + "=" * 80)
    print("BUILD COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
