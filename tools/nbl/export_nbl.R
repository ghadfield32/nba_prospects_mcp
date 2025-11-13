#!/usr/bin/env Rscript

#' NBL Data Export via nblR Package
#'
#' This script uses the nblR CRAN package to extract official NBL Australia statistics
#' and export them to Parquet files for ingestion into the Python cbb_data pipeline.
#'
#' Data Coverage:
#' - Results: All NBL matches since 1979
#' - Player box scores: Since 2015-16 season
#' - Team box scores: Since 2015-16 season
#' - Play-by-play: Since 2015-16 season
#' - Shot locations (x,y): Since 2015-16 season
#'
#' License: GPL-3 (nblR package license)
#' Usage: This script CALLS the nblR package (legal under GPL-3)
#'        We do not copy or redistribute nblR's internal code
#'
#' Environment Variables:
#' - NBL_EXPORT_DIR: Output directory for Parquet files (default: data/nbl_raw)
#'
#' Dependencies:
#' - nblR (CRAN package)
#' - dplyr (data manipulation)
#' - arrow (Parquet export)
#'
#' Install dependencies:
#'   install.packages(c("nblR", "dplyr", "arrow"))
#'
#' Usage:
#'   Rscript tools/nbl/export_nbl.R
#'   # Or with custom output directory:
#'   NBL_EXPORT_DIR=/path/to/output Rscript tools/nbl/export_nbl.R

# ==============================================================================
# Setup
# ==============================================================================

# Check for required packages
required_packages <- c("nblR", "dplyr", "arrow")
missing_packages <- required_packages[!sapply(required_packages, requireNamespace, quietly = TRUE)]

if (length(missing_packages) > 0) {
  stop(paste(
    "Missing required R packages:",
    paste(missing_packages, collapse = ", "),
    "\n\nInstall with: install.packages(c(",
    paste(paste0("\"", missing_packages, "\""), collapse = ", "),
    "))"
  ))
}

# Load packages
library(nblR)
library(dplyr)
library(arrow)

# Get output directory from environment or use default
out_dir <- Sys.getenv("NBL_EXPORT_DIR", "data/nbl_raw")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

cat(sprintf("NBL Export Tool\n"))
cat(sprintf("===============\n"))
cat(sprintf("Output directory: %s\n\n", out_dir))

# ==============================================================================
# Export Functions
# ==============================================================================

#' Export a dataset to Parquet
#'
#' @param data DataFrame to export
#' @param name File name (without extension)
#' @param description Human-readable description
export_dataset <- function(data, name, description) {
  out_path <- file.path(out_dir, paste0(name, ".parquet"))

  cat(sprintf("[%s] Exporting %s...", name, description))

  if (nrow(data) == 0) {
    cat(" EMPTY (no data)\n")
    return(invisible(NULL))
  }

  tryCatch({
    write_parquet(data, out_path)
    cat(sprintf(" OK (%d rows, %d cols)\n", nrow(data), ncol(data)))
  }, error = function(e) {
    cat(sprintf(" ERROR: %s\n", e$message))
  })
}

# ==============================================================================
# Fetch NBL Data via nblR
# ==============================================================================

cat("Fetching NBL data via nblR package...\n\n")

# 1. Match Results (1979-present)
cat("[1/5] Fetching match results since 1979...\n")
results <- tryCatch(
  nbl_results(wide_or_long = "long"),
  error = function(e) {
    cat(sprintf("  ERROR: %s\n", e$message))
    return(data.frame())
  }
)
export_dataset(results, "nbl_results", "match results (1979-present)")

# 2. Player Box Scores (2015-16+)
cat("\n[2/5] Fetching player box scores (2015-16+)...\n")
box_player <- tryCatch(
  nbl_box_player(),
  error = function(e) {
    cat(sprintf("  ERROR: %s\n", e$message))
    return(data.frame())
  }
)
export_dataset(box_player, "nbl_box_player", "player box scores")

# 3. Team Box Scores (2015-16+)
cat("\n[3/5] Fetching team box scores (2015-16+)...\n")
box_team <- tryCatch(
  nbl_box_team(),
  error = function(e) {
    cat(sprintf("  ERROR: %s\n", e$message))
    return(data.frame())
  }
)
export_dataset(box_team, "nbl_box_team", "team box scores")

# 4. Play-by-Play (2015-16+)
cat("\n[4/5] Fetching play-by-play data (2015-16+)...\n")
pbp <- tryCatch(
  nbl_pbp(),
  error = function(e) {
    cat(sprintf("  ERROR: %s\n", e$message))
    return(data.frame())
  }
)
export_dataset(pbp, "nbl_pbp", "play-by-play events")

# 5. Shot Locations (2015-16+)
cat("\n[5/5] Fetching shot location data (2015-16+)...\n")
shots <- tryCatch(
  nbl_shots(),
  error = function(e) {
    cat(sprintf("  ERROR: %s\n", e$message))
    return(data.frame())
  }
)
export_dataset(shots, "nbl_shots", "shot locations (x,y)")

# ==============================================================================
# Summary
# ==============================================================================

cat("\n===============\n")
cat("Export complete!\n\n")
cat(sprintf("Output files in: %s\n", out_dir))
cat("  - nbl_results.parquet (match results, 1979+)\n")
cat("  - nbl_box_player.parquet (player stats, 2015-16+)\n")
cat("  - nbl_box_team.parquet (team stats, 2015-16+)\n")
cat("  - nbl_pbp.parquet (play-by-play, 2015-16+)\n")
cat("  - nbl_shots.parquet (shot locations, 2015-16+)\n\n")
cat("Next step: Run Python ingest script to load into DuckDB\n")
cat("  python -c \"from cbb_data.fetchers.nbl_official import ingest_nbl_into_duckdb; ingest_nbl_into_duckdb()\"\n")
