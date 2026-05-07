# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
py -m pip install -r requirements.txt

# Run the app (dev mode, auto-reloads)
py app.py

# App runs at http://localhost:5000
```

Use `py` (the Python launcher) — `python` is not on PATH on this machine.

## Architecture

Single-process Flask app with a background monitoring thread.

**Data flow:**
1. `monitor.py` (`SmbMonitor`) runs in a daemon thread, polling `Get-SmbOpenFile` via PowerShell subprocess every 30 seconds (configurable via `POLL_INTERVAL` env var).
2. Changes (files opened/closed) are written to SQLite via Flask-SQLAlchemy.
3. Flask routes in `app.py` query the database and render HTML templates.

**Key files:**
- `app.py` — Flask routes + app startup; also initialises the DB and starts the monitor
- `monitor.py` — `SmbMonitor` class; PowerShell subprocess calls, change detection, DB writes
- `db.py` — two SQLAlchemy models: `FileAccess` (log entries) and `ServerConfig` (configured servers)
- `config.py` — Flask/SQLAlchemy config; reads `SECRET_KEY` and `POLL_INTERVAL` from env

**Monitor state:** `SmbMonitor._open_files` is an in-memory dict `{server_key: {file_id: file_info}}` that tracks the previous poll result. Diffs between polls produce `opened`/`closed` log entries.

**Remote servers:** Hostname stored in `ServerConfig.hostname` (empty = local). When non-empty, the PowerShell command is wrapped in `Invoke-Command -ComputerName <hostname>`. Requires WinRM/PowerShell Remoting enabled on the target (`Enable-PSRemoting`) and admin credentials.

**Required Windows privileges:** `Get-SmbOpenFile` requires administrator rights on the file server being monitored.
