"""Docker container sandbox — isolated execution via ephemeral containers.

Each session runs inside its own Docker container built from a minimal
image (stdlib + allowlisted data-science packages).  The host temp
directory is bind-mounted to ``/work`` inside the container so file
I/O can be done from the host side without ``docker exec``.

Uses the ``docker`` CLI via ``asyncio.create_subprocess_exec`` — no
Docker SDK dependency.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import structlog

from remi.agent.sandbox.bridge import DATA_BRIDGE_SOURCE
from remi.agent.sandbox.policy import is_dangerous_command
from remi.agent.sandbox.types import ExecResult, ExecStatus, Sandbox, SandboxSession

_log = structlog.get_logger(__name__)

_SANDBOX_ROOT = Path(tempfile.gettempdir()) / "remi-sandbox"


class DockerSandbox(Sandbox):
    """Docker-based sandbox — each session is an ephemeral container."""

    def __init__(
        self,
        image: str = "remi-sandbox:latest",
        root: Path | None = None,
        default_timeout: int = 30,
        max_output_bytes: int = 100_000,
        extra_env: dict[str, str] | None = None,
        network: str = "host",
        memory_limit: str = "512m",
        cpu_limit: float = 1.0,
    ) -> None:
        self._image = image
        self._root = root or _SANDBOX_ROOT
        self._root.mkdir(parents=True, exist_ok=True)
        self._default_timeout = default_timeout
        self._max_output = max_output_bytes
        self._extra_env = extra_env or {}
        self._network = network
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._sessions: dict[str, SandboxSession] = {}
        self._containers: dict[str, str] = {}  # session_id -> container_id
        self._session_env: dict[str, dict[str, str]] = {}

    async def create_session(
        self,
        session_id: str | None = None,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> SandboxSession:
        sid = session_id or f"sandbox-{uuid.uuid4().hex[:12]}"
        work_dir = self._root / sid
        work_dir.mkdir(parents=True, exist_ok=True)

        # Write the data bridge into the host dir (visible inside via mount)
        (work_dir / "remi_data.py").write_text(DATA_BRIDGE_SOURCE, encoding="utf-8")

        # Merge env vars
        merged_env = dict(self._extra_env)
        if extra_env:
            merged_env.update(extra_env)
            self._session_env[sid] = extra_env

        # Build docker create command
        cmd: list[str] = [
            "docker", "create",
            "--name", f"remi-sandbox-{sid}",
            f"--network={self._network}",
            f"--memory={self._memory_limit}",
            f"--cpus={self._cpu_limit}",
            "--pids-limit=100",
            "--read-only",
            "--tmpfs", "/tmp:size=64m",
            "-v", f"{work_dir}:/work",
            "-w", "/work",
        ]
        for key, value in merged_env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend([self._image, "sleep", "infinity"])

        result = await self._run_docker_cmd(cmd)
        if result["exit_code"] != 0:
            _log.error(
                "docker_create_failed",
                session_id=sid,
                stderr=result["stderr"],
            )
            raise RuntimeError(f"Failed to create sandbox container: {result['stderr']}")

        container_id = result["stdout"].strip()[:12]
        self._containers[sid] = container_id

        # Start the container
        start_result = await self._run_docker_cmd(["docker", "start", container_id])
        if start_result["exit_code"] != 0:
            _log.error("docker_start_failed", session_id=sid, stderr=start_result["stderr"])
            await self._run_docker_cmd(["docker", "rm", "-f", container_id])
            raise RuntimeError(f"Failed to start sandbox container: {start_result['stderr']}")

        session = SandboxSession(session_id=sid, working_dir=str(work_dir))
        self._sessions[sid] = session

        _log.info(
            "sandbox_session_created",
            session_id=sid,
            container_id=container_id,
            dir=str(work_dir),
        )
        return session

    async def exec_python(
        self,
        session_id: str,
        code: str,
        *,
        timeout_seconds: int = 30,
    ) -> ExecResult:
        session = self._sessions.get(session_id)
        container_id = self._containers.get(session_id)
        if session is None or container_id is None:
            return ExecResult(status=ExecStatus.ERROR, error=f"Session '{session_id}' not found")

        work_dir = Path(session.working_dir)
        script_name = f"_exec_{session.exec_count}.py"
        script_path = work_dir / script_name
        script_path.write_text(code, encoding="utf-8")

        timeout = timeout_seconds or self._default_timeout
        result = await self._docker_exec(
            container_id,
            ["python", f"/work/{script_name}"],
            timeout=timeout,
        )

        session.exec_count += 1
        new_files = self._scan_files(work_dir)
        result_files = [f for f in new_files if f not in session.files]
        session.files = new_files

        return ExecResult(
            status=result["status"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            duration_ms=result["duration_ms"],
            files_created=result_files,
            error=result.get("error"),
        )

    async def exec_shell(
        self,
        session_id: str,
        command: str,
        *,
        timeout_seconds: int = 30,
    ) -> ExecResult:
        session = self._sessions.get(session_id)
        container_id = self._containers.get(session_id)
        if session is None or container_id is None:
            return ExecResult(status=ExecStatus.ERROR, error=f"Session '{session_id}' not found")

        if is_dangerous_command(command):
            return ExecResult(
                status=ExecStatus.ERROR,
                error=f"Command blocked by sandbox policy: {command[:80]}",
            )

        work_dir = Path(session.working_dir)
        timeout = timeout_seconds or self._default_timeout
        result = await self._docker_exec(
            container_id,
            ["sh", "-c", command],
            timeout=timeout,
        )

        session.exec_count += 1
        new_files = self._scan_files(work_dir)
        result_files = [f for f in new_files if f not in session.files]
        session.files = new_files

        return ExecResult(
            status=result["status"],
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            duration_ms=result["duration_ms"],
            files_created=result_files,
            error=result.get("error"),
        )

    async def write_file(
        self,
        session_id: str,
        filename: str,
        content: str,
    ) -> str:
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")

        work_dir = Path(session.working_dir)
        safe_name = Path(filename).name
        file_path = work_dir / safe_name
        file_path.write_text(content, encoding="utf-8")

        if safe_name not in session.files:
            session.files.append(safe_name)

        return safe_name

    async def read_file(
        self,
        session_id: str,
        filename: str,
    ) -> str | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        work_dir = Path(session.working_dir)
        safe_name = Path(filename).name
        file_path = work_dir / safe_name

        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    async def list_files(self, session_id: str) -> list[str]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return self._scan_files(Path(session.working_dir))

    async def get_session(self, session_id: str) -> SandboxSession | None:
        return self._sessions.get(session_id)

    async def destroy_session(self, session_id: str) -> None:
        container_id = self._containers.pop(session_id, None)
        session = self._sessions.pop(session_id, None)
        self._session_env.pop(session_id, None)

        if container_id:
            await self._run_docker_cmd(["docker", "rm", "-f", container_id])

        if session is not None:
            work_dir = Path(session.working_dir)
            if work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
            _log.info(
                "sandbox_session_destroyed",
                session_id=session_id,
                container_id=container_id,
            )

    async def _docker_exec(
        self,
        container_id: str,
        cmd: list[str],
        timeout: int,
    ) -> dict[str, Any]:
        """Run a command inside a running container via ``docker exec``."""
        full_cmd = ["docker", "exec", container_id, *cmd]
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_raw, stderr_raw = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                proc.kill()
                await proc.wait()
                # Also stop the command inside the container
                await self._run_docker_cmd(["docker", "stop", "-t", "1", container_id])
                await self._run_docker_cmd(["docker", "start", container_id])
                elapsed = (time.monotonic() - start) * 1000
                return {
                    "status": ExecStatus.TIMEOUT,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -1,
                    "duration_ms": elapsed,
                    "error": f"Timed out after {timeout}s",
                }

            elapsed = (time.monotonic() - start) * 1000
            stdout = stdout_raw.decode("utf-8", errors="replace")[: self._max_output]
            stderr = stderr_raw.decode("utf-8", errors="replace")[: self._max_output]

            return {
                "status": ExecStatus.SUCCESS if proc.returncode == 0 else ExecStatus.ERROR,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "exit_code": proc.returncode or 0,
                "duration_ms": elapsed,
            }

        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return {
                "status": ExecStatus.ERROR,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "duration_ms": elapsed,
                "error": str(exc),
            }

    async def _run_docker_cmd(self, cmd: list[str]) -> dict[str, Any]:
        """Run a docker management command (create, start, rm, etc.)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_raw, stderr_raw = await asyncio.wait_for(
                proc.communicate(),
                timeout=30,
            )
            return {
                "stdout": stdout_raw.decode("utf-8", errors="replace").strip(),
                "stderr": stderr_raw.decode("utf-8", errors="replace").strip(),
                "exit_code": proc.returncode or 0,
            }
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "exit_code": -1}

    def _scan_files(self, work_dir: Path) -> list[str]:
        if not work_dir.exists():
            return []
        return sorted(
            f.name for f in work_dir.iterdir() if f.is_file() and not f.name.startswith("_exec_")
        )
