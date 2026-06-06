import fnmatch
import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
]

_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}


class SSRFGuard:
    @staticmethod
    def check_url(url: str, host_whitelist: list[str] | None = None) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname in _LOOPBACK_HOSTNAMES:
            return False

        if host_whitelist:
            for pattern in host_whitelist:
                if fnmatch.fnmatch(hostname, pattern):
                    return True

        try:
            ip = ipaddress.ip_address(hostname)
            for network in _PRIVATE_NETWORKS:
                if ip in network:
                    return False
        except ValueError:
            pass

        return True
