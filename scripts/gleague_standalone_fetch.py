#!/usr/bin/env python
"""Standalone G-League Fetcher (bypasses package circular import)

Fetches G-League box score data directly from stats.gleague.nba.com.
"""

import re
import sys
import time
import unicodedata
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests

# API Configuration
GLEAGUE_BASE_URL = "https://stats.gleague.nba.com/stats"
GLEAGUE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://stats.gleague.nba.com/",
    "Origin": "https://stats.gleague.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

# Rate limiting
RATE_LIMIT_DELAY = 0.3  # seconds between requests

# Validation players
VALIDATION_PLAYERS = {
    "jalen_green": {"seasons": ["2020-21"], "team": "Ignite"},
    "jonathan_kuminga": {"seasons": ["2020-21"], "team": "Ignite"},
    "scoot_henderson": {"seasons": ["2022-23"], "team": "Ignite"},
}

# Output directory
DATA_DIR = Path(__file__).parent.parent / "data"
CANONICAL_DIR = DATA_DIR / "canonical"
CANONICAL_DIR.mkdir(parents=True, exist_ok=True)


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


def make_api_request(endpoint: str, params: dict) -> dict:
    """Make request to G-League API."""
    time.sleep(RATE_LIMIT_DELAY)
    url = f"{GLEAGUE_BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, headers=GLEAGUE_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  API request failed: {e}")
        return {}


def parse_resultset(data: dict, result_set_name: str) -> pd.DataFrame:
    """Parse API ResultSet into DataFrame."""
    if "resultSets" not in data:
        return pd.DataFrame()

    result_set = None
    for rs in data["resultSets"]:
        if rs.get("name", "").lower() == result_set_name.lower():
            result_set = rs
            break

    if result_set is None and data["resultSets"]:
        result_set = data["resultSets"][0]

    if result_set is None:
        return pd.DataFrame()

    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])

    if not headers or not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=headers)


def fetch_gleague_schedule(season: str) -> pd.DataFrame:
    """Fetch G-League game schedule."""
    print(f"  Fetching G-League schedule for {season}...")

    params = {
        "LeagueID": "20",  # G-League ID
        "Season": season,
        "SeasonType": "Regular Season",
    }

    data = make_api_request("leaguegamefinder", params)
    df = parse_resultset(data, "LeagueGameFinderResults")

    if df.empty:
        print(f"  No games found for {season}")
        return df

    # Get unique game IDs
    if "GAME_ID" in df.columns:
        game_ids = df["GAME_ID"].unique()
        print(f"  Found {len(game_ids)} games")
        return df

    return df


def fetch_gleague_box_score(game_id: str) -> pd.DataFrame:
    """Fetch G-League box score for a single game."""
    params = {
        "GameID": game_id,
        "StartPeriod": 0,
        "EndPeriod": 10,
        "StartRange": 0,
        "EndRange": 28800,
        "RangeType": 0,
    }

    data = make_api_request("boxscoretraditionalv2", params)
    df = parse_resultset(data, "PlayerStats")

    if df.empty:
        return df

    df["GAME_ID"] = game_id
    df["LEAGUE"] = "G_LEAGUE"

    # Convert STARTER to 0/1
    if "START_POSITION" in df.columns:
        df["STARTER"] = (df["START_POSITION"].notna() & (df["START_POSITION"] != "")).astype(int)

    return df


def fetch_gleague_season_box_scores(season: str) -> pd.DataFrame:
    """Fetch all box scores for a G-League season."""
    schedule = fetch_gleague_schedule(season)

    if schedule.empty or "GAME_ID" not in schedule.columns:
        return pd.DataFrame()

    game_ids = schedule["GAME_ID"].unique()
    print(f"  Fetching box scores for {len(game_ids)} games...")

    all_box_scores = []
    for i, game_id in enumerate(game_ids):
        if i > 0 and i % 50 == 0:
            print(f"    Progress: {i}/{len(game_ids)}")

        try:
            box = fetch_gleague_box_score(str(game_id))
            if not box.empty:
                box["SEASON"] = season

                # Get game date from schedule
                game_info = (
                    schedule[schedule["GAME_ID"] == game_id].iloc[0]
                    if len(schedule[schedule["GAME_ID"] == game_id]) > 0
                    else None
                )
                if game_info is not None and "GAME_DATE" in schedule.columns:
                    box["GAME_DATE"] = game_info["GAME_DATE"]

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

    # Standardize player ID column
    if "PLAYER_ID" in df.columns:
        df["SOURCE_PLAYER_ID"] = df["PLAYER_ID"].astype(str)

    return df


def search_validation_players(df: pd.DataFrame) -> dict:
    """Search for validation players in the data."""
    results = {}

    if "NAME_KEY" not in df.columns:
        return results

    for player_key, info in VALIDATION_PLAYERS.items():
        search_term = player_key.split("_")[1]  # e.g., "green" from "jalen_green"
        matches = df[df["NAME_KEY"].str.contains(search_term, case=False, na=False)]

        if len(matches) > 0:
            seasons_found = (
                matches["SEASON"].unique().tolist() if "SEASON" in matches.columns else []
            )
            teams = (
                matches["TEAM_ABBREVIATION"].unique().tolist()
                if "TEAM_ABBREVIATION" in matches.columns
                else []
            )
            results[player_key] = {
                "found": True,
                "games": len(matches),
                "seasons": seasons_found,
                "teams": teams,
                "expected_seasons": info["seasons"],
            }
        else:
            results[player_key] = {
                "found": False,
                "expected_seasons": info["seasons"],
            }

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch G-League data")
    parser.add_argument(
        "--seasons",
        nargs="+",
        default=["2020-21", "2021-22", "2022-23", "2023-24"],
        help="Seasons to fetch",
    )
    parser.add_argument("--save", action="store_true", help="Save to parquet")
    args = parser.parse_args()

    print("=" * 60)
    print("G-LEAGUE STANDALONE FETCHER")
    print(f"Seasons: {args.seasons}")
    print("=" * 60)

    all_data = []

    for season in args.seasons:
        print(f"\nProcessing {season}...")
        df = fetch_gleague_season_box_scores(season)

        if not df.empty:
            print(f"  Collected {len(df):,} player-game rows")
            all_data.append(df)

            # Search for validation players
            validation = search_validation_players(df)
            if validation:
                print("  Validation player search:")
                for player, info in validation.items():
                    if info["found"]:
                        print(
                            f"    [OK] {player}: {info['games']} games, teams: {info.get('teams', [])}"
                        )
                    else:
                        print(f"    [X] {player}: NOT FOUND")

    if not all_data:
        print("\nNo data collected")
        return

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal rows collected: {len(combined):,}")

    # Final validation search
    print("\n" + "=" * 60)
    print("FINAL VALIDATION PLAYER SEARCH")
    print("=" * 60)
    validation = search_validation_players(combined)
    for player, info in validation.items():
        if info["found"]:
            print(f"[OK] {player}: {info['games']} games in {info['seasons']}")
        else:
            print(f"[X] {player}: NOT FOUND (expected: {info['expected_seasons']})")

    if args.save:
        output_file = CANONICAL_DIR / "G_LEAGUE_backfill.parquet"
        combined.to_parquet(output_file, index=False)
        print(f"\nSaved: {output_file}")


if __name__ == "__main__":
    main()
