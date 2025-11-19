#!/usr/bin/env python3
"""Discover and map ALL LNB leagues and competitions

This script queries the Atrium API fixtures endpoint to discover:
1. Betclic ELITE (formerly Pro A) - top tier, 16 teams
2. ELITE 2 (formerly Pro B) - second tier, 20 teams
3. Espoirs ELITE - U21 top-tier youth
4. Espoirs PROB - U21 second-tier youth (may be Espoirs Elite 2)
5. Leaders Cup, Playoffs, All-Star games

Created: 2025-11-18
Purpose: Complete league discovery based on user's intel about naming changes
"""

from __future__ import annotations

import io
import json
import sys
from typing import Any

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ==============================================================================
# CONFIG
# ==============================================================================

ATRIUM_BASE = "https://eapi.web.prod.cloud.atriumsports.com"
FIXTURES_ENDPOINT = f"{ATRIUM_BASE}/v1/embed/12/fixtures"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://lnb.fr/",
}

# Seed competition ID (2024-2025 Betclic Elite) to bootstrap discovery
SEED_COMPETITION = "a2262b45-2fab-11ef-8eb7-99149ebb5652"

print("=" * 80)
print("LNB COMPLETE LEAGUE DISCOVERY")
print("=" * 80)
print()

# ==============================================================================
# STEP 1: Query seed competition to get all available leagues
# ==============================================================================

print("[STEP 1] Querying Atrium API for league structure...")
print("-" * 80)

try:
    response = requests.get(
        FIXTURES_ENDPOINT,
        params={"competitionId": SEED_COMPETITION},
        headers=HEADERS,
        timeout=30,
    )

    if response.status_code != 200:
        print(f"✗ HTTP {response.status_code}")
        sys.exit(1)

    data = response.json()
    fixtures_data = data.get("data", {})
    seasons_data = fixtures_data.get("seasons", {})

    competitions = seasons_data.get("competitions", {})
    seasons_list = seasons_data.get("seasons", [])

    print(f"✓ Found {len(competitions)} competitions")
    print(f"✓ Found {len(seasons_list)} season entries")
    print()

except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# ==============================================================================
# STEP 2: Categorize leagues by type
# ==============================================================================

print("[STEP 2] Categorizing leagues...")
print("-" * 80)

league_categories: dict[str, list[dict[str, Any]]] = {
    "Betclic ELITE": [],
    "ELITE 2": [],
    "Espoirs ELITE": [],
    "Espoirs PROB": [],
    "Leaders Cup": [],
    "Playoffs": [],
    "Other": [],
}

for comp_id, comp_info in competitions.items():
    comp_name = comp_info.get("name", "")

    # Find matching season entries
    matching_seasons = [s for s in seasons_list if s.get("competitionId") == comp_id]

    entry = {
        "competition_id": comp_id,
        "name": comp_name,
        "seasons": matching_seasons,
    }

    # Categorize
    if (
        "Betclic" in comp_name
        and "LITE" in comp_name
        and "Playoff" not in comp_name
        and "Play-In" not in comp_name
    ):
        league_categories["Betclic ELITE"].append(entry)
    elif "LITE 2" in comp_name or comp_name == "ÉLITE 2":
        league_categories["ELITE 2"].append(entry)
    elif "Espoirs ELITE" in comp_name or "Espoirs ELITE" in comp_name:
        league_categories["Espoirs ELITE"].append(entry)
    elif "Espoirs PROB" in comp_name:
        league_categories["Espoirs PROB"].append(entry)
    elif "Leaders Cup" in comp_name:
        league_categories["Leaders Cup"].append(entry)
    elif "Playoff" in comp_name or "Play-In" in comp_name:
        league_categories["Playoffs"].append(entry)
    elif comp_name == "PROB":
        league_categories["ELITE 2"].append(entry)
    else:
        league_categories["Other"].append(entry)

# Print summary
for category, entries in league_categories.items():
    if entries:
        print(f"\n{category}: {len(entries)} competitions")
        for entry in entries:
            print(f"  - {entry['name']}")
            for season in entry["seasons"]:
                year = season.get("year")
                season_id = season.get("seasonId", "N/A")
                print(f"    {year}: season_id={season_id[:8]}...")

print()
print("=" * 80)

# ==============================================================================
# STEP 3: Build SEASON_METADATA for main leagues
# ==============================================================================

print("[STEP 3] Building SEASON_METADATA for regular season leagues...")
print("-" * 80)

# Group by league type and year
metadata_by_league: dict[str, dict[str, dict[str, str]]] = {
    "betclic_elite": {},
    "elite_2": {},
    "espoirs_elite": {},
    "espoirs_prob": {},
}

# Betclic ELITE
for entry in league_categories["Betclic ELITE"]:
    for season in entry["seasons"]:
        year = season.get("year")
        season_key = f"{year-1}-{year}"
        metadata_by_league["betclic_elite"][season_key] = {
            "competition_id": entry["competition_id"],
            "season_id": season.get("seasonId"),
            "competition_name": entry["name"],
        }

# ELITE 2
for entry in league_categories["ELITE 2"]:
    for season in entry["seasons"]:
        year = season.get("year")
        season_key = f"{year-1}-{year}"
        metadata_by_league["elite_2"][season_key] = {
            "competition_id": entry["competition_id"],
            "season_id": season.get("seasonId"),
            "competition_name": entry["name"],
        }

# Espoirs ELITE
for entry in league_categories["Espoirs ELITE"]:
    for season in entry["seasons"]:
        year = season.get("year")
        season_key = f"{year-1}-{year}"
        metadata_by_league["espoirs_elite"][season_key] = {
            "competition_id": entry["competition_id"],
            "season_id": season.get("seasonId"),
            "competition_name": entry["name"],
        }

# Espoirs PROB
for entry in league_categories["Espoirs PROB"]:
    for season in entry["seasons"]:
        year = season.get("year")
        season_key = f"{year-1}-{year}"
        metadata_by_league["espoirs_prob"][season_key] = {
            "competition_id": entry["competition_id"],
            "season_id": season.get("seasonId"),
            "competition_name": entry["name"],
        }

print("\nGenerated SEASON_METADATA:")
print()
for league, seasons in metadata_by_league.items():
    if seasons:
        print(f"# {league.upper().replace('_', ' ')}")
        print(f"{league.upper()}_SEASONS = {{")
        for season_key in sorted(seasons.keys()):
            meta = seasons[season_key]
            print(f'    "{season_key}": {{')
            print(f'        "competition_id": "{meta["competition_id"]}",')
            print(f'        "season_id": "{meta["season_id"]}",')
            print(f'        "competition_name": "{meta["competition_name"]}",')
            print("    },")
        print("}")
        print()

# ==============================================================================
# STEP 4: Test fixture discovery for each league
# ==============================================================================

print("=" * 80)
print("[STEP 4] Testing fixture discovery for each league...")
print("-" * 80)

test_results = []

for league_name, seasons in metadata_by_league.items():
    if not seasons:
        continue

    print(f"\n{league_name.upper().replace('_', ' ')}:")

    # Test most recent season
    latest_season = sorted(seasons.keys())[-1]
    meta = seasons[latest_season]
    comp_id = meta["competition_id"]

    try:
        response = requests.get(
            FIXTURES_ENDPOINT,
            params={"competitionId": comp_id},
            headers=HEADERS,
            timeout=10,
        )

        if response.status_code == 200:
            fixtures_data = response.json().get("data", {})
            fixtures = fixtures_data.get("fixtures", [])

            print(f"  ✓ {latest_season}: {len(fixtures)} fixtures found")
            print(f"    Competition ID: {comp_id[:8]}...")

            # Sample first fixture
            if fixtures:
                sample = fixtures[0]
                print(f"    Sample: {sample.get('name', 'N/A')}")
                print(f"    Date: {sample.get('startTimeLocal', 'N/A')}")

            test_results.append(
                {
                    "league": league_name,
                    "season": latest_season,
                    "fixtures_count": len(fixtures),
                    "status": "SUCCESS",
                }
            )
        else:
            print(f"  ✗ {latest_season}: HTTP {response.status_code}")
            test_results.append(
                {
                    "league": league_name,
                    "season": latest_season,
                    "status": "FAILED",
                }
            )

    except Exception as e:
        print(f"  ✗ Error: {e}")
        test_results.append(
            {
                "league": league_name,
                "season": latest_season,
                "status": "ERROR",
            }
        )

# ==============================================================================
# SUMMARY
# ==============================================================================

print()
print("=" * 80)
print("DISCOVERY SUMMARY")
print("=" * 80)
print()

print("Leagues Discovered:")
print(f"  Betclic ELITE:   {len(metadata_by_league['betclic_elite'])} seasons")
print(f"  ELITE 2:         {len(metadata_by_league['elite_2'])} seasons")
print(f"  Espoirs ELITE:   {len(metadata_by_league['espoirs_elite'])} seasons")
print(f"  Espoirs PROB:    {len(metadata_by_league['espoirs_prob'])} seasons")
print()

print("Fixture Discovery Test Results:")
successful = sum(1 for r in test_results if r["status"] == "SUCCESS")
print(f"  {successful}/{len(test_results)} leagues successfully queried")
print()

print("✅ DISCOVERY COMPLETE")
print()
print("Next Steps:")
print("  1. Update build_game_index.py with all SEASON_METADATA")
print("  2. Update bulk_discover_atrium_api.py to support all leagues")
print("  3. Run bulk discovery for Elite 2 and Espoirs leagues")
print("  4. Update validation/monitoring scripts for multi-league support")
print()

# ==============================================================================
# EXPORT DATA
# ==============================================================================

# Save to JSON for easy import
output = {
    "leagues": metadata_by_league,
    "test_results": test_results,
    "discovery_date": "2025-11-18",
}

output_file = "lnb_leagues_discovered.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Saved discovery results to: {output_file}")
print()
