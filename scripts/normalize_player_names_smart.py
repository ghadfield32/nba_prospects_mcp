#!/usr/bin/env python3
"""Smart Player Name Normalization - Fix Multi-UID Player Splits

This script implements format-aware name normalization to prevent players from
being split across multiple UIDs due to league-specific name format differences.

Problem:
  - EuroLeague: "DONCIC, LUKA" → current: "doncic_luka"
  - ACB: "L. Doncic" → current: "l_doncic"
  - Result: Same player gets 13 different UIDs instead of 1

Solution:
  - Detect format patterns: "LAST, FIRST" vs "I. Last" vs "First Last"
  - Use NBA player data as source of truth to expand initials
  - Standardize all to canonical "firstname_lastname" format
  - Add extensive debugging to show each transformation step

Usage:
    python scripts/normalize_player_names_smart.py --debug --test-only
    python scripts/normalize_player_names_smart.py --apply
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# Global NBA lookup tables (loaded once)
NBA_INITIAL_LAST_LOOKUP = None
NBA_LAST_NAME_LOOKUP = None


def load_nba_lookup_tables():
    """Load NBA name lookup tables from JSON files.

    Returns:
        Tuple of (initial_last_lookup, last_name_lookup) dicts
    """
    global NBA_INITIAL_LAST_LOOKUP, NBA_LAST_NAME_LOOKUP

    if NBA_INITIAL_LAST_LOOKUP is not None:
        # Already loaded
        return NBA_INITIAL_LAST_LOOKUP, NBA_LAST_NAME_LOOKUP

    print("Loading NBA lookup tables...")

    initial_last_path = Path("data/mappings/nba_initial_last_lookup.json")
    last_name_path = Path("data/mappings/nba_last_name_lookup.json")

    if not initial_last_path.exists():
        print(f"WARNING: NBA lookup not found at {initial_last_path}")
        print("Run: python scripts/build_nba_name_lookup.py")
        NBA_INITIAL_LAST_LOOKUP = {}
        NBA_LAST_NAME_LOOKUP = {}
        return NBA_INITIAL_LAST_LOOKUP, NBA_LAST_NAME_LOOKUP

    with open(initial_last_path) as f:
        NBA_INITIAL_LAST_LOOKUP = json.load(f)

    with open(last_name_path) as f:
        NBA_LAST_NAME_LOOKUP = json.load(f)

    print(f"  Loaded {len(NBA_INITIAL_LAST_LOOKUP):,} initial+last lookups")
    print(f"  Loaded {len(NBA_LAST_NAME_LOOKUP):,} last name lookups")

    return NBA_INITIAL_LAST_LOOKUP, NBA_LAST_NAME_LOOKUP


class NameNormalizationDebugger:
    """Debug logger for name transformation steps."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.transformations = []

    def log_step(self, step: str, original: str, result: str, reason: str):
        """Log a transformation step."""
        if self.enabled:
            self.transformations.append(
                {"step": step, "original": original, "result": result, "reason": reason}
            )
            print(f"  [{step}] '{original}' → '{result}' ({reason})")

    def get_summary(self):
        """Return summary of all transformations."""
        return pd.DataFrame(self.transformations)


def detect_name_format(name: str) -> str:
    """Detect the format pattern of a player name.

    Formats:
        - "LAST, FIRST" (EuroLeague): Contains comma
        - "I. Last" (NCAA/ACB): Starts with 1-2 chars + period + space
        - "First Last" (G-League/NBL/OTE): Multiple words, no special patterns
        - "SINGLE" (Edge case): Single word name

    Args:
        name: Raw player name

    Returns:
        Format identifier: "LAST_COMMA_FIRST", "INITIAL_DOT_LAST", "FIRST_LAST", "SINGLE"
    """
    if not name or pd.isna(name):
        return "EMPTY"

    name_clean = name.strip()

    # Pattern 1: "LAST, FIRST" (comma-separated)
    if "," in name_clean:
        return "LAST_COMMA_FIRST"

    # Pattern 2: "I. Last" or "I.Last" (initial with period)
    # Match: 1-2 chars, period, optional space, then rest
    if re.match(r"^[A-Z]{1,2}\.\s*[A-Z]", name_clean, re.IGNORECASE):
        return "INITIAL_DOT_LAST"

    # Pattern 3: Single word (e.g., "Nene", "Pele")
    if len(name_clean.split()) == 1:
        return "SINGLE"

    # Pattern 4: "First Last" (default)
    return "FIRST_LAST"


def normalize_name_smart(name: str, debug: bool = False) -> str:
    """Smart name normalization that handles league-specific formats.

    Transformation Pipeline:
        1. Detect format pattern
        2. Standardize to "First Last" format
        3. Remove accents/special characters
        4. Lowercase
        5. Replace spaces with underscores

    Args:
        name: Raw player name from any league
        debug: If True, print detailed transformation steps

    Returns:
        Normalized name key (e.g., "luka_doncic")

    Examples:
        >>> normalize_name_smart("DONCIC, LUKA")
        'luka_doncic'
        >>> normalize_name_smart("L. Doncic")
        'l_doncic'  # Note: Initial expansion requires external lookup
        >>> normalize_name_smart("Luka Doncic")
        'luka_doncic'
    """
    debugger = NameNormalizationDebugger(enabled=debug)

    if not name or pd.isna(name):
        return ""

    original_name = str(name)
    debugger.log_step("INPUT", "", original_name, "Raw input from source")

    # Step 1: Detect format
    name_format = detect_name_format(original_name)
    debugger.log_step("DETECT", original_name, name_format, "Format pattern detected")

    # Step 2: Standardize format to "First Last"
    standardized = original_name

    if name_format == "LAST_COMMA_FIRST":
        # "DONCIC, LUKA" → "LUKA DONCIC"
        parts = [p.strip() for p in original_name.split(",")]
        if len(parts) == 2:
            last_name, first_name = parts
            standardized = f"{first_name} {last_name}"
            debugger.log_step(
                "REVERSE", original_name, standardized, "Reversed LAST, FIRST to FIRST LAST"
            )

    elif name_format == "INITIAL_DOT_LAST":
        # "L. Doncic" → Expand using NBA lookup
        # Load NBA lookups if not already loaded
        initial_last_lookup, _ = load_nba_lookup_tables()

        # Parse initial and last name
        match = re.match(r"^([A-Z]{1,2})\.\s*(.+)$", original_name, re.IGNORECASE)
        if match:
            initial = match.group(1).lower()
            last_name = match.group(2).lower()

            # Normalize last name (remove accents, special chars)
            last_norm = unicodedata.normalize("NFD", last_name)
            last_norm = "".join(c for c in last_norm if unicodedata.category(c) != "Mn")
            last_norm = re.sub(r"[^a-z0-9]", "", last_norm)

            # Create lookup key: "i_lastname"
            lookup_key = f"{initial}_{last_norm}"

            if lookup_key in initial_last_lookup:
                # Found in NBA data - use full name
                full_name_nba = initial_last_lookup[lookup_key]
                standardized = full_name_nba.title()  # "luka doncic" → "Luka Doncic"
                debugger.log_step(
                    "NBA_LOOKUP",
                    original_name,
                    standardized,
                    f"Expanded using NBA lookup (key: {lookup_key})",
                )
            else:
                # Not found in NBA - keep normalized initial format
                standardized = f"{initial} {last_norm}"
                debugger.log_step(
                    "NORMALIZE_INITIAL",
                    original_name,
                    standardized,
                    f"NBA lookup failed for '{lookup_key}', kept initial format",
                )
        else:
            # Regex didn't match - just remove period
            standardized = re.sub(r"([A-Z])\.", r"\1", original_name)
            debugger.log_step(
                "NORMALIZE_INITIAL",
                original_name,
                standardized,
                "Removed period from initial (regex parse failed)",
            )

    # Step 3: Unicode normalization (remove accents)
    # "Luka Dončić" → "Luka Doncic"
    normalized_unicode = unicodedata.normalize("NFD", standardized)
    no_accents = "".join(c for c in normalized_unicode if unicodedata.category(c) != "Mn")

    if no_accents != standardized:
        debugger.log_step("UNICODE", standardized, no_accents, "Removed accent marks")
    standardized = no_accents

    # Step 4: Lowercase
    lowercased = standardized.lower()
    debugger.log_step("LOWERCASE", standardized, lowercased, "Converted to lowercase")

    # Step 5: Remove special characters (keep only alphanumeric and spaces)
    cleaned = re.sub(r"[^a-z0-9\s]", "", lowercased)
    if cleaned != lowercased:
        debugger.log_step("CLEAN", lowercased, cleaned, "Removed special characters")

    # Step 6: Collapse whitespace and replace with underscores
    final = re.sub(r"\s+", "_", cleaned.strip())
    debugger.log_step("FINAL", cleaned, final, "Replaced spaces with underscores")

    if debug:
        print(f"\nFINAL TRANSFORMATION: '{original_name}' → '{final}'\n")

    return final


def analyze_name_formats_in_data(data_path: Path) -> pd.DataFrame:
    """Analyze name format patterns in existing dataset.

    Args:
        data_path: Path to unified career dataset

    Returns:
        DataFrame with format distribution by league
    """
    print("Loading unified dataset...")
    df = pd.read_parquet(data_path)

    print("Analyzing name formats by league...")

    # Sample players from each league
    results = []

    for league in df["SOURCE_LEAGUE"].unique():
        league_df = df[df["SOURCE_LEAGUE"] == league]
        sample_names = league_df["PLAYER_NAME_RAW"].dropna().unique()[:20]

        format_counts = {}
        for name in sample_names:
            fmt = detect_name_format(name)
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        # Determine dominant format
        if format_counts:
            dominant_format = max(format_counts, key=format_counts.get)
        else:
            dominant_format = "UNKNOWN"

        results.append(
            {
                "league": league,
                "dominant_format": dominant_format,
                "format_distribution": format_counts,
                "sample_names": list(sample_names[:5]),
            }
        )

    return pd.DataFrame(results)


def test_normalization_on_luka_doncic(data_path: Path):
    """Test smart normalization on Luka Doncic case (13 UIDs → 1 UID).

    This is our primary test case to validate the fix works.
    """
    print("\n" + "=" * 80)
    print("TEST CASE: Luka Doncic Name Normalization")
    print("=" * 80)

    df = pd.read_parquet(data_path)

    # Find all Luka Doncic variations
    luka_mask = df["PLAYER_NAME_RAW"].str.contains("doncic", case=False, na=False)
    luka_df = df[luka_mask].copy()

    # Detect NAME_KEY column (may be NAME_KEY or NAME_KEY_x from merge)
    name_key_col = None
    for col in ["NAME_KEY", "NAME_KEY_x", "NAME_KEY_y"]:
        if col in luka_df.columns:
            name_key_col = col
            break

    if name_key_col is None:
        print("WARNING: No NAME_KEY column found in dataset")
        print(f"Available columns: {luka_df.columns.tolist()}")
        print("\nSkipping NAME_KEY comparison, will only test normalization logic")
        name_key_col = None
    else:
        print(f"Using NAME_KEY column: {name_key_col}")

    print(f"\nFound {len(luka_df)} games with 'doncic' in player name")
    print(f"Current UIDs: {luka_df['PLAYER_UID'].nunique()}")

    if name_key_col:
        print(f"Current NAME_KEYs: {luka_df[name_key_col].nunique()}\n")

        # Show current NAME_KEY variations
        current_variations = (
            luka_df.groupby(["PLAYER_NAME_RAW", name_key_col, "SOURCE_LEAGUE"])
            .size()
            .reset_index(name="games")
        )
        current_variations = current_variations.sort_values("games", ascending=False)

        print("Current NAME_KEY variations:")
        print(current_variations.to_string(index=False))

    # Apply smart normalization
    print("\n" + "-" * 80)
    print("Applying smart normalization...")
    print("-" * 80 + "\n")

    unique_names = luka_df["PLAYER_NAME_RAW"].unique()

    new_name_keys = {}
    for name in unique_names:
        print(f"\nProcessing: '{name}'")
        new_key = normalize_name_smart(name, debug=True)
        new_name_keys[name] = new_key

    # Compare results
    print("\n" + "=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)

    comparison = []
    for name in unique_names:
        if name_key_col:
            old_key = luka_df[luka_df["PLAYER_NAME_RAW"] == name][name_key_col].iloc[0]
        else:
            old_key = "N/A"
        new_key = new_name_keys[name]
        comparison.append(
            {
                "original_name": name,
                "old_name_key": old_key,
                "new_name_key": new_key,
                "changed": old_key != new_key if name_key_col else "N/A",
            }
        )

    comparison_df = pd.DataFrame(comparison)
    print(comparison_df.to_string(index=False))

    # Count unique new keys
    unique_new_keys = set(new_name_keys.values())
    if name_key_col:
        print(f"\n✓ Current unique NAME_KEYs: {luka_df[name_key_col].nunique()}")
    print(f"✓ After smart normalization: {len(unique_new_keys)}")
    if name_key_col:
        print(
            f"✓ Improvement: {luka_df[name_key_col].nunique() - len(unique_new_keys)} fewer splits"
        )

    if len(unique_new_keys) == 1:
        print("\n✓✓✓ SUCCESS! All Luka Doncic variations now map to single NAME_KEY")
    else:
        print(f"\n⚠ WARNING: Still {len(unique_new_keys)} unique keys remaining")
        print("Unique new keys:", unique_new_keys)


def apply_smart_normalization_to_dataset(input_path: Path, output_path: Path):
    """Apply smart normalization to entire dataset and save updated version.

    Args:
        input_path: Path to current unified dataset
        output_path: Path to save updated dataset with smart normalization
    """
    print("\n" + "=" * 80)
    print("APPLYING SMART NORMALIZATION TO FULL DATASET")
    print("=" * 80)

    print(f"\nLoading data from: {input_path}")
    df = pd.read_parquet(input_path)

    print(f"Total records: {len(df):,}")

    # Detect NAME_KEY column
    name_key_col = None
    for col in ["NAME_KEY", "NAME_KEY_x", "NAME_KEY_y"]:
        if col in df.columns:
            name_key_col = col
            break

    if name_key_col:
        print(f"Found NAME_KEY column: {name_key_col}")
        print(f"Current unique NAME_KEYs: {df[name_key_col].nunique():,}")
    else:
        print("No NAME_KEY column found, will create new one")

    # Apply smart normalization
    print("\nApplying smart normalization to all player names...")

    # Create new NAME_KEY column
    df["NAME_KEY_NEW"] = df["PLAYER_NAME_RAW"].apply(lambda x: normalize_name_smart(x, debug=False))

    # Compare old vs new if old column exists
    if name_key_col:
        changes = df[df[name_key_col] != df["NAME_KEY_NEW"]]
        print(
            f"\nRecords with changed NAME_KEY: {len(changes):,} ({len(changes)/len(df)*100:.1f}%)"
        )

        # Show sample changes
        if len(changes) > 0:
            print("\nSample changes:")
            sample = (
                changes.groupby(["PLAYER_NAME_RAW", name_key_col, "NAME_KEY_NEW"])
                .size()
                .reset_index(name="records")
            )
            sample = sample.head(20)
            print(sample.to_string(index=False))

    # Replace old NAME_KEY with new
    if name_key_col:
        df["NAME_KEY_OLD"] = df[name_key_col]
        df.drop(columns=[name_key_col], inplace=True)

    df["NAME_KEY"] = df["NAME_KEY_NEW"]
    df.drop(columns=["NAME_KEY_NEW"], inplace=True)

    print(f"\nNew unique NAME_KEYs: {df['NAME_KEY'].nunique():,}")
    if name_key_col and "NAME_KEY_OLD" in df.columns:
        print(
            f"Reduction: {df['NAME_KEY_OLD'].nunique() - df['NAME_KEY'].nunique():,} fewer unique keys"
        )

    # Save updated dataset
    print(f"\nSaving updated dataset to: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"✓ Saved {len(df):,} records")
    print(f"✓ File size: {file_size_mb:.1f} MB")

    return df


def main():
    """Main execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Smart player name normalization")
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Run test on Luka Doncic only, don't modify dataset",
    )
    parser.add_argument(
        "--analyze", action="store_true", help="Analyze name format patterns in dataset"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply smart normalization to full dataset"
    )
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging")

    args = parser.parse_args()

    # Default: Run test only
    if not (args.test_only or args.analyze or args.apply):
        args.test_only = True

    data_path = Path("data/gold/player_career_unified_tier1.parquet")

    if not data_path.exists():
        print(f"ERROR: Dataset not found at {data_path}")
        return 1

    if args.analyze:
        print("Analyzing name format patterns...")
        format_analysis = analyze_name_formats_in_data(data_path)
        print("\nFormat distribution by league:")
        print(format_analysis.to_string(index=False))

    if args.test_only or args.debug:
        test_normalization_on_luka_doncic(data_path)

    if args.apply:
        response = input("\nThis will modify the dataset. Continue? (yes/no): ").strip().lower()
        if response != "yes":
            print("Aborted.")
            return 0

        output_path = Path("data/gold/player_career_unified_tier1_normalized.parquet")
        apply_smart_normalization_to_dataset(data_path, output_path)

        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("1. Re-run player matching with new NAME_KEYs:")
        print("   python scripts/multi_gate_player_matcher.py")
        print("\n2. Rebuild unified career dataset:")
        print("   python scripts/build_unified_career_gold_chunked.py")
        print("\n3. Validate Luka Doncic now has single UID:")
        print("   python scripts/validate_multi_league_players.py --player 'doncic'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
