#!/usr/bin/env python3
"""
ACB Zenodo Historical Data Setup Helper

Downloads and validates ACB historical data from Zenodo (1983-2023 seasons).
The ACB fetcher automatically falls back to this data for older seasons when
the live website blocks requests.

Usage:
    python tools/acb/setup_zenodo_data.py --download
    python tools/acb/setup_zenodo_data.py --validate --season 2022
    python tools/acb/setup_zenodo_data.py --test --season 2022
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Zenodo dataset configuration
ZENODO_RECORD_ID = "8186617"  # Example - replace with actual record ID
ZENODO_API_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
ZENODO_FILES_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}/files"

# Local data paths
DATA_DIR = Path("data/acb/zenodo")
CACHE_DIR = Path(".cache/acb_zenodo")


class ACBZenodoHelper:
    """Helper for ACB Zenodo historical data"""

    def __init__(self, data_dir: Path = DATA_DIR, cache_dir: Path = CACHE_DIR):
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.metadata: Dict = {}

    def fetch_metadata(self) -> Dict:
        """Fetch Zenodo dataset metadata"""
        logger.info(f"Fetching Zenodo metadata for record {ZENODO_RECORD_ID}...")

        try:
            response = requests.get(ZENODO_API_URL, timeout=15)
            response.raise_for_status()

            self.metadata = response.json()
            logger.info(f"✅ Retrieved metadata for: {self.metadata.get('metadata', {}).get('title', 'Unknown')}")

            return self.metadata

        except requests.RequestException as e:
            logger.error(f"❌ Could not fetch Zenodo metadata: {e}")
            return {}

    def list_available_files(self) -> List[Dict]:
        """List files available in the Zenodo dataset"""
        if not self.metadata:
            self.fetch_metadata()

        files = self.metadata.get("files", [])

        print("\n" + "=" * 70)
        print("Available Files in Zenodo Dataset")
        print("=" * 70)

        for i, file_info in enumerate(files, 1):
            filename = file_info.get("key", "Unknown")
            size_mb = file_info.get("size", 0) / (1024 * 1024)
            checksum = file_info.get("checksum", "Unknown")

            print(f"\n{i}. {filename}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"   Checksum: {checksum}")

        print("\n" + "=" * 70 + "\n")

        return files

    def download_file(self, file_info: Dict, output_dir: Path) -> Optional[Path]:
        """Download a single file from Zenodo"""
        filename = file_info.get("key")
        download_url = file_info.get("links", {}).get("self")
        file_size = file_info.get("size", 0)

        if not download_url:
            logger.error(f"No download URL for {filename}")
            return None

        output_path = output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if already downloaded
        if output_path.exists() and output_path.stat().st_size == file_size:
            logger.info(f"✅ {filename} already downloaded (size matches)")
            return output_path

        logger.info(f"Downloading {filename} ({file_size / (1024*1024):.2f} MB)...")

        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            # Download with progress
            downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Simple progress indicator
                        if downloaded % (1024 * 1024 * 10) == 0:  # Every 10MB
                            progress = (downloaded / file_size) * 100
                            print(f"  {progress:.1f}% ({downloaded / (1024*1024):.1f} MB)", end='\r')

            print()  # New line after progress
            logger.info(f"✅ Downloaded {filename} to {output_path}")
            return output_path

        except requests.RequestException as e:
            logger.error(f"❌ Download failed for {filename}: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def download_all(self) -> List[Path]:
        """Download all files from Zenodo dataset"""
        if not self.metadata:
            self.fetch_metadata()

        files = self.metadata.get("files", [])

        if not files:
            logger.warning("No files found in Zenodo dataset")
            return []

        logger.info(f"Downloading {len(files)} files to {self.data_dir}...")

        downloaded_files = []
        for file_info in files:
            output_path = self.download_file(file_info, self.data_dir)
            if output_path:
                downloaded_files.append(output_path)

        logger.info(f"\n✅ Downloaded {len(downloaded_files)}/{len(files)} files successfully")
        return downloaded_files

    def validate_season_data(self, season: str) -> bool:
        """Validate downloaded data for a specific season"""
        logger.info(f"Validating ACB data for season {season}...")

        # Expected files for a season
        expected_files = [
            f"acb_player_stats_{season}.csv",
            f"acb_team_stats_{season}.csv",
        ]

        all_valid = True

        for filename in expected_files:
            file_path = self.data_dir / filename

            if not file_path.exists():
                logger.warning(f"⚠️  Missing: {filename}")
                all_valid = False
                continue

            # Load and validate structure
            try:
                df = pd.read_csv(file_path)

                if df.empty:
                    logger.warning(f"⚠️  Empty: {filename}")
                    all_valid = False
                    continue

                logger.info(f"✅ {filename}: {len(df)} rows, {len(df.columns)} columns")

                # Check key columns
                if "player" in filename.lower():
                    required_cols = ["PLAYER_NAME", "TEAM", "PTS", "REB", "AST"]
                else:
                    required_cols = ["TEAM", "PTS", "REB", "AST"]

                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    logger.warning(f"⚠️  {filename} missing columns: {missing_cols}")
                    all_valid = False

            except Exception as e:
                logger.error(f"❌ Could not validate {filename}: {e}")
                all_valid = False

        return all_valid

    def test_fetcher_integration(self, season: str):
        """Test that ACB fetcher can load Zenodo data"""
        logger.info(f"Testing ACB fetcher integration for season {season}...")

        try:
            # Import ACB fetcher
            from src.cbb_data.fetchers import acb

            # Test player season
            logger.info("Testing fetch_acb_player_season...")
            df_player = acb.fetch_acb_player_season(season)

            if not df_player.empty:
                logger.info(f"✅ Player season: {len(df_player)} players")
            else:
                logger.warning(f"⚠️  Player season returned empty DataFrame")

            # Test team season
            logger.info("Testing fetch_acb_team_season...")
            df_team = acb.fetch_acb_team_season(season)

            if not df_team.empty:
                logger.info(f"✅ Team season: {len(df_team)} teams")
            else:
                logger.warning(f"⚠️  Team season returned empty DataFrame")

            # Check SOURCE column
            if "SOURCE" in df_player.columns:
                sources = df_player["SOURCE"].value_counts()
                logger.info(f"Data sources: {sources.to_dict()}")

                if "zenodo" in sources:
                    logger.info(f"✅ Zenodo fallback working correctly")
                else:
                    logger.warning(f"⚠️  Data not from Zenodo - may be using live API")

        except Exception as e:
            logger.error(f"❌ Fetcher integration test failed: {e}")

    def print_summary(self):
        """Print summary of available data"""
        print("\n" + "=" * 70)
        print("ACB Zenodo Data Summary")
        print("=" * 70)

        if not self.data_dir.exists():
            print("\n⚠️  No data directory found. Run with --download to get data.")
            print("=" * 70 + "\n")
            return

        # List all CSV files
        csv_files = list(self.data_dir.glob("*.csv"))

        if not csv_files:
            print("\n⚠️  No CSV files found in data directory.")
            print("=" * 70 + "\n")
            return

        print(f"\nFound {len(csv_files)} CSV files:")

        # Group by season
        seasons = set()
        for file_path in csv_files:
            # Extract season from filename (e.g., acb_player_stats_2022.csv → 2022)
            parts = file_path.stem.split("_")
            if parts[-1].isdigit():
                seasons.add(parts[-1])

        seasons = sorted(seasons)

        print(f"\nAvailable seasons: {', '.join(seasons)}")
        print(f"Coverage: {seasons[0]} - {seasons[-1]}")

        print("\n" + "=" * 70 + "\n")


def main():
    """Main setup workflow"""
    parser = argparse.ArgumentParser(
        description="ACB Zenodo historical data setup helper"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download all files from Zenodo"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate downloaded data"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test fetcher integration"
    )
    parser.add_argument(
        "--season",
        help="Season to validate/test (e.g., 2022)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available files in Zenodo dataset"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Data directory (default: {DATA_DIR})"
    )

    args = parser.parse_args()

    # Create helper
    helper = ACBZenodoHelper(data_dir=args.data_dir)

    # List files
    if args.list:
        helper.list_available_files()
        return

    # Download
    if args.download:
        helper.download_all()
        helper.print_summary()

    # Validate
    if args.validate:
        if not args.season:
            print("❌ --season required for validation")
            sys.exit(1)

        is_valid = helper.validate_season_data(args.season)

        if is_valid:
            print(f"\n✅ Season {args.season} data is valid")
        else:
            print(f"\n❌ Season {args.season} data has issues (see warnings above)")

    # Test
    if args.test:
        if not args.season:
            print("❌ --season required for testing")
            sys.exit(1)

        helper.test_fetcher_integration(args.season)

    # Summary
    if not any([args.download, args.validate, args.test, args.list]):
        helper.print_summary()
        print("Usage:")
        print("  --download     Download Zenodo data")
        print("  --validate     Validate downloaded data (requires --season)")
        print("  --test         Test fetcher integration (requires --season)")
        print("  --list         List available files")
        print("\nExample:")
        print("  python tools/acb/setup_zenodo_data.py --download")
        print("  python tools/acb/setup_zenodo_data.py --validate --season 2022")
        print("  python tools/acb/setup_zenodo_data.py --test --season 2022\n")


if __name__ == "__main__":
    main()
