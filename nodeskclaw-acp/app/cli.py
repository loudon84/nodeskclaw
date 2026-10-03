from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys

from app.agent import AcpV1Agent
from app.config import Settings
from app.constants import (
    ACP_PROTOCOL_VERSION,
    ACP_SDK_PIN,
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_VERSION,
    CONFORMANCE_LABEL,
    REMOTE_AGENT_CONTRACT_DIGEST,
    REMOTE_AGENT_CONTRACT_VERSION,
)
from app.credentials import CredentialStore
from app.errors import AdapterError
from app.jsonrpc import JsonRpcServer
from app.permission_bridge import PermissionBridge
from app.profile import load_profile
from app.prompt_turn import PromptTurnController
from app.remote_client import RemoteAgentHttpClient
from app.session_registry import SessionRegistry


def _settings() -> Settings:
    settings = Settings()
    if not settings.NODESKCLAW_BASE_URL.strip():
        raise SystemExit("NODESKCLAW_BASE_URL 未设置")
    return settings


async def _serve(profile_path: str) -> None:
    settings = _settings()
    profile = load_profile(profile_path)
    client = RemoteAgentHttpClient(settings, CredentialStore(settings, None))  # type: ignore[arg-type]
    store = CredentialStore(settings, client.refresh_tokens)
    client.store = store
    registry = SessionRegistry(profile.agent_ref, max_sessions=settings.NODESKCLAW_ACP_MAX_SESSIONS)
    permissions = PermissionBridge(client)
    turns = PromptTurnController(
        profile,
        registry,
        client,
        permissions,
        artifact_hints=settings.NODESKCLAW_ACP_ARTIFACT_HINTS,
    )
    agent = AcpV1Agent(profile, registry, client, turns, permissions, sys.stdout)
    server = JsonRpcServer(agent)
    try:
        await server.serve()
    finally:
        await client.close()


def _login() -> None:
    settings = _settings()
    if (settings.NODESKCLAW_CREDENTIAL_MODE or "").strip().lower() == "managed":
        raise SystemExit("ACP_DESKTOP_CREDENTIAL_INVALID")
    account = os.environ.get("NODESKCLAW_LOGIN_ACCOUNT") or input("account: ")
    password = os.environ.get("NODESKCLAW_LOGIN_PASSWORD") or getpass.getpass("password: ")

    async def run() -> None:
        client = RemoteAgentHttpClient(settings, CredentialStore(settings, None))  # type: ignore[arg-type]
        store = CredentialStore(settings, client.refresh_tokens)
        client.store = store
        try:
            data = await client.login(account, password)
            access = str(data.get("access_token") or "")
            refresh = str(data.get("refresh_token") or "")
            store.store_login_tokens(access, refresh)
        finally:
            await client.close()

    asyncio.run(run())


def _logout() -> None:
    settings = _settings()
    store = CredentialStore(settings, lambda *_: None)
    store.keyring_clear()


def _doctor(profile_path: str | None) -> None:
    settings = _settings()
    report = {
        "protocolVersion": ACP_PROTOCOL_VERSION,
        "sdk": ACP_SDK_PIN,
        "conformance": CONFORMANCE_LABEL,
        "remoteAgentContractDigest": REMOTE_AGENT_CONTRACT_DIGEST,
        "baseUrl": settings.NODESKCLAW_BASE_URL,
        "profile": None,
        "auth": "missing",
    }
    if profile_path:
        profile = load_profile(profile_path)
        report["profile"] = {"name": profile.name, "agent_ref": profile.agent_ref}

    async def run() -> None:
        client = RemoteAgentHttpClient(settings, CredentialStore(settings, None))  # type: ignore[arg-type]
        store = CredentialStore(settings, client.refresh_tokens)
        client.store = store
        try:
            await store.resolve_access_token()
            await client.doctor_me()
            report["auth"] = "ok"
        except AdapterError as exc:
            report["auth"] = exc.symbol
        finally:
            await client.close()
        print(json.dumps(report, ensure_ascii=False))

    asyncio.run(run())


def _version() -> None:
    from app.constants import ADAPTER_CONTRACT_DIGEST

    print(
        json.dumps(
            {
                "adapterVersion": ADAPTER_VERSION,
                "protocolVersion": ACP_PROTOCOL_VERSION,
                "adapterContractVersion": ADAPTER_CONTRACT_VERSION,
                "adapterContractDigest": ADAPTER_CONTRACT_DIGEST,
                "remoteAgentContractVersion": REMOTE_AGENT_CONTRACT_VERSION,
                "remoteAgentContractDigest": REMOTE_AGENT_CONTRACT_DIGEST,
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="nodeskclaw-acp")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--profile", required=True)
    sub.add_parser("login")
    sub.add_parser("logout")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--profile")
    version = sub.add_parser("version")
    version.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args()
    if args.command == "serve":
        asyncio.run(_serve(args.profile))
    elif args.command == "login":
        _login()
    elif args.command == "logout":
        _logout()
    elif args.command == "doctor":
        _doctor(args.profile)
    elif args.command == "version":
        _version()


if __name__ == "__main__":
    main()
