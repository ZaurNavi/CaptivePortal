#!/usr/bin/python3
"""Captiv-Prod production diagnostic snapshot: bounded, aggregated and read-only.

Runs as root by a strict sudoers single-command rule. Never prints environment
values (except validated database paths), raw journald messages, rows, MACs,
IP addresses, credentials, tokens, private keys, or visitor payloads.
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

UNITS = (
    'captive-portal.service', 'fingerprint-sensor.service',
    'fingerprint-suricata.service', 'fingerprint-evidence.service',
    'tpeap.service', 'captiv-net01-watchdog.service',
    'captiv-net01-firewall.service', 'captiv-omada-guard.service',
    'captiv-backup.timer', 'captiv-npm-backup-online.timer',
    'captiv-omada-native-mirror.timer',
    'captiv-backup.service', 'captiv-npm-backup-online.service',
    'captiv-omada-native-mirror.service',
)
LOG_UNITS = (
    'captive-portal.service', 'fingerprint-sensor.service',
    'fingerprint-suricata.service', 'fingerprint-evidence.service',
    'tpeap.service',
)
ALLOWED_PATH_ROOTS = ('/opt/', '/var/lib/', '/srv/', '/data/', '/var/opt/')
STORAGE_ROOTS = (
    '/opt/CaptivePortal/data',
    '/opt/captivprod-portal-v2fix/data',
    '/opt/captivprod-sensor-src/data',
    '/opt/captivprod-evidence-src/data',
    '/var/lib/captivprod-evidence', '/var/lib/captivprod-sensor',
    '/var/lib/captivprod-portal', '/var/lib/captive-portal',
    '/srv/captivprod', '/srv/captive-portal',
)
DB_SUFFIXES = ('.db', '.sqlite', '.sqlite3', '.db3')
QUEUE_NAMES = re.compile(r'queue|pending|outbox|retry|spool|ack|event|receipt|source|visit|checkpoint|job', re.I)
FLAGS = ('_ENABLED', '_INTERVAL_SECONDS', '_SCAN_INTERVAL_SECONDS')
FILE_KEYS = ('_DB_PATH', '_DATABASE_PATH', '_SQLITE_PATH', '_SPOOL_DIR', '_QUEUE_DIR')
MAX_FILES = 1000
MAX_DBS = 60
MAX_TABLES = 60
MAX_QUEUE_TABLES = 12
MAX_ROWS_CHECK = 1001


def run(*args, timeout=10):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.stdout if p.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def as_json(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def iso(timestamp=None):
    try:
        return dt.datetime.fromtimestamp(timestamp or time.time(), dt.timezone.utc).isoformat(timespec='seconds')
    except (ValueError, OverflowError):
        return None


def service_snapshots():
    result = {}
    names = ('ActiveState', 'SubState', 'Result', 'MainPID', 'NRestarts',
             'ExecMainStartTimestamp', 'ActiveEnterTimestamp', 'MemoryCurrent')
    for unit in UNITS:
        raw = run('systemctl', 'show', unit, '--no-pager', *sum((['-p', k] for k in names), []))
        values = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
        result[unit] = {k: values.get(k) for k in names}
    return result


def allowed_path(value):
    if not value or '\x00' in value or '\n' in value or '\r' in value or len(value) > 4096:
        return None
    p = os.path.normpath(value.strip().strip('"').strip("'"))
    if not os.path.isabs(p) or not p.startswith(ALLOWED_PATH_ROOTS):
        return None
    return p


def configured_paths(services):
    paths = set()
    flags = {}
    for unit in ('captive-portal.service', 'fingerprint-evidence.service', 'fingerprint-sensor.service'):
        try:
            pid = int(services.get(unit, {}).get('MainPID', 0) or 0)
            if not pid:
                continue
            # Read only. Never serialize arbitrary environment values.
            entries = Path('/proc') .joinpath(str(pid), 'environ').read_bytes().split(b'\x00')
            for item in entries:
                if b'=' not in item:
                    continue
                k, v = item.split(b'=', 1)
                key = k.decode('ascii', 'ignore')
                if not re.fullmatch(r'[A-Z][A-Z0-9_]{2,90}', key):
                    continue
                if key.endswith(FILE_KEYS):
                    path = allowed_path(v.decode('utf-8', 'replace'))
                    if path:
                        paths.add(path)
                elif key.endswith(FLAGS):
                    val = v.decode('utf-8', 'replace')
                    if re.fullmatch(r'(?:true|false|0|1|[0-9]{1,8})', val, re.I):
                        flags.setdefault(unit, {})[key] = val
        except (ValueError, OSError):
            continue
    return paths, flags


def discover_files(roots, expected_paths):
    found = set()
    spool_dirs = []
    for path in expected_paths:
        if path.endswith(DB_SUFFIXES) and os.path.isfile(path):
            found.add(path)
    examined = 0
    for root in roots:
        if not os.path.isdir(root) or os.path.islink(root):
            continue
        for folder, directories, files in os.walk(root, followlinks=False):
            depth = os.path.relpath(folder, root).count(os.sep)
            if depth >= 4:
                directories[:] = []
            else:
                directories[:] = [name for name in directories if not os.path.islink(os.path.join(folder, name))
                                  and name not in ('.git', 'node_modules', 'venv', '__pycache__')]
            if QUEUE_NAMES.search(os.path.basename(folder)) and len(spool_dirs) < 32:
                spool_dirs.append(folder)
            for name in files:
                examined += 1
                if examined > MAX_FILES:
                    break
                if name.endswith(DB_SUFFIXES):
                    path = os.path.join(folder, name)
                    if not os.path.islink(path):
                        found.add(path)
            if examined > MAX_FILES:
                break
        if examined > MAX_FILES:
            break
    return sorted(found)[:MAX_DBS], spool_dirs


def db_report(path):
    out = {'path': path}
    try:
        info = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            return {'path': path, 'error': 'not_regular_file'}
        out.update(bytes=info.st_size, mtime_utc=iso(info.st_mtime))
        wal = path + '-wal'
        if os.path.isfile(wal) and not os.path.islink(wal):
            w = os.stat(wal)
            out['wal'] = {'bytes': w.st_size, 'mtime_utc': iso(w.st_mtime)}
        # sqlite read-only URI: no INSERT/UPDATE/DELETE, no checkpoint.
        uri = Path(path).as_uri() + '?mode=ro'
        conn = sqlite3.connect(uri, uri=True, timeout=0.2)
        try:
            conn.execute('PRAGMA query_only=ON')
            conn.execute('PRAGMA busy_timeout=200')
            out['page_count'] = conn.execute('PRAGMA page_count').fetchone()[0]
            out['freelist_count'] = conn.execute('PRAGMA freelist_count').fetchone()[0]
            out['journal_mode'] = conn.execute('PRAGMA journal_mode').fetchone()[0]
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT ?", (MAX_TABLES,))]
            out['tables'] = tables
            candidate = [s for s in tables if QUEUE_NAMES.search(s)][:MAX_QUEUE_TABLES]
            queue = {}
            for name in candidate:
                sql_name = '"' + name.replace('"', '""') + '"'
                try:
                    # Bounded inspection of up to 1001 rows; not a backlog semantic assertion.
                    n = conn.execute('SELECT COUNT(*) FROM (SELECT 1 FROM ' + sql_name + ' LIMIT ' + str(MAX_ROWS_CHECK) + ')').fetchone()[0]
                    queue[name] = {'rows_at_least': n if n >= MAX_ROWS_CHECK else None,
                                   'rows_if_below_limit': n if n < MAX_ROWS_CHECK else None}
                except sqlite3.Error:
                    queue[name] = {'error': 'query_unavailable'}
            out['candidate_tables_bounded_counts'] = queue
            out['note'] = 'Rows in a queue-named table do NOT prove backlog; semantics require code review.'
        finally:
            conn.close()
    except (OSError, sqlite3.Error) as e:
        out['error'] = type(e).__name__
    return out


def spool_metadata(path):
    try:
        items = []
        for idx, entry in enumerate(os.scandir(path)):
            if idx >= 3000:
                break
            if entry.is_file(follow_symlinks=False):
                st = entry.stat(follow_symlinks=False)
                items.append(st.st_mtime)
        return {'path': path, 'sampled_file_count': len(items),
                'oldest_file_mtime_utc': iso(min(items)) if items else None,
                'count_capped_at': 3000}
    except OSError:
        return {'path': path, 'status': 'not_readable'}


def logs(unit):
    raw = run('journalctl', '-u', unit, '--since', '2 hours ago', '-n', '12000',
              '-o', 'json', '--no-pager', timeout=12)
    levels = collections.Counter()
    http = collections.Counter()
    errors = collections.Counter()
    last_seen = None
    for line in raw.splitlines():
        try:
            item = json.loads(line)
        except (ValueError, TypeError):
            continue
        levels[str(item.get('PRIORITY', '?'))] += 1
        msg = str(item.get('MESSAGE', ''))
        try:
            ts = int(item.get('__REALTIME_TIMESTAMP', '0')) / 1000000
            last_seen = max(ts, last_seen or 0)
        except (TypeError, ValueError):
            pass
        m = re.search(r'\b(?:GET|POST|PUT|PATCH|DELETE|OPTIONS)\s+/\S+\s+HTTP/\d(?:\.\d)?[\" ]+([1-5]\d\d)\b', msg)
        if m:
            http[m.group(1)] += 1
        for kind, pat in (
            ('exception', r'\b(?:Traceback|Exception|fatal|failed)\b'),
            ('timeout', r'\b(?:timeout|timed out)\b'),
            ('database_locked', r'\b(?:database is locked|SQLITE_BUSY)\b'),
            ('retry', r'\b(?:retry|reconnect)\b'),
            ('queue', r'\b(?:backlog|pending|spool|queue)\b'),
            ('drop_or_gap', r'\b(?:overflow|dropped|discarded|source_gap)\b'),
        ):
            if re.search(pat, msg, re.I):
                errors[kind] += 1
    return {'service': unit, 'time_window': 'last_2h', 'log_lines': sum(levels.values()),
            'priority_counts': dict(levels), 'http_status_counts': dict(http),
            'keyword_counts': dict(errors), 'last_line_utc': iso(last_seen) if last_seen else None,
            'raw_messages_included': False}


def main():
    if len(sys.argv) != 1:
        print('This tool accepts no arguments.', file=sys.stderr)
        return 2
    os.umask(0o077)
    result = {'version': 'CAPTIVPROD-AUDIT-RO-01-v0.1', 'timestamp_utc': iso(),
              'mode': 'read-only, aggregate/metadata only, no secrets/visitor records',
              'host': os.uname().nodename}
    services = service_snapshots()
    result['services'] = services
    paths, flags = configured_paths(services)
    result['safe_effective_flags'] = flags
    additional_roots = sorted(set(os.path.dirname(p) for p in paths if p.endswith(DB_SUFFIXES)))
    roots = list(STORAGE_ROOTS) + additional_roots
    dbs, spooldirs = discover_files(roots, paths)
    result['sqlite'] = [db_report(p) for p in dbs]
    result['queue_like_directories'] = [spool_metadata(p) for p in spooldirs[:20]]
    result['journals'] = [logs(s) for s in LOG_UNITS]
    try:
        result['load_average'] = list(os.getloadavg())
        mem = Path('/proc/meminfo').read_text().splitlines()
        result['memory_kib'] = {k: int(v.strip().split()[0]) for k, v in (x.split(':', 1) for x in mem)
                                if k in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree')}
        result['root_statvfs'] = {'blocks_total': os.statvfs('/').f_blocks,
                                  'blocks_available': os.statvfs('/').f_bavail,
                                  'block_size': os.statvfs('/').f_frsize}
    except (OSError, ValueError):
        result['resource_status'] = 'unavailable'
    result['limitations'] = [
        'No unbounded SQL scans; queue counts are bounded and not inferred as pending.',
        'Read-only SQLite connections may use existing WAL shared-memory metadata; no checkpoint is requested.',
        'No Omada API authorization, guest E2E, or proof of durable downstream ACK.',
        'Historical snapshots must be compared to establish actual throughput and oldest-work age.',
    ]
    as_json(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
