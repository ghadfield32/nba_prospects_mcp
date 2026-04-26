#!/usr/bin/env python
"""LKL FIBA ID Mapper

The LKL game index contains internal website IDs that don't work with the
FIBA LiveStats API. This script extracts the real FIBA game IDs from LKL
game detail pages.

Usage:
    python scripts/lkl_fiba_id_mapper.py --season 2023-24
    python scripts/lkl_fiba_id_mapper.py --build-mapping
    python scripts/lkl_fiba_id_mapper.py --test-sample 10
"""

import argparse
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configuration
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,lt;q=0.8",
}
REQUEST_DELAY = 1.5

# Data paths
GAME_INDEX_DIR = PROJECT_ROOT / "data" / "game_indexes"
MAPPING_OUTPUT = PROJECT_ROOT / "data" / "lkl_fiba_mapping.csv"

# LKL URLs
LKL_URLS = [
    "https://lfrygtas.lkl.lt/en/game/{game_id}",
    "https://lkl.lt/en/game/{game_id}",
    "https://lkl.lt/rungtynes/{game_id}",
]


def find_fiba_id_on_page(html: str) -> str:
    """Extract FIBA LiveStats ID from page content."""
    # Pattern 1: Direct FIBA LiveStats URL
    fiba_patterns = [
        r"fibalivestats\.com/[^/]+/(\d+)",
        r'data-game-id=["\'](\d+)["\']',
        r'fibaGameId["\']?\s*[:=]\s*["\']?(\d+)',
        r"/livestats/(\d+)",
    ]

    for pattern in fiba_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            return matches[0]

    # Pattern 2: Look for data attributes in HTML
    soup = BeautifulSoup(html, "html.parser")

    # Check various data attributes
    for attr in ["data-game-id", "data-fiba-id", "data-livestats-id"]:
        elem = soup.find(attrs={attr: True})
        if elem:
            fiba_id = elem.get(attr)
            if fiba_id and str(fiba_id).isdigit():
                return str(fiba_id)

    # Check script tags for game ID
    for script in soup.find_all("script"):
        text = script.get_text()
        for pattern in fiba_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]

    return None


def fetch_fiba_id(lkl_game_id: str) -> str:
    """Fetch FIBA ID for an LKL game by checking the game page."""
    for url_template in LKL_URLS:
        url = url_template.format(game_id=lkl_game_id)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                fiba_id = find_fiba_id_on_page(resp.text)
                if fiba_id:
                    return fiba_id
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            continue

    return None


def load_lkl_game_index() -> pd.DataFrame:
    """Load the LKL game index file."""
    # Find LKL index files
    lkl_files = list(GAME_INDEX_DIR.glob("LKL_*.csv"))

    if not lkl_files:
        print(f"No LKL index files found in {GAME_INDEX_DIR}")
        return pd.DataFrame()

    all_games = []
    for f in sorted(lkl_files):
        try:
            df = pd.read_csv(f)
            df["INDEX_FILE"] = f.name
            all_games.append(df)
            print(f"  Loaded {f.name}: {len(df)} games")
        except Exception as e:
            print(f"  Error loading {f}: {e}")

    if all_games:
        combined = pd.concat(all_games, ignore_index=True)
        return combined
    return pd.DataFrame()


def build_mapping_table(
    game_index: pd.DataFrame, max_games: int = None, season_filter: str = None
) -> pd.DataFrame:
    """Build LKL ID → FIBA ID mapping table."""
    if game_index.empty:
        return pd.DataFrame()

    # Filter by season if specified
    if season_filter and "SEASON" in game_index.columns:
        game_index = game_index[game_index["SEASON"] == season_filter]
        print(f"Filtered to {len(game_index)} games for season {season_filter}")

    # Limit if specified
    if max_games:
        game_index = game_index.head(max_games)

    mappings = []
    success = 0
    failed = 0

    print(f"\nBuilding mapping for {len(game_index)} games...")

    for idx, row in game_index.iterrows():
        lkl_id = str(row.get("GAME_ID", ""))
        if not lkl_id:
            continue

        fiba_id = fetch_fiba_id(lkl_id)

        mapping = {
            "LKL_GAME_ID": lkl_id,
            "FIBA_GAME_ID": fiba_id,
            "SEASON": row.get("SEASON"),
            "GAME_DATE": row.get("GAME_DATE"),
            "HOME_TEAM": row.get("HOME_TEAM"),
            "AWAY_TEAM": row.get("AWAY_TEAM"),
        }
        mappings.append(mapping)

        if fiba_id:
            success += 1
            print(f"  [{idx+1}] LKL {lkl_id} → FIBA {fiba_id}")
        else:
            failed += 1
            print(f"  [{idx+1}] LKL {lkl_id} → NOT FOUND")

        time.sleep(REQUEST_DELAY)

    print(f"\n=== Mapping complete: {success} success, {failed} failed ===")
    return pd.DataFrame(mappings)


def save_mapping(df: pd.DataFrame, output_path: Path):
    """Save mapping table to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved mapping to {output_path}")


def test_fiba_fetch(fiba_id: str) -> bool:
    """Test if we can fetch data from FIBA with the mapped ID."""
    url = f"https://www.fibalivestats.com/data/{fiba_id}/data.json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "tm" in data or "pbp" in data:
                return True
    except Exception:
        pass
    return False


def main():
    parser = argparse.ArgumentParser(description="Build LKL FIBA ID mapping table")
    parser.add_argument("--build-mapping", action="store_true", help="Build full mapping table")
    parser.add_argument("--season", type=str, help="Filter to specific season (e.g., 2023-24)")
    parser.add_argument("--test-sample", type=int, help="Test with N sample games")
    parser.add_argument("--output", type=str, default=str(MAPPING_OUTPUT), help="Output CSV path")

    args = parser.parse_args()

    # Load game index
    print("Loading LKL game index...")
    game_index = load_lkl_game_index()

    if game_index.empty:
        print("No game index data available")
        return

    print(f"Total LKL games in index: {len(game_index)}")

    if "SEASON" in game_index.columns:
        print("Seasons:", sorted(game_index["SEASON"].unique()))

    # Build mapping
    if args.test_sample:
        mapping_df = build_mapping_table(
            game_index, max_games=args.test_sample, season_filter=args.season
        )
    elif args.build_mapping or args.season:
        mapping_df = build_mapping_table(game_index, season_filter=args.season)
    else:
        # Default: test with 5 games
        print("\nTesting with 5 sample games (use --build-mapping for full)")
        mapping_df = build_mapping_table(game_index, max_games=5)

    if not mapping_df.empty:
        # Test a successful mapping
        successful = mapping_df[mapping_df["FIBA_GAME_ID"].notna()]
        if len(successful) > 0:
            test_id = successful.iloc[0]["FIBA_GAME_ID"]
            print(f"\nTesting FIBA fetch with ID {test_id}...")
            if test_fiba_fetch(test_id):
                print("  SUCCESS - FIBA data accessible!")
            else:
                print("  FAILED - Could not fetch FIBA data")

        # Save mapping
        save_mapping(mapping_df, Path(args.output))


if __name__ == "__main__":
    main()
