#!/usr/bin/env python
"""DuckDB Setup for Player Career Data (Phase 6)

Sets up DuckDB database from parquet files and creates:
1. Views for game indexes, canonical data, and gold career table
2. Sample career stitching queries
3. Multi-league player analytics

DuckDB enables:
- Fast SQL queries over parquet without loading into memory
- Efficient aggregations for career stats
- Easy integration with Python for analysis

Usage:
    python scripts/setup_duckdb.py
    python scripts/setup_duckdb.py --query "SELECT * FROM gold_career LIMIT 10"
"""

import argparse
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb not installed. Install with: pip install duckdb")
    sys.exit(1)

# Constants
DATA_DIR = Path("data")
GOLD_DIR = DATA_DIR / "gold"
CANONICAL_DIR = DATA_DIR / "canonical"
DB_PATH = DATA_DIR / "basketball.duckdb"


def setup_database() -> duckdb.DuckDBPyConnection:
    """Setup DuckDB database with views over parquet files."""

    # Create/connect to persistent database
    conn = duckdb.connect(str(DB_PATH))

    print(f"Connected to DuckDB: {DB_PATH}")

    # Create view for gold career table
    gold_path = GOLD_DIR / "player_career_game.parquet"
    if gold_path.exists():
        conn.execute(f"""
            CREATE OR REPLACE VIEW gold_career AS
            SELECT * FROM read_parquet('{gold_path.as_posix()}')
        """)
        print("Created view: gold_career")

    # Create view for player crosswalk
    xwalk_path = DATA_DIR / "player_xwalk.parquet"
    if xwalk_path.exists():
        conn.execute(f"""
            CREATE OR REPLACE VIEW player_xwalk AS
            SELECT * FROM read_parquet('{xwalk_path.as_posix()}')
        """)
        print("Created view: player_xwalk")

    # Create view for canonical players
    players_path = DATA_DIR / "canonical_players.parquet"
    if players_path.exists():
        conn.execute(f"""
            CREATE OR REPLACE VIEW canonical_players AS
            SELECT * FROM read_parquet('{players_path.as_posix()}')
        """)
        print("Created view: canonical_players")

    # Create view for all game indexes
    game_index_pattern = DATA_DIR / "game_indexes" / "*.csv"
    conn.execute(f"""
        CREATE OR REPLACE VIEW game_indexes AS
        SELECT * FROM read_csv_auto('{game_index_pattern.as_posix()}',
                                     header=true,
                                     union_by_name=true)
    """)
    print("Created view: game_indexes")

    return conn


def run_sample_queries(conn: duckdb.DuckDBPyConnection) -> None:
    """Run sample queries to demonstrate capabilities."""

    print("\n" + "=" * 70)
    print("SAMPLE QUERIES")
    print("=" * 70)

    # Query 1: Overview stats
    print("\n--- Gold Career Table Overview ---")
    result = conn.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT CANONICAL_PLAYER_ID) as unique_players,
            COUNT(DISTINCT LEAGUE) as leagues,
            COUNT(DISTINCT SEASON) as seasons,
            MIN(GAME_DATE) as first_game,
            MAX(GAME_DATE) as last_game
        FROM gold_career
    """).fetchdf()
    print(result.to_string(index=False))

    # Query 2: Records by league
    print("\n--- Records by League ---")
    result = conn.execute("""
        SELECT
            LEAGUE,
            COUNT(*) as records,
            COUNT(DISTINCT CANONICAL_PLAYER_ID) as players,
            COUNT(DISTINCT SEASON) as seasons
        FROM gold_career
        GROUP BY LEAGUE
        ORDER BY records DESC
    """).fetchdf()
    print(result.to_string(index=False))

    # Query 3: Top players by game count
    print("\n--- Top 10 Players by Games Played ---")
    result = conn.execute("""
        SELECT
            CANONICAL_PLAYER_ID,
            COALESCE(PLAYER_NAME_RAW, 'Unknown') as player_name,
            COUNT(DISTINCT GAME_ID) as games,
            COUNT(DISTINCT SEASON) as seasons,
            MIN(GAME_DATE) as first_game,
            MAX(GAME_DATE) as last_game
        FROM gold_career
        GROUP BY CANONICAL_PLAYER_ID, PLAYER_NAME_RAW
        ORDER BY games DESC
        LIMIT 10
    """).fetchdf()
    print(result.to_string(index=False))

    # Query 4: Game indexes summary
    print("\n--- Game Index Summary ---")
    result = conn.execute("""
        SELECT
            LEAGUE,
            COUNT(*) as games,
            COUNT(DISTINCT SEASON) as seasons,
            SUM(CASE WHEN GAME_DATE IS NOT NULL THEN 1 ELSE 0 END) as with_date,
            SUM(CASE WHEN HOME_SCORE IS NOT NULL THEN 1 ELSE 0 END) as with_score
        FROM game_indexes
        GROUP BY LEAGUE
        ORDER BY games DESC
    """).fetchdf()
    print(result.to_string(index=False))

    print("\n" + "=" * 70)


def career_stitching_demo(conn: duckdb.DuckDBPyConnection) -> None:
    """Demonstrate career stitching capabilities."""

    print("\n" + "=" * 70)
    print("CAREER STITCHING DEMO")
    print("=" * 70)

    # Find players who played in multiple leagues (when we have that data)
    print("\n--- Multi-League Career Query Template ---")
    print("""
    -- Query to find players with careers across multiple leagues:
    SELECT
        CANONICAL_PLAYER_ID,
        PLAYER_NAME_RAW,
        STRING_AGG(DISTINCT LEAGUE, ' -> ' ORDER BY MIN_DATE) as career_path,
        COUNT(DISTINCT LEAGUE) as league_count,
        SUM(games) as total_games
    FROM (
        SELECT
            CANONICAL_PLAYER_ID,
            PLAYER_NAME_RAW,
            LEAGUE,
            COUNT(*) as games,
            MIN(GAME_DATE) as MIN_DATE
        FROM gold_career
        GROUP BY CANONICAL_PLAYER_ID, PLAYER_NAME_RAW, LEAGUE
    ) player_leagues
    GROUP BY CANONICAL_PLAYER_ID, PLAYER_NAME_RAW
    HAVING COUNT(DISTINCT LEAGUE) > 1
    ORDER BY league_count DESC, total_games DESC
    """)

    # Example career timeline query
    print("\n--- Career Timeline Query Template ---")
    print("""
    -- Get complete career timeline for a player:
    SELECT
        GAME_DATE,
        LEAGUE,
        SEASON,
        TEAM_KEY,
        -- Add stat columns here
        PTS, REB, AST
    FROM gold_career
    WHERE CANONICAL_PLAYER_ID = '<player_id>'
    ORDER BY GAME_DATE
    """)


def main():
    parser = argparse.ArgumentParser(description="Setup DuckDB for basketball data")
    parser.add_argument("--query", help="Run a custom SQL query")
    parser.add_argument("--no-samples", action="store_true", help="Skip sample queries")
    args = parser.parse_args()

    print("=" * 70)
    print("DUCKDB SETUP FOR PLAYER CAREER DATA (Phase 6)")
    print("=" * 70)
    print()

    # Setup database
    conn = setup_database()

    # Run custom query if provided
    if args.query:
        print("\n--- Custom Query ---")
        print(f"SQL: {args.query}")
        try:
            result = conn.execute(args.query).fetchdf()
            print(result.to_string(index=False))
        except Exception as e:
            print(f"ERROR: {e}")

    # Run sample queries
    if not args.no_samples:
        run_sample_queries(conn)
        career_stitching_demo(conn)

    # Print usage info
    print("\n" + "=" * 70)
    print("USAGE")
    print("=" * 70)
    print(f"""
Database saved to: {DB_PATH}

To use in Python:
    import duckdb
    conn = duckdb.connect('{DB_PATH}')
    df = conn.execute("SELECT * FROM gold_career WHERE LEAGUE='NBL'").fetchdf()

Available views:
    - gold_career: Full player career game records
    - player_xwalk: Player identity crosswalk
    - canonical_players: Unique canonical player records
    - game_indexes: All game index records

Example queries:
    python scripts/setup_duckdb.py --query "SELECT COUNT(*) FROM gold_career"
    python scripts/setup_duckdb.py --query "SELECT DISTINCT LEAGUE FROM game_indexes"
""")

    conn.close()


if __name__ == "__main__":
    main()
