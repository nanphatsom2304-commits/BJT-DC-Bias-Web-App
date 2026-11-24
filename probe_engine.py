import json
import spice_engine as s

raw = {
    "vcc": "12", "r1": "100", "r1_unit": "kohm", "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm", "re": "1", "re_unit": "kohm",
    "rl": "10", "rl_unit": "kohm", "cin": "10", "cin_unit": "uf",
    "cout": "10", "cout_unit": "uf", "amp_mv": "10", "freq_hz": "1000",
}
print("engine:", json.dumps(s.engine_info(), ensure_ascii=False))
for mode in ("dc", "ac", "tran"):
    inputs, errors = s.parse_inputs(raw, mode)
    assert not errors, errors
    out = s.run_analysis(inputs, mode)
    if mode == "dc":
        print("DC:", json.dumps(out["operating_point"], indent=1))
    elif mode == "ac":
        print("AC midband:", out["midband"], "cutoff:", out["cutoff"], "points:", len(out["frequency_hz"]))
    else:
        print("TRAN:", json.dumps(out["summary"], indent=1), "points:", len(out["time_s"]), "raw:", out["raw_point_count"])
print("OK")
