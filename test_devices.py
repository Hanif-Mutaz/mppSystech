import os, sys
sys.path.insert(0,os.path.dirname(__file__))
from server import app
c=app.test_client()
for path in ('/health','/api/devices/status'):
 r=c.get(path); print(path,r.status_code,r.get_json())
r=c.post('/api/fingerprint/event',json={'employee_code':'FP001','device_id':'FP-TEST','template':'DILARANG_DISIMPAN'})
print('fingerprint',r.status_code,r.get_json())
r=c.post('/api/scan',json={'employee_code':'QR001','scan_type':'QR','device_id':'USB-HID'})
print('scanner',r.status_code,r.get_json())
