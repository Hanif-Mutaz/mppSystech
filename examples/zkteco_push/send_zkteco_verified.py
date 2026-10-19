"""Contoh middleware fingerprint generik -> MPP Server.
Panggil send_verified() HANYA setelah SDK/vendor menyatakan sidik jari cocok dengan employee_code.
Tidak mengirim image/template biometrik.
"""
import json, os, urllib.request
SERVER=os.getenv('MPP_SERVER','http://127.0.0.1:5000')
TOKEN=os.getenv('MPP_DEVICE_TOKEN','')

def send_verified(employee_code, device_id='FP-01'):
    body=json.dumps({'employee_code':str(employee_code),'device_id':device_id}).encode()
    req=urllib.request.Request(SERVER+'/api/fingerprint/event',data=body,method='POST',headers={'Content-Type':'application/json','X-Device-Token':TOKEN})
    with urllib.request.urlopen(req,timeout=5) as r: return json.loads(r.read())

if __name__=='__main__': print(send_verified('22060049','FP-DEMO'))
