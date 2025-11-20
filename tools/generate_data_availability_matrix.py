"""Generate Enhanced Data Availability Matrix

Creates a comprehensive matrix showing data availability across all leagues,
including min/max date coverage for each dataset.

Usage:
    python tools/generate_data_availability_matrix.py
    python tools/generate_data_availability_matrix.py --compute-coverage

Output:
    - data_availability_matrix.md (Markdown table)
    - data_availability_matrix.txt (ASCII table with dates)
    - Prints summary to console
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources

# Try to import coverage module
try:
    from cbb_data.metadata.coverage import CoverageMap, load_coverage

    COVERAGE_AVAILABLE = True
except ImportError:
    COVERAGE_AVAILABLE = False
    CoverageMap = dict

# Ensure league sources are registered
_register_league_sources()

# League tiers for organization
TIER_0 = ["NCAA-MBB", "NCAA-WBB", "EuroLeague", "EuroCup", "G-League", "WNBA"]
TIER_1 = ["NBL", "NZ-NBL", "LNB_PROA", "ACB", "OTE", "CEBL"]
TIER_2 = ["NJCAA", "NAIA", "USPORTS", "CCAA", "LKL", "BAL", "BCL", "ABA"]
LNB_EXTRA = ["LNB_ELITE2", "LNB_ESPOIRS_ELITE", "LNB_ESPOIRS_PROB"]


def generate_matrix():
    """Generate data availability matrix from registry"""

    # Define dataset columns
    datasets = [
        ("player_season", "player_season_source"),
        ("team_season", "team_season_source"),
        ("schedule", "schedule_source"),
        ("box_score", "box_score_source"),
        ("pbp", "pbp_source"),
        ("shots", "shots_source"),
    ]

    # Collect data
    rows = []
    for league_id, config in sorted(LEAGUE_SOURCES.items()):
        row = {
            "league": league_id,
            "notes": config.notes or "",
        }

        # Check each dataset
        available_count = 0
        for dataset_name, source_attr in datasets:
            source = getattr(config, source_attr, "none")
            fetch_attr = f"fetch_{dataset_name.replace('box_score', 'player_game')}"

            # Check if fetch function is wired
            fetch_func = getattr(config, fetch_attr, None) if hasattr(config, fetch_attr) else None

            if source and source != "none":
                if fetch_func:
                    row[dataset_name] = "✅"
                    available_count += 1
                else:
                    row[dataset_name] = "⚠️"  # Source defined but not wired
            else:
                row[dataset_name] = "❌"

        row["count"] = available_count
        rows.append(row)

    return rows, datasets


def format_markdown(rows, datasets):
    """Format matrix as Markdown table"""

    # Header
    lines = [
        "# Data Availability Matrix",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Legend",
        "- ✅ Available and wired",
        "- ⚠️ Source defined but not wired",
        "- ❌ Not available",
        "",
        "## Coverage Matrix",
        "",
    ]

    # Table header
    header = "| League | " + " | ".join(d[0] for d in datasets) + " | Total |"
    separator = "|" + "|".join(["---"] * (len(datasets) + 2)) + "|"

    lines.append(header)
    lines.append(separator)

    # Table rows
    for row in rows:
        cells = [row["league"]]
        for dataset_name, _ in datasets:
            cells.append(row[dataset_name])
        cells.append(f"{row['count']}/6")
        lines.append("| " + " | ".join(cells) + " |")

    # Summary
    lines.extend(
        [
            "",
            "## Summary",
            "",
        ]
    )

    # Count leagues by coverage level
    full_coverage = sum(1 for r in rows if r["count"] == 6)
    partial_coverage = sum(1 for r in rows if 1 <= r["count"] < 6)
    no_coverage = sum(1 for r in rows if r["count"] == 0)

    lines.extend(
        [
            f"- Full coverage (6/6): {full_coverage} leagues",
            f"- Partial coverage (1-5/6): {partial_coverage} leagues",
            f"- No coverage (0/6): {no_coverage} leagues",
            f"- Total leagues: {len(rows)}",
            "",
        ]
    )

    # Top leagues
    top_leagues = sorted(rows, key=lambda x: x["count"], reverse=True)[:10]
    lines.extend(
        [
            "## Top Leagues by Coverage",
            "",
        ]
    )
    for i, row in enumerate(top_leagues, 1):
        lines.append(f"{i}. **{row['league']}** - {row['count']}/6 datasets")

    return "\n".join(lines)


def format_text(rows, datasets, coverage: CoverageMap = None):
    """Format matrix as ASCII table with optional date coverage"""

    # Calculate column widths
    league_width = max(len(r["league"]) for r in rows)
    dataset_width = 6  # Width for status

    # Header
    lines = [
        "=" * 120,
        "DATA AVAILABILITY MATRIX",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 120,
        "",
        "Legend: Y=Available, P=Partial, -=Not available",
        "",
    ]

    # Table header
    header = f"{'League':<{league_width}} | "
    header += " | ".join(f"{d[0][:6]:^{dataset_width}}" for d in datasets)
    header += " | Total"

    separator = "-" * len(header)

    # Organize by tiers
    tier_groups = [
        ("TIER 0 - Core Feeders", TIER_0),
        ("TIER 1 - Secondary", TIER_1),
        ("LNB France", LNB_EXTRA),
        ("TIER 2 - Development", TIER_2),
    ]

    for tier_name, tier_leagues in tier_groups:
        lines.append("")
        lines.append(tier_name)
        lines.append(header)
        lines.append(separator)

        for row in rows:
            if row["league"] not in tier_leagues:
                continue

            cells = [f"{row['league']:<{league_width}}"]
            for dataset_name, _ in datasets:
                symbol = row[dataset_name]
                # Convert emoji to ASCII for text format
                if symbol == "✅":
                    symbol = "Y"
                elif symbol == "⚠️":
                    symbol = "P"
                else:
                    symbol = "-"
                cells.append(f"{symbol:^{dataset_width}}")
            cells.append(f"{row['count']}/6")
            lines.append(" | ".join(cells))

    # Date Coverage section (if coverage data available)
    if coverage:
        lines.extend(
            [
                "",
                "=" * 120,
                "DATE COVERAGE BY LEAGUE",
                "=" * 120,
                "",
                "Format: dataset: min_date – max_date [source]",
                "",
            ]
        )

        # Map dataset names for coverage lookup
        dataset_map = {
            "player_season": "player_season",
            "team_season": "team_season",
            "schedule": "schedule",
            "box_score": "player_game",  # box_score maps to player_game
            "pbp": "pbp",
            "shots": "shots",
        }

        for tier_name, tier_leagues in tier_groups:
            tier_has_coverage = False
            tier_lines = [tier_name, "-" * len(tier_name)]

            for row in rows:
                league = row["league"]
                if league not in tier_leagues:
                    continue

                league_cov = []
                for ds_name, _ in datasets:
                    cov_key = (league, dataset_map.get(ds_name, ds_name))
                    cov = coverage.get(cov_key)
                    if cov:
                        date_str = f"{cov.min_date[:10]}–{cov.max_date[:10]}"
                        if cov.notes:
                            date_str += f" [{cov.notes}]"
                        elif cov.record_count:
                            date_str += f" ({cov.record_count:,} records)"
                        league_cov.append(f"  {ds_name}: {date_str}")

                if league_cov:
                    tier_has_coverage = True
                    tier_lines.append(f"\n{league}:")
                    tier_lines.extend(league_cov)

            if tier_has_coverage:
                lines.extend(tier_lines)
                lines.append("")

    # Summary
    lines.extend(
        [
            "",
            "=" * 80,
            "SUMMARY",
            "=" * 80,
            "",
        ]
    )

    # Count by coverage
    full = sum(1 for r in rows if r["count"] == 6)
    high = sum(1 for r in rows if 4 <= r["count"] < 6)
    medium = sum(1 for r in rows if 2 <= r["count"] < 4)

    lines.extend(
        [
            f"Full (6/6):    {full} leagues",
            f"High (4-5/6):  {high} leagues",
            f"Medium (2-3/6): {medium} leagues",
            f"Total:         {len(rows)} leagues",
            "",
        ]
    )

    # Filter reference
    lines.extend(
        [
            "=" * 80,
            "FILTER QUICK REFERENCE",
            "=" * 80,
            "",
            "Date Filters:",
            "  relative_days: 7 (last week), 30 (last month), 365 (last year)",
            "  start_date / end_date: YYYY-MM-DD format",
            "",
            "Game Segment Filters:",
            "  periods: [1,2,3,4] for quarters, [5,6,7] for OT",
            "  halves: [1] first half, [2] second half (NCAA)",
            "  start_seconds / end_seconds: elapsed time from tip",
            "",
            "Common Time Windows:",
            "  Crunch time (NBA): periods=[4], start_seconds=2640 (last 2 min)",
            "  First half (NCAA): halves=[1]",
            "  Overtime: periods=[5,6,7,8]",
            "",
            "Name Filters:",
            "  team_names: ['Duke', 'Kentucky'] - case-insensitive",
            "  player_names: ['LeBron James'] - partial match supported",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    """Generate and save data availability matrix"""

    parser = argparse.ArgumentParser(description="Generate data availability matrix")
    parser.add_argument(
        "--compute-coverage", action="store_true", help="Compute coverage from data files"
    )
    args = parser.parse_args()

    print("Generating data availability matrix...")
    print()

    # Load coverage if available
    coverage = {}
    if COVERAGE_AVAILABLE:
        if args.compute_coverage:
            print("Computing coverage from data files...")
            try:
                from compute_coverage import compute_all_coverage

                coverage = compute_all_coverage()
            except Exception as e:
                print(f"Error computing coverage: {e}")
        else:
            coverage = load_coverage()
            if coverage:
                print(f"Loaded coverage for {len(coverage)} league/dataset combinations")

    # Generate matrix
    rows, datasets = generate_matrix()

    # Format outputs
    md_content = format_markdown(rows, datasets)
    txt_content = format_text(rows, datasets, coverage)

    # Save files
    output_dir = Path(__file__).parent.parent
    md_path = output_dir / "data_availability_matrix.md"
    txt_path = output_dir / "data_availability_matrix.txt"

    md_path.write_text(md_content, encoding="utf-8")
    txt_path.write_text(txt_content, encoding="utf-8")

    print(f"Saved: {md_path}")
    print(f"Saved: {txt_path}")
    print()

    # Print summary to console
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Count by coverage
    full = sum(1 for r in rows if r["count"] == 6)
    high = sum(1 for r in rows if 4 <= r["count"] < 6)
    medium = sum(1 for r in rows if 2 <= r["count"] < 4)
    low = sum(1 for r in rows if 1 <= r["count"] < 2)
    none = sum(1 for r in rows if r["count"] == 0)

    print(f"Full (6/6):    {full} leagues")
    print(f"High (4-5/6):  {high} leagues")
    print(f"Medium (2-3/6): {medium} leagues")
    print(f"Low (1/6):     {low} leagues")
    print(f"None (0/6):    {none} leagues")
    print(f"Total:         {len(rows)} leagues")
    print()

    # Top leagues
    print("Top 5 by coverage:")
    top_5 = sorted(rows, key=lambda x: x["count"], reverse=True)[:5]
    for i, row in enumerate(top_5, 1):
        print(f"  {i}. {row['league']}: {row['count']}/6")

    print()
    print("Matrix generation complete!")


if __name__ == "__main__":
    main()
