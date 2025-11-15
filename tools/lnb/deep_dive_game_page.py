#!/usr/bin/env python3
"""
Deep dive into LNB match-center pages to capture play-by-play and shot data.

This script navigates to the real LNB match-center URLs (provided by user)
and captures ALL JSON API responses to identify:

- play-by-play (PBP) endpoint(s)
- shot-by-shot (shot chart) endpoint(s)
- pre-match odds / lineups endpoint(s)

Usage:
    uv run python tools/lnb/deep_dive_game_page.py
"""

import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Console encoding fix (Windows)
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print("=" * 80)
print("  LNB Match Center Deep Dive - CAPTURE JSON for PBP & SHOTS")
print("=" * 80)
print()

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

output_dir = Path(__file__).parent / "match_center_capture"
output_dir.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# URLs provided by you (KEEP these unless LNB changes)
# ---------------------------------------------------------------------------

URLS_TO_TEST = {
    "pre_match": {
        "url": "https://lnb.fr/fr/pre-match-center?mid=0d2989af-6715-11f0-b609-27e6e78614e1",
        "description": "Pre-match center (odds, lineups, etc.)",
        "match_id": "0d2989af-6715-11f0-b609-27e6e78614e1",
    },
    "match_center_pbp": {
        "url": "https://lnb.fr/fr/match-center/3522345e-3362-11f0-b97d-7be2bdc7a840?&~w=f~eJwtjEEKhDAMAL8iORtIGmNbH-AD_EFr2pMH2b0p_l0C3mZgmBv-sAxgXZgKKSoXQ-ZOWC1l3KOoUmrcKMM4wOFx_-G6uV1uZz2du7NoCDJpQ5E5fJscDWNtodoeS5oInhdqtRxC",
        "description": "Match center - (initial) view",
        "match_id": "3522345e-3362-11f0-b97d-7be2bdc7a840",
    },
    "match_center_shots": {
        "url": "https://lnb.fr/fr/match-center/3522345e-3362-11f0-b97d-7be2bdc7a840?%7Ew=f%7EeJwtjMEJwzAMAFcJelcgWVFtd4AO0AWCbdnkUSgkeTVk9yLo847jTtjhMYENYSqkqFwMmQdhtZSxRVGl1LlThtsEb4_Hhs-X09dpXz_H0tayHa6GK9EQZNaOIvfwv-VoGGsP1VosaSa4fncmHy8",
        "description": "Match center - alternate state (used to probe shots/PBP)",
        "match_id": "3522345e-3362-11f0-b97d-7be2bdc7a840",
    },
}

# ---------------------------------------------------------------------------
# Capture configuration
# ---------------------------------------------------------------------------

# Set to None to capture ALL JSON hosts.
# If you want to restrict later, set to a list of substrings, e.g.:
# ALLOWED_HOST_KEYWORDS = ["lnb", "api-prod.lnb.fr"]
ALLOWED_HOST_KEYWORDS = None

response_counter = 0
current_page_type = "unknown"
current_section = "initial"  # "initial" / "pbp" / "shots" / "other"


def host_allowed(host: str) -> bool:
    """Return True if this host should be captured."""
    if ALLOWED_HOST_KEYWORDS is None:
        return True
    host = host.lower()
    return any(key.lower() in host for key in ALLOWED_HOST_KEYWORDS)


def save_api_response(
    url: str, data: object, page_type: str, response_type: str, section: str
) -> str:
    """Save API response to a JSON file with metadata."""
    global response_counter
    response_counter += 1

    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path.replace("/", "_").strip("_") or "root"

    timestamp = datetime.now().strftime("%H%M%S")
    filename = (
        f"{page_type}_{section}_{response_type}_{path[:40]}_{timestamp}_{response_counter}.json"
    )

    payload = {
        "url": url,
        "host": host,
        "path": parsed.path,
        "page_type": page_type,
        "section": section,
        "response_type": response_type,
        "timestamp": timestamp,
        "data": data,
    }

    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return filename


print("Starting browser automation…")
print()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="fr-FR",
        timezone_id="Europe/Paris",
        viewport={"width": 1920, "height": 1080},
    )
    page = context.new_page()

    # -----------------------------------------------------------------------
    # Network response handler
    # -----------------------------------------------------------------------

    def handle_response(response):
        """Capture ALL JSON API responses from any host (optionally filtered)."""
        url = response.url
        parsed = urlparse(url)
        host = parsed.netloc

        if not host_allowed(host):
            return

        try:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type.lower():
                return

            data = response.json()

            # Basic classification by URL / structure
            url_l = url.lower()
            response_type = "unknown"
            highlight = False

            # PBP-ish endpoints
            if any(kw in url_l for kw in ["play", "event", "action", "timeline", "pbp"]):
                response_type = "PLAY_BY_PLAY"
                highlight = True

            # Shot-ish endpoints
            if any(kw in url_l for kw in ["shot", "tir", "shoot", "fieldgoal", "fg"]):
                response_type = "SHOTS"
                highlight = True

            # Other useful ones
            if any(
                kw in url_l
                for kw in ["matchdetails", "matchdetail", "getmatchdetails", "match-info"]
            ):
                response_type = "match_details"
            if any(kw in url_l for kw in ["boxscore", "matchstats", "stats"]):
                if response_type == "unknown":
                    response_type = "boxscore"
            if any(kw in url_l for kw in ["odd", "bet", "cote"]):
                response_type = "odds"

            filename = save_api_response(
                url, data, current_page_type, response_type, current_section
            )

            short_host = host.split(":")[0]
            short_path = parsed.path

            if highlight:
                print("\n" + "=" * 80)
                print(f"🎯 FOUND {response_type} DATA!")
                print("=" * 80)
                print(f"Page type : {current_page_type}")
                print(f"Section   : {current_section}")
                print(f"Host      : {short_host}")
                print(f"Path      : {short_path}")
                print(f"Status    : {response.status}")
                print(f"Saved     : {filename}")
                if isinstance(data, dict):
                    print(f"Top-level keys: {list(data.keys())[:12]}")
                    if "data" in data:
                        inner = data["data"]
                        if isinstance(inner, list) and inner:
                            print(
                                f" - data: list[{len(inner)}], first keys: {list(inner[0].keys())[:10]}"
                            )
                        elif isinstance(inner, dict):
                            print(f" - data: dict keys: {list(inner.keys())[:15]}")
                print()
            else:
                print(
                    f"[API] {current_page_type}/{current_section} -> {short_host}{short_path} ({response_type})"
                )

        except Exception as e:
            print(f"[ERROR] Processing response from {url}: {e!r}")

    page.on("response", handle_response)

    # -----------------------------------------------------------------------
    # OPTIONAL: websocket capture (if they push live data this way)
    # -----------------------------------------------------------------------
    # Commented for now to keep noise down; you can enable if needed.
    """
    def handle_websocket(ws):
        print(f"[WS OPEN] {ws.url}")

        def on_frame(msg):
            try:
                text = msg["payload"]
                # Many providers use JSON text frames
                if isinstance(text, str) and text.strip().startswith("{"):
                    data = json.loads(text)
                    filename = save_api_response(ws.url, data, current_page_type, "WEBSOCKET", current_section)
                    print(f"[WS JSON] Saved websocket frame to {filename}")
            except Exception:
                pass

        ws.on("framereceived", on_frame)

    page.on("websocket", handle_websocket)
    """

    # -----------------------------------------------------------------------
    # Helper to click tabs safely
    # -----------------------------------------------------------------------

    def click_tab(
        label: str, selectors: list[str], section_tag: str, wait_seconds: int = 6
    ) -> bool:
        """Try a list of selectors to activate a tab, set section_tag while it loads."""
        global current_section

        for sel in selectors:
            try:
                locator = page.locator(sel)
                if not locator.first.is_visible():
                    continue

                text_preview = locator.first.inner_text()[:40].strip()
                print(f"[CLICK] Trying {label} via '{sel}' ({text_preview!r})")
                current_section = section_tag
                locator.first.click()
                time.sleep(wait_seconds)
                print(f"[OK] {label} tab active (section={section_tag})")
                return True
            except Exception:
                # Just keep trying alternatives
                # print(f"[WARN] Failed '{sel}' for {label}: {e!r}")
                continue

        print(f"[WARN] Could not find visible tab for {label}")
        return False

    # -----------------------------------------------------------------------
    # Visit each URL and exercise relevant interactions
    # -----------------------------------------------------------------------

    for page_key, page_info in URLS_TO_TEST.items():
        current_page_type = page_key
        current_section = "initial"

        print()
        print("=" * 80)
        print(f"  Testing: {page_info['description']} ({page_key})")
        print("=" * 80)
        print(f"URL      : {page_info['url']}")
        print(f"Match ID : {page_info['match_id']}")
        print()

        try:
            print(f"[LOAD] Navigating to {page_key} …")
            resp = page.goto(page_info["url"], wait_until="networkidle", timeout=60000)
            print(f"[STATUS] HTTP {resp.status}")
            print(f"[TITLE]  {page.title()}")
            print(f"[FINAL]  {page.url}")
            print()

            print("[WAIT] Letting initial content load (10s)…")
            time.sleep(10)

            # Screenshot + HTML for debugging
            screenshot_path = output_dir / f"{page_key}_screenshot.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"[SAVED] Screenshot: {screenshot_path.name}")

            html_path = output_dir / f"{page_key}_page.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"[SAVED] HTML      : {html_path.name}")
            print()

            # Interactions for match-center pages
            if "match_center" in page_key:
                print("[INTERACT] Looking for PLAY BY PLAY and POSITIONS TIRS tabs…")

                # 1) PLAY BY PLAY tab (PBP)
                click_tab(
                    "PLAY BY PLAY",
                    selectors=[
                        'role=tab[name="PLAY BY PLAY"]',
                        "text=PLAY BY PLAY",
                        'button:has-text("PLAY BY PLAY")',
                    ],
                    section_tag="pbp",
                )

                # 2) POSITIONS TIRS tab (shots)
                click_tab(
                    "POSITIONS TIRS",
                    selectors=[
                        'role=tab[name="POSITIONS TIRS"]',
                        "text=POSITIONS TIRS",
                        'button:has-text("POSITIONS TIRS")',
                        "text=POSITIONS TIR",
                    ],
                    section_tag="shots",
                )

                # 3) Cycle through quarters a bit (still in 'shots' section)
                current_section = "shots"
                print("[INTERACT] Cycling quarter buttons (Q1–Q4/TOUTE)…")
                quarter_selectors = [
                    'button:has-text("Q1")',
                    'button:has-text("Q2")',
                    'button:has-text("Q3")',
                    'button:has-text("Q4")',
                    'button:has-text("TOUTE")',
                    'button:has-text("1er")',
                    'button:has-text("2ème")',
                    'button:has-text("3ème")',
                    'button:has-text("4ème")',
                ]
                for sel in quarter_selectors:
                    try:
                        loc = page.locator(sel)
                        if loc.first.is_visible():
                            txt = loc.first.inner_text().strip()
                            print(f"  [CLICK] Quarter '{txt}'")
                            loc.first.click()
                            time.sleep(2)
                    except Exception:
                        continue

            print(f"[COMPLETE] Finished {page_key}")
            print()

        except Exception as e:
            print(f"[ERROR] Failed to load {page_key}: {e!r}")

    browser.close()

print()
print("=" * 80)
print("  BROWSER CAPTURE COMPLETE")
print("=" * 80)
print(f"Total JSON responses captured: {response_counter}")
print(f"Saved to: {output_dir}")
print()

print("Next: run debug_response_analyzer.py to locate PBP/shot JSON.")
print()
