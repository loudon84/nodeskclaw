"""Compute a unified display_status from instance status + health_status."""


def compute_docker_display_status(docker_status: str, health_status: str) -> str:
    if docker_status == "running" and health_status == "healthy":
        return "running"
    if docker_status == "running" and health_status != "healthy":
        return "unreachable"
    if docker_status in ("exited", "created", "stopped"):
        return "stopped"
    if docker_status == "restarting":
        return "restarting"
    if docker_status == "missing":
        return "missing"
    return "unknown"


def compute_display_status(status: str, health_status: str = "unknown") -> str:
    if status == "running":
        docker_like = compute_docker_display_status("running", health_status)
        if docker_like == "running":
            return "ready"
        if docker_like == "unreachable":
            return "unreachable"
        return "checking"
    return {
        "creating": "preparing", "pending": "preparing", "deploying": "preparing",
        "restarting": "restarting", "updating": "updating",
        "rebuilding": "rebuilding", "restoring": "restoring",
        "learning": "learning", "failed": "error", "deleting": "leaving",
        "stopped": "stopped", "missing": "missing", "unknown": "unknown",
    }.get(status, status)
