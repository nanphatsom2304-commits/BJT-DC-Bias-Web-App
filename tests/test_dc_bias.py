import unittest

from dc_bias import DcBiasInputs, calculate_dc_bias, parse_inputs


RAW = {
    "vcc": "12", "r1": "100", "r1_unit": "kohm", "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm", "re": "1", "re_unit": "kohm",
    "beta": "100", "vbe": "0.7",
}


class ReferenceCaseTest(unittest.TestCase):
    def test_reference_case_matches_independent_calculation(self):
        result = calculate_dc_bias(DcBiasInputs(
            vcc_v=12.0, r1_ohm=100_000.0, r2_ohm=22_000.0,
            rc_ohm=2_200.0, re_ohm=1_000.0, beta=100.0, vbe_v=0.70,
        ))
        self.assertAlmostEqual(result.vth_v, 2.163934, places=4)
        self.assertAlmostEqual(result.rth_ohm, 18_032.787, delta=0.01)
        self.assertAlmostEqual(result.ib_a * 1e6, 12.2986, places=4)
        self.assertAlmostEqual(result.ic_a * 1e3, 1.22986, places=4)
        self.assertAlmostEqual(result.ie_a * 1e3, 1.24216, places=4)
        self.assertAlmostEqual(result.vb_v, 1.94216, places=4)
        self.assertAlmostEqual(result.ve_v, 1.24216, places=4)
        self.assertAlmostEqual(result.vc_v, 9.29431, places=4)
        self.assertAlmostEqual(result.vce_v, 8.05215, places=4)
        self.assertAlmostEqual(result.vbc_v, -7.35215, places=4)
        self.assertEqual(result.region, "forward_active")
        self.assertEqual(result.warnings, [])


class ParseInputsTest(unittest.TestCase):
    def test_ohm_and_kohm_inputs_give_same_result(self):
        k = dict(RAW)
        o = dict(RAW, r1="100000", r1_unit="ohm", r2="22000", r2_unit="ohm",
                 rc="2200", rc_unit="ohm", re="1000", re_unit="ohm")
        ki, kerr = parse_inputs(k)
        oi, oerr = parse_inputs(o)
        self.assertEqual(kerr, {})
        self.assertEqual(oerr, {})
        self.assertAlmostEqual(ki.r1_ohm, 100_000.0)
        self.assertAlmostEqual(oi.r1_ohm, 100_000.0)

    def test_rejects_missing_and_nonnumeric_fields(self):
        missing = dict(RAW)
        del missing["beta"]
        inputs, errors = parse_inputs(missing)
        self.assertIsNone(inputs)
        self.assertIn("beta", errors)

        bad = dict(RAW, r1="abc")
        inputs, errors = parse_inputs(bad)
        self.assertIsNone(inputs)
        self.assertIn("r1", errors)

    def test_rejects_nonpositive_resistance_beta_vcc(self):
        for key, value in (("r1", "0"), ("beta", "-1"), ("vcc", "0")):
            data = dict(RAW)
            data[key] = value
            inputs, errors = parse_inputs(data)
            self.assertIsNone(inputs, key)
            self.assertIn(key, errors)

    def test_rejects_unknown_unit_and_infinite_value(self):
        inputs, errors = parse_inputs(dict(RAW, r1_unit="M"))
        self.assertIsNone(inputs)
        self.assertIn("r1", errors)

        inputs, errors = parse_inputs(dict(RAW, r1="inf"))
        self.assertIsNone(inputs)
        self.assertIn("r1", errors)


class RegionTest(unittest.TestCase):
    def test_cutoff_when_vth_not_above_vbe(self):
        inputs, errors = parse_inputs(dict(RAW, r2="1", r2_unit="kohm"))
        self.assertEqual(errors, {})
        result = calculate_dc_bias(inputs)
        self.assertEqual(result.region, "cutoff")
        self.assertTrue(result.warnings)

    def test_saturation_when_vce_below_threshold(self):
        inputs, _ = parse_inputs(dict(RAW, rc="8.6", rc_unit="kohm"))
        result = calculate_dc_bias(inputs)
        self.assertEqual(result.region, "saturation")
        self.assertLess(result.vce_v, 0.3)
        self.assertTrue(result.warnings)

    def test_deep_saturation_negative_vce_does_not_crash(self):
        inputs, _ = parse_inputs(dict(RAW, rc="20", rc_unit="kohm"))
        result = calculate_dc_bias(inputs)
        self.assertEqual(result.region, "saturation")
        self.assertLess(result.vce_v, 0.0)

    def test_extreme_values_stay_finite(self):
        import math
        inputs, errors = parse_inputs(dict(
            RAW, r1="1000000000", r1_unit="ohm", r2="1000000000", r2_unit="ohm",
            rc="1", rc_unit="ohm", re="1", re_unit="ohm",
        ))
        self.assertEqual(errors, {})
        result = calculate_dc_bias(inputs)
        for value in (result.ic_a, result.vce_v, result.vb_v):
            self.assertTrue(math.isfinite(value))
