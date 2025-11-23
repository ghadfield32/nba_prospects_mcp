#!/usr/bin/env python3
"""Inspect all user-provided Pro B seeds to find bulk listing access"""

import json
from pathlib import Path

import requests

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")
BASE_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12"
DETAIL_URL = BASE_URL + "/fixture_detail?fixtureId={fid}"
FIXTURES_URL = BASE_URL + "/fixtures?competitionId={cid}&seasonId={sid}"


def inspect_seed(season_key: str, seed_uuid: str, index: int):
    """Inspect a seed and test bulk listing access"""
    # Get fixture detail
    url = DETAIL_URL.format(fid=seed_uuid)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        payload = r.json()

        # Extract metadata
        banner = payload.get("data", {}).get("banner", {})
        comp_id = banner.get("competition", {}).get("id", "Unknown")
        season_id = banner.get("season", {}).get("id", "Unknown")
        comp_name = banner.get("competition", {}).get("name", "Unknown")
        season_name = banner.get("season", {}).get("name", "Unknown")

        # Test bulk listing
        fixtures_url = FIXTURES_URL.format(cid=comp_id, sid=season_id)
        r2 = requests.get(fixtures_url, timeout=30)
        r2.raise_for_status()
        fixtures_data = r2.json()
        fixtures = fixtures_data.get("data", {}).get("fixtures", [])

        print(f"  {index}. {seed_uuid[:20]}...")
        print(f"     Competition: {comp_name} ({comp_id[:12]}...)")
        print(f"     Season: {season_name} ({season_id[:12]}...)")
        print(f"     Bulk listing: {len(fixtures)} fixtures")

        return {
            "seed": seed_uuid,
            "comp_id": comp_id,
            "season_id": season_id,
            "comp_name": comp_name,
            "season_name": season_name,
            "fixture_count": len(fixtures),
        }

    except Exception as e:
        print(f"  {index}. {seed_uuid[:20]}... ERROR: {e}")
        return None


def main():
    # Load mappings
    with open(MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Filter to user-provided Pro B seasons
    target_seasons = ["2021-2022_elite_2", "2022-2023_elite_2", "2023-2024_elite_2"]

    for season_key in target_seasons:
        if season_key not in data["mappings"]:
            print(f"\n[SKIP] {season_key} not in mappings")
            continue

        seeds = data["mappings"][season_key]
        print(f"\n{'='*80}")
        print(f"{season_key}: {len(seeds)} seeds")
        print("=" * 80)

        results = []
        for i, seed in enumerate(seeds, 1):
            result = inspect_seed(season_key, seed, i)
            if result:
                results.append(result)

        # Find seeds that unlock bulk listing (>10 fixtures)
        unlocked = [r for r in results if r["fixture_count"] > 10]

        print(f"\n[SUMMARY] {len(unlocked)}/{len(results)} seeds unlock bulk listing")
        if unlocked:
            for r in unlocked:
                print(f"  - {r['season_name']}: {r['fixture_count']} fixtures")
                print(f"    Competition ID: {r['comp_id']}")
                print(f"    Season ID: {r['season_id']}")


if __name__ == "__main__":
    main()
