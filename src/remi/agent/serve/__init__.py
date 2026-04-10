"""serve — kernel bootstrap, HTTP server, and lifecycle management.

The ``Kernel`` class is the central object of the Agent OS. It owns
every infrastructure subsystem (LLM, sandbox, memory, events, tasks,
sessions, vectors, tools) and provides a single ``boot()`` entry point
that wires them all from settings.

Products call ``Kernel.boot()``, register their own tool providers,
load their manifests, and either call ``kernel.serve()`` for HTTP or
use ``kernel.runtime`` / ``kernel.supervisor`` directly.
"""

from remi.agent.serve.kernel import Kernel, KernelSettings

__all__ = ["Kernel", "KernelSettings"]
