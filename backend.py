import json, os, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('MPP_DB_PATH', BASE / 'data' / 'mpp.db'))
LOCK = threading.RLock()
ALLOWED_SOURCES = {'desktop', 'tv', 'scanner', 'fingerprint'}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    return con

def init_db():
    with LOCK, connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS app_state (
          id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL DEFAULT 0,
          payload TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'desktop');
        CREATE TABLE IF NOT EXISTS scan_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, employee_code TEXT NOT NULL,
          scan_type TEXT NOT NULL DEFAULT 'QR', source TEXT NOT NULL DEFAULT 'scanner',
          payload TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
        INSERT OR IGNORE INTO app_state(id,version,payload,updated_at,source)
          VALUES(1,0,'{}',datetime('now'),'desktop');
        ''')

def get_state():
    with connect() as con:
        row = con.execute('SELECT version,payload,updated_at,source FROM app_state WHERE id=1').fetchone()
    try: payload = json.loads(row['payload'])
    except Exception: payload = {}
    return {'version': row['version'], 'payload': payload, 'updated_at': row['updated_at'], 'source': row['source']}

def get_version():
    with connect() as con:
        row = con.execute('SELECT version FROM app_state WHERE id=1').fetchone()
    return int(row['version'])

def save_state(payload, source='desktop', expected_version=None):
    if not isinstance(payload, dict): raise ValueError('payload harus object JSON')
    # Tolak payload kosong: mencegah klien/format lama menimpa data server dengan {}
    if not payload: raise ValueError('payload kosong ditolak')
    source = source if source in ALLOWED_SOURCES else 'desktop'
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) > 8_000_000: raise ValueError('payload terlalu besar')
    with LOCK, connect() as con:
        row = con.execute('SELECT version FROM app_state WHERE id=1').fetchone()
        current = int(row['version'])
        if expected_version is not None and int(expected_version) != current:
            return None, current
        new_version = current + 1
        con.execute('UPDATE app_state SET version=?,payload=?,updated_at=?,source=? WHERE id=1',
                    (new_version, raw, utc_now(), source))
    return new_version, current

def merge_state(changes=None, removed=None, source='desktop'):
    """Terapkan perubahan PER KEY (bukan timpa seluruh snapshot).
    Dua perangkat yang mengubah key berbeda tidak saling menimpa.
    Return (version_baru, version_sebelumnya)."""
    changes = changes if isinstance(changes, dict) else {}
    removed = removed if isinstance(removed, list) else []
    if not changes and not removed: raise ValueError('tidak ada perubahan')
    source = source if source in ALLOWED_SOURCES else 'desktop'
    with LOCK, connect() as con:
        row = con.execute('SELECT version,payload FROM app_state WHERE id=1').fetchone()
        current = int(row['version'])
        try: payload = json.loads(row['payload'])
        except Exception: payload = {}
        if not isinstance(payload, dict): payload = {}
        for k, v in changes.items(): payload[str(k)] = v if isinstance(v, str) else json.dumps(v)
        for k in removed: payload.pop(str(k), None)
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        if len(raw.encode('utf-8')) > 8_000_000: raise ValueError('payload terlalu besar')
        new_version = current + 1
        con.execute('UPDATE app_state SET version=?,payload=?,updated_at=?,source=? WHERE id=1',
                    (new_version, raw, utc_now(), source))
    return new_version, current

def add_scan(employee_code, scan_type='QR', source='scanner', device_id='', payload=None):
    employee_code = str(employee_code or '').strip()
    if not employee_code or len(employee_code) > 128: raise ValueError('employee_code tidak valid')
    scan_type = str(scan_type or 'QR').upper()[:24]
    source = source if source in ALLOWED_SOURCES else 'scanner'
    with LOCK, connect() as con:
        cur = con.execute('INSERT INTO scan_events(device_id,employee_code,scan_type,source,payload,created_at) VALUES(?,?,?,?,?,?)',
          (str(device_id)[:128], employee_code, scan_type, source, json.dumps(payload or {}, ensure_ascii=False), utc_now()))
        event_id = cur.lastrowid
    return event_id

def scans_after(after_id=0, limit=100):
    limit=max(1,min(int(limit),500)); after_id=max(0,int(after_id))
    with connect() as con:
        rows=con.execute('SELECT * FROM scan_events WHERE id>? ORDER BY id ASC LIMIT?',(after_id,limit)).fetchall()
    return [dict(r) | {'payload': json.loads(r['payload'] or '{}')} for r in rows]

init_db()
