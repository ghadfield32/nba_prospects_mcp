#!/usr/bin/env python3
"""Scan for additional LNB data that may exist but hasn't been discovered

Purpose:
    - Check all data directories for LNB-related files
    - Look for raw PBP/shots data beyond 2025-2026
    - Search for any other parquet/JSON files
    - Determine if there's more data available that we haven't cataloged
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# ==============================================================================
# CONFIG
# ==============================================================================

DATA_ROOT = Path("data")

# ==============================================================================
# SCANNING FUNCTIONS
# ==============================================================================


def scan_directory_recursive(root_dir: Path, pattern: str = "*") -> list[Path]:
    """Recursively scan directory for files matching pattern

    Args:
        root_dir: Root directory to scan
        pattern: Glob pattern (default: all files)

    Returns:
        List of file paths
    """
    if not root_dir.exists():
        return []

    return sorted(root_dir.rglob(pattern))


def analyze_file(file_path: Path) -> dict:
    """Analyze a data file

    Args:
        file_path: Path to file

    Returns:
        Dict with file info
    """
    info = {
        "path": str(file_path),
        "name": file_path.name,
        "size_bytes": file_path.stat().st_size,
        "extension": file_path.suffix,
    }

    # If parquet, try to read metadata
    if file_path.suffix == ".parquet":
        try:
            df = pd.read_parquet(file_path)
            info["rows"] = len(df)
            info["columns"] = len(df.columns)

            # Check for LNB-specific columns
            if "GAME_ID" in df.columns:
                info["unique_games"] = int(df["GAME_ID"].nunique())

            if "fixture_uuid" in df.columns:
                info["unique_games"] = int(df["fixture_uuid"].nunique())

        except Exception as e:
            info["error"] = str(e)[:100]

    return info


def main():
    """Main scanning workflow"""

    print(f"{'#'*80}")
    print("# COMPREHENSIVE DATA SCAN: LNB FILES")
    print(f"{'#'*80}\n")

    # Scan all LNB-related directories
    lnb_data_dirs = [
        DATA_ROOT / "lnb",
        DATA_ROOT / "normalized" / "lnb",
    ]

    all_files = {}

    for data_dir in lnb_data_dirs:
        if not data_dir.exists():
            print(f"❌ Directory does not exist: {data_dir}\n")
            continue

        print(f"\n{'='*80}")
        print(f"SCANNING: {data_dir}")
        print(f"{'='*80}\n")

        # Find all parquet files
        parquet_files = scan_directory_recursive(data_dir, "*.parquet")
        print(f"Found {len(parquet_files)} parquet files:\n")

        for file_path in parquet_files:
            rel_path = file_path.relative_to(DATA_ROOT)
            info = analyze_file(file_path)

            all_files[str(rel_path)] = info

            print(f"📄 {rel_path}")
            print(f"   Size: {info['size_bytes']:,} bytes")

            if "rows" in info:
                print(f"   Rows: {info['rows']:,}")
                print(f"   Columns: {info['columns']}")

            if "unique_games" in info:
                print(f"   Unique Games: {info['unique_games']}")

            if "error" in info:
                print(f"   ERROR: {info['error']}")

            print()

        # Find all JSON files
        json_files = scan_directory_recursive(data_dir, "*.json")
        if json_files:
            print(f"\nFound {len(json_files)} JSON files:")
            for file_path in json_files:
                rel_path = file_path.relative_to(DATA_ROOT)
                print(f"📄 {rel_path} ({file_path.stat().st_size:,} bytes)")

        # Find all CSV files
        csv_files = scan_directory_recursive(data_dir, "*.csv")
        if csv_files:
            print(f"\nFound {len(csv_files)} CSV files:")
            for file_path in csv_files:
                rel_path = file_path.relative_to(DATA_ROOT)
                print(f"📄 {rel_path} ({file_path.stat().st_size:,} bytes)")

    # Summary
    print(f"\n\n{'='*80}")
    print("SCAN SUMMARY")
    print(f"{'='*80}\n")

    print(f"Total parquet files found: {len(all_files)}")

    # Group by type
    normalized_files = [k for k in all_files.keys() if "normalized" in k]
    historical_files = [k for k in all_files.keys() if "historical" in k]
    other_files = [
        k for k in all_files.keys() if k not in normalized_files and k not in historical_files
    ]

    print(f"\nNormalized files: {len(normalized_files)}")
    print(f"Historical files: {len(historical_files)}")
    print(f"Other files: {len(other_files)}")

    if other_files:
        print("\nOther files found:")
        for f in other_files:
            print(f"  - {f}")

    # Check for raw PBP data beyond 2025-2026
    print(f"\n{'='*80}")
    print("CHECKING FOR ADDITIONAL HISTORICAL SEASONS")
    print(f"{'='*80}\n")

    historical_root = DATA_ROOT / "lnb" / "historical"
    if historical_root.exists():
        all_season_dirs = sorted([d for d in historical_root.iterdir() if d.is_dir()])
        print(f"Historical season directories found: {len(all_season_dirs)}")

        for season_dir in all_season_dirs:
            parquet_count = len(list(season_dir.glob("*.parquet")))
            print(f"  {season_dir.name}: {parquet_count} parquet files")

            # Check what files exist
            fixtures = season_dir / "fixtures.parquet"
            pbp = season_dir / "pbp_events.parquet"
            shots = season_dir / "shots.parquet"

            status = []
            if fixtures.exists():
                status.append(f"fixtures ({len(pd.read_parquet(fixtures))} rows)")
            if pbp.exists():
                status.append(f"PBP ({len(pd.read_parquet(pbp))} events)")
            if shots.exists():
                status.append(f"shots ({len(pd.read_parquet(shots))} shots)")

            if status:
                print(f"    Data: {', '.join(status)}")

    print(f"\n{'='*80}")
    print("SCAN COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
