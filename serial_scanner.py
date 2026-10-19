import os, threading, time
from datetime import datetime, timezone
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial=None; list_ports=None

class SerialScanner:
    def __init__(self, on_scan):
        self.on_scan=on_scan; self.stop_event=threading.Event(); self.thread=None
        self.status={'enabled':False,'connected':False,'port':None,'baudrate':None,'last_scan':None,'last_error':None,'mode':'SERIAL'}
    def candidates(self):
        explicit=os.getenv('MPP_SCANNER_PORT','').strip()
        if explicit: return [explicit]
        if not list_ports: return []
        ports=[]
        for p in list_ports.comports():
            text=f'{p.device} {p.description} {p.manufacturer or ""}'.lower()
            if any(x in text for x in ('scanner','barcode','qr','usb serial','ch340','ftdi','cp210')): ports.append(p.device)
        return ports or [p.device for p in list_ports.comports()]
    def run(self):
        self.status['enabled']=True
        if not serial:
            self.status['last_error']='pyserial belum terpasang'; return
        baud=int(os.getenv('MPP_SCANNER_BAUD','9600'))
        while not self.stop_event.is_set():
            connected=False
            for port in self.candidates():
                if self.stop_event.is_set(): break
                try:
                    with serial.Serial(port,baudrate=baud,timeout=0.5) as dev:
                        connected=True; self.status.update(connected=True,port=port,baudrate=baud,last_error=None)
                        while not self.stop_event.is_set():
                            raw=dev.readline()
                            if not raw: continue
                            code=raw.decode(os.getenv('MPP_SCANNER_ENCODING','utf-8'),errors='ignore').strip()
                            if code:
                                self.on_scan(code,'QR','usb-serial',port,{'transport':'serial'})
                                self.status['last_scan']=datetime.now(timezone.utc).isoformat()
                except Exception as e:
                    self.status.update(connected=False,last_error=str(e))
            if not connected: time.sleep(3)
        self.status['connected']=False
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.thread=threading.Thread(target=self.run,name='usb-serial-scanner',daemon=True); self.thread.start()
    def stop(self): self.stop_event.set()
