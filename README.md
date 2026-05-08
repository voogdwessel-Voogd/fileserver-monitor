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

## Functionaliteit

De app heeft vier schermen bereikbaar via de navigatiebalk:

| Scherm | Omschrijving |
|---|---|
| **Activiteitenlog** | Historisch overzicht van bestandstoegang, filterbaar op gebruiker, actie en periode |
| **Live** | Realtime weergave van events uit de afgelopen 5 minuten (ververst elke 10 seconden) |
| **Instellingen** | Alle configuratie op één pagina (zie hieronder) |

### Activiteitenlog

- Toont alle gelogde bestandstoegang **gegroepeerd per gebruiker** — elke gebruiker krijgt een eigen sectie met de bestandstoegang gesorteerd op tijdstip (nieuwste eerst)
- De eerste gebruiker is standaard uitgeklapt; overige gebruikers zijn ingeklapt en kunnen worden opengedraaid
- **Zoeken** op gebruikersnaam, datum en map/bestandspad — velden zijn combineerbaar
- **Scherm wissen** — verbergt alle bestaande logregels in de weergave zonder ze uit de database te verwijderen. Handig na het instellen van nieuwe filters zodat alleen nieuwe activiteit zichtbaar is.
- **Exporteren** — downloadt de gefilterde resultaten als CSV-bestand. Zonder actieve filters wordt de volledige database geëxporteerd. Het bestand gebruikt `;` als scheidingsteken en UTF-8 BOM zodat Excel het direct correct opent. De bestandsnaam bevat automatisch de toegepaste filters, bijv. `activiteitenlog_jan_2026-05-08.csv`.

### Instellingen

Alle configuratie staat op één pagina, verdeeld in vier secties:

**Algemeen**
- *Poll interval* — hoe vaak het Event Log wordt uitgelezen (standaard 30 seconden)
- *Bewaarperiode* — aantal dagen dat logregels bewaard worden (standaard 365 dagen, `0` = nooit verwijderen)
- *Log wissen* — verwijdert alle logregels permanent uit de database

**Mappen**
Geeft aan welke mappen gemonitord worden. Zonder actieve mappen worden events van alle paden bijgehouden. Voeg specifieke datamappen toe om de scope te beperken (bijv. `D:\Data\`).

**Account filters**
Bepaalt welke gebruikersaccounts gemonitord worden. Zonder actieve filters worden alle accounts bijgehouden. Ondersteunt wildcards:

| Patroon | Betekenis |
|---|---|
| `AH*` | Alle accounts die beginnen met `AH` |
| `DOMEIN\jan*` | Alle accounts van Jan in het domein |
| `*\marie.jansen` | Specifieke gebruiker in elk domein |

**Servers**
Beheerpagina voor te monitoren servers (voor toekomstige remote server-ondersteuning).

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

Een SACL (System Access Control List) bepaalt op welke mappen en bestanden geauditeerd wordt. Dit is de belangrijkste manier om ruis te beperken — audit **alleen de mappen die relevant zijn**, niet de volledige `C:\`-schijf.

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

> **Tip:** Stel ook de **Mappen**-filter in de app in op dezelfde map. Dit zorgt dat events van andere paden niet opgeslagen worden, ook als SACL breder is ingesteld.

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

Instellingen zijn te beheren via de webinterface (**Instellingen → Algemeen**) of via omgevingsvariabelen als fallback:

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
| `monitor.py` | `EventLogMonitor` — PowerShell polling, NT→DOS padconversie, ruisfiltering, DB-schrijven |
| `db.py` | SQLAlchemy-modellen: `FileAccess`, `AccountFilter`, `WatchPath`, `AppSetting`, `ServerConfig` |
| `config.py` | Flask/SQLAlchemy-configuratie en standaardwaarden |

**Ruisfiltering:** systeemaccounts (`SYSTEM`, `LOCAL SERVICE`, `DWM-*`, `UMFD-*`), machine-accounts (eindigen op `$`) en Windows-systeempaden (`C:\Windows\`, `C:\ProgramData\Microsoft\`) worden automatisch weggefilterd.

**NT→DOS padconversie:** Event ID 4663 rapporteert bestandspaden soms in NT device-formaat (`\Device\HarddiskVolume3\...`). De monitor converteert deze automatisch naar DOS-formaat (`C:\...`) via `QueryDosDevice` zodat de mapfilters correct werken.
