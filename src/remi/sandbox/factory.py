"""Sandbox factory — selects and constructs the appropriate backend.

The container calls ``build_sandbox(settings)`` — it does not inline
backend selection or construction logic.
"""

from __future__ import annotations

import platform
import subprocess

import structlog

from remi.sandbox.types import Sandbox
from remi.types.config import RemiSettings

_log = structlog.get_logger(__name__)


def _resolve_network(explicit: str) -> str:
    """Pick the Docker network mode.  Empty string → platform default."""
    if explicit:
        return explicit
    return "host" if platform.system() == "Linux" else "bridge"


def build_sandbox(settings: RemiSettings) -> Sandbox:
    """Select and construct the appropriate sandbox backend."""
    cfg = settings.sandbox
    network = _resolve_network(cfg.network)
    api_url = _resolve_api_url(settings, network)
    extra_env = {"REMI_API_URL": api_url}

    backend = cfg.backend
    if backend == "auto":
        backend = "docker" if _docker_image_exists(cfg.image) else "local"

    if backend == "docker":
        from remi.sandbox.docker import DockerSandbox

        _log.info("sandbox_backend", backend="docker", image=cfg.image, network=network)
        return DockerSandbox(
            image=cfg.image,
            extra_env=extra_env,
            network=network,
            memory_limit=cfg.memory_limit,
            cpu_limit=cfg.cpu_limit,
            default_timeout=cfg.default_timeout,
            max_output_bytes=cfg.max_output_bytes,
        )

    from remi.sandbox.local import LocalSandbox

    _log.info("sandbox_backend", backend="local")
    return LocalSandbox(
        extra_env=extra_env,
        default_timeout=cfg.default_timeout,
        max_output_bytes=cfg.max_output_bytes,
    )


def _resolve_api_url(settings: RemiSettings, network: str) -> str:
    """Determine the API URL the sandbox should use to reach the REMI server."""
    port = settings.api.port
    backend = settings.sandbox.backend
    is_docker = backend == "docker" or (
        backend == "auto" and _docker_image_exists(settings.sandbox.image)
    )

    if is_docker:
        if network == "host":
            return f"http://127.0.0.1:{port}"
        return f"http://host.docker.internal:{port}"

    return f"http://127.0.0.1:{port}"


def _docker_image_exists(image: str) -> bool:
    """Check if Docker daemon is reachable and the sandbox image is built."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
