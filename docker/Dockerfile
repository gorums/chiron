# One image, two services. Studio and the bridge need exactly the same things — Python to
# run, and the Claude Code CLI to reach Claude — so they share a build and differ only in the
# command compose gives them. Two Dockerfiles here would be two things to keep in step.

FROM python:3.13-slim

# Node is here only to install the Claude Code CLI. Everything else is Python.
# git and ca-certificates: the CLI expects both.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code \
 && npm cache clean --force \
 && apt-get purge -y curl \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# The build engine's only third-party dependency.
RUN pip install --no-cache-dir markdown==3.10.3

# Claude Code keeps two things in $HOME: the ~/.claude directory (OAuth tokens, mounted from
# the host) and a separate ~/.claude.json holding UI state. Only the first is mounted, so the
# CLI warns on every call that the second is missing. The warning goes to stderr and does not
# corrupt output, but it would run onboarding on each invocation. Seed a minimal one that
# stays inside the image; nothing here needs to persist or come from the host.
RUN printf '{"hasCompletedOnboarding":true}' > /root/.claude.json

WORKDIR /work

# Nothing is COPYed: the repo arrives as a bind mount so that a course written inside the
# container is a real file in the user's folder, and editing the platform does not need a
# rebuild. Rebuild only when this file changes.

# Both services bind all interfaces *inside* the container. Compose publishes their ports to
# 127.0.0.1 on the host, so they stay unreachable from the network — the loopback default in
# the code is preserved at the boundary that actually matters.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STUDIO_HOST=0.0.0.0 \
    BRIDGE_HOST=0.0.0.0

EXPOSE 8790 8787

CMD ["python", "platform/build.py", "studio", "--no-open"]
