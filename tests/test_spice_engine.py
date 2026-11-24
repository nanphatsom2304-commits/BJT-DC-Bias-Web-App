"""Tests for the ngspice adapter (netlist, validation, parsing).

Only the integration test at the bottom needs a real ngspice install; it is
skipped when the executable is missing so the suite stays runnable anywhere.
"""

import math
import unittest

import spice_engine as spice
from spice_engine import (
    SpiceParseError,
    SpiceRunError,
    build_netlist,
    parse_inputs,
    parse_log,
)

BASE_FORM = {
    "vcc": "12",
    "r1": "100", "r1_unit": "kohm",
    "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm",
    "re": "1", "re_unit": "kohm",
    "rl": "10", "rl_unit": "kohm",
    "cin": "10", "cin_unit": "uf",
    "cout": "10", "cout_unit": "uf",
    "amp_mv": "10",
    "freq_hz": "1000",
}


def form(**overrides):
    data = dict(BASE_FORM)
    data.update(overrides)
    return data


DC_LOG = """
Circuit: * Lab 04 - BJT CE voltage-divider amplifier

Doing analysis at TEMP = 27.000000 and TNOM = 27.000000
No. of Data Rows : 1
	Node                                  Voltage
	----                                  -------
	----	-------
	out                              0.000000e+00
	emit                             1.331351e+00
	coll                             9.093577e+00
	base                             1.979097e+00
	src                              0.000000e+00
	vcc                              1.200000e+01

	Source	Current
	------	-------

	@q1[ie]                          -1.33144e-03
	@q1[ib]                          1.025072e-05
	@q1[ic]                          1.321194e-03
	vcc#branch                       -1.42131e-03
"""

AC_LOG = """
Circuit: * Lab 04 - BJT CE voltage-divider amplifier
No. of Data Rows : 6
Index   frequency       vm(out)         vp(out)
--------------------------------------------------------------------------------
0\t1.000000e+00\t1.000000e-01\t-1.570000e+00
1\t1.000000e+01\t1.000000e+00\t-3.120000e+00
2\t1.000000e+02\t1.740000e+00\t-3.140000e+00
3\t1.000000e+03\t1.752483e+00\t-3.139394e+00
4\t1.000000e+05\t1.740000e+00\t3.140000e+00
5\t1.000000e+07\t5.000000e-01\t2.000000e-01
"""


class ParseInputsTest(unittest.TestCase):
    def test_baseline_form_converts_to_si_units(self):
        inputs, errors = parse_inputs(BASE_FORM, "dc")
        self.assertEqual(errors, {})
        self.assertAlmostEqual(inputs.vcc_v, 12.0)
        self.assertAlmostEqual(inputs.r1_ohm, 100_000.0)
        self.assertAlmostEqual(inputs.r2_ohm, 22_000.0)
        self.assertAlmostEqual(inputs.rc_ohm, 2_200.0)
        self.assertAlmostEqual(inputs.re_ohm, 1_000.0)
        self.assertAlmostEqual(inputs.rl_ohm, 10_000.0)
        self.assertAlmostEqual(inputs.cin_f, 10e-6)
        self.assertAlmostEqual(inputs.cout_f, 10e-6)
        self.assertAlmostEqual(inputs.source_amplitude_v, 0.010)
        self.assertAlmostEqual(inputs.source_frequency_hz, 1_000.0)

    def test_dc_ignores_missing_source_fields(self):
        raw = form()
        del raw["amp_mv"]
        del raw["freq_hz"]
        inputs, errors = parse_inputs(raw, "dc")
        self.assertEqual(errors, {})
        self.assertAlmostEqual(inputs.source_amplitude_v, 0.010)
        self.assertAlmostEqual(inputs.source_frequency_hz, 1_000.0)

    def test_transient_requires_source_fields(self):
        raw = form()
        del raw["amp_mv"]
        _, errors = parse_inputs(raw, "tran")
        self.assertIn("amp_mv", errors)

    def test_nan_and_infinity_are_rejected(self):
        for value in ("nan", "inf", "-Infinity"):
            with self.subTest(value=value):
                _, errors = parse_inputs(form(vcc=value), "dc")
                self.assertIn("vcc", errors)

    def test_bad_units_report_the_base_field(self):
        for key in ("r1_unit", "rl_unit"):
            with self.subTest(key=key):
                raw = form(**{key: "M"})
                _, errors = parse_inputs(raw, "dc")
                self.assertIn(key.removesuffix("_unit"), errors)

    def test_capacitor_unit_is_validated(self):
        _, errors = parse_inputs(form(cin_unit="uf_typo"), "dc")
        self.assertIn("cin", errors)

    def test_out_of_range_and_zero_values_are_rejected(self):
        cases = {
            "vcc": "0",
            "r2": "0",
            "rl": "1e9",
            "cin": "0",
            "amp_mv": "0",
            "freq_hz": "1",
        }
        for key, value in cases.items():
            with self.subTest(field=key):
                _, errors = parse_inputs(form(**{key: value}), "tran")
                self.assertIn(key, errors)

    def test_unknown_analysis_is_rejected(self):
        _, errors = parse_inputs(BASE_FORM, "fft")
        self.assertIn("analysis", errors)


class NetlistTest(unittest.TestCase):
    def setUp(self):
        self.inputs, _ = parse_inputs(BASE_FORM, "dc")

    def test_dc_netlist_uses_reference_topology(self):
        netlist = build_netlist(self.inputs, "dc")
        for line in (
            "VCC vcc 0 12",
            "VIN src 0 DC 0 AC 1 SIN(0 0.01 1000)",
            "R1 vcc base 100000",
            "R2 base 0 22000",
            "RC vcc coll 2200",
            "RE emit 0 1000",
            "CIN src base 1e-05",
            "COUT coll out 1e-05",
            "RL out 0 10000",
            "Q1 coll base emit T2N2222",
        ):
            self.assertIn(line, netlist)
        self.assertIn(".model T2N2222 NPN(", netlist)
        self.assertIn(".op", netlist)
        self.assertIn("@q1[ic]", netlist)
        self.assertTrue(netlist.rstrip().endswith(".end"))

    def test_ac_and_tran_netlists_use_their_own_directive(self):
        ac = build_netlist(self.inputs, "ac")
        self.assertIn(".ac dec", ac)
        self.assertIn("vm(out) vp(out)", ac)
        self.assertNotIn(".tran", ac)

        tran = build_netlist(self.inputs, "tran")
        self.assertIn(".tran", tran)
        self.assertIn("v(src) v(out)", tran)
        self.assertNotIn(".ac ", tran)

    def test_transient_duration_follows_source_frequency(self):
        slow, _ = parse_inputs(form(freq_hz="100"), "tran")
        fast, _ = parse_inputs(form(freq_hz="10000"), "tran")
        slow_stop = float(build_netlist(slow, "tran").split(".tran")[1].split()[1])
        fast_stop = float(build_netlist(fast, "tran").split(".tran")[1].split()[1])
        self.assertGreater(slow_stop, fast_stop)
        self.assertAlmostEqual(fast_stop, 1e-3, places=9)

    def test_unknown_analysis_raises(self):
        with self.assertRaises(SpiceParseError):
            build_netlist(self.inputs, "fft")


class ParseLogTest(unittest.TestCase):
    def test_dc_operating_point_is_read_from_nodes_and_currents(self):
        data = parse_log(DC_LOG, "dc")
        point = data["operating_point"]
        self.assertAlmostEqual(point["vb_v"], 1.979097, places=6)
        self.assertAlmostEqual(point["ve_v"], 1.331351, places=6)
        self.assertAlmostEqual(point["vce_v"], 7.762226, places=6)
        self.assertAlmostEqual(point["ic_a"], 1.321194e-3, places=9)
        self.assertAlmostEqual(point["ib_a"], 1.025072e-5, places=9)
        self.assertAlmostEqual(point["ie_a"], point["ic_a"] + point["ib_a"], places=12)

    def test_dc_with_missing_node_raises(self):
        broken = DC_LOG.replace("coll                             9.093577e+00\n", "")
        with self.assertRaises(SpiceParseError):
            parse_log(broken, "dc")

    def test_dc_without_currents_raises(self):
        broken = DC_LOG.replace("\t@q1[ic]                          1.321194e-03\n", "")
        with self.assertRaises(SpiceParseError):
            parse_log(broken, "dc")

    def test_ac_rows_produce_gain_phase_and_cutoffs(self):
        data = parse_log(AC_LOG, "ac")
        self.assertEqual(len(data["frequency_hz"]), 6)
        self.assertAlmostEqual(data["midband"]["frequency_hz"], 1000.0)
        self.assertAlmostEqual(data["midband"]["gain_db"], 4.873, places=3)
        self.assertIsNotNone(data["cutoff"]["low_hz"])
        self.assertIsNotNone(data["cutoff"]["high_hz"])
        self.assertGreater(data["cutoff"]["high_hz"], data["cutoff"]["low_hz"])

    def test_ac_operating_point_follows_requested_frequency(self):
        data = parse_log(AC_LOG, "ac", target_hz=100.0)
        self.assertAlmostEqual(data["midband"]["frequency_hz"], 100.0)
        self.assertAlmostEqual(data["midband"]["target_hz"], 100.0)
        self.assertAlmostEqual(data["midband"]["gain_vv"], 1.74, places=6)

    def test_ac_phase_is_unwrapped(self):
        data = parse_log(AC_LOG, "ac")
        phases = data["phase_deg"]
        for previous, current in zip(phases, phases[1:]):
            self.assertLess(abs(current - previous), 180.0)

    def test_empty_ac_output_raises(self):
        with self.assertRaises(SpiceParseError):
            parse_log("no numeric table here", "ac")

    def test_tran_rows_produce_steady_state_summary(self):
        lines = ["Index   time            v(src)          v(out)",
                 "-" * 60]
        for index in range(1000):
            time_value = index * 2e-6
            vin = 0.010 * math.sin(2 * math.pi * 1000 * time_value)
            vout = -1.75 * vin
            lines.append(f"{index}\t{time_value:.6e}\t{vin:.6e}\t{vout:.6e}")
        data = parse_log("\n".join(lines), "tran")
        summary = data["summary"]
        self.assertAlmostEqual(summary["vin_pp_v"], 0.020, places=3)
        self.assertAlmostEqual(summary["gain_vv"], 1.75, places=2)
        self.assertTrue(summary["inverted"])
        self.assertLess(summary["correlation"], -0.9)


class IntegrationTest(unittest.TestCase):
    """Runs the real ngspice binary; skipped when it is not installed."""

    @classmethod
    def setUpClass(cls):
        try:
            spice.find_ngspice()
        except spice.NgspiceNotFound:
            raise unittest.SkipTest("ngspice not installed")

    def run_mode(self, analysis, **overrides):
        inputs, errors = parse_inputs(form(**overrides), analysis)
        self.assertEqual(errors, {})
        return spice.run_analysis(inputs, analysis)

    def test_dc_run_matches_reference_operating_point(self):
        data = self.run_mode("dc")
        point = data["operating_point"]
        self.assertEqual(data["analysis"], "dc")
        self.assertGreater(point["vce_v"], 7.0)
        self.assertLess(point["vce_v"], 9.0)
        self.assertAlmostEqual(point["vce_v"], point["vc_v"] - point["ve_v"], places=6)
        self.assertEqual(data["engine"]["name"], "ngspice")
        self.assertIn("ngspice", data["engine"]["version"])
        self.assertEqual(len(data["warnings"]), 1)

    def test_bigger_re_lowers_current(self):
        baseline = self.run_mode("dc")["operating_point"]["ic_a"]
        larger_re = self.run_mode("dc", re="2")["operating_point"]["ic_a"]
        self.assertLess(larger_re, baseline)

    def test_ac_run_reports_midband_gain_and_cutoffs(self):
        data = self.run_mode("ac")
        self.assertGreater(data["midband"]["gain_vv"], 1.0)
        self.assertLess(data["midband"]["gain_vv"], 3.0)
        self.assertLess(data["midband"]["phase_deg"], -150.0)
        self.assertIsNotNone(data["cutoff"]["low_hz"])
        self.assertGreater(len(data["frequency_hz"]), 50)

    def test_tran_run_is_inverted_and_scaled(self):
        data = self.run_mode("tran")
        summary = data["summary"]
        self.assertAlmostEqual(summary["vin_pp_v"], 0.020, places=3)
        self.assertGreater(summary["vout_pp_v"], 0.020)
        self.assertTrue(summary["inverted"])
        self.assertLessEqual(len(data["time_s"]), 1_000)

    def test_timeout_is_reported_as_user_error(self):
        inputs, _ = parse_inputs(form(), "dc")
        with self.assertRaises(SpiceRunError):
            spice.run_analysis(inputs, "dc", timeout_s=0.001)


if __name__ == "__main__":
    unittest.main()
