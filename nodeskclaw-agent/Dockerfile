FROM python:3.12-slim

ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""

WORKDIR /app

RUN pip install --no-cache-dir \
    ${PIP_INDEX_URL:+--index-url=$PIP_INDEX_URL} \
    ${PIP_TRUSTED_HOST:+--trusted-host=$PIP_TRUSTED_HOST} \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy[asyncio]>=2.0.36" \
    "asyncpg>=0.30.0" \
    "httpx>=0.28.0" \
    "pydantic-settings>=2.7.0"

COPY nodeskclaw-agent/app ./app

EXPOSE 4520
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4520"]
