# NBL Setup - Windows Quick Commands

**Copy-paste these commands in order** ⚡

---

## ✅ Step 1: Verify R is Accessible

```powershell
# Navigate to project
cd C:\docker_projects\betts_basketball\nba_prospects_mcp

# Activate Python environment
& .\.venv\Scripts\Activate.ps1

# Test R (should show version)
Rscript --version
```

**Expected**: `Rscript (R) version 4.5.2 (2025-10-31)`

✅ **If this works**, proceed to Step 2.

❌ **If "command not found"**, run PATH fix:
```powershell
# Option A: Reload PATH in current session
.\tools\nbl\fix_r_path.ps1

# Option B: Close PowerShell and open a NEW window
exit
```

---

## ✅ Step 2: Install R Packages

```powershell
# Run the installer script
Rscript tools/nbl/install_nbl_packages.R
```

**Expected output**:
```
╔════════════════════════════════════════════════════════════════════╗
║           NBL R Package Installer                                  ║
╚════════════════════════════════════════════════════════════════════╝

🔍 Checking installed packages...

📦 Missing packages:
   • nblR
   • dplyr
   • arrow

🚀 Installing from CRAN...
✅ Successfully installed nblR
✅ Successfully installed dplyr
✅ Successfully installed arrow

🎉 SUCCESS! All required packages are now installed
```

⏱️ **Takes**: 2-5 minutes

---

## ✅ Step 3: Validate Full Setup

```powershell
uv run python tools/nbl/validate_setup.py
```

**Expected output**:
```
╔════════════════════════════════════════════════════════════════════╗
║                 NBL R Setup Validation                             ║
╚════════════════════════════════════════════════════════════════════╝

======================================================================
1. Checking R Installation
======================================================================
✅ R is installed: Rscript (R) version 4.5.2

======================================================================
2. Checking R Package Dependencies
======================================================================
✅ R package 'nblR' is installed
✅ R package 'dplyr' is installed
✅ R package 'arrow' is installed

======================================================================
3. Checking Export Script
======================================================================
✅ Export script found: tools\nbl\export_nbl.R

======================================================================
4. Checking Python Dependencies
======================================================================
✅ Python package 'pandas' is installed
✅ Python package 'pyarrow' is installed
✅ Python package 'duckdb' is installed

======================================================================
5. Checking Directory Structure
======================================================================
✅ Export directory exists: data\nbl_raw

======================================================================
Summary
======================================================================
✅ PASS  R Installation
✅ PASS  R Packages
✅ PASS  Export Script
✅ PASS  Python Dependencies
✅ PASS  Directory Structure

Result: 5/5 checks passed

🎉 All checks passed! You're ready to run NBL data export.
```

✅ **All 5 checks must pass** before proceeding.

---

## ✅ Step 4: Export NBL Data

```powershell
uv run nbl-export
```

**What happens**:
- Runs R script to fetch NBL data via nblR package
- Downloads ~10k games since 1979
- Downloads ~500k shot locations with x,y coordinates
- Exports to Parquet files (~500 MB)
- Ingests into DuckDB (~400 MB)

**Expected output** (abbreviated):
```
🏀 NBL Data Export Starting...
============================================================
Step 1/2: Running R export script (nblR package)
------------------------------------------------------------

NBL Export Tool
===============
Output directory: data/nbl_raw

[1/5] Fetching match results since 1979...
[nbl_results] Exporting match results... OK (10234 rows, 12 cols)

[2/5] Fetching player box scores (2015-16+)...
[nbl_box_player] Exporting player box scores... OK (152847 rows, 28 cols)

[3/5] Fetching team box scores (2015-16+)...
[nbl_box_team] Exporting team box scores... OK (3284 rows, 24 cols)

[4/5] Fetching play-by-play data (2015-16+)...
[nbl_pbp] Exporting play-by-play events... OK (2145623 rows, 18 cols)

[5/5] Fetching shot location data (2015-16+)...
[nbl_shots] Exporting shot locations (x,y)... OK (523847 rows, 16 cols)

===============
Export complete!

Step 2/2: Ingesting data into DuckDB
------------------------------------------------------------
✅ NBL official data exported and ingested successfully!
```

⏱️ **Takes**: 10-30 minutes (first time)

---

## ✅ Step 5: Test Your Data

```python
# Start Python
python

# Then run:
from cbb_data.api.datasets import get_dataset

# Get shot chart data (x,y coordinates!)
shots = get_dataset("shots", filters={"league": "NBL", "season": "2024"})
print(f"✅ Loaded {len(shots)} NBL shots with x,y coordinates")

# Get player stats
players = get_dataset("player_season", filters={"league": "NBL", "season": "2024"})
print(f"✅ Loaded {len(players)} NBL players")

# View sample shot data
print(shots[["PLAYER_NAME", "TEAM", "LOC_X", "LOC_Y", "IS_MAKE"]].head())
```

---

## 🚨 Common Issues

### Issue: "Rscript is not recognized"
**Fix**:
```powershell
.\tools\nbl\fix_r_path.ps1
# OR restart PowerShell
```

### Issue: "Error: '\U' used without hex digits"
**Fix**: You're trying to use `R -e '...'` command. Use the installer script instead:
```powershell
Rscript tools/nbl/install_nbl_packages.R
```

### Issue: Package install fails with network error
**Fix**: Check firewall/proxy, or install manually in R console:
```powershell
R
# Then in R:
install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")
```

### Issue: Validation shows 4/5 (R Packages failed)
**Fix**: Re-run the installer:
```powershell
Rscript tools/nbl/install_nbl_packages.R
```

---

## 📚 Full Documentation

- **Quick troubleshooting**: [TROUBLESHOOTING_WINDOWS.md](TROUBLESHOOTING_WINDOWS.md)
- **Detailed setup**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Quick overview**: [QUICKSTART.md](QUICKSTART.md)
- **Complete summary**: [../../NBL_SETUP_SUMMARY.md](../../NBL_SETUP_SUMMARY.md)

---

## 🎯 Success Checklist

- [x] R 4.5.2 installed (`Rscript --version` works)
- [ ] R packages installed (nblR, dplyr, arrow)
- [ ] Validation passes (5/5 checks)
- [ ] NBL data exported (~500 MB Parquet files in `data/nbl_raw/`)
- [ ] Data accessible via `get_dataset("shots", filters={"league": "NBL"})`

---

**Total setup time**: ~15-40 minutes (depending on download speed)

**Result**: Free access to premium NBL data including shot charts ($240/year value)! 🎉
