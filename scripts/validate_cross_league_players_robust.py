#!/usr/bin/env python3
# ruff: noqa: E402
"""Validate Cross-League Player Tracking (ROBUST VERSION)

Tests that we can track players across multiple leagues using robust search
that handles different name formats:
- NCAA: "Z. Williamson" (initial + last)
- EuroLeague/ACB: "DONCIC, LUKA" (LAST, FIRST)
- Standard: "First Last"

This version searches using:
1. NAME_KEY_CANONICAL / NAME_KEY_INITIAL (if backfill complete)
2. PLAYER_NAME_CANONICAL (if backfill complete)
3. PLAYER_NAME_RAW with accent/format handling (fallback)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.identity.name_normalization import clean_spaces, strip_accents


def _token_variants(full_name: str) -> list[str]:
    """Generate search tokens for robust matching.

    Examples:
        "Zion Williamson" → ["Zion Williamson", "Z. Williamson", "Z Williamson",
                             "Williamson, Zion", "Williamson"]
        "Luka Dončić" → ["Luka Doncic", "L. Doncic", "L Doncic",
                        "Doncic, Luka", "Doncic"]
    """
    s = clean_spaces(strip_accents(full_name))
    parts = s.split()

    if len(parts) < 2:
        return [s]

    first, last = parts[0], parts[-1]
    first_initial = first[0].upper()

    variants = {
        s,  # Full name
        f"{first} {last}",  # Explicit first last
        f"{first_initial}. {last}",  # Initial with period
        f"{first_initial} {last}",  # Initial without period
        f"{last}, {first}",  # Comma format
        last,  # Last name only (anchor)
    }

    return sorted(v for v in variants if v)


def _contains_all_tokens(series: pd.Series, tokens: list[str]) -> pd.Series:
    """Check if series contains all tokens (case-insensitive, NA-safe).

    Uses literal matching (regex=False) for safety.
    """
    mask = pd.Series(True, index=series.index)
    for token in tokens:
        # Escape special regex characters for literal matching
        mask &= series.str.contains(re.escape(token), case=False, na=False, regex=True)
    return mask


def find_player_rows(gold: pd.DataFrame, query_name: str) -> pd.DataFrame:
    """Find player using robust multi-strategy search.

    Search strategy (in order of preference):
    1. NAME_KEY_CANONICAL / NAME_KEY_INITIAL columns (best, if backfill done)
    2. PLAYER_NAME_CANONICAL column (good, if backfill done)
    3. PLAYER_NAME_RAW with variants (fallback, handles all formats)

    Args:
        gold: Unified dataset dataframe
        query_name: Player name to search for (e.g., "Zion Williamson")

    Returns:
        Filtered dataframe with matching rows

    Examples:
        >>> find_player_rows(gold, "Zion Williamson")
        # Finds: "Z. Williamson" (NCAA), "Zion Williamson" (G-League)

        >>> find_player_rows(gold, "Luka Dončić")
        # Finds: "L. Doncic" (ACB), "DONCIC, LUKA" (EuroLeague)
    """
    cols = set(gold.columns)
    tokens = _token_variants(query_name)

    # Extract last name (anchor for all searches)
    last_name = tokens[0].split()[-1]
    last_name_key = re.sub(r"[^a-z0-9]+", "_", last_name.lower()).strip("_")

    # Strategy 1: Name key columns (most reliable if present)
    if "NAME_KEY_CANONICAL" in cols or "NAME_KEY_INITIAL" in cols:
        mask = pd.Series(False, index=gold.index)

        if "NAME_KEY_CANONICAL" in cols:
            mask |= (
                gold["NAME_KEY_CANONICAL"]
                .astype(str)
                .str.contains(last_name_key, case=False, na=False, regex=False)
            )

        if "NAME_KEY_INITIAL" in cols:
            mask |= (
                gold["NAME_KEY_INITIAL"]
                .astype(str)
                .str.contains(last_name_key, case=False, na=False, regex=False)
            )

        candidates = gold[mask]

        if len(candidates) > 0:
            # Refine: try to match first name or initial if provided
            first = tokens[0].split()[0] if len(tokens[0].split()) >= 2 else None
            if first:
                first_initial = first[0].lower()

                # Accept either full first name OR initial match
                refine_mask = pd.Series(False, index=candidates.index)

                if "NAME_KEY_CANONICAL" in cols:
                    refine_mask |= (
                        candidates["NAME_KEY_CANONICAL"]
                        .astype(str)
                        .str.startswith(f"{first.lower()}_", na=False)
                    )
                    refine_mask |= (
                        candidates["NAME_KEY_CANONICAL"]
                        .astype(str)
                        .str.startswith(f"{first_initial}_", na=False)
                    )

                if "NAME_KEY_INITIAL" in cols:
                    refine_mask |= (
                        candidates["NAME_KEY_INITIAL"]
                        .astype(str)
                        .str.startswith(f"{first_initial}_", na=False)
                    )

                refined = candidates[refine_mask]
                if len(refined) > 0:
                    return refined

            return candidates

    # Strategy 2: PLAYER_NAME_CANONICAL column (good if backfill done)
    if "PLAYER_NAME_CANONICAL" in cols:
        # Anchor on last name
        mask = (
            gold["PLAYER_NAME_CANONICAL"]
            .astype(str)
            .str.contains(re.escape(last_name), case=False, na=False, regex=True)
        )
        candidates = gold[mask]

        if len(candidates) > 0:
            # Try to refine with full name matches
            full_name_tokens = [t for t in tokens if " " in t][:1]
            if full_name_tokens:
                refine_mask = _contains_all_tokens(
                    candidates["PLAYER_NAME_CANONICAL"].astype(str), [full_name_tokens[0]]
                )
                refined = candidates[refine_mask]
                if len(refined) > 0:
                    return refined

            return candidates

    # Strategy 3: PLAYER_NAME_RAW fallback (handles all legacy formats)
    raw_col = (
        "PLAYER_NAME_RAW"
        if "PLAYER_NAME_RAW" in cols
        else ("PLAYER_NAME" if "PLAYER_NAME" in cols else None)
    )

    if raw_col is None:
        return gold.iloc[0:0]  # Empty result

    # Normalize raw names for comparison
    raw_normalized = gold[raw_col].astype(str).apply(lambda s: clean_spaces(strip_accents(s)))

    # Anchor on last name
    mask = raw_normalized.str.contains(re.escape(last_name), case=False, na=False, regex=True)
    candidates = gold[mask]

    if len(candidates) == 0:
        return candidates

    # Refine: match first name OR initial (handles "Z. Williamson" matching "Zion")
    first = tokens[0].split()[0] if len(tokens[0].split()) >= 2 else None
    if first:
        first_initial = first[0]
        raw_cand_normalized = (
            candidates[raw_col].astype(str).apply(lambda s: clean_spaces(strip_accents(s)))
        )

        # Accept either full first name OR initial with period/space
        refine_mask = (
            raw_cand_normalized.str.contains(re.escape(first), case=False, na=False, regex=True)
            | raw_cand_normalized.str.contains(
                re.escape(f"{first_initial}."), case=False, na=False, regex=True
            )
            | raw_cand_normalized.str.contains(
                re.escape(f"{first_initial} "), case=False, na=False, regex=True
            )
        )

        refined = candidates[refine_mask]
        if len(refined) > 0:
            return refined

    return candidates


# --- Main validation logic ---


def main():
    """Run cross-league player validation."""
    # Load unified dataset
    gold_path = Path("data/gold/player_career_unified_tier1.parquet")
    if not gold_path.exists():
        print(f"ERROR: Unified dataset not found at {gold_path}")
        return 1

    gold = pd.read_parquet(gold_path)

    # Check if backfill has been run
    has_normalized = "NAME_KEY_CANONICAL" in gold.columns
    print("=" * 80)
    print("CROSS-LEAGUE PLAYER VALIDATION (ROBUST)")
    print("=" * 80)
    print(f"Unified dataset: {gold_path}")
    print(f"Total players: {gold['PLAYER_UID'].nunique():,}")
    print(f"Total records: {len(gold):,}")
    print(f"Leagues: {sorted(gold['SOURCE_LEAGUE'].unique())}")
    print(
        f"Normalization status: {'✓ Backfill complete' if has_normalized else '⚠ Not backfilled (using fallback search)'}"
    )
    print()

    # Players to validate
    players = [
        {"name": "Karter Knox", "expected_leagues": ["OTE"], "notes": "OTE → NBA draft 2024"},
        {
            "name": "Zion Williamson",
            "expected_leagues": ["NCAA_MBB"],
            "notes": "Duke 2018-19 → NBA (1st pick)",
        },
        {
            "name": "Alex Caruso",
            "expected_leagues": ["NCAA_MBB", "G_LEAGUE"],
            "notes": "NCAA → G-League → NBA",
        },
        {
            "name": "Sasha Vezenkov",
            "expected_leagues": ["EUROLEAGUE", "ACB"],
            "notes": "EuroLeague ↔ NBA",
        },
        {
            "name": "Luka Dončić",
            "expected_leagues": ["ACB", "EUROLEAGUE"],
            "notes": "ACB + EuroLeague → NBA",
        },
        {
            "name": "Amen Thompson",
            "expected_leagues": ["OTE"],
            "notes": "OTE 2021-23 → NBA (4th pick)",
        },
        {
            "name": "LaMelo Ball",
            "expected_leagues": ["NBL"],
            "notes": "NBL 2019-20 → NBA (3rd pick)",
        },
        {"name": "Tazé Moore", "expected_leagues": ["CEBL"], "notes": "CEBL → NBA two-way"},
        {
            "name": "David Thompson",
            "expected_leagues": ["ABA", "NCAA_MBB"],
            "notes": "ABA → NBA (historical)",
        },
    ]

    results = []

    for player_info in players:
        name = player_info["name"]
        expected_leagues = player_info["expected_leagues"]
        notes = player_info["notes"]

        print(f"\n{'=' * 80}")
        print(f"SEARCHING: {name}")
        print(f"Expected leagues: {', '.join(expected_leagues)}")
        print(f"Notes: {notes}")
        print("-" * 80)

        # Use robust search
        player_data = find_player_rows(gold, name)

        if len(player_data) == 0:
            print("❌ NOT FOUND in unified dataset")
            print(f"   Search variants tried: {_token_variants(name)}")

            results.append(
                {"player": name, "status": "NOT_FOUND", "games": 0, "leagues": [], "uids": 0}
            )
            continue

        # Found player - analyze
        total_games = len(player_data)
        unique_uids = player_data["PLAYER_UID"].nunique()
        leagues_found = sorted(player_data["SOURCE_LEAGUE"].unique())

        print(f"✅ FOUND: {total_games} games across {len(leagues_found)} league(s)")
        print(f"   Unique PLAYER_UIDs: {unique_uids}")
        print(f"   Leagues: {', '.join(leagues_found)}")

        # Show breakdown by league and season
        print("\n   Career Breakdown:")
        summary = (
            player_data.groupby(["SOURCE_LEAGUE", "SEASON"])
            .agg({"PLAYER_NAME_RAW": "first", "PLAYER_UID": "first", "GAME_ID": "count"})
            .rename(columns={"GAME_ID": "games"})
            .reset_index()
        )

        for _, row in summary.iterrows():
            uid_short = (
                row["PLAYER_UID"][:25] + "..." if len(row["PLAYER_UID"]) > 25 else row["PLAYER_UID"]
            )
            print(
                f"     {row['SOURCE_LEAGUE']:12} {row['SEASON']:8} - {row['games']:3} games (UID: {uid_short})"
            )

        # Check if all expected leagues are present
        missing_leagues = set(expected_leagues) - set(leagues_found)
        if missing_leagues:
            print(f"\n   ⚠️  WARNING: Missing expected leagues: {', '.join(missing_leagues)}")

        # Check if unified under single UID
        if unique_uids == 1:
            print("\n   🎉 SUCCESS: Unified under single PLAYER_UID")
        else:
            print(f"\n   ⚠️  WARNING: Split across {unique_uids} UIDs")

        results.append(
            {
                "player": name,
                "status": "FOUND",
                "games": total_games,
                "leagues": leagues_found,
                "uids": unique_uids,
                "missing_leagues": list(missing_leagues) if missing_leagues else None,
            }
        )

    # Summary report
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)

    found_count = sum(1 for r in results if r["status"] == "FOUND")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

    print(f"\nPlayers found: {found_count}/{len(players)}")
    print(f"Players missing: {not_found_count}/{len(players)}")

    if not_found_count > 0:
        print("\nMissing players:")
        for r in results:
            if r["status"] == "NOT_FOUND":
                print(f"  - {r['player']}")

    print("\nPlayers by league coverage:")
    league_coverage = {}
    for r in results:
        if r["status"] == "FOUND":
            for league in r["leagues"]:
                if league not in league_coverage:
                    league_coverage[league] = []
                league_coverage[league].append(r["player"])

    for league in sorted(league_coverage.keys()):
        players_list = league_coverage[league]
        print(f"  {league:12} - {len(players_list)} players: {', '.join(players_list)}")

    # Multi-UID warnings
    multi_uid_players = [r for r in results if r["status"] == "FOUND" and r["uids"] > 1]
    if multi_uid_players:
        print("\n⚠️  Players with multiple UIDs (need investigation):")
        for r in multi_uid_players:
            print(f"  - {r['player']:20} - {r['uids']} UIDs across {len(r['leagues'])} leagues")

    print("\n" + "=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
