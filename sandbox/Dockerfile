# REMI sandbox image — isolated Python execution environment.
#
# This image runs agent-generated code inside a throwaway container per
# session.  It intentionally has NO access to the REMI source tree or
# application secrets; it communicates back to the host API only via the
# `remi` CLI operating in client mode (REMI_API_URL env var).
#
# Security posture
# ----------------
# - Non-root user (sandbox) with no sudo
# - Standard library + data/analytics packages + remi CLI
# - No Docker socket, no host mount, no privileged flag
# - Network egress limited to the REMI API by Docker network policy
#
# Build (from repo root)
# ----------------------
#   docker build -t remi-sandbox:latest -f sandbox/Dockerfile .
#
# The API container spawns sessions via DockerSandbox, which starts
# each container with `sleep infinity` and uses `docker exec` for code
# execution.  Network is restricted to the remi_sandbox internal bridge.

FROM python:3.13-slim

# Analytics packages
RUN pip install --no-cache-dir \
        pandas \
        numpy \
        scipy \
        scikit-learn \
        statsmodels

# Install remi CLI from source.  In the sandbox, REMI_API_URL is always
# set so the CLI runs in client mode (stdlib urllib -> host API).
COPY pyproject.toml README.md ./build/
COPY src/ ./build/src/
RUN pip install --no-cache-dir ./build \
    && rm -rf ./build

# Non-root execution
RUN useradd --create-home --shell /bin/false --uid 1001 sandbox
USER sandbox

WORKDIR /session

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

HEALTHCHECK --interval=30s --timeout=5s --retries=2 \
    CMD ["python", "-c", "print('ok')"]
