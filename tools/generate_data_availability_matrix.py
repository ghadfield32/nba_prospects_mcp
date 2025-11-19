"""Generate Data Availability Matrix

Creates a comprehensive matrix showing data availability across all leagues.
Outputs in both Markdown and text formats.

Usage:
    python tools/generate_data_availability_matrix.py

Output:
    - data_availability_matrix.md (Markdown table)
    - data_availability_matrix.txt (ASCII table)
    - Prints summary to console
"""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cbb_data.catalog.sources import LEAGUE_SOURCES, _register_league_sources

# Ensure league sources are registered
_register_league_sources()


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


def format_text(rows, datasets):
    """Format matrix as ASCII table"""

    # Calculate column widths
    league_width = max(len(r["league"]) for r in rows)
    dataset_width = 6  # Width for emoji

    # Header
    lines = [
        "=" * 80,
        "DATA AVAILABILITY MATRIX",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 80,
        "",
    ]

    # Table header
    header = f"{'League':<{league_width}} | "
    header += " | ".join(f"{d[0][:6]:^{dataset_width}}" for d in datasets)
    header += " | Total"

    separator = "-" * len(header)

    lines.append(header)
    lines.append(separator)

    # Table rows
    for row in rows:
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

    # Summary
    lines.extend(
        [
            "",
            separator,
            "",
            "Legend: Y=Available, P=Partial, -=Not available",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    """Generate and save data availability matrix"""

    print("Generating data availability matrix...")
    print()

    # Generate matrix
    rows, datasets = generate_matrix()

    # Format outputs
    md_content = format_markdown(rows, datasets)
    txt_content = format_text(rows, datasets)

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
