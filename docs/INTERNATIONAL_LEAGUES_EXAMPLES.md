# International Basketball Leagues - Usage Examples

Comprehensive examples for fetching and analyzing data from international basketball leagues (ACB, FIBA cluster, LNB).

## Table of Contents

1. [Quick Start](#quick-start)
2. [FIBA Leagues (BCL, BAL, ABA, LKL)](#fiba-leagues)
3. [ACB (Spanish League)](#acb-spanish-league)
4. [LNB Pro A (French League)](#lnb-pro-a-french-league)
5. [Shot Chart Visualization](#shot-chart-visualization)
6. [Advanced Analytics](#advanced-analytics)
7. [Data Quality & Source Tracking](#data-quality--source-tracking)

## Quick Start

### Installation

```python
# Install the package
pip install cbbpy

# Or for development
pip install -e .
```

### Basic Usage

```python
from src.cbb_data.fetchers import bcl, acb, lnb

# Fetch BCL player season stats
bcl_players = bcl.fetch_player_season("2023-24")
print(bcl_players[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]].head(10))

# Fetch ACB team season stats
acb_teams = acb.fetch_acb_team_season("2024")
print(acb_teams[["TEAM", "GP", "W", "L", "WIN_PCT"]].head())

# Fetch LNB standings
lnb_standings = lnb.fetch_lnb_team_season("2024")
print(lnb_standings[["RANK", "TEAM", "W_L", "WIN_PCT"]].head())
```

## FIBA Leagues

FIBA leagues (BCL, BAL, ABA, LKL) use the FIBA LiveStats JSON API with HTML fallback.

### Basketball Champions League (BCL)

```python
from src.cbb_data.fetchers import bcl

# Fetch schedule
schedule = bcl.fetch_schedule("2023-24")
print(f"Found {len(schedule)} BCL games")
print(schedule[["GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]].head())

# Fetch player game-level stats
player_game = bcl.fetch_player_game("2023-24")
print(f"Found {len(player_game)} player-game records")

# Top scorers
top_scorers = player_game.nlargest(10, "PTS")
print(top_scorers[["PLAYER_NAME", "TEAM", "GAME_ID", "PTS", "REB", "AST"]])

# Check data source (JSON API vs HTML fallback)
source_breakdown = player_game["SOURCE"].value_counts()
print(f"\nData sources:")
print(source_breakdown)

# Fetch play-by-play
pbp = bcl.fetch_pbp("2023-24")
print(f"Found {len(pbp)} play-by-play events")

# Shot chart data (JSON API only)
shots = bcl.fetch_shots("2023-24")
print(f"Found {len(shots)} shot events with coordinates")
print(shots[["PLAYER_NAME", "SHOT_TYPE", "SHOT_RESULT", "X", "Y"]].head())
```

### Basketball Africa League (BAL)

```python
from src.cbb_data.fetchers import bal

# Same API as BCL
schedule = bal.fetch_schedule("2023-24")
player_game = bal.fetch_player_game("2023-24")
shots = bal.fetch_shots("2023-24")

# Analyze 3-point shooting
three_pointers = shots[shots["SHOT_TYPE"] == "3PT"]
three_pt_pct = (
    three_pointers[three_pointers["SHOT_RESULT"] == "MADE"].shape[0]
    / three_pointers.shape[0] * 100
)
print(f"BAL 3PT%: {three_pt_pct:.1f}%")
```

### ABA League (Adriatic League)

```python
from src.cbb_data.fetchers import aba

schedule = aba.fetch_schedule("2023-24")
player_game = aba.fetch_player_game("2023-24")
pbp = aba.fetch_pbp("2023-24")
shots = aba.fetch_shots("2023-24")

# Player season aggregates
player_season = aba.fetch_player_season("2023-24")
print(player_season.nlargest(10, "PTS")[["PLAYER_NAME", "TEAM", "GP", "PPG", "RPG", "APG"]])
```

### LKL (Lithuanian League)

```python
from src.cbb_data.fetchers import lkl

schedule = lkl.fetch_schedule("2023-24")
player_game = lkl.fetch_player_game("2023-24")
team_game = lkl.fetch_team_game("2023-24")
pbp = lkl.fetch_pbp("2023-24")
shots = lkl.fetch_shots("2023-24")

# Team performance analysis
team_season = lkl.fetch_team_season("2023-24")
print(team_season.sort_values("PPG", ascending=False))
```

## ACB (Spanish League)

ACB uses web scraping with comprehensive error handling and manual CSV fallback.

### Player Season Stats

```python
from src.cbb_data.fetchers import acb

# Fetch player season stats
player_season = acb.fetch_acb_player_season("2024", per_mode="Totals")
print(f"Found {len(player_season)} ACB players")

# Top scorers
top_scorers = player_season.nlargest(10, "PTS")
print(top_scorers[["PLAYER_NAME", "TEAM", "GP", "PTS", "REB", "AST"]])

# Per-game averages
player_season_pg = acb.fetch_acb_player_season("2024", per_mode="PerGame")
print(player_season_pg[["PLAYER_NAME", "TEAM", "PPG", "RPG", "APG"]].head())
```

### Team Season Stats

```python
# Team standings
team_season = acb.fetch_acb_team_season("2024")
print(team_season.sort_values("WIN_PCT", ascending=False))

# Offensive/Defensive ratings
print(team_season[["TEAM", "OFF_RATING", "DEF_RATING", "NET_RATING"]].head())
```

### Error Handling & Fallback

```python
# ACB automatically handles 403 errors and falls back to manual CSV
try:
    schedule = acb.fetch_acb_schedule("2024-25")

    if schedule.empty:
        print("Schedule not available. Create manual CSV at:")
        print("  data/manual/acb/schedule_2024-25.csv")
        print("See tools/acb/README.md for CSV format")
except Exception as e:
    print(f"Error fetching ACB schedule: {e}")
```

### Historical Data (Zenodo)

```python
# Historical ACB data (1983-2023) automatically fetched from Zenodo
historical = acb.fetch_acb_player_season("2020", per_mode="Totals")
print(f"Historical data: {len(historical)} players from 2020 season")
```

## LNB Pro A (French League)

LNB currently has team standings available. Player/game data requires API discovery.

### Team Standings

```python
from src.cbb_data.fetchers import lnb

# Fetch standings (available)
standings = lnb.fetch_lnb_team_season("2024")
print(standings[["RANK", "TEAM", "GP", "W", "L", "WIN_PCT", "PTS_DIFF"]].head())

# Form analysis
print(standings[["TEAM", "FORM", "HOME_RECORD", "AWAY_RECORD"]])
```

### API Discovery (Required for Player/Game Data)

```python
# These return empty DataFrames until API is discovered
# See tools/lnb/README.md for implementation guide

schedule = lnb.fetch_lnb_schedule("2024")  # Empty (needs implementation)
player_season = lnb.fetch_lnb_player_season("2024")  # Empty (needs implementation)
box_score = lnb.fetch_lnb_box_score("12345")  # Empty (needs implementation)

if schedule.empty:
    print("LNB schedule requires API discovery")
    print("See tools/lnb/README.md for instructions")
    print("Use browser DevTools to discover endpoints")
```

## Shot Chart Visualization

Visualize shot locations from FIBA JSON API.

### Basic Shot Chart

```python
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from src.cbb_data.fetchers import bcl

# Fetch shots for a team
shots = bcl.fetch_shots("2023-24")
team_shots = shots[shots["TEAM"] == "Team Name Here"]

# Create court visualization
fig, ax = plt.subplots(figsize=(10, 9.4))

# Draw half court (simplified)
ax.set_xlim(0, 50)
ax.set_ylim(0, 47)

# Paint (key)
paint = patches.Rectangle((17, 0), 16, 19, linewidth=2, edgecolor='black', facecolor='none')
ax.add_patch(paint)

# 3-point arc (FIBA: 6.75m radius)
three_pt = patches.Arc((25, 5.25), 13.5, 13.5, angle=0, theta1=0, theta2=180, linewidth=2, edgecolor='black')
ax.add_patch(three_pt)

# Plot shots
made = team_shots[team_shots["SHOT_RESULT"] == "MADE"]
missed = team_shots[team_shots["SHOT_RESULT"] == "MISSED"]

ax.scatter(made["X"], made["Y"], c='green', s=50, alpha=0.6, label='Made')
ax.scatter(missed["X"], missed["Y"], c='red', s=50, alpha=0.4, marker='x', label='Missed')

ax.legend()
ax.set_aspect('equal')
ax.set_title(f"Shot Chart: {team_shots['TEAM'].iloc[0]}")
plt.show()
```

### Shot Chart with Hexbin Heatmap

```python
import numpy as np

# Create hexbin heatmap
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# Made shots heatmap
hexbin1 = ax1.hexbin(made["X"], made["Y"], gridsize=15, cmap='Greens', alpha=0.7)
ax1.set_title("Made Shots")
ax1.set_xlim(0, 50)
ax1.set_ylim(0, 47)
plt.colorbar(hexbin1, ax=ax1)

# Missed shots heatmap
hexbin2 = ax2.hexbin(missed["X"], missed["Y"], gridsize=15, cmap='Reds', alpha=0.7)
ax2.set_title("Missed Shots")
ax2.set_xlim(0, 50)
ax2.set_ylim(0, 47)
plt.colorbar(hexbin2, ax=ax2)

plt.suptitle(f"Shot Heatmap: {team_shots['TEAM'].iloc[0]}")
plt.show()
```

### Shot Accuracy by Zone

```python
# Define zones
def categorize_shot_distance(x, y):
    """Categorize shot by distance from basket (25, 5.25)"""
    dist = np.sqrt((x - 25)**2 + (y - 5.25)**2)
    if dist < 10:
        return "Paint"
    elif dist < 22.5:  # ~6.75m FIBA 3-point line
        return "Mid-range"
    else:
        return "Three-point"

shots["ZONE"] = shots.apply(lambda row: categorize_shot_distance(row["X"], row["Y"]), axis=1)

# Calculate accuracy by zone
zone_stats = shots.groupby(["ZONE", "SHOT_RESULT"]).size().unstack(fill_value=0)
zone_stats["TOTAL"] = zone_stats.sum(axis=1)
zone_stats["FG_PCT"] = zone_stats["MADE"] / zone_stats["TOTAL"] * 100

print(zone_stats)
```

## Advanced Analytics

### Player Efficiency

```python
from src.cbb_data.fetchers import bcl

player_game = bcl.fetch_player_game("2023-24")

# Calculate efficiency rating
player_game["EFF"] = (
    player_game["PTS"]
    + player_game["REB"]
    + player_game["AST"]
    + player_game["STL"]
    + player_game["BLK"]
    - (player_game["FGA"] - player_game["FGM"])
    - (player_game["FTA"] - player_game["FTM"])
    - player_game["TOV"]
)

# Top performers by efficiency
top_eff = player_game.nlargest(20, "EFF")
print(top_eff[["PLAYER_NAME", "TEAM", "PTS", "REB", "AST", "EFF"]])
```

### Team Pace & Efficiency

```python
from src.cbb_data.fetchers import aba

team_game = aba.fetch_team_game("2023-24")

# Calculate possessions (approximation)
team_game["POSS"] = (
    team_game["FGA"]
    + 0.44 * team_game["FTA"]
    - team_game["OREB"]
    + team_game["TOV"]
)

# Offensive/Defensive ratings
team_game["OFF_RATING"] = team_game["PTS"] / team_game["POSS"] * 100
team_game["DEF_RATING"] = 100  # Requires opponent data

# Team season aggregates
team_season = team_game.groupby("TEAM").agg({
    "PTS": "sum",
    "POSS": "sum",
    "OFF_RATING": "mean"
}).reset_index()

print(team_season.sort_values("OFF_RATING", ascending=False))
```

### Four Factors Analysis

```python
from src.cbb_data.fetchers import lkl

team_game = lkl.fetch_team_game("2023-24")

# Four Factors
team_game["EFG_PCT"] = (team_game["FGM"] + 0.5 * team_game["FG3M"]) / team_game["FGA"] * 100
team_game["TOV_PCT"] = team_game["TOV"] / (team_game["FGA"] + 0.44 * team_game["FTA"] + team_game["TOV"]) * 100
team_game["OREB_PCT"] = team_game["OREB"] / (team_game["OREB"] + team_game["DREB"]) * 100  # Simplified
team_game["FT_RATE"] = team_game["FTA"] / team_game["FGA"]

# Team season four factors
team_season = team_game.groupby("TEAM").agg({
    "EFG_PCT": "mean",
    "TOV_PCT": "mean",
    "OREB_PCT": "mean",
    "FT_RATE": "mean"
}).reset_index()

print(team_season)
```

## Data Quality & Source Tracking

### Check Data Sources

```python
from src.cbb_data.fetchers import bcl, bal, aba, lkl

# All FIBA leagues track SOURCE metadata
leagues = [
    ("BCL", bcl),
    ("BAL", bal),
    ("ABA", aba),
    ("LKL", lkl),
]

for league_name, league_module in leagues:
    player_game = league_module.fetch_player_game("2023-24")

    if not player_game.empty and "SOURCE" in player_game.columns:
        sources = player_game["SOURCE"].value_counts()
        print(f"\n{league_name} Data Sources:")
        print(sources)
        print(f"  JSON API: {sources.get('fiba_json', 0)} records")
        print(f"  HTML Fallback: {sources.get('fiba_html', 0)} records")
```

### Validate Data Completeness

```python
from src.cbb_data.fetchers import bcl

player_game = bcl.fetch_player_game("2023-24")

# Check for missing values
missing = player_game.isnull().sum()
print("Missing values:")
print(missing[missing > 0])

# Check for required columns
required_cols = ["PLAYER_NAME", "TEAM", "GAME_ID", "PTS", "REB", "AST", "SOURCE"]
missing_cols = [col for col in required_cols if col not in player_game.columns]
if missing_cols:
    print(f"Missing required columns: {missing_cols}")
else:
    print("All required columns present")

# Check data types
print("\nData types:")
print(player_game[required_cols].dtypes)
```

### Performance Monitoring

```python
import time

# Time data fetching
start = time.time()
player_game = bcl.fetch_player_game("2023-24")
elapsed = time.time() - start

print(f"Fetched {len(player_game)} records in {elapsed:.2f}s")
print(f"Rate: {len(player_game) / elapsed:.0f} records/sec")

# Check caching
start2 = time.time()
player_game_cached = bcl.fetch_player_game("2023-24")
elapsed2 = time.time() - start2

print(f"Cached fetch: {elapsed2:.4f}s (speedup: {elapsed / elapsed2:.1f}x)")
```

## Best Practices

### 1. Handle Empty DataFrames

```python
from src.cbb_data.fetchers import lnb

# Always check if DataFrame is empty
schedule = lnb.fetch_lnb_schedule("2024")

if schedule.empty:
    print("No schedule data available")
    print("Check logs for reason (not implemented, 403 error, etc.)")
else:
    print(f"Found {len(schedule)} games")
```

### 2. Use Try-Except for Network Errors

```python
from src.cbb_data.fetchers import acb

try:
    player_season = acb.fetch_acb_player_season("2024")
except Exception as e:
    print(f"Error fetching ACB data: {e}")
    print("Consider using manual CSV fallback")
```

### 3. Respect Rate Limits

```python
# Fetchers have built-in rate limiting
# For bulk fetching, add additional delays

import time

seasons = ["2020-21", "2021-22", "2022-23", "2023-24"]
all_data = []

for season in seasons:
    print(f"Fetching {season}...")
    data = bcl.fetch_player_season(season)
    all_data.append(data)
    time.sleep(2)  # Extra delay between seasons

combined = pd.concat(all_data, ignore_index=True)
```

### 4. Cache Results Locally

```python
# Save fetched data to avoid repeated API calls
player_season = bcl.fetch_player_season("2023-24")
player_season.to_parquet("bcl_player_season_2023_24.parquet")

# Load from local cache
cached_data = pd.read_parquet("bcl_player_season_2023_24.parquet")
```

## Troubleshooting

### FIBA JSON API Fails

```python
# Check if HTML fallback is working
from src.cbb_data.fetchers import bcl

player_game = bcl.fetch_player_game("2023-24", force_refresh=True)

if not player_game.empty:
    if (player_game["SOURCE"] == "fiba_html").all():
        print("JSON API failed, but HTML fallback working")
    elif (player_game["SOURCE"] == "fiba_json").all():
        print("JSON API working correctly")
```

### ACB 403 Errors

```python
# ACB may block requests - use manual CSV fallback
# See tools/acb/README.md for CSV format
print("Create manual CSV files at:")
print("  data/manual/acb/player_season_2024.csv")
print("  data/manual/acb/schedule_2024-25.csv")
```

### LNB API Not Implemented

```python
# LNB player/game data requires API discovery
# See tools/lnb/README.md for implementation guide
print("Use browser DevTools to discover LNB API endpoints")
print("See tools/lnb/README.md for step-by-step guide")
```

## Resources

- **FIBA Game Index Builder**: `tools/fiba/build_game_index.py`
- **ACB API Discovery**: `tools/acb/README.md`
- **LNB API Discovery**: `tools/lnb/README.md`
- **Validation Tests**: `tests/test_international_data_sources.py`
- **Web Scraping Findings**: `docs/LEAGUE_WEB_SCRAPING_FINDINGS.md`

## Contributing

To add support for new leagues or improve existing fetchers:

1. Follow the patterns in existing fetchers (JSON-first, HTML fallback)
2. Add comprehensive error handling
3. Track data source in SOURCE column
4. Add validation tests
5. Document in README and examples
6. Update PROJECT_LOG.md

For questions or issues, see `PROJECT_LOG.md` for development history.
