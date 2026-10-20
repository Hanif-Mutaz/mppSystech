import ipaddress, logging, os
from datetime import date
from flask import Flask, jsonify, request, send_from_directory
from config import load_env
load_env()
import backend
from backend import (get_state, get_version, save_state, merge_state, add_scan, scans_after, latest_scan_id,
                     report_employees, report_attendance)
from fingerprint_adapter import verify_token, normalize_event

logging.basicConfig(level=os.getenv('MPP_LOG_LEVEL', 'INFO'), format='%(asctime)s %(levelname)s %(name)s: %(message)s')
BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(BASE, 'frontend')
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
backend.init_db()

# Hanya jaringan privat/LAN yang boleh mengakses server (cegah ikut terbuka ke internet).
# Ubah lewat MPP_ALLOWED_NETS (daftar CIDR dipisah koma). Isi "*" untuk menonaktifkan (tidak disarankan).
DEFAULT_NETS = '127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,fc00::/7,fe80::/10'

def _allowed_nets():
    raw = os.getenv('MPP_ALLOWED_NETS', DEFAULT_NETS).strip()
    if raw == '*': return None
    return [ipaddress.ip_network(x.strip(), strict=False) for x in raw.split(',') if x.strip()]

@app.before_request
def guard():
    nets = _allowed_nets()
    if nets is None: return None
    try:
        ip = ipaddress.ip_address((request.remote_addr or '').split('%')[0])
        if ip.version == 6 and ip.ipv4_mapped: ip = ip.ipv4_mapped
    except ValueError:
        return jsonify(ok=False, error='forbidden'), 403
    if not any(ip in n for n in nets):
        return jsonify(ok=False, error='forbidden'), 403

@app.after_request
def headers(r):
    r.headers['Cache-Control'] = 'no-store'
    r.headers['X-Content-Type-Options'] = 'nosniff'
    return r

def _body():
    b = request.get_json(silent=True)
    return b if isinstance(b, dict) else {}

@app.get('/')
def index(): return send_from_directory(FRONTEND, 'index.html')
@app.get('/tv')
def tv(): return send_from_directory(FRONTEND, 'tv.html')
@app.get('/frontend/<path:filename>')
def frontend_asset(filename): return send_from_directory(FRONTEND, filename)

@app.get('/health')
def health():
    ok = backend.db_ok()
    return jsonify(ok=ok, service='MPP Server', port=int(os.getenv('MPP_PORT', '5000')), database='postgresql' if ok else 'unreachable'), (200 if ok else 503)

@app.get('/api/state')
def state_get(): return jsonify(ok=True, **get_state())
@app.get('/api/state/version')
def state_version(): return jsonify(ok=True, version=get_version())

@app.put('/api/state')
def state_put():
    body = _body()
    try:
        version, current = save_state(body.get('payload', {}), body.get('source', 'desktop'), body.get('expected_version'))
        if version is None: return jsonify(ok=False, error='version_conflict', current_version=current), 409
        return jsonify(ok=True, version=version)
    except ValueError as e: return jsonify(ok=False, error=str(e)), 400

@app.patch('/api/state')
def state_patch():
    body = _body()
    try:
        version, prev = merge_state(body.get('changes'), body.get('removed'), body.get('source', 'desktop'))
        return jsonify(ok=True, version=version, previous_version=prev)
    except ValueError as e: return jsonify(ok=False, error=str(e)), 400

@app.post('/api/scan')
def scan_post():
    body = _body()
    try:
        event_id = add_scan(body.get('employee_code'), body.get('scan_type', 'QR'), body.get('source', 'scanner'),
                            body.get('device_id', ''), body.get('payload'))
        return jsonify(ok=True, id=event_id), 201
    except ValueError as e: return jsonify(ok=False, error=str(e)), 400

@app.get('/api/scans')
def scan_get():
    try: return jsonify(ok=True, events=scans_after(request.args.get('after', 0), request.args.get('limit', 100)))
    except ValueError: return jsonify(ok=False, error='parameter tidak valid'), 400

@app.get('/api/scans/latest')
def scan_latest(): return jsonify(ok=True, id=latest_scan_id())

@app.post('/api/fingerprint/event')
def fingerprint_event():
    if not verify_token(request): return jsonify(ok=False, error='unauthorized'), 401
    try:
        employee, device, payload = normalize_event(_body())
        event_id = add_scan(employee, 'FINGERPRINT', 'fingerprint', device, payload)
        return jsonify(ok=True, id=event_id, employee_code=employee), 201
    except ValueError as e: return jsonify(ok=False, error=str(e)), 400

# ---- Laporan read-only dari tabel per entitas ----
@app.get('/api/report/employees')
def report_emp():
    try: return jsonify(ok=True, rows=report_employees(request.args.get('q', ''), request.args.get('limit', 500)))
    except ValueError: return jsonify(ok=False, error='parameter tidak valid'), 400

@app.get('/api/report/attendance')
def report_att():
    def d(name):
        v = request.args.get(name)
        if not v: return None
        return date.fromisoformat(v)
    try:
        rows = report_attendance(d('from'), d('to'), request.args.get('emp') or None, request.args.get('line') or None,
                                 request.args.get('limit', 1000))
        return jsonify(ok=True, rows=rows)
    except ValueError: return jsonify(ok=False, error='parameter tidak valid (tanggal: YYYY-MM-DD)'), 400

@app.get('/api/devices/status')
def devices_status():
    try:
        from runtime_devices import scanner
        serial_status = scanner.status
    except Exception:
        serial_status = {'enabled': False, 'connected': False}
    return jsonify(ok=True, usb_hid={'ready': True, 'mode': 'keyboard'}, usb_serial=serial_status,
                   fingerprint={'ready': True, 'endpoint': '/api/fingerprint/event',
                                'token_required': True, 'token_configured': bool(os.getenv('MPP_DEVICE_TOKEN'))})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
