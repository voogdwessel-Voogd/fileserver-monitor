# File Server Monitor

Webapplicatie voor het monitoren van bestandstoegang op een Windows file server. De app leest het Windows Security Event Log (Event ID 4663) en toont wie welk bestand heeft geopend, bewerkt of verwijderd.

## Vereisten

- Windows Server of Windows 10/11 (als Administrator)
- Python 3.10+
- PowerShell 5.1+

## Installatie

```powershell
# Dependencies installeren
py -m pip install -r requirements.txt

# App starten (ontwikkelmodus)
py app.py
```

De app is bereikbaar op `http://localhost:5000`.

Om de app automatisch te starten bij het opstarten van de server, voer het installatiescript uit als Administrator:

```powershell
.\install-service.ps1
```

---

## Audit logging instellen op de file server

Voordat de monitor events ontvangt, moet Windows-auditlogging worden geconfigureerd.

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
$pad   = "D:\Data\Gedeeld"           # pas aan naar de gewenste map
$audit = New-Object System.Security.AccessControl.FileSystemAuditRule(
    "Everyone",                        # wie te auditen (of een specifieke gebruiker/groep)
    "ReadData, WriteData, Delete",     # welke acties
    "ContainerInherit, ObjectInherit", # doorwerking naar submappen en bestanden
    "None",
    "Success"                          # Success, Failure, of beide
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

## Configuratie

| Omgevingsvariabele | Standaard | Omschrijving |
|---|---|---|
| `POLL_INTERVAL` | `30` | Polling-interval in seconden |
| `RETENTION_DAYS` | `365` | Aantal dagen dat events bewaard worden (`0` = nooit verwijderen) |
| `SECRET_KEY` | `change-me-in-production` | Flask sessie-sleutel, wijzig in productie |

---

## Architectuur

Single-process Flask-app met een achtergrondthread.

| Bestand | Rol |
|---|---|
| `app.py` | Flask routes en app-startup |
| `monitor.py` | `EventLogMonitor` — PowerShell polling, ruisfiltering, DB-schrijven |
| `db.py` | SQLAlchemy-modellen: `FileAccess` en `ServerConfig` |
| `config.py` | Flask/SQLAlchemy-configuratie |

**Ruisfiltering:** systeemaccounts (`SYSTEM`, `LOCAL SERVICE`, `DWM-*`, `UMFD-*`), machine-accounts (eindigen op `$`) en Windows-systeempaden (`C:\Windows\`, `C:\ProgramData\Microsoft\`) worden automatisch weggefilterd.
