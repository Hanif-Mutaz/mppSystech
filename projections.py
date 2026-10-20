"""Proyeksi key localStorage -> tabel per entitas (read model).

Sumber data utama tetap tabel app_kv (supaya frontend lama tidak perlu diubah).
Tiap kali sebuah key berubah, tabel entitas terkait dibangun ulang dalam transaksi
yang sama, sehingga selalu konsisten dengan app_kv.
"""
import json, re
from psycopg.types.json import Jsonb

_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}')

def _loads(value, default):
    if value is None: return default
    try: return json.loads(value)
    except Exception: return default

def _s(v):
    return None if v is None else str(v).strip()

def _date(v):
    m = _DATE.match(str(v or ''))
    return m.group(0) if m else None

def _rows(v):
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []

def _db(cur, value):
    data = _loads(value, {})
    data = data if isinstance(data, dict) else {}
    emp = {}
    for r in _rows(data.get('Master_Karyawan')):
        k = _s(r.get('EmpID'))
        if k: emp[k] = r                               # EmpID ganda: baris terakhir menang
    lines = {}
    for r in _rows(data.get('Master_Line')):
        k = _s(r.get('Line'))
        if k: lines[k] = r
    skills = [r for r in _rows(data.get('Skill_Matrix')) if _s(r.get('EmpID'))]

    cur.execute('DELETE FROM employees')
    cur.executemany(
        'INSERT INTO employees(emp_id,barcode,nama,departemen,grp,status,work_type,position,line,join_date,data)'
        ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
        [(k, _s(r.get('Barcode')), _s(r.get('Nama')), _s(r.get('Departemen')), _s(r.get('Group')),
          _s(r.get('Status')), _s(r.get('WorkType')), _s(r.get('Position')), _s(r.get('Line')),
          _s(r.get('Join_Date')), Jsonb(r)) for k, r in emp.items()])
    cur.execute('DELETE FROM lines')
    cur.executemany('INSERT INTO lines(line,data) VALUES (%s,%s)', [(k, Jsonb(r)) for k, r in lines.items()])
    cur.execute('DELETE FROM skill_matrix')
    cur.executemany('INSERT INTO skill_matrix(emp_id,nama,skill_line,data) VALUES (%s,%s,%s,%s)',
        [(_s(r.get('EmpID')), _s(r.get('Nama')), _s(r.get('Skill Line')), Jsonb(r)) for r in skills])

def _attendance(cur, value):
    rows = _rows(_loads(value, []))
    cur.execute('DELETE FROM attendance')
    cur.executemany(
        'INSERT INTO attendance(emp_id,name,line,shift,work_date,time_in,time_out,data) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
        [(_s(r.get('emp')), _s(r.get('name')), _s(r.get('line')), _s(r.get('shift')),
          _date(r.get('workDate') or r.get('date')), _s(r.get('in')), _s(r.get('out')), Jsonb(r)) for r in rows])

def _assign(cur, value):
    rows = _rows(_loads(value, []))
    cur.execute('DELETE FROM assignments')
    cur.executemany(
        'INSERT INTO assignments(emp_id,name,line,job,shift,work_date,data) VALUES (%s,%s,%s,%s,%s,%s,%s)',
        [(_s(r.get('emp')), _s(r.get('name')), _s(r.get('line')), _s(r.get('job')), _s(r.get('shift')),
          _date(r.get('workDate') or r.get('date')), Jsonb(r)) for r in rows])

def _users(cur, value):
    rows = _rows(_loads(value, []))
    seen = {}
    for r in rows:
        u = _s(r.get('username'))
        if u: seen[u] = r
    cur.execute('DELETE FROM app_users')
    cur.executemany('INSERT INTO app_users(username,role,fullname) VALUES (%s,%s,%s)',   # password sengaja tidak disalin
        [(u, _s(r.get('role')), _s(r.get('fullname'))) for u, r in seen.items()])

def _audit(cur, value):
    rows = _rows(_loads(value, []))
    cur.execute('DELETE FROM audit_log')
    cur.executemany('INSERT INTO audit_log(logged_at,username,role,action) VALUES (%s,%s,%s,%s)',
        [(_s(r.get('time')), _s(r.get('user')), _s(r.get('role')), _s(r.get('action'))) for r in reversed(rows)])

PROJECTIONS = {
    'mpp23db': _db,
    'mpp25attendance': _attendance,
    'mpp23assign': _assign,
    'mpp28users': _users,
    'mpp28audit': _audit,
}

def project(cur, key, value):
    """value=None artinya key dihapus. Return True bila key punya proyeksi."""
    fn = PROJECTIONS.get(key)
    if not fn: return False
    fn(cur, value)
    return True

def rebuild_all(cur, kv):
    """Bangun ulang semua tabel entitas dari dict {key: value}."""
    for key in PROJECTIONS:
        project(cur, key, kv.get(key))
