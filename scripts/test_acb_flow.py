#!/usr/bin/env python
# ruff: noqa: E402
"""Quick test of ACB full flow with just 5 games."""

import sys

sys.path.insert(0, "src")

# Force unbuffered output
import functools

print = functools.partial(print, flush=True)

import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

print("=" * 60)
print("ACB FLOW TEST - Fetching 5 games from 2017-18")
print("=" * 60)

ACB_BASE_URL = "https://www.acb.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}


def _safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        if hasattr(value, "item"):
            return int(value.item())
        if isinstance(value, int | float):
            return int(value)
        s = str(value).strip().replace(",", "")
        if "." in s:
            return int(float(s))
        match = re.search(r"-?\d+", s)
        return int(match.group(0)) if match else default
    except Exception:
        return default


def _parse_shooting(text):
    try:
        text = str(text).strip()
        if "/" in text:
            parts = text.split("/")
            if len(parts) == 2:
                return _safe_int(parts[0]), _safe_int(parts[1])
    except Exception:
        pass
    return 0, 0


# Step 1: Fetch schedule
print("\n1. Fetching 2017-18 schedule...")
temporada = 2018 - 1936  # 82
url = f"{ACB_BASE_URL}/es/calendario?temporada={temporada}"
print(f"   URL: {url}")

resp = requests.get(url, headers=HEADERS, timeout=30)
soup = BeautifulSoup(resp.content, "html.parser")

# Find Next.js data
data_content = None
for script in soup.find_all("script"):
    content = script.string or ""
    if len(content) > 100000 and "teams" in content:
        data_content = content.replace('\\"', '"')
        break

if not data_content:
    print("   ERROR: No data found!")
    sys.exit(1)

# Extract teams
team_pattern = r'"id":(\d+),"clubId":\d+,"fullName":"([^"]+)","shortName":"([^"]+)","abbreviatedName":"([^"]+)"'
teams = []
for m in re.finditer(team_pattern, data_content):
    teams.append({"id": int(m.group(1)), "short_name": m.group(3)})
print(f"   Found {len(teams)} teams")

# Extract matches
match_pattern = r'"id":(\d+),"homeTeam":"[^"]+:(\d+)","awayTeam":"[^"]+:(\d+)","homeTeamScore":(\d+|null),"awayTeamScore":(\d+|null),"startDateTime":"([^"]+)"'
games = []
for m in re.finditer(match_pattern, data_content):
    game_id = int(m.group(1))
    home_idx, away_idx = int(m.group(2)), int(m.group(3))
    home_team = teams[home_idx]["short_name"] if home_idx < len(teams) else f"Team{home_idx}"
    away_team = teams[away_idx]["short_name"] if away_idx < len(teams) else f"Team{away_idx}"
    games.append(
        {
            "GAME_ID": str(game_id),
            "HOME_TEAM": home_team,
            "AWAY_TEAM": away_team,
            "GAME_DATE": m.group(6),
        }
    )

print(f"   Found {len(games)} games")

# Step 2: Fetch box scores for first 5 games
print("\n2. Fetching box scores for 5 games...")
all_players = []

for i, game in enumerate(games[:5]):
    game_id = game["GAME_ID"]
    print(f"   Game {i+1}: {game_id} ({game['HOME_TEAM']} vs {game['AWAY_TEAM']})")

    box_url = f"{ACB_BASE_URL}/partido/estadisticas/id/{game_id}"
    try:
        tables = pd.read_html(box_url, encoding="utf-8")

        for table_idx in [1, 2]:
            if table_idx >= len(tables):
                continue
            table = tables[table_idx]
            if isinstance(table.columns, pd.MultiIndex):
                table.columns = range(len(table.columns))

            team_name = game["HOME_TEAM"] if table_idx == 1 else game["AWAY_TEAM"]

            for _, row in table.iterrows():
                player_name = str(row.iloc[1]) if len(row) > 1 else ""
                if not player_name or player_name.lower() in ["totales", "jugador"]:
                    continue

                all_players.append(
                    {
                        "GAME_ID": game_id,
                        "PLAYER_NAME": player_name,
                        "TEAM": team_name,
                        "PTS": _safe_int(row.iloc[3]),
                        "REB": _safe_int(row.iloc[10]),
                        "AST": _safe_int(row.iloc[12]),
                    }
                )

        print(f"      -> Found {len([p for p in all_players if p['GAME_ID'] == game_id])} players")
    except Exception as e:
        print(f"      -> ERROR: {e}")

    import time

    time.sleep(0.5)

# Step 3: Summary
print("\n3. Summary:")
print(f"   Total player-game rows: {len(all_players)}")

df = pd.DataFrame(all_players)
print(f"   Unique players: {df['PLAYER_NAME'].nunique()}")

# Check for Luka (he might not be in first 5 games)
luka = df[df["PLAYER_NAME"].str.contains("Doncic", case=False, na=False)]
if len(luka) > 0:
    print("\n   FOUND LUKA DONCIC!")
    print(luka)
else:
    print("\n   (Luka not in first 5 games - expected)")

# Show sample data
print("\n   Sample data (first 10 rows):")
print(df.head(10).to_string())

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
