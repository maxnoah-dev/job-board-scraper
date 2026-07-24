# syntax=docker/dockerfile:1.7
#
# job-board-scraper — one-shot ETL container.
#
# Per ADR-0006 the production runtime is a one-shot container driven by an
# external scheduler (cron / Kubernetes CronJob / Cloud Scheduler). The
# image therefore has no entrypoint daemon; it just runs the CLI and exits
# with the pipeline exit code (`0` success, `1` partial, `2` failed).
#
# Build variants:
#   docker build --target runtime          -> minimal image (no Playwright)
#   docker build --target runtime-browser  -> image with Playwright + Chromium
#
# The base Python version is pinned to the lowest supported (3.11) so the
# build matrix in CI matches the lockfile's `python = ">=3.11,<3.13"`.
ARG PYTHON_VERSION=3.11
ARG POETRY_VERSION=1.8.5

# ---------------------------------------------------------------------------
# Stage 1: builder — install dependencies into a virtual env we can copy
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=true

# System build deps for cffi / cryptography wheels. These stay in the
# builder image only; the runtime image is slimmer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /build

# Copy dependency manifests first so this layer is cached when only source
# code changes.
COPY pyproject.toml poetry.lock* ./
COPY README.md ./

# Install runtime + dev dependencies into the project venv. `--no-root`
# leaves the source out of the install; we copy it in below.
RUN poetry install --no-interaction --no-root --with dev

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image with the prebuilt venv only
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# runtime-only system packages: libexpat for lxml, libxml2/css for
# beautifulsoup4, postgresql client for asyncpg/DATABASE_URL validation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libexpat1 \
        libxml2 \
        libxslt1.1 \
        libpq5 \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for the scraper process. The mounted data / logs / config
# volumes must be writable by this uid.
RUN groupadd --system --gid 1001 scraper \
    && useradd --system --uid 1001 --gid scraper --home /app --shell /usr/sbin/nologin scraper

WORKDIR /app

# Copy the prebuilt venv from the builder (already contains the package).
COPY --from=builder --chown=scraper:scraper /app/.venv /app/.venv

# Copy the application source. Order matters: changes here invalidate the
# venv cache but not the venv itself.
COPY --chown=scraper:scraper pyproject.toml poetry.lock* ./
COPY --chown=scraper:scraper README.md ./
COPY --chown=scraper:scraper src ./src
COPY --chown=scraper:scraper scripts ./scripts
COPY --chown=scraper:scraper migrations ./migrations
COPY --chown=scraper:scraper alembic.ini* ./

# Writable directories for runtime data.
RUN mkdir -p /app/data /app/logs /app/config \
    && chown -R scraper:scraper /app/data /app/logs /app/config

# Switch to the unprivileged user for execution.
USER scraper

# Default environment knobs. The scheduler overrides these on every run.
ENV DATABASE_URL="sqlite+aiosqlite:///./data/jobs.db" \
    LOG_LEVEL="INFO" \
    LOG_FILE="./logs/scraper.log" \
    EXPORT_DIR="./data" \
    SCHEDULER_ENABLED="false" \
    PLAYWRIGHT_BROWSERS_INSTALLED="false"

# tini reaps zombies and forwards SIGTERM to the scraper so the graceful
# shutdown in the pipeline gets a chance to mark the run as interrupted.
ENTRYPOINT ["/usr/bin/tini", "--"]

# The default command is a no-op smoke test; CI / the scheduler override this
# with `["python", "-m", "job_board_scraper.cli", "run"]` or
# `["python", "-m", "job_board_scraper.cli", "init-db"]`.
CMD ["python", "-m", "job_board_scraper.cli", "--help"]

# ---------------------------------------------------------------------------
# Stage 3: runtime-browser — same image but with Playwright + Chromium installed
# ---------------------------------------------------------------------------
FROM runtime AS runtime-browser

USER root

# System libs required by headless Chromium.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libglib2.0-0 \
        libnspr4 \
        libnss3 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libx11-6 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright + Chromium into the shared venv and hand the files to
# the unprivileged user.
RUN /app/.venv/bin/pip install --no-cache-dir playwright \
    && /app/.venv/bin/playwright install --with-deps chromium \
    && chown -R scraper:scraper /app/.venv

USER scraper

ENV PLAYWRIGHT_BROWSERS_INSTALLED="true"
