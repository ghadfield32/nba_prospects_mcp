# R Installation Diagnostic and Fix Script
# This script diagnoses R installation issues on Windows and attempts to fix PATH problems

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           R Installation Diagnostic Tool (Windows)                ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Step 1: Check if R is installed (file system check)
# ==============================================================================

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "STEP 1: Checking R Installation (File System)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

$rLocations = @(
    "C:\Program Files\R",
    "$env:LOCALAPPDATA\Programs\R",
    "C:\R"
)

$rInstallPath = $null
$rBinPath = $null

foreach ($location in $rLocations) {
    if (Test-Path $location) {
        Write-Host "✅ Found R directory: $location" -ForegroundColor Green

        # Find Rscript.exe
        $rscriptPath = Get-ChildItem -Path $location -Recurse -Filter "Rscript.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

        if ($rscriptPath) {
            $rInstallPath = $location
            $rBinPath = Split-Path $rscriptPath.FullName
            Write-Host "✅ Found Rscript.exe: $($rscriptPath.FullName)" -ForegroundColor Green

            # Get R version from directory name
            $versionDir = $rscriptPath.DirectoryName | Split-Path -Leaf
            Write-Host "ℹ️  R Version detected: $versionDir" -ForegroundColor Cyan
            break
        }
    }
}

if (-not $rBinPath) {
    Write-Host "❌ R is NOT installed on this system" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install R first:" -ForegroundColor Yellow
    Write-Host "  Option 1: winget install RProject.R" -ForegroundColor White
    Write-Host "  Option 2: Download from https://cran.r-project.org/bin/windows/base/" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host ""

# ==============================================================================
# Step 2: Check if R is in PATH
# ==============================================================================

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "STEP 2: Checking if R is in PATH" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# Check current session PATH
$currentPath = $env:Path
$rInPath = $currentPath -split ';' | Where-Object { $_ -like "*R*bin*" }

if ($rInPath) {
    Write-Host "✅ R is in current session PATH:" -ForegroundColor Green
    $rInPath | ForEach-Object { Write-Host "   $_" -ForegroundColor White }
} else {
    Write-Host "❌ R is NOT in current session PATH" -ForegroundColor Red
}

Write-Host ""

# Check if Rscript command works
Write-Host "Testing Rscript command..." -ForegroundColor Cyan
try {
    $rscriptTest = & Rscript --version 2>&1
    Write-Host "✅ Rscript command works!" -ForegroundColor Green
    Write-Host "   Output: $rscriptTest" -ForegroundColor White
    $rWorking = $true
} catch {
    Write-Host "❌ Rscript command does NOT work" -ForegroundColor Red
    $rWorking = $false
}

Write-Host ""

# ==============================================================================
# Step 3: Check System vs User PATH
# ==============================================================================

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "STEP 3: Checking System and User PATH Variables" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

# Get registry PATH values
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")

$rInMachinePath = $machinePath -split ';' | Where-Object { $_ -like "*R*bin*" }
$rInUserPath = $userPath -split ';' | Where-Object { $_ -like "*R*bin*" }

Write-Host "System PATH (Machine):" -ForegroundColor Cyan
if ($rInMachinePath) {
    Write-Host "  ✅ R found in System PATH:" -ForegroundColor Green
    $rInMachinePath | ForEach-Object { Write-Host "     $_" -ForegroundColor White }
} else {
    Write-Host "  ❌ R NOT in System PATH" -ForegroundColor Red
}

Write-Host ""

Write-Host "User PATH:" -ForegroundColor Cyan
if ($rInUserPath) {
    Write-Host "  ✅ R found in User PATH:" -ForegroundColor Green
    $rInUserPath | ForEach-Object { Write-Host "     $_" -ForegroundColor White }
} else {
    Write-Host "  ❌ R NOT in User PATH" -ForegroundColor Red
}

Write-Host ""

# ==============================================================================
# Step 4: Diagnosis and Recommendation
# ==============================================================================

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "STEP 4: Diagnosis and Recommendation" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

if ($rWorking) {
    Write-Host "✅ DIAGNOSIS: R is working correctly!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Install R packages: R -e 'install.packages(c(`"nblR`", `"dplyr`", `"arrow`"))'" -ForegroundColor White
    Write-Host "  2. Validate setup: uv run python tools/nbl/validate_setup.py" -ForegroundColor White
    Write-Host ""
} elseif ($rInMachinePath -or $rInUserPath) {
    Write-Host "⚠️  DIAGNOSIS: R is installed and in registry PATH, but not in current session" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "CAUSE: Your current PowerShell session has a cached PATH from before R was installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "SOLUTION (Choose one):" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Option A (Recommended): Close this PowerShell and open a NEW window" -ForegroundColor White
    Write-Host "     Then test: Rscript --version" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Option B: Reload PATH in this session (run this command):" -ForegroundColor White
    Write-Host '     $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")' -ForegroundColor Gray
    Write-Host "     Then test: Rscript --version" -ForegroundColor Gray
    Write-Host ""

    Write-Host "Would you like me to reload PATH in this session now? (y/n): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host

    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host ""
        Write-Host "Reloading PATH..." -ForegroundColor Cyan
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

        Write-Host "Testing Rscript command..." -ForegroundColor Cyan
        try {
            $rscriptTest = & Rscript --version 2>&1
            Write-Host "✅ SUCCESS! Rscript command now works!" -ForegroundColor Green
            Write-Host "   Output: $rscriptTest" -ForegroundColor White
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "  1. Install R packages: R -e 'install.packages(c(`"nblR`", `"dplyr`", `"arrow`"))'" -ForegroundColor White
            Write-Host "  2. Validate setup: uv run python tools/nbl/validate_setup.py" -ForegroundColor White
            Write-Host ""
        } catch {
            Write-Host "❌ Still not working. You may need to restart PowerShell." -ForegroundColor Red
            Write-Host ""
        }
    }
} else {
    Write-Host "❌ DIAGNOSIS: R is installed but NOT in system PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "R Binary Location: $rBinPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "SOLUTION: Add R to PATH manually" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Would you like me to add R to your User PATH now? (y/n): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host

    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host ""
        Write-Host "Adding R to User PATH..." -ForegroundColor Cyan

        # Add to User PATH permanently
        $newUserPath = $userPath + ";" + $rBinPath
        [System.Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")

        # Update current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

        Write-Host "✅ R added to User PATH" -ForegroundColor Green
        Write-Host ""

        Write-Host "Testing Rscript command..." -ForegroundColor Cyan
        try {
            $rscriptTest = & Rscript --version 2>&1
            Write-Host "✅ SUCCESS! Rscript command now works!" -ForegroundColor Green
            Write-Host "   Output: $rscriptTest" -ForegroundColor White
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "  1. Install R packages: R -e 'install.packages(c(`"nblR`", `"dplyr`", `"arrow`"))'" -ForegroundColor White
            Write-Host "  2. Validate setup: uv run python tools/nbl/validate_setup.py" -ForegroundColor White
            Write-Host ""
        } catch {
            Write-Host "❌ Still not working. Please restart PowerShell and try again." -ForegroundColor Red
            Write-Host ""
        }
    }
}

# ==============================================================================
# Step 5: Summary
# ==============================================================================

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "SUMMARY" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

Write-Host "Installation Status:" -ForegroundColor Cyan
Write-Host "  R Location: $rBinPath" -ForegroundColor White
Write-Host "  In System PATH: $(if ($rInMachinePath) { '✅ Yes' } else { '❌ No' })" -ForegroundColor $(if ($rInMachinePath) { 'Green' } else { 'Red' })
Write-Host "  In User PATH: $(if ($rInUserPath) { '✅ Yes' } else { '❌ No' })" -ForegroundColor $(if ($rInUserPath) { 'Green' } else { 'Red' })
Write-Host "  Command Works: $(if ($rWorking) { '✅ Yes' } else { '❌ No' })" -ForegroundColor $(if ($rWorking) { 'Green' } else { 'Red' })
Write-Host ""

Write-Host "For more help, see:" -ForegroundColor Cyan
Write-Host "  tools/nbl/SETUP_GUIDE.md" -ForegroundColor White
Write-Host "  tools/nbl/QUICKSTART.md" -ForegroundColor White
Write-Host ""
