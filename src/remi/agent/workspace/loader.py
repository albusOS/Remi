"""Workspace loader — read/inject persistent agent working memory.

Well-known files in the sandbox working directory:

- ``PLAN.md``    — current objectives and approach (the agent's "todo list")
- ``CONTEXT.md`` — accumulated context from prior turns (flush-before-truncate)

The loader reads whatever subset exists and renders them into a single
system message for thread injection.  Files that don't exist are silently
skipped — a fresh session simply has no workspace context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from remi.agent.sandbox.types import Sandbox

_log = structlog.get_logger(__name__)

WORKSPACE_FILES: list[str] = ["PLAN.md", "CONTEXT.md"]

_MAX_FILE_CHARS = 8_000
_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Contents of the workspace files at the start of a turn."""

    files: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not any(v.strip() for v in self.files.values())

    def render(self) -> str:
        """Render the workspace into a system-message string."""
        if self.is_empty:
            return ""
        parts = ["[Workspace — persistent working memory from prior turns]"]
        for name, content in self.files.items():
            text = content.strip()
            if not text:
                continue
            if len(text) > _MAX_FILE_CHARS:
                text = text[:_MAX_FILE_CHARS] + f"\n\n[...truncated, {len(content)} chars total]"
            parts.append(f"### {name}\n{text}")
        return "\n\n".join(parts)

    @property
    def estimated_tokens(self) -> int:
        return sum(len(v) for v in self.files.values()) // _CHARS_PER_TOKEN


async def load_workspace(
    sandbox: Sandbox,
    session_id: str,
) -> WorkspaceSnapshot:
    """Read all workspace files from the sandbox session directory.

    Returns a snapshot containing whichever files exist.  Missing files
    are silently omitted — a new session starts with an empty workspace.
    """
    session = await sandbox.get_session(session_id)
    if session is None:
        return WorkspaceSnapshot()

    files: dict[str, str] = {}
    for filename in WORKSPACE_FILES:
        content = await sandbox.read_file(session_id, filename)
        if content is not None and content.strip():
            files[filename] = content

    if files:
        _log.debug(
            "workspace_loaded",
            session_id=session_id,
            files=list(files.keys()),
            total_chars=sum(len(v) for v in files.values()),
        )
    return WorkspaceSnapshot(files=files)


def inject_workspace(
    thread: list,
    snapshot: WorkspaceSnapshot,
) -> None:
    """Insert workspace context into the thread before the last user message.

    Uses the same tail-injection pattern as ContextBuilder — the workspace
    appears in recent context where the model's attention is strongest,
    while keeping the system-prompt prefix stable for KV-cache hits.
    """
    if snapshot.is_empty:
        return

    from remi.agent.llm.types import Message

    rendered = snapshot.render()
    if not rendered:
        return

    ws_msg = Message(role="system", content=rendered)

    insert_idx = len(thread)
    for i in range(len(thread) - 1, -1, -1):
        if thread[i].role == "user":
            insert_idx = i
            break

    thread.insert(insert_idx, ws_msg)
