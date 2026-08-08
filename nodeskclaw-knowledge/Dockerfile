FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY nodeskclaw-knowledge/pyproject.toml ./
RUN uv sync --no-dev

COPY nodeskclaw-knowledge/ .

ENV PYTHONUNBUFFERED=1
EXPOSE 4530

CMD ["/bin/sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 4530"]
