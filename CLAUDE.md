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
1. `monitor.py` (`EventLogMonitor`) runs in a daemon thread, polling the Windows Security Event Log (Event ID 4663) via PowerShell subprocess every 30 seconds (configurable via `POLL_INTERVAL` env var).
2. New events are parsed and written to SQLite via Flask-SQLAlchemy.
3. Flask routes in `app.py` query the database and render HTML templates.

**Key files:**
- `app.py` — Flask routes + app startup; initialises the DB and starts the monitor
- `monitor.py` — `EventLogMonitor` class; PowerShell subprocess calls, noise filtering, DB writes
- `db.py` — two SQLAlchemy models: `FileAccess` (log entries) and `ServerConfig` (for future multi-server use)
- `config.py` — Flask/SQLAlchemy config; reads `SECRET_KEY` and `POLL_INTERVAL` from env

**Monitor state:** `EventLogMonitor._last_poll_time` tracks the UTC timestamp of the last poll. Each poll queries events since that timestamp, filters noise, and stores new entries.

**Noise filtering (`monitor.py`):**
- Skips Windows system accounts: `SYSTEM`, `LOCAL SERVICE`, `NETWORK SERVICE`, `DWM-*`, `UMFD-*`
- Skips machine accounts (usernames ending with `$`)
- Skips events from `C:\Windows\`, `C:\ProgramData\Microsoft\`, and raw `\Device\HarddiskVolume` paths

**Action mapping (access mask → label):**
- `0x10000` → `delete`
- `0x106` (WriteData | AppendData | WriteAttributes) → `write`
- `0x1` (ReadData) → `read`
- anything else → `other`

**Required Windows setup (prerequisites):**
1. Enable audit policy for file system access:
   ```
   auditpol /set /subcategory:"File System" /success:enable
   ```
2. Set a SACL (audit ACE) on the directories you want to monitor — this is the primary way to control noise. Only files under audited directories generate Event ID 4663.
3. The app must run as Administrator (or as SYSTEM via the scheduled task) to read the Security Event Log.

**DB schema change note:** If upgrading from the SMB-based version, delete `instance/fileserver.db` before starting — the `FileAccess` table schema changed (`file_id`/`share_name` removed, `process_name` added).
