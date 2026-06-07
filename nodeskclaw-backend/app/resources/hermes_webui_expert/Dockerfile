# syntax=docker/dockerfile:1
ARG HERMES_AGENT_REPO=
ARG HERMES_WEBUI_REPO=
ARG HERMES_EXPERT_IMAGE=

FROM ${HERMES_EXPERT_IMAGE:-python:3.12-slim-bookworm} AS runtime

ARG HERMES_AGENT_REPO
ARG HERMES_WEBUI_REPO

ENV HERMES_HOME=/data/hermes \
    HERMES_CONFIG_PATH=/data/hermes/config.yaml \
    HERMES_WEBUI_HOST=0.0.0.0 \
    HERMES_WEBUI_PORT=8787

WORKDIR /opt/hermes-agent

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY expert-templates/base/config.yaml /opt/hermes-agent/config.yaml.template

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8787/health || exit 1

CMD ["python", "-m", "http.server", "8787"]
