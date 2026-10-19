using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

public static class DigitalPersonaAdapterExample
{
    static readonly HttpClient http = new HttpClient();
    const string Endpoint = "http://127.0.0.1:5000/api/fingerprint/event";

    // Hubungkan method ini ke callback MATCH SUCCESS dari DigitalPersona SDK resmi.
    public static async Task OnVendorFingerprintMatched(string employeeCode, string deviceId="DIGITALPERSONA-USB")
    {
        if (String.IsNullOrWhiteSpace(employeeCode)) return;
        string json = "{\"employee_code\":\"" + Escape(employeeCode) + "\",\"device_id\":\"" + Escape(deviceId) + "\"}";
        var req = new HttpRequestMessage(HttpMethod.Post, Endpoint);
        req.Content = new StringContent(json, Encoding.UTF8, "application/json");
        var token = Environment.GetEnvironmentVariable("MPP_DEVICE_TOKEN");
        if (!String.IsNullOrWhiteSpace(token)) req.Headers.Add("X-Device-Token", token);
        var response = await http.SendAsync(req);
        response.EnsureSuccessStatusCode();
    }
    static string Escape(string s) => s.Replace("\\", "\\\\").Replace("\"", "\\\"");
}
