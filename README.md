# College & International Basketball Data Library

A unified Python library for accessing college basketball (NCAA Men's & Women's) and international basketball data (EuroLeague) with a simple, consistent API.

## 🎯 What Is This?

This library provides **one simple function** to pull basketball data from multiple sources:

```python
from cbb_data.api.datasets import get_dataset

# Get player stats for Duke's last 10 games
df = get_dataset(
    "player_game",
    filters={"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]},
    limit=10
)
```

**Key Features:**
- Single function interface (`get_dataset()`) for all data
- Support for NCAA Men's, NCAA Women's, and EuroLeague
- Flexible filtering by player, team, date, season, and more
- Built-in caching for fast repeated queries
- Historical data from 2002-present (NCAA) and 2001-present (EuroLeague)

---

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip or uv package manager

### Install with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/ghadfield32/nba_prospects_mcp.git
cd nba_prospects_mcp

# Create virtual environment with uv
uv venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux

# Install the package
uv pip install -e .
```

### Install with pip

```bash
# Clone the repository
git clone https://github.com/ghadfield32/nba_prospects_mcp.git
cd nba_prospects_mcp

# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux

# Install the package
pip install -e .
```

---

## 🚀 Quick Start

### 1. Get Recent Games

```python
from cbb_data.api.datasets import get_dataset, get_recent_games

# Get yesterday + today's NCAA Men's games
df = get_recent_games("NCAA-MBB", days=2)
print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]])
```

### 2. Get Player Stats

```python
# Get Duke player stats for current season
df = get_dataset(
    "player_game",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke"],
    },
    limit=50
)
print(df[["PLAYER_NAME", "GAME_DATE", "PTS", "AST", "REB", "MIN"]])
```

### 3. Get Season Leaders

```python
# Get EuroLeague scoring leaders for 2024 season
df = get_dataset(
    "player_season",
    filters={
        "league": "EuroLeague",
        "season": "2024",
        "PerMode": "Totals"
    },
    limit=20
)
df_sorted = df.sort_values("PTS", ascending=False)
print(df_sorted[["PLAYER_NAME", "TEAM", "GP", "PTS", "AST", "REB"]])
```

### 4. Get Play-by-Play Data

```python
# Get play-by-play for a specific game
df = get_dataset(
    "pbp",
    filters={
        "league": "NCAA-MBB",
        "game_ids": ["401587082"]
    }
)
print(df[["PERIOD", "CLOCK", "PLAY_TYPE", "TEXT", "SCORE"]])
```

---

## 📚 Core Functions

### `get_dataset(grouping, filters, columns=None, limit=None)`

The main function to retrieve any basketball dataset.

**Parameters:**
- `grouping` (str): Dataset type - see [Available Datasets](#-available-datasets)
- `filters` (dict): Filter parameters - see [Filter Reference](#-filter-reference)
- `columns` (list, optional): Specific columns to return
- `limit` (int, optional): Maximum number of rows to return
- `force_fresh` (bool, optional): Bypass cache and fetch fresh data

**Returns:**
- pandas DataFrame with the requested data

**Example:**
```python
df = get_dataset(
    "schedule",
    filters={"league": "NCAA-WBB", "season": "2025", "team": ["Connecticut"]},
    columns=["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE"],
    limit=10
)
```

### `list_datasets()`

Get information about all available datasets.

**Returns:**
- List of dictionaries with dataset metadata

**Example:**
```python
from cbb_data.api.datasets import list_datasets

datasets = list_datasets()
for ds in datasets:
    print(f"{ds['id']}: {ds['description']}")
    print(f"  Leagues: {', '.join(ds['leagues'])}")
    print(f"  Filters: {', '.join(ds['supports'])}")
```

### `get_recent_games(league, days=2, teams=None, Division=None)`

Convenience function for fetching recent games without date math.

**Parameters:**
- `league` (str): League identifier ("NCAA-MBB", "NCAA-WBB", "EuroLeague")
- `days` (int): Number of days to look back (default: 2 = yesterday + today)
- `teams` (list, optional): Filter by team names
- `Division` (str, optional): NCAA division filter ("D1", "D2", "D3", "all")

**Returns:**
- pandas DataFrame with recent games

**Example:**
```python
# Get last 7 days of Duke games
df = get_recent_games("NCAA-MBB", days=7, teams=["Duke"])
```

---

## 📊 Available Datasets

All datasets use the same `get_dataset()` function with different `grouping` parameters:

### Game-Level Datasets

#### `schedule`
Game schedules and results

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** GAME_ID, GAME_DATE, HOME_TEAM, AWAY_TEAM, HOME_SCORE, AWAY_SCORE, STATUS
**Common Filters:** season, date, team, opponent, league

```python
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})
```

#### `pbp`
Play-by-play event data (requires game_ids)

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** GAME_ID, PERIOD, CLOCK, PLAY_TYPE, TEXT, SCORE
**Common Filters:** game_ids, league, quarter, team, player

```python
df = get_dataset("pbp", filters={"league": "NCAA-MBB", "game_ids": ["401587082"]})
```

#### `shots`
Shot chart data with X/Y coordinates

**Supported Leagues:** NCAA-MBB, EuroLeague
**Key Columns:** GAME_ID, LOC_X, LOC_Y, PLAYER_NAME, SHOT_MADE
**Common Filters:** game_ids, season, league, player, team

```python
df = get_dataset("shots", filters={"league": "EuroLeague", "season": "2024", "game_ids": ["1"]})
```

### Player Datasets

#### `player_game`
Per-player per-game statistics (box scores)

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** PLAYER_NAME, TEAM, GAME_ID, PTS, REB, AST, MIN, FGM, FGA
**Common Filters:** season, team, player, date, last_n_games, min_minutes

```python
df = get_dataset("player_game", filters={"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]})
```

#### `player_season`
Per-player season aggregates

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** PLAYER_NAME, SEASON, GP, PTS, REB, AST, MIN, FG_PCT
**Common Filters:** season, team, player, per_mode ("Totals" or "PerGame")

```python
df = get_dataset("player_season", filters={"league": "NCAA-WBB", "season": "2025", "PerMode": "Totals"})
```

#### `player_team_season`
Per-player per-team season stats (captures mid-season transfers)

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** PLAYER_NAME, TEAM_NAME, SEASON, GP, PTS, REB, AST
**Common Filters:** season, team, player, per_mode

```python
df = get_dataset("player_team_season", filters={"league": "EuroLeague", "season": "2024"})
```

### Team Datasets

#### `team_game`
Per-team per-game results

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** TEAM_NAME, GAME_ID, GAME_DATE, OPPONENT, HOME_AWAY, SCORE
**Common Filters:** season, team, opponent, date, home_away

```python
df = get_dataset("team_game", filters={"league": "NCAA-MBB", "season": "2025", "team": ["Kansas"]})
```

#### `team_season`
Per-team season aggregates

**Supported Leagues:** NCAA-MBB, NCAA-WBB, EuroLeague
**Key Columns:** TEAM_NAME, SEASON, GP, W, L, PTS, OPP_PTS, WIN_PCT
**Common Filters:** season, team, league

```python
df = get_dataset("team_season", filters={"league": "NCAA-WBB", "season": "2025"})
```

---

## 🔧 Filter Reference

All filters are passed as a dictionary to the `filters` parameter of `get_dataset()`.

### Required Filters

| Filter | Description | Example Values | Required For |
|--------|-------------|----------------|--------------|
| `league` | League identifier | `"NCAA-MBB"`, `"NCAA-WBB"`, `"EuroLeague"` | All datasets |
| `season` | Season year | `"2025"` (NCAA), `"2024"` (EuroLeague) | Most datasets |
| `game_ids` | Specific game IDs | `["401587082"]` | `pbp`, `shots` |

### Common Filters

| Filter | Type | Description | Example |
|--------|------|-------------|---------|
| `team` | list | Team names | `["Duke", "North Carolina"]` |
| `player` | list | Player names | `["Cooper Flagg"]` |
| `date` | dict | Date range | `{"start": "2024-11-01", "end": "2024-12-01"}` |
| `season_type` | str | Season phase | `"Regular Season"`, `"Playoffs"` |
| `home_away` | str | Game location | `"Home"`, `"Away"` |
| `limit` | int | Max rows to return | `10`, `50`, `100` |

### NCAA-Specific Filters

| Filter | Description | Example Values |
|--------|-------------|----------------|
| `conference` | Conference filter | `"ACC"`, `"Big Ten"`, `"SEC"` |
| `Division` | Division level | `"D1"`, `"D2"`, `"D3"`, `"all"` |
| `groups` | ESPN division code | `"50"` (D-I only), `"51"` (non-D-I) |

### Statistical Filters

| Filter | Description | Example Values |
|--------|-------------|----------------|
| `per_mode` / `PerMode` | Aggregation mode | `"Totals"`, `"PerGame"`, `"Per40"` |
| `last_n_games` | Recent N games | `5`, `10`, `20` |
| `min_minutes` | Minimum minutes | `10`, `20`, `30` |
| `quarter` | Specific periods | `[1, 2]` (first half only) |

### Filter Name Conventions

All filters support **both PascalCase and snake_case**:
- `per_mode` = `PerMode`
- `season_type` = `SeasonType`
- `home_away` = `HomeAway`
- `last_n_games` = `LastNGames`

Use whichever style you prefer!

### Supported Leagues

| League Code | Full Name | Historical Data | Status |
|-------------|-----------|-----------------|--------|
| `NCAA-MBB` | NCAA Men's Basketball | 2002-present | ✅ Production |
| `NCAA-WBB` | NCAA Women's Basketball | 2005-present | ✅ Production |
| `EuroLeague` | EuroLeague | 2001-present | ✅ Production |

---

## 💡 More Examples

### Example 1: Compare Two Teams

```python
from cbb_data.api.datasets import get_dataset

# Get season stats for Duke and North Carolina
df = get_dataset(
    "team_season",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke", "North Carolina"]
    }
)

print(df[["TEAM_NAME", "GP", "WIN", "LOSS", "WIN_PCT", "POINTS"]])
```

### Example 2: Find Top Scorers

```python
# Get top scorers in NCAA Women's Basketball
df = get_dataset(
    "player_season",
    filters={
        "league": "NCAA-WBB",
        "season": "2025",
        "PerMode": "Totals",
        "min_minutes": 20  # Only players with significant playing time
    }
)

# Sort by points and get top 10
top_scorers = df.sort_values("PTS", ascending=False).head(10)
print(top_scorers[["PLAYER_NAME", "TEAM", "GP", "PTS", "PPG"]])
```

### Example 3: Conference Tournament Analysis

```python
# Get all Big Ten tournament games
df = get_dataset(
    "schedule",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "season_type": "Conference Tournament",
        "conference": "Big Ten"
    }
)

print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE", "STATUS"]])
```

### Example 4: Shot Chart Analysis (EuroLeague)

```python
# Get shot data for a specific EuroLeague game
df = get_dataset(
    "shots",
    filters={
        "league": "EuroLeague",
        "season": "2024",
        "game_ids": ["1"]
    }
)

# Plot shot chart with matplotlib
import matplotlib.pyplot as plt

made_shots = df[df["SHOT_MADE"] == 1]
missed_shots = df[df["SHOT_MADE"] == 0]

plt.figure(figsize=(10, 8))
plt.scatter(made_shots["LOC_X"], made_shots["LOC_Y"], c='green', alpha=0.6, label='Made')
plt.scatter(missed_shots["LOC_X"], missed_shots["LOC_Y"], c='red', alpha=0.6, label='Missed')
plt.legend()
plt.title("Shot Chart")
plt.show()
```

### Example 5: Player Last N Games Analysis

```python
# Get Cooper Flagg's last 5 games
df = get_dataset(
    "player_game",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke"],
        "player": ["Cooper Flagg"],
        "last_n_games": 5
    }
)

print(df[["PLAYER_NAME", "GAME_DATE", "PTS", "REB", "AST", "MIN", "FG_PCT"]])

# Calculate averages
print(f"\nAverages over last 5 games:")
print(f"PPG: {df['PTS'].mean():.1f}")
print(f"RPG: {df['REB'].mean():.1f}")
print(f"APG: {df['AST'].mean():.1f}")
```

### Example 6: Export to Different Formats

```python
# Export as JSON
df_json = get_dataset(
    "schedule",
    filters={"league": "NCAA-MBB", "season": "2025"},
    as_format="json"
)

# Export as Parquet
result = get_dataset(
    "player_season",
    filters={"league": "EuroLeague", "season": "2024"},
    as_format="parquet"
)
print(f"Saved to: {result['path']}, Rows: {result['rows']}")

# Standard pandas DataFrame (default)
df = get_dataset(
    "team_game",
    filters={"league": "NCAA-WBB", "season": "2025", "team": ["Connecticut"]}
)
df.to_csv("uconn_games.csv", index=False)
```

---

## ⚡ Performance Tips

### 1. Use Caching for Repeated Queries

The library uses DuckDB caching automatically. First query may be slow, but subsequent queries are instant:

```python
# First call: 3-7 minutes (fetching from API)
df = get_dataset("schedule", filters={"league": "EuroLeague", "season": "2024"})

# Second call: <1 second (loaded from cache)
df = get_dataset("schedule", filters={"league": "EuroLeague", "season": "2024"})
```

### 2. Use `limit` Parameter

Limit results to fetch only what you need:

```python
# Fast: Only fetches 10 games
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"}, limit=10)

# Slower: Fetches all games for the season
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})
```

### 3. Filter Early

Use specific filters to reduce data fetching:

```python
# Better: Specific team and date range
df = get_dataset(
    "player_game",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke"],
        "date": {"start": "2024-11-01", "end": "2024-12-01"}
    }
)

# Slower: Fetches entire season then filters
df = get_dataset("player_game", filters={"league": "NCAA-MBB", "season": "2025"})
df = df[df["TEAM"] == "Duke"]
```

### 4. Use `force_fresh=True` for Live Data

By default, data is cached. For real-time updates during games:

```python
# Get today's games with fresh data (bypass cache)
df = get_recent_games("NCAA-MBB", days=1, force_fresh=True)
```

---

## 🔍 Troubleshooting

### "Dataset requires game_ids filter"

Some datasets require specific game IDs. First get games from schedule, then fetch detailed data:

```python
# 1. Get game IDs from schedule
schedule = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]}, limit=5)
game_ids = schedule["GAME_ID"].tolist()

# 2. Use game IDs for play-by-play
pbp = get_dataset("pbp", filters={"league": "NCAA-MBB", "game_ids": game_ids})
```

### "Invalid season format"

Seasons should be in YYYY format:

```python
# Correct
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})

# Incorrect
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2024-25"})  # Use "2025" instead
```

### Empty DataFrame Returned

Check that:
1. Season has available data (NCAA-MBB: 2002+, NCAA-WBB: 2005+, EuroLeague: 2001+)
2. Team names are spelled correctly (use common names like "Duke", "Connecticut")
3. Filters are compatible with the dataset

```python
# See all available datasets and their filters
from cbb_data.api.datasets import list_datasets
datasets = list_datasets()
for ds in datasets:
    print(f"{ds['id']}: supports {ds['supports']}")
```

### Performance Issues

If queries are slow:
1. Add `limit` parameter to reduce data fetched
2. Use more specific filters (team, date range)
3. Check internet connection (first fetch requires API calls)
4. Ensure DuckDB cache is working (check `data/basketball.duckdb` file exists)

---

## 🧪 Testing

Run the comprehensive test suite to validate all datasets:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_comprehensive_datasets.py -v

# Run with coverage
pytest tests/ --cov=src/cbb_data --cov-report=html
```

**Test Results:** 21/23 tests passing (91.3% success rate)

---

## 📚 Additional Resources

- **[PROJECT_LOG.md](PROJECT_LOG.md)**: Detailed development log, architecture decisions, and session notes
- **Architecture**: Inspired by [nba_mcp](https://github.com/ghadfield32/nba_mcp) pattern
- **Data Sources**:
  - ESPN API (NCAA Men's & Women's)
  - [EuroLeague API](https://github.com/giasemidis/euroleague_api)
  - [CBBpy](https://github.com/dcstats/cbbpy) for NCAA box scores

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional league support (FIBA, NBL, ACB, etc.)
- Enhanced entity resolution for player/team name matching
- Advanced analytics and derived statistics
- Documentation improvements

---

## 📄 License

MIT License - See LICENSE file for details

---

## 📞 Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Status**: ✅ **Production Ready**

This library provides production-ready access to NCAA (Men's & Women's) and EuroLeague basketball data with:
- ✅ 21/23 tests passing (91.3% coverage)
- ✅ Historical data: NCAA-MBB (2002+), NCAA-WBB (2005+), EuroLeague (2001+)
- ✅ DuckDB caching for 1000x+ speedup
- ✅ Flexible PascalCase & snake_case filter syntax
- ✅ Simple single-function API
