"""The Jupyter server configuration for the course platform, used by both routes to run it.

    docker compose up          the `jupyter` service mounts this file as the server's config
    build.py jupyter           runs `python -m notebook --config=<this file>` on the host

It reads the same settings as everything else - `jupyter.*` and `studio.*` in
platform/settings.json, overridden by JUPYTER_PORT, JUPYTER_TOKEN, JUPYTER_HOST,
STUDIO_PORT and the rest of ENV_KEYS - so the port Studio tells a course page, the port
this server binds, and the origin it allows to frame it never disagree.

What it sets, and why:

- The root directory is the courses directory, so `courses/<id>/notebooks/<file>` is
  `/notebooks/<id>/notebooks/<file>` on the server: the course page builds that URL.
- A fixed token, from settings. The page gets it from Studio (`GET /api/jupyter`), which
  binds to loopback; the served port is published to loopback too. Do not remove it.
- `frame-ancestors` in the Content-Security-Policy names Studio's origin. Jupyter's
  default is `'self'`, which refuses to be framed by the course page. Same host, other
  port, so the login cookie is same-site and travels into the frame.
- No terminals, no trash: the container has neither a shell to offer nor a bin to fill.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform"))

from coursekit.settings import ANY_HOST, LOOPBACK, SETTINGS  # noqa: E402

c = get_config()  # noqa: F821 - Jupyter defines it before running this file

host = str(SETTINGS.get("jupyter.host"))
c.ServerApp.ip = host
c.ServerApp.port = int(SETTINGS.get("jupyter.port"))
c.ServerApp.open_browser = False
c.ServerApp.root_dir = SETTINGS.courses_dir
c.ServerApp.allow_remote_access = host in ANY_HOST
# The container runs as root, and Jupyter refuses to start as root unless told so; on the
# host this is a no-op for an ordinary user.
c.ServerApp.allow_root = True
c.ServerApp.terminals_enabled = False
c.FileContentsManager.delete_to_trash = False

c.IdentityProvider.token = str(SETTINGS.get("jupyter.token") or "")

studio = SETTINGS.studio_url
ancestors = " ".join(sorted({studio, studio.replace(LOOPBACK, "localhost")}))
c.ServerApp.tornado_settings = {
    "headers": {
        "Content-Security-Policy": "frame-ancestors 'self' %s; report-uri /api/security/csp-report"
        % ancestors,
    }
}
