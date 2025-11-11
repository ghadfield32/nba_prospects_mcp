"""Filter compiler - converts FilterSpec to endpoint params and post-masks

The compiler takes a normalized FilterSpec and produces:
1. Endpoint-specific parameters (for API calls)
2. Post-processing masks (for filtering results after fetch)

This separation allows us to:
- Use native endpoint filters when available (more efficient)
- Apply additional filters client-side when endpoints don't support them
- Handle differences between ESPN, EuroLeague, Sports-Ref, etc.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .spec import FilterSpec

# Type alias for entity resolver function
# Takes (name, entity_type, league) and returns ID or None
ResolverFn = Callable[[str, str, str | None], int | None]


def _resolve_names_to_ids(
    names: list[str] | None,
    entity_type: str,
    league: str | None,
    resolver: ResolverFn | None,
) -> list[int] | None:
    """Resolve entity names to IDs using the provided resolver

    Args:
        names: List of entity names (team/player)
        entity_type: "team" or "player"
        league: League context for resolution (e.g., "NCAA-MBB")
        resolver: Function to resolve name -> ID

    Returns:
        List of resolved IDs, or None if no resolver or no names
    """
    if not names:
        return None
    if not resolver:
        # No resolver provided; post-mask will handle name matching
        return None

    ids = []
    for name in names:
        try:
            resolved_id = resolver(name, entity_type, league)
            if resolved_id is not None:
                ids.append(resolved_id)
        except Exception:
            # Resolver failed; skip this name
            continue

    return ids or None


def compile_params(
    dataset_id: str,
    f: FilterSpec,
    name_resolver: ResolverFn | None = None,
) -> dict[str, Any]:
    """Convert FilterSpec to endpoint params + post-mask dict

    This function is the core translation layer between our unified FilterSpec
    and the specific requirements of each data source (ESPN, EuroLeague, etc.)

    Args:
        dataset_id: Dataset being queried (affects param generation)
        f: The filter specification
        name_resolver: Optional function to resolve names -> IDs

    Returns:
        Dictionary with:
            - "params": endpoint-specific parameters for API call
            - "post_mask": filters to apply after fetching data
            - "meta": metadata about the query (league, season, etc.)

    Example:
        >>> spec = FilterSpec(
        ...     league="NCAA-MBB",
        ...     season="2024-25",
        ...     team=["Duke"],
        ...     last_n_games=5
        ... )
        >>> compile_params("player_game", spec)
        {
            "params": {"Season": "2024-25", "LastNGames": 5},
            "post_mask": {"TEAM_ID": [150], "LEAGUE": "NCAA-MBB"},
            "meta": {"league": "NCAA-MBB", "season": "2024-25"}
        }
    """
    params: dict[str, Any] = {}
    post_mask: dict[str, Any] = {}
    meta: dict[str, Any] = {}

    # Resolve names -> IDs (if resolver provided)
    team_ids = f.team_ids or _resolve_names_to_ids(f.team, "team", f.league, name_resolver)
    opp_ids = f.opponent_ids or _resolve_names_to_ids(f.opponent, "team", f.league, name_resolver)
    player_ids = f.player_ids or _resolve_names_to_ids(f.player, "player", f.league, name_resolver)

    # Store league/season in meta for logging/caching
    if f.league:
        meta["league"] = f.league
    if f.season:
        meta["season"] = f.season

    # --- Common parameters (supported by many endpoints) ---

    # Season
    if f.season:
        params["Season"] = f.season
        # Some sources want just the year (EuroLeague), others want YYYY-YY (ESPN)
        # The fetcher will adapt based on the source

    # Season type
    if f.season_type:
        params["SeasonType"] = f.season_type

    # Date range
    if f.date:
        if f.date.start:
            # ESPN format: MM/DD/YYYY
            params["DateFrom"] = f.date.start.strftime("%m/%d/%Y")
        if f.date.end:
            params["DateTo"] = f.date.end.strftime("%m/%d/%Y")

    # Per-mode aggregation
    if f.per_mode:
        params["PerMode"] = f.per_mode

    # Last N games
    if f.last_n_games:
        params["LastNGames"] = f.last_n_games

    # --- Post-processing masks ---
    # These filters are applied after data is fetched, either because:
    # 1. The endpoint doesn't support native filtering, or
    # 2. We want to ensure consistent behavior across sources

    # IDs
    post_mask["TEAM_ID"] = team_ids
    post_mask["OPPONENT_TEAM_ID"] = opp_ids
    post_mask["PLAYER_ID"] = player_ids
    post_mask["GAME_ID"] = f.game_ids

    # Names (for sources that return names but not IDs)
    post_mask["TEAM_NAME"] = f.team
    post_mask["OPPONENT_NAME"] = f.opponent
    post_mask["PLAYER_NAME"] = f.player

    # Game location
    post_mask["HOME_AWAY"] = f.home_away
    post_mask["VENUE"] = f.venue

    # Statistical filters
    post_mask["MIN_MINUTES"] = f.min_minutes
    post_mask["QUARTER"] = f.quarter

    # Shot/PBP filters
    post_mask["CONTEXT_MEASURE"] = f.context_measure

    # League filter (for multi-source queries)
    if f.league:
        post_mask["LEAGUE"] = f.league

    # Conference filter (post-mask if endpoint doesn't support it)
    if f.conference:
        post_mask["CONFERENCE"] = f.conference

    # Data quality
    post_mask["ONLY_COMPLETE"] = f.only_complete

    return {"params": params, "post_mask": post_mask, "meta": meta}


def apply_post_mask(df: Any, post_mask: dict[str, Any]) -> Any:
    """Apply post-processing filters to a DataFrame

    This function is used by fetchers to filter data after retrieval.
    Filters are applied in order of selectivity (most selective first) for performance.

    Filter application order:
    1. ID-based filters (most selective, fastest)
    2. League/Conference filters (categorical)
    3. Statistical filters (numeric comparisons)
    4. Name-based filters (slower string operations)

    Args:
        df: pandas DataFrame with data
        post_mask: Dictionary of filters from compile_params

    Returns:
        Filtered DataFrame
    """
    import pandas as pd

    if df.empty:
        return df

    out = df.copy()

    # --- Phase 1: ID-based filters (most selective, fastest) ---
    # These typically eliminate the most rows with O(n) complexity

    if post_mask.get("GAME_ID") and "GAME_ID" in out.columns:
        out = out[out["GAME_ID"].isin(post_mask["GAME_ID"])]
        if out.empty:
            return out  # Early exit

    if post_mask.get("PLAYER_ID") and "PLAYER_ID" in out.columns:
        out = out[out["PLAYER_ID"].isin(post_mask["PLAYER_ID"])]
        if out.empty:
            return out  # Early exit

    if post_mask.get("TEAM_ID") and "TEAM_ID" in out.columns:
        out = out[out["TEAM_ID"].isin(post_mask["TEAM_ID"])]
        if out.empty:
            return out  # Early exit

    if post_mask.get("OPPONENT_TEAM_ID") and "OPPONENT_TEAM_ID" in out.columns:
        out = out[out["OPPONENT_TEAM_ID"].isin(post_mask["OPPONENT_TEAM_ID"])]
        if out.empty:
            return out  # Early exit

    # --- Phase 2: Categorical filters (fast equality/membership checks) ---

    if post_mask.get("LEAGUE") and "LEAGUE" in out.columns:
        out = out[out["LEAGUE"] == post_mask["LEAGUE"]]
        if out.empty:
            return out

    if post_mask.get("HOME_AWAY") and "HOME_AWAY" in out.columns:
        out = out[out["HOME_AWAY"] == post_mask["HOME_AWAY"]]
        if out.empty:
            return out

    if post_mask.get("QUARTER") and "PERIOD" in out.columns:
        out = out[out["PERIOD"].isin(post_mask["QUARTER"])]
        if out.empty:
            return out

    # --- Phase 3: Statistical filters (numeric comparisons) ---

    if post_mask.get("MIN_MINUTES") is not None and "MIN" in out.columns:
        min_val = float(post_mask["MIN_MINUTES"])
        out = out[pd.to_numeric(out["MIN"], errors="coerce") >= min_val]
        if out.empty:
            return out

    # --- Phase 4: String-based filters (slower, done last) ---

    if post_mask.get("CONFERENCE") and "CONFERENCE" in out.columns:
        conf = post_mask["CONFERENCE"]
        out = out[out["CONFERENCE"].str.contains(conf, case=False, na=False)]
        if out.empty:
            return out

    if post_mask.get("VENUE") and "VENUE" in out.columns:
        pattern = post_mask["VENUE"]
        out = out[out["VENUE"].str.contains(pattern, case=False, na=False)]
        if out.empty:
            return out

    if post_mask.get("PLAYER_NAME") and "PLAYER_NAME" in out.columns:
        pattern = "|".join(post_mask["PLAYER_NAME"])
        out = out[out["PLAYER_NAME"].str.contains(pattern, case=False, na=False)]
        if out.empty:
            return out

    if post_mask.get("TEAM_NAME") and "TEAM_NAME" in out.columns:
        pattern = "|".join(post_mask["TEAM_NAME"])
        out = out[out["TEAM_NAME"].str.contains(pattern, case=False, na=False)]
        if out.empty:
            return out

    if post_mask.get("OPPONENT_NAME") and "OPPONENT_NAME" in out.columns:
        pattern = "|".join(post_mask["OPPONENT_NAME"])
        out = out[out["OPPONENT_NAME"].str.contains(pattern, case=False, na=False)]
        if out.empty:
            return out

    # --- Phase 5: Data completeness filter (last, as it's broad) ---

    if post_mask.get("ONLY_COMPLETE"):
        # Only keep rows with non-null key fields
        key_cols = ["GAME_ID", "PLAYER_ID", "TEAM_ID"]
        existing_keys = [c for c in key_cols if c in out.columns]
        if existing_keys:
            out = out.dropna(subset=existing_keys)

    return out
