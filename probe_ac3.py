import spice_engine as s
raw = {"vcc":"12","r1":"100","r1_unit":"kohm","r2":"22","r2_unit":"kohm","rc":"2.2","rc_unit":"kohm","re":"1","re_unit":"kohm","rl":"10","rl_unit":"kohm","cin":"10","cin_unit":"uf","cout":"10","cout_unit":"uf","amp_mv":"10","freq_hz":"1000"}
for re in ("1","2"):
    inputs, _ = s.parse_inputs(dict(raw, re=re), "ac")
    out = s.run_analysis(inputs, "ac")
    print("RE", re, "midband", round(out["midband"]["gain_db"],3), out["cutoff"], "points", len(out["frequency_hz"]))
