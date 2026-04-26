#!/usr/bin/env python
# ruff: noqa: E402
"""Find and fetch a Real Madrid game with Luka Doncic."""

import sys

sys.path.insert(0, "src")
import functools

print = functools.partial(print, flush=True)

import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

ACB_BASE_URL = "https://www.acb.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        if hasattr(value, "item"):
            return int(value.item())
        if isinstance(value, int | float):
            return int(value)
        s = str(value).strip()
        if "." in s:
            return int(float(s))
        match = re.search(r"-?\d+", s)
        return int(match.group(0)) if match else default
    except Exception:
        return default


# Fetch 2017-18 schedule
temporada = 2018 - 1936
url = f"{ACB_BASE_URL}/es/calendario?temporada={temporada}"
print(f"Fetching schedule: {url}")

resp = requests.get(url, headers=HEADERS, timeout=30)
soup = BeautifulSoup(resp.content, "html.parser")

data_content = None
for script in soup.find_all("script"):
    content = script.string or ""
    if len(content) > 100000 and "teams" in content:
        data_content = content.replace('\\"', '"')
        break

# Extract teams
team_pattern = r'"id":(\d+),"clubId":\d+,"fullName":"([^"]+)","shortName":"([^"]+)"'
teams = []
for m in re.finditer(team_pattern, data_content):
    teams.append({"id": int(m.group(1)), "full_name": m.group(2), "short_name": m.group(3)})

print(f"Found {len(teams)} teams")
rm_idx = None
for i, t in enumerate(teams):
    if "real madrid" in t["full_name"].lower():
        rm_idx = i
        print(f"Real Madrid: index={i}, name='{t['short_name']}'")
        break

# Extract Real Madrid games
match_pattern = r'"id":(\d+),"homeTeam":"[^"]+:(\d+)","awayTeam":"[^"]+:(\d+)","homeTeamScore":(\d+|null),"awayTeamScore":(\d+|null),"startDateTime":"([^"]+)"'
rm_games = []
for m in re.finditer(match_pattern, data_content):
    home_idx, away_idx = int(m.group(2)), int(m.group(3))
    if home_idx == rm_idx or away_idx == rm_idx:
        rm_games.append(
            {
                "GAME_ID": m.group(1),
                "HOME": teams[home_idx]["short_name"]
                if home_idx < len(teams)
                else f"Team{home_idx}",
                "AWAY": teams[away_idx]["short_name"]
                if away_idx < len(teams)
                else f"Team{away_idx}",
            }
        )

print(f"Found {len(rm_games)} Real Madrid games")

# Fetch first Real Madrid game
if rm_games:
    game = rm_games[0]
    print(f"\nFetching: {game['HOME']} vs {game['AWAY']} (ID: {game['GAME_ID']})")

    box_url = f"{ACB_BASE_URL}/partido/estadisticas/id/{game['GAME_ID']}"
    tables = pd.read_html(box_url, encoding="utf-8")

    for table_idx in [1, 2]:
        table = tables[table_idx]
        if isinstance(table.columns, pd.MultiIndex):
            table.columns = range(len(table.columns))

        print(f"\nTeam {table_idx} players:")
        for _, row in table.iterrows():
            name = str(row.iloc[1]) if len(row) > 1 else ""
            if not name or name.lower() in ["totales", "jugador"]:
                continue
            pts = _safe_int(row.iloc[3])
            reb = _safe_int(row.iloc[10])
            ast = _safe_int(row.iloc[12])
            is_luka = "LUKA" if "doncic" in name.lower() else ""
            print(f"  {name:<20} {pts:>3}pts {reb:>2}reb {ast:>2}ast {is_luka}")
