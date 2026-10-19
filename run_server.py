from waitress import serve
from server import app
from runtime_devices import scanner
if __name__=='__main__':
    scanner.start()
    try: serve(app,host='0.0.0.0',port=5000,threads=8,channel_timeout=120)
    finally: scanner.stop()
