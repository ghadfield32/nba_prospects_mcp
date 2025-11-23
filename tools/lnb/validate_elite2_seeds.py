#!/usr/bin/env python3
"""Validate that Elite 2 seeds are genuine Pro B / ÉLITE 2 games"""

import json
from pathlib import Path

import requests

MAPPING_FILE = Path("tools/lnb/fixture_uuids_by_season.json")
BASE_URL = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12"
DETAIL_URL = BASE_URL + "/fixture_detail?fixtureId={fid}"

# Expected competition names for Pro B / ÉLITE 2
VALID_COMPETITIONS = {
    "PROB",  # Historical name
    "PRO B",
    "ÉLITE 2",
    "ELITE 2",
    "Pro B",
}


def validate_seed(season_key: str, seed_uuid: str) -> dict:
    """Validate a single seed fixture

    Returns dict with: uuid, competition, season, home, away, valid
    """
    url = DETAIL_URL.format(fid=seed_uuid)

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        payload = r.json()

        # Extract metadata from fixture detail
        banner = payload.get("data", {}).get("banner", {})
        competition_name = banner.get("competition", {}).get("name", "Unknown")
        season_name = banner.get("season", {}).get("name", "Unknown")

        # Extract team names
        competitors = payload.get("data", {}).get("competitors", [])
        home_team = "Unknown"
        away_team = "Unknown"

        if len(competitors) >= 2:
            for comp in competitors:
                if comp.get("position") == "home":
                    home_team = comp.get("name", "Unknown")
                elif comp.get("position") == "away":
                    away_team = comp.get("name", "Unknown")

        # Validate competition is Pro B / ÉLITE 2
        is_valid = competition_name in VALID_COMPETITIONS

        return {
            "uuid": seed_uuid,
            "competition": competition_name,
            "season": season_name,
            "home": home_team,
            "away": away_team,
            "valid": is_valid,
        }

    except Exception as e:
        return {
            "uuid": seed_uuid,
            "competition": "ERROR",
            "season": "ERROR",
            "home": str(e),
            "away": "",
            "valid": False,
        }


def main():
    # Load mappings
    with open(MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Filter to Elite 2 seasons
    elite2_keys = [k for k in data["mappings"].keys() if "elite_2" in k]

    print("Validating Elite 2 seeds...")
    print("=" * 80)

    all_valid = True

    for season_key in sorted(elite2_keys):
        seeds = data["mappings"][season_key]

        print(f"\n{season_key}: {len(seeds)} seeds")
        print("-" * 80)

        for i, seed in enumerate(seeds, 1):
            result = validate_seed(season_key, seed)

            status = "[OK]" if result["valid"] else "[FAIL]"
            print(f"  {i}. {status} {result['uuid'][:20]}...")
            print(f"     Competition: {result['competition']}")
            print(f"     Season: {result['season']}")
            print(f"     {result['home']} vs {result['away']}")

            if not result["valid"]:
                all_valid = False

    print("\n" + "=" * 80)
    if all_valid:
        print("[SUCCESS] All seeds validated as genuine Pro B / ÉLITE 2 fixtures")
    else:
        print("[WARNING] Some seeds failed validation - review above")

    return 0 if all_valid else 1


if __name__ == "__main__":
    exit(main())
