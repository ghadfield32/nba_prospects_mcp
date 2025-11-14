# Quick R PATH Diagnostic
# Run this to see exactly what's wrong with your R setup

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           R PATH Diagnostic (Quick Check)                          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==============================================================================
# Check 1: Is R installed (file system)?
# ==============================================================================

Write-Host "1️⃣  Checking if R is installed..." -ForegroundColor Yellow
Write-Host ""

$rLocations = @(
    "C:\Program Files\R",
    "$env:LOCALAPPDATA\Programs\R",
    "C:\R"
)

$rFound = $false
$rBinPath = $null

foreach ($location in $rLocations) {
    if (Test-Path $location) {
        Write-Host "   ✅ Found R directory: $location" -ForegroundColor Green

        # Find Rscript.exe
        $rscript = Get-ChildItem -Path $location -Recurse -Filter "Rscript.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

        if ($rscript) {
            $rBinPath = Split-Path $rscript.FullName
            $rFound = $true
            Write-Host "   ✅ Found Rscript.exe: $($rscript.FullName)" -ForegroundColor Green
            Write-Host ""
            break
        }
    }
}

if (-not $rFound) {
    Write-Host "   ❌ R is NOT installed on this system" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Install R with: winget install RProject.R" -ForegroundColor Yellow
    Write-Host "   Or download: https://cran.r-project.org/bin/windows/base/" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# ==============================================================================
# Check 2: Is R in current session PATH?
# ==============================================================================

Write-Host "2️⃣  Checking if R is in current session PATH..." -ForegroundColor Yellow
Write-Host ""

$currentPath = $env:Path
$rInCurrentPath = $currentPath -split ';' | Where-Object { $_ -like "*R*bin*" }

if ($rInCurrentPath) {
    Write-Host "   ✅ R IS in current session PATH:" -ForegroundColor Green
    $rInCurrentPath | ForEach-Object { Write-Host "      $_" -ForegroundColor White }
    Write-Host ""
} else {
    Write-Host "   ❌ R is NOT in current session PATH" -ForegroundColor Red
    Write-Host ""
}

# ==============================================================================
# Check 3: Does Rscript command work?
# ==============================================================================

Write-Host "3️⃣  Testing if Rscript command works..." -ForegroundColor Yellow
Write-Host ""

try {
    $rVersion = & Rscript --version 2>&1
    Write-Host "   ✅ Rscript command WORKS!" -ForegroundColor Green
    Write-Host "      $rVersion" -ForegroundColor White
    Write-Host ""
    $rWorks = $true
} catch {
    Write-Host "   ❌ Rscript command does NOT work" -ForegroundColor Red
    Write-Host ""
    $rWorks = $false
}

# ==============================================================================
# Check 4: Is R in System PATH (registry)?
# ==============================================================================

Write-Host "4️⃣  Checking System PATH (registry - Machine level)..." -ForegroundColor Yellow
Write-Host ""

$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$rInMachinePath = $machinePath -split ';' | Where-Object { $_ -like "*R*bin*" }

if ($rInMachinePath) {
    Write-Host "   ✅ R IS in System PATH (registry):" -ForegroundColor Green
    $rInMachinePath | ForEach-Object { Write-Host "      $_" -ForegroundColor White }
    Write-Host ""
} else {
    Write-Host "   ❌ R is NOT in System PATH (registry)" -ForegroundColor Red
    Write-Host ""
}

# ==============================================================================
# Check 5: Is R in User PATH (registry)?
# ==============================================================================

Write-Host "5️⃣  Checking User PATH (registry - User level)..." -ForegroundColor Yellow
Write-Host ""

$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$rInUserPath = $userPath -split ';' | Where-Object { $_ -like "*R*bin*" }

if ($rInUserPath) {
    Write-Host "   ✅ R IS in User PATH (registry):" -ForegroundColor Green
    $rInUserPath | ForEach-Object { Write-Host "      $_" -ForegroundColor White }
    Write-Host ""
} else {
    Write-Host "   ❌ R is NOT in User PATH (registry)" -ForegroundColor Red
    Write-Host ""
}

# ==============================================================================
# Diagnosis & Recommendation
# ==============================================================================

Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "DIAGNOSIS & RECOMMENDED ACTION" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

if ($rWorks) {
    # Case 1: Everything works!
    Write-Host "✅ DIAGNOSIS: R is fully functional!" -ForegroundColor Green
    Write-Host ""
    Write-Host "   R Location: $rBinPath" -ForegroundColor White
    Write-Host "   R is accessible via Rscript command" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 NEXT STEPS:" -ForegroundColor Cyan
    Write-Host "   1. Install R packages: Rscript tools/nbl/install_nbl_packages.R" -ForegroundColor White
    Write-Host "   2. Validate setup: uv run python tools/nbl/validate_setup.py" -ForegroundColor White
    Write-Host ""

} elseif ($rInMachinePath -or $rInUserPath) {
    # Case 2: In registry but not in current session
    Write-Host "⚠️  DIAGNOSIS: R is in registry PATH but NOT in current session" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   CAUSE: Your current PowerShell session has an old cached PATH." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "🔧 RECOMMENDED FIX (choose one):" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Option A (Simplest): Close PowerShell and open a NEW window" -ForegroundColor White
    Write-Host "      Then test: Rscript --version" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Option B (No restart): Reload PATH in this session" -ForegroundColor White
    Write-Host "      Run: .\tools\nbl\fix_r_path.ps1" -ForegroundColor Gray
    Write-Host "      Then test: Rscript --version" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   Option C (Manual): Run this command" -ForegroundColor White
    Write-Host '      $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")' -ForegroundColor Gray
    Write-Host "      Then test: Rscript --version" -ForegroundColor Gray
    Write-Host ""

} else {
    # Case 3: Not in registry at all
    Write-Host "❌ DIAGNOSIS: R is installed but NOT in Windows PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "   R Location: $rBinPath" -ForegroundColor White
    Write-Host "   R is NOT in registry PATH (neither System nor User)" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔧 RECOMMENDED FIX:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Run the diagnostic script which can add R to PATH automatically:" -ForegroundColor White
    Write-Host "      .\tools\nbl\debug_r_installation.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   This script will:" -ForegroundColor Yellow
    Write-Host "      • Find R installation" -ForegroundColor White
    Write-Host "      • Detect PATH issue" -ForegroundColor White
    Write-Host "      • Offer to add R to your User PATH (with your permission)" -ForegroundColor White
    Write-Host ""
}

Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
