"""Sub-Game Granularity Aggregation Module

This module provides functions to aggregate play-by-play data into sub-game level
box scores (half-level or quarter-level statistics).

Key Features:
- Filter PBP data by half or quarter
- Aggregate PBP events into box score statistics
- Support both NCAA (half) and EuroLeague (quarter) formats
- Return unified schema matching full-game box scores

Supported Granularity Levels:
- 'game' (default): Full game stats (no aggregation)
- 'half': NCAA-MBB half-level stats (1st half, 2nd half)
- 'quarter': EuroLeague quarter-level stats (Q1, Q2, Q3, Q4)
- 'play': Raw play-by-play events (no aggregation)

Data Derivation from PBP:
From CBBpy PBP, we can derive:
- PTS: From scoring_play events
- FGM/FGA: From shooting_play events
- FG3M/FG3A: From is_three=True shooting plays
- FTM/FTA: From 'free throw' play_type
- AST: From is_assisted=True plays
- REB: From 'rebound' play_type (can't separate OREB/DREB)
- TOV: From 'turnover' play_type
- STL: From 'steal' play_type (if available)
- BLK: From 'block' play_type (if available)
- PF: From 'foul' play_type

Limitations:
- OREB/DREB: PBP doesn't distinguish offensive vs defensive rebounds
- BLK_AGAINST, PF_DRAWN: Not available in PBP
- MIN: Requires time tracking (complex, not implemented)
- VALUATION, PLUS_MINUS: EuroLeague-specific, not in PBP
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def filter_pbp_by_half(pbp_df: pd.DataFrame, half: int) -> pd.DataFrame:
    """Filter play-by-play data to a specific half

    NCAA basketball has 2 halves (20 minutes each).

    Args:
        pbp_df: Play-by-play DataFrame (from CBBpy or ESPN)
        half: Half number (1 or 2)

    Returns:
        Filtered DataFrame containing only events from specified half

    Example:
        >>> pbp = fetch_cbbpy_pbp('401824809')
        >>> first_half = filter_pbp_by_half(pbp, half=1)
        >>> print(len(first_half))  # ~240 events in first half
    """
    if pbp_df.empty:
        return pbp_df

    if 'half' not in pbp_df.columns:
        logger.warning("PBP data does not have 'half' column - cannot filter by half")
        return pbp_df

    if half not in [1, 2]:
        logger.warning(f"Invalid half number: {half}. Must be 1 or 2.")
        return pbp_df

    filtered = pbp_df[pbp_df['half'] == half].copy()
    logger.debug(f"Filtered PBP to half {half}: {len(filtered)} events (from {len(pbp_df)} total)")

    return filtered


def filter_pbp_by_quarter(pbp_df: pd.DataFrame, quarter: int) -> pd.DataFrame:
    """Filter play-by-play data to a specific quarter

    EuroLeague basketball has 4 quarters (10 minutes each).

    Args:
        pbp_df: Play-by-play DataFrame (from EuroLeague API)
        quarter: Quarter number (1, 2, 3, or 4)

    Returns:
        Filtered DataFrame containing only events from specified quarter

    Example:
        >>> pbp = fetch_euroleague_play_by_play(2024, 1)
        >>> q1 = filter_pbp_by_quarter(pbp, quarter=1)
    """
    if pbp_df.empty:
        return pbp_df

    # Try different column names (QUARTER, PERIOD, quarter)
    quarter_col = None
    for col in ['QUARTER', 'quarter', 'PERIOD', 'period']:
        if col in pbp_df.columns:
            quarter_col = col
            break

    if quarter_col is None:
        logger.warning("PBP data does not have quarter/period column - cannot filter by quarter")
        return pbp_df

    if quarter not in [1, 2, 3, 4]:
        logger.warning(f"Invalid quarter number: {quarter}. Must be 1-4.")
        return pbp_df

    filtered = pbp_df[pbp_df[quarter_col] == quarter].copy()
    logger.debug(f"Filtered PBP to quarter {quarter}: {len(filtered)} events (from {len(pbp_df)} total)")

    return filtered


def aggregate_pbp_to_box_score(
    pbp_df: pd.DataFrame,
    group_by: List[str],
    league: str = 'NCAA-MBB'
) -> pd.DataFrame:
    """Aggregate play-by-play events into box score statistics

    This function converts raw PBP events into player-level statistics by:
    1. Grouping by (game, player, period)
    2. Counting scoring plays, shots, assists, rebounds, etc.
    3. Returning a unified box score schema

    Args:
        pbp_df: Play-by-play DataFrame
        group_by: List of columns to group by (e.g., ['game_id', 'shooter', 'half'])
        league: League identifier for schema formatting

    Returns:
        DataFrame with box score statistics (unified 35-column schema)

    Example:
        >>> pbp = fetch_cbbpy_pbp('401824809')
        >>> pbp_half1 = filter_pbp_by_half(pbp, half=1)
        >>> box_half1 = aggregate_pbp_to_box_score(
        ...     pbp_half1,
        ...     group_by=['game_id', 'shooter', 'half']
        ... )
        >>> print(box_half1[['PLAYER_NAME', 'HALF', 'PTS', 'FGM', 'FGA']].head())
    """
    if pbp_df.empty:
        logger.warning("Empty PBP DataFrame - cannot aggregate")
        return pd.DataFrame()

    logger.info(f"Aggregating {len(pbp_df)} PBP events to box score stats")

    # CBBpy PBP column mapping
    # Columns: ['game_id', 'home_team', 'away_team', 'play_desc', 'home_score',
    #           'away_score', 'half', 'secs_left_half', 'secs_left_reg', 'play_team',
    #           'play_type', 'shooting_play', 'scoring_play', 'is_three', 'shooter',
    #           'is_assisted', 'assist_player', 'shot_x', 'shot_y']

    # Strategy: Create separate aggregations for different stat types, then combine

    # 1. SCORING STATS (shooter-based)
    # Filter to plays with a shooter (shooting plays + free throws)
    shooter_plays = pbp_df[pbp_df['shooter'].notna()].copy()

    if shooter_plays.empty:
        logger.warning("No shooter plays found in PBP - cannot derive scoring stats")
        return pd.DataFrame()

    # Rename 'shooter' to 'player' for consistent grouping
    shooter_plays['player'] = shooter_plays['shooter']

    # Calculate shooting stats
    shooting_stats = shooter_plays.groupby(group_by + ['player']).agg({
        'scoring_play': 'sum',  # Total made shots
        'shooting_play': 'sum',  # Total shot attempts
        'is_three': lambda x: (x == True).sum(),  # 3PM (3-pointers made)
        'is_assisted': lambda x: (x == True).sum(),  # Won't use directly (assists come from assist_player)
    }).reset_index()

    # Calculate points from scoring plays
    # Need to distinguish FG (2 or 3 pts) from FT (1 pt)
    shooter_plays['is_free_throw'] = shooter_plays['play_type'].str.contains('free throw', case=False, na=False)
    shooter_plays['is_two_pointer'] = (shooter_plays['shooting_play'] == True) & (shooter_plays['is_three'] == False) & (shooter_plays['is_free_throw'] == False)
    shooter_plays['is_three_pointer'] = (shooter_plays['shooting_play'] == True) & (shooter_plays['is_three'] == True)

    # Calculate points: FTM=1, FG2M=2, FG3M=3
    shooter_plays['points'] = (
        (shooter_plays['is_free_throw'] & shooter_plays['scoring_play']).astype(int) * 1 +
        (shooter_plays['is_two_pointer'] & shooter_plays['scoring_play']).astype(int) * 2 +
        (shooter_plays['is_three_pointer'] & shooter_plays['scoring_play']).astype(int) * 3
    )

    # Calculate detailed shooting stats
    detailed_shooting = shooter_plays.groupby(group_by + ['player']).agg({
        'points': 'sum',  # Total points
        'is_free_throw': 'sum',  # FTA
        'is_two_pointer': 'sum',  # FG2A
        'is_three_pointer': 'sum',  # FG3A
    }).reset_index()

    # Calculate makes
    shooter_plays['ftm'] = (shooter_plays['is_free_throw'] & shooter_plays['scoring_play']).astype(int)
    shooter_plays['fg2m'] = (shooter_plays['is_two_pointer'] & shooter_plays['scoring_play']).astype(int)
    shooter_plays['fg3m'] = (shooter_plays['is_three_pointer'] & shooter_plays['scoring_play']).astype(int)

    makes = shooter_plays.groupby(group_by + ['player']).agg({
        'ftm': 'sum',
        'fg2m': 'sum',
        'fg3m': 'sum',
    }).reset_index()

    # Merge shooting stats
    shooting_combined = detailed_shooting.merge(makes, on=group_by + ['player'], how='outer')

    # 2. ASSISTS (assist_player-based)
    assist_plays = pbp_df[pbp_df['assist_player'].notna()].copy()
    if not assist_plays.empty:
        assist_plays['player'] = assist_plays['assist_player']
        assists = assist_plays.groupby(group_by + ['player']).size().reset_index(name='AST')
    else:
        assists = pd.DataFrame(columns=group_by + ['player', 'AST'])

    # 3. REBOUNDS (rebound play_type)
    rebound_plays = pbp_df[pbp_df['play_type'].str.contains('rebound', case=False, na=False)].copy()
    if not rebound_plays.empty:
        # Rebounds are assigned to play_team, but we need individual player
        # CBBpy PBP doesn't have player-level rebound attribution
        # We'll skip rebounds for now (limitation of PBP data)
        logger.debug("Rebounds detected in PBP but player attribution not available")
        rebounds = pd.DataFrame(columns=group_by + ['player', 'REB'])
    else:
        rebounds = pd.DataFrame(columns=group_by + ['player', 'REB'])

    # 4. TURNOVERS
    turnover_plays = pbp_df[pbp_df['play_type'].str.contains('turnover', case=False, na=False)].copy()
    if not turnover_plays.empty:
        # Turnovers might be assigned to play_team, not individual player
        # Check if we can extract player from play_desc
        logger.debug("Turnovers detected but player attribution may be limited")
        turnovers = pd.DataFrame(columns=group_by + ['player', 'TOV'])
    else:
        turnovers = pd.DataFrame(columns=group_by + ['player', 'TOV'])

    # 5. FOULS
    foul_plays = pbp_df[pbp_df['play_type'].str.contains('foul', case=False, na=False)].copy()
    if not foul_plays.empty:
        logger.debug("Fouls detected but player attribution may be limited")
        fouls = pd.DataFrame(columns=group_by + ['player', 'PF'])
    else:
        fouls = pd.DataFrame(columns=group_by + ['player', 'PF'])

    # COMBINE ALL STATS
    # Start with shooting stats (has all players who took shots)
    box_score = shooting_combined.copy()

    # Add assists
    if not assists.empty:
        box_score = box_score.merge(assists, on=group_by + ['player'], how='outer')
    else:
        box_score['AST'] = 0

    # Fill NaN values with 0
    box_score = box_score.fillna(0)

    # Calculate derived stats
    box_score['PTS'] = box_score['points'].astype(int)
    box_score['FTM'] = box_score['ftm'].astype(int)
    box_score['FTA'] = box_score['is_free_throw'].astype(int)
    box_score['FG2M'] = box_score['fg2m'].astype(int)
    box_score['FG2A'] = box_score['is_two_pointer'].astype(int)
    box_score['FG3M'] = box_score['fg3m'].astype(int)
    box_score['FG3A'] = box_score['is_three_pointer'].astype(int)
    box_score['FGM'] = (box_score['FG2M'] + box_score['FG3M']).astype(int)
    box_score['FGA'] = (box_score['FG2A'] + box_score['FG3A']).astype(int)

    # Calculate percentages
    box_score['FG_PCT'] = np.where(
        box_score['FGA'] > 0,
        box_score['FGM'] / box_score['FGA'],
        0.0
    )
    box_score['FG3_PCT'] = np.where(
        box_score['FG3A'] > 0,
        box_score['FG3M'] / box_score['FG3A'],
        0.0
    )
    box_score['FT_PCT'] = np.where(
        box_score['FTA'] > 0,
        box_score['FTM'] / box_score['FTA'],
        0.0
    )

    # Add missing stats with placeholder values
    box_score['REB'] = 0  # PBP doesn't have player-level rebounds
    box_score['OREB'] = 0
    box_score['DREB'] = 0
    box_score['STL'] = 0  # Not in CBBpy PBP
    box_score['BLK'] = 0  # Not in CBBpy PBP
    box_score['TOV'] = 0  # Player attribution difficult
    box_score['PF'] = 0  # Player attribution difficult
    box_score['MIN'] = 0  # Requires time tracking

    # Rename columns to match unified schema
    if 'player' in box_score.columns:
        box_score = box_score.rename(columns={'player': 'PLAYER_NAME'})

    if 'game_id' in box_score.columns:
        box_score = box_score.rename(columns={'game_id': 'GAME_ID'})

    if 'half' in box_score.columns:
        box_score = box_score.rename(columns={'half': 'HALF'})

    if 'quarter' in box_score.columns:
        box_score = box_score.rename(columns={'quarter': 'QUARTER'})

    # Add metadata columns
    box_score['LEAGUE'] = league
    box_score['SOURCE'] = 'pbp_aggregation'

    # Select final columns (matching unified schema where possible)
    final_columns = [
        'GAME_ID', 'PLAYER_NAME', 'PTS', 'FGM', 'FGA', 'FG_PCT',
        'FG2M', 'FG2A', 'FG3M', 'FG3A', 'FG3_PCT',
        'FTM', 'FTA', 'FT_PCT', 'AST', 'REB', 'OREB', 'DREB',
        'STL', 'BLK', 'TOV', 'PF', 'MIN', 'LEAGUE', 'SOURCE'
    ]

    # Add granularity column if present
    if 'HALF' in box_score.columns:
        final_columns.insert(2, 'HALF')
    if 'QUARTER' in box_score.columns:
        final_columns.insert(2, 'QUARTER')

    # Keep only columns that exist
    available_columns = [c for c in final_columns if c in box_score.columns]
    box_score = box_score[available_columns]

    logger.info(f"Aggregated PBP to {len(box_score)} player box scores")

    return box_score


def aggregate_by_half(pbp_df: pd.DataFrame, league: str = 'NCAA-MBB') -> pd.DataFrame:
    """Aggregate play-by-play data to half-level box scores

    Returns box scores for each player for each half (1st half, 2nd half).
    For a game with 22 players, this returns 44 rows (22 × 2 halves).

    Args:
        pbp_df: Play-by-play DataFrame (from CBBpy)
        league: League identifier

    Returns:
        DataFrame with half-level box scores

    Example:
        >>> pbp = fetch_cbbpy_pbp('401824809')
        >>> half_stats = aggregate_by_half(pbp)
        >>> print(len(half_stats))  # 44 rows (22 players × 2 halves)
        >>> print(half_stats[half_stats['HALF'] == 1][['PLAYER_NAME', 'PTS']].head())
    """
    if pbp_df.empty:
        return pd.DataFrame()

    if 'half' not in pbp_df.columns:
        logger.error("PBP data does not have 'half' column - cannot aggregate by half")
        return pd.DataFrame()

    logger.info("Aggregating PBP to half-level box scores")

    # Group by game, player, and half
    group_by = ['game_id']
    if 'half' in pbp_df.columns:
        group_by.append('half')

    box_score = aggregate_pbp_to_box_score(pbp_df, group_by=group_by, league=league)

    return box_score


def aggregate_by_quarter(pbp_df: pd.DataFrame, league: str = 'EuroLeague') -> pd.DataFrame:
    """Aggregate play-by-play data to quarter-level box scores

    Returns box scores for each player for each quarter (Q1, Q2, Q3, Q4).
    For a game with 20 players, this returns 80 rows (20 × 4 quarters).

    Args:
        pbp_df: Play-by-play DataFrame (from EuroLeague API)
        league: League identifier

    Returns:
        DataFrame with quarter-level box scores

    Example:
        >>> pbp = fetch_euroleague_play_by_play(2024, 1)
        >>> quarter_stats = aggregate_by_quarter(pbp)
        >>> print(quarter_stats[quarter_stats['QUARTER'] == 1][['PLAYER_NAME', 'PTS']].head())
    """
    if pbp_df.empty:
        return pd.DataFrame()

    # Try different column names
    quarter_col = None
    for col in ['QUARTER', 'quarter', 'PERIOD', 'period']:
        if col in pbp_df.columns:
            quarter_col = col
            break

    if quarter_col is None:
        logger.error("PBP data does not have quarter/period column - cannot aggregate by quarter")
        return pd.DataFrame()

    logger.info("Aggregating PBP to quarter-level box scores")

    # Normalize column name to 'quarter'
    if quarter_col != 'quarter':
        pbp_df = pbp_df.rename(columns={quarter_col: 'quarter'})

    # Group by game, player, and quarter
    group_by = ['game_id', 'quarter'] if 'game_id' in pbp_df.columns else ['quarter']

    box_score = aggregate_pbp_to_box_score(pbp_df, group_by=group_by, league=league)

    return box_score
