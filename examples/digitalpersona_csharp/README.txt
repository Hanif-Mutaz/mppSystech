CONTOH ADAPTER HID DIGITALPERSONA / U.ARE.U
===========================================
Referensi SDK resmi: HID DigitalPersona SDK for Windows.
SDK resmi menyediakan sample capture, template extraction dan matching serta interface C/C++/C#/Java/.NET/JavaScript.

FLOW YANG DIPAKAI MPP:
Reader USB -> DigitalPersona SDK -> aplikasi C# vendor adapter -> employee_code terverifikasi -> POST http://127.0.0.1:5000/api/fingerprint/event

File DigitalPersonaAdapterExample.cs sengaja memakai fungsi placeholder OnVendorFingerprintMatched(employeeCode),
karena nama class/API capture dan matching harus mengikuti versi SDK resmi yang Anda instal.
Letakkan callback SDK setelah proses matching sukses lalu panggil OnVendorFingerprintMatched("NIK/EMP-ID").
Jangan kirim raw fingerprint image/template ke MPP Server.
