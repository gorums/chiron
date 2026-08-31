# The Claude bridge — optional

**You probably do not need this.** A course site calls Anthropic directly: open its
`-local.html` copy from `dist/`, go to Settings, paste an API key, press Connect. Nothing to
install, nothing to keep running.

This folder is for one case only: **you would rather use Claude Code than an API key.** The
bridge routes questions through the `claude` command you are already signed in to, so no key
and no per-use billing are involved. Start it, then pick "Use the bridge" in the site's
Settings under the collapsed alternative section.

## How it works

A small program runs on your own computer and passes messages along:

```
course site (your browser)  →  http://127.0.0.1:8787  →  api.anthropic.com
```

It listens on `127.0.0.1` only, which means nothing outside this computer can reach it. It never writes your API key to disk, and never logs it.

## Setup, once

1. **Get an API key** — console.anthropic.com → API keys → Create key. Copy it (starts with `sk-ant-`). This is billed per use, separately from a Claude subscription; a typical question costs a fraction of a cent.
2. **Start the bridge** — double-click `start-bridge.bat`. A window opens saying it is listening on port 8787. Leave it open while you study.
3. **Open the course** — open the `-local.html` copy from `dist/<course>/`, not the published web link. A published page cannot reach your computer.
4. **Connect** — in the site, go to **Settings** in the sidebar, paste the key, click **Test connection**. The dot turns green.

After the first time, it is just: double-click `start-bridge.bat`, open the local course file, study.

## Where your key lives

In your browser's local storage for that file, and in memory in the bridge for the moment it takes to make each request. It is sent to `api.anthropic.com` and nowhere else. If you would rather not keep it in the browser, set it as an environment variable before starting instead, and leave the Settings field blank:

```
set ANTHROPIC_API_KEY=sk-ant-...
start-bridge.bat
```

## If something is wrong

| What you see | What it means |
|---|---|
| Settings dot stays grey | The bridge window is not running, or it started on a different port. |
| "Could not start on port 8787" | Something else is using that port. Run `set BRIDGE_PORT=8788`, start again, and change the URL in Settings to match. |
| "The API key was rejected" | Bad or revoked key. Make a new one in the Anthropic console. |
| "Rate limited or out of credit" | The key has no credit left, or you are sending too fast. |
| Python not found | Install Python from python.org and tick "Add python.exe to PATH". |

## Testing it without spending anything

```
set BRIDGE_ECHO=1
start-bridge.bat
```

The bridge then echoes your messages back instead of calling Anthropic. Useful for confirming the plumbing works before you put a real key in.
