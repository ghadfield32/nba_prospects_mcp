#!/usr/bin/env Rscript
# ============================================================================
# NBL Data Export Script
# ============================================================================
# Exports NBL Australia data to Parquet files using the nblR CRAN package.
#
# Output: data/nbl_raw/*.parquet
#
# Datasets exported:
#   1. nbl_results.parquet    - Match results (1979-present, ~10k games)
#   2. nbl_box_player.parquet - Player box scores (2015-16+, ~150k records)
#   3. nbl_box_team.parquet   - Team box scores (2015-16+, ~3k records)
#   4. nbl_pbp.parquet        - Play-by-play events (2015-16+, ~2M events)
#   5. nbl_shots.parquet      - Shot locations with x,y (2015-16+, ~500k shots)
#
# Usage:
#   Rscript tools/nbl/export_nbl.R
#   # or via Python CLI:
#   uv run nbl-export
#
# Requirements:
#   - R 4.0+
#   - nblR package (GPL-3, CRAN)
#   - dplyr package
#   - arrow package (for Parquet I/O)
#
# Install requirements:
#   Rscript tools/nbl/install_nbl_packages.R
# ============================================================================

# Suppress startup messages for cleaner output
suppressPackageStartupMessages({
  library(nblR)
  library(dplyr)
  library(arrow)
})

# Configuration
OUTPUT_DIR <- "data/nbl_raw"

# Create output directory if it doesn't exist
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

cat("\n")
cat("╔══════════════════════════════════════════════════════════════════╗\n")
cat("║                    NBL Data Export (nblR)                        ║\n")
cat("╚══════════════════════════════════════════════════════════════════╝\n")
cat("\n")
cat(sprintf("Output directory: %s\n", OUTPUT_DIR))
cat(sprintf("Timestamp: %s\n", Sys.time()))
cat("\n")

# Track total records
total_records <- 0

# ----------------------------------------------------------------------------
# 1. Match Results (1979-present)
# ----------------------------------------------------------------------------
cat("─────────────────────────────────────────────────────────────────────\n")
cat("1. Fetching match results (1979-present)...\n")
cat("─────────────────────────────────────────────────────────────────────\n")

tryCatch({
  results <- nbl_results()
  output_path <- file.path(OUTPUT_DIR, "nbl_results.parquet")
  write_parquet(results, output_path)
  cat(sprintf("   ✓ Saved %s records to %s\n", format(nrow(results), big.mark=","), output_path))
  cat(sprintf("   Date range: %s to %s\n",
              min(results$Date, na.rm = TRUE),
              max(results$Date, na.rm = TRUE)))
  total_records <- total_records + nrow(results)
}, error = function(e) {
  cat(sprintf("   ✗ ERROR: %s\n", e$message))
})

cat("\n")

# ----------------------------------------------------------------------------
# 2. Player Box Scores (2015-16+)
# ----------------------------------------------------------------------------
cat("─────────────────────────────────────────────────────────────────────\n")
cat("2. Fetching player box scores (2015-16+)...\n")
cat("─────────────────────────────────────────────────────────────────────\n")

tryCatch({
  box_player <- nbl_box_player()
  output_path <- file.path(OUTPUT_DIR, "nbl_box_player.parquet")
  write_parquet(box_player, output_path)
  cat(sprintf("   ✓ Saved %s records to %s\n", format(nrow(box_player), big.mark=","), output_path))

  # Show season breakdown
  if ("Season" %in% colnames(box_player)) {
    season_counts <- box_player %>%
      group_by(Season) %>%
      summarise(n = n(), .groups = "drop") %>%
      arrange(Season)
    cat("   Seasons:\n")
    for (i in 1:min(5, nrow(season_counts))) {
      cat(sprintf("     %s: %s records\n",
                  season_counts$Season[i],
                  format(season_counts$n[i], big.mark=",")))
    }
    if (nrow(season_counts) > 5) {
      cat(sprintf("     ... and %d more seasons\n", nrow(season_counts) - 5))
    }
  }
  total_records <- total_records + nrow(box_player)
}, error = function(e) {
  cat(sprintf("   ✗ ERROR: %s\n", e$message))
})

cat("\n")

# ----------------------------------------------------------------------------
# 3. Team Box Scores (2015-16+)
# ----------------------------------------------------------------------------
cat("─────────────────────────────────────────────────────────────────────\n")
cat("3. Fetching team box scores (2015-16+)...\n")
cat("─────────────────────────────────────────────────────────────────────\n")

tryCatch({
  box_team <- nbl_box_team()
  output_path <- file.path(OUTPUT_DIR, "nbl_box_team.parquet")
  write_parquet(box_team, output_path)
  cat(sprintf("   ✓ Saved %s records to %s\n", format(nrow(box_team), big.mark=","), output_path))
  total_records <- total_records + nrow(box_team)
}, error = function(e) {
  cat(sprintf("   ✗ ERROR: %s\n", e$message))
})

cat("\n")

# ----------------------------------------------------------------------------
# 4. Play-by-Play (2015-16+)
# ----------------------------------------------------------------------------
cat("─────────────────────────────────────────────────────────────────────\n")
cat("4. Fetching play-by-play events (2015-16+)...\n")
cat("   (This may take a few minutes - ~2M events)\n")
cat("─────────────────────────────────────────────────────────────────────\n")

tryCatch({
  pbp <- nbl_pbp()
  output_path <- file.path(OUTPUT_DIR, "nbl_pbp.parquet")
  write_parquet(pbp, output_path)
  cat(sprintf("   ✓ Saved %s records to %s\n", format(nrow(pbp), big.mark=","), output_path))
  total_records <- total_records + nrow(pbp)
}, error = function(e) {
  cat(sprintf("   ✗ ERROR: %s\n", e$message))
})

cat("\n")

# ----------------------------------------------------------------------------
# 5. Shot Locations (2015-16+) - The premium feature!
# ----------------------------------------------------------------------------
cat("─────────────────────────────────────────────────────────────────────\n")
cat("5. Fetching shot locations with x,y coordinates (2015-16+)...\n")
cat("   (Premium feature - FREE via nblR!)\n")
cat("─────────────────────────────────────────────────────────────────────\n")

tryCatch({
  shots <- nbl_shots()
  output_path <- file.path(OUTPUT_DIR, "nbl_shots.parquet")
  write_parquet(shots, output_path)
  cat(sprintf("   ✓ Saved %s records to %s\n", format(nrow(shots), big.mark=","), output_path))

  # Show shot chart column info
  if ("x" %in% colnames(shots) && "y" %in% colnames(shots)) {
    cat("   Shot coordinates available:\n")
    cat(sprintf("     x range: %.1f to %.1f\n", min(shots$x, na.rm=TRUE), max(shots$x, na.rm=TRUE)))
    cat(sprintf("     y range: %.1f to %.1f\n", min(shots$y, na.rm=TRUE), max(shots$y, na.rm=TRUE)))
  }
  total_records <- total_records + nrow(shots)
}, error = function(e) {
  cat(sprintf("   ✗ ERROR: %s\n", e$message))
})

cat("\n")

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
cat("═══════════════════════════════════════════════════════════════════\n")
cat("                         EXPORT COMPLETE                           \n")
cat("═══════════════════════════════════════════════════════════════════\n")
cat(sprintf("Total records exported: %s\n", format(total_records, big.mark=",")))
cat(sprintf("Output directory: %s\n", OUTPUT_DIR))
cat("\n")

# List output files with sizes
files <- list.files(OUTPUT_DIR, pattern = "\\.parquet$", full.names = TRUE)
if (length(files) > 0) {
  cat("Output files:\n")
  for (f in files) {
    size_mb <- file.info(f)$size / (1024 * 1024)
    cat(sprintf("  • %s (%.2f MB)\n", basename(f), size_mb))
  }
}

cat("\n")
cat("Next steps:\n")
cat("  1. Run Python ingestion: uv run python -c 'from cbb_data.fetchers.nbl_official import ingest_nbl_into_duckdb; ingest_nbl_into_duckdb()'\n")
cat("  2. Query via API: get_dataset('player_season', filters={'league': 'NBL'})\n")
cat("\n")
