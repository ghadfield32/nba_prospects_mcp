# LNB Play-by-Play and Shot Chart Investigation Summary

## Investigation Period
Date: 2025-11-14 to 2025-11-15

## Objective
Deep dive into the LNB (French basketball league) website to find and extract play-by-play and shot chart data.

##  Key Findings

### 1. API Endpoint Testing ✅ COMPLETE

**Tested 26+ different API endpoint patterns** for match-specific data:

```
TESTED ENDPOINTS (ALL RETURNED HTTP 404):
- /match/getMatchPlayByPlay
- /match/getMatchShots
- /match/getMatchEvents
- /match/getMatchTimeline
- /match/getMatchActions
- /altrstats/getMatchPlayByPlay
- /altrstats/getMatchShots
- /altrstats/getMatchEvents
- /stats/getMatchPlayByPlay
- /stats/getMatchShots
... and 16 more variations
```

**Result**: ❌ **NO direct API endpoints available** for play-by-play or shot chart data.

**Working API Endpoints Found**:
- ✅ `/match/getLiveMatch` - Returns live/upcoming games
- ✅ `/match/getCalenderByDivision` - Returns season schedule
- ✅ `/altrstats/getStanding` - Returns league standings
- ✅ `/altrstats/getPerformancePersonV2` - Returns player stats

### 2. Game Page Navigation Testing ✅ COMPLETE

**Game Tested**: external_id 28910 (Cholet 76 vs Nanterre 78)
**Status in API**: COMPLETE
**Match Date**: 2025-11-14

**URL Patterns Tested**:
```
❌ https://www.lnb.fr/fr/match/28910  → Redirects to home
❌ https://www.lnb.fr/match/28910     → Redirects to home
✅ https://lnb.fr/fr/match/28910      → Returns HTTP 200
❌ (but shows 404 "Page introuvable" error page)
```

**Key Finding**: Game page URLs return HTTP 200 but display "404 Page not found" content, suggesting:
- Games are archived/removed after completion
- Individual game pages may only exist for live/upcoming games
- Historical game data may not be accessible via web pages

### 3. HTML Element Analysis ✅ COMPLETE

**Elements Found on Pages**:
- 17 elements with `class*="events"` → All were UI overlays (modals, search boxes), NOT play-by-play data
- 4 "Événements" (Events) buttons found → Exist but marked as `not visible` (hidden/collapsed)
- 164 SVG elements found → Mostly icons, NOT shot charts (largest had only 9 circles, likely pagination dots)

**Screenshot Evidence**:
- `game_page_28910_success.png` shows "404 Page introuvable" error
- `screenshot_final.png` shows home page after redirect

### 4. Network Request Monitoring ✅ COMPLETE

**Monitored Requests**:
- Total API calls captured: 134
- Game-specific calls (containing game ID): 0
- Match-related endpoints called: 2 (getLiveMatch, getCalenderByDivision)

**Finding**: No game-specific API requests are made when attempting to load a game page, further confirming that individual game data is not available.

### 5. Stats Center Exploration ✅ COMPLETE

**URL Tested**: `https://lnb.fr/fr/stats-centre`
**Status**: Loaded successfully
**Match Links Found**: 0

**Finding**: Stats center does not contain clickable links to individual match pages.

## 🔍 Technical Challenges Identified

1. **Game Page Availability**:
   - Games in API calendar return 404 when accessing their pages
   - Pages may only exist for live/upcoming games, not completed games
   - No way found to access historical game pages

2. **API Limitations**:
   - No endpoints exist for play-by-play data
   - No endpoints exist for shot chart data
   - Match detail endpoints all return 404

3. **JavaScript/Dynamic Content**:
   - "Événements" buttons exist but are not visible/clickable
   - May require specific user interactions or authentication
   - May only appear for live games

4. **Third-Party Stats Provider**:
   - Images/assets served from `altrstat.xyz` domain
   - Stats may be embedded via iframe or external service
   - May require API integration with Altrstat directly

## 📊 Scripts Created During Investigation

1. `explore_lnb_website.py` - Initial website exploration
2. `test_working_endpoints.py` - API endpoint testing
3. `test_match_details.py` - Comprehensive match endpoint testing (26 endpoints)
4. `deep_dive_game_page.py` - Game page element analysis
5. `extract_pbp_structure.py` - Play-by-play structure extraction attempt
6. `extract_pbp_after_click.py` - Button click and data extraction
7. `monitor_game_page_requests.py` - Network request monitoring
8. `navigate_to_game_direct.py` - URL pattern testing
9. `explore_stats_center.py` - Stats center exploration

## 🎯 Conclusions

### Play-by-Play Data
**Status**: ❌ **NOT ACCESSIBLE** via current methods

**Evidence**:
- No API endpoints available
- Game pages return 404
- No HTML elements contain play-by-play data
- No network requests fetch play-by-play data

### Shot Chart Data
**Status**: ❌ **NOT ACCESSIBLE** via current methods

**Evidence**:
- No API endpoints available
- No shot chart SVG elements found (164 SVGs were icons/UI elements)
- No coordinate data found in HTML
- No network requests fetch shot data

## 🤔 Questions for User

1. **Where specifically** did you see play-by-play and shot charts on the LNB website?
   - Was it for a specific game?
   - Was it during a live game?
   - Was it in a different section (not individual match pages)?

2. **When** did you see this data?
   - Recently, or in a previous season?
   - Was the game live at the time?

3. **What type of data** did you see?
   - Detailed play-by-play timeline?
   - Shot chart with coordinates?
   - Box score with quarter breakdowns?

## 💡 Alternative Approaches to Explore

1. **Altrstat API Integration**:
   - Investigate if Altrstat (the third-party provider) has public APIs
   - Check if LNB has a partnership/data agreement with Altrstat

2. **Live Game Monitoring**:
   - Monitor a game while it's LIVE to see if play-by-play appears
   - Check if data is only available during live games

3. **Authentication/Subscription**:
   - Check if detailed stats require login/subscription
   - Investigate if there's a premium tier with more data

4. **Mobile App**:
   - Check if the LNB mobile app has different data access
   - Mobile APIs may differ from web APIs

5. **Broadcast Data**:
   - Games are broadcast on DAZN - they may have play-by-play
   - Check if broadcast providers offer data APIs

## 📁 Output Files Generated

### Analysis Directories:
- `tools/lnb/exploration_output/`
- `tools/lnb/api_responses/`
- `tools/lnb/game_page_analysis/`
- `tools/lnb/pbp_structure_analysis/`
- `tools/lnb/pbp_after_click/`
- `tools/lnb/game_network_monitoring/`
- `tools/lnb/game_page_direct/`
- `tools/lnb/stats_center_exploration/`

### Key Files:
- `api_calls.json` - Captured API requests
- `network_requests_28910.json` - Game page network activity
- `game_page_28910.html` - Full HTML of attempted game page
- `all_api_calls.json` - Comprehensive API call log
- `sample_game.json` - Example game data structure from calendar API
- Screenshots showing 404 errors and redirects

## ⚠️ Current Status

**Play-by-Play Implementation**: ❌ **BLOCKED**
- Cannot proceed without accessible data source

**Shot Chart Implementation**: ❌ **BLOCKED**
- Cannot proceed without accessible data source

**Next Steps**:
1. ✅ Document findings (this summary)
2. ⏳ Update PROJECT_LOG.md
3. ⏸️ **AWAITING USER CLARIFICATION** on where they saw the data
