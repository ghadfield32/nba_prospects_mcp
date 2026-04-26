#!/usr/bin/env python
"""Quick test of ACB schedule fetch."""

import sys

sys.path.insert(0, "src")
import re

import requests
from bs4 import BeautifulSoup

ACB_BASE_URL = "https://www.acb.com"
season = "2017-18"
temporada = 2018 - 1936

url = f"{ACB_BASE_URL}/es/calendario?temporada={temporada}"
print(f"Fetching: {url}")

resp = requests.get(url, timeout=30)
print(f"Status: {resp.status_code}")

soup = BeautifulSoup(resp.content, "html.parser")
scripts = soup.find_all("script")
print(f"Found {len(scripts)} script tags")

data_content = None
for i, script in enumerate(scripts):
    content = script.string or ""
    if len(content) > 100000 and "teams" in content:
        data_content = content.replace('\\"', '"')
        print(f"Using script {i} with {len(content)} chars")
        break

if not data_content:
    print("No Next.js data found")
    sys.exit(1)

# Extract teams
team_pattern = r'"id":(\d+),"clubId":\d+,"fullName":"([^"]+)","shortName":"([^"]+)","abbreviatedName":"([^"]+)"'
teams = []
for m in re.finditer(team_pattern, data_content):
    teams.append(
        {
            "id": int(m.group(1)),
            "full_name": m.group(2),
            "short_name": m.group(3),
            "abbrev": m.group(4),
        }
    )

print(f"Found {len(teams)} teams:")
for t in teams[:5]:
    print(f"  {t['abbrev']}: {t['short_name']}")

# Extract matches
match_pattern = r'"id":(\d+),"homeTeam":"[^"]+:(\d+)","awayTeam":"[^"]+:(\d+)","homeTeamScore":(\d+|null),"awayTeamScore":(\d+|null),"startDateTime":"([^"]+)"'

games = []
for m in re.finditer(match_pattern, data_content):
    game_id = int(m.group(1))
    home_idx = int(m.group(2))
    away_idx = int(m.group(3))
    home_score = None if m.group(4) == "null" else int(m.group(4))
    away_score = None if m.group(5) == "null" else int(m.group(5))
    game_date = m.group(6)

    if home_idx < len(teams) and away_idx < len(teams):
        home_team = teams[home_idx]["short_name"]
        away_team = teams[away_idx]["short_name"]
    else:
        home_team = f"Team{home_idx}"
        away_team = f"Team{away_idx}"

    games.append(
        {
            "GAME_ID": str(game_id),
            "HOME_TEAM": home_team,
            "AWAY_TEAM": away_team,
            "HOME_SCORE": home_score,
            "AWAY_SCORE": away_score,
            "GAME_DATE": game_date,
        }
    )

print(f"\nFound {len(games)} games:")
for g in games[:5]:
    print(
        f"  {g['GAME_ID']}: {g['HOME_TEAM']} vs {g['AWAY_TEAM']} ({g['HOME_SCORE']}-{g['AWAY_SCORE']})"
    )

# Check for Real Madrid games
rm_games = [g for g in games if "Real Madrid" in g["HOME_TEAM"] or "Real Madrid" in g["AWAY_TEAM"]]
print(f"\nReal Madrid games: {len(rm_games)}")
