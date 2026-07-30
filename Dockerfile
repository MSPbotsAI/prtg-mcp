# Multi-stage build for efficient container size
FROM python:3.12-slim AS builder

ARG VERSION="unknown"
ARG COMMIT_SHA="unknown"
ARG BUILD_DATE="unknown"

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Compile bytecode and use copy link mode (avoids cross-device hardlink issues)
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (layer-cached when only src changes)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# Install the project itself
COPY . .
RUN uv sync --frozen --no-dev

# Production stage — slim image, no uv, no build tools
FROM python:3.12-slim AS production

# Create non-root user for security
RUN groupadd -g 1001 prtg && \
    useradd -u 1001 -g prtg -s /bin/sh -m prtg

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment and source from builder
COPY --from=builder --chown=prtg:prtg /app/.venv /app/.venv
COPY --from=builder --chown=prtg:prtg /app/src /app/src

# Put venv on PATH so `python -m prtg_mcp` resolves correctly
ENV PATH="/app/.venv/bin:$PATH"

ENV MCP_HTTP_PORT=8080
ENV MCP_HTTP_HOST=0.0.0.0

USER prtg

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["python", "-m", "prtg_mcp"]

# OCI image labels
LABEL org.opencontainers.image.title="prtg-mcp"
LABEL org.opencontainers.image.description="PRTG Network Monitor MCP server — exposes PRTG's sensors, devices, and historic sensor data table.json/historicdata.json API as MCP tools"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.revision="${COMMIT_SHA}"
LABEL org.opencontainers.image.licenses="Apache-2.0"
