"""SSRF and redirect-escape guards for outbound HTTP connectors."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import parse_private_network_allowlist
from app.core.exceptions import ValidationError

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }
)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_private: set[str]) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    # Cloud metadata ranges
    if ip in ipaddress.ip_network("169.254.0.0/16") or ip in ipaddress.ip_network("fd00:ec2::/32"):
        return True
    if ip.version == 4 and str(ip) == "169.254.169.254":
        return True
    if ip.is_private:
        for item in allow_private:
            try:
                if "/" in item:
                    if ip in ipaddress.ip_network(item, strict=False):
                        return False
                elif ip == ipaddress.ip_address(item):
                    return False
            except ValueError:
                continue
        return True
    return False


def resolve_and_validate_url(
    url: str,
    *,
    allow_private_networks: set[str] | None = None,
    allow_schemes: set[str] | None = None,
) -> str:
    parsed = urlparse(url)
    schemes = allow_schemes or {"http", "https"}
    if parsed.scheme not in schemes:
        raise ValidationError(
            message="HTTP URL scheme 不被允许",
            message_key="errors.knowledge.http_url_blocked",
            details={"url": url},
        )
    host = (parsed.hostname or "").strip().lower()
    if not host or host in BLOCKED_HOSTNAMES:
        raise ValidationError(
            message="HTTP URL host 被拒绝",
            message_key="errors.knowledge.http_url_blocked",
            details={"host": host},
        )
    allow_private = allow_private_networks if allow_private_networks is not None else parse_private_network_allowlist()
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValidationError(
            message="HTTP URL DNS 解析失败",
            message_key="errors.knowledge.http_url_blocked",
            details={"host": host},
        ) from exc
    if not infos:
        raise ValidationError(
            message="HTTP URL DNS 无结果",
            message_key="errors.knowledge.http_url_blocked",
            details={"host": host},
        )
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip, allow_private=allow_private):
            raise ValidationError(
                message="HTTP URL 目标地址被拒绝",
                message_key="errors.knowledge.http_url_blocked",
                details={"host": host, "ip": str(ip)},
            )
    return url


class SafeRedirectGuard:
    """Validate every redirect hop against SSRF rules (redirect escape prevention)."""

    def __init__(self, *, allow_private_networks: set[str] | None = None, max_redirects: int = 5) -> None:
        self.allow_private_networks = (
            allow_private_networks if allow_private_networks is not None else parse_private_network_allowlist()
        )
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def on_redirect(self, url: str) -> str:
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise ValidationError(
                message="HTTP 重定向次数过多",
                message_key="errors.knowledge.http_url_blocked",
            )
        return resolve_and_validate_url(url, allow_private_networks=self.allow_private_networks)
