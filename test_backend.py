"""Tes backend + API terhadap PostgreSQL.

Pakai database KHUSUS TES (nama harus berakhiran _test); semua tabel dikosongkan di awal.
    set MPP_TEST_DATABASE_URL=postgresql://mpp:PASSWORD@127.0.0.1:5432/mpp_test
    python test_backend.py
"""
import json, os, sqlite3, subprocess, sys, tempfile
from urllib.parse import urlparse

url = os.getenv('MPP_TEST_DATABASE_URL', '').strip()
if not url or not urlparse(url).path.rstrip('/').endswith('_test'):
    sys.exit('Set MPP_TEST_DATABASE_URL ke database dengan nama berakhiran _test (jangan pakai database produksi).')
os.environ['MPP_DATABASE_URL'] = url
os.environ['MPP_DEVICE_TOKEN'] = 'tok-123'
os.environ.pop('MPP_ALLOWED_NETS', None)
os.environ['MPP_LOG_LEVEL'] = 'WARNING'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backend
from server import app

backend.init_db()
with backend.connection() as con:
    con.execute('TRUNCATE app_kv, scan_events, employees, lines, skill_matrix, attendance, assignments, app_users, audit_log RESTART IDENTITY')
    con.execute('UPDATE app_revision SET version=0')

c = app.test_client()
ok_count = 0
def check(name, cond, extra=''):
    global ok_count
    if not cond:
        backend.close(); sys.exit(f'GAGAL: {name} {extra}')
    ok_count += 1; print('ok  ', name)

# --- state ---
check('state awal kosong', c.get('/api/state').get_json()['payload'] == {})
check('PUT kosong ditolak', c.put('/api/state', json={'payload': {}}).status_code == 400)
db = {'Master_Karyawan': [{'EmpID': 'EMP001', 'Barcode': '123', 'Nama': 'Andi', 'Departemen': 'PRODUKSI', 'Group': 'A', 'Status': 'Tetap'},
                          {'EmpID': 'EMP002', 'Barcode': '456', 'Nama': 'Siti', 'Departemen': 'PRODUKSI'}],
      'Master_Line': [{'Line': '41SY01', 'Total': 6}],
      'Skill_Matrix': [{'EmpID': 'EMP001', 'Nama': 'Andi', 'Skill Line': '41SY01'}]}
r = c.patch('/api/state', json={'changes': {'mpp23db': json.dumps(db), 'mpp28users': json.dumps([{'username': 'admin', 'password': 'RAHASIA', 'role': 'ADMIN', 'fullname': 'Admin'}])}, 'source': 'desktop'}).get_json()
check('PATCH versi 1', r['ok'] and r['version'] == 1 and r['previous_version'] == 0, r)
st = c.get('/api/state').get_json()
check('GET state mengembalikan string asli', st['payload']['mpp23db'] == json.dumps(db) and st['version'] == 1)

# --- tabel entitas ---
with backend.connection() as con:
    q = lambda s, *a: con.execute(s, a).fetchall()
    check('employees terisi', [r['emp_id'] for r in q('SELECT emp_id FROM employees ORDER BY emp_id')] == ['EMP001', 'EMP002'])
    check('lines + skill terisi', q('SELECT count(*) AS n FROM lines')[0]['n'] == 1 and q('SELECT count(*) AS n FROM skill_matrix')[0]['n'] == 1)
    check('app_users TANPA password', q('SELECT * FROM app_users')[0].keys().isdisjoint({'password'}) and q('SELECT username FROM app_users')[0]['username'] == 'admin')

att = [{'emp': 'EMP001', 'name': 'Andi', 'date': '2026-10-19', 'workDate': '2026-10-19', 'shift': 'SHIFT 1', 'line': '41SY01', 'in': '08:01:00', 'out': ''},
       {'emp': 'EMP002', 'name': 'Siti', 'date': '2026-10-18', 'workDate': '2026-10-18', 'shift': 'SHIFT 2', 'line': '41SY02', 'in': '20:00:00', 'out': '08:00:00'}]
c.patch('/api/state', json={'changes': {'mpp25attendance': json.dumps(att), 'mpp23assign': json.dumps([{'emp': 'EMP001', 'line': '41SY01', 'job': 'Inspector', 'shift': 'SHIFT 1', 'workDate': '2026-10-19'}]),
                                          'mpp28audit': json.dumps([{'time': '19/10/2026 08.00', 'user': 'admin', 'role': 'ADMIN', 'action': 'LOGIN'}])}})
rows = c.get('/api/report/attendance?from=2026-10-19&to=2026-10-19').get_json()['rows']
check('laporan absensi per tanggal', len(rows) == 1 and rows[0]['emp_id'] == 'EMP001' and rows[0]['work_date'] == '2026-10-19', rows)
check('laporan absensi per line', len(c.get('/api/report/attendance?line=41SY02').get_json()['rows']) == 1)
check('tanggal salah -> 400', c.get('/api/report/attendance?from=bukan-tanggal').status_code == 400)
check('cari karyawan', [r['emp_id'] for r in c.get('/api/report/employees?q=sit').get_json()['rows']] == ['EMP002'])
check('wildcard % tidak jadi match-all', c.get('/api/report/employees?q=%25').get_json()['rows'] == [])
with backend.connection() as con:
    check('audit & assignments terisi', con.execute('SELECT count(*) AS n FROM audit_log').fetchone()['n'] == 1 and con.execute('SELECT count(*) AS n FROM assignments').fetchone()['n'] == 1)

# tidak ada perubahan nyata -> versi TIDAK boleh naik (mencegah reload bolak-balik antar perangkat)
v_now = c.get('/api/state/version').get_json()['version']
r = c.patch('/api/state', json={'changes': {'mpp28audit': json.dumps([{'time': '19/10/2026 08.00', 'user': 'admin', 'role': 'ADMIN', 'action': 'LOGIN'}])}}).get_json()
check('PATCH nilai sama: versi tidak naik', r['ok'] and r['version'] == v_now and r['previous_version'] == v_now, r)
r = c.patch('/api/state', json={'removed': ['key-yang-tidak-ada']}).get_json()
check('hapus key yang tidak ada: versi tidak naik', r['ok'] and r['version'] == v_now, r)
check('versi di server tetap', c.get('/api/state/version').get_json()['version'] == v_now)
r = c.patch('/api/state', json={'changes': {'mpp28audit': json.dumps([{'time': 'x', 'user': 'u', 'role': 'r', 'action': 'BARU'}])}}).get_json()
check('PATCH nilai beda: versi naik 1', r['version'] == v_now + 1, r)
c.patch('/api/state', json={'changes': {'mpp28audit': json.dumps([{'time': '19/10/2026 08.00', 'user': 'admin', 'role': 'ADMIN', 'action': 'LOGIN'}])}})

# hapus key -> tabel ikut kosong
c.patch('/api/state', json={'removed': ['mpp25attendance']})
check('hapus key mengosongkan attendance', c.get('/api/report/attendance').get_json()['rows'] == [])

# key rusak tidak menggagalkan simpan
r = c.patch('/api/state', json={'changes': {'mpp25attendance': 'bukan json{'}}).get_json()
check('JSON rusak tetap tersimpan', r['ok'])

# PUT + konflik versi
v = c.get('/api/state/version').get_json()['version']
check('PUT konflik 409', c.put('/api/state', json={'payload': {'mppX': '1'}, 'expected_version': v - 1}).status_code == 409)
check('PUT ok', c.put('/api/state', json={'payload': {'mppX': '1'}, 'expected_version': v}).get_json()['version'] == v + 1)
check('PUT menghapus key lain', list(c.get('/api/state').get_json()['payload']) == ['mppX'])
with backend.connection() as con:
    check('PUT mengosongkan employees', con.execute('SELECT count(*) AS n FROM employees').fetchone()['n'] == 0)
check('body bukan object -> 400', c.patch('/api/state', data='[1,2]', content_type='application/json').status_code == 400)

# --- scan ---
check('scan masuk', c.post('/api/scan', json={'employee_code': 'EMP001', 'device_id': 'USB-HID'}).status_code == 201)
check('scan kosong ditolak', c.post('/api/scan', json={'employee_code': ' '}).status_code == 400)
ev = c.get('/api/scans?after=0').get_json()['events']
check('scan terbaca', len(ev) == 1 and ev[0]['employee_code'] == 'EMP001' and 'T' in ev[0]['created_at'])
check('scans/latest', c.get('/api/scans/latest').get_json()['id'] == ev[0]['id'])
check('after bukan angka -> 400', c.get('/api/scans?after=abc').status_code == 400)

# --- fingerprint: fail-closed + token ---
fp = {'employee_code': 'FP001', 'template': 'JANGAN_DISIMPAN', 'device_id': 'FP-1'}
check('fingerprint tanpa token 401', c.post('/api/fingerprint/event', json=fp).status_code == 401)
check('fingerprint token salah 401', c.post('/api/fingerprint/event', json=fp, headers={'X-Device-Token': 'salah'}).status_code == 401)
r = c.post('/api/fingerprint/event', json=fp, headers={'X-Device-Token': 'tok-123'})
check('fingerprint token benar 201', r.status_code == 201)
with backend.connection() as con:
    p = con.execute("SELECT payload FROM scan_events WHERE source='fingerprint'").fetchone()['payload']
check('template tidak disimpan', 'template' not in p)
os.environ.pop('MPP_DEVICE_TOKEN')
check('tanpa MPP_DEVICE_TOKEN ditolak (fail-closed)', c.post('/api/fingerprint/event', json=fp).status_code == 401)
os.environ['MPP_DEVICE_TOKEN'] = 'tok-123'

# --- allowlist jaringan ---
check('localhost diizinkan', c.get('/health', environ_overrides={'REMOTE_ADDR': '127.0.0.1'}).status_code == 200)
check('IP LAN diizinkan', c.get('/health', environ_overrides={'REMOTE_ADDR': '192.168.147.74'}).status_code == 200)
check('IP publik ditolak 403', c.get('/api/state', environ_overrides={'REMOTE_ADDR': '8.8.8.8'}).status_code == 403)
check('IPv4-mapped IPv6 publik ditolak', c.get('/api/state', environ_overrides={'REMOTE_ADDR': '::ffff:8.8.8.8'}).status_code == 403)
os.environ['MPP_ALLOWED_NETS'] = '10.1.0.0/16'
check('MPP_ALLOWED_NETS dihormati', c.get('/health', environ_overrides={'REMOTE_ADDR': '192.168.1.5'}).status_code == 403)
os.environ.pop('MPP_ALLOWED_NETS')

# --- migrasi dari SQLite ---
tmp = tempfile.mkdtemp(); sq = os.path.join(tmp, 'mpp.db')
lite = sqlite3.connect(sq)
lite.executescript('''CREATE TABLE app_state(id INTEGER PRIMARY KEY, version INTEGER, payload TEXT, updated_at TEXT, source TEXT);
CREATE TABLE scan_events(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, employee_code TEXT, scan_type TEXT, source TEXT, payload TEXT, created_at TEXT);''')
lite.execute('INSERT INTO app_state VALUES (1,7,?,?,?)', (json.dumps({'mpp23db': json.dumps(db)}), '2026-10-01T00:00:00+00:00', 'desktop'))
lite.execute("INSERT INTO scan_events(device_id,employee_code,scan_type,source,payload,created_at) VALUES ('D','EMP009','QR','scanner','{}','2026-10-01T01:02:03+00:00')")
lite.commit(); lite.close()
env = dict(os.environ)
r = subprocess.run([sys.executable, 'migrate_sqlite_to_pg.py', '--sqlite', sq], env=env, capture_output=True, text=True)
check('migrasi menolak tujuan tidak kosong', r.returncode != 0 and 'tidak kosong' in (r.stdout + r.stderr), r.stdout + r.stderr)
r = subprocess.run([sys.executable, 'migrate_sqlite_to_pg.py', '--sqlite', sq, '--force'], env=env, capture_output=True, text=True)
check('migrasi --force berhasil', r.returncode == 0 and 'employees=2' in r.stdout and 'scan_events=1' in r.stdout, r.stdout + r.stderr)
st = c.get('/api/state').get_json()
check('migrasi: state & versi', st['version'] == 8 and json.loads(st['payload']['mpp23db'])['Master_Line'][0]['Line'] == '41SY01', st['version'])
check('migrasi: scan lama + created_at asli', c.get('/api/scans?after=0').get_json()['events'][0]['created_at'].startswith('2026-10-01T01:02:03'))
check('scan baru lanjut dari id berikutnya', c.post('/api/scan', json={'employee_code': 'N1'}).get_json()['id'] == 2)

# --- konkurensi: tidak ada update yang hilang ---
import threading
def worker(i):
    cl = app.test_client()
    for j in range(10): cl.patch('/api/state', json={'changes': {f'mppK{i}_{j}': 'x'}})
ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
v0 = c.get('/api/state/version').get_json()['version']
[t.start() for t in ts]; [t.join() for t in ts]
check('80 PATCH paralel: versi naik tepat 80 & semua key ada', c.get('/api/state/version').get_json()['version'] == v0 + 80 and sum(k.startswith('mppK') for k in c.get('/api/state').get_json()['payload']) == 80)

backend.close()
print(f'\nSEMUA {ok_count} PENGECEKAN LULUS')
