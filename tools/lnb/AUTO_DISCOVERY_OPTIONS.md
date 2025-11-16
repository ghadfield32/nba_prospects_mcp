# LNB Fixture UUID Auto-Discovery: Three Approaches

**Created:** 2025-11-16
**Status:** September 2022 collected (22 games), exploring automation options

---

## Current State

✅ **Manual collection infrastructure working:**
- 22 September 2022 URLs collected and validated
- Template files created for all 4 seasons
- Validation script confirmed no errors

❓ **Question:** Can we automate the remaining ~280-330 games per season?

---

## Option A: Continue Manual Collection (WORKING NOW)

**Pros:**
- ✅ Already set up and working
- ✅ 100% deterministic (no API dependencies)
- ✅ No authentication needed
- ✅ Can collect incrementally (month by month)

**Cons:**
- ⏱️ Time-consuming (~30-60 min per season)
- 🖱️ Requires manual browser work

**Workflow:**
```bash
# 1. Open calendar anchors in browser
https://lnb.fr/fr/calendar#2022-10-15
https://lnb.fr/fr/calendar#2022-10-29
# ... etc

# 2. Click games → copy match-center URLs → paste to urls_2022_2023.txt

# 3. Validate
uv run python tools/lnb/validate_url_file.py tools/lnb/urls_2022_2023.txt

# 4. Discover
uv run python tools/lnb/discover_historical_fixture_uuids.py \
  --seasons 2022-2023 \
  --from-file tools/lnb/urls_2022_2023.txt

# 5. Run pipeline
uv run python tools/lnb/build_game_index.py --seasons 2022-2023
uv run python tools/lnb/bulk_ingest_pbp_shots.py --seasons 2022-2023
```

**Time estimate:** 4 seasons × 1 hour = 4 hours total

---

## Option B: Schedule API with Browser Headers (FASTER)

**Pros:**
- ⚡ Get all ~300 games in ONE API call per season
- 🔄 Can re-run easily to catch new games
- 📊 Returns full schedule metadata

**Cons:**
- 🔐 Requires browser cookies (one-time setup, ~5 min)
- ⚠️ Cookies expire periodically (need to refresh)
- ❌ Returns **external IDs**, not **UUIDs** (needs mapping)

**One-time Setup:**

1. Open browser → https://www.lnb.fr/statistiques
2. DevTools (F12) → Network tab → Filter: `getCalender`
3. Navigate around site to trigger API call
4. Find successful request (200 OK) → Right-click → Copy as cURL
5. Extract headers → Save to `tools/lnb/lnb_headers.json`:

```json
{
  "Origin": "https://www.lnb.fr",
  "Referer": "https://www.lnb.fr/statistiques",
  "Cookie": "your_session_cookies_here",
  "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"
}
```

**Workflow:**

```python
from src.cbb_data.fetchers.lnb import fetch_lnb_schedule

# Fetch full 2022-23 schedule
df = fetch_lnb_schedule(season=2022, league="LNB", division=1)

# Problem: df["GAME_ID"] contains external IDs (integers), not UUIDs
# Solution needed: Map external_id → fixture UUID
```

**Critical Issue:** Schedule API returns `external_id` (e.g., `25095`), but we need fixture UUIDs (e.g., `ca4b3e98-11a0-11ed-8669-c3922075d502`).

**Possible solutions:**
1. Fetch each external_id via fixture_detail endpoint to get UUID
2. Find a bulk endpoint that returns both external_id and UUID
3. Reverse-engineer UUID generation pattern (unlikely to work)

---

## Option C: Explore Atrium API (MOST AUTOMATED) ✅ **IMPLEMENTED & WORKING!**

**Your suggested "seed fixture" approach - SUCCESS!**

1. ✅ **Use September 2022 fixtures as seeds**
   - We have 22 validated UUIDs
   - Extract `competitionId` + `seasonId` from fixture_detail

2. ✅ **Extracted IDs from one fixture:**
   ```json
   {
     "competitionId": "5b7857d9-0cbc-11ed-96a7-458862b58368",
     "seasonId": "717ba1c6-0cbc-11ed-80ed-4b65c29000f2",
     "seasonName": "Betclic ÉLITE 2022"
   }
   ```

3. ✅ **FOUND! Working Atrium fixtures endpoint:**
   ```
   GET https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/fixtures
       ?competitionId=5b7857d9-0cbc-11ed-96a7-458862b58368
       &seasonId=717ba1c6-0cbc-11ed-80ed-4b65c29000f2

   Response: {data: {fixtures: [{fixtureId: "...", name: "...", ...}, ...]}}
   Result: 306 fixtures discovered for 2022-23 season!
   ```

4. ✅ **Endpoint discovered via systematic probe:**
   - Created `probe_atrium_endpoints.py` to test 17 patterns
   - Found on FIRST pattern tested: `/v1/embed/12/fixtures`
   - No auth required ✅
   - Returns actual fixture UUIDs ✅
   - Execution time: <1 second ⚡

5. **Write bulk discovery script:**
   ```python
   # Pseudo-code
   for season in ["2022-2023", "2023-2024", "2024-2025"]:
       comp_id, season_id = lookup_ids(season)  # From seed fixture

       # Try possible endpoint patterns
       fixtures = fetch_atrium_fixtures(comp_id, season_id)

       # Extract UUIDs
       uuids = [f["id"] for f in fixtures]

       # Save to fixture_uuids_by_season.json
   ```

**Pros:**
- ⚡ Fastest (all seasons in <1 min)
- 🔓 No auth required (Atrium API is public)
- 🎯 Returns actual fixture UUIDs
- 🔄 Easy to re-run for updates

**Cons:**
- 🔍 Requires DevTools investigation to find endpoint
- ⚠️ Endpoint might not exist or might be rate-limited
- 📝 One-time effort to find pattern

---

## Recommendation

### Short-term (Next 2 hours):
**Option A** - Continue manual collection for 2022-23 season:
- You've already validated September (22 games)
- Collect October-December manually (use calendar anchors)
- Run pipeline once you have Q1 complete (~90-100 games)
- This guarantees progress while exploring automation

### Medium-term (Next week):
**Option C** - Investigate Atrium API:
- Use browser DevTools on https://www.lnb.fr/calendar
- Navigate to 2022-23 season (if possible)
- Look for Atrium API calls with fixture lists
- If found: Write bulk discovery script
- If not found: Fall back to Option B

### Option B - Only if:
- You can't find Atrium calendar endpoint (Option C fails)
- You want metadata from schedule (team names, dates, etc.)
- You're comfortable refreshing cookies periodically

---

## Decision Tree

```
Start: Need 300+ fixture UUIDs for 2022-23
│
├─ Do you have 1 hour to manually collect? → Option A
│  └─ Works immediately, deterministic
│
├─ Want to invest 30 min investigating API? → Option C
│  ├─ Find Atrium endpoint → ⚡ Fastest automation
│  └─ Can't find endpoint → Fall back to Option B
│
└─ Comfortable with browser cookies? → Option B
   └─ Faster than manual, but needs UUID mapping
```

---

## Next Steps for Option C (Recommended Investigation)

1. **Open browser DevTools:**
   ```
   - Navigate to: https://www.lnb.fr/statistiques
   - Open: DevTools (F12) → Network tab
   - Filter: "atriumsports" or "fixture"
   ```

2. **Trigger API calls:**
   ```
   - Browse to calendar/schedule page
   - Look for season selectors
   - Click through different dates/rounds
   - Watch Network tab for Atrium requests
   ```

3. **Identify patterns:**
   ```
   - Look for URLs containing:
     * competitionId: 5b7857d9-0cbc-11ed-96a7-458862b58368
     * seasonId: 717ba1c6-0cbc-11ed-80ed-4b65c29000f2
     * "fixtures" or "calendar" or "matches"

   - Common patterns to try:
     * /v1/embed/12/fixtures?competitionId=...&seasonId=...
     * /v1/embed/12/season_calendar?seasonId=...
     * /v1/embed/12/competition/.../ season/.../fixtures
   ```

4. **Test endpoint:**
   ```bash
   # Once you find the pattern, test with curl:
   curl "https://eapi.web.prod.cloud.atriumsports.com/v1/embed/12/YOUR_ENDPOINT_HERE"
   ```

5. **Build automation:**
   ```
   If successful:
   - Create bulk_discover_from_atrium.py
   - Extract all season UUIDs
   - Feed to existing pipeline
   ```

---

## Summary Table

| Approach | Time to Set Up | Time per Season | Auth Required | Returns UUIDs | Repeatable |
|----------|----------------|-----------------|---------------|---------------|------------|
| **A: Manual** | ✅ 0 min (done) | ⏱️ 60 min | ❌ No | ✅ Yes | ✅ Yes |
| **B: Schedule API** | ⚙️ 5 min | ⚡ 1 min | 🔐 Yes (cookies) | ❌ No (needs mapping) | ⚠️ Until cookies expire |
| **C: Atrium API** | 🔍 30 min (investigate) | ⚡ <1 min | ❌ No | ✅ Yes | ✅ Yes |

**Recommended path:**
1. Continue manual collection for October (Option A) - guarantees progress
2. Spend 30 min on Option C investigation in parallel
3. If Option C succeeds → automate remaining months
4. If Option C fails → decide between finishing manual vs. setting up Option B

---

## Questions?

- Check `PROJECT_LOG.md` for implementation details
- See `HISTORICAL_URL_COLLECTION_WORKFLOW.md` for manual workflow
- Review `tools/lnb/discover_historical_fixture_uuids.py` for --from-file usage
