# Multi-stage home-worker image (D-B5a): Python 3.12 + uv deps + rclone + git.
# Build context is the repository root:
#   docker build -f worker/Dockerfile .
#
# No secrets in layers — credentials mount at runtime via host .env (D-B8).

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY pipeline/ pipeline/
COPY store/ store/
COPY config/ config/

RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends rclone git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/pyproject.toml /app/uv.lock ./
COPY --from=builder /app/pipeline /app/pipeline
COPY --from=builder /app/store /app/store
COPY --from=builder /app/config /app/config
COPY web/ web/
COPY worker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["/entrypoint.sh"]
