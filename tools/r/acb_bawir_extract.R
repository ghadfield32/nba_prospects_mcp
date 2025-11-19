#!/usr/bin/env Rscript
# ACB BAwiR Data Extraction Script
#
# Extracts ACB data using BAwiR package and outputs CSV for Python consumption.
# This bypasses rpy2 limitations on Windows by using Rscript subprocess.
#
# Usage:
#   Rscript acb_bawir_extract.R --type games --season 2024 --output games.csv
#   Rscript acb_bawir_extract.R --type shots --season 2024 --output shots.csv
#   Rscript acb_bawir_extract.R --type days --season 2024 --output days.csv

suppressPackageStartupMessages({
  library(BAwiR)
  library(dplyr)
})

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)

# Default values
data_type <- "games"
season <- "2024"
output_file <- NULL
game_code <- NULL
user_email <- "cbb_data@example.com"  # Default email for BAwiR API

# Parse arguments
i <- 1
while (i <= length(args)) {
  if (args[i] == "--type") {
    data_type <- args[i + 1]
    i <- i + 2
  } else if (args[i] == "--season") {
    season <- args[i + 1]
    i <- i + 2
  } else if (args[i] == "--output") {
    output_file <- args[i + 1]
    i <- i + 2
  } else if (args[i] == "--game") {
    game_code <- args[i + 1]
    i <- i + 2
  } else if (args[i] == "--email") {
    user_email <- args[i + 1]
    i <- i + 2
  } else {
    i <- i + 1
  }
}

# Convert season format (e.g., "2024" -> "2024-2025")
if (!grepl("-", season)) {
  season_start <- as.integer(season)
  season <- paste0(season_start, "-", season_start + 1)
}

# Set default output file if not provided
if (is.null(output_file)) {
  output_file <- paste0("acb_", data_type, "_", gsub("-", "_", season), ".csv")
}

tryCatch({
  if (data_type == "games") {
    # Scrape game index for the season
    cat("Fetching ACB games for season:", season, "\n", file = stderr())

    # Use scraping_games_acb to get game codes
    # Requires user_email parameter for identification
    games <- scraping_games_acb(season, user_email = user_email)

    if (is.null(games) || nrow(games) == 0) {
      cat("No games found for season:", season, "\n", file = stderr())
      # Write empty CSV with headers
      write.csv(data.frame(
        game_code = character(),
        date = character(),
        home_team = character(),
        away_team = character(),
        home_score = integer(),
        away_score = integer()
      ), output_file, row.names = FALSE)
    } else {
      write.csv(games, output_file, row.names = FALSE)
      cat("Saved", nrow(games), "games to", output_file, "\n", file = stderr())
    }

  } else if (data_type == "shots") {
    # Scrape shot chart data
    cat("Fetching ACB shots for season:", season, "\n", file = stderr())

    # First get games
    games <- scraping_games_acb(season)

    if (is.null(games) || nrow(games) == 0) {
      cat("No games found for season:", season, "\n", file = stderr())
      write.csv(data.frame(
        game_code = character(),
        player = character(),
        team = character(),
        x = numeric(),
        y = numeric(),
        made = logical(),
        shot_type = character()
      ), output_file, row.names = FALSE)
    } else {
      # Get shots for each game
      all_shots <- data.frame()

      for (i in 1:min(nrow(games), 50)) {  # Limit to first 50 games for speed
        gc <- games$game_code[i]
        cat("Processing game", i, "/", min(nrow(games), 50), ":", gc, "\n", file = stderr())

        tryCatch({
          shots <- do_scrape_shots_acb(gc)
          if (!is.null(shots) && nrow(shots) > 0) {
            shots$game_code <- gc
            all_shots <- bind_rows(all_shots, shots)
          }
        }, error = function(e) {
          cat("Error fetching shots for game", gc, ":", conditionMessage(e), "\n", file = stderr())
        })
      }

      if (nrow(all_shots) > 0) {
        write.csv(all_shots, output_file, row.names = FALSE)
        cat("Saved", nrow(all_shots), "shots to", output_file, "\n", file = stderr())
      } else {
        cat("No shot data collected\n", file = stderr())
        write.csv(data.frame(
          game_code = character(),
          player = character(),
          team = character(),
          x = numeric(),
          y = numeric(),
          made = logical()
        ), output_file, row.names = FALSE)
      }
    }

  } else if (data_type == "days") {
    # Scrape schedule/days
    cat("Fetching ACB schedule days for season:", season, "\n", file = stderr())

    days <- do_scrape_days_acb(season)

    if (is.null(days) || nrow(days) == 0) {
      cat("No schedule data found\n", file = stderr())
      write.csv(data.frame(
        date = character(),
        round = integer()
      ), output_file, row.names = FALSE)
    } else {
      write.csv(days, output_file, row.names = FALSE)
      cat("Saved", nrow(days), "days to", output_file, "\n", file = stderr())
    }

  } else {
    stop(paste("Unknown data type:", data_type))
  }

  # Success exit
  quit(status = 0)

}, error = function(e) {
  cat("ERROR:", conditionMessage(e), "\n", file = stderr())
  quit(status = 1)
})
