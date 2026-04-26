#!/usr/bin/env python
# ruff: noqa: E402
"""Backfill League Data for Data Coverage Gaps

Fetches missing historical data for leagues with validation player gaps:
- G-League 2020-2024 (Ignite era: Jalen Green, Kuminga, Scoot Henderson)
- ABA 2012-2022 (Jokic at Mega Basket 2012-2015, Jovic 2020-2022)
- LNB 2021-2023 (Wembanyama at Metropolitans 92)

Usage:
    python scripts/backfill_league_data.py --league G_LEAGUE --seasons 2020-21,2021-22,2022-23,2023-24
    python scripts/backfill_league_data.py --league ABA --seasons 2012-13,2013-14,2014-15
    python scripts/backfill_league_data.py --all
"""

import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pandas as pd

DATA_DIR = PROJECT_ROOT / "data"
CANONICAL_DIR = DATA_DIR / "canonical"
CANONICAL_DIR.mkdir(parents=True, exist_ok=True)

# Validation players to search for
VALIDATION_PLAYERS = {
    "G_LEAGUE": {
        "jalen_green": {"seasons": ["2020-21"], "team": "Ignite"},
        "jonathan_kuminga": {"seasons": ["2020-21"], "team": "Ignite"},
        "scoot_henderson": {"seasons": ["2022-23"], "team": "Ignite"},
    },
    "ABA": {
        "nikola_jokic": {"seasons": ["2012-13", "2013-14", "2014-15"], "team": "Mega"},
        "nikola_jovic": {"seasons": ["2020-21", "2021-22"], "team": "Mega"},
    },
    "LNB_PROA": {
        "victor_wembanyama": {"seasons": ["2021-22", "2022-23"], "team": "Metropolitans"},
    },
}


def normalize_name(name: str) -> str:
    """Normalize player name to key."""
    import re
    import unicodedata

    if not name or pd.isna(name):
        return ""
    normalized = unicodedata.normalize("NFD", str(name))
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized


def fetch_gleague_season(season: str) -> pd.DataFrame:
    """Fetch G-League data for a season using the API."""
    try:
        from cbb_data.fetchers.gleague import (
            fetch_gleague_box_score,
            fetch_gleague_schedule,
        )
    except ImportError as e:
        print(f"  Import error: {e}")
        return pd.DataFrame()

    print(f"  Fetching G-League schedule for {season}...")
    try:
        schedule = fetch_gleague_schedule(season=season)
        if schedule.empty:
            print(f"  No schedule found for {season}")
            return pd.DataFrame()
        print(f"  Found {len(schedule)} games")
    except Exception as e:
        print(f"  Error fetching schedule: {e}")
        return pd.DataFrame()

    # Fetch box scores for each game
    all_box_scores = []
    game_ids = schedule["GAME_ID"].unique() if "GAME_ID" in schedule.columns else []

    print(f"  Fetching box scores for {len(game_ids)} games...")
    for i, game_id in enumerate(game_ids):
        if i % 50 == 0:
            print(f"    Progress: {i}/{len(game_ids)}")
        try:
            box = fetch_gleague_box_score(str(game_id))
            if not box.empty:
                box["SEASON"] = season
                all_box_scores.append(box)
        except Exception as e:
            print(f"    Error fetching game {game_id}: {e}")
            continue

    if not all_box_scores:
        return pd.DataFrame()

    df = pd.concat(all_box_scores, ignore_index=True)

    # Add NAME_KEY
    if "PLAYER_NAME" in df.columns:
        df["NAME_KEY"] = df["PLAYER_NAME"].apply(normalize_name)
    elif "PLAYER_NAME_RAW" in df.columns:
        df["NAME_KEY"] = df["PLAYER_NAME_RAW"].apply(normalize_name)

    # Standardize columns
    df["LEAGUE"] = "G_LEAGUE"
    if "PLAYER_ID" in df.columns and "SOURCE_PLAYER_ID" not in df.columns:
        df["SOURCE_PLAYER_ID"] = df["PLAYER_ID"].astype(str)

    return df


def fetch_aba_season(season: str) -> pd.DataFrame:
    """Fetch ABA data for a season using FIBA HTML scraping."""
    try:
        from cbb_data.fetchers.aba import fetch_player_game
    except ImportError as e:
        print(f"  Import error: {e}")
        return pd.DataFrame()

    print(f"  Fetching ABA player_game for {season}...")
    try:
        df = fetch_player_game(season=season, force_refresh=True)
        if df.empty:
            print(f"  No data found for {season}")
            return pd.DataFrame()
        print(f"  Found {len(df)} player-game rows")
    except Exception as e:
        print(f"  Error fetching ABA data: {e}")
        return pd.DataFrame()

    # Add NAME_KEY
    if "PLAYER_NAME" in df.columns:
        df["NAME_KEY"] = df["PLAYER_NAME"].apply(normalize_name)
    elif "PLAYER_NAME_RAW" in df.columns:
        df["NAME_KEY"] = df["PLAYER_NAME_RAW"].apply(normalize_name)

    # Standardize
    df["LEAGUE"] = "ABA"

    return df


def search_validation_players(df: pd.DataFrame, league: str) -> dict:
    """Search for validation players in the data."""
    results = {}

    if league not in VALIDATION_PLAYERS:
        return results

    if "NAME_KEY" not in df.columns:
        return results

    for player_key, info in VALIDATION_PLAYERS[league].items():
        # Search by partial name match
        search_term = player_key.split("_")[1]  # e.g., "jokic" from "nikola_jokic"
        matches = df[df["NAME_KEY"].str.contains(search_term, case=False, na=False)]

        if len(matches) > 0:
            seasons_found = (
                matches["SEASON"].unique().tolist() if "SEASON" in matches.columns else []
            )
            games = len(matches)
            results[player_key] = {
                "found": True,
                "games": games,
                "seasons": seasons_found,
                "expected_seasons": info["seasons"],
            }
        else:
            results[player_key] = {
                "found": False,
                "expected_seasons": info["seasons"],
            }

    return results


def backfill_league(league: str, seasons: list[str]) -> pd.DataFrame:
    """Backfill data for a specific league and seasons."""
    print(f"\n{'='*60}")
    print(f"BACKFILLING {league}")
    print(f"Seasons: {seasons}")
    print(f"{'='*60}")

    all_data = []

    for season in seasons:
        print(f"\nProcessing {league} {season}...")

        if league == "G_LEAGUE":
            df = fetch_gleague_season(season)
        elif league == "ABA":
            df = fetch_aba_season(season)
        else:
            print(f"  Unknown league: {league}")
            continue

        if not df.empty:
            all_data.append(df)

            # Search for validation players
            validation = search_validation_players(df, league)
            if validation:
                print("  Validation player search:")
                for player, info in validation.items():
                    if info["found"]:
                        print(f"    [OK] {player}: {info['games']} games in {info['seasons']}")
                    else:
                        print(f"    [X] {player}: NOT FOUND (expected: {info['expected_seasons']})")

    if not all_data:
        print(f"\nNo data collected for {league}")
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal {league} rows collected: {len(combined):,}")

    return combined


def save_to_canonical(df: pd.DataFrame, league: str):
    """Save backfilled data to canonical format."""
    if df.empty:
        return

    # Save combined file
    output_file = CANONICAL_DIR / f"{league}_backfill.parquet"
    df.to_parquet(output_file, index=False)
    print(f"Saved: {output_file}")

    # Also append to existing combined file if it exists
    combined_file = CANONICAL_DIR / "all_leagues_combined.parquet"
    if combined_file.exists():
        existing = pd.read_parquet(combined_file)
        # Remove existing rows for this league to avoid duplicates
        existing = existing[existing["LEAGUE"] != league]
        updated = pd.concat([existing, df], ignore_index=True)
        updated.to_parquet(combined_file, index=False)
        print(f"Updated: {combined_file} (now {len(updated):,} rows)")


def main():
    parser = argparse.ArgumentParser(description="Backfill league data for coverage gaps")
    parser.add_argument("--league", help="League to backfill (G_LEAGUE, ABA, LNB_PROA)")
    parser.add_argument("--seasons", help="Comma-separated seasons (e.g., 2020-21,2021-22)")
    parser.add_argument("--all", action="store_true", help="Backfill all leagues with gaps")
    parser.add_argument("--save", action="store_true", help="Save to canonical format")
    args = parser.parse_args()

    if args.all:
        # Backfill all leagues with known gaps
        backfill_tasks = [
            ("G_LEAGUE", ["2020-21", "2021-22", "2022-23", "2023-24"]),
            ("ABA", ["2012-13", "2013-14", "2014-15", "2020-21", "2021-22"]),
        ]

        for league, seasons in backfill_tasks:
            df = backfill_league(league, seasons)
            if args.save and not df.empty:
                save_to_canonical(df, league)

    elif args.league and args.seasons:
        seasons = [s.strip() for s in args.seasons.split(",")]
        df = backfill_league(args.league, seasons)
        if args.save and not df.empty:
            save_to_canonical(df, args.league)

    else:
        print("Usage:")
        print(
            "  python scripts/backfill_league_data.py --league G_LEAGUE --seasons 2020-21,2021-22"
        )
        print("  python scripts/backfill_league_data.py --all --save")


if __name__ == "__main__":
    main()
