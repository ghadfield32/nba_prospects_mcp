#!/usr/bin/env python3
"""Inspect seed fixture to extract competition/season IDs and verify endpoints"""

import requests

BASE = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12"
DETAIL_URL = BASE + "/fixture_detail?fixtureId={fid}"

# Our current seeds
SEEDS = {
    "2022-2023": "e212bbe0-d4b4-11ee-9363-772280fe00b4",
    "2023-2024": "6cf71dda-6f71-11ef-a0d0-fbbe38dcdd15",
}


def get_json(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def find_ids(obj, hits=None, path=""):
    """Recursively find all fields that look like season/competition IDs"""
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p2 = f"{path}.{k}" if path else k
            # Look for ID-like fields
            if isinstance(v, str) and any(
                x in k.lower() for x in ["season", "competition", "league", "tournament"]
            ):
                if "id" in k.lower() or "uuid" in k.lower():
                    hits.append((p2, v))
            find_ids(v, hits, p2)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_ids(v, hits, f"{path}[{i}]")
    return hits


print("Inspecting Pro B seed fixtures...\n")

for season, seed_uuid in SEEDS.items():
    print(f"{'='*70}")
    print(f"SEASON: {season}")
    print(f"SEED: {seed_uuid}")
    print("=" * 70)

    # Fetch fixture detail
    url = DETAIL_URL.format(fid=seed_uuid)
    print(f"\nFetching: {url}")

    try:
        payload = get_json(url)

        # Find all ID fields
        id_fields = find_ids(payload)

        print(f"\nFound {len(id_fields)} ID-like fields:")
        for path, value in sorted(id_fields)[:20]:  # First 20
            print(f"  {path}: {value}")

        # Try to extract the canonical ones
        banner = payload.get("data", {}).get("banner", {})
        comp_id = banner.get("competition", {}).get("id")
        season_id = banner.get("season", {}).get("id")
        season_name = banner.get("season", {}).get("name")
        comp_name = banner.get("competition", {}).get("name")

        print("\nExtracted (from data.banner):")
        print(f"  Competition ID: {comp_id}")
        print(f"  Competition Name: {comp_name}")
        print(f"  Season ID: {season_id}")
        print(f"  Season Name: {season_name}")

        # Now try the fixtures endpoint
        if comp_id and season_id:
            fixtures_url = f"{BASE}/fixtures?competitionId={comp_id}&seasonId={season_id}"
            print("\nTrying fixtures endpoint:")
            print(f"  {fixtures_url}")

            try:
                fixtures_data = get_json(fixtures_url)
                fixtures_list = fixtures_data.get("data", {}).get("fixtures", [])
                print(f"  Result: {len(fixtures_list)} fixtures found")

                if fixtures_list:
                    print("\n  Sample (first 3):")
                    for i, f in enumerate(fixtures_list[:3]):
                        fid = f.get("fixtureId", "")[:12]
                        name = f.get("name", "Unknown")
                        status = f.get("status", {}).get("value", "")
                        comps = f.get("competitors", [])
                        teams = " vs ".join([c.get("name", "?") for c in comps[:2]])
                        print(f"    {i+1}. {fid}... | {teams} | {status}")
            except Exception as e:
                print(f"  ERROR: {e}")

        print()

    except Exception as e:
        print(f"ERROR fetching fixture: {e}\n")
