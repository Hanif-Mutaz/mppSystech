"""Loader .env sederhana (tanpa dependensi). Nilai yang sudah ada di environment tidak ditimpa."""
import os
from pathlib import Path

def load_env(path=None):
    p = Path(path) if path else Path(__file__).resolve().parent / '.env'
    if not p.is_file(): return False
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, v = line.split('=', 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'': v = v[1:-1]
        os.environ.setdefault(k, v)
    return True
