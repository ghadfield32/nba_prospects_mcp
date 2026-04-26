#!/usr/bin/env python
"""Player Identity Crosswalk Builder v2 - Deduplicated

Builds deterministic player identity crosswalk by first extracting unique players
per (LEAGUE, SOURCE_PLAYER_ID), then matching across leagues.

Key fix: Processes ~20K unique players, not ~526K game rows.

Usage:
    python scripts/build_player_xwalk_v2.py
"""

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

DATA_DIR = Path("data")
CANONICAL_DIR = DATA_DIR / "canonical"
REPORTS_DIR = DATA_DIR / "_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
IDENTITY_DIR = DATA_DIR / "identity"
IDENTITY_DIR.mkdir(parents=True, exist_ok=True)

# Known pathway players with birth years for seeding
# NOTE: NAME_KEY format varies by league:
#   - EUROLEAGUE: "last_first" (e.g., doncic_luka)
#   - NCAA: abbreviated (e.g., p_banchero)
#   - ABA: abbreviated (e.g., jokic_n)
#   - ACB: abbreviated (e.g., j_rubio)
#   - NBL/G_LEAGUE/LNB: full name (e.g., lamelo_ball)
# Each entry has "aliases" for alternative NAME_KEY formats
KNOWN_PATHWAYS = {
    # NBL players (full name format)
    "alexandre_sarr": {"birth_year": 2005, "expected_leagues": ["NBL"], "aliases": ["alex_sarr"]},
    "lamelo_ball": {"birth_year": 2001, "expected_leagues": ["NBL"], "aliases": []},
    "josh_giddey": {"birth_year": 2002, "expected_leagues": ["NBL"], "aliases": []},
    # EUROLEAGUE players (last_first format)
    "doncic_luka": {
        "birth_year": 1999,
        "expected_leagues": ["EUROLEAGUE"],
        "aliases": ["luka_doncic"],
    },
    "vesely_jan": {
        "birth_year": 1990,
        "expected_leagues": ["EUROLEAGUE"],
        "aliases": ["jan_vesely"],
    },
    # NCAA players (abbreviated format)
    "p_banchero": {
        "birth_year": 2002,
        "expected_leagues": ["NCAA_MBB"],
        "aliases": ["paolo_banchero"],
    },
    "c_holmgren": {
        "birth_year": 2002,
        "expected_leagues": ["NCAA_MBB"],
        "aliases": ["chet_holmgren"],
    },
    "z_edey": {"birth_year": 2002, "expected_leagues": ["NCAA_MBB"], "aliases": ["zach_edey"]},
    # G-League players (full name format)
    "jalen_green": {"birth_year": 2002, "expected_leagues": ["G_LEAGUE"], "aliases": []},
    "scoot_henderson": {"birth_year": 2004, "expected_leagues": ["G_LEAGUE"], "aliases": []},
    "jonathan_kuminga": {"birth_year": 2002, "expected_leagues": ["G_LEAGUE"], "aliases": []},
    # ABA players (abbreviated format: last_initial)
    "jokic_n": {"birth_year": 1995, "expected_leagues": ["ABA"], "aliases": ["nikola_jokic"]},
    "jovic_n": {"birth_year": 2003, "expected_leagues": ["ABA"], "aliases": ["nikola_jovic"]},
    # ACB players (abbreviated format: initial_last)
    "j_rubio": {"birth_year": 1990, "expected_leagues": ["ACB"], "aliases": ["ricky_rubio"]},
    # LNB players (full name format)
    "victor_wembanyama": {"birth_year": 2004, "expected_leagues": ["LNB_PROA"], "aliases": []},
    # LKL players (for future)
    "deividas_sirvydis": {"birth_year": 2000, "expected_leagues": ["LKL"], "aliases": []},
}


def normalize_name(name: str) -> str:
    """Normalize player name to key."""
    if not name or pd.isna(name):
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized


def generate_player_uid(name_key: str, birth_year: int | None = None) -> str:
    """Generate deterministic PLAYER_UID.

    Format: P_{name_key}_{birth_year}_{hash8}
    """
    if birth_year:
        base = f"{name_key}_{birth_year}"
    else:
        base = name_key
    hash8 = hashlib.sha256(base.encode()).hexdigest()[:8]
    return f"P_{name_key[:20]}_{birth_year or 'UNK'}_{hash8}"


def extract_unique_players(df: pd.DataFrame) -> pd.DataFrame:
    """Extract unique players from game-level data.

    Groups by (LEAGUE, SOURCE_PLAYER_ID) and aggregates metadata.
    Falls back to (LEAGUE, NAME_KEY) when SOURCE_PLAYER_ID is null-like.
    """
    print(f"  Input rows: {len(df):,}")

    # Determine name column
    name_col = None
    for col in ["PLAYER_NAME_RAW", "NAME_KEY", "PLAYER_NAME"]:
        if col in df.columns:
            name_col = col
            break

    if name_col is None:
        print("  WARNING: No name column found")
        return pd.DataFrame()

    # Fix null-like SOURCE_PLAYER_IDs (string "None", empty string, etc.)
    df = df.copy()
    null_like = df["SOURCE_PLAYER_ID"].isin(["None", "none", "", "null", "NULL"])
    null_like |= df["SOURCE_PLAYER_ID"].isna()

    # For null-like IDs, use NAME_KEY as the identifier
    if "NAME_KEY" in df.columns:
        df.loc[null_like, "SOURCE_PLAYER_ID"] = df.loc[null_like, "NAME_KEY"]
        fixed_count = null_like.sum()
        if fixed_count > 0:
            print(f"  Fixed {fixed_count:,} null-like SOURCE_PLAYER_IDs")

    # Group by unique player identifiers
    group_cols = ["LEAGUE", "SOURCE_PLAYER_ID"]
    available_cols = [c for c in group_cols if c in df.columns]

    if len(available_cols) < 2:
        print(f"  WARNING: Missing columns. Have: {list(df.columns)}")
        return pd.DataFrame()

    # Aggregate: first name, count games, list seasons
    agg_dict = {
        name_col: "first",
    }

    # Also aggregate NAME_KEY if it exists (to preserve when PLAYER_NAME is None)
    if "NAME_KEY" in df.columns and name_col != "NAME_KEY":
        agg_dict["NAME_KEY"] = "first"

    # Add season list if available
    if "SEASON" in df.columns:
        agg_dict["SEASON"] = lambda x: sorted(x.unique().tolist())

    # Add game count
    if "GAME_ID" in df.columns:
        agg_dict["GAME_ID"] = "nunique"

    # Add team if available
    for team_col in ["TEAM_KEY", "TEAM_NAME_RAW", "TEAM"]:
        if team_col in df.columns:
            agg_dict[team_col] = "first"
            break

    players = df.groupby(available_cols, as_index=False).agg(agg_dict)

    # Rename columns
    rename_map = {name_col: "PLAYER_NAME"}
    if "GAME_ID" in players.columns:
        rename_map["GAME_ID"] = "GAME_COUNT"
    if "SEASON" in players.columns:
        rename_map["SEASON"] = "SEASONS"

    players = players.rename(columns=rename_map)

    # Add NAME_KEY - use existing if available and valid, otherwise normalize PLAYER_NAME
    if "NAME_KEY" not in players.columns:
        players["NAME_KEY"] = players["PLAYER_NAME"].apply(normalize_name)
    else:
        # Fill in NAME_KEY from PLAYER_NAME where NAME_KEY is missing/empty
        missing_key = players["NAME_KEY"].isna() | (players["NAME_KEY"] == "")
        players.loc[missing_key, "NAME_KEY"] = players.loc[missing_key, "PLAYER_NAME"].apply(
            normalize_name
        )

    print(f"  Unique players: {len(players):,}")
    return players


def find_multi_league_players(players_df: pd.DataFrame) -> pd.DataFrame:
    """Find players appearing in multiple leagues."""
    # Group by NAME_KEY
    multi = (
        players_df.groupby("NAME_KEY")
        .agg(
            {
                "LEAGUE": lambda x: list(x.unique()),
                "SOURCE_PLAYER_ID": list,
                "PLAYER_NAME": "first",
            }
        )
        .reset_index()
    )

    # Filter to multi-league only
    multi["LEAGUE_COUNT"] = multi["LEAGUE"].apply(len)
    multi = multi[multi["LEAGUE_COUNT"] > 1].copy()

    return multi


def build_known_pathway_lookup() -> dict:
    """Build reverse lookup from all name_keys and aliases to pathway info."""
    lookup = {}
    for name_key, info in KNOWN_PATHWAYS.items():
        lookup[name_key] = info
        for alias in info.get("aliases", []):
            lookup[alias] = info
    return lookup


KNOWN_PATHWAY_LOOKUP = build_known_pathway_lookup()


def build_crosswalk(players_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Build player crosswalk and edge table.

    Returns:
        - xwalk_df: Main crosswalk table
        - edges_df: Edge table for deterministic joins
        - unresolved: List of unresolved cases
    """
    xwalk_entries = []
    edge_entries = []
    unresolved = []

    # Group by NAME_KEY
    name_groups = players_df.groupby("NAME_KEY")

    for name_key, group in name_groups:
        leagues = group["LEAGUE"].unique().tolist()

        # Check if this is a known pathway player (check primary key and aliases)
        known_birth_year = KNOWN_PATHWAY_LOOKUP.get(name_key, {}).get("birth_year")

        if len(group) == 1:
            # Single occurrence - straightforward
            row = group.iloc[0]
            player_uid = generate_player_uid(name_key, known_birth_year)

            xwalk_entries.append(
                {
                    "PLAYER_UID": player_uid,
                    "NAME_KEY": name_key,
                    "DISPLAY_NAME": row["PLAYER_NAME"],
                    "BIRTH_YEAR": known_birth_year,
                    "LEAGUES": [row["LEAGUE"]],
                    "MATCH_RULE": "single_occurrence",
                    "CONFIDENCE": 1.0,
                }
            )

            edge_entries.append(
                {
                    "PLAYER_UID": player_uid,
                    "SOURCE_LEAGUE": row["LEAGUE"],
                    "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                    "SEASON_RANGE": str(row.get("SEASONS", "")),
                    "MATCH_RULE": "single_occurrence",
                    "CONFIDENCE": 1.0,
                }
            )

        elif len(leagues) == 1:
            # Multiple records in same league - could be same player different seasons
            # or different players with same name
            league = leagues[0]

            if len(group) <= 3:
                # Likely same player across seasons
                player_uid = generate_player_uid(name_key, known_birth_year)

                xwalk_entries.append(
                    {
                        "PLAYER_UID": player_uid,
                        "NAME_KEY": name_key,
                        "DISPLAY_NAME": group.iloc[0]["PLAYER_NAME"],
                        "BIRTH_YEAR": known_birth_year,
                        "LEAGUES": [league],
                        "MATCH_RULE": "same_league_merge",
                        "CONFIDENCE": 0.85,
                    }
                )

                for _, row in group.iterrows():
                    edge_entries.append(
                        {
                            "PLAYER_UID": player_uid,
                            "SOURCE_LEAGUE": row["LEAGUE"],
                            "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                            "SEASON_RANGE": str(row.get("SEASONS", "")),
                            "MATCH_RULE": "same_league_merge",
                            "CONFIDENCE": 0.85,
                        }
                    )
            else:
                # Too many records - ambiguous, needs review
                unresolved.append(
                    {
                        "name_key": name_key,
                        "record_count": len(group),
                        "leagues": leagues,
                        "reason": "multiple_same_league_ids",
                    }
                )

        else:
            # Multiple leagues - potential cross-league career
            player_uid = generate_player_uid(name_key, known_birth_year)

            # Check if this is a known pathway (check primary key and aliases)
            expected_leagues = set(
                KNOWN_PATHWAY_LOOKUP.get(name_key, {}).get("expected_leagues", [])
            )
            actual_leagues = set(leagues)

            if expected_leagues and expected_leagues.issubset(actual_leagues):
                match_rule = "known_pathway"
                confidence = 0.98
            else:
                match_rule = "cross_league_name_match"
                confidence = 0.75

            xwalk_entries.append(
                {
                    "PLAYER_UID": player_uid,
                    "NAME_KEY": name_key,
                    "DISPLAY_NAME": group.iloc[0]["PLAYER_NAME"],
                    "BIRTH_YEAR": known_birth_year,
                    "LEAGUES": leagues,
                    "MATCH_RULE": match_rule,
                    "CONFIDENCE": confidence,
                }
            )

            for _, row in group.iterrows():
                edge_entries.append(
                    {
                        "PLAYER_UID": player_uid,
                        "SOURCE_LEAGUE": row["LEAGUE"],
                        "SOURCE_PLAYER_ID": row["SOURCE_PLAYER_ID"],
                        "SEASON_RANGE": str(row.get("SEASONS", "")),
                        "MATCH_RULE": match_rule,
                        "CONFIDENCE": confidence,
                    }
                )

    xwalk_df = pd.DataFrame(xwalk_entries) if xwalk_entries else pd.DataFrame()
    edges_df = pd.DataFrame(edge_entries) if edge_entries else pd.DataFrame()

    return xwalk_df, edges_df, unresolved


def validate_known_pathways(xwalk_df: pd.DataFrame, edges_df: pd.DataFrame) -> list[dict]:
    """Validate that known pathway players are correctly identified."""
    results = []

    for name_key, pathway_info in KNOWN_PATHWAYS.items():
        expected_leagues = set(pathway_info["expected_leagues"])
        birth_year = pathway_info["birth_year"]
        aliases = pathway_info.get("aliases", [])

        # Find in crosswalk - check primary name_key and aliases
        all_keys = [name_key] + aliases
        matches = xwalk_df[xwalk_df["NAME_KEY"].isin(all_keys)]

        if len(matches) == 0:
            results.append(
                {
                    "name_key": name_key,
                    "birth_year": birth_year,
                    "expected_leagues": list(expected_leagues),
                    "status": "NOT_FOUND",
                    "actual_leagues": [],
                    "searched_keys": all_keys,
                }
            )
        elif len(matches) >= 1:
            # Aggregate all leagues from all matches (including aliases)
            actual_leagues = set()
            for _, row in matches.iterrows():
                leagues = row["LEAGUES"]
                if isinstance(leagues, str):
                    actual_leagues.update(leagues.split(","))
                elif isinstance(leagues, list):
                    actual_leagues.update(leagues)

            found_expected = expected_leagues.intersection(actual_leagues)

            if expected_leagues.issubset(actual_leagues):
                status = "PASS"
            elif found_expected:
                status = "PARTIAL"
            else:
                status = "MISMATCH"

            results.append(
                {
                    "name_key": name_key,
                    "birth_year": birth_year,
                    "expected_leagues": list(expected_leagues),
                    "actual_leagues": list(actual_leagues),
                    "status": status,
                    "player_uid": matches.iloc[0]["PLAYER_UID"],
                    "matched_keys": matches["NAME_KEY"].tolist(),
                }
            )

    return results


def main():
    print("=" * 70)
    print("PLAYER CROSSWALK BUILDER v2 (Deduplicated)")
    print("=" * 70)
    print()

    # Load canonical data
    combined_file = CANONICAL_DIR / "all_leagues_combined.parquet"

    if not combined_file.exists():
        print(f"Combined file not found: {combined_file}")
        print("Run transform_canonical_cache.py first")
        return

    print(f"Loading: {combined_file}")
    df = pd.read_parquet(combined_file)
    print(f"  Total game rows: {len(df):,}")
    print(f"  Leagues: {df['LEAGUE'].unique().tolist()}")
    print()

    # Step 1: Extract unique players
    print("Step 1: Extracting unique players per (LEAGUE, SOURCE_PLAYER_ID)...")
    players_df = extract_unique_players(df)

    if players_df.empty:
        print("No players extracted")
        return

    # Summary by league
    print("\n  Players by league:")
    for league in players_df["LEAGUE"].unique():
        count = len(players_df[players_df["LEAGUE"] == league])
        print(f"    {league}: {count:,}")
    print()

    # Step 2: Find multi-league players
    print("Step 2: Finding multi-league players...")
    multi_league = find_multi_league_players(players_df)
    print(f"  Multi-league players: {len(multi_league):,}")

    if len(multi_league) > 0:
        print("  Sample multi-league players:")
        for _, row in multi_league.head(10).iterrows():
            print(f"    {row['NAME_KEY']}: {row['LEAGUE']}")
    print()

    # Step 3: Build crosswalk
    print("Step 3: Building crosswalk and edge table...")
    xwalk_df, edges_df, unresolved = build_crosswalk(players_df)

    print(f"  Crosswalk entries: {len(xwalk_df):,}")
    print(f"  Edge entries: {len(edges_df):,}")
    print(f"  Unresolved: {len(unresolved):,}")
    print()

    # Step 4: Validate known pathways
    print("Step 4: Validating known pathway players...")
    pathway_results = validate_known_pathways(xwalk_df, edges_df)

    pass_count = sum(1 for r in pathway_results if r["status"] == "PASS")
    partial_count = sum(1 for r in pathway_results if r["status"] == "PARTIAL")
    not_found = sum(1 for r in pathway_results if r["status"] == "NOT_FOUND")

    print(f"  PASS: {pass_count}/{len(pathway_results)}")
    print(f"  PARTIAL: {partial_count}/{len(pathway_results)}")
    print(f"  NOT_FOUND: {not_found}/{len(pathway_results)}")
    print()

    print("  Pathway validation details:")
    for result in pathway_results:
        status_icon = {"PASS": "[OK]", "PARTIAL": "[~]", "NOT_FOUND": "[X]", "MISMATCH": "[!]"}.get(
            result["status"], "[?]"
        )
        print(f"    {status_icon} {result['name_key']}: {result['status']}")
        if result["status"] in ["PASS", "PARTIAL"]:
            print(f"        Expected: {result['expected_leagues']}")
            print(f"        Actual: {result['actual_leagues']}")
    print()

    # Step 5: Save outputs
    print("Step 5: Saving outputs...")

    # Save crosswalk
    if not xwalk_df.empty:
        # Convert lists to strings for parquet
        xwalk_df["LEAGUES"] = xwalk_df["LEAGUES"].apply(
            lambda x: ",".join(x) if isinstance(x, list) else x
        )
        xwalk_df.to_parquet(DATA_DIR / "player_xwalk.parquet", index=False)
        xwalk_df.to_csv(DATA_DIR / "player_xwalk.csv", index=False)
        print(f"  Saved: data/player_xwalk.parquet ({len(xwalk_df):,} entries)")

    # Save edge table
    if not edges_df.empty:
        edges_df.to_parquet(IDENTITY_DIR / "player_edges.parquet", index=False)
        print(f"  Saved: data/identity/player_edges.parquet ({len(edges_df):,} edges)")

    # Save unresolved
    if unresolved:
        with open(REPORTS_DIR / "xwalk_unresolved_v2.json", "w") as f:
            json.dump(unresolved, f, indent=2, default=str)
        print(f"  Saved: data/_reports/xwalk_unresolved_v2.json ({len(unresolved)} cases)")

    # Save pathway validation
    with open(REPORTS_DIR / "pathway_validation.json", "w") as f:
        json.dump(pathway_results, f, indent=2, default=str)
    print("  Saved: data/_reports/pathway_validation.json")

    # Summary
    print()
    print("=" * 70)
    print("CROSSWALK SUMMARY")
    print("=" * 70)
    print(f"Unique players processed: {len(players_df):,}")
    print(f"Crosswalk entries: {len(xwalk_df):,}")
    print(f"Edge table entries: {len(edges_df):,}")
    print(f"Multi-league players: {len(multi_league):,}")
    print(f"Unresolved: {len(unresolved):,}")
    print(f"Known pathway validation: {pass_count}/{len(pathway_results)} PASS")
    print()

    # Match rule breakdown
    if not xwalk_df.empty and "MATCH_RULE" in xwalk_df.columns:
        print("Match rule breakdown:")
        for rule, count in xwalk_df["MATCH_RULE"].value_counts().items():
            print(f"  {rule}: {count:,}")


if __name__ == "__main__":
    main()
