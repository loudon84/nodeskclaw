"""Docker Compose generation for Hermes WebUI expert instances."""

from __future__ import annotations

import secrets
from pathlib import Path

from app.core.config import settings
from app.services.docker_constants import DOCKER_DATA_DIR
from app.services.hermes_expert.expert_filesystem import expert_compose_dir, expert_host_data_dir_for_bind
from app.services.runtime.compute.base import InstanceComputeConfig


class ExpertComposeBuilder:
    def build_env(self, config: InstanceComputeConfig) -> dict[str, str]:
        advanced = config.advanced_config or {}
        expert = advanced.get("expert") or {}
        webui = advanced.get("webui") or {}
        hindsight = advanced.get("hindsight") or {}

        profile = str(expert.get("profile") or config.slug)
        expert_name = str(expert.get("template") or profile)
        host_port = str(config.env_vars.get("DOCKER_HOST_PORT", "8787"))
        bind_host = str(webui.get("host") or settings.HERMES_EXPERT_DEFAULT_BIND_HOST or "0.0.0.0")
        webui_password = str(config.env_vars.get("HERMES_WEBUI_PASSWORD") or secrets.token_urlsafe(16))

        image = config.env_vars.get("DOCKER_IMAGE")
        if not image:
            registry = settings.HERMES_EXPERT_IMAGE_REGISTRY or settings.HERMES_EXPERT_DEFAULT_IMAGE
            tag = config.image_version or "latest"
            image = f"{registry}:{tag}" if registry else tag

        env = {
            "HERMES_PROFILE": profile,
            "HERMES_EXPERT": expert_name,
            "HERMES_EXPERT_IMAGE": str(image),
            "HERMES_WEBUI_BIND": bind_host,
            "HERMES_WEBUI_PORT": host_port,
            "HERMES_WEBUI_PASSWORD": webui_password,
            "HOST_DATA_DIR": expert_host_data_dir_for_bind(config.slug),
            "HINDSIGHT_API_URL": str(hindsight.get("api_url") or settings.HERMES_EXPERT_DEFAULT_HINDSIGHT_API_URL or ""),
            "HINDSIGHT_BANK_ID": str(hindsight.get("bank_id") or f"hermes-{profile}"),
        }
        for key, value in config.env_vars.items():
            if key.startswith("HERMES_") or key.startswith("HINDSIGHT_") or key == "DOCKER_IMAGE":
                continue
            env[key] = str(value)
        return env

    def build_compose(self, config: InstanceComputeConfig) -> dict:
        env = self.build_env(config)
        profile = env["HERMES_PROFILE"]
        host_port = env["HERMES_WEBUI_PORT"]
        container_name = f"hermes-{profile}"
        service = {
            "image": env["HERMES_EXPERT_IMAGE"],
            "container_name": container_name,
            "restart": "unless-stopped",
            "ports": [f"{host_port}:8787"],
            "environment": {
                "HERMES_PROFILE": env["HERMES_PROFILE"],
                "HERMES_EXPERT": env["HERMES_EXPERT"],
                "HERMES_HOME": "/data/hermes",
                "HERMES_CONFIG_PATH": "/data/hermes/config.yaml",
                "HERMES_WEBUI_HOST": "0.0.0.0",
                "HERMES_WEBUI_PORT": "8787",
                "HERMES_WEBUI_STATE_DIR": "/data/hermes/webui",
                "HERMES_WEBUI_DEFAULT_WORKSPACE": "/data/hermes/workspace",
                "HERMES_WEBUI_AGENT_DIR": "/opt/hermes-agent",
                "HERMES_WEBUI_AUTO_INSTALL": "1",
                "HERMES_WEBUI_PASSWORD": env["HERMES_WEBUI_PASSWORD"],
                "HINDSIGHT_MODE": "local_external",
                "HINDSIGHT_API_URL": env["HINDSIGHT_API_URL"],
                "HINDSIGHT_BANK_ID": env["HINDSIGHT_BANK_ID"],
            },
            "volumes": [{
                "type": "bind",
                "source": env["HOST_DATA_DIR"],
                "target": "/data/hermes",
            }],
            "shm_size": "1gb",
            "healthcheck": {
                "test": ["CMD-SHELL", "curl -fsS http://127.0.0.1:8787/health || exit 1"],
                "interval": "30s",
                "timeout": "5s",
                "retries": 5,
                "start_period": "60s",
            },
            "platform": "linux/amd64",
        }
        return {"services": {"hermes-webui": service}}

    def write_files(self, config: InstanceComputeConfig) -> tuple[str, str, str]:
        project_dir = expert_compose_dir(config.slug)
        compose_path = str(project_dir / "docker-compose.yml")
        env_path = project_dir / ".env"
        env_map = self.build_env(config)
        compose = self.build_compose(config)

        lines = [f"{key}={value}" for key, value in env_map.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        try:
            import yaml
            with open(compose_path, "w", encoding="utf-8") as handle:
                yaml.dump(compose, handle, default_flow_style=False)
        except ImportError:
            import json
            with open(compose_path, "w", encoding="utf-8") as handle:
                json.dump(compose, handle, indent=2)

        profile = env_map["HERMES_PROFILE"]
        container_name = f"hermes-{profile}"
        return compose_path, str(env_path), container_name
