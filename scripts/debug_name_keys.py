#!/usr/bin/env python
"""Debug NAME_KEY patterns for validation players."""

import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "src")
import pandas as pd

gold = pd.read_parquet("data/gold/player_career_game.parquet")

print("Searching for Luka Doncic variations...")
luka_patterns = ["doncic", "luka", "dončić"]
for p in luka_patterns:
    matches = gold[gold["NAME_KEY"].str.contains(p, case=False, na=False)]
    if len(matches) > 0:
        print(f"  Pattern '{p}': {len(matches)} rows")
        print(f"    NAME_KEY samples: {list(matches.NAME_KEY.unique()[:5])}")

print()
print("Searching for Nikola Jokic variations...")
jokic_patterns = ["jokic", "nikola", "jokić"]
for p in jokic_patterns:
    matches = gold[gold["NAME_KEY"].str.contains(p, case=False, na=False)]
    if len(matches) > 0:
        print(f"  Pattern '{p}': {len(matches)} rows")
        leagues = list(matches.LEAGUE.unique())
        print(f"    Leagues: {leagues}")
        print(f"    NAME_KEY samples: {list(matches.NAME_KEY.unique()[:5])}")

print()
print("Searching for Paolo Banchero...")
banchero_patterns = ["banchero", "paolo"]
for p in banchero_patterns:
    matches = gold[gold["NAME_KEY"].str.contains(p, case=False, na=False)]
    if len(matches) > 0:
        print(f"  Pattern '{p}': {len(matches)} rows")
        print(f"    NAME_KEY samples: {list(matches.NAME_KEY.unique()[:3])}")

print()
print("ACB NAME_KEY samples (top 20 by games):")
acb = gold[gold["LEAGUE"] == "ACB"]
for name in acb["NAME_KEY"].value_counts().head(20).index:
    print(f"  {name}")

print()
print("ABA NAME_KEY samples (top 20 by games):")
aba = gold[gold["LEAGUE"] == "ABA"]
for name in aba["NAME_KEY"].value_counts().head(20).index:
    print(f"  {name}")

print()
print("NCAA NAME_KEY samples (top 20 by games):")
ncaa = gold[gold["LEAGUE"] == "NCAA_MBB"]
for name in ncaa["NAME_KEY"].value_counts().head(20).index:
    print(f"  {name}")
