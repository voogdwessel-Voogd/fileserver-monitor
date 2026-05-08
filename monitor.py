import subprocess
import json
import threading
import time
import logging
import fnmatch
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_SYSTEM_ACCOUNTS = frozenset({
    'SYSTEM', 'LOCAL SERVICE', 'NETWORK SERVICE',
    'DWM-1', 'DWM-2', 'DWM-3',
    'UMFD-0', 'UMFD-1', 'UMFD-2',
    'ANONYMOUS LOGON',
})

_NOISY_PATH_PREFIXES = (
    'C:\\Windows\\',
    'C:\\ProgramData\\Microsoft\\',
    '\\Device\\HarddiskVolume',  # raw device paths
)


def _parse_action(mask_hex):
    try:
        mask = int(mask_hex, 16)
    except (ValueError, TypeError):
        return 'other'
    if mask & 0x10000:
        return 'delete'
    if mask & 0x106:   # WriteData | AppendData | WriteAttributes
        return 'write'
    if mask & 0x1:     # ReadData
        return 'read'
    return 'other'


def _matches_account(username, patterns):
    u = username.lower()
    return any(fnmatch.fnmatch(u, p.lower()) for p in patterns)


def _is_noisy(username, obj_name):
    if not username or username in _SYSTEM_ACCOUNTS or username.endswith('$'):
        return True
    if obj_name:
        for prefix in _NOISY_PATH_PREFIXES:
            if obj_name.startswith(prefix):
                return True
    return False


class EventLogMonitor:
    def __init__(self, app, db):
        self.app = app
        self.db = db
        self._running = False
        self._thread = None
        self._last_poll_time = datetime.utcnow() - timedelta(seconds=60)
        self._last_cleanup = datetime.utcnow() - timedelta(days=1)  # run on first loop

    def _run_powershell(self, command):
        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command', command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode

    def get_new_events(self, since_dt):
        since_str = since_dt.strftime('%Y-%m-%d %H:%M:%S')
        cmd = (
            "$ev=Get-WinEvent -FilterHashtable @{LogName='Security';Id=4663;"
            "StartTime=([DateTime]::ParseExact('" + since_str + "',"
            "'yyyy-MM-dd HH:mm:ss',$null))} -ErrorAction SilentlyContinue;"
            "if($ev){$ev|ForEach-Object{"
            "$x=[xml]$_.ToXml();$d=$x.Event.EventData.Data;"
            "[PSCustomObject]@{"
            "TC=$_.TimeCreated.ToUniversalTime().ToString('o');"
            "UN=($d|Where-Object{$_.Name -eq 'SubjectUserName'}).'#text';"
            "DN=($d|Where-Object{$_.Name -eq 'SubjectDomainName'}).'#text';"
            "ON=($d|Where-Object{$_.Name -eq 'ObjectName'}).'#text';"
            "AM=($d|Where-Object{$_.Name -eq 'AccessMask'}).'#text';"
            "PN=($d|Where-Object{$_.Name -eq 'ProcessName'}).'#text'"
            "}}|ConvertTo-Json -Depth 3}"
        )
        output, stderr, code = self._run_powershell(cmd)
        if code != 0 and stderr:
            logger.error(f'PowerShell error (code {code}): {stderr[:500]}')
        if not output:
            return []
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return data or []
        except json.JSONDecodeError:
            logger.error(f'Failed to parse PowerShell output: {output[:200]}')
            return []

    def _poll(self):
        from db import FileAccess, AccountFilter

        since = self._last_poll_time
        now = datetime.utcnow()

        try:
            events = self.get_new_events(since)
        except Exception as e:
            logger.error(f'Error polling event log: {e}')
            return

        self._last_poll_time = now

        if not events:
            return

        with self.app.app_context():
            patterns = [f.pattern for f in AccountFilter.query.filter_by(is_active=True).all()]

            new_entries = []
            for ev in events:
                user = ev.get('UN') or ''
                obj = ev.get('ON') or ''

                if _is_noisy(user, obj):
                    continue

                domain = ev.get('DN') or ''
                username = f'{domain}\\{user}' if domain else user

                if patterns and not _matches_account(username, patterns):
                    continue

                ts_raw = (ev.get('TC') or '')[:19]  # YYYY-MM-DDTHH:MM:SS
                try:
                    ts = datetime.fromisoformat(ts_raw)
                except (ValueError, TypeError):
                    ts = now

                new_entries.append(FileAccess(
                    timestamp=ts,
                    server='local',
                    username=username,
                    file_path=obj,
                    process_name=ev.get('PN') or '',
                    action=_parse_action(ev.get('AM') or ''),
                ))

            if new_entries:
                for entry in new_entries:
                    self.db.session.add(entry)
                self.db.session.commit()
                logger.info(f'Stored {len(new_entries)} event(s)')

    def _cleanup(self):
        from db import FileAccess
        from config import Config

        days = Config.RETENTION_DAYS
        if not days:
            return
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.app.app_context():
            deleted = FileAccess.query.filter(FileAccess.timestamp < cutoff).delete()
            self.db.session.commit()
        if deleted:
            logger.info(f'Retention cleanup: {deleted} record(s) ouder dan {days} dagen verwijderd')

    def _loop(self):
        from config import Config

        interval = Config.POLL_INTERVAL

        while self._running:
            try:
                self._poll()
            except Exception as e:
                logger.error(f'Poll error: {e}')

            if (datetime.utcnow() - self._last_cleanup).total_seconds() >= 86400:
                try:
                    self._cleanup()
                except Exception as e:
                    logger.error(f'Cleanup error: {e}')
                self._last_cleanup = datetime.utcnow()

            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name='eventlog-monitor'
        )
        self._thread.start()
        logger.info('Event log monitor started')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info('Event log monitor stopped')

    def get_recent_events(self, minutes=5):
        from db import FileAccess
        since = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            {
                'timestamp': e.timestamp.strftime('%H:%M:%S'),
                'username': e.username,
                'file_path': e.file_path,
                'process_name': e.process_name,
                'action': e.action,
            }
            for e in FileAccess.query
                .filter(FileAccess.timestamp >= since)
                .order_by(FileAccess.timestamp.desc())
                .limit(100)
                .all()
        ]
