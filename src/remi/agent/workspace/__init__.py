"""Agent workspace — persistent working memory via sandbox files.

The workspace is a set of well-known Markdown files in the agent's sandbox
directory that persist across chat turns.  The agent reads them at the start
of each turn (via ``load_workspace``) and the runtime injects their contents
into the conversation thread so the agent never loses its plan, observations,
or accumulated context even when ``trim_thread`` drops old exchanges.

Public API::

    from remi.agent.workspace import load_workspace, inject_workspace, WORKSPACE_FILES
"""

from remi.agent.workspace.flush import flush_before_trim
from remi.agent.workspace.loader import (
    WORKSPACE_FILES,
    WorkspaceSnapshot,
    inject_workspace,
    load_workspace,
)

__all__ = [
    "WORKSPACE_FILES",
    "WorkspaceSnapshot",
    "flush_before_trim",
    "inject_workspace",
    "load_workspace",
]
