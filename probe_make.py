import spice_engine as s
inputs, _ = s.parse_inputs({"vcc":"12","r1":"100","r1_unit":"kohm","r2":"22","r2_unit":"kohm","rc":"2.2","rc_unit":"kohm","re":"1","re_unit":"kohm","rl":"10","rl_unit":"kohm","cin":"10","cin_unit":"uf","cout":"10","cout_unit":"uf","amp_mv":"10","freq_hz":"1000"}, "dc")
open("probe_dc.cir","w",encoding="ascii").write(s.build_netlist(inputs,"dc"))
