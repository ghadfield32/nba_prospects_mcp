#!/usr/bin/env python
"""Test a single ACB box score fetch to verify parsing."""

import sys

sys.path.insert(0, "src")

import pandas as pd


def _safe_int(value, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        if pd.isna(value):
            return default
        # Handle numpy types directly
        if hasattr(value, "item"):
            return int(value.item())
        # Handle float/int types
        if isinstance(value, int | float):
            return int(value)
        # Handle string with potential decimal
        s = str(value).strip().replace(",", "")
        if "." in s:
            return int(float(s))
        import re

        match = re.search(r"-?\d+", s)
        return int(match.group(0)) if match else default
    except (ValueError, TypeError):
        return default


def _parse_shooting(text: str) -> tuple:
    """Parse shooting stat 'Made/Attempted'."""
    try:
        text = str(text).strip()
        if "%" in text:
            return 0, 0
        if "/" in text:
            parts = text.split("/")
            if len(parts) == 2:
                return _safe_int(parts[0]), _safe_int(parts[1])
    except Exception:
        pass
    return 0, 0


# ACB box score URL
game_id = "17745"  # 2017-18 game
url = f"https://www.acb.com/partido/estadisticas/id/{game_id}"
print(f"Fetching: {url}")

try:
    tables = pd.read_html(url, encoding="utf-8")
    print(f"Found {len(tables)} tables")

    # Process table 1 (first team)
    table = tables[1]

    # Flatten multi-level columns to simple indices
    if isinstance(table.columns, pd.MultiIndex):
        table.columns = range(len(table.columns))

    print(f"\nTable has {table.shape[1]} columns, {len(table)} rows")

    # Parse a few rows
    all_players = []
    for _idx, row in table.iterrows():
        # Column 1 is player name
        player_name = str(row.iloc[1]) if len(row) > 1 else ""

        if not player_name or player_name.lower() in ["totales", "jugador", "nombre"]:
            continue

        # Column 2: Minutes (MM:SS format)
        min_str = str(row.iloc[2]) if len(row) > 2 else "0"
        if ":" in min_str:
            parts = min_str.split(":")
            minutes = int(parts[0]) + int(parts[1]) / 60
        else:
            minutes = _safe_int(min_str)

        # Column 3: Points (use _safe_int for numpy floats)
        pts = _safe_int(row.iloc[3]) if len(row) > 3 else 0

        # Column 4: T2 (2PT field goals)
        t2m, t2a = _parse_shooting(row.iloc[4]) if len(row) > 4 else (0, 0)

        # Column 6: T3 (3PT field goals)
        t3m, t3a = _parse_shooting(row.iloc[6]) if len(row) > 6 else (0, 0)

        # Column 8: Free throws
        ftm, fta = _parse_shooting(row.iloc[8]) if len(row) > 8 else (0, 0)

        # Column 10: Total rebounds
        reb = _safe_int(row.iloc[10]) if len(row) > 10 else 0

        # Column 12: Assists
        ast = _safe_int(row.iloc[12]) if len(row) > 12 else 0

        # Column 13: Steals
        stl = _safe_int(row.iloc[13]) if len(row) > 13 else 0

        # Column 14: Turnovers
        tov = _safe_int(row.iloc[14]) if len(row) > 14 else 0

        # Column 15: Blocks
        blk = _safe_int(row.iloc[15]) if len(row) > 15 else 0

        all_players.append(
            {
                "name": player_name,
                "min": round(minutes, 1),
                "pts": pts,
                "2pm/a": f"{t2m}/{t2a}",
                "3pm/a": f"{t3m}/{t3a}",
                "ftm/a": f"{ftm}/{fta}",
                "reb": reb,
                "ast": ast,
                "stl": stl,
                "tov": tov,
                "blk": blk,
            }
        )

    print(f"\nParsed {len(all_players)} players:")
    print(
        f"{'Name':<20} {'Min':>5} {'Pts':>3} {'2PT':>5} {'3PT':>5} {'FT':>4} {'Reb':>3} {'Ast':>3} {'Stl':>3} {'Tov':>3} {'Blk':>3}"
    )
    print("-" * 75)
    for p in all_players[:12]:
        print(
            f"{p['name'][:20]:<20} {p['min']:>5.1f} {p['pts']:>3} {p['2pm/a']:>5} {p['3pm/a']:>5} {p['ftm/a']:>4} {p['reb']:>3} {p['ast']:>3} {p['stl']:>3} {p['tov']:>3} {p['blk']:>3}"
        )

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
