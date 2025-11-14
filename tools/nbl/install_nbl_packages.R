#!/usr/bin/env Rscript

# Install NBL R Package Dependencies
#
# This script installs the required R packages for NBL data integration:
# - nblR: Official NBL Australia data package
# - dplyr: Data manipulation
# - arrow: Parquet file support
#
# Usage:
#   Rscript tools/nbl/install_nbl_packages.R
#
# Why use this script instead of 'R -e install.packages(...)'?
# - Avoids Windows PowerShell quoting issues
# - Avoids '\U' Unicode escape errors with Windows paths like C:\Users\...
# - More robust and easier to debug
# - Can be run from any shell (PowerShell, cmd, bash)

# ==============================================================================
# Configuration
# ==============================================================================

required_pkgs <- c("nblR", "dplyr", "arrow")
cran_mirror <- "https://cloud.r-project.org"

# ==============================================================================
# Check Current Installation Status
# ==============================================================================

cat("\n")
cat("╔════════════════════════════════════════════════════════════════════╗\n")
cat("║           NBL R Package Installer                                  ║\n")
cat("╚════════════════════════════════════════════════════════════════════╝\n")
cat("\n")

cat("🔍 Checking installed packages...\n")
cat("\n")

installed <- rownames(installed.packages())
missing   <- setdiff(required_pkgs, installed)
already_installed <- intersect(required_pkgs, installed)

# Show what's already installed
if (length(already_installed) > 0) {
  cat("✅ Already installed:\n")
  for (pkg in already_installed) {
    version <- as.character(packageVersion(pkg))
    cat(sprintf("   • %s (version %s)\n", pkg, version))
  }
  cat("\n")
}

# Check if we need to install anything
if (length(missing) == 0) {
  cat("🎉 All NBL R packages are already installed!\n")
  cat("\n")
  cat("Required packages:\n")
  for (pkg in required_pkgs) {
    version <- as.character(packageVersion(pkg))
    cat(sprintf("  ✅ %s (version %s)\n", pkg, version))
  }
  cat("\n")
  cat("Next steps:\n")
  cat("  1. Validate setup: uv run python tools/nbl/validate_setup.py\n")
  cat("  2. Export NBL data: uv run nbl-export\n")
  cat("\n")
  quit(status = 0)
}

# ==============================================================================
# Install Missing Packages
# ==============================================================================

cat("📦 Missing packages:\n")
for (pkg in missing) {
  cat(sprintf("   • %s\n", pkg))
}
cat("\n")

cat(sprintf("🚀 Installing from CRAN (%s)...\n", cran_mirror))
cat("   This may take 2-5 minutes depending on your connection speed.\n")
cat("\n")

# Set repository
options(repos = c(CRAN = cran_mirror))

# Install each package with error handling
installation_errors <- list()

for (pkg in missing) {
  cat("─────────────────────────────────────────────────────────────────────\n")
  cat(sprintf("Installing %s...\n", pkg))
  cat("─────────────────────────────────────────────────────────────────────\n")

  tryCatch(
    {
      install.packages(pkg, repos = cran_mirror, quiet = FALSE)
      cat(sprintf("✅ Successfully installed %s\n", pkg))
    },
    error = function(e) {
      cat(sprintf("❌ Failed to install %s: %s\n", pkg, e$message))
      installation_errors[[pkg]] <<- e$message
    }
  )
  cat("\n")
}

# ==============================================================================
# Verify Installation
# ==============================================================================

cat("═════════════════════════════════════════════════════════════════════\n")
cat("Verification\n")
cat("═════════════════════════════════════════════════════════════════════\n")
cat("\n")

installed_after <- rownames(installed.packages())
still_missing   <- setdiff(required_pkgs, installed_after)

if (length(still_missing) == 0 && length(installation_errors) == 0) {
  cat("🎉 SUCCESS! All required packages are now installed:\n")
  cat("\n")
  for (pkg in required_pkgs) {
    version <- as.character(packageVersion(pkg))
    cat(sprintf("  ✅ %s (version %s)\n", pkg, version))
  }
  cat("\n")
  cat("Next steps:\n")
  cat("  1. Validate full setup: uv run python tools/nbl/validate_setup.py\n")
  cat("  2. Export NBL data: uv run nbl-export\n")
  cat("\n")
  quit(status = 0)

} else {
  cat("⚠️  Installation completed with issues:\n")
  cat("\n")

  # Show what succeeded
  newly_installed <- setdiff(intersect(required_pkgs, installed_after), already_installed)
  if (length(newly_installed) > 0) {
    cat("✅ Successfully installed:\n")
    for (pkg in newly_installed) {
      version <- as.character(packageVersion(pkg))
      cat(sprintf("   • %s (version %s)\n", pkg, version))
    }
    cat("\n")
  }

  # Show what failed
  if (length(still_missing) > 0) {
    cat("❌ Still missing:\n")
    for (pkg in still_missing) {
      cat(sprintf("   • %s\n", pkg))
      if (!is.null(installation_errors[[pkg]])) {
        cat(sprintf("     Error: %s\n", installation_errors[[pkg]]))
      }
    }
    cat("\n")
  }

  cat("Troubleshooting:\n")
  cat("  1. Check your internet connection\n")
  cat("  2. Try installing manually in R console:\n")
  cat("     R\n")
  cat(sprintf("     install.packages(c(%s), repos=\"%s\")\n",
              paste(sprintf('"%s"', still_missing), collapse=", "),
              cran_mirror))
  cat("  3. Check firewall/proxy settings\n")
  cat("  4. See tools/nbl/TROUBLESHOOTING_WINDOWS.md for more help\n")
  cat("\n")

  quit(status = 1)
}
