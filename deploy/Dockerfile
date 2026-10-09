FROM python:3.12-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.9.7
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY config/catalog-imports ./config/catalog-imports
COPY config/sealed/2026-10-04 ./config/sealed/2026-10-04
COPY config/sealed/2026-10-04-151/package.json ./config/sealed/2026-10-04-151/package.json
COPY config/sealed/2026-10-05-det1-e1c/package.json ./config/sealed/2026-10-05-det1-e1c/package.json
COPY config/catalog-pipeline ./config/catalog-pipeline
RUN uv sync --frozen --no-dev && useradd --uid 10001 --create-home dex
USER dex
ENV DEX_PROFILE=staging PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python", "-m", "pokemon_hunter.beta.deployment", "web"]
