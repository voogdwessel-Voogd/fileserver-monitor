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

---

## Audit logging instellen op de file server

Dit zijn de stappen om Windows-auditlogging te activeren zodat de monitor events ontvangt.

### Stap 1 — Auditbeleid inschakelen

Voer uit als Administrator (eenmalig):

```powershell
auditpol /set /subcategory:"File System" /success:enable /failure:enable
```

Controleren of het actief is:

```powershell
auditpol /get /subcategory:"File System"
```

Verwachte uitvoer:
```
  File System                     Success and Failure
```

> **Opmerking:** Op domeinomgevingen kan het auditbeleid worden afgedwongen via Group Policy:
> `Computer Configuration → Windows Settings → Security Settings → Advanced Audit Policy Configuration → Object Access → Audit File System`

---

### Stap 2 — SACL instellen op te monitoren mappen

Een SACL (System Access Control List) bepaalt op welke mappen en bestanden geauditeerd wordt. Dit is de belangrijkste manier om ruis te beperken — audit alleen de mappen die relevant zijn.

**Via PowerShell (aanbevolen):**

```powershell
$pad    = "D:\Data\Gedeeld"          # pas aan naar de gewenste map
$audit  = New-Object System.Security.AccessControl.FileSystemAuditRule(
    "Everyone",                       # wie te auditen (of een specifieke gebruiker/groep)
    "ReadData, WriteData, Delete",    # welke acties
    "ContainerInherit, ObjectInherit",# doorwerking naar submappen en bestanden
    "None",
    "Success"                         # Success, Failure, of beide
)
$acl = Get-Acl $pad
$acl.AddAuditRule($audit)
Set-Acl $pad $acl
```

**Via de GUI:**
1. Rechtermuisknop op de map → **Eigenschappen** → tabblad **Beveiliging**
2. Klik op **Geavanceerd** → tabblad **Controle**
3. Klik op **Toevoegen** → selecteer principal (bijv. `Iedereen` of een specifieke groep)
4. Vink de gewenste machtigingen aan: `Map weergeven / Bestanden uitvoeren`, `Bestanden maken / Gegevens schrijven`, `Verwijderen`
5. Zorg dat **Van toepassing op** staat op `Deze map, submappen en bestanden`

> **Tip:** Audit niet de volledige `C:\`-schijf maar alleen de specifieke datamappen (bijv. `D:\Data\`). Dit voorkomt duizenden events per seconde van Windows zelf.

---

### Stap 3 — Verifiëren dat events binnenkomen

Open Event Viewer en navigeer naar:
```
Windows Logboeken → Beveiliging
```
Filter op Event ID **4663**. Na het openen van een bestand in de gemonitorde map moet binnen enkele seconden een event verschijnen.

Of via PowerShell:

```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4663} -MaxEvents 5 |
    Select-Object TimeCreated, Message | Format-List
```

---

### Omgevingsvariabelen

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `POLL_INTERVAL` | `30` | Polling-interval in seconden |
| `RETENTION_DAYS` | `365` | Aantal dagen dat events bewaard worden (0 = nooit verwijderen) |
| `SECRET_KEY` | `change-me-in-production` | Flask sessie-sleutel, wijzig in productie |

---

**DB schema change note:** If upgrading from the SMB-based version, delete `instance/fileserver.db` before starting — the `FileAccess` table schema changed (`file_id`/`share_name` removed, `process_name` added).
