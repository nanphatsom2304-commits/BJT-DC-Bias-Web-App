import json, urllib.request, urllib.parse
data = {
    "sim_analysis": "ac", "sim_vcc": "12", "sim_r1": "100", "sim_r1_unit": "kohm",
    "sim_r2": "22", "sim_r2_unit": "kohm", "sim_rc": "2.2", "sim_rc_unit": "kohm",
    "sim_re": "2", "sim_re_unit": "kohm", "sim_rl": "10", "sim_rl_unit": "kohm",
    "sim_cin": "10", "sim_cin_unit": "uf", "sim_cout": "10", "sim_cout_unit": "uf",
    "sim_amp_mv": "10", "sim_freq_hz": "1000",
}
req = urllib.request.Request("http://127.0.0.1:5001/api/simulate", data=urllib.parse.urlencode(data).encode())
body = json.load(urllib.request.urlopen(req))["data"]
print("midband", body["midband"])
print("cutoff", body["cutoff"])
for f, g in list(zip(body["frequency_hz"], body["gain_db"]))[-12:]:
    print(f"{f:12.4g} {g:8.3f}")
