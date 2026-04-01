# Minimal sandbox image for REMI agent code execution.
#
# Contains ONLY stdlib + allowlisted data-science packages.
# No remi, anthropic, sqlalchemy, httpx, or any infrastructure package.
# The remi_data.py bridge (injected at session creation) talks to the
# REMI API over HTTP — that is the sole interface to the platform.

FROM python:3.13-slim AS builder

RUN pip install --no-cache-dir \
    pandas \
    numpy \
    matplotlib \
    scipy \
    statsmodels \
    scikit-learn

# ---------- runtime stage ----------
FROM python:3.13-slim

COPY --from=builder /usr/local/lib/python3.13/site-packages \
                    /usr/local/lib/python3.13/site-packages

# Strip pip so sandbox code can't install extra packages at runtime
RUN rm -rf /usr/local/lib/python3.13/site-packages/pip* \
           /usr/local/lib/python3.13/site-packages/setuptools* \
           /usr/local/bin/pip*

RUN useradd --create-home --shell /bin/false sandbox

USER sandbox
WORKDIR /work
