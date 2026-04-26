#!/usr/bin/env python
"""ABA League Game Index Builder

Extracts real game IDs from aba-liga.com calendar pages and builds
proper game indexes for historical data fetching.

Validation players:
- Nikola Jokic (Mega Basket): 2012-13, 2013-14, 2014-15
- Nikola Jovic (Mega Basket): 2020-21, 2021-22
"""

import re
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configuration
ABA_BASE_URL = "https://www.aba-liga.com"
RATE_LIMIT_DELAY = 1.0  # seconds between requests

# Output directories
DATA_DIR = Path(__file__).parent.parent / "data"
GAME_INDEX_DIR = DATA_DIR / "game_indexes"
GAME_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Season mapping: season_code -> season_name
SEASONS = {
    "12": "2012-13",
    "13": "2013-14",
    "14": "2014-15",
    "15": "2015-16",
    "16": "2016-17",
    "17": "2017-18",
    "18": "2018-19",
    "19": "2019-20",
    "20": "2020-21",
    "21": "2021-22",
    "22": "2022-23",
    "23": "2023-24",
    "24": "2024-25",
}

# Team abbreviation mappings
TEAM_ABBREVS = {
    "partizan": "PAR",
    "mega": "MEG",
    "cibona": "CIB",
    "zadar": "ZAD",
    "cedevita": "CED",
    "crvena zvezda": "CZV",
    "zvezda": "CZV",
    "buducnost": "BUD",
    "igokea": "IGO",
    "split": "SPL",
    "mornar": "MOR",
    "fmp": "FMP",
    "krka": "KRK",
    "dynamic": "DYN",
    "borac": "BOR",
    "metalac": "MET",
    "rogaska": "ROG",
    "student": "STU",
    "vojvodina": "VOJ",
    "olimpija": "OLI",
    "mzt": "MZT",
    "szolnoki": "SZO",
    "primorska": "PRI",
    "kk mega": "MEG",
}


def fetch_calendar_html(season_code: str) -> str:
    """Fetch calendar HTML for a season."""
    url = f"{ABA_BASE_URL}/calendar/{season_code}/1/"
    print(f"  Fetching {url}...")
    time.sleep(RATE_LIMIT_DELAY)

    response = requests.get(
        url,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    response.raise_for_status()
    return response.text


def parse_calendar_games(html: str, season_code: str, season_name: str) -> list[dict]:
    """Parse games from calendar HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Find all game links
    pattern = re.compile(r"/match/(\d+)/" + season_code + r"/1/")
    game_links = soup.find_all("a", href=pattern)

    games_data = {}
    for link in game_links:
        href = link.get("href")
        match = pattern.search(href)
        if not match:
            continue

        game_id = int(match.group(1))
        text = link.get_text(strip=True)

        if game_id not in games_data:
            games_data[game_id] = {
                "GAME_ID": game_id,
                "SEASON": season_name,
                "LEAGUE": "ABA",
                "texts": [],
                "href": href,
            }

        if text:
            games_data[game_id]["texts"].append(text)

    # Process each game to extract teams and scores
    games = []
    for game_id, data in games_data.items():
        texts = data["texts"]

        # Extract team abbreviations (format: "ABC:XYZ")
        abbrev_match = None
        for t in texts:
            if re.match(r"^[A-Z]{2,4}:[A-Z]{2,4}$", t):
                abbrev_match = t
                break

        # Extract score (format: "NN : NN")
        score_match = None
        for t in texts:
            if re.match(r"^\d{1,3}\s*:\s*\d{1,3}$", t):
                score_match = t
                break

        # Extract team names
        home_team, away_team = None, None
        home_score, away_score = None, None

        if abbrev_match:
            parts = abbrev_match.split(":")
            home_team = parts[0].strip()
            away_team = parts[1].strip()

        if score_match:
            parts = score_match.replace(" ", "").split(":")
            try:
                home_score = int(parts[0])
                away_score = int(parts[1])
            except ValueError:
                pass

        games.append(
            {
                "GAME_ID": game_id,
                "GAME_DATE": None,  # Will need to fetch from game page
                "HOME_TEAM": home_team,
                "AWAY_TEAM": away_team,
                "HOME_SCORE": home_score,
                "AWAY_SCORE": away_score,
                "SEASON": season_name,
                "LEAGUE": "ABA",
                "STATUS": "COMPLETE" if score_match else "SCHEDULED",
            }
        )

    return games


def fetch_game_date(game_id: int, season_code: str) -> str | None:
    """Fetch game date from individual game page."""
    url = f"{ABA_BASE_URL}/match/{game_id}/{season_code}/1/Overview/"
    time.sleep(RATE_LIMIT_DELAY / 2)  # Faster for date fetching

    try:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        response.raise_for_status()

        # Look for date in page
        soup = BeautifulSoup(response.text, "html.parser")

        # Try to find date elements
        date_patterns = [
            r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})",
            r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})",
        ]

        text = soup.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                # Try to parse and normalize
                for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"]:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime("%Y-%m-%d")
                    except ValueError:
                        continue

        return None
    except Exception:
        return None


def build_season_index(season_code: str, fetch_dates: bool = False) -> pd.DataFrame:
    """Build game index for a season."""
    season_name = SEASONS.get(season_code, f"20{season_code}")
    print(f"\nProcessing ABA {season_name}...")

    html = fetch_calendar_html(season_code)
    games = parse_calendar_games(html, season_code, season_name)

    print(f"  Found {len(games)} games")

    if fetch_dates:
        print("  Fetching game dates (this may take a while)...")
        for i, game in enumerate(games):
            if i > 0 and i % 20 == 0:
                print(f"    Progress: {i}/{len(games)}")
            game["GAME_DATE"] = fetch_game_date(game["GAME_ID"], season_code)

    df = pd.DataFrame(games)

    # Show Mega games for validation
    if "HOME_TEAM" in df.columns:
        mega_games = df[(df["HOME_TEAM"] == "MEG") | (df["AWAY_TEAM"] == "MEG")]
        if len(mega_games) > 0:
            print(f"  Mega Basket games: {len(mega_games)}")

    return df


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build ABA game indexes")
    parser.add_argument("--seasons", nargs="+", help="Season codes to process (e.g., 12 13 14)")
    parser.add_argument("--jokic", action="store_true", help="Process Jokic seasons (12, 13, 14)")
    parser.add_argument("--jovic", action="store_true", help="Process Jovic seasons (20, 21)")
    parser.add_argument("--all", action="store_true", help="Process all available seasons")
    parser.add_argument("--dates", action="store_true", help="Fetch game dates (slower)")
    parser.add_argument("--save", action="store_true", help="Save to CSV files")
    args = parser.parse_args()

    # Determine which seasons to process
    if args.all:
        season_codes = list(SEASONS.keys())
    elif args.jokic:
        season_codes = ["12", "13", "14"]
    elif args.jovic:
        season_codes = ["20", "21"]
    elif args.seasons:
        season_codes = args.seasons
    else:
        # Default: Jokic + Jovic seasons
        season_codes = ["12", "13", "14", "20", "21"]

    print("=" * 60)
    print("ABA LEAGUE GAME INDEX BUILDER")
    print(f"Seasons: {[SEASONS.get(s, s) for s in season_codes]}")
    print(f"Fetch dates: {args.dates}")
    print("=" * 60)

    all_games = []

    for season_code in season_codes:
        df = build_season_index(season_code, fetch_dates=args.dates)

        if not df.empty:
            all_games.append(df)

            if args.save:
                season_name = SEASONS.get(season_code, f"20{season_code}")
                filename = f"ABA_{season_name.replace('-', '_')}.csv"
                output_path = GAME_INDEX_DIR / filename
                df.to_csv(output_path, index=False)
                print(f"  Saved: {output_path}")

    if all_games:
        combined = pd.concat(all_games, ignore_index=True)
        print(f"\nTotal games across all seasons: {len(combined)}")

        # Summary by season
        print("\nGames by season:")
        for season in combined["SEASON"].unique():
            count = len(combined[combined["SEASON"] == season])
            mega = len(
                combined[
                    (combined["SEASON"] == season)
                    & ((combined["HOME_TEAM"] == "MEG") | (combined["AWAY_TEAM"] == "MEG"))
                ]
            )
            print(f"  {season}: {count} games ({mega} Mega)")


if __name__ == "__main__":
    main()
