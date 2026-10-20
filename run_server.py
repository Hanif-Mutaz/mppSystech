from config import load_env
load_env()
import os
from waitress import serve
from server import app
from runtime_devices import scanner

if __name__ == '__main__':
    scanner.start()
    try:
        serve(app, host=os.getenv('MPP_HOST', '0.0.0.0'), port=int(os.getenv('MPP_PORT', '5000')), threads=8, channel_timeout=120)
    finally:
        scanner.stop()
