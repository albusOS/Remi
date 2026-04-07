"""runtime/conversation — thread management, compression, and compaction.

Internal to agent/runtime/. Not a public package.

Modules:
- ``thread.py``      — thread construction, trimming, output formatting
- ``compression.py`` — per-tool-call result compression and offload
- ``compaction.py``  — multi-stage context window management
"""
