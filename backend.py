import json, logging, os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from projections import project, rebuild_all

log = logging.getLogger('mpp.backend')
BASE = Path(__file__).resolve().parent
ALLOWED_SOURCES = {'desktop', 'tv', 'scanner', 'fingerprint'}
MAX_BYTES = 8_000_000

_pool = None

def _dsn():
    dsn = os.getenv('MPP_DATABASE_URL', '').strip()
    if not dsn:
        raise RuntimeError('MPP_DATABASE_URL belum di-set. Contoh: postgresql://mpp:PASSWORD@127.0.0.1:5432/mpp')
    return dsn

def pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(_dsn(), min_size=1, max_size=int(os.getenv('MPP_DB_POOL', '10')),
                               kwargs={'row_factory': dict_row}, open=False, name='mpp')
        _pool.open(wait=True, timeout=15)
    return _pool

def close():
    global _pool
    if _pool is not None:
        _pool.close(); _pool = None

def connection():
    return pool().connection()

def init_db():
    sql = (BASE / 'schema.sql').read_text(encoding='utf-8')
    with connection() as con:
        con.execute('SELECT pg_advisory_xact_lock(7340211)')    # cegah race kalau dua proses start bersamaan
        con.execute(sql)

def db_ok():
    try:
        with connection() as con: con.execute('SELECT 1')
        return True
    except Exception as e:
        log.warning('db check gagal: %s', e); return False

def _lock_revision(con):
    return int(con.execute('SELECT version FROM app_revision WHERE id=1 FOR UPDATE').fetchone()['version'])

def _bump(con, current, source):
    new = current + 1
    con.execute('UPDATE app_revision SET version=%s, updated_at=now(), source=%s WHERE id=1', (new, source))
    return new

def _project(con, key, value):
    """Update tabel entitas untuk satu key. Gagal proyeksi tidak boleh menggagalkan penyimpanan."""
    try:
        with con.transaction(), con.cursor() as cur:             # savepoint
            project(cur, key, value)
    except Exception as e:
        log.warning('proyeksi %s gagal: %s', key, e)

def _check_size(con):
    total = con.execute('SELECT COALESCE(SUM(octet_length(value)),0) AS n FROM app_kv').fetchone()['n']
    if int(total) > MAX_BYTES: raise ValueError('payload terlalu besar')

def _upsert(con, key, value, source):
    r = con.execute(
        'INSERT INTO app_kv(key,value,updated_by) VALUES (%s,%s,%s) '
        'ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now(), updated_by=EXCLUDED.updated_by '
        'WHERE app_kv.value IS DISTINCT FROM EXCLUDED.value RETURNING key', (key, value, source)).fetchone()
    return r is not None

def get_state():
    with connection() as con:
        rows = con.execute('SELECT key,value FROM app_kv').fetchall()
        rev = con.execute('SELECT version,updated_at,source FROM app_revision WHERE id=1').fetchone()
    return {'version': int(rev['version']), 'payload': {r['key']: r['value'] for r in rows},
            'updated_at': rev['updated_at'].isoformat(), 'source': rev['source']}

def get_version():
    with connection() as con:
        return int(con.execute('SELECT version FROM app_revision WHERE id=1').fetchone()['version'])

def save_state(payload, source='desktop', expected_version=None):
    """Timpa seluruh state (PUT). Return (versi_baru, versi_lama) atau (None, versi_sekarang) bila konflik."""
    if not isinstance(payload, dict): raise ValueError('payload harus object JSON')
    if not payload: raise ValueError('payload kosong ditolak')   # cegah klien lama menimpa data server dengan {}
    source = source if source in ALLOWED_SOURCES else 'desktop'
    values = {str(k): v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in payload.items()}
    if any(len(v.encode('utf-8')) > MAX_BYTES for v in values.values()): raise ValueError('payload terlalu besar')
    with connection() as con, con.transaction():
        current = _lock_revision(con)
        if expected_version is not None and int(expected_version) != current:
            return None, current
        existing = {r['key'] for r in con.execute('SELECT key FROM app_kv').fetchall()}
        changed = [k for k, v in values.items() if _upsert(con, k, v, source)]
        gone = sorted(existing - set(values))
        if gone: con.execute('DELETE FROM app_kv WHERE key = ANY(%s)', (gone,))
        _check_size(con)
        if not changed and not gone: return current, current   # tidak ada perubahan nyata: jangan naikkan version
        for k in changed: _project(con, k, values[k])
        for k in gone: _project(con, k, None)
        return _bump(con, current, source), current

def merge_state(changes=None, removed=None, source='desktop'):
    """Terapkan perubahan PER KEY (bukan timpa seluruh snapshot).
    Dua perangkat yang mengubah key berbeda tidak saling menimpa.
    Return (version_baru, version_sebelumnya)."""
    changes = changes if isinstance(changes, dict) else {}
    removed = removed if isinstance(removed, list) else []
    if not changes and not removed: raise ValueError('tidak ada perubahan')
    source = source if source in ALLOWED_SOURCES else 'desktop'
    values = {str(k): v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in changes.items()}
    removed = [str(k) for k in removed if str(k) not in values]
    if any(len(v.encode('utf-8')) > MAX_BYTES for v in values.values()): raise ValueError('payload terlalu besar')
    with connection() as con, con.transaction():
        current = _lock_revision(con)
        changed = [k for k, v in values.items() if _upsert(con, k, v, source)]
        gone = [r['key'] for r in con.execute('DELETE FROM app_kv WHERE key = ANY(%s) RETURNING key', (removed,)).fetchall()] if removed else []
        _check_size(con)
        # Tidak ada perubahan nyata (nilai sama / key sudah tidak ada): JANGAN naikkan version.
        # Kalau dinaikkan, perangkat lain mengira ada data baru -> saling reload tanpa henti.
        if not changed and not gone: return current, current
        for k in changed: _project(con, k, values[k])
        for k in gone: _project(con, k, None)
        return _bump(con, current, source), current

def rebuild_projections():
    """Bangun ulang semua tabel entitas dari app_kv (dipakai setelah migrasi/restore)."""
    with connection() as con, con.transaction(), con.cursor() as cur:
        kv = {r['key']: r['value'] for r in con.execute('SELECT key,value FROM app_kv').fetchall()}
        rebuild_all(cur, kv)

def add_scan(employee_code, scan_type='QR', source='scanner', device_id='', payload=None):
    employee_code = str(employee_code or '').strip()
    if not employee_code or len(employee_code) > 128: raise ValueError('employee_code tidak valid')
    scan_type = str(scan_type or 'QR').upper()[:24]
    source = source if source in ALLOWED_SOURCES else 'scanner'
    payload = payload if isinstance(payload, dict) else {}
    with connection() as con:
        return con.execute(
            'INSERT INTO scan_events(device_id,employee_code,scan_type,source,payload) VALUES (%s,%s,%s,%s,%s) RETURNING id',
            (str(device_id or '')[:128], employee_code, scan_type, source, Jsonb(payload))).fetchone()['id']

def _scan_row(r):
    r = dict(r); r['created_at'] = r['created_at'].isoformat(); return r

def scans_after(after_id=0, limit=100):
    limit = max(1, min(int(limit), 500)); after_id = max(0, int(after_id))
    with connection() as con:
        rows = con.execute('SELECT * FROM scan_events WHERE id>%s ORDER BY id ASC LIMIT %s', (after_id, limit)).fetchall()
    return [_scan_row(r) for r in rows]

def latest_scan_id():
    with connection() as con:
        return int(con.execute('SELECT COALESCE(MAX(id),0) AS n FROM scan_events').fetchone()['n'])

# ---------- query laporan (read-only) ----------
def report_employees(q='', limit=500):
    limit = max(1, min(int(limit), 2000)); q = (q or '').strip()
    sql = 'SELECT emp_id,barcode,nama,departemen,grp,status,work_type,position,line,join_date FROM employees'
    args = []
    if q:
        like = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        sql += ' WHERE emp_id ILIKE %s OR nama ILIKE %s OR barcode ILIKE %s'
        args = [like, like, like]
    with connection() as con:
        return con.execute(sql + ' ORDER BY emp_id LIMIT %s', (*args, limit)).fetchall()

def report_attendance(date_from=None, date_to=None, emp_id=None, line=None, limit=1000):
    limit = max(1, min(int(limit), 5000))
    where, args = [], []
    if date_from: where.append('work_date >= %s'); args.append(date_from)
    if date_to:   where.append('work_date <= %s'); args.append(date_to)
    if emp_id:    where.append('emp_id = %s');     args.append(emp_id)
    if line:      where.append('line = %s');       args.append(line)
    sql = 'SELECT emp_id,name,line,shift,work_date,time_in,time_out FROM attendance'
    if where: sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY work_date DESC NULLS LAST, id DESC LIMIT %s'
    with connection() as con:
        rows = con.execute(sql, (*args, limit)).fetchall()
    for r in rows:
        if r['work_date']: r['work_date'] = r['work_date'].isoformat()
    return rows
