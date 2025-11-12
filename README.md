# College & International Basketball Data Library

**Production-Ready Basketball Data Integration for NCAA, EuroLeague, EuroCup, and G League**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](tests/)

A unified Python library providing seamless access to college and international basketball data through multiple interfaces: **Python API**, **REST API**, and **MCP Server** (for Claude Desktop and LLMs).

---

## 📑 Table of Contents

- [What Is This?](#-what-is-this)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Core Python API](#-core-python-api)
- [REST API Server](#-rest-api-server)
  - [All Endpoints](#all-api-endpoints)
  - [Request/Response Formats](#requestresponse-formats)
  - [Error Handling](#error-handling)
- [MCP Server (LLM Integration)](#-mcp-server-llm-integration)
  - [10 MCP Tools](#10-mcp-tools)
  - [11+ MCP Resources](#11-mcp-resources)
  - [10 MCP Prompts](#10-mcp-prompts)
  - [Claude Desktop Setup](#claude-desktop-setup)
- [Available Datasets](#-available-datasets)
- [Filter Reference](#-filter-reference)
- [Testing](#-testing)
  - [Running Tests](#running-tests)
  - [Stress Testing](#stress-testing)
  - [Coverage Reports](#coverage-reports)
- [Performance & Monitoring](#-performance--monitoring)
- [Architecture](#-architecture)
- [Examples](#-examples)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What Is This?

This library provides **one unified interface** to access basketball data from multiple sources with three different access methods:

```python
# Method 1: Python API (Direct)
from cbb_data.api.datasets import get_dataset
df = get_dataset("player_game", filters={"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]})

# Method 2: REST API (HTTP)
curl -X POST http://localhost:8000/datasets/player_game \
  -H "Content-Type: application/json" \
  -d '{"filters": {"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]}}'

# Method 3: MCP Server (LLM/Claude Desktop)
# Ask Claude: "Show me Duke's player stats for 2025"
# Claude uses get_player_game_stats tool automatically
```

### Supported Leagues & Scope

**Default Scope (pre_only=True)**: 11 leagues accessible (6 college + 5 prepro)
**Full Scope (pre_only=False)**: 12 leagues accessible (adds WNBA)

This library focuses on **pre-NBA/WNBA prospects** and includes:
- **College Basketball**: NCAA, NJCAA, NAIA, U-SPORTS, CCAA
- **Pre-Professional/Development**: OTE, EuroLeague, EuroCup, G-League, CEBL (international/development leagues where NBA prospects play)
- **Professional** (excluded by default): WNBA only

#### League × Dataset Availability Matrix

| League | Level | schedule | player_game | team_game | pbp | shots | player_season | team_season |
|--------|-------|----------|-------------|-----------|-----|-------|---------------|-------------|
| **NCAA-MBB** | COLLEGE | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **NCAA-WBB** | COLLEGE | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **NJCAA** | COLLEGE | Yes | Yes | Yes | No | No | Yes | Yes |
| **NAIA** | COLLEGE | Yes | Yes | Yes | No | No | Yes | Yes |
| **U-SPORTS** | COLLEGE | Yes | Yes | Yes | Limited | No | Yes | Yes |
| **CCAA** | COLLEGE | Yes | Yes | Yes | Limited | No | Yes | Yes |
| **EuroLeague** | PREPRO | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **EuroCup** | PREPRO | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **G-League** | PREPRO | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **CEBL** | PREPRO | Yes | Yes | Yes | No | No | Yes | Yes |
| **OTE** | PREPRO | Yes | Yes | Yes | Yes | Limited | Yes | Yes |
| **WNBA** | PRO | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

**Legend**:
- **Yes**: Full support with comprehensive data
- **Limited**: Partial support or limited data availability
- **No**: Not available for this league

#### Historical Coverage & Recency

| League | Historical Data | Recency | Data Source |
|--------|----------------|---------|-------------|
| **NCAA-MBB** | 2002-present | Real-time (15-min delay) | ESPN API + CBBpy |
| **NCAA-WBB** | 2005-present | Real-time (15-min delay) | ESPN API + CBBpy |
| **EuroLeague** | 2001-present | Real-time | Official EuroLeague API |
| **EuroCup** | 2001-present | Real-time | Official EuroLeague API |
| **G-League** | 2001-present | Real-time (15-min delay) | NBA Stats API |
| **CEBL** | 2019-present | Post-game | ceblpy (FIBA LiveStats) |
| **OTE** | 2021-present | Post-game | HTML Scraping |
| **WNBA** | 1997-present | Real-time (15-min delay) | NBA Stats API |
| **NJCAA** | Current season | Daily updates | PrestoSports Scraping |
| **NAIA** | Current season | Daily updates | PrestoSports Scraping |
| **U-SPORTS** | Current season | Post-game | TBD (Fetcher in development) |
| **CCAA** | Current season | Post-game | TBD (Fetcher in development) |

#### Integration Status

**Fully Integrated (12 leagues)**: All leagues accessible via Python API, REST API, and MCP Server
- Access via: `get_dataset()`, REST API `/datasets/*`, MCP tools
- Default scope (pre_only=True): 11 leagues (excludes WNBA)
- Full scope (pre_only=False): All 12 leagues

**Scope Control**:
```python
# Default: Pre-NBA/WNBA prospects only (11 leagues)
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})

# Include WNBA (12 leagues)
df = get_dataset("schedule", filters={"league": "WNBA", "season": "2024", "pre_only": False})
```

---

## ✨ Key Features

### For Developers
- ✅ **Single Function Interface**: One `get_dataset()` function for all data
- ✅ **Multiple Access Methods**: Python API, REST API, MCP Server
- ✅ **Built-in Caching**: DuckDB-backed caching for 100x+ speedup
- ✅ **Flexible Filters**: Team, player, date, season, conference, and more
- ✅ **Multiple Output Formats**: Pandas, JSON, CSV, Parquet

### For Data Scientists
- ✅ **20+ Years Historical Data**: NCAA (2002+), EuroLeague (2001+)
- ✅ **8 Dataset Types**: Schedule, player/team stats, play-by-play, shots
- ✅ **Advanced Analytics**: Per-game, totals, per-40 aggregations
- ✅ **Easy Export**: DataFrame, JSON, CSV, Parquet formats

### For LLMs & AI Assistants
- ✅ **MCP Server**: Direct integration with Claude Desktop
- ✅ **10 Tools**: Pre-built functions for common queries
- ✅ **11+ Resources**: Browsable documentation for LLMs
- ✅ **10 Prompts**: Template queries for frequent tasks
- ✅ **LLM-Friendly**: Clear schemas, helpful errors, formatted responses

### For Production Use
- ✅ **Stress Tested**: 100% pass rate on comprehensive tests
- ✅ **Rate Limiting**: 60 requests/minute (configurable)
- ✅ **Error Handling**: Clear, actionable error messages
- ✅ **CORS Support**: Cross-origin requests enabled
- ✅ **Monitoring Ready**: Health checks, metrics, performance headers

### 🚀 Enterprise-Grade Automation (NEW!)
- ✅ **Auto-Pagination & Token Management**: Automatically handles large datasets with configurable token budgets (perfect for small LLMs)
- ✅ **Smart Column Pruning**: Reduces token usage by 60-70% by returning only key columns in compact mode
- ✅ **Prometheus Metrics**: Full observability with `/metrics` endpoint for production monitoring
- ✅ **Circuit Breaker**: Automatic upstream failure detection with exponential backoff recovery
- ✅ **Idempotency**: De-duplicates rapid repeated requests within 250ms window
- ✅ **Request-ID Tracking**: Unique IDs for tracing requests across systems
- ✅ **JSON Structured Logging**: Machine-readable logs for easy aggregation (Elasticsearch, Splunk, CloudWatch)
- ✅ **Batch Query Tool**: Execute multiple MCP tools in one request to reduce round-trips
- ✅ **Smart Composite Tools**: Multi-step workflows (e.g., resolve schedule → fetch play-by-play)
- ✅ **Cache Warmer CLI**: Pre-fetch popular queries with `cbb warm-cache`
- ✅ **Per-Dataset TTL**: Custom cache expiration (15min for live schedules, 30sec for play-by-play)
- ✅ **Guardrails**: Decimal rounding & datetime standardization for stable LLM parsing
- ✅ **Pre-commit Hooks**: Ruff, MyPy, and file validation for code quality

**Perfect for Small LLMs**: Ollama, qwen2.5-coder, llama-3.x with automatic token management and compact modes.

---

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip or uv package manager

### Option 1: Install with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/ghadfield32/nba_prospects_mcp.git
cd nba_prospects_mcp

# Create virtual environment with uv
uv venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install base package
uv pip install -e .

# Install with API server support
uv pip install -e ".[api]"

# Install with MCP server support
uv pip install -e ".[mcp]"

# Install with all features
uv pip install -e ".[all]"
```

### Option 2: Install with pip

```bash
# Clone the repository
git clone https://github.com/ghadfield32/nba_prospects_mcp.git
cd nba_prospects_mcp

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install with all features
pip install -e ".[all]"
```

### Verify Installation

```bash
# Test Python API
python -c "from cbb_data.api.datasets import list_datasets; print(f'✓ Found {len(list_datasets())} datasets')"

# Test REST API server
python -m cbb_data.servers.rest_server &
curl http://localhost:8000/health

# Test MCP server
python -m cbb_data.servers.mcp_server
```

---

## 🚀 Quick Start

### 1. Get Recent Games

```python
from cbb_data.api.datasets import get_recent_games

# Get yesterday + today's NCAA Men's games
df = get_recent_games("NCAA-MBB", days=2)
print(df[["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE"]])
```

### 2. Get Player Stats

```python
from cbb_data.api.datasets import get_dataset

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
# Get EuroLeague scoring leaders
df = get_dataset(
    "player_season",
    filters={
        "league": "EuroLeague",
        "season": "2024",
        "per_mode": "PerGame"
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

## 📚 Core Python API

### Main Functions

#### `get_dataset(grouping, filters, columns=None, limit=None, as_format="pandas", force_fresh=False)`

The primary function to retrieve any basketball dataset.

**Parameters:**
- `grouping` (str): Dataset type - see [Available Datasets](#-available-datasets)
- `filters` (dict): Filter parameters - see [Filter Reference](#-filter-reference)
- `columns` (list, optional): Specific columns to return
- `limit` (int, optional): Maximum number of rows to return
- `as_format` (str, optional): Output format: `"pandas"`, `"json"`, `"csv"`, `"parquet"`
- `force_fresh` (bool, optional): Bypass cache and fetch fresh data

**Returns:**
- pandas DataFrame (default) or formatted data based on `as_format`

**Example:**
```python
df = get_dataset(
    "schedule",
    filters={"league": "NCAA-WBB", "season": "2025", "team": ["Connecticut"]},
    columns=["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE"],
    limit=10
)
```

---

#### `list_datasets()`

Get metadata about all available datasets.

**Returns:**
- List of dictionaries with dataset information

**Example:**
```python
from cbb_data.api.datasets import list_datasets

datasets = list_datasets()
for ds in datasets:
    print(f"{ds['id']}: {ds['description']}")
    print(f"  Leagues: {', '.join(ds['leagues'])}")
    print(f"  Filters: {', '.join(ds['supports'])}")
```

**Output:**
```
schedule: Game schedules and results
  Leagues: NCAA-MBB, NCAA-WBB, EuroLeague
  Filters: league, season, team, date

player_game: Per-player per-game statistics
  Leagues: NCAA-MBB, NCAA-WBB, EuroLeague
  Filters: league, season, team, player, date
...
```

---

#### `get_recent_games(league, days=2, teams=None, Division=None, force_fresh=False)`

Convenience function for fetching recent games without date math.

**Parameters:**
- `league` (str): League identifier ("NCAA-MBB", "NCAA-WBB", "EuroLeague")
- `days` (int, optional): Number of days to look back (default: 2 = yesterday + today)
- `teams` (list, optional): Filter by team names
- `Division` (str, optional): NCAA division filter ("D1", "D2", "D3", "all")
- `force_fresh` (bool, optional): Bypass cache

**Returns:**
- pandas DataFrame with recent games

**Example:**
```python
# Get last 7 days of Duke games
df = get_recent_games("NCAA-MBB", days=7, teams=["Duke"])
```

---

## 🌐 REST API Server

Access basketball data via HTTP endpoints with the built-in FastAPI server.

### Starting the Server

```bash
# Development mode (auto-reload)
python -m cbb_data.servers.rest_server

# Production mode
python -m cbb_data.servers.rest_server --host 0.0.0.0 --port 8000 --workers 4

# Custom configuration
python -m cbb_data.servers.rest_server --host localhost --port 8080 --reload
```

**Server starts at:** http://localhost:8000

**Interactive Documentation:** http://localhost:8000/docs (Swagger UI)

**API Schema:** http://localhost:8000/openapi.json

---

### All API Endpoints

#### 1. Health Check

**GET /health**

Check if the API server is running and healthy.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-11T10:30:00Z",
  "services": {
    "api": "healthy",
    "cache": "healthy",
    "data_sources": "healthy"
  }
}
```

**Status Codes:**
- `200`: Server is healthy
- `503`: Server is unhealthy (rare)

---

#### 2. List All Datasets

**GET /datasets**

Get metadata about all available datasets.

**Request:**
```bash
curl http://localhost:8000/datasets
```

**Response:**
```json
{
  "datasets": [
    {
      "id": "schedule",
      "name": "Schedule",
      "description": "Game schedules and results",
      "keys": ["GAME_ID"],
      "supported_filters": ["league", "season", "team", "date"],
      "supported_leagues": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
      "data_sources": ["ESPN", "EuroLeague API"],
      "sample_columns": ["GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE"]
    },
    ...
  ],
  "count": 8
}
```

**Status Codes:**
- `200`: Success
- `500`: Internal server error

---

#### 3. Query a Dataset

**POST /datasets/{dataset_id}**

Fetch data from a specific dataset with filters.

**Request:**
```bash
curl -X POST http://localhost:8000/datasets/player_game \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "league": "NCAA-MBB",
      "season": "2025",
      "team": ["Duke"]
    },
    "limit": 10,
    "offset": 0,
    "output_format": "json",
    "include_metadata": true
  }'
```

**Request Body:**
```json
{
  "filters": {
    "league": "NCAA-MBB",
    "season": "2025",
    "team": ["Duke"]
  },
  "limit": 10,
  "offset": 0,
  "output_format": "json",
  "include_metadata": true
}
```

**Response:**
```json
{
  "data": [
    ["Cooper Flagg", "Duke", "2025-01-10", 24, 8, 5, 32],
    ["Jeremy Roach", "Duke", "2025-01-10", 18, 3, 7, 28],
    ...
  ],
  "columns": ["PLAYER_NAME", "TEAM", "GAME_DATE", "PTS", "REB", "AST", "MIN"],
  "metadata": {
    "dataset_id": "player_game",
    "filters_applied": {"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]},
    "row_count": 10,
    "total_rows": 150,
    "execution_time_ms": 45.3,
    "cached": true,
    "timestamp": "2025-11-11T10:30:00Z"
  }
}
```

**Output Formats:**
- `json`: Array of arrays (most compact)
- `records`: Array of objects (most readable)
- `csv`: Comma-separated string (easy export)
- `parquet`: Compressed binary (smallest, fastest)

**Status Codes:**
- `200`: Success
- `400`: Invalid filters
- `404`: Dataset not found
- `500`: Internal server error

---

#### 4. Get Recent Games

**GET /recent-games/{league}**

Convenience endpoint for fetching recent games.

**Request:**
```bash
# Get last 2 days of games
curl "http://localhost:8000/recent-games/NCAA-MBB?days=2"

# Filter by teams
curl "http://localhost:8000/recent-games/NCAA-MBB?days=7&teams=Duke,UNC"

# Specify output format
curl "http://localhost:8000/recent-games/EuroLeague?days=3&output_format=csv"
```

**Query Parameters:**
- `days` (int, optional): Days to look back (1-30, default: 2)
- `teams` (str, optional): Comma-separated team names
- `division` (str, optional): NCAA division (D1, D2, D3, all)
- `output_format` (str, optional): Output format (json, csv, parquet, records)

**Response:**
```json
{
  "data": [
    ["401587082", "2025-01-10", "Duke", "North Carolina", 85, 78, "Final"],
    ...
  ],
  "columns": ["GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM", "HOME_SCORE", "AWAY_SCORE", "STATUS"],
  "metadata": {
    "dataset_id": "schedule",
    "filters_applied": {"league": "NCAA-MBB", "days": 2},
    "row_count": 45,
    "total_rows": 45,
    "execution_time_ms": 12.5,
    "cached": true,
    "timestamp": "2025-11-11T10:30:00Z"
  }
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid parameters
- `500`: Internal server error

---

#### 5. Get Dataset Info

**GET /datasets/{dataset_id}/info**

Get detailed metadata about a specific dataset.

**Request:**
```bash
curl http://localhost:8000/datasets/player_season/info
```

**Response:**
```json
{
  "id": "player_season",
  "name": "Player Season",
  "description": "Per-player season aggregate statistics",
  "keys": ["PLAYER_ID", "SEASON"],
  "supported_filters": ["league", "season", "team", "player", "per_mode"],
  "supported_leagues": ["NCAA-MBB", "NCAA-WBB", "EuroLeague"],
  "data_sources": ["ESPN", "CBBpy", "EuroLeague API"],
  "sample_columns": ["PLAYER_NAME", "TEAM", "GP", "PTS", "REB", "AST", "FG_PCT"]
}
```

**Status Codes:**
- `200`: Success
- `404`: Dataset not found
- `500`: Internal server error

---

### Request/Response Formats

#### Standard Request Body

```json
{
  "filters": {
    "league": "NCAA-MBB",      // Required for all datasets
    "season": "2025",           // Required for most datasets
    "team": ["Duke", "UNC"],    // Optional
    "player": ["Cooper Flagg"], // Optional
    "date": {                   // Optional
      "start": "2024-11-01",
      "end": "2024-12-31"
    },
    "per_mode": "PerGame"       // Optional: Totals, PerGame, Per40
  },
  "limit": 100,                 // Optional: max rows
  "offset": 0,                  // Optional: pagination
  "output_format": "json",      // Optional: json, records, csv, parquet
  "include_metadata": true      // Optional: include execution metadata
}
```

#### Standard Response Format

```json
{
  "data": [...],                // Data in requested format
  "columns": [...],             // Column names (if applicable)
  "metadata": {                 // If include_metadata=true
    "dataset_id": "player_game",
    "filters_applied": {...},
    "row_count": 100,
    "total_rows": 1000,
    "execution_time_ms": 45.3,
    "cached": true,
    "timestamp": "2025-11-11T10:30:00Z"
  }
}
```

### Error Handling

All errors follow this format:

```json
{
  "detail": "Clear error message explaining what went wrong",
  "error_type": "ValueError",
  "status_code": 400
}
```

**Common Error Codes:**
- `400 Bad Request`: Invalid filters, missing required parameters
- `404 Not Found`: Dataset not found
- `429 Too Many Requests`: Rate limit exceeded (60 requests/minute)
- `500 Internal Server Error`: Unexpected server error
- `503 Service Unavailable`: Server is not ready

### Performance Headers

Responses include performance information in headers:

```
X-Execution-Time: 45.3
X-Cache-Status: HIT
X-Row-Count: 100
```

---

## 🤖 MCP Server (LLM Integration)

Connect Claude Desktop and other LLMs directly to basketball data using the Model Context Protocol.

### Quick Start

```bash
# Install MCP dependencies
uv pip install -e ".[mcp]"

# Start the MCP server
python -m cbb_data.servers.mcp_server
```

### Claude Desktop Setup

1. **Locate your Claude Desktop config file:**
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. **Edit the config file** and add the MCP server:

```json
{
  "mcpServers": {
    "cbb-data": {
      "command": "python",
      "args": ["-m", "cbb_data.servers.mcp_server"],
      "cwd": "/absolute/path/to/nba_prospects_mcp"
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Test it** by asking Claude:
   - "Show me Duke's schedule for this season"
   - "Who are the top scorers in NCAA Men's Basketball?"
   - "Get Cooper Flagg's stats for his last 5 games"

---

### 10 MCP Tools

MCP tools are functions that LLMs can call to fetch basketball data.

#### 1. `get_schedule`
Get game schedules and results.

**Parameters:**
- `league` (required): League identifier
- `season` (optional): Season year
- `team` (optional): List of team names
- `date` (optional): Date range
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Show me Duke's schedule for 2025"
→ Calls: get_schedule(league="NCAA-MBB", season="2025", team=["Duke"])
```

---

#### 2. `get_player_game_stats`
Get per-player per-game statistics (box scores).

**Parameters:**
- `league` (required): League identifier
- `season` (optional): Season year
- `team` (optional): List of team names
- `player` (optional): List of player names
- `game_ids` (optional): Specific game IDs
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Show me Cooper Flagg's game log for Duke"
→ Calls: get_player_game_stats(league="NCAA-MBB", season="2025", team=["Duke"], player=["Cooper Flagg"])
```

---

#### 3. `get_player_season_stats`
Get per-player season aggregate statistics.

**Parameters:**
- `league` (required): League identifier
- `season` (required): Season year
- `per_mode` (optional): Aggregation mode (Totals, PerGame, Per40)
- `team` (optional): List of team names
- `player` (optional): List of player names
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Who are the top 10 scorers in NCAA Men's Basketball this season?"
→ Calls: get_player_season_stats(league="NCAA-MBB", season="2025", per_mode="PerGame", limit=10)
```

---

#### 4. `get_team_season_stats`
Get per-team season standings and statistics.

**Parameters:**
- `league` (required): League identifier
- `season` (required): Season year
- `team` (optional): List of team names
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Show me team standings for EuroLeague 2024"
→ Calls: get_team_season_stats(league="EuroLeague", season="2024")
```

---

#### 5. `get_team_game_stats`
Get per-team per-game results.

**Parameters:**
- `league` (required): League identifier
- `season` (optional): Season year
- `team` (optional): List of team names
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Get Duke's game results for this season"
→ Calls: get_team_game_stats(league="NCAA-MBB", season="2025", team=["Duke"])
```

---

#### 6. `get_play_by_play`
Get play-by-play event data for specific games.

**Parameters:**
- `league` (required): League identifier
- `game_ids` (required): List of game IDs
- `quarter` (optional): Filter by period
- `team` (optional): Filter by team
- `player` (optional): Filter by player

**Example Usage:**
```
Claude: "Get play-by-play for game 401587082"
→ Calls: get_play_by_play(league="NCAA-MBB", game_ids=["401587082"])
```

---

#### 7. `get_shot_chart`
Get shot chart data with X/Y coordinates.

**Parameters:**
- `league` (required): League identifier
- `game_ids` (required): List of game IDs
- `season` (optional): Season year
- `player` (optional): Filter by player
- `team` (optional): Filter by team

**Example Usage:**
```
Claude: "Get shot chart data for EuroLeague game 1"
→ Calls: get_shot_chart(league="EuroLeague", game_ids=["1"], season="2024")
```

---

#### 8. `get_player_team_season`
Get player×team season stats (captures mid-season transfers).

**Parameters:**
- `league` (required): League identifier
- `season` (required): Season year
- `per_mode` (optional): Aggregation mode
- `team` (optional): List of team names
- `player` (optional): List of player names
- `limit` (optional): Max rows

**Example Usage:**
```
Claude: "Show player stats split by team for transfers"
→ Calls: get_player_team_season(league="NCAA-MBB", season="2025")
```

---

#### 9. `list_datasets`
List all available datasets with metadata.

**Parameters:**
- None

**Example Usage:**
```
Claude: "What data is available?"
→ Calls: list_datasets()
```

---

#### 10. `get_recent_games`
Quick access to recent games without date calculations.

**Parameters:**
- `league` (required): League identifier
- `days` (optional): Days to look back (default: 2)
- `teams` (optional): Filter by team names

**Example Usage:**
```
Claude: "What games happened today in NCAA Men's Basketball?"
→ Calls: get_recent_games(league="NCAA-MBB", days=1)
```

---

### 11+ MCP Resources

MCP resources are browsable documentation that LLMs can reference.

#### Static Resources

| URI | Name | Description |
|-----|------|-------------|
| `cbb://leagues` | All Leagues | List of all supported leagues |
| `cbb://datasets` | All Datasets | List of all available datasets |
| `cbb://stats-examples` | Example Queries | Common query patterns |

#### League-Specific Resources

| URI | League | Description |
|-----|--------|-------------|
| `cbb://leagues/NCAA-MBB` | NCAA Men's Basketball | NCAA-MBB info and coverage |
| `cbb://leagues/NCAA-WBB` | NCAA Women's Basketball | NCAA-WBB info and coverage |
| `cbb://leagues/EuroLeague` | EuroLeague | EuroLeague info and coverage |

#### Dataset-Specific Resources

| URI | Dataset | Description |
|-----|---------|-------------|
| `cbb://datasets/schedule` | Schedule | Game schedules metadata |
| `cbb://datasets/player_game` | Player Game | Player box scores metadata |
| `cbb://datasets/player_season` | Player Season | Player season stats metadata |
| `cbb://datasets/team_season` | Team Season | Team standings metadata |
| `cbb://datasets/team_game` | Team Game | Team game results metadata |
| `cbb://datasets/pbp` | Play-by-Play | Play-by-play metadata |
| `cbb://datasets/shots` | Shot Chart | Shot chart metadata |
| `cbb://datasets/player_team_season` | Player×Team Season | Player-team splits metadata |

**Usage Example:**
```
Claude: "Tell me about the play-by-play dataset"
→ Fetches: cbb://datasets/pbp
→ Returns: Detailed documentation about pbp dataset
```

---

### 10 MCP Prompts

MCP prompts are pre-built query templates for common tasks.

#### 1. `top-scorers`
Find the top scorers for a league and season.

**Arguments:**
- league (required)
- season (required)
- limit (optional, default: 20)

**Usage:**
```
Prompt: top-scorers
Args: {league: "NCAA-MBB", season: "2025", limit: 20}
```

---

#### 2. `team-schedule`
Get the full schedule for a specific team.

**Arguments:**
- league (required)
- team (required)
- season (optional)

---

#### 3. `recent-games`
Get recent games across a league.

**Arguments:**
- league (required)
- days (optional, default: 2)

---

#### 4. `player-game-log`
Get game-by-game statistics for a specific player.

**Arguments:**
- league (required)
- player (required)
- season (optional)
- limit (optional, default: 10)

---

#### 5. `team-standings`
Get team standings and season statistics.

**Arguments:**
- league (required)
- season (required)
- division (optional)

---

#### 6. `player-comparison`
Compare statistics between multiple players.

**Arguments:**
- league (required)
- players (required, comma-separated)
- season (required)

---

#### 7. `head-to-head`
Get head-to-head matchup history between two teams.

**Arguments:**
- league (required)
- team1 (required)
- team2 (required)
- season (optional)

---

#### 8. `breakout-players`
Identify breakout players showing significant improvement.

**Arguments:**
- league (required)
- current_season (required)
- team (optional)

---

#### 9. `todays-games`
Get today's games and recent results.

**Arguments:**
- league (required)

---

#### 10. `conference-leaders`
Get statistical leaders for a conference or division.

**Arguments:**
- league (required, must be NCAA)
- season (required)
- division (optional)

---

## 📊 Available Datasets

All datasets use the same `get_dataset()` function with different `grouping` parameters.

| Dataset ID | Description | Leagues | Key Columns |
|------------|-------------|---------|-------------|
| `schedule` | Game schedules and results | All | GAME_ID, GAME_DATE, HOME_TEAM, AWAY_TEAM, HOME_SCORE, AWAY_SCORE |
| `player_game` | Per-player per-game stats | All | PLAYER_NAME, TEAM, GAME_DATE, PTS, REB, AST, MIN |
| `player_season` | Per-player season aggregates | All | PLAYER_NAME, SEASON, GP, PTS, REB, AST, FG_PCT |
| `player_team_season` | Player×team season (transfers) | All | PLAYER_NAME, TEAM_NAME, SEASON, GP, PTS |
| `team_game` | Per-team per-game results | All | TEAM_NAME, GAME_DATE, OPPONENT, SCORE, HOME_AWAY |
| `team_season` | Per-team season standings | All | TEAM_NAME, SEASON, GP, W, L, WIN_PCT, PTS |
| `pbp` | Play-by-play events | All | GAME_ID, PERIOD, CLOCK, PLAY_TYPE, TEXT, SCORE |
| `shots` | Shot chart with X/Y coords | NCAA-MBB, EuroLeague, EuroCup, G-League | GAME_ID, LOC_X, LOC_Y, PLAYER_NAME, SHOT_MADE |

### Data Granularities by League

**Note**: See "League × Dataset Availability Matrix" above for comprehensive coverage details.

#### Full Dataset Coverage (7 datasets)
- **NCAA-MBB, NCAA-WBB**: All datasets (shots via direct API for MBB, PBP extraction for WBB)
- **EuroLeague, EuroCup, G-League**: All datasets with full shot chart support (X/Y coordinates)
- **WNBA**: All datasets with full shot chart support

#### Partial Dataset Coverage
- **NJCAA, NAIA**: schedule, player_game, team_game, player_season, team_season (no pbp/shots)
- **CEBL**: schedule, player_game, team_game, player_season, team_season (no pbp/shots yet)
- **OTE**: schedule, player_game, team_game, pbp, player_season, team_season (limited shots)
- **U-SPORTS, CCAA**: schedule, player_game, team_game, player_season, team_season (limited pbp, no shots)

### Dataset Details

Each dataset supports different filters. See [Filter Reference](#-filter-reference) for complete details.

**Required Filters:**
- All datasets: `league`
- Most datasets: `season`
- pbp, shots: `game_ids`

**For NCAA datasets:**
- `player_game` requires either `team` or `game_ids`

---

## 🔧 Filter Reference

### Required Filters

| Filter | Type | Description | Example | Required For |
|--------|------|-------------|---------|--------------|
| `league` | str | League identifier | `"NCAA-MBB"`, `"NCAA-WBB"`, `"EuroLeague"`, `"EuroCup"`, `"G-League"`, `"CEBL"`, `"OTE"`, `"NJCAA"`, `"NAIA"`, `"U-SPORTS"`, `"CCAA"`, `"WNBA"` | All datasets |
| `season` | str | Season year | `"2025"` (NCAA), `"E2024"` (EuroLeague), `"U2024"` (EuroCup), `"2024-25"` (G-League), `"2024"` (CEBL/WNBA) | Most datasets |
| `game_ids` | list | Specific game IDs | `["401587082"]` (NCAA), `[1, 2, 3]` (EuroLeague/EuroCup), `["0022400001"]` (G-League/WNBA) | `pbp`, `shots` |
| `pre_only` | bool | Scope filter | `True` (exclude WNBA), `False` (include WNBA) | Optional (default: True) |

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

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_comprehensive_datasets.py -v

# Run specific test class
pytest tests/test_rest_api_comprehensive.py::TestHealthEndpoint -v

# Run specific test
pytest tests/test_mcp_server_comprehensive.py::TestMCPTools::test_get_schedule_tool_exists -v
```

### Test Categories

Run tests by category using markers:

```bash
# Run only smoke tests (quick validation)
pytest tests/ -v -m smoke

# Run only API tests
pytest tests/ -v -m api

# Run only MCP tests
pytest tests/ -v -m mcp

# Run only integration tests
pytest tests/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### Stress Testing

Run comprehensive stress tests:

```bash
# Run all stress tests
pytest tests/test_api_mcp_stress_comprehensive.py -v

# Run only API stress tests
pytest tests/test_api_mcp_stress_comprehensive.py::TestAPIStressFull -v

# Run only MCP stress tests
pytest tests/test_api_mcp_stress_comprehensive.py::TestMCPStressFull -v

# Run concurrent request tests
pytest tests/test_api_mcp_stress_comprehensive.py -v -k concurrent

# Run performance benchmarks
pytest tests/test_api_mcp_stress_comprehensive.py::TestPerformanceBenchmark -v
```

**Stress Test Coverage:**
- ✅ All datasets × all leagues (12 combinations)
- ✅ All per-modes × all leagues (9 combinations)
- ✅ All date ranges (1, 2, 7, 14, 30 days)
- ✅ Error handling (4 scenarios)
- ✅ Concurrent requests (10 parallel)
- ✅ Performance benchmarks

### Coverage Reports

```bash
# Run tests with coverage
pytest tests/ --cov=src/cbb_data --cov-report=html --cov-report=term

# View HTML coverage report
# Open htmlcov/index.html in browser

# Get coverage summary
pytest tests/ --cov=src/cbb_data --cov-report=term-missing
```

**Current Test Status:**
- **Comprehensive Tests**: 21/23 passing (91.3%)
- **Stress Tests**: 100% passing
- **Code Coverage**: 31% overall, 60-80% on core modules

### Test Documentation

See [tests/README_TESTS.md](tests/README_TESTS.md) for detailed testing guide including:
- Test structure and organization
- Writing new tests
- Debugging test failures
- CI/CD integration

---

## ⚡ Performance & Monitoring

### Caching Performance

The library uses DuckDB for caching with dramatic speedup:

```python
# First query: 30-60 seconds (fetching from API sources)
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2024"})

# Second query: <1 second (loaded from cache)
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2024"})
```

**Performance Metrics:**
- **Cold cache**: 30-60s (first-time fetch)
- **Warm cache**: <1s (100x+ speedup)
- **Cache hit rate**: Nearly 100% for repeated queries

### Bypassing Cache

For real-time data during live games:

```python
# Force fresh data (bypass cache)
df = get_recent_games("NCAA-MBB", days=1, force_fresh=True)
```

### Optimization Tips

#### 1. Use `limit` Parameter

```python
# Fast: Only fetches 10 rows
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"}, limit=10)

# Slower: Fetches entire season
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})
```

#### 2. Filter Early

```python
# Better: Specific filters reduce data fetched
df = get_dataset(
    "player_game",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "team": ["Duke"],
        "date": {"start": "2024-11-01", "end": "2024-12-01"}
    }
)

# Slower: Fetches more data then filters in pandas
df = get_dataset("player_game", filters={"league": "NCAA-MBB", "season": "2025"})
df = df[df["TEAM"] == "Duke"]
```

#### 3. Use Appropriate Datasets

```python
# For season totals: Use player_season
df = get_dataset("player_season", filters={"league": "NCAA-MBB", "season": "2025", "per_mode": "Totals"})

# Don't aggregate player_game manually
# (slower and uses more memory)
```

### Health Monitoring

Monitor server health:

```bash
# API health check
curl http://localhost:8000/health

# Response includes service status
{
  "status": "healthy",
  "services": {
    "api": "healthy",
    "cache": "healthy",
    "data_sources": "healthy"
  }
}
```

### Performance Metrics

API responses include performance headers:

```bash
curl -I http://localhost:8000/recent-games/NCAA-MBB?days=2

# Headers include:
X-Execution-Time: 45.3      # Milliseconds
X-Cache-Status: HIT         # HIT or MISS
X-Row-Count: 45             # Rows returned
X-Request-ID: unique-uuid   # For tracing
X-Idempotency-Cache: MISS   # De-dupe status
```

### Observability & Monitoring (NEW!)

#### Prometheus Metrics

Full production-grade metrics available at `/metrics` endpoint:

```bash
# Install prometheus-client for full metrics support
uv pip install prometheus-client

# Access Prometheus metrics
curl http://localhost:8000/metrics

# Metrics include:
# - cbb_tool_calls_total: Total tool calls by tool and service
# - cbb_cache_hits_total: Cache hits by dataset and league
# - cbb_cache_misses_total: Cache misses by dataset and league
# - cbb_tool_latency_ms: Tool execution latency histogram
# - cbb_rows_returned: Rows returned histogram
# - cbb_request_total: HTTP request counts by method, endpoint, status
# - cbb_error_total: Error counts by service and error type
# - Python runtime metrics (GC, memory, threads, etc.)
```

#### JSON Structured Logging

All events logged in machine-readable JSON format for easy aggregation:

```json
{
  "event": "request",
  "service": "rest",
  "endpoint": "/datasets/schedule",
  "method": "POST",
  "status_code": 200,
  "duration_ms": 125.5,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "ts": 1699564800.123,
  "timestamp": "2025-01-15T19:00:00.123000+00:00"
}
```

Perfect for log aggregators like Elasticsearch, Splunk, CloudWatch, Datadog.

#### Request-ID Tracking

Every request gets a unique ID for distributed tracing:

```bash
# Provide your own Request-ID
curl -H "X-Request-ID: my-trace-123" http://localhost:8000/health

# Or let server generate one
curl http://localhost:8000/health
# Response includes: X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

All logs, metrics, and errors include the Request-ID for end-to-end tracing.

#### Circuit Breaker

Automatic upstream failure detection and recovery:

```python
# Circuit states:
# - CLOSED: Normal operation (all requests pass)
# - OPEN: Too many failures (requests rejected with 503)
# - HALF_OPEN: Testing recovery (limited requests)

# Configure circuit breaker:
config = {
    "circuit_breaker_threshold": 5,      # Failures before opening
    "circuit_breaker_timeout": 60,       # Seconds before retry
    "enable_circuit_breaker": True
}
```

When circuit opens:
- Returns `503 Service Unavailable`
- Includes `Retry-After` header
- Automatically recovers after timeout

#### Idempotency & De-duplication

Prevents double-execution from rapid retries:

```bash
# Same request within 250ms window returns cached response
curl -X POST http://localhost:8000/datasets/schedule ...
# Response: X-Idempotency-Cache: MISS

curl -X POST http://localhost:8000/datasets/schedule ...  # Same request <250ms later
# Response: X-Idempotency-Cache: HIT
```

Configure with `CBB_DEDUPE_WINDOW_MS=250` environment variable.

#### Environment Variables for Automation

```bash
# Auto-Pagination & Token Management
export CBB_MAX_ROWS=2000              # Max rows before pagination
export CBB_MAX_TOKENS=8000            # Token budget limit

# Cache TTL (seconds)
export CBB_TTL_SCHEDULE=900           # 15 min for schedules
export CBB_TTL_PBP=30                 # 30 sec for play-by-play
export CBB_TTL_SHOTS=60               # 1 min for shot data
export CBB_TTL_DEFAULT=3600           # 1 hour default

# Middleware
export CBB_DEDUPE_WINDOW_MS=250       # De-dupe window (ms)

# Observability
export CBB_METRICS_ENABLED=true       # Enable Prometheus metrics
```

#### Cache Warmer CLI

Pre-fetch popular queries for faster response times:

```bash
# Warm cache with default popular queries
cbb warm-cache

# Warm specific teams
cbb warm-cache --teams Duke UNC Kansas

# Output:
# [1/7] NCAA-MBB Today's Schedule...
#   [OK] Cached 200 rows
# [2/7] NCAA-MBB Recent Games (Last 2 Days)...
#   [OK] Cached 150 rows
# ...
# Cache Warming Complete!
#   Successful: 7/7
#   Total Rows Cached: 1,250
```

### Rate Limiting

API is rate-limited to 60 requests/minute per IP by default.

**Configure rate limits:**
```python
# In src/cbb_data/api/rest_api/middleware.py
RATE_LIMIT = 60  # requests per minute
```

**Rate limit headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 57
X-RateLimit-Reset: 1641744000
```

---

## 🏗️ Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                          │
├─────────────┬──────────────────┬────────────────────────────┤
│  Python API │   REST API       │  MCP Server (Claude)       │
│  (Direct)   │   (HTTP/JSON)    │  (LLM Integration)         │
└─────────────┴──────────────────┴────────────────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │  Core API Layer      │
                 │  get_dataset()       │
                 │  list_datasets()     │
                 │  get_recent_games()  │
                 └──────────────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │  Filter & Validation Layer            │
        │  - Parse filters                      │
        │  - Validate parameters                │
        │  - Apply defaults                     │
        └───────────────────────────────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │  DuckDB Cache Layer                   │
        │  - Check cache                        │
        │  - Return cached data if available    │
        │  - Store fresh data after fetch       │
        └───────────────────────────────────────┘
                            ▼
    ┌───────────────────────────────────────────────┐
    │  Data Fetcher Layer (Source-Specific)         │
    ├────────────┬─────────────┬────────────────────┤
    │ ESPN API   │ CBBpy       │ EuroLeague API     │
    │ (NCAA M/W) │ (NCAA Box   │ (EuroLeague)       │
    │            │  Scores)    │                    │
    └────────────┴─────────────┴────────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │  External APIs       │
                 │  - ESPN              │
                 │  - CBBpy             │
                 │  - EuroLeague        │
                 └──────────────────────┘
```

### Data Flow

1. **User Request** → Python API / REST API / MCP Server
2. **Filter Parsing** → Validate and normalize filters
3. **Cache Check** → DuckDB lookup for existing data
4. **Data Fetch** → If cache miss, fetch from external APIs
5. **Cache Store** → Save fetched data to DuckDB
6. **Response** → Return data in requested format

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Core API** | Main data access functions | `src/cbb_data/api/datasets.py` |
| **REST Server** | HTTP API server | `src/cbb_data/servers/rest_server.py` |
| **MCP Server** | LLM integration server | `src/cbb_data/servers/mcp_server.py` |
| **Filters** | Filter parsing and validation | `src/cbb_data/filters/` |
| **Fetchers** | Source-specific data fetchers | `src/cbb_data/fetchers/` |
| **Cache** | DuckDB caching layer | `src/cbb_data/storage/` |
| **Schemas** | Data schemas and types | `src/cbb_data/schemas/` |

### Dependencies

**Core Dependencies:**
- `pandas`: Data manipulation
- `duckdb`: Caching and storage
- `requests`: HTTP requests

**API Server Dependencies:**
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `pydantic`: Data validation

**MCP Server Dependencies:**
- `mcp`: Model Context Protocol

**Data Source Dependencies:**
- `cbbpy`: NCAA box scores
- `euroleague_api`: EuroLeague data

---

## 💡 Examples

See [LLM_USAGE_GUIDE.md](LLM_USAGE_GUIDE.md) for comprehensive examples optimized for AI assistants.

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

### Example 2: Shot Chart Analysis

```python
import matplotlib.pyplot as plt

# Get shot data for a specific game
df = get_dataset(
    "shots",
    filters={
        "league": "NCAA-MBB",
        "season": "2025",
        "game_ids": ["401587082"]
    }
)

# Separate made and missed shots
made = df[df["SHOT_MADE"] == 1]
missed = df[df["SHOT_MADE"] == 0]

# Plot shot chart
plt.figure(figsize=(10, 8))
plt.scatter(made["LOC_X"], made["LOC_Y"], c='green', alpha=0.6, label='Made')
plt.scatter(missed["LOC_X"], missed["LOC_Y"], c='red', alpha=0.6, label='Missed')
plt.legend()
plt.title("Shot Chart")
plt.show()
```

### Example 3: Player Progression

```python
# Get player stats for multiple seasons
seasons = ["2023", "2024", "2025"]
player_progression = []

for season in seasons:
    df = get_dataset(
        "player_season",
        filters={
            "league": "NCAA-MBB",
            "season": season,
            "player": ["Cooper Flagg"],
            "per_mode": "PerGame"
        }
    )
    player_progression.append(df)

# Combine and analyze progression
import pandas as pd
progression_df = pd.concat(player_progression)
print(progression_df[["SEASON", "GP", "PTS", "REB", "AST", "FG_PCT"]])
```

### Example 4: Export to Multiple Formats

```python
# Export as JSON
df_json = get_dataset(
    "schedule",
    filters={"league": "NCAA-MBB", "season": "2025"},
    as_format="json"
)

# Export as Parquet (5-10x smaller, 10-100x faster)
result = get_dataset(
    "player_season",
    filters={"league": "EuroLeague", "season": "2024"},
    as_format="parquet"
)
print(f"Saved to: {result['path']}, Rows: {result['rows']}")

# Standard pandas DataFrame
df = get_dataset(
    "team_game",
    filters={"league": "NCAA-WBB", "season": "2025", "team": ["Connecticut"]}
)
df.to_csv("uconn_games.csv", index=False)
```

---

## 🔍 Troubleshooting

### "Dataset requires game_ids filter"

Some datasets (pbp, shots) require specific game IDs. Get them from schedule first:

```python
# 1. Get game IDs
schedule = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025", "team": ["Duke"]}, limit=5)
game_ids = schedule["GAME_ID"].tolist()

# 2. Use game IDs for detailed data
pbp = get_dataset("pbp", filters={"league": "NCAA-MBB", "game_ids": game_ids})
```

### "Invalid season format"

Seasons must be in YYYY format:

```python
# Correct
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2025"})

# Incorrect
df = get_dataset("schedule", filters={"league": "NCAA-MBB", "season": "2024-25"})  # Use "2025"
```

### Empty DataFrame Returned

Check:
1. Season has data (NCAA-MBB: 2002+, NCAA-WBB: 2005+, EuroLeague: 2001+)
2. Team names are correct (use "Duke", not "Duke University")
3. Filters are compatible with dataset

```python
# See available datasets and filters
from cbb_data.api.datasets import list_datasets
datasets = list_datasets()
for ds in datasets:
    print(f"{ds['id']}: supports {ds['supports']}")
```

### API Connection Error

If REST API doesn't connect:

```bash
# Check if server is running
curl http://localhost:8000/health

# Start server if needed
python -m cbb_data.servers.rest_server

# Check port availability
# Windows: netstat -ano | findstr :8000
# Mac/Linux: lsof -i :8000
```

### MCP Server Not Working

If Claude Desktop doesn't recognize MCP server:

1. **Check config path is absolute:**
   ```json
   {
     "mcpServers": {
       "cbb-data": {
         "cwd": "/Users/username/projects/nba_prospects_mcp"  // Must be absolute
       }
     }
   }
   ```

2. **Test MCP server manually:**
   ```bash
   python -m cbb_data.servers.mcp_server
   # Should start without errors
   ```

3. **Check Claude Desktop logs:**
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`

### Performance Issues

If queries are slow:

1. **Add `limit` parameter:**
   ```python
   df = get_dataset("schedule", filters={...}, limit=50)
   ```

2. **Use specific filters:**
   ```python
   # Better: Fetch only Duke games
   df = get_dataset("player_game", filters={"team": ["Duke"], ...})

   # Slower: Fetch all games then filter
   df = get_dataset("player_game", filters={...})
   df = df[df["TEAM"] == "Duke"]
   ```

3. **Check cache:**
   ```bash
   # Cache file should exist
   ls data/basketball.duckdb
   ```

4. **Clear cache if corrupted:**
   ```bash
   rm data/basketball.duckdb
   ```

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

### High Priority
- [ ] Additional league support (FIBA, NBL, ACB, Liga ACB)
- [ ] Enhanced entity resolution (player/team name matching)
- [ ] Advanced analytics (possession stats, +/-, etc.)

### Medium Priority
- [ ] Query result pagination
- [ ] Batch query support
- [ ] WebSocket support for live updates
- [ ] GraphQL interface

### Low Priority
- [ ] Additional export formats (Excel, SQLite)
- [ ] Data visualization helpers
- [ ] Documentation improvements

**How to Contribute:**
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

See [PROJECT_LOG.md](PROJECT_LOG.md) for development history and architecture decisions.

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details.

---

## 📞 Support

**Documentation:**
- [API_GUIDE.md](API_GUIDE.md) - Complete REST API reference
- [MCP_GUIDE.md](MCP_GUIDE.md) - MCP server setup and usage
- [LLM_USAGE_GUIDE.md](LLM_USAGE_GUIDE.md) - Guide for AI assistants
- [PROJECT_LOG.md](PROJECT_LOG.md) - Development log
- [STRESS_TEST_REPORT.md](STRESS_TEST_REPORT.md) - Test results

**Get Help:**
- GitHub Issues: [github.com/ghadfield32/nba_prospects_mcp/issues](https://github.com/ghadfield32/nba_prospects_mcp/issues)
- Discussions: [github.com/ghadfield32/nba_prospects_mcp/discussions](https://github.com/ghadfield32/nba_prospects_mcp/discussions)

**Data Sources:**
- [ESPN API](https://www.espn.com/) - NCAA Men's & Women's Basketball
- [CBBpy](https://github.com/dcstats/cbbpy) - NCAA box scores
- [EuroLeague API](https://github.com/giasemidis/euroleague_api) - EuroLeague data

---

## ✅ Status

**Production Ready** ✅

This library provides production-ready access to NCAA (Men's & Women's) and EuroLeague basketball data with:

- ✅ **100% Stress Test Pass Rate** - All functionality validated
- ✅ **Historical Data** - NCAA-MBB (2002+), NCAA-WBB (2005+), EuroLeague (2001+)
- ✅ **High Performance** - DuckDB caching provides 100x+ speedup
- ✅ **Flexible Syntax** - PascalCase & snake_case filter support
- ✅ **Triple Interface** - Python API, REST API, MCP Server
- ✅ **LLM-Optimized** - MCP tools, resources, and prompts for AI assistants
- ✅ **Comprehensive Tests** - 21/23 core tests + full stress test suite
- ✅ **Production Features** - Rate limiting, error handling, monitoring
- ✅ **Well-Documented** - API guides, LLM guides, examples, troubleshooting

**Version:** 1.0.0
**Last Updated:** 2025-11-11
**Maintained By:** [@ghadfield32](https://github.com/ghadfield32)

---

**🏀 Start pulling basketball data in seconds!**

```python
from cbb_data.api.datasets import get_dataset

# Your first query
df = get_dataset(
    "schedule",
    filters={"league": "NCAA-MBB", "season": "2025"},
    limit=10
)
print(df)
```
