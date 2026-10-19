CONTOH ADAPTER ZKTECO PUSH/ADMS
===============================
ZKTeco menyediakan PUSH SDK. Pada model/firmware yang mendukung Push/ADMS, arahkan integrasi vendor ke middleware yang membaca attendance/punch.
Setelah middleware memperoleh user/PIN yang telah diverifikasi perangkat, teruskan ID tersebut ke MPP:
POST http://127.0.0.1:5000/api/fingerprint/event
JSON: {"employee_code":"22060049","device_id":"ZK-01"}
Header: X-Device-Token sesuai MPP_DEVICE_TOKEN.

send_zkteco_verified.py menunjukkan bagian pengiriman ke MPP, bukan implementasi proprietary Push protocol.
