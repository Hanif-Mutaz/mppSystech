import os
from flask import Flask, jsonify, request, send_from_directory
from backend import get_state, get_version, save_state, merge_state, add_scan, scans_after
from fingerprint_adapter import verify_token, normalize_event

BASE=os.path.dirname(os.path.abspath(__file__))
FRONTEND=os.path.join(BASE,'frontend')
app=Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH']=10*1024*1024

@app.after_request
def headers(r):
    r.headers['Cache-Control']='no-store'
    r.headers['X-Content-Type-Options']='nosniff'
    return r

@app.get('/')
def index(): return send_from_directory(FRONTEND,'index.html')
@app.get('/tv')
def tv(): return send_from_directory(FRONTEND,'tv.html')
@app.get('/frontend/<path:filename>')
def frontend_asset(filename): return send_from_directory(FRONTEND,filename)
@app.get('/health')
def health(): return jsonify(ok=True,service='MPP Server',port=5000)
@app.get('/api/state')
def state_get(): return jsonify(ok=True, **get_state())
@app.get('/api/state/version')
def state_version(): return jsonify(ok=True, version=get_version())
@app.put('/api/state')
def state_put():
    body=request.get_json(silent=True) or {}
    try:
        version,current=save_state(body.get('payload',{}),body.get('source','desktop'),body.get('expected_version'))
        if version is None: return jsonify(ok=False,error='version_conflict',current_version=current),409
        return jsonify(ok=True,version=version)
    except ValueError as e: return jsonify(ok=False,error=str(e)),400
@app.patch('/api/state')
def state_patch():
    body=request.get_json(silent=True) or {}
    try:
        version,prev=merge_state(body.get('changes'),body.get('removed'),body.get('source','desktop'))
        return jsonify(ok=True,version=version,previous_version=prev)
    except ValueError as e: return jsonify(ok=False,error=str(e)),400
@app.post('/api/scan')
def scan_post():
    body=request.get_json(silent=True) or {}
    try:
        event_id=add_scan(body.get('employee_code'),body.get('scan_type','QR'),body.get('source','scanner'),body.get('device_id',''),body.get('payload'))
        return jsonify(ok=True,id=event_id),201
    except ValueError as e: return jsonify(ok=False,error=str(e)),400
@app.get('/api/scans')
def scan_get(): return jsonify(ok=True,events=scans_after(request.args.get('after',0),request.args.get('limit',100)))

@app.post('/api/fingerprint/event')
def fingerprint_event():
    if not verify_token(request): return jsonify(ok=False,error='unauthorized'),401
    try:
        employee,device,payload=normalize_event(request.get_json(silent=True) or {})
        event_id=add_scan(employee,'FINGERPRINT','fingerprint',device,payload)
        return jsonify(ok=True,id=event_id,employee_code=employee),201
    except ValueError as e: return jsonify(ok=False,error=str(e)),400

@app.get('/api/devices/status')
def devices_status():
    try:
        from runtime_devices import scanner
        serial_status=scanner.status
    except Exception:
        serial_status={'enabled':False,'connected':False}
    return jsonify(ok=True,usb_hid={'ready':True,'mode':'keyboard'},usb_serial=serial_status,
                   fingerprint={'ready':True,'endpoint':'/api/fingerprint/event','token_required':bool(os.getenv('MPP_DEVICE_TOKEN'))})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=False,threaded=True)
