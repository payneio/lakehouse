# syntax=docker/dockerfile:1.7
#
# Lakehouse / amplifierd backend image
#
# Build context: REPO ROOT (not amplifierd/), because amplifierd's
# pyproject.toml declares amplifier_library as a sibling editable
# dependency: { path = "../amplifier_library", editable = true }
#
# Build:    docker build -t lakehouse-daemon .
# Run:      docker run -p 8421:8421 -v lakehouse-data:/data lakehouse-daemon

############################
# Stage 1: build / install
############################
FROM python:3.11-slim AS builder

# git is required because amplifier-core is pulled from GitHub via uv.
# build-essential is occasionally needed for native wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (pinned image tag for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Copy both projects so the relative editable path (../amplifier_library) resolves.
COPY amplifier_library/ ./amplifier_library/
COPY amplifierd/        ./amplifierd/

# Resolve and install the locked dependency set into amplifierd/.venv
WORKDIR /app/amplifierd
RUN uv sync --frozen --no-dev

############################
# Stage 2: runtime
############################
FROM python:3.11-slim AS runtime

# git is needed at runtime too — the daemon clones/updates profile repos
# (see amplifier_library/services and gitpython dependency).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for the app
RUN useradd --create-home --shell /bin/bash --uid 1000 amplifier

# Copy installed app + venv from builder, preserving the sibling layout
# that amplifier_library's editable install points at.
COPY --from=builder --chown=amplifier:amplifier /app /app

# Persistent state directory.
# On Azure Web App for Containers, /home is a persistent mount that
# survives restarts (when WEBSITES_ENABLE_APP_SERVICE_STORAGE=true is
# set as an app setting). We point AMPLIFIERD_HOME there so config,
# state, cache, and logs persist. The directory is created lazily by
# the daemon on first boot; we don't pre-create it because /home is
# overlaid by the platform mount at runtime.

# Daemon configuration via environment (precedence: env > yaml > defaults)
ENV AMPLIFIERD_HOME=/home/amplifierd \
    AMPLIFIERD_DAEMON_HOST=0.0.0.0 \
    AMPLIFIERD_DAEMON_PORT=8421 \
    AMPLIFIERD_DAEMON_LOG_LEVEL=INFO \
    AMPLIFIERD_DAEMON_TIMEZONE=UTC \
    PATH="/app/amplifierd/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER amplifier
WORKDIR /app/amplifierd

EXPOSE 8421

# tini reaps zombies from any subprocesses the scheduler / claude-code-sdk spawns
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "amplifierd"]
