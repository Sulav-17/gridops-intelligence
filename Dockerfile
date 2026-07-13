FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system gridops && useradd --system --gid gridops --create-home gridops

COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev && chown -R gridops:gridops /app

USER gridops
EXPOSE 8000

CMD ["uvicorn", "gridops.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
