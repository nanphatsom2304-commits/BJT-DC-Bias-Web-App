import spice_engine as s
raw = {"vcc":"12","r1":"100","r1_unit":"kohm","r2":"22","r2_unit":"kohm","rc":"2.2","rc_unit":"kohm","re":"2","re_unit":"kohm","rl":"10","rl_unit":"kohm","cin":"10","cin_unit":"uf","cout":"10","cout_unit":"uf","amp_mv":"10","freq_hz":"1000"}
inputs, _ = s.parse_inputs(raw, "ac")
out = s.run_analysis(inputs, "ac")
peak = max(out["gain_db"]); print("peak", peak, "at", out["frequency_hz"][out["gain_db"].index(peak)])
for f, g in list(zip(out["frequency_hz"], out["gain_db"]))[-8:]:
    print(f"{f:12.4g} {g:8.3f}")
print("first", out["frequency_hz"][0], out["gain_db"][0])
