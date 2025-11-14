# NBL Setup Troubleshooting - Windows Specific Issues

## 🔴 Problem: "R is not recognized as an internal or external command"

### Root Cause

When you install R on Windows, the installer adds R to your system PATH. **However**, your current PowerShell session has a **cached copy** of the PATH from when it was opened. This cached PATH doesn't include R yet.

### Why This Happens

```
1. You open PowerShell
   → PowerShell loads PATH from registry
   → PATH does NOT include R (R not installed yet)

2. You run: winget install RProject.R
   → R installs successfully
   → Installer updates registry PATH
   → But PowerShell still has the OLD cached PATH

3. You run: Rscript --version
   → PowerShell searches in its cached PATH
   → R's bin directory not in cached PATH
   → Error: "Rscript is not recognized"
```

---

## ✅ Solutions (Choose One)

### **Solution 1: Restart PowerShell** ⭐ EASIEST

This is the simplest and most reliable solution:

1. **Close your current PowerShell window completely** (X button or type `exit`)
2. **Open a NEW PowerShell window**
3. **Navigate back to your project**:
   ```powershell
   cd C:\docker_projects\betts_basketball\nba_prospects_mcp
   ```
4. **Test R**:
   ```powershell
   Rscript --version
   ```

**Expected output**:
```
R scripting front-end version 4.5.2 (2025-01-10)
```

✅ If you see this, R is working! Skip to [Next Steps](#next-steps)

---

### **Solution 2: Reload PATH in Current Session** ⭐ NO RESTART NEEDED

If you don't want to restart PowerShell, run this command to reload PATH:

```powershell
.\tools\nbl\fix_r_path.ps1
```

**OR** manually reload PATH:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

Then test:
```powershell
Rscript --version
```

---

### **Solution 3: Run Diagnostic Script** ⭐ FULL DIAGNOSIS

If the above solutions don't work, run our comprehensive diagnostic:

```powershell
.\tools\nbl\debug_r_installation.ps1
```

This script will:
- ✅ Find where R is installed
- ✅ Check if R is in system PATH
- ✅ Check if R is in user PATH
- ✅ Test if R commands work
- ✅ Offer to fix PATH automatically

---

## 🎯 Next Steps (After R Works)

Once `Rscript --version` works, proceed with these steps:

### 1. Install R Packages (2-3 minutes)

**Use the installer script** (recommended - avoids Windows quoting issues):

```powershell
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

🚀 Installing from CRAN (https://cloud.r-project.org)...
...
✅ Successfully installed nblR
✅ Successfully installed dplyr
✅ Successfully installed arrow

🎉 SUCCESS! All required packages are now installed
```

**OR manually in R console** (if the script has issues):

```powershell
# Open R console
R

# Then inside R:
install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")
```

### 2. Validate Full Setup

```powershell
uv run python tools/nbl/validate_setup.py
```

**Expected output**:
```
✅ PASS  R Installation
✅ PASS  R Packages
✅ PASS  Export Script
✅ PASS  Python Dependencies
✅ PASS  Directory Structure

Result: 5/5 checks passed

🎉 All checks passed! You're ready to run NBL data export.
```

### 3. Export NBL Data (10-30 minutes first time)

```powershell
uv run nbl-export
```

---

## 🐛 Common Issues & Fixes

### Issue: "Error: '\U' used without hex digits in character string"

**Cause**: Windows paths like `C:\Users\...` contain `\U` which R interprets as a Unicode escape sequence. When using `R -e '...'` in PowerShell, the path gets passed to R and causes a parse error.

**Fix**: Use the installer script instead (no quoting issues):

```powershell
# ✅ Recommended (avoids all quoting problems)
Rscript tools/nbl/install_nbl_packages.R
```

**OR** run from R console directly:

```powershell
# Open R console
R

# Then inside R:
install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")
```

**Technical explanation**: The `R -e '...'` command on Windows has complex quoting rules. PowerShell, cmd, and R each interpret special characters differently. Using a dedicated R script (`Rscript file.R`) avoids this entirely.

---

### Issue: "Error: package 'nblR' is not available"

**Cause**: CRAN mirror not set or package name typo.

**Fix**: Specify the repos explicitly:

```r
install.packages(c("nblR", "dplyr", "arrow"), repos="https://cloud.r-project.org")
```

---

### Issue: "Warning: cannot remove prior installation of package"

**Cause**: Package is loaded in another R session.

**Fix**: Close all R sessions/RStudio and try again.

---

### Issue: Validation shows "R Packages check: [WinError 2]"

**Cause**: R is not accessible yet (PATH issue).

**Fix**: Follow [Solutions](#-solutions-choose-one) above to fix PATH first.

---

## 🔍 Debugging Commands

### Check where R is installed:

```powershell
Get-ChildItem "C:\Program Files\R" -Recurse -Filter "Rscript.exe" | Select-Object FullName
```

### Check current PATH:

```powershell
$env:Path -split ';' | Where-Object { $_ -like "*R*" }
```

### Check system PATH (registry):

```powershell
[System.Environment]::GetEnvironmentVariable("Path", "Machine") -split ';' | Where-Object { $_ -like "*R*" }
```

### Check user PATH (registry):

```powershell
[System.Environment]::GetEnvironmentVariable("Path", "User") -split ';' | Where-Object { $_ -like "*R*" }
```

---

## 📊 Diagnostic Scripts Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `fix_r_path.ps1` | Quick PATH reload | R installed but not recognized |
| `debug_r_installation.ps1` | Full diagnostic + auto-fix | PATH reload didn't work |
| `validate_setup.py` | Validate entire NBL setup | After R packages installed |

---

## 🆘 Still Not Working?

If none of the above solutions work:

1. **Completely uninstall R**:
   ```powershell
   winget uninstall RProject.R
   ```

2. **Restart your computer** (ensures clean PATH)

3. **Reinstall R**:
   ```powershell
   winget install RProject.R
   ```

4. **Open a NEW PowerShell** (critical!)

5. **Test immediately**:
   ```powershell
   Rscript --version
   ```

---

## ✅ Success Indicators

You'll know everything is working when:

1. ✅ `Rscript --version` shows R version
2. ✅ `R --version` shows R version
3. ✅ `validate_setup.py` shows 5/5 checks passed
4. ✅ `uv run nbl-export` starts downloading data

---

## 📚 Additional Resources

- **R Official Site**: https://cran.r-project.org/
- **R Installation Guide**: https://cran.r-project.org/bin/windows/base/
- **Our Setup Guide**: [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- **Quick Start**: [QUICKSTART.md](./QUICKSTART.md)
- **Main Summary**: [../../NBL_SETUP_SUMMARY.md](../../NBL_SETUP_SUMMARY.md)

---

## 💡 Pro Tips

### Tip 1: Always Use Fresh PowerShell After Installing Software

When installing any software that modifies PATH (R, Python, Git, etc.), **always open a new terminal** after installation.

### Tip 2: Check Installation Immediately

Right after installing R:
```powershell
# Close PowerShell
exit

# Open NEW PowerShell
Rscript --version  # Test immediately
```

### Tip 3: Use Windows Terminal

Windows Terminal handles PATH updates better than legacy PowerShell. Download from Microsoft Store or:
```powershell
winget install Microsoft.WindowsTerminal
```

---

**Last Updated**: 2025-11-13
