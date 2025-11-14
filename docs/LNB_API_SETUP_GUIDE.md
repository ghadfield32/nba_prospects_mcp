# LNB API Setup Guide

## Overview

This guide explains how to use the LNB API client for accessing official French basketball (Betclic ÉLITE / LNB Pro A) data from api-prod.lnb.fr.

**Current Status**: ⚠️ **API requires additional authentication headers**

The stress test revealed that `api-prod.lnb.fr` returns **403 Forbidden** errors with basic headers. The API requires additional security headers, cookies, or tokens that are set when accessing the website through a browser.

## Quick Start (After Header Capture)

```python
from src.cbb_data.fetchers.lnb_api import LNBClient

# Create client
client = LNBClient()

# Get available seasons
years = client.get_all_years(end_year=2025)

# Get competitions for a year
comps = client.get_main_competitions(year=2024)

# Get teams
teams = client.get_competition_teams(competition_external_id=302)

# Get schedule
from datetime import date
games = client.get_calendar(
    from_date=date(2024, 11, 1),
    to_date=date(2024, 11, 30)
)

# Run comprehensive test
from src.cbb_data.fetchers.lnb_api import stress_test_lnb
results = stress_test_lnb(seasons_back=2, max_matches_per_season=5)
```

## Problem: 403 Forbidden Errors

### What We Observed

When running the stress test, ALL endpoints return:
```
HTTPError('403 Client Error: Forbidden for url: https://api-prod.lnb.fr/...')
```

### What This Means

The API has anti-bot protections that reject requests without proper authentication. Possible requirements:

1. **Origin header**: Must match the LNB website origin
2. **Cookies**: Session cookies or auth tokens set by the website
3. **CSRF tokens**: Anti-CSRF tokens in headers or cookies
4. **Additional headers**: X-Requested-With, custom security headers
5. **TLS fingerprinting**: API may check TLS/SSL handshake fingerprints

### Current Headers (Not Working)

```python
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Referer": "https://www.lnb.fr/",
}
```

## Solution: Capture Real Headers from DevTools

### Step 1: Open DevTools

1. Open Chrome/Firefox
2. Navigate to: https://www.lnb.fr/statistiques
3. Open DevTools (F12)
4. Go to **Network** tab
5. Filter by: **XHR** or **Fetch**

### Step 2: Trigger API Calls

Navigate to the Stats Center and click through tabs:
- **Calendar** → Triggers `getCalendar`
- **Competition standings** → Triggers `getMainCompetition`
- **Team pages** → Triggers `getCompetitionTeams`
- **Match pages** → Triggers match context endpoints

### Step 3: Capture Request Headers

For each successful XHR request to `api-prod.lnb.fr`:

1. Click the request in Network tab
2. Go to **Headers** section
3. Copy **Request Headers** (all of them!)

Example of what to capture:

```http
GET /common/getAllYears?end_year=2025 HTTP/1.1
Host: api-prod.lnb.fr
Connection: keep-alive
Accept: application/json, text/plain, */*
User-Agent: Mozilla/5.0 ...
Origin: https://www.lnb.fr
Referer: https://www.lnb.fr/statistiques
Accept-Encoding: gzip, deflate, br
Accept-Language: en-US,en;q=0.9
Cookie: <SESSION_COOKIES_HERE>
X-Requested-With: XMLHttpRequest  (if present)
Authorization: Bearer <TOKEN>  (if present)
```

### Step 4: Update LNBClient Headers

Edit `src/cbb_data/fetchers/lnb_api.py`:

```python
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
    "Referer": "https://www.lnb.fr/statistiques",
    "Origin": "https://www.lnb.fr",  # ADD THIS
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    # ADD ANY OTHER HEADERS YOU SEE IN DEVTOOLS
}
```

### Step 5: Handle Cookies

If cookies are required, you have two options:

#### Option A: Extract and Hardcode Cookies (Quick but temporary)

```python
# In lnb_api.py, update DEFAULT_HEADERS:
DEFAULT_HEADERS = {
    ...
    "Cookie": "session=abc123; auth_token=xyz789; ...",  # From DevTools
}
```

⚠️ **Warning**: Cookies expire! This is only for testing.

#### Option B: Session Management (Proper solution)

1. **Option B1: Selenium** - Use Selenium to login and capture cookies:

```python
from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://www.lnb.fr/statistiques")
# Wait for page load
time.sleep(5)

# Extract cookies
cookies = driver.get_cookies()
driver.quit()

# Use cookies in requests session
session = requests.Session()
for cookie in cookies:
    session.cookies.set(cookie['name'], cookie['value'])
```

2. **Option B2: Playwright** - Similar to Selenium but modern:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.lnb.fr/statistiques")

    # Extract cookies
    cookies = page.context.cookies()
    browser.close()

# Use cookies in requests session
```

### Step 6: Test Again

```bash
python3 src/cbb_data/fetchers/lnb_api.py
```

Look for:
- ✅ **Success**: Endpoints return data
- ❌ **Still 403**: Need more headers or different approach

## Alternative Approaches (If Headers Don't Work)

### 1. Selenium/Playwright Full Browser Automation

Instead of hitting the API directly, automate a browser:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    # Navigate and extract data from rendered page
    page.goto("https://www.lnb.fr/statistiques")
    page.click("text=Calendar")

    # Wait for API call to complete (watch network)
    page.wait_for_response("**/api-prod.lnb.fr/stats/getCalendar")

    # Extract data from DOM
    data = page.locator(".game-list").all_text_contents()
```

**Pros**: Bypasses API restrictions completely
**Cons**: Slower, more fragile, requires browser installation

### 2. Reverse Proxy / MITM

Capture ALL traffic (including encrypted) using mitmproxy:

```bash
pip install mitmproxy
mitmproxy --mode reverse:https://api-prod.lnb.fr
```

Then browse www.lnb.fr with proxy configured, and mitmproxy will show you:
- Exact headers
- Cookie flow
- CSRF tokens
- TLS details

### 3. Contact LNB for Official API Access

If the data is meant to be public, LNB might provide:
- Official API keys
- Developer documentation
- Terms of service for data usage

## File Structure

```
nba_prospects_mcp/
├── src/
│   └── cbb_data/
│       └── fetchers/
│           ├── lnb.py           # High-level DataFrame interface
│           └── lnb_api.py       # Low-level API client (THIS FILE)
├── tests/
│   └── test_lnb_api_stress.py  # Comprehensive endpoint tests
├── docs/
│   └── LNB_API_SETUP_GUIDE.md  # This guide
└── lnb_stress_test_output.txt  # Latest test results
```

## Current Endpoint Catalog

### ✅ Implemented (waiting for headers)

**Structure Discovery:**
- `GET /common/getAllYears?end_year=YYYY`
- `GET /common/getMainCompetition?year=YYYY`
- `GET /common/getDivisionCompetitionByYear?year=YYYY&division_external_id=N`
- `GET /stats/getCompetitionTeams?competition_external_id=N`

**Schedule:**
- `POST /stats/getCalendar` (JSON: `{from: date, to: date}`)

**Match Context:**
- `GET /stats/getTeamComparison?match_external_id=N`
- `GET /stats/getLastFiveMatchesHomeAway?match_external_id=N`
- `GET /stats/getLastFiveMatchesHeadToHead?match_external_id=N`
- `GET /stats/getMatchOfficialsPreGame?match_external_id=N`

**Season Stats:**
- `GET /stats/getPersonsLeaders?competition_external_id=N&year=YYYY&...`

**Live:**
- `GET /stats/getLiveMatch`

### ⚠️ Placeholders (need DevTools path discovery)

- **Boxscore**: Unknown path (player_game, team_game stats)
- **Play-by-Play**: Unknown path (event stream)
- **Shot Chart**: Unknown path (x,y coordinates)

## Next Steps

1. ✅ **You're here**: Read this guide
2. ⏭️ **Capture headers**: Use DevTools to capture working request headers
3. ⏭️ **Update client**: Add headers to `DEFAULT_HEADERS` in `lnb_api.py`
4. ⏭️ **Retest**: Run `python3 src/cbb_data/fetchers/lnb_api.py`
5. ⏭️ **Discover boxscore/PBP**: Once API works, find missing endpoint paths
6. ⏭️ **Integrate**: Update `lnb.py` to use `lnb_api.py` internally

## Stress Test Results

Last run: 2025-11-14 19:47:53 UTC

```
Endpoint Health Summary:
❌ getAllYears                     0 OK /   1 FAIL (  1 total)
❌ getMainCompetition              0 OK /   2 FAIL (  2 total)
❌ getDivisionCompetitionByYear    0 OK /   2 FAIL (  2 total)
❌ getLiveMatch                    0 OK /   1 FAIL (  1 total)

Status: ALL endpoints returning 403 Forbidden
Diagnosis: Missing authentication headers or cookies
Solution: Capture real headers from browser DevTools
```

## Questions?

- **Q: Why 403 errors?**
  A: API requires authentication headers that browsers add automatically.

- **Q: Is this legal/ethical?**
  A: If data is publicly visible on www.lnb.fr, you're accessing public data. Check LNB's Terms of Service. Don't overload their servers.

- **Q: Can I just scrape HTML instead?**
  A: Yes! The existing `lnb.py` does this for standings. But API is cleaner and more reliable.

- **Q: Will cookies expire?**
  A: Yes. You'll need to refresh them periodically or use Selenium for automated session management.

- **Q: What about rate limiting?**
  A: Be respectful! The client has built-in retry_sleep (0.25s default). Don't spam requests.

## Resources

- LNB Official Site: https://www.lnb.fr/
- Stats Center: https://www.lnb.fr/statistiques
- Chrome DevTools Network Tab: https://developer.chrome.com/docs/devtools/network/
- Playwright (browser automation): https://playwright.dev/python/
- mitmproxy (traffic capture): https://mitmproxy.org/

---

**Created**: 2025-11-14
**Status**: Waiting for user to capture headers from DevTools
**Next Update**: After successful API authentication
