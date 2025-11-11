"""
Natural Language Parser for Basketball Data Queries

This module provides intelligent parsing of natural language date and season
references to make the API more LLM-friendly.

Examples:
    - "yesterday" → actual date
    - "last week" → date range
    - "this season" → current season year
    - "last season" → previous season year
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import re


def parse_relative_date(date_str: str) -> Optional[str]:
    """
    Parse natural language date references into ISO format dates.

    Supported formats:
        - "today" → today's date
        - "yesterday" → yesterday's date
        - "tomorrow" → tomorrow's date
        - "N days ago" → N days in the past
        - "last week" → 7 days ago
        - "last month" → 30 days ago

    Args:
        date_str: Natural language date string

    Returns:
        ISO format date string (YYYY-MM-DD) or None if not parseable

    Examples:
        >>> parse_relative_date("today")
        "2025-11-11"
        >>> parse_relative_date("yesterday")
        "2025-11-10"
        >>> parse_relative_date("3 days ago")
        "2025-11-08"
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.lower().strip()
    today = datetime.now().date()

    # Direct mappings
    mappings = {
        "today": today,
        "yesterday": today - timedelta(days=1),
        "tomorrow": today + timedelta(days=1),
        "last week": today - timedelta(days=7),
        "last month": today - timedelta(days=30),
        "this week": today,
        "this month": today,
    }

    if date_str in mappings:
        return mappings[date_str].isoformat()

    # Pattern: "N days ago"
    days_ago_match = re.match(r"(\d+)\s+days?\s+ago", date_str)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return (today - timedelta(days=days)).isoformat()

    # Pattern: "N weeks ago"
    weeks_ago_match = re.match(r"(\d+)\s+weeks?\s+ago", date_str)
    if weeks_ago_match:
        weeks = int(weeks_ago_match.group(1))
        return (today - timedelta(weeks=weeks)).isoformat()

    # If it's already in ISO format, return as-is
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str

    return None


def parse_relative_date_range(range_str: str) -> Optional[Dict[str, str]]:
    """
    Parse natural language date range into start/end dates.

    Supported formats:
        - "last N days" → past N days including today
        - "last week" → past 7 days
        - "last month" → past 30 days
        - "this week" → Monday to today
        - "this month" → 1st to today

    Args:
        range_str: Natural language range string

    Returns:
        Dict with 'start' and 'end' keys containing ISO dates, or None

    Examples:
        >>> parse_relative_date_range("last 7 days")
        {"start": "2025-11-04", "end": "2025-11-11"}
        >>> parse_relative_date_range("last week")
        {"start": "2025-11-04", "end": "2025-11-11"}
    """
    if not range_str or not isinstance(range_str, str):
        return None

    range_str = range_str.lower().strip()
    today = datetime.now().date()

    # Pattern: "last N days"
    last_days_match = re.match(r"last\s+(\d+)\s+days?", range_str)
    if last_days_match:
        days = int(last_days_match.group(1))
        return {
            "start": (today - timedelta(days=days-1)).isoformat(),
            "end": today.isoformat()
        }

    # Direct mappings for common ranges
    if range_str in ["last week", "past week"]:
        return {
            "start": (today - timedelta(days=7)).isoformat(),
            "end": today.isoformat()
        }

    if range_str in ["last month", "past month"]:
        return {
            "start": (today - timedelta(days=30)).isoformat(),
            "end": today.isoformat()
        }

    if range_str in ["this week"]:
        # Monday to today
        monday = today - timedelta(days=today.weekday())
        return {
            "start": monday.isoformat(),
            "end": today.isoformat()
        }

    if range_str in ["this month"]:
        # 1st of month to today
        first_of_month = today.replace(day=1)
        return {
            "start": first_of_month.isoformat(),
            "end": today.isoformat()
        }

    return None


def parse_relative_season(season_str: str, current_month: Optional[int] = None) -> Optional[str]:
    """
    Parse natural language season references into season year.

    Basketball seasons are named by their ending year:
        - "2024-25 season" → "2025"
        - "2025 season" → "2025"

    The season starts in November and ends in April:
        - Nov-Dec → current year is start of season
        - Jan-Apr → current year is end of season
        - May-Oct → current year is off-season (use previous season)

    Supported formats:
        - "this season" → current active season
        - "current season" → current active season
        - "last season" → previous season
        - "previous season" → previous season
        - "next season" → upcoming season
        - "2024 season" → specific season
        - "2024-25" → season 2025

    Args:
        season_str: Natural language season string
        current_month: Override current month (1-12) for testing

    Returns:
        Season year as string (YYYY format) or None

    Examples:
        >>> parse_relative_season("this season")  # If called in January 2025
        "2025"
        >>> parse_relative_season("last season")  # If called in January 2025
        "2024"
        >>> parse_relative_season("2024-25")
        "2025"
    """
    if not season_str or not isinstance(season_str, str):
        return None

    season_str = season_str.lower().strip()

    # Get current date info
    now = datetime.now()
    current_year = now.year
    month = current_month if current_month is not None else now.month

    # Determine current season
    # Basketball season: Nov (11) - Apr (4)
    # Nov-Dec: season is current_year + 1
    # Jan-Apr: season is current_year
    # May-Oct: season is current_year (previous season ended)
    if month >= 11:  # November or December
        current_season = current_year + 1
    elif month <= 4:  # January through April
        current_season = current_year
    else:  # May through October (off-season)
        current_season = current_year  # Use most recent completed season

    # Handle natural language references
    if season_str in ["this season", "current season", "this year"]:
        return str(current_season)

    if season_str in ["last season", "previous season", "last year"]:
        return str(current_season - 1)

    if season_str in ["next season", "upcoming season", "next year"]:
        return str(current_season + 1)

    # Pattern: "YYYY-YY" format → use ending year
    hyphen_match = re.match(r"(\d{4})-(\d{2})", season_str)
    if hyphen_match:
        start_year = int(hyphen_match.group(1))
        end_year_short = int(hyphen_match.group(2))
        # Validate that end year = start year + 1
        expected_end = start_year + 1
        if expected_end % 100 == end_year_short:
            return str(expected_end)

    # Pattern: "YYYY season" → use that year
    year_match = re.search(r"(\d{4})", season_str)
    if year_match:
        return year_match.group(1)

    return None


def parse_days_parameter(days_str: str) -> Optional[int]:
    """
    Parse natural language "days" parameter for recent games.

    Supported formats:
        - "today" → 1
        - "yesterday" → 2 (yesterday + today)
        - "last N days" → N
        - "last week" → 7
        - "last month" → 30

    Args:
        days_str: Natural language days string

    Returns:
        Number of days as integer, or None

    Examples:
        >>> parse_days_parameter("today")
        1
        >>> parse_days_parameter("last week")
        7
        >>> parse_days_parameter("last 5 days")
        5
    """
    if not days_str or not isinstance(days_str, str):
        return None

    days_str = days_str.lower().strip()

    # Direct mappings
    mappings = {
        "today": 1,
        "yesterday": 2,
        "last week": 7,
        "last month": 30,
        "this week": 7,
        "this month": 30,
    }

    if days_str in mappings:
        return mappings[days_str]

    # Pattern: "last N days"
    match = re.match(r"last\s+(\d+)\s+days?", days_str)
    if match:
        return int(match.group(1))

    # If it's just a number, return it
    if days_str.isdigit():
        return int(days_str)

    return None


def normalize_filters_for_llm(filters: Dict[str, any]) -> Dict[str, any]:
    """
    Normalize filter values from natural language to API format.

    This function intelligently converts LLM-friendly natural language
    into the format expected by the basketball data API.

    Args:
        filters: Raw filters dict from LLM

    Returns:
        Normalized filters dict

    Examples:
        >>> normalize_filters_for_llm({"league": "NCAA-MBB", "season": "this season"})
        {"league": "NCAA-MBB", "season": "2025"}

        >>> normalize_filters_for_llm({"league": "NCAA-MBB", "date": "yesterday"})
        {"league": "NCAA-MBB", "date": {"start": "2025-11-10", "end": "2025-11-10"}}
    """
    normalized = filters.copy()

    # Parse season references
    if "season" in normalized and isinstance(normalized["season"], str):
        parsed_season = parse_relative_season(normalized["season"])
        if parsed_season:
            normalized["season"] = parsed_season

    # Parse single date references
    if "date" in normalized and isinstance(normalized["date"], str):
        parsed_date = parse_relative_date(normalized["date"])
        if parsed_date:
            # Convert single date to range for consistency
            normalized["date"] = {"start": parsed_date, "end": parsed_date}

    # Parse date range references
    if "date_range" in normalized:
        parsed_range = parse_relative_date_range(normalized["date_range"])
        if parsed_range:
            normalized["date"] = parsed_range
            del normalized["date_range"]

    # Parse date_from/date_to
    if "date_from" in normalized and isinstance(normalized["date_from"], str):
        parsed = parse_relative_date(normalized["date_from"])
        if parsed:
            normalized["date_from"] = parsed

    if "date_to" in normalized and isinstance(normalized["date_to"], str):
        parsed = parse_relative_date(normalized["date_to"])
        if parsed:
            normalized["date_to"] = parsed

    return normalized


# Convenience function for testing
def test_parser():
    """Test the natural language parser with various inputs."""
    print("=== Testing Date Parser ===")
    test_dates = ["today", "yesterday", "3 days ago", "last week"]
    for date_str in test_dates:
        result = parse_relative_date(date_str)
        print(f"{date_str:20} → {result}")

    print("\n=== Testing Date Range Parser ===")
    test_ranges = ["last 7 days", "last week", "this month"]
    for range_str in test_ranges:
        result = parse_relative_date_range(range_str)
        print(f"{range_str:20} → {result}")

    print("\n=== Testing Season Parser ===")
    test_seasons = ["this season", "last season", "2024-25", "2024 season"]
    for season_str in test_seasons:
        result = parse_relative_season(season_str)
        print(f"{season_str:20} → {result}")

    print("\n=== Testing Days Parameter ===")
    test_days = ["today", "last week", "last 5 days"]
    for days_str in test_days:
        result = parse_days_parameter(days_str)
        print(f"{days_str:20} → {result}")


if __name__ == "__main__":
    test_parser()
