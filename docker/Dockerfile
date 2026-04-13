# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder
ENV UV_LINK_MODE=copy PATH="/root/.local/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-packages

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 1000 plex

COPY --from=builder /src/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /config
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER plex
VOLUME ["/config", "/reports"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["scan", "--config", "/config/config.yaml"]
