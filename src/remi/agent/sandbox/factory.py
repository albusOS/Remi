"""Sandbox factory — selects and constructs the sandbox backend.

The container calls ``build_sandbox(settings)`` — it does not inline
backend selection or construction logic.

Supported backends
------------------
local  (default)
    Long-lived Python subprocess per session running on the host.
    Adequate for single-server deployments where the API and agent
    processes share the same machine.

docker
    Spawn an isolated Docker container per session via the Docker socket.
    Requires ``/var/run/docker.sock`` to be mounted into the API container
    and the ``remi-sandbox`` image to be present on the host.
"""

from __future__ import annotations

import importlib

import structlog

from remi.agent.sandbox.types import SandboxSettings
from remi.agent.sandbox.adapters.local import LocalSandbox
from remi.agent.sandbox.types import Sandbox

_log = structlog.get_logger(__name__)

_ADAPTERS: dict[str, tuple[str, str]] = {
    "docker": ("remi.agent.sandbox.adapters.docker", "DockerSandbox"),
}


def build_sandbox(
    settings: SandboxSettings,
    *,
    api_url: str = "",
    session_files: dict[str, str] | None = None,
) -> Sandbox:
    """Construct the sandbox backend selected by ``settings.backend``.

    *api_url* is injected by the composition root so the kernel never
    reaches into product-level ``ApiSettings``.
    """
    cfg = settings
    extra_env = {"REMI_API_URL": api_url} if api_url else {}

    backend = cfg.backend.lower()

    if backend == "local":
        _log.info("sandbox_backend", backend="local", api_url=api_url)
        sb: Sandbox = LocalSandbox(
            extra_env=extra_env,
            default_timeout=cfg.default_timeout,
            max_output_bytes=cfg.max_output_bytes,
            session_ttl_seconds=cfg.session_ttl_seconds,
        )
    elif backend in _ADAPTERS:
        module_path, class_name = _ADAPTERS[backend]
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _log.info(
            "sandbox_backend",
            backend=backend,
            api_url=api_url,
            image=cfg.image,
            network=cfg.network,
        )
        sb = cls(
            image=cfg.image,
            network=cfg.network,
            extra_env=extra_env,
            default_timeout=cfg.default_timeout,
            max_output_bytes=cfg.max_output_bytes,
            session_ttl_seconds=cfg.session_ttl_seconds,
            memory_limit=cfg.memory_limit,
            cpu_quota=cfg.cpu_quota,
            pids_limit=cfg.pids_limit,
        )
    else:
        _log.warning(
            "sandbox_unknown_backend",
            backend=backend,
            fallback="local",
        )
        _log.info("sandbox_backend", backend="local", api_url=api_url)
        sb = LocalSandbox(
            extra_env=extra_env,
            default_timeout=cfg.default_timeout,
            max_output_bytes=cfg.max_output_bytes,
            session_ttl_seconds=cfg.session_ttl_seconds,
        )

    if session_files:
        sb.set_session_files(session_files)
    return sb
