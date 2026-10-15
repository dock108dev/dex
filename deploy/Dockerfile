FROM python:3.14-slim-trixie@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.9.10
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY config/catalog-imports ./config/catalog-imports
COPY config/sealed/2026-10-04 ./config/sealed/2026-10-04
COPY config/sealed/2026-10-04-151/package.json ./config/sealed/2026-10-04-151/package.json
COPY config/sealed/2026-10-05-det1-e1c/package.json ./config/sealed/2026-10-05-det1-e1c/package.json
COPY config/catalog-pipeline ./config/catalog-pipeline
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home dex
USER dex
ENV DEX_PROFILE=staging PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python", "-m", "pokemon_hunter.beta.deployment", "web"]
