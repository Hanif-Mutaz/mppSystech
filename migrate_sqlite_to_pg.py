"""Migrasi sekali jalan: data/mpp.db (SQLite lama) -> PostgreSQL.

Pemakaian:
    python migrate_sqlite_to_pg.py [--sqlite data/mpp.db] [--force]

Hentikan server dulu. SQLite tidak diubah (hanya dibaca), jadi bisa diulang.
Tanpa --force, skrip menolak jalan bila tabel tujuan sudah berisi data.
"""
import argparse, json, sqlite3, sys
from pathlib import Path
from config import load_env
load_env()
import backend
from psycopg.types.json import Jsonb

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sqlite', default=str(Path(__file__).resolve().parent / 'data' / 'mpp.db'))
    ap.add_argument('--force', action='store_true', help='hapus data tujuan lalu isi ulang dari SQLite')
    a = ap.parse_args()

    src = Path(a.sqlite)
    if not src.is_file(): sys.exit(f'File SQLite tidak ditemukan: {src}')
    lite = sqlite3.connect(f'file:{src}?mode=ro', uri=True)   # read-only
    lite.row_factory = sqlite3.Row
    row = lite.execute('SELECT payload FROM app_state WHERE id=1').fetchone()
    payload = json.loads(row['payload']) if row and row['payload'] else {}
    scans = lite.execute('SELECT * FROM scan_events ORDER BY id').fetchall()
    print(f'SQLite: {len(payload)} key state, {len(scans)} scan event')

    backend.init_db()
    with backend.connection() as con, con.transaction():
        have = con.execute('SELECT (SELECT count(*) FROM app_kv) AS kv, (SELECT count(*) FROM scan_events) AS sc').fetchone()
        if (have['kv'] or have['sc']) and not a.force:
            sys.exit(f"Tujuan tidak kosong (app_kv={have['kv']}, scan_events={have['sc']}). Pakai --force untuk menimpa.")
        if a.force:
            con.execute('TRUNCATE app_kv, scan_events RESTART IDENTITY')
        for k, v in payload.items():
            con.execute('INSERT INTO app_kv(key,value,updated_by) VALUES (%s,%s,%s)', (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False), 'desktop'))
        for r in scans:
            try: p = json.loads(r['payload'] or '{}')
            except Exception: p = {}
            con.execute('INSERT INTO scan_events(id,device_id,employee_code,scan_type,source,payload,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                        (r['id'], r['device_id'] or '', r['employee_code'], r['scan_type'], r['source'], Jsonb(p), r['created_at']))
        con.execute("SELECT setval(pg_get_serial_sequence('scan_events','id'), GREATEST((SELECT COALESCE(MAX(id),0) FROM scan_events),1))")
        con.execute('UPDATE app_revision SET version=%s, updated_at=now() WHERE id=1', (int(lite.execute('SELECT version FROM app_state WHERE id=1').fetchone()['version']) + 1,))
    backend.rebuild_projections()

    with backend.connection() as con:
        n = lambda t: con.execute(f'SELECT count(*) AS n FROM {t}').fetchone()['n']
        print(f"Selesai. app_kv={n('app_kv')} scan_events={n('scan_events')} employees={n('employees')} "
              f"lines={n('lines')} skill_matrix={n('skill_matrix')} attendance={n('attendance')} assignments={n('assignments')}")
    backend.close()

if __name__ == '__main__':
    main()
