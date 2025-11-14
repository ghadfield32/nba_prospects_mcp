# Quick Fix: Reload PATH to make R accessible in current PowerShell session
# Run this if R was just installed but commands don't work yet

Write-Host ""
Write-Host "🔧 Quick Fix: Reloading PATH to make R accessible..." -ForegroundColor Cyan
Write-Host ""

# Save old PATH
$oldPath = $env:Path

# Reload PATH from registry (combines Machine + User)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

Write-Host "✅ PATH reloaded from registry" -ForegroundColor Green
Write-Host ""

# Test if R works now
Write-Host "Testing Rscript command..." -ForegroundColor Cyan
try {
    $rVersion = & Rscript --version 2>&1
    Write-Host "✅ SUCCESS! R is now accessible!" -ForegroundColor Green
    Write-Host "   $rVersion" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Install R packages:" -ForegroundColor White
    Write-Host "     R -e 'install.packages(c(`"nblR`", `"dplyr`", `"arrow`"), repos=`"https://cloud.r-project.org`")'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Validate setup:" -ForegroundColor White
    Write-Host "     uv run python tools/nbl/validate_setup.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  3. Export NBL data:" -ForegroundColor White
    Write-Host "     uv run nbl-export" -ForegroundColor Gray
    Write-Host ""
}
catch {
    Write-Host "❌ R command still not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "This means R might not be installed, or is not in the system PATH." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Try one of these:" -ForegroundColor Cyan
    Write-Host "  1. Close PowerShell completely and open a NEW window" -ForegroundColor White
    Write-Host "  2. Run the diagnostic script:" -ForegroundColor White
    Write-Host "     .\tools\nbl\debug_r_installation.ps1" -ForegroundColor Gray
    Write-Host "  3. Reinstall R:" -ForegroundColor White
    Write-Host "     winget install RProject.R" -ForegroundColor Gray
    Write-Host ""
}
