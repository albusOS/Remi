"""Test DockerSandbox — container-based isolated execution.

Requires Docker running and the ``remi-sandbox:latest`` image built.
All tests are marked ``docker`` so they can be skipped in CI without Docker.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from remi.sandbox.docker import DockerSandbox
from remi.sandbox.ports import ExecStatus


def _docker_available() -> bool:
    """Check if docker daemon is reachable and sandbox image exists."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "remi-sandbox:latest"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _docker_available(), reason="Docker not available or sandbox image not built"),
]


@pytest.fixture
async def sandbox(tmp_path: Path) -> DockerSandbox:
    sb = DockerSandbox(root=tmp_path / "sandbox")
    yield sb  # type: ignore[misc]
    # Cleanup all sessions
    for sid in list(sb._sessions):
        await sb.destroy_session(sid)


async def test_create_and_destroy_session(sandbox: DockerSandbox) -> None:
    session = await sandbox.create_session("docker-1")
    assert session.session_id == "docker-1"
    assert Path(session.working_dir).exists()

    await sandbox.destroy_session("docker-1")
    assert await sandbox.get_session("docker-1") is None


async def test_exec_python_hello(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d1")
    result = await sandbox.exec_python("d1", 'print("hello from docker")')
    assert result.status == ExecStatus.SUCCESS
    assert "hello from docker" in result.stdout


async def test_exec_python_error(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d2")
    result = await sandbox.exec_python("d2", "raise ValueError('boom')")
    assert result.status == ExecStatus.ERROR
    assert "boom" in result.stderr


async def test_pandas_available(sandbox: DockerSandbox) -> None:
    """pandas should be available inside the container."""
    await sandbox.create_session("d3")
    result = await sandbox.exec_python(
        "d3",
        "import pandas as pd; print(pd.__version__)",
    )
    assert result.status == ExecStatus.SUCCESS
    assert result.stdout.strip()


async def test_numpy_available(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d4")
    result = await sandbox.exec_python(
        "d4",
        "import numpy as np; print(np.array([1,2,3]).sum())",
    )
    assert result.status == ExecStatus.SUCCESS
    assert "6" in result.stdout


async def test_matplotlib_available(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d5")
    result = await sandbox.exec_python(
        "d5",
        "import matplotlib; print(matplotlib.__version__)",
    )
    assert result.status == ExecStatus.SUCCESS
    assert result.stdout.strip()


async def test_remi_import_blocked(sandbox: DockerSandbox) -> None:
    """remi packages should NOT be importable inside the container."""
    await sandbox.create_session("d6")
    result = await sandbox.exec_python("d6", "import remi")
    assert result.status == ExecStatus.ERROR
    assert "ModuleNotFoundError" in result.stderr or result.exit_code != 0


async def test_pip_not_available(sandbox: DockerSandbox) -> None:
    """pip should be stripped so sandbox can't install extra packages."""
    await sandbox.create_session("d7")
    result = await sandbox.exec_shell("d7", "pip install requests 2>&1 || echo 'pip blocked'")
    assert "pip blocked" in result.stdout or result.exit_code != 0


async def test_write_and_read_file(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d8")
    name = await sandbox.write_file("d8", "data.csv", "a,b,c\n1,2,3\n")
    assert name == "data.csv"

    content = await sandbox.read_file("d8", "data.csv")
    assert content is not None
    assert "a,b,c" in content


async def test_exec_python_sees_written_file(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d9")
    await sandbox.write_file("d9", "input.txt", "hello docker")

    result = await sandbox.exec_python(
        "d9",
        'with open("input.txt") as f: print(f.read().upper())',
    )
    assert result.status == ExecStatus.SUCCESS
    assert "HELLO DOCKER" in result.stdout


async def test_exec_python_creates_file(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d10")
    result = await sandbox.exec_python(
        "d10",
        'with open("result.txt", "w") as f: f.write("42")\nprint("done")',
    )
    assert result.status == ExecStatus.SUCCESS
    assert "result.txt" in result.files_created

    content = await sandbox.read_file("d10", "result.txt")
    assert content == "42"


async def test_timeout(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d11")
    result = await sandbox.exec_python(
        "d11",
        "import time; time.sleep(10)",
        timeout_seconds=2,
    )
    assert result.status == ExecStatus.TIMEOUT


async def test_dangerous_command_blocked(sandbox: DockerSandbox) -> None:
    await sandbox.create_session("d12")
    result = await sandbox.exec_shell("d12", "sudo rm -rf /")
    assert result.status == ExecStatus.ERROR
    assert "blocked" in (result.error or "").lower()
