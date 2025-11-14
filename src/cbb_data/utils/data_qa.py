"""
Data Quality Assurance Utilities

Shared QA functions for validating basketball data across all leagues.
Used by golden season scripts to ensure data integrity.
"""

import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class DataQAResults:
    """Container for QA check results"""

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.checks: List[Dict] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add_check(self, check_name: str, passed: bool, message: str, **metadata):
        """Add a QA check result"""
        self.checks.append({
            "check": check_name,
            "passed": passed,
            "message": message,
            **metadata
        })

        if not passed:
            self.errors.append(f"{check_name}: {message}")

    def add_warning(self, message: str):
        """Add a warning"""
        self.warnings.append(message)

    def is_healthy(self) -> bool:
        """Check if all critical checks passed"""
        return len(self.errors) == 0

    def print_summary(self):
        """Print QA summary"""
        print(f"\n{'='*70}")
        print(f"QA Results: {self.dataset_name}")
        print(f"{'='*70}")

        # Print checks
        passed_count = sum(1 for c in self.checks if c["passed"])
        total_count = len(self.checks)

        print(f"\nChecks: {passed_count}/{total_count} passed")
        for check in self.checks:
            status = "✅" if check["passed"] else "❌"
            print(f"  {status} {check['check']}: {check['message']}")

        # Print warnings
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        # Print errors
        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ❌ {error}")

        # Overall status
        print(f"\n{'='*70}")
        if self.is_healthy():
            print("✅ OVERALL: HEALTHY - All checks passed")
        else:
            print("❌ OVERALL: UNHEALTHY - Critical issues found")
        print(f"{'='*70}\n")


def check_no_duplicates(df: pd.DataFrame, key_columns: List[str],
                        dataset_name: str) -> Tuple[bool, str, int]:
    """
    Check for duplicate rows based on key columns.

    Args:
        df: DataFrame to check
        key_columns: Columns that should uniquely identify rows
        dataset_name: Name of dataset for error messages

    Returns:
        (passed, message, duplicate_count)
    """
    if df.empty:
        return True, "Dataset empty (no duplicates possible)", 0

    # Check if all key columns exist
    missing_cols = [col for col in key_columns if col not in df.columns]
    if missing_cols:
        return False, f"Missing key columns: {missing_cols}", -1

    duplicate_count = df.duplicated(subset=key_columns).sum()

    if duplicate_count == 0:
        return True, f"No duplicates on {key_columns}", 0
    else:
        return False, f"{duplicate_count} duplicate rows found on {key_columns}", duplicate_count


def check_required_columns(df: pd.DataFrame, required_columns: List[str],
                           dataset_name: str) -> Tuple[bool, str]:
    """
    Check that all required columns are present.

    Args:
        df: DataFrame to check
        required_columns: List of column names that must exist
        dataset_name: Name of dataset for error messages

    Returns:
        (passed, message)
    """
    missing_columns = [col for col in required_columns if col not in df.columns]

    if not missing_columns:
        return True, f"All {len(required_columns)} required columns present"
    else:
        return False, f"Missing columns: {missing_columns}"


def check_no_nulls_in_keys(df: pd.DataFrame, key_columns: List[str],
                            dataset_name: str) -> Tuple[bool, str, int]:
    """
    Check that key columns have no null values.

    Args:
        df: DataFrame to check
        key_columns: Columns that should not have nulls
        dataset_name: Name of dataset for error messages

    Returns:
        (passed, message, null_count)
    """
    if df.empty:
        return True, "Dataset empty (no nulls possible)", 0

    missing_cols = [col for col in key_columns if col not in df.columns]
    if missing_cols:
        return False, f"Missing key columns: {missing_cols}", -1

    null_counts = df[key_columns].isnull().sum()
    total_nulls = null_counts.sum()

    if total_nulls == 0:
        return True, f"No nulls in key columns {key_columns}", 0
    else:
        null_cols = null_counts[null_counts > 0].to_dict()
        return False, f"Nulls found in key columns: {null_cols}", int(total_nulls)


def check_row_count(df: pd.DataFrame, min_rows: int, max_rows: Optional[int] = None,
                   dataset_name: str = "") -> Tuple[bool, str]:
    """
    Check that DataFrame has reasonable row count.

    Args:
        df: DataFrame to check
        min_rows: Minimum expected rows
        max_rows: Maximum expected rows (None = no limit)
        dataset_name: Name of dataset for messages

    Returns:
        (passed, message)
    """
    row_count = len(df)

    if row_count < min_rows:
        return False, f"Too few rows: {row_count} < {min_rows}"

    if max_rows is not None and row_count > max_rows:
        return False, f"Too many rows: {row_count} > {max_rows}"

    return True, f"Row count OK: {row_count:,} rows"


def check_numeric_range(df: pd.DataFrame, column: str, min_val: float,
                        max_val: float, allow_null: bool = False) -> Tuple[bool, str]:
    """
    Check that numeric column values are within expected range.

    Args:
        df: DataFrame to check
        column: Column name to check
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        allow_null: Whether null values are acceptable

    Returns:
        (passed, message)
    """
    if column not in df.columns:
        return False, f"Column {column} not found"

    if df.empty:
        return True, f"{column} empty (no values to check)"

    series = df[column]

    # Check nulls
    null_count = series.isnull().sum()
    if null_count > 0 and not allow_null:
        return False, f"{column} has {null_count} null values (not allowed)"

    # Check range (ignore nulls)
    valid_values = series.dropna()
    if valid_values.empty:
        if allow_null:
            return True, f"{column} all null (allowed)"
        else:
            return False, f"{column} all null"

    out_of_range = ((valid_values < min_val) | (valid_values > max_val)).sum()

    if out_of_range == 0:
        return True, f"{column} range OK [{min_val}, {max_val}]"
    else:
        return False, f"{column} has {out_of_range} values outside [{min_val}, {max_val}]"


def check_team_totals_match_player_sums(team_game_df: pd.DataFrame,
                                         player_game_df: pd.DataFrame,
                                         stat_columns: List[str],
                                         tolerance: float = 1.0) -> Tuple[bool, str]:
    """
    Check that team game totals match sum of player stats for each game/team.

    Args:
        team_game_df: Team game stats
        player_game_df: Player game stats
        stat_columns: Stat columns to check (e.g., ['PTS', 'REB', 'AST'])
        tolerance: Allowed difference (for rounding)

    Returns:
        (passed, message)
    """
    if team_game_df.empty or player_game_df.empty:
        return True, "Empty dataset (cannot check totals)"

    # Check required columns
    required_team_cols = ['GAME_ID', 'TEAM_ID'] + stat_columns
    required_player_cols = ['GAME_ID', 'TEAM_ID'] + stat_columns

    missing_team = [c for c in required_team_cols if c not in team_game_df.columns]
    missing_player = [c for c in required_player_cols if c not in player_game_df.columns]

    if missing_team or missing_player:
        return False, f"Missing columns - team: {missing_team}, player: {missing_player}"

    # Aggregate player stats by game/team
    player_totals = player_game_df.groupby(['GAME_ID', 'TEAM_ID'])[stat_columns].sum().reset_index()

    # Merge with team totals
    comparison = team_game_df[required_team_cols].merge(
        player_totals,
        on=['GAME_ID', 'TEAM_ID'],
        suffixes=('_team', '_player'),
        how='inner'
    )

    if comparison.empty:
        return False, "No matching games found between team and player data"

    # Check each stat column
    mismatches = []
    for stat in stat_columns:
        team_col = f"{stat}_team" if f"{stat}_team" in comparison.columns else stat
        player_col = f"{stat}_player" if f"{stat}_player" in comparison.columns else stat

        if team_col not in comparison.columns or player_col not in comparison.columns:
            continue

        diff = (comparison[team_col] - comparison[player_col]).abs()
        mismatch_count = (diff > tolerance).sum()

        if mismatch_count > 0:
            max_diff = diff.max()
            mismatches.append(f"{stat}: {mismatch_count} mismatches (max diff: {max_diff:.1f})")

    if not mismatches:
        return True, f"Team totals match player sums for {len(comparison)} game-teams"
    else:
        return False, f"Mismatches found: {'; '.join(mismatches)}"


def check_shot_coordinates(shots_df: pd.DataFrame,
                           coord_columns: Tuple[str, str] = ('X', 'Y'),
                           court_bounds: Optional[Dict[str, Tuple[float, float]]] = None) -> Tuple[bool, str]:
    """
    Check that shot coordinates are within reasonable court bounds.

    Args:
        shots_df: Shot data with coordinates
        coord_columns: (X_column, Y_column) names
        court_bounds: Optional dict with 'X' and 'Y' keys mapping to (min, max) tuples

    Returns:
        (passed, message)
    """
    if shots_df.empty:
        return True, "No shots to check"

    x_col, y_col = coord_columns

    if x_col not in shots_df.columns or y_col not in shots_df.columns:
        return False, f"Missing coordinate columns: {x_col}, {y_col}"

    # Default FIBA court bounds (meters or normalized)
    if court_bounds is None:
        court_bounds = {
            'X': (0, 100),  # Normalized 0-100
            'Y': (0, 100)
        }

    # Check X coordinates
    x_min, x_max = court_bounds['X']
    x_out_of_bounds = ((shots_df[x_col] < x_min) | (shots_df[x_col] > x_max)).sum()

    # Check Y coordinates
    y_min, y_max = court_bounds['Y']
    y_out_of_bounds = ((shots_df[y_col] < y_min) | (shots_df[y_col] > y_max)).sum()

    total_out = x_out_of_bounds + y_out_of_bounds

    if total_out == 0:
        return True, f"All {len(shots_df)} shots have valid coordinates"
    else:
        return False, f"{total_out} shots outside court bounds (X: {x_out_of_bounds}, Y: {y_out_of_bounds})"


def check_pbp_final_score_matches_boxscore(pbp_df: pd.DataFrame,
                                            team_game_df: pd.DataFrame,
                                            sample_size: int = 10) -> Tuple[bool, str]:
    """
    Check that PBP final score matches team game boxscore for a sample of games.

    Args:
        pbp_df: Play-by-play data with GAME_ID, SCORE_HOME, SCORE_AWAY
        team_game_df: Team game data with GAME_ID, TEAM_ID, PTS
        sample_size: Number of games to sample for check

    Returns:
        (passed, message)
    """
    if pbp_df.empty or team_game_df.empty:
        return True, "Empty dataset (cannot check scores)"

    # Check required columns
    if 'GAME_ID' not in pbp_df.columns:
        return False, "PBP missing GAME_ID column"

    if not all(col in team_game_df.columns for col in ['GAME_ID', 'PTS']):
        return False, "Team game missing required columns"

    # Get final PBP score for each game
    # Assuming last event has final score
    final_pbp = pbp_df.groupby('GAME_ID').last().reset_index()

    if 'SCORE_HOME' not in final_pbp.columns or 'SCORE_AWAY' not in final_pbp.columns:
        return False, "PBP missing SCORE_HOME or SCORE_AWAY columns"

    # Sample games
    sample_games = final_pbp['GAME_ID'].drop_duplicates().sample(
        min(sample_size, len(final_pbp))
    ).tolist()

    mismatches = []

    for game_id in sample_games:
        pbp_final = final_pbp[final_pbp['GAME_ID'] == game_id].iloc[0]
        team_scores = team_game_df[team_game_df['GAME_ID'] == game_id]

        if len(team_scores) != 2:
            mismatches.append(f"Game {game_id}: Expected 2 teams, got {len(team_scores)}")
            continue

        pts_sorted = sorted(team_scores['PTS'].tolist())
        pbp_sorted = sorted([pbp_final['SCORE_HOME'], pbp_final['SCORE_AWAY']])

        if pts_sorted != pbp_sorted:
            mismatches.append(
                f"Game {game_id}: Boxscore {pts_sorted} != PBP {pbp_sorted}"
            )

    if not mismatches:
        return True, f"PBP scores match boxscore for {len(sample_games)} games"
    else:
        return False, f"{len(mismatches)} mismatches: {'; '.join(mismatches[:3])}"


def run_schedule_qa(df: pd.DataFrame, league: str, season: str,
                    min_games: int = 10) -> DataQAResults:
    """Run standard QA checks on schedule data"""
    results = DataQAResults(f"{league} {season} Schedule")

    # Check required columns
    required_cols = ['LEAGUE', 'SEASON', 'GAME_ID', 'GAME_DATE',
                     'HOME_TEAM', 'AWAY_TEAM']
    passed, msg = check_required_columns(df, required_cols, "schedule")
    results.add_check("Required Columns", passed, msg)

    if not passed:
        return results  # Can't continue without required columns

    # Check no duplicates on GAME_ID
    passed, msg, dup_count = check_no_duplicates(df, ['GAME_ID'], "schedule")
    results.add_check("No Duplicate Games", passed, msg, duplicate_count=dup_count)

    # Check no nulls in keys
    passed, msg, null_count = check_no_nulls_in_keys(
        df, ['GAME_ID', 'GAME_DATE'], "schedule"
    )
    results.add_check("No Null Keys", passed, msg, null_count=null_count)

    # Check row count
    passed, msg = check_row_count(df, min_games, dataset_name="schedule")
    results.add_check("Row Count", passed, msg)

    # Check league and season are correct
    if 'LEAGUE' in df.columns:
        wrong_league = (df['LEAGUE'] != league).sum()
        if wrong_league > 0:
            results.add_check(
                "League Values",
                False,
                f"{wrong_league} rows have wrong league (expected {league})"
            )
        else:
            results.add_check("League Values", True, f"All rows have LEAGUE={league}")

    if 'SEASON' in df.columns:
        wrong_season = (df['SEASON'] != season).sum()
        if wrong_season > 0:
            results.add_check(
                "Season Values",
                False,
                f"{wrong_season} rows have wrong season (expected {season})"
            )
        else:
            results.add_check("Season Values", True, f"All rows have SEASON={season}")

    return results


def run_player_game_qa(df: pd.DataFrame, league: str, season: str,
                       min_players: int = 50) -> DataQAResults:
    """Run standard QA checks on player game data"""
    results = DataQAResults(f"{league} {season} Player Game")

    # Check required columns
    required_cols = ['LEAGUE', 'SEASON', 'GAME_ID', 'TEAM_ID', 'PLAYER_ID',
                     'PLAYER_NAME', 'MIN', 'PTS', 'REB', 'AST']
    passed, msg = check_required_columns(df, required_cols, "player_game")
    results.add_check("Required Columns", passed, msg)

    if not passed:
        return results

    # Check no duplicates on (GAME_ID, TEAM_ID, PLAYER_ID)
    passed, msg, dup_count = check_no_duplicates(
        df, ['GAME_ID', 'TEAM_ID', 'PLAYER_ID'], "player_game"
    )
    results.add_check("No Duplicate Players", passed, msg, duplicate_count=dup_count)

    # Check no nulls in keys
    passed, msg, null_count = check_no_nulls_in_keys(
        df, ['GAME_ID', 'PLAYER_ID'], "player_game"
    )
    results.add_check("No Null Keys", passed, msg, null_count=null_count)

    # Check row count
    passed, msg = check_row_count(df, min_players, dataset_name="player_game")
    results.add_check("Row Count", passed, msg)

    # Check stat ranges
    if 'PTS' in df.columns:
        passed, msg = check_numeric_range(df, 'PTS', 0, 100, allow_null=False)
        results.add_check("PTS Range", passed, msg)

    if 'MIN' in df.columns:
        passed, msg = check_numeric_range(df, 'MIN', 0, 60, allow_null=True)
        results.add_check("MIN Range", passed, msg)

    return results


def run_team_game_qa(df: pd.DataFrame, league: str, season: str,
                     min_teams: int = 20) -> DataQAResults:
    """Run standard QA checks on team game data"""
    results = DataQAResults(f"{league} {season} Team Game")

    # Check required columns
    required_cols = ['LEAGUE', 'SEASON', 'GAME_ID', 'TEAM_ID',
                     'PTS', 'REB', 'AST']
    passed, msg = check_required_columns(df, required_cols, "team_game")
    results.add_check("Required Columns", passed, msg)

    if not passed:
        return results

    # Check no duplicates
    passed, msg, dup_count = check_no_duplicates(
        df, ['GAME_ID', 'TEAM_ID'], "team_game"
    )
    results.add_check("No Duplicate Teams", passed, msg, duplicate_count=dup_count)

    # Check no nulls in keys
    passed, msg, null_count = check_no_nulls_in_keys(
        df, ['GAME_ID', 'TEAM_ID'], "team_game"
    )
    results.add_check("No Null Keys", passed, msg, null_count=null_count)

    # Check row count
    passed, msg = check_row_count(df, min_teams, dataset_name="team_game")
    results.add_check("Row Count", passed, msg)

    # Check stat ranges
    if 'PTS' in df.columns:
        passed, msg = check_numeric_range(df, 'PTS', 0, 200, allow_null=False)
        results.add_check("PTS Range", passed, msg)

    return results


def run_cross_granularity_qa(schedule_df: pd.DataFrame,
                             player_game_df: pd.DataFrame,
                             team_game_df: pd.DataFrame,
                             league: str, season: str) -> DataQAResults:
    """Run QA checks across multiple granularities"""
    results = DataQAResults(f"{league} {season} Cross-Granularity")

    # Check that team totals match player sums
    if not team_game_df.empty and not player_game_df.empty:
        stat_cols = ['PTS', 'REB', 'AST']
        # Only check columns that exist in both
        stat_cols = [c for c in stat_cols
                     if c in team_game_df.columns and c in player_game_df.columns]

        if stat_cols:
            passed, msg = check_team_totals_match_player_sums(
                team_game_df, player_game_df, stat_cols, tolerance=1.0
            )
            results.add_check("Team Totals Match Player Sums", passed, msg)

    # Check that all games in player_game/team_game exist in schedule
    if not schedule_df.empty and not team_game_df.empty:
        schedule_games = set(schedule_df['GAME_ID'].unique())
        team_games = set(team_game_df['GAME_ID'].unique())

        missing_from_schedule = team_games - schedule_games
        if missing_from_schedule:
            results.add_check(
                "All Team Games in Schedule",
                False,
                f"{len(missing_from_schedule)} games in team_game not in schedule"
            )
        else:
            results.add_check(
                "All Team Games in Schedule",
                True,
                f"All {len(team_games)} games in schedule"
            )

    return results
