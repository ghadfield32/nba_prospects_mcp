"""Discover Elite 2 historical fixtures for 2022-2023 and 2023-2024 seasons"""

import requests

ATRIUM_API_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURES_ENDPOINT = "/v1/embed/12/fixtures"

# Elite 2 season metadata from lnb_league_config.py
ELITE_2_SEASONS = {
    "2022-2023": {
        "competition_id": "213e021f-19b5-11ee-9190-29c4f278bc32",
        "season_id": "7561dbee-19b5-11ee-affc-23e4d3a88307",
    },
    "2023-2024": {
        "competition_id": "0847055c-2fb3-11ef-9b30-3333ffdb8385",
        "season_id": "91334b18-2fb3-11ef-be14-e92481b1d83d",
    },
}

url = f"{ATRIUM_API_BASE}{FIXTURES_ENDPOINT}"

for season, metadata in ELITE_2_SEASONS.items():
    print(f"\n{'='*80}")
    print(f"SEASON: {season}")
    print(f"{'='*80}")

    params = {
        "competitionId": metadata["competition_id"],
        "seasonId": metadata["season_id"],
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        print(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            fixtures = data.get("data", {}).get("fixtures", [])
            print(f"Fixtures found: {len(fixtures)}")

            if fixtures:
                print(f"\nFirst fixture: {fixtures[0].get('fixtureId')}")
                print(f"Last fixture: {fixtures[-1].get('fixtureId')}")
                print(f"Sample game: {fixtures[0].get('name')}")

                # Sample first 3 fixture IDs
                print("\nFirst 3 fixture IDs:")
                for i, fixture in enumerate(fixtures[:3]):
                    print(f"  {i+1}. {fixture.get('fixtureId')} - {fixture.get('name')}")
        else:
            print(f"Error: {r.text[:200]}")

    except Exception as e:
        print(f"Exception: {e}")
