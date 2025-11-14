"""LNB API Configuration Layer

This module provides a clean way to configure authentication headers and cookies
for the LNB API client without hardcoding them into the source code.

Usage:
    1. Create a JSON file with your headers/cookies from DevTools:
       tools/lnb/lnb_headers.json

    2. Headers are automatically loaded by LNBClient on initialization

    3. Example JSON format:
       {
           "Origin": "https://www.lnb.fr",
           "Cookie": "session=abc123; token=xyz789",
           "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
           "X-Requested-With": "XMLHttpRequest"
       }

How to Generate:
    1. Run: python3 tools/lnb/test_api_headers.py --curl-file headers_curl.txt
    2. If successful, extract headers from cURL and save as JSON
    3. Place in tools/lnb/lnb_headers.json OR src/cbb_data/fetchers/lnb_headers.json

Security Notes:
    - DO NOT commit lnb_headers.json to version control (contains cookies)
    - Add to .gitignore
    - Rotate cookies periodically (they expire)
    - Use environment variables for production deployments

Created: 2025-11-14
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def _find_config_file() -> Path | None:
    """Search for lnb_headers.json in multiple locations.

    Search order:
    1. Environment variable: LNB_HEADERS_PATH
    2. Same directory as this file
    3. tools/lnb/ directory
    4. Repository root

    Returns:
        Path to config file if found, None otherwise
    """
    # 1. Check environment variable first
    env_path = os.getenv("LNB_HEADERS_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            logger.debug(f"Found config at LNB_HEADERS_PATH: {p}")
            return p
        logger.warning(f"LNB_HEADERS_PATH set but file not found: {p}")

    # 2. Same directory as this module
    module_dir = Path(__file__).parent
    local_path = module_dir / "lnb_headers.json"
    if local_path.exists():
        logger.debug(f"Found config in module directory: {local_path}")
        return local_path

    # 3. tools/lnb/ directory
    repo_root = module_dir.parent.parent.parent  # src/cbb_data/fetchers → root
    tools_path = repo_root / "tools" / "lnb" / "lnb_headers.json"
    if tools_path.exists():
        logger.debug(f"Found config in tools/lnb: {tools_path}")
        return tools_path

    # 4. Repository root
    root_path = repo_root / "lnb_headers.json"
    if root_path.exists():
        logger.debug(f"Found config in repo root: {root_path}")
        return root_path

    logger.debug("No lnb_headers.json found in any search location")
    return None


def load_lnb_headers() -> Dict[str, str]:
    """Load authentication headers from configuration file.

    Searches for lnb_headers.json in multiple locations and loads
    headers for LNB API authentication.

    Returns:
        Dictionary of HTTP headers to add to requests. Empty dict if no config found.

    Example:
        >>> headers = load_lnb_headers()
        >>> if headers:
        ...     print("Auth headers loaded")
        ... else:
        ...     print("Using default headers only")

    Notes:
        - File is optional; returns {} if not found
        - Invalid JSON will log a warning and return {}
        - See module docstring for file format
    """
    config_path = _find_config_file()

    if config_path is None:
        logger.info(
            "No lnb_headers.json found. Using default headers only. "
            "To add authentication, create tools/lnb/lnb_headers.json. "
            "See docs/LNB_API_SETUP_GUIDE.md for details."
        )
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            headers = json.load(f)

        if not isinstance(headers, dict):
            logger.warning(
                f"Invalid format in {config_path}: expected JSON object, "
                f"got {type(headers)}. Using default headers only."
            )
            return {}

        # Convert all values to strings (some might be numbers or bools)
        headers = {str(k): str(v) for k, v in headers.items()}

        logger.info(
            f"Loaded {len(headers)} custom headers from {config_path.name} "
            f"(keys: {list(headers.keys())})"
        )
        return headers

    except json.JSONDecodeError as e:
        logger.warning(
            f"Failed to parse {config_path}: {e}. "
            "Using default headers only. Check JSON syntax."
        )
        return {}
    except Exception as e:
        logger.warning(
            f"Error loading {config_path}: {e}. Using default headers only."
        )
        return {}


def save_headers_template(output_path: Path | str | None = None) -> None:
    """Create a template lnb_headers.json file for user to fill in.

    Args:
        output_path: Where to save template. Defaults to tools/lnb/lnb_headers.json.template

    Example:
        >>> save_headers_template()
        Template saved to: tools/lnb/lnb_headers.json.template

        >>> # User fills in template, then renames:
        >>> # mv lnb_headers.json.template lnb_headers.json
    """
    if output_path is None:
        repo_root = Path(__file__).parent.parent.parent.parent
        output_path = repo_root / "tools" / "lnb" / "lnb_headers.json.template"
    else:
        output_path = Path(output_path)

    template = {
        "_comment": "Fill in these headers from your browser DevTools",
        "_instructions": [
            "1. Open Chrome → https://www.lnb.fr/statistiques",
            "2. DevTools (F12) → Network → XHR filter",
            "3. Click around site to trigger API calls",
            "4. Find successful request to api-prod.lnb.fr (200 OK)",
            "5. Right-click → Copy → Copy as cURL",
            "6. Extract headers below from cURL command",
            "7. Remove this comment and rename file to lnb_headers.json",
        ],
        "Origin": "https://www.lnb.fr",
        "Referer": "https://www.lnb.fr/statistiques",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        "Cookie": "session=YOUR_SESSION_COOKIE; token=YOUR_TOKEN",
        "X-Requested-With": "XMLHttpRequest",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    logger.info(f"Template saved to: {output_path}")
    print(f"\nTemplate saved to: {output_path}")
    print("\nNext steps:")
    print("1. Fill in the headers from your browser DevTools")
    print("2. Remove the '_comment' and '_instructions' keys")
    print(f"3. Rename to: {output_path.parent / 'lnb_headers.json'}")
    print("4. Rerun stress test: python3 src/cbb_data/fetchers/lnb_api.py")


if __name__ == "__main__":
    # Quick test/demo
    print("LNB API Config Test")
    print("=" * 60)

    # Try to load existing config
    headers = load_lnb_headers()
    if headers:
        print(f"\n✅ Loaded {len(headers)} headers:")
        for key in headers:
            value_preview = headers[key][:50] + "..." if len(headers[key]) > 50 else headers[key]
            print(f"  - {key}: {value_preview}")
    else:
        print("\n⚠️  No headers loaded (using defaults)")
        print("\nTo add authentication headers:")
        print("1. Run: save_headers_template()")
        print("2. Fill in template from DevTools")
        print("3. Rename to lnb_headers.json")

    # Optionally create template
    import sys
    if "--create-template" in sys.argv:
        save_headers_template()
