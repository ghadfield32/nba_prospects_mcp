#!/usr/bin/env Rscript
# ============================================================================
# NBL R Package Installer
# ============================================================================
# Installs required R packages for NBL data export.
#
# Required packages:
#   - nblR: Official NBL stats wrapper (GPL-3, CRAN)
#   - dplyr: Data manipulation
#   - arrow: Parquet I/O
#
# Usage:
#   Rscript tools/nbl/install_nbl_packages.R
#
# Note: On some systems, you may need to run R as administrator/sudo
#       for package installation to succeed.
# ============================================================================

cat("\n")
cat("╔══════════════════════════════════════════════════════════════════╗\n")
cat("║                NBL R Package Installer                           ║\n")
cat("╚══════════════════════════════════════════════════════════════════╝\n")
cat("\n")

# Configuration
CRAN_MIRROR <- "https://cloud.r-project.org"
REQUIRED_PACKAGES <- c("nblR", "dplyr", "arrow")

cat(sprintf("R version: %s\n", R.version.string))
cat(sprintf("CRAN mirror: %s\n", CRAN_MIRROR))
cat(sprintf("Packages to install: %s\n", paste(REQUIRED_PACKAGES, collapse=", ")))
cat("\n")

# Track results
install_results <- list()

# ----------------------------------------------------------------------------
# Check and install each package
# ----------------------------------------------------------------------------
for (pkg in REQUIRED_PACKAGES) {
  cat(sprintf("─── %s ───\n", pkg))

  if (requireNamespace(pkg, quietly = TRUE)) {
    # Package already installed
    pkg_version <- as.character(packageVersion(pkg))
    cat(sprintf("  ✓ Already installed (version %s)\n", pkg_version))
    install_results[[pkg]] <- "already_installed"
  } else {
    # Need to install
    cat(sprintf("  Installing %s from CRAN...\n", pkg))

    tryCatch({
      install.packages(pkg, repos = CRAN_MIRROR, quiet = FALSE)

      # Verify installation
      if (requireNamespace(pkg, quietly = TRUE)) {
        pkg_version <- as.character(packageVersion(pkg))
        cat(sprintf("  ✓ Successfully installed (version %s)\n", pkg_version))
        install_results[[pkg]] <- "installed"
      } else {
        cat(sprintf("  ✗ Installation reported success but package not loadable\n"))
        install_results[[pkg]] <- "failed"
      }
    }, error = function(e) {
      cat(sprintf("  ✗ Installation failed: %s\n", e$message))
      install_results[[pkg]] <- "failed"
    }, warning = function(w) {
      cat(sprintf("  ⚠ Warning during installation: %s\n", w$message))
    })
  }

  cat("\n")
}

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
cat("═══════════════════════════════════════════════════════════════════\n")
cat("                     INSTALLATION SUMMARY                          \n")
cat("═══════════════════════════════════════════════════════════════════\n")

all_ok <- TRUE
for (pkg in REQUIRED_PACKAGES) {
  status <- install_results[[pkg]]
  if (status == "already_installed") {
    cat(sprintf("  ✓ %s: Already installed\n", pkg))
  } else if (status == "installed") {
    cat(sprintf("  ✓ %s: Newly installed\n", pkg))
  } else {
    cat(sprintf("  ✗ %s: FAILED\n", pkg))
    all_ok <- FALSE
  }
}

cat("\n")

if (all_ok) {
  cat("═══════════════════════════════════════════════════════════════════\n")
  cat("  🎉 All packages installed successfully!\n")
  cat("═══════════════════════════════════════════════════════════════════\n")
  cat("\n")
  cat("Next steps:\n")
  cat("  1. Validate setup: python tools/nbl/validate_setup.py\n")
  cat("  2. Export data: Rscript tools/nbl/export_nbl.R\n")
  cat("\n")
  quit(status = 0)
} else {
  cat("═══════════════════════════════════════════════════════════════════\n")
  cat("  ⚠ Some packages failed to install.\n")
  cat("═══════════════════════════════════════════════════════════════════\n")
  cat("\n")
  cat("Troubleshooting:\n")
  cat("  1. Try running R as administrator (Windows) or with sudo (Linux)\n")
  cat("  2. Check internet connection\n")
  cat("  3. Try installing manually in R console:\n")
  cat(sprintf('     install.packages(c("%s"), repos="%s")\n',
              paste(REQUIRED_PACKAGES, collapse='", "'), CRAN_MIRROR))
  cat("\n")
  cat("For more help, see: tools/nbl/SETUP_GUIDE.md\n")
  cat("\n")
  quit(status = 1)
}
