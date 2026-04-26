#!/usr/bin/env python3
"""Build Gold Layer Unified Player Career Dataset (Memory-Efficient Version)

Processes leagues one at a time to avoid memory issues.

Usage:
    python scripts/build_unified_career_gold_chunked.py
"""

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name with smart format handling.

    This function implements format-aware normalization to prevent player splits:
    - "LAST, FIRST" (EuroLeague) → "first_last"
    - "I. Last" (ACB, NCAA) → Expands to "first_last" using NBA lookup
    - "First Last" (standard) → "first_last"

    Returns:
        Normalized name key (e.g., "luka_doncic")
    """
    if not name or pd.isna(name):
        return ""

    original_name = str(name).strip()

    # Step 1: Detect and handle format patterns
    standardized = original_name

    # Pattern 1: "LAST, FIRST" (comma-separated) → Reverse to "FIRST LAST"
    if "," in original_name:
        parts = [p.strip() for p in original_name.split(",")]
        if len(parts) == 2:
            last_name, first_name = parts
            standardized = f"{first_name} {last_name}"

    # Pattern 2: "I. Last" or "I.Last" (initial with period) → Expand using NBA lookup
    elif re.match(r"^[A-Z]{1,2}\.\s*[A-Z]", original_name, re.IGNORECASE):
        # Try to expand using NBA lookup
        match = re.match(r"^([A-Z]{1,2})\.\s*(.+)$", original_name, re.IGNORECASE)
        if match:
            initial = match.group(1).lower()
            last_name = match.group(2).lower()

            # Normalize last name for lookup
            last_norm = unicodedata.normalize("NFD", last_name)
            last_norm = "".join(c for c in last_norm if unicodedata.category(c) != "Mn")
            last_norm = re.sub(r"[^a-z0-9]", "", last_norm)

            # Load NBA lookup (cached in global var after first call)
            global NBA_INITIAL_LAST_LOOKUP
            if NBA_INITIAL_LAST_LOOKUP is None:
                import json

                lookup_path = Path("data/mappings/nba_initial_last_lookup.json")
                if lookup_path.exists():
                    with open(lookup_path) as f:
                        NBA_INITIAL_LAST_LOOKUP = json.load(f)
                else:
                    NBA_INITIAL_LAST_LOOKUP = {}

            # Try NBA lookup
            lookup_key = f"{initial}_{last_norm}"
            if lookup_key in NBA_INITIAL_LAST_LOOKUP:
                standardized = NBA_INITIAL_LAST_LOOKUP[lookup_key].title()
            else:
                # Not in NBA - keep normalized initial format
                standardized = f"{initial} {last_norm}"

    # Step 2: Unicode normalization (remove accents)
    normalized_unicode = unicodedata.normalize("NFD", standardized)
    standardized = "".join(c for c in normalized_unicode if unicodedata.category(c) != "Mn")

    # Step 3: Lowercase and clean
    standardized = standardized.lower()
    standardized = re.sub(r"[^a-z0-9\s]", "", standardized)

    # Step 4: Collapse whitespace and replace with underscores
    final = re.sub(r"\s+", "_", standardized.strip())

    return final


# Global cache for NBA lookup (loaded once on first use)
NBA_INITIAL_LAST_LOOKUP = None


def process_single_league(league: str, edges_df: pd.DataFrame) -> pd.DataFrame:
    """Process a single league and join with player edges.

    Args:
        league: League code (e.g., "NCAA_MBB")
        edges_df: Player edges dataframe

    Returns:
        Processed dataframe for this league
    """
    print(f"\nProcessing {league}...")

    # League code mapping
    league_code_map = {
        "GLEAGUE": "G_LEAGUE",
        "G_LEAGUE": "G_LEAGUE",
    }
    league_normalized = league_code_map.get(league, league)

    # Load canonical data for this league
    base_path = Path("data/canonical/box_player_game")
    league_dir = base_path / f"league={league_normalized}"

    if not league_dir.exists():
        print(f"  WARNING: {league} directory not found, skipping")
        return pd.DataFrame()

    all_league_data = []

    # Load all seasons for this league
    season_dirs = sorted([d for d in league_dir.iterdir() if d.is_dir()])

    for season_dir in season_dirs:
        data_file = season_dir / "data.parquet"

        if data_file.exists():
            try:
                df = pd.read_parquet(data_file)

                # Add league column if missing
                if "LEAGUE" not in df.columns or df["LEAGUE"].isna().all():
                    df["LEAGUE"] = league_normalized

                df.rename(columns={"LEAGUE": "SOURCE_LEAGUE"}, inplace=True)

                all_league_data.append(df)
                print(f"  [OK] Loaded {season_dir.name}: {len(df):,} records")
            except Exception as e:
                print(f"  [ERROR] Error loading {data_file}: {e}")

    if not all_league_data:
        return pd.DataFrame()

    # Combine all seasons for this league
    league_df = pd.concat(all_league_data, ignore_index=True)

    print(f"  Total {league} records: {len(league_df):,}")

    # Drop gold layer columns if present (contaminated data)
    gold_columns = [
        "PLAYER_UID",
        "CANONICAL_PLAYER_ID",
        "CAREER_GAME_NUMBER",
        "LEAGUE_GAME_NUMBER",
        "CONFIDENCE",
        "MATCH_RULE",
    ]
    cols_to_drop = [col for col in gold_columns if col in league_df.columns]
    if cols_to_drop:
        print(f"  WARNING: Dropping contaminated gold columns: {cols_to_drop}")
        league_df = league_df.drop(columns=cols_to_drop)

    # Filter edges to this league
    league_edges = edges_df[edges_df["SOURCE_LEAGUE"] == league_normalized].copy()

    print(f"  Player edges for {league}: {len(league_edges):,}")

    if len(league_edges) == 0:
        print(f"  WARNING: No player edges found for {league_normalized}")
        return pd.DataFrame()

    # Optimize datatypes
    league_df["SOURCE_LEAGUE"] = league_df["SOURCE_LEAGUE"].astype("category")
    league_df["SOURCE_PLAYER_ID"] = league_df["SOURCE_PLAYER_ID"].astype(str)
    league_edges["SOURCE_PLAYER_ID"] = league_edges["SOURCE_PLAYER_ID"].astype(str)

    # Check if SOURCE_PLAYER_ID is reliable (not all "None")
    none_count = (league_df["SOURCE_PLAYER_ID"] == "None").sum()
    none_pct = none_count / len(league_df) * 100

    print(f"  SOURCE_PLAYER_ID reliability: {none_pct:.1f}% are 'None'")

    # Choose join strategy
    if none_pct > 50:
        # Use NAME_KEY join for CEBL and other leagues with unreliable IDs
        print("  Using NAME_KEY join (unreliable SOURCE_PLAYER_IDs)")

        # Ensure NAME_KEY exists
        if "NAME_KEY" not in league_df.columns:
            league_df["NAME_KEY"] = league_df["PLAYER_NAME_RAW"].apply(normalize_name)

        merged_df = league_df.merge(
            league_edges[["NAME_KEY", "PLAYER_UID", "MATCH_RULE", "CONFIDENCE"]],
            on="NAME_KEY",
            how="inner",
        )
    else:
        # Use SOURCE_PLAYER_ID join for reliable leagues
        print("  Using SOURCE_PLAYER_ID join")

        merged_df = league_df.merge(
            league_edges[
                ["SOURCE_PLAYER_ID", "PLAYER_UID", "NAME_KEY", "MATCH_RULE", "CONFIDENCE"]
            ],
            on="SOURCE_PLAYER_ID",
            how="inner",
        )

    merge_count = len(merged_df)
    original_count = len(league_df)
    inflation_pct = (merge_count / original_count) * 100 if original_count > 0 else 0.0

    print(f"  After merge: {merge_count:,} records ({inflation_pct:.1f}% of original)")
    print(f"  Unique players: {merged_df['PLAYER_UID'].nunique():,}")

    # CRITICAL VALIDATION: Must be exactly 100.0% (no inflation!)
    if inflation_pct > 100.0:
        raise ValueError(
            f"CRITICAL: Merge inflated rows for {league}!\n"
            f"  Original: {original_count:,} records\n"
            f"  After merge: {merge_count:,} records ({inflation_pct:.1f}%)\n"
            f"  This indicates duplicate join keys in player_map.\n"
            f"  Expected: 100.0% row retention (1:1 mapping)"
        )

    return merged_df


def main():
    """Main execution."""
    print("=" * 80)
    print("UNIFIED PLAYER CAREER DATASET BUILDER (CHUNKED)")
    print("=" * 80)

    # Load player map (1:1 join key - guaranteed no duplicates)
    print("\nLoading player identity map...")
    player_map_path = Path("data/identity/player_map.parquet")

    if not player_map_path.exists():
        print(f"ERROR: player_map.parquet not found at {player_map_path}")
        print("Please run multi_gate_player_matcher.py first to generate player_map.parquet")
        return 1

    edges_df = pd.read_parquet(player_map_path)
    print(f"[OK] Loaded {len(edges_df):,} player mappings")

    # CRITICAL VALIDATION: Ensure 1:1 mapping (no duplicate join keys)
    unique_join_keys = edges_df.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]).ngroups

    if len(edges_df) != unique_join_keys:
        duplicates = len(edges_df) - unique_join_keys
        raise ValueError(
            f"CRITICAL: player_map.parquet has {duplicates} duplicate join keys!\n"
            f"Expected {len(edges_df)} unique (SOURCE_LEAGUE, SOURCE_PLAYER_ID) pairs, "
            f"but found only {unique_join_keys}.\n"
            f"This should never happen if player_map was created via deduplicate_to_player_map()."
        )

    print(
        f"[OK] Validated 1:1 mapping: {unique_join_keys:,} unique (SOURCE_LEAGUE, SOURCE_PLAYER_ID) pairs"
    )

    # Process each league
    leagues = ["NCAA_MBB", "GLEAGUE", "ABA_ADRIATIC", "NBL", "CEBL", "OTE", "EUROLEAGUE", "ACB"]

    all_gold_data = []

    for league in leagues:
        league_gold = process_single_league(league, edges_df)

        if len(league_gold) > 0:
            all_gold_data.append(league_gold)

    # Combine all leagues
    print("\n" + "=" * 80)
    print("COMBINING ALL LEAGUES")
    print("=" * 80)

    gold_df = pd.concat(all_gold_data, ignore_index=True)

    print(f"Total combined records: {len(gold_df):,}")
    print(f"Unique players: {gold_df['PLAYER_UID'].nunique():,}")

    # Deduplicate rows (Session 331/332: Fix duplicate PKs)
    # Primary key: (PLAYER_UID, SOURCE_LEAGUE, SEASON, GAME_ID)
    # Note: SEASON is needed because same GAME_ID can appear in multiple season directories
    print("\nDeduplicating rows...")
    pk_cols = ["PLAYER_UID", "SOURCE_LEAGUE", "SEASON", "GAME_ID"]
    before_dedup = len(gold_df)
    gold_df = gold_df.drop_duplicates(subset=pk_cols, keep="first")
    after_dedup = len(gold_df)
    removed = before_dedup - after_dedup
    print(f"  Before: {before_dedup:,} rows")
    print(f"  After: {after_dedup:,} rows")
    print(f"  Removed: {removed:,} duplicates ({removed/before_dedup*100:.2f}%)")

    # Add CANONICAL_PLAYER_ID alias
    gold_df["CANONICAL_PLAYER_ID"] = gold_df["PLAYER_UID"]

    # Fix PLAYER_NAME column (Session 335: 99.1% were NULL)
    # Create display name from NAME_KEY_y (from player_map)
    print("\nFixing PLAYER_NAME column...")
    if "NAME_KEY_y" in gold_df.columns:
        # Convert name_key to Title Case (e.g., "zion_williamson" -> "Zion Williamson")
        gold_df["PLAYER_NAME"] = gold_df["NAME_KEY_y"].apply(
            lambda k: k.replace("_", " ").title() if pd.notna(k) and k else None
        )
        gold_df["PLAYER_NAME"].isna().sum()
        null_after = gold_df["PLAYER_NAME"].isna().sum()
        print(
            f"  PLAYER_NAME populated: {len(gold_df) - null_after:,} records ({(len(gold_df) - null_after)/len(gold_df)*100:.1f}%)"
        )
    else:
        print("  WARNING: NAME_KEY_y column not found, PLAYER_NAME not populated")

    # Convert game dates
    print("\nProcessing dates...")
    gold_df["GAME_DATE"] = pd.to_datetime(gold_df["GAME_DATE"], errors="coerce")

    # Sort
    print("Sorting by PLAYER_UID and GAME_DATE...")
    gold_df = gold_df.sort_values(["PLAYER_UID", "GAME_DATE"])

    # Calculate sequence numbers
    print("Calculating career sequence numbers...")

    gold_df["CAREER_GAME_NUMBER"] = gold_df.groupby("PLAYER_UID").cumcount() + 1
    gold_df["LEAGUE_GAME_NUMBER"] = gold_df.groupby(["PLAYER_UID", "SOURCE_LEAGUE"]).cumcount() + 1

    # Days since first game
    first_game = gold_df.groupby("PLAYER_UID")["GAME_DATE"].transform("first")
    gold_df["DAYS_SINCE_FIRST_GAME"] = (gold_df["GAME_DATE"] - first_game).dt.days

    # Fix data type issues before saving
    print("\nFixing data types...")

    # Convert MIN and PLUS_MINUS to string (OTE has special formats)
    string_cols = ["MIN", "PLUS_MINUS"]
    for col in string_cols:
        if col in gold_df.columns:
            gold_df[col] = gold_df[col].astype(str)

    # Ensure numeric columns are float or int
    numeric_cols = [
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "PF",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
    ]
    for col in numeric_cols:
        if col in gold_df.columns:
            gold_df[col] = pd.to_numeric(gold_df[col], errors="coerce").fillna(0).astype("Int64")

    # Percentage columns as float
    pct_cols = ["FG_PCT", "FG3_PCT", "FT_PCT"]
    for col in pct_cols:
        if col in gold_df.columns:
            gold_df[col] = pd.to_numeric(gold_df[col], errors="coerce")

    # Save
    print("\n" + "=" * 80)
    print("SAVING")
    print("=" * 80)

    output_path = Path("data/gold/player_career_unified_tier1.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gold_df.to_parquet(output_path, index=False)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"[OK] Saved to {output_path}")
    print(f"  Records: {len(gold_df):,}")
    print(f"  Players: {gold_df['PLAYER_UID'].nunique():,}")
    print(f"  File size: {file_size_mb:.1f} MB")

    # Summary stats
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print("\nLeague distribution:")
    for league, count in gold_df["SOURCE_LEAGUE"].value_counts().items():
        pct = count / len(gold_df) * 100
        print(f"  {league}: {count:,} ({pct:.1f}%)")

    print("\nConfidence distribution:")
    for conf, count in sorted(gold_df["CONFIDENCE"].value_counts().items(), reverse=True):
        pct = count / len(gold_df) * 100
        print(f"  {conf:.2f}: {count:,} ({pct:.1f}%)")

    multi_league = gold_df.groupby("PLAYER_UID")["SOURCE_LEAGUE"].nunique().gt(1).sum()
    print(f"\nMulti-league players: {multi_league:,}")

    print("\n[OK] BUILD COMPLETE")

    return 0


if __name__ == "__main__":
    sys.exit(main())
