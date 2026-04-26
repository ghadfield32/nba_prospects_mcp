#!/usr/bin/env python3
"""Multi-Gate Progressive Player Matching System

Implements 5-gate progressive matching using ONLY available data (no bio dependency):
- Gate 1: Exact unique name (1.0 confidence)
- Gate 2: Same-league unique ID (0.95 confidence)
- Gate 3: Temporal no-overlap (0.90 confidence)
- Gate 4: Statistical signature (0.85 confidence)
- Gate 5: Team history validation (0.80 confidence)
- Unresolved: Insufficient data (0.0 confidence)

Usage:
    python scripts/multi_gate_player_matcher.py
    python scripts/multi_gate_player_matcher.py --leagues NCAA_MBB GLEAGUE OTE
    python scripts/multi_gate_player_matcher.py --output data/identity/player_edges_multigate.parquet
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def normalize_name(name: str) -> str:
    """Create deterministic name key from player name with smart format handling.

    This function implements format-aware normalization to prevent player splits:
    - "LAST, FIRST" (EuroLeague) → "first_last"
    - "I. Last" (ACB, NCAA) → Expands to "first_last" using NBA lookup
    - "First Last" (standard) → "first_last"

    Args:
        name: Raw player name

    Returns:
        Normalized name key (e.g., "luka_doncic")
    """
    if not name or pd.isna(name):
        return ""

    import unicodedata

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


def generate_player_uid(name_key: str, suffix: str = "") -> str:
    """Generate deterministic player UID.

    Args:
        name_key: Normalized name key
        suffix: Optional suffix for disambiguation

    Returns:
        Player UID (e.g., P_john_smith_a3f2c1)
    """
    base = f"{name_key}_{suffix}" if suffix else name_key

    # Create short hash for uniqueness
    hash_suffix = hashlib.md5(base.encode()).hexdigest()[:6]

    return f"P_{name_key[:20]}_{hash_suffix}"


class MultiGatePlayerMatcher:
    """Progressive player matching through 5 gates."""

    def __init__(self, canonical_df: pd.DataFrame):
        """Initialize matcher with canonical player-game data.

        Args:
            canonical_df: DataFrame with columns:
                - SOURCE_LEAGUE
                - SOURCE_PLAYER_ID
                - PLAYER_NAME_RAW
                - GAME_DATE
                - PTS, REB, AST, FG_PCT, FG3_PCT, FT_PCT
                - TEAM_KEY
        """
        self.canonical_df = canonical_df.copy()
        self.matches = []
        self.unmatched = None
        self.gate_stats = {}

        # Preprocess data
        self._preprocess_data()

    def _preprocess_data(self):
        """Prepare data for matching."""
        print("\n" + "=" * 80)
        print("PREPROCESSING DATA")
        print("=" * 80)

        # Normalize names
        self.canonical_df["NAME_KEY"] = self.canonical_df["PLAYER_NAME_RAW"].apply(normalize_name)

        # Convert game dates
        self.canonical_df["GAME_DATE"] = pd.to_datetime(
            self.canonical_df["GAME_DATE"], errors="coerce"
        )

        # Create player-level aggregates for statistical matching
        self.player_stats = (
            self.canonical_df.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID", "NAME_KEY"])
            .agg(
                {
                    "PTS": ["mean", "std", "count"],
                    "REB": "mean",
                    "AST": "mean",
                    "FG_PCT": "mean",
                    "FG3_PCT": "mean",
                    "FT_PCT": "mean",
                    "GAME_DATE": ["min", "max"],
                    "TEAM_KEY": lambda x: list(x.unique()),
                }
            )
            .reset_index()
        )

        # Flatten column names
        self.player_stats.columns = [
            "_".join(col).strip("_") if isinstance(col, tuple) else col
            for col in self.player_stats.columns.values
        ]

        # Rename for clarity
        self.player_stats.rename(
            columns={
                "PTS_mean": "PPG",
                "PTS_std": "PPG_STD",
                "PTS_count": "GAMES_PLAYED",
                "REB_mean": "RPG",
                "AST_mean": "APG",
                "FG_PCT_mean": "FG_PCT",
                "FG3_PCT_mean": "FG3_PCT",
                "FT_PCT_mean": "FT_PCT",
                "GAME_DATE_min": "FIRST_GAME",
                "GAME_DATE_max": "LAST_GAME",
                "TEAM_KEY_<lambda>": "TEAMS",
            },
            inplace=True,
        )

        print(f"Total unique players: {len(self.player_stats):,}")
        print(f"Total player-game records: {len(self.canonical_df):,}")
        print(f"Leagues: {self.canonical_df['SOURCE_LEAGUE'].unique().tolist()}")

        self.unmatched = self.player_stats.copy()

    def run_all_gates(self) -> pd.DataFrame:
        """Run all 5 gates in sequence.

        Returns:
            DataFrame with columns:
                - PLAYER_UID
                - SOURCE_LEAGUE
                - SOURCE_PLAYER_ID
                - NAME_KEY
                - MATCH_RULE
                - CONFIDENCE
        """
        print("\n" + "=" * 80)
        print("MULTI-GATE PLAYER MATCHING")
        print("=" * 80)

        # Gate 1: Exact unique name
        self._gate1_exact_unique_name()

        # Gates 3-5: Try to link across leagues (skip Gate 2 for now)
        # Gate 3: Temporal no-overlap
        self._gate3_temporal_no_overlap()

        # Gate 4: Statistical signature
        self._gate4_statistical_signature()

        # Gate 5: Team history validation
        self._gate5_team_history_validation()

        # Gate 2 (DEFAULT): Trust SOURCE_PLAYER_ID for remaining players
        # This runs LAST to give Gates 3-5 a chance to link across leagues first
        self._gate2_same_league_unique_id()

        # Combine all matches
        edges_df = pd.DataFrame(self.matches)

        # Print summary
        self._print_summary(edges_df)

        return edges_df

    def _gate1_exact_unique_name(self):
        """Gate 1: NAME_KEY appears exactly once globally."""
        print("\n" + "-" * 80)
        print("GATE 1: EXACT_UNIQUE_NAME (Confidence: 1.0)")
        print("-" * 80)

        # Count name occurrences
        name_counts = self.unmatched.groupby("NAME_KEY").size()
        unique_names = name_counts[name_counts == 1].index

        # Filter to unique names
        matched = self.unmatched[self.unmatched["NAME_KEY"].isin(unique_names)]

        # Create player UIDs and edges
        for _, row in matched.iterrows():
            player_uid = generate_player_uid(row["NAME_KEY"])

            self.matches.append(
                {
                    "PLAYER_UID": player_uid,
                    "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                    "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                    "NAME_KEY": row["NAME_KEY"],
                    "MATCH_RULE": "exact_unique_name",
                    "CONFIDENCE": 1.0,
                }
            )

        # Remove matched from unmatched pool
        self.unmatched = self.unmatched[~self.unmatched["NAME_KEY"].isin(unique_names)]

        self.gate_stats["gate1"] = {
            "matched": len(matched),
            "unique_players": len(unique_names),
            "remaining": len(self.unmatched),
        }

        print(f"✓ Matched: {len(matched):,} records ({len(unique_names):,} unique players)")
        print(f"  Remaining: {len(self.unmatched):,} records")

    def _gate2_same_league_unique_id(self):
        """Gate 2: (NAME_KEY, SOURCE_LEAGUE, SOURCE_PLAYER_ID) unique - each SOURCE_PLAYER_ID gets unique UID."""
        print("\n" + "-" * 80)
        print("GATE 2: SAME_LEAGUE_UNIQUE_ID (Confidence: 0.95)")
        print("-" * 80)

        # For all remaining unmatched players, create unique UID based on SOURCE_PLAYER_ID
        # This handles cases where same name appears multiple times (different players)
        matched_count = 0
        unique_players = 0

        for _, row in self.unmatched.iterrows():
            # Create unique UID based on league + player_id
            player_uid = generate_player_uid(
                row["NAME_KEY"], suffix=f"{row['SOURCE_LEAGUE']}_{row['SOURCE_PLAYER_ID']}"
            )

            self.matches.append(
                {
                    "PLAYER_UID": player_uid,
                    "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                    "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                    "NAME_KEY": row["NAME_KEY"],
                    "MATCH_RULE": "same_league_unique_id",
                    "CONFIDENCE": 0.95,
                }
            )

            matched_count += 1
            unique_players += 1

        # Remove all matched from unmatched pool
        self.unmatched = pd.DataFrame(columns=self.unmatched.columns)

        self.gate_stats["gate2"] = {
            "matched": matched_count,
            "unique_players": unique_players,
            "remaining": 0,
        }

        print(f"✓ Matched: {matched_count:,} records ({unique_players:,} unique players)")
        print("  Remaining: 0 records")

    def _gate3_temporal_no_overlap(self):
        """Gate 3: Same NAME_KEY across leagues with no temporal overlap."""
        print("\n" + "-" * 80)
        print("GATE 3: TEMPORAL_NO_OVERLAP (Confidence: 0.90)")
        print("-" * 80)

        matched_count = 0
        matched_names = set()

        for name_key, group in self.unmatched.groupby("NAME_KEY"):
            # Check if this name appears in multiple leagues
            leagues = group["SOURCE_LEAGUE"].unique()

            if len(leagues) <= 1:
                continue  # Single league, skip (handled by gate 2)

            # Check for temporal overlap
            overlap_found = False

            for i, league1 in enumerate(leagues):
                for league2 in leagues[i + 1 :]:
                    # Get date ranges for each league
                    league1_data = group[group["SOURCE_LEAGUE"] == league1]
                    league2_data = group[group["SOURCE_LEAGUE"] == league2]

                    first1 = league1_data["FIRST_GAME"].iloc[0]
                    last1 = league1_data["LAST_GAME"].iloc[0]
                    first2 = league2_data["FIRST_GAME"].iloc[0]
                    last2 = league2_data["LAST_GAME"].iloc[0]

                    # Check if date ranges overlap (with 30-day tolerance for offseason)
                    if not (
                        last1 + timedelta(days=30) < first2 or last2 + timedelta(days=30) < first1
                    ):
                        overlap_found = True
                        break

                if overlap_found:
                    break

            if not overlap_found:
                # No overlap - likely same player across leagues
                player_uid = generate_player_uid(name_key, suffix="multiLg")

                for _, row in group.iterrows():
                    self.matches.append(
                        {
                            "PLAYER_UID": player_uid,
                            "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                            "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                            "NAME_KEY": row["NAME_KEY"],
                            "MATCH_RULE": "temporal_no_overlap",
                            "CONFIDENCE": 0.90,
                        }
                    )

                matched_count += len(group)
                matched_names.add(name_key)

        # Remove matched from unmatched pool
        self.unmatched = self.unmatched[~self.unmatched["NAME_KEY"].isin(matched_names)]

        self.gate_stats["gate3"] = {
            "matched": matched_count,
            "unique_players": len(matched_names),
            "remaining": len(self.unmatched),
        }

        print(f"✓ Matched: {matched_count:,} records ({len(matched_names):,} unique players)")
        print(f"  Remaining: {len(self.unmatched):,} records")

    def _gate4_statistical_signature(self):
        """Gate 4: Statistical signature matching (PPG, shooting %, consistency)."""
        print("\n" + "-" * 80)
        print("GATE 4: STATISTICAL_SIGNATURE (Confidence: 0.85)")
        print("-" * 80)

        matched_count = 0
        matched_names = set()

        for name_key, group in self.unmatched.groupby("NAME_KEY"):
            # Require at least 10 games per player for statistical reliability
            if (group["GAMES_PLAYED"] < 10).any():
                continue

            # Check if statistical profiles are similar across leagues
            ppg_values = group["PPG"].values
            fg_values = group["FG_PCT"].values

            # Calculate coefficient of variation for PPG
            if len(ppg_values) > 1:
                ppg_cv = np.std(ppg_values) / (
                    np.mean(ppg_values) + 0.01
                )  # Add small value to avoid div by 0

                # If PPG is very consistent across leagues (CV < 0.4), likely same player
                if ppg_cv < 0.4:
                    # Additional check: FG% should be similar (within 10%)
                    fg_diff = np.max(fg_values) - np.min(fg_values)

                    if fg_diff < 0.10 or pd.isna(fg_diff):
                        # Statistical profiles match - likely same player
                        player_uid = generate_player_uid(name_key, suffix="statSig")

                        for _, row in group.iterrows():
                            self.matches.append(
                                {
                                    "PLAYER_UID": player_uid,
                                    "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                                    "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                                    "NAME_KEY": row["NAME_KEY"],
                                    "MATCH_RULE": "statistical_signature",
                                    "CONFIDENCE": 0.85,
                                }
                            )

                        matched_count += len(group)
                        matched_names.add(name_key)

        # Remove matched from unmatched pool
        self.unmatched = self.unmatched[~self.unmatched["NAME_KEY"].isin(matched_names)]

        self.gate_stats["gate4"] = {
            "matched": matched_count,
            "unique_players": len(matched_names),
            "remaining": len(self.unmatched),
        }

        print(f"✓ Matched: {matched_count:,} records ({len(matched_names):,} unique players)")
        print(f"  Remaining: {len(self.unmatched):,} records")

    def _gate5_team_history_validation(self):
        """Gate 5: Team history and career progression validation."""
        print("\n" + "-" * 80)
        print("GATE 5: TEAM_HISTORY_VALIDATION (Confidence: 0.80)")
        print("-" * 80)

        # This gate is complex and requires domain knowledge about league tiers
        # For now, we'll implement a simple version:
        # If same name appears in a logical career path (e.g., NCAA -> G-League)
        # and teams make sense, match them

        matched_count = 0
        matched_names = set()

        # Define logical career paths
        career_paths = [
            ["NCAA_MBB", "G_LEAGUE"],
            ["NCAA_MBB", "ABA"],
            ["OTE", "G_LEAGUE"],
            ["OTE", "NBL"],
            ["CEBL", "G_LEAGUE"],
        ]

        for name_key, group in self.unmatched.groupby("NAME_KEY"):
            # Check if leagues match any logical career path
            leagues = sorted(group["SOURCE_LEAGUE"].unique())

            is_logical_path = False
            for path in career_paths:
                if set(leagues).issubset(set(path)):
                    is_logical_path = True
                    break

            if is_logical_path and len(leagues) >= 2:
                # Check chronological order
                group_sorted = group.sort_values("FIRST_GAME")

                # Verify dates are in correct order
                dates_in_order = True
                for i in range(len(group_sorted) - 1):
                    if group_sorted.iloc[i]["LAST_GAME"] > group_sorted.iloc[i + 1]["FIRST_GAME"]:
                        dates_in_order = False
                        break

                if dates_in_order:
                    # Logical career progression - match
                    player_uid = generate_player_uid(name_key, suffix="careerPath")

                    for _, row in group.iterrows():
                        self.matches.append(
                            {
                                "PLAYER_UID": player_uid,
                                "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                                "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                                "NAME_KEY": row["NAME_KEY"],
                                "MATCH_RULE": "team_history_validation",
                                "CONFIDENCE": 0.80,
                            }
                        )

                    matched_count += len(group)
                    matched_names.add(name_key)

        # Remove matched from unmatched pool
        self.unmatched = self.unmatched[~self.unmatched["NAME_KEY"].isin(matched_names)]

        self.gate_stats["gate5"] = {
            "matched": matched_count,
            "unique_players": len(matched_names),
            "remaining": len(self.unmatched),
        }

        print(f"✓ Matched: {matched_count:,} records ({len(matched_names):,} unique players)")
        print(f"  Remaining: {len(self.unmatched):,} records")

    def _mark_unresolved(self):
        """Mark remaining records as unresolved."""
        print("\n" + "-" * 80)
        print("MARKING UNRESOLVED")
        print("-" * 80)

        for _, row in self.unmatched.iterrows():
            # Create unique UID per unresolved record
            player_uid = f"UNRESOLVED_{row['SOURCE_LEAGUE']}_{row['SOURCE_PLAYER_ID']}"

            self.matches.append(
                {
                    "PLAYER_UID": player_uid,
                    "SOURCE_LEAGUE": row["SOURCE_LEAGUE"],
                    "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                    "NAME_KEY": row.get("NAME_KEY", ""),
                    "MATCH_RULE": "unresolved",
                    "CONFIDENCE": 0.0,
                }
            )

        print(f"  Unresolved: {len(self.unmatched):,} records")

    def _print_summary(self, edges_df: pd.DataFrame):
        """Print matching summary."""
        print("\n" + "=" * 80)
        print("MATCHING SUMMARY")
        print("=" * 80)

        print(f"\nTotal edges: {len(edges_df):,}")

        print("\nConfidence distribution:")
        conf_dist = edges_df["CONFIDENCE"].value_counts().sort_index(ascending=False)
        for conf, count in conf_dist.items():
            pct = count / len(edges_df) * 100
            print(f"  {conf:.2f}: {count:,} ({pct:.1f}%)")

        print("\nMatch rule distribution:")
        rule_dist = edges_df["MATCH_RULE"].value_counts()
        for rule, count in rule_dist.items():
            pct = count / len(edges_df) * 100
            print(f"  {rule}: {count:,} ({pct:.1f}%)")

        print("\nGate-by-gate summary:")
        for gate, stats in self.gate_stats.items():
            print(f"  {gate}: {stats['matched']:,} matched, {stats['remaining']:,} remaining")

        # Unique players
        unique_players = edges_df[edges_df["MATCH_RULE"] != "unresolved"]["PLAYER_UID"].nunique()
        print(f"\nUnique players (resolved): {unique_players:,}")

        # Unresolved count
        unresolved = len(edges_df[edges_df["MATCH_RULE"] == "unresolved"])
        unresolved_pct = unresolved / len(edges_df) * 100
        print(f"Unresolved records: {unresolved:,} ({unresolved_pct:.1f}%)")


def load_tier1_canonical_data(leagues: list[str] = None) -> pd.DataFrame:
    """Load canonical data from Tier 1 leagues.

    Args:
        leagues: List of league codes. If None, loads all Tier 1 leagues.

    Returns:
        Combined DataFrame with all player-game records
    """
    if leagues is None:
        leagues = ["NCAA_MBB", "GLEAGUE", "ABA_ADRIATIC", "NBL", "CEBL", "OTE", "EUROLEAGUE", "ACB"]

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


def deduplicate_to_player_map(edges_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create 1:1 player_map from many-to-many edges.

    Deduplication Strategy (in priority order):
    1. Highest CONFIDENCE (1.0 > 0.99 > 0.95 > ...)
    2. Match rule priority: exact_unique_name > birth_date_match > birth_year_height > ...
    3. Lexicographic PLAYER_UID (stable tiebreaker)

    Args:
        edges_df: player_edges with potential duplicate join keys

    Returns:
        player_map with unique (SOURCE_LEAGUE, SOURCE_PLAYER_ID)

    Raises:
        ValueError: If duplicates remain after deduplication
    """

    print("\n" + "=" * 80)
    print("DEDUPLICATING TO PLAYER MAP")
    print("=" * 80)

    print(f"Input edges: {len(edges_df):,} rows")

    unique_join_keys = edges_df.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]).ngroups
    print(f"Unique (SOURCE_LEAGUE, SOURCE_PLAYER_ID): {unique_join_keys:,}")

    duplicates = len(edges_df) - unique_join_keys
    if duplicates > 0:
        print(f"⚠ Found {duplicates} duplicate join keys ({duplicates/len(edges_df)*100:.1f}%)")
    else:
        print("✓ No duplicate join keys found")

    # Define match rule priority
    match_rule_priority = {
        "exact_unique_name": 1,
        "birth_date_match": 2,
        "birth_year_height_match": 3,
        "height_timeline_match": 4,
        "same_league_unique_id": 5,
        "temporal_no_overlap": 6,
        "statistical_profile_match": 7,
        "unresolved": 999,
    }

    edges_df = edges_df.assign(
        MATCH_RULE_PRIORITY=edges_df["MATCH_RULE"].map(match_rule_priority).fillna(999)
    )

    # Sort by priority
    # Highest confidence first, lowest priority number first, lexicographic UID
    sorted_edges = edges_df.sort_values(
        by=["SOURCE_LEAGUE", "SOURCE_PLAYER_ID", "CONFIDENCE", "MATCH_RULE_PRIORITY", "PLAYER_UID"],
        ascending=[True, True, False, True, True],
    )

    # Keep first occurrence (highest priority)
    player_map = sorted_edges.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]).first().reset_index()

    print(f"\nAfter deduplication: {len(player_map):,} rows")

    unique_after = player_map.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"]).ngroups
    print(f"Unique (SOURCE_LEAGUE, SOURCE_PLAYER_ID): {unique_after:,}")

    # CRITICAL VALIDATION: Must be 1:1
    if len(player_map) != unique_after:
        raise ValueError("CRITICAL: Deduplication failed! Duplicates remain in player_map")

    # Report collisions (same source mapped to different UIDs)
    collisions = (
        sorted_edges.groupby(["SOURCE_LEAGUE", "SOURCE_PLAYER_ID"])
        .agg(
            {
                "PLAYER_UID": "nunique",
                "MATCH_RULE": lambda x: list(x),
                "CONFIDENCE": lambda x: list(x),
            }
        )
        .reset_index()
    )

    collisions = collisions[collisions["PLAYER_UID"] > 1]

    if len(collisions) > 0:
        print(f"\n⚠ {len(collisions)} source players mapped to multiple UIDs")
        print("  Resolved via priority rules. See collision report for details.")

        # Export collision report
        collision_report_path = Path("data/_reports/player_map_collisions.json")
        collision_report_path.parent.mkdir(parents=True, exist_ok=True)
        collisions.to_json(collision_report_path, orient="records", indent=2)
        print(f"  Saved collision report to {collision_report_path}")

    # Drop priority column
    player_map = player_map.drop(columns=["MATCH_RULE_PRIORITY"])

    print(f"\n✓ Created player_map with {len(player_map):,} entries (1:1 guaranteed)")

    return player_map


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Multi-gate progressive player matching system")
    parser.add_argument(
        "--leagues",
        nargs="+",
        help="Specific leagues to process (default: all Tier 1)",
        default=None,
    )
    parser.add_argument(
        "--output",
        default="data/identity/player_edges_multigate.parquet",
        help="Output file path (default: data/identity/player_edges_multigate.parquet)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("MULTI-GATE PLAYER MATCHING SYSTEM")
    print("=" * 80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")

    # Load canonical data
    canonical_df = load_tier1_canonical_data(leagues=args.leagues)

    # Run multi-gate matcher
    matcher = MultiGatePlayerMatcher(canonical_df)
    edges_df = matcher.run_all_gates()

    # Save player edges (many-to-many graph)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    edges_df.to_parquet(output_path, index=False)
    print(f"\n✓ Saved {len(edges_df):,} edges to {output_path}")

    # Also save CSV for review
    csv_path = output_path.with_suffix(".csv")
    edges_df.to_csv(csv_path, index=False)
    print(f"✓ Saved CSV to {csv_path}")

    # Create player_map (1:1 join key) via deduplication
    player_map = deduplicate_to_player_map(edges_df)

    # Save player_map
    player_map_path = Path("data/identity/player_map.parquet")
    player_map_path.parent.mkdir(parents=True, exist_ok=True)
    player_map.to_parquet(player_map_path, index=False)
    print(f"\n✓ Saved {len(player_map):,} player mappings (1:1) to {player_map_path}")

    # Save unresolved for manual review
    unresolved = edges_df[edges_df["MATCH_RULE"] == "unresolved"]
    if len(unresolved) > 0:
        unresolved_path = Path("data/_reports/multigate_unresolved.csv")
        unresolved_path.parent.mkdir(parents=True, exist_ok=True)
        unresolved.to_csv(unresolved_path, index=False)
        print(f"✓ Saved {len(unresolved):,} unresolved cases to {unresolved_path}")

    # Save gate statistics
    stats_path = Path("data/_reports/multigate_statistics.json")
    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_edges": len(edges_df),
        "unique_players": edges_df[edges_df["MATCH_RULE"] != "unresolved"]["PLAYER_UID"].nunique(),
        "confidence_distribution": edges_df["CONFIDENCE"].value_counts().to_dict(),
        "match_rule_distribution": edges_df["MATCH_RULE"].value_counts().to_dict(),
        "gate_stats": matcher.gate_stats,
        "unresolved_count": len(unresolved),
        "unresolved_pct": len(unresolved) / len(edges_df) * 100,
    }

    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"✓ Saved statistics to {stats_path}")

    print("\n" + "=" * 80)
    print("MATCHING COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
