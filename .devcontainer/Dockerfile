# CBB Data Devcontainer
# Full environment with R + BAwiR + rpy2 for ACB pbp/shots
#
# This container provides complete functionality including:
# - Python 3.13 with all cbb_data dependencies
# - R with BAwiR package for ACB play-by-play and shot data
# - rpy2 for Python <-> R integration
# - Playwright for NZ-NBL JS widget rendering
# - DuckDB for data storage

FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for R + rpy2 + Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    # R and development tools
    r-base \
    r-base-dev \
    # Build tools for R packages
    build-essential \
    gfortran \
    # Libraries for R packages
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    # Git for version control
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure R to use the Cloud R repository for faster package installation
RUN echo 'options(repos = c(CRAN = "https://cloud.r-project.org"))' >> /etc/R/Rprofile.site

# Install R packages needed by BAwiR
RUN Rscript -e "install.packages(c('httr', 'rvest', 'xml2', 'jsonlite', 'dplyr', 'tidyr', 'stringr'))"

# Install BAwiR package
RUN Rscript -e "install.packages('BAwiR')"

# Verify BAwiR installation
RUN Rscript -e "library(BAwiR); cat('BAwiR version:', as.character(packageVersion('BAwiR')), '\n')"

# Set up uv for Python package management
# uv is already installed in the devcontainer base image
ENV UV_SYSTEM_PYTHON=1

# Set working directory
WORKDIR /workspace

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock* ./

# Install Python dependencies with all extras
# Note: We use --extra flags to install optional dependencies
RUN uv sync --extra dev --extra nz_nbl --extra acb --extra servers || \
    uv pip install -e ".[dev,nz_nbl,acb,servers]"

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy the rest of the project
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports for any services (FastAPI, MCP servers, etc.)
EXPOSE 8000 8080

# Default command
CMD ["bash"]
