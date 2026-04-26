#!/usr/bin/env python
"""Probe FIBA LiveStats JSON endpoints to find working patterns.

The HTML scraper is failing because BCL website changed.
This script tests alternative JSON endpoints.
"""

import sys
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Game indexes location
UNIFIED_BASE = (
    Path(__file__).parent.parent.parent / "unified_basketball_mcp" / "servers" / "nba_prospects_mcp"
)
GAME_INDEX_DIR = UNIFIED_BASE / "data" / "game_indexes"

# FIBA LiveStats base URLs
FIBA_BASES = [
    "https://fibalivestats.dcd.shared.geniussports.com",
    "https://livebcl.dcd.shared.geniussports.com",
    "https://live.basketball-champions-league.com",
]


def get_sample_game_ids(league: str, limit: int = 3) -> list:
    """Get sample game IDs from a league's index."""
    import pandas as pd

    game_ids = []
    for f in GAME_INDEX_DIR.glob(f"{league}*.csv"):
        try:
            df = pd.read_csv(f)
            if "GAME_ID" in df.columns:
                game_ids.extend(df["GAME_ID"].head(limit).tolist())
                if len(game_ids) >= limit:
                    break
        except Exception:
            pass

    return game_ids[:limit]


def extract_numeric_id(game_id: str) -> str:
    """Extract numeric portion from game ID.

    Examples:
        '104486-TENE-BEAR' -> '104486'
        'BCL-2024-104486' -> '104486'
    """
    parts = str(game_id).split("-")
    for part in parts:
        if part.isdigit() and len(part) >= 5:
            return part
    # Fallback: return first numeric-looking part
    for part in parts:
        if part.isdigit():
            return part
    return str(game_id)


def probe_endpoint(url: str, timeout: int = 10) -> dict:
    """Probe a single endpoint and return result."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/html, */*",
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        return {
            "url": url,
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type", "unknown"),
            "size": len(response.content),
            "success": response.status_code == 200,
            "sample": response.text[:500] if response.status_code == 200 else None,
        }
    except requests.exceptions.Timeout:
        return {"url": url, "status": "timeout", "success": False}
    except Exception as e:
        return {"url": url, "status": str(e), "success": False}


def probe_game_patterns(game_id: str, league: str = "BCL"):
    """Try various URL patterns for a game ID."""
    numeric_id = extract_numeric_id(game_id)

    print(f"\nProbing game: {game_id} (numeric: {numeric_id})")
    print("-" * 60)

    patterns = []

    for base in FIBA_BASES:
        # Pattern 1: /data/{numeric}/data.json
        patterns.append(f"{base}/data/{numeric_id}/data.json")

        # Pattern 2: /u/{LEAGUE}/{game_id}/data.json
        patterns.append(f"{base}/u/{league}/{game_id}/data.json")

        # Pattern 3: /u/{LEAGUE}/{numeric}/data.json
        patterns.append(f"{base}/u/{league}/{numeric_id}/data.json")

        # Pattern 4: /gamedata/{numeric}.json
        patterns.append(f"{base}/gamedata/{numeric_id}.json")

        # Pattern 5: Original HTML (for comparison)
        patterns.append(f"{base}/u/{league}/{game_id}/bs.html")

    results = []
    for url in patterns:
        result = probe_endpoint(url)
        results.append(result)

        status_str = "OK" if result["success"] else str(result["status"])
        print(f"  [{status_str:>3}] {url}")

        if result["success"] and result.get("sample"):
            # Show first bit of successful response
            sample = result["sample"][:100].replace("\n", " ")
            print(f"       -> {sample}...")

    return results


def main():
    print("=" * 60)
    print("FIBA LiveStats JSON Endpoint Probe")
    print("=" * 60)

    # Test BCL games
    print("\n== BCL Games ==")
    bcl_games = get_sample_game_ids("BCL", 2)
    if bcl_games:
        for game_id in bcl_games:
            probe_game_patterns(game_id, "BCL")
    else:
        print("No BCL game IDs found in index")

    # Test BAL games
    print("\n== BAL Games ==")
    bal_games = get_sample_game_ids("BAL", 2)
    if bal_games:
        for game_id in bal_games:
            probe_game_patterns(game_id, "BAL")
    else:
        print("No BAL game IDs found in index")

    # Test LKL games
    print("\n== LKL Games ==")
    lkl_games = get_sample_game_ids("LKL", 2)
    if lkl_games:
        for game_id in lkl_games:
            probe_game_patterns(game_id, "LKL")
    else:
        print("No LKL game IDs found in index")

    print("\n" + "=" * 60)
    print("Probe complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
