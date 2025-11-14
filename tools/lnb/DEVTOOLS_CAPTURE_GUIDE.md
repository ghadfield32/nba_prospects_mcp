# LNB API DevTools Capture Guide

## Current Status: 403 Forbidden (Authentication Required)

The LNB API requires authentication via cookies/session tokens. Headers alone are insufficient.

**Test Results (2025-11-14)**:
```
✅ Headers extracted successfully (12 headers)
✅ Endpoint path corrected: /match/getLiveMatch
❌ API returns 403 Forbidden (missing cookies/auth)
```

## How to Capture Working Headers + Cookies

### Step 1: Open Chrome DevTools
1. Open Chrome browser
2. Navigate to: https://www.lnb.fr/statistiques
3. Press F12 to open DevTools
4. Click the **Network** tab
5. Check **Preserve log** (prevents clearing on navigation)
6. Filter by **XHR** or **Fetch** (API requests only)

### Step 2: Trigger API Calls
1. Click around the LNB website to trigger API calls:
   - Click "Statistiques" (Statistics)
   - Click on a player name
   - Click on a team
   - Change season dropdown
   - Click on a match/game
2. Watch the Network tab for requests to `api-prod.lnb.fr`
3. Look for **200 OK** responses (successful calls)

### Step 3: Find a Successful Request
In the Network tab, look for:
- Domain: `api-prod.lnb.fr`
- Status: **200** (green)
- Type: `xhr` or `fetch`
- Method: `GET` or `POST`

Common successful endpoints:
- `/match/getLiveMatch`
- `/stats/getCalendar`
- `/stats/getPlayerStats`
- `/common/getAllYears`

### Step 4: Copy as cURL (with Cookies!)
1. **Right-click** on a successful (200 OK) request
2. Select **Copy** → **Copy as cURL (bash)**
3. This automatically includes:
   - All headers
   - **Cookies** (session tokens)
   - Request method
   - URL with parameters

**CRITICAL**: The cURL command MUST include a `-H 'cookie: ...'` line. If it doesn't, the API won't work.

### Step 5: Test the cURL Command
1. Paste the cURL into a terminal
2. Verify it returns JSON data (not "Access denied")
3. Example successful response:
   ```json
   {"data": [...], "status": "success"}
   ```

### Step 6: Extract to JSON Config
Once you have a **working cURL** (returns 200 with data):

1. Save the cURL to: `tools/lnb/working_headers.curl`
2. Extract headers to JSON format
3. **INCLUDE THE COOKIE HEADER** in the JSON:

```json
{
  "accept": "application/json, text/plain, */*",
  "accept-language": "en-US,en;q=0.9",
  "cookie": "YOUR_ACTUAL_COOKIES_HERE",
  "language_code": "fr",
  "origin": "https://lnb.fr",
  "referer": "https://lnb.fr/fr",
  "sec-ch-ua": "\"Google Chrome\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": "\"Windows\"",
  "sec-fetch-dest": "empty",
  "sec-fetch-mode": "cors",
  "sec-fetch-site": "same-site",
  "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
}
```

4. Save to: `tools/lnb/lnb_headers.json`

### Step 7: Test with Python
Run the test script:
```bash
python3 test_headers_simple.py
```

Expected output:
```
✅ SUCCESS! Got 5 live matches
✅ SUCCESS! Got 10 years
✅ SUCCESS! Got 3 competitions
```

---

## Why Cookies Are Required

Most modern web APIs use cookies for:
1. **Session management**: Tracking your browser session
2. **Authentication**: Verifying you're a legitimate user (not a bot)
3. **Rate limiting**: Preventing abuse
4. **Analytics**: Tracking usage patterns

Without cookies, the API assumes you're an unauthorized bot and returns **403 Forbidden**.

---

## Cookie Expiration

**Important**: Cookies expire! Typical lifetimes:
- Session cookies: Expire when browser closes
- Persistent cookies: 1-7 days (varies by site)
- Auth tokens: 1-24 hours

If the API starts returning 403 again, **recapture fresh cookies** from DevTools.

---

## Alternative: Look for Public Endpoints

Some APIs have public endpoints that don't require auth. Try:
1. Documentation pages (if available)
2. Mobile app API calls (often less restricted)
3. RSS/Atom feeds
4. Public statistics pages

For LNB, we haven't found public endpoints yet. All tested endpoints require authentication.

---

## Security Notes

**DO NOT COMMIT COOKIES TO GIT**:
- Cookies contain session tokens (like passwords)
- Add `lnb_headers.json` to `.gitignore`
- Rotate cookies regularly
- Use environment variables for production

```bash
# Add to .gitignore
echo "tools/lnb/lnb_headers.json" >> .gitignore
echo "src/cbb_data/fetchers/lnb_headers.json" >> .gitignore
```

---

## Next Steps

Once you have working headers with cookies:

1. ✅ Verify endpoints return 200 OK
2. ✅ Test all 47+ endpoints in `lnb_api.py`
3. ✅ Create JSON parsers for each endpoint
4. ✅ Integrate with `lnb.py` (replace placeholders)
5. ✅ Add to dataset registry
6. ✅ Create health check function
7. ✅ Update documentation

---

## Common Issues

### Issue: cURL returns 403 even with cookies
**Cause**: Cookies expired
**Fix**: Capture fresh cookies from browser

### Issue: cURL has no cookie header
**Cause**: Didn't visit the website before capturing
**Fix**: Click around the website first, THEN capture

### Issue: cURL works in terminal but not in Python
**Cause**: Header formatting differences
**Fix**: Verify JSON exactly matches cURL headers (case-sensitive)

### Issue: Different endpoints need different cookies
**Cause**: API uses different auth for different routes
**Fix**: Capture cookies from each endpoint category

---

## Questions?

If you encounter issues:
1. Verify cURL works in terminal first
2. Check that cookie header exists
3. Compare working cURL to JSON config
4. Check cookie expiration dates
5. Try different browsers (Chrome, Firefox)

---

**Last Updated**: 2025-11-14
**Status**: Awaiting fresh cookies from user
