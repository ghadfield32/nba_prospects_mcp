#!/usr/bin/env python3
"""NZ-NBL Game Index Creator

This script helps create and maintain the NZ-NBL game index, which maps
FIBA LiveStats game IDs to NZ-NBL games.

Purpose:
    - Build initial game index from CSV or manual input
    - Validate game IDs against FIBA LiveStats
    - Update index with new games
    - Export to Parquet/CSV for use by fetchers

Usage:
    # Create from CSV template
    python tools/nz_nbl/create_game_index.py --input nz_nbl_games.csv --output data/nz_nbl_game_index.parquet

    # Add individual game
    python tools/nz_nbl/create_game_index.py --add-game \
        --game-id "301234" \
        --season "2024" \
        --date "2024-04-15" \
        --home "Auckland" \
        --away "Wellington"

    # Validate existing index
    python tools/nz_nbl/create_game_index.py --validate data/nz_nbl_game_index.parquet

Input CSV Format:
    SEASON,GAME_ID,GAME_DATE,HOME_TEAM,AWAY_TEAM,HOME_SCORE,AWAY_SCORE
    2024,301234,2024-04-15,Auckland Tuatara,Wellington Saints,,
    2024,301235,2024-04-16,Canterbury Rams,Otago Nuggets,85,78

Note:
    FIBA LiveStats game IDs must be manually discovered by inspecting
    the NZ-NBL schedule on FIBA LiveStats website:
    https://fibalivestats.dcd.shared.geniussports.com/u/NZN/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def create_empty_template(output_path: Path) -> None:
    """Create empty CSV template for manual filling

    Args:
        output_path: Path to save CSV template
    """
    template = pd.DataFrame(
        columns=[
            "SEASON",
            "GAME_ID",
            "GAME_DATE",
            "HOME_TEAM",
            "AWAY_TEAM",
            "HOME_SCORE",
            "AWAY_SCORE",
        ]
    )

    # Add example rows
    template.loc[0] = [
        "2024",
        "301234",
        "2024-04-15",
        "Auckland Tuatara",
        "Wellington Saints",
        "",
        "",
    ]
    template.loc[1] = [
        "2024",
        "301235",
        "2024-04-16",
        "Canterbury Rams",
        "Otago Nuggets",
        "85",
        "78",
    ]

    template.to_csv(output_path, index=False)
    print(f"Created template CSV: {output_path}")
    print("\nInstructions:")
    print("1. Fill in game details (SEASON, GAME_ID, GAME_DATE, teams)")
    print("2. Game IDs must be found manually from FIBA LiveStats")
    print("3. Date format: YYYY-MM-DD")
    print("4. Scores optional (leave blank if game not played yet)")
    print(f"5. Run: python {Path(__file__).name} --input {output_path}")


def load_csv_index(input_path: Path) -> pd.DataFrame:
    """Load game index from CSV

    Args:
        input_path: Path to CSV file

    Returns:
        DataFrame with game index
    """
    df = pd.read_csv(input_path)

    # Validate required columns
    required_cols = ["SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Convert date column
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

    # Handle optional score columns
    if "HOME_SCORE" not in df.columns:
        df["HOME_SCORE"] = None
    if "AWAY_SCORE" not in df.columns:
        df["AWAY_SCORE"] = None

    # Convert scores to numeric (empty strings become NaN)
    df["HOME_SCORE"] = pd.to_numeric(df["HOME_SCORE"], errors="coerce")
    df["AWAY_SCORE"] = pd.to_numeric(df["AWAY_SCORE"], errors="coerce")

    print(f"Loaded {len(df)} games from {input_path}")
    return df


def save_index(df: pd.DataFrame, output_path: Path, format: str = "parquet") -> None:
    """Save game index to file

    Args:
        df: Game index DataFrame
        output_path: Output file path
        format: File format ("parquet" or "csv")
    """
    if format == "parquet":
        df.to_parquet(output_path, index=False)
    elif format == "csv":
        df.to_csv(output_path, index=False)
    else:
        raise ValueError(f"Unknown format: {format}")

    print(f"Saved game index: {output_path} ({len(df)} games)")


def validate_index(df: pd.DataFrame, check_fiba: bool = False) -> bool:
    """Validate game index data

    Args:
        df: Game index DataFrame
        check_fiba: If True, check game IDs against FIBA LiveStats (slow)

    Returns:
        True if valid, False otherwise
    """
    print("\n=== Validating Game Index ===\n")

    errors = []

    # Check required columns
    required_cols = ["SEASON", "GAME_ID", "GAME_DATE", "HOME_TEAM", "AWAY_TEAM"]
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False

    # Check for duplicates
    duplicates = df[df.duplicated(subset=["GAME_ID"], keep=False)]
    if not duplicates.empty:
        errors.append(f"Found {len(duplicates)} duplicate game IDs")
        print("❌ Duplicate game IDs found:")
        for _, row in duplicates.iterrows():
            print(f"   - {row['GAME_ID']} ({row['HOME_TEAM']} vs {row['AWAY_TEAM']})")

    # Check for missing values
    for col in required_cols:
        missing = df[col].isna().sum()
        if missing > 0:
            errors.append(f"{missing} missing values in {col}")
            print(f"⚠️  {missing} missing values in {col}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Total games: {len(df)}")
    print(f"Seasons: {df['SEASON'].nunique()}")
    print(f"Unique teams: {pd.concat([df['HOME_TEAM'], df['AWAY_TEAM']]).nunique()}")

    if check_fiba:
        print("\nValidating game IDs against FIBA LiveStats...")
        print("(This may take several minutes)")

        # Import NZ-NBL fetcher
        from src.cbb_data.fetchers.nz_nbl_fiba import _scrape_fiba_box_score

        valid_count = 0
        invalid_count = 0

        for game_id in df["GAME_ID"].unique():
            try:
                result = _scrape_fiba_box_score(str(game_id))
                if not result.empty:
                    valid_count += 1
                    print(f"  ✅ {game_id} - Valid")
                else:
                    invalid_count += 1
                    print(f"  ❌ {game_id} - No data found")
            except Exception as e:
                invalid_count += 1
                print(f"  ❌ {game_id} - Error: {str(e)[:50]}")

        print(f"\nFIBA Validation: {valid_count} valid, {invalid_count} invalid")

    if errors:
        print(f"\n❌ Validation failed with {len(errors)} errors")
        return False
    else:
        print("\n✅ Validation passed!")
        return True


def add_game(
    existing_index: pd.DataFrame | None,
    season: str,
    game_id: str,
    game_date: str,
    home_team: str,
    away_team: str,
    home_score: int | None = None,
    away_score: int | None = None,
) -> pd.DataFrame:
    """Add a new game to the index

    Args:
        existing_index: Existing game index (or None for new index)
        season: Season string (e.g., "2024")
        game_id: FIBA game ID
        game_date: Game date (YYYY-MM-DD)
        home_team: Home team name
        away_team: Away team name
        home_score: Home team score (optional)
        away_score: Away team score (optional)

    Returns:
        Updated game index
    """
    new_game = {
        "SEASON": season,
        "GAME_ID": game_id,
        "GAME_DATE": pd.to_datetime(game_date),
        "HOME_TEAM": home_team,
        "AWAY_TEAM": away_team,
        "HOME_SCORE": home_score,
        "AWAY_SCORE": away_score,
    }

    if existing_index is None or existing_index.empty:
        df = pd.DataFrame([new_game])
    else:
        # Check for duplicate
        if game_id in existing_index["GAME_ID"].values:
            print(f"⚠️  Game ID {game_id} already exists in index. Skipping.")
            return existing_index

        df = pd.concat([existing_index, pd.DataFrame([new_game])], ignore_index=True)

    print(f"✅ Added game: {home_team} vs {away_team} ({game_id})")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Create and manage NZ-NBL game index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--create-template",
        metavar="OUTPUT_CSV",
        help="Create empty CSV template for manual filling",
    )

    parser.add_argument(
        "--input",
        metavar="CSV_FILE",
        help="Input CSV file with game data",
    )

    parser.add_argument(
        "--output",
        metavar="OUTPUT_FILE",
        help="Output file path (default: data/nz_nbl_game_index.parquet)",
        default="data/nz_nbl_game_index.parquet",
    )

    parser.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default="parquet",
        help="Output file format (default: parquet)",
    )

    parser.add_argument(
        "--validate",
        metavar="INDEX_FILE",
        help="Validate existing game index",
    )

    parser.add_argument(
        "--check-fiba",
        action="store_true",
        help="Check game IDs against FIBA LiveStats (slow)",
    )

    parser.add_argument(
        "--add-game",
        action="store_true",
        help="Add a single game to the index",
    )

    parser.add_argument("--game-id", help="FIBA game ID")
    parser.add_argument("--season", help="Season (e.g., 2024)")
    parser.add_argument("--date", help="Game date (YYYY-MM-DD)")
    parser.add_argument("--home", help="Home team name")
    parser.add_argument("--away", help="Away team name")
    parser.add_argument("--home-score", type=int, help="Home team score (optional)")
    parser.add_argument("--away-score", type=int, help="Away team score (optional)")

    args = parser.parse_args()

    # Create template
    if args.create_template:
        create_empty_template(Path(args.create_template))
        return

    # Validate
    if args.validate:
        index_path = Path(args.validate)
        if index_path.suffix == ".parquet":
            df = pd.read_parquet(index_path)
        else:
            df = pd.read_csv(index_path)
            df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

        validate_index(df, check_fiba=args.check_fiba)
        return

    # Add single game
    if args.add_game:
        required = ["game_id", "season", "date", "home", "away"]
        missing = [arg for arg in required if not getattr(args, arg.replace("-", "_"))]

        if missing:
            print(
                f"Error: Missing required arguments for --add-game: {', '.join(['--' + m for m in missing])}"
            )
            sys.exit(1)

        # Load existing index if exists
        output_path = Path(args.output)
        if output_path.exists():
            if output_path.suffix == ".parquet":
                existing = pd.read_parquet(output_path)
            else:
                existing = pd.read_csv(output_path)
                existing["GAME_DATE"] = pd.to_datetime(existing["GAME_DATE"])
        else:
            existing = None

        # Add game
        updated = add_game(
            existing,
            args.season,
            args.game_id,
            args.date,
            args.home,
            args.away,
            args.home_score,
            args.away_score,
        )

        # Save
        save_index(updated, output_path, args.format)
        return

    # Build from CSV
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {input_path}")
            sys.exit(1)

        df = load_csv_index(input_path)

        # Validate
        if validate_index(df):
            output_path = Path(args.output)
            save_index(df, output_path, args.format)
        else:
            print("\nValidation failed. Please fix errors and try again.")
            sys.exit(1)
        return

    # No action specified
    parser.print_help()


if __name__ == "__main__":
    main()
