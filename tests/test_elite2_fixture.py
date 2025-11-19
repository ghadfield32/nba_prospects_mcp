import requests

url = "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixture_detail"
elite2_uuid = "bf0f06a2-67e5-11f0-a6cc-4b31bc5c544b"  # Elite 2 game: Orléans - Caen

# Try without state parameter
params = {"fixtureId": elite2_uuid}
r = requests.get(url, params=params, timeout=10)

print(f"Status Code: {r.status_code}")
print(f"Content Length: {len(r.text)}")

if r.status_code == 200:
    try:
        data = r.json()
        game_data = data.get("data", {})

        # Extract from banner structure
        banner = game_data.get("banner", {})
        competition = banner.get("competition", {})
        fixture = banner.get("fixture", {})
        competitors = fixture.get("competitors", [])

        print(f"\nCompetition: {competition.get('name')}")
        print(f"Competition ID: {competition.get('id')}")

        if len(competitors) >= 2:
            print(f"Home: {competitors[0].get('name')}")
            print(f"Away: {competitors[1].get('name')}")

        print(f"Date: {fixture.get('startsAt')}")
        status_val = fixture.get("status")
        print(f"Status: {status_val.get('value') if isinstance(status_val, dict) else status_val}")

        # Check for PBP/shots data
        print(f"\nHas periodData: {'periodData' in game_data}")
        print(f"Has statistics: {'statistics' in game_data}")

    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        import traceback

        traceback.print_exc()
else:
    print(f"Error response: {r.text[:200]}")
