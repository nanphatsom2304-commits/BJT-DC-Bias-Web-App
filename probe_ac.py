import spice_engine as s
raw = {"vcc":"12","r1":"100","r1_unit":"kohm","r2":"22","r2_unit":"kohm","rc":"2.2","rc_unit":"kohm","re":"1","re_unit":"kohm","rl":"10","rl_unit":"kohm","cin":"10","cin_unit":"uf","cout":"10","cout_unit":"uf","amp_mv":"10","freq_hz":"1000"}
inputs, errors = s.parse_inputs(raw, "ac")
out = s.run_analysis(inputs, "ac")
for f, g, p in zip(out["frequency_hz"], out["gain_db"], out["phase_deg"]):
    if f in (1.0, 2.0, 10.0, 100.0, 1000.0, 1e4, 1e5, 1e6, 1e7, 1e8) or abs(f-1e7)<1:
        print(f"{f:12.1f} Hz  gain={g:7.3f} dB  phase={p:8.2f} deg")
