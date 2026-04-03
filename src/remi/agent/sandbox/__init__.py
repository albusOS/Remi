"""Sandbox package — code execution ports, adapters, and factory.

Public API::

    from remi.agent.sandbox import Sandbox, build_sandbox
"""

from remi.agent.sandbox.factory import build_sandbox
from remi.agent.sandbox.types import Sandbox

__all__ = [
    "Sandbox",
    "build_sandbox",
]
