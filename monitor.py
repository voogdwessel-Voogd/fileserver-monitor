import subprocess
import json
import threading
import time
import logging

logger = logging.getLogger(__name__)


class SmbMonitor:
    def __init__(self, app, db):
        self.app = app
        self.db = db
        self._running = False
        self._thread = None
        self._open_files = {}  # {server_key: {file_id: file_info}}

    def _run_powershell(self, command, hostname=None):
        if hostname:
            full_cmd = (
                f'Invoke-Command -ComputerName {hostname} '
                f'-ScriptBlock {{ {command} }}'
            )
        else:
            full_cmd = command

        result = subprocess.run(
            ['powershell', '-NonInteractive', '-Command', full_cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip(), result.returncode

    def get_open_files(self, hostname=None):
        cmd = (
            'Get-SmbOpenFile | '
            'Select-Object FileId, ClientUserName, Path, ShareRelativePath | '
            'ConvertTo-Json -Depth 3'
        )
        output, code = self._run_powershell(cmd, hostname)

        if code != 0 or not output:
            return []

        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return data or []
        except json.JSONDecodeError:
            logger.error(f'Failed to parse PowerShell output: {output[:200]}')
            return []

    def _poll(self, server):
        from db import FileAccess

        hostname = server.hostname or None
        server_key = server.hostname or 'local'

        try:
            current_files = self.get_open_files(hostname)
        except Exception as e:
            logger.error(f'Error polling {server_key}: {e}')
            return

        current_map = {str(f.get('FileId', '')): f for f in current_files}
        prev_map = self._open_files.get(server_key, {})

        new_entries = []

        for fid, finfo in current_map.items():
            if fid not in prev_map:
                new_entries.append(FileAccess(
                    server=server_key,
                    username=finfo.get('ClientUserName', 'Unknown'),
                    file_path=finfo.get('Path', ''),
                    share_name=finfo.get('ShareRelativePath', ''),
                    action='opened',
                    file_id=fid,
                ))

        for fid, finfo in prev_map.items():
            if fid not in current_map:
                new_entries.append(FileAccess(
                    server=server_key,
                    username=finfo.get('ClientUserName', 'Unknown'),
                    file_path=finfo.get('Path', ''),
                    share_name=finfo.get('ShareRelativePath', ''),
                    action='closed',
                    file_id=fid,
                ))

        if new_entries:
            with self.app.app_context():
                for entry in new_entries:
                    self.db.session.add(entry)
                self.db.session.commit()

        self._open_files[server_key] = current_map

    def _loop(self):
        from db import ServerConfig
        from config import Config

        interval = Config.POLL_INTERVAL

        while self._running:
            with self.app.app_context():
                servers = ServerConfig.query.filter_by(is_active=True).all()

            for server in servers:
                if not self._running:
                    break
                try:
                    self._poll(server)
                except Exception as e:
                    logger.error(f'Poll error for {server.name}: {e}')

            # Sleep in 1s increments so shutdown is responsive
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name='smb-monitor'
        )
        self._thread.start()
        logger.info('SMB monitor started')

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info('SMB monitor stopped')

    def get_current_open(self, server_key='local'):
        return list(self._open_files.get(server_key, {}).values())
