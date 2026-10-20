import hmac, os

def verify_token(request):
    """Fail-closed: tanpa MPP_DEVICE_TOKEN semua event fingerprint ditolak.
    Hanya untuk uji lokal: set MPP_ALLOW_NO_DEVICE_TOKEN=1 agar tanpa token diizinkan."""
    expected = os.getenv('MPP_DEVICE_TOKEN', '').strip()
    if not expected:
        return os.getenv('MPP_ALLOW_NO_DEVICE_TOKEN', '').strip() == '1'
    given = request.headers.get('X-Device-Token', '')
    return hmac.compare_digest(given.encode('utf-8'), expected.encode('utf-8'))

def normalize_event(body):
    body = body if isinstance(body, dict) else {}
    employee = str(body.get('employee_code') or body.get('user_id') or body.get('pin') or body.get('template_id') or '').strip()
    if not employee: raise ValueError('employee_code/user_id/pin/template_id wajib diisi')
    device = str(body.get('device_id') or body.get('serial_number') or 'FINGERPRINT-01')[:128]
    payload = {k: v for k, v in body.items() if k not in ('image', 'fingerprint_image', 'raw_template', 'template')}
    payload['integration'] = 'generic-fingerprint-webhook-v1'
    return employee, device, payload
