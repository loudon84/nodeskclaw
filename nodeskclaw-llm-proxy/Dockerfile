FROM python:3.12-slim

ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""
ARG NPM_REGISTRY=""
ARG APT_MIRROR=""

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    UV_INDEX_URL=${PIP_INDEX_URL}
ENV TZ=Asia/Shanghai
ARG CODEX_CLI_VERSION=0.116.0

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    pip install --no-cache-dir uv && \
    apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm install -g @openai/codex@${CODEX_CLI_VERSION} \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen --no-dev

COPY . .

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
