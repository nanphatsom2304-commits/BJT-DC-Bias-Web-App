"""HTTP contract tests for the Lab 4 simulator endpoints."""

import unittest
from unittest.mock import patch

import spice_engine
from app import app

FORM = {
    "analysis": "dc",
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


def simulate_payload(**overrides):
    data = {f"sim_{key}": value for key, value in FORM.items()}
    data.update({f"sim_{key}": value for key, value in overrides.items()})
    return data


FAKE_RESULT = {
    "analysis": "dc",
    "analysis_label": "DC operating point (.op)",
    "operating_point": {
        "vb_v": 1.979097, "ve_v": 1.331351, "vc_v": 9.093577,
        "vbe_v": 0.647746, "vce_v": 7.762226, "vbc_v": -7.11448,
        "ic_a": 1.321194e-3, "ib_a": 1.025072e-5, "ie_a": 1.331445e-3,
    },
    "engine": {
        "name": "ngspice",
        "version": "ngspice-47",
        "command": "ngspice_con.exe",
        "run_mode": "batch",
        "model": {"name": "T2N2222", "source": "test", "note": "test"},
    },
    "netlist": "* netlist",
    "warnings": ["model note"],
}


class EngineStatusTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_engine_status_always_returns_json(self):
        response = self.client.get("/api/engine")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("available", body["data"])

    def test_missing_engine_is_reported_without_crashing(self):
        with patch.object(
            spice_engine, "engine_info", side_effect=spice_engine.NgspiceNotFound("missing")
        ):
            response = self.client.get("/api/engine")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["data"]["available"])
        self.assertIn("missing", body["data"]["message"])


class SimulateValidationTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_missing_fields_return_400_with_prefixed_keys(self):
        response = self.client.post("/api/simulate", data={"sim_analysis": "dc"})
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["ok"])
        for key in ("vcc", "r1", "rc", "re", "rl", "cin", "cout"):
            self.assertIn(key, body["errors"])

    def test_bad_value_and_unit_are_reported(self):
        response = self.client.post(
            "/api/simulate", data=simulate_payload(rc="abc", rl_unit="M")
        )
        self.assertEqual(response.status_code, 400)
        errors = response.get_json()["errors"]
        self.assertIn("rc", errors)
        self.assertIn("rl", errors)

    def test_transient_requires_amplitude(self):
        payload = simulate_payload(analysis="tran")
        del payload["sim_amp_mv"]
        response = self.client.post("/api/simulate", data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("amp_mv", response.get_json()["errors"])

    def test_unknown_analysis_is_rejected(self):
        response = self.client.post(
            "/api/simulate", data=simulate_payload(analysis="fft")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("analysis", response.get_json()["errors"])


class SimulateResponseTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_successful_run_includes_reference_and_engine_metadata(self):
        with patch.object(spice_engine, "run_analysis", return_value=dict(FAKE_RESULT)):
            response = self.client.post("/api/simulate", data=simulate_payload())

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        data = body["data"]

        # SPICE payload is passed through unchanged.
        self.assertEqual(data["operating_point"]["ic_a"], FAKE_RESULT["operating_point"]["ic_a"])
        self.assertEqual(data["engine"]["model"]["name"], "T2N2222")

        # Analytical reference is recomputed by the Lab 3 equations.
        reference = data["reference"]
        self.assertEqual(reference["assumptions"]["beta"], 100.0)
        self.assertAlmostEqual(reference["vth_v"], 2.163934, places=4)
        self.assertAlmostEqual(reference["rth_ohm"], 18_032.79, places=1)
        self.assertAlmostEqual(reference["operating_point"]["ic_a"] * 1e3, 1.22986, places=4)
        self.assertEqual(reference["region"], "forward_active")

    def test_reference_uses_the_submitted_resistors(self):
        with patch.object(spice_engine, "run_analysis", return_value=dict(FAKE_RESULT)):
            response = self.client.post(
                "/api/simulate", data=simulate_payload(re="2")
            )
        reference = response.get_json()["data"]["reference"]
        self.assertLess(reference["operating_point"]["ic_a"] * 1e3, 1.0)

    def test_missing_engine_returns_503_with_flag(self):
        with patch.object(
            spice_engine, "run_analysis", side_effect=spice_engine.NgspiceNotFound("no binary")
        ):
            response = self.client.post("/api/simulate", data=simulate_payload())
        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["engine_unavailable"])
        self.assertIn("no binary", body["message"])

    def test_spice_failure_returns_502_with_message(self):
        with patch.object(
            spice_engine, "run_analysis", side_effect=spice_engine.SpiceRunError("boom")
        ):
            response = self.client.post("/api/simulate", data=simulate_payload())
        self.assertEqual(response.status_code, 502)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["message"], "boom")


class SimulateIntegrationTest(unittest.TestCase):
    """End-to-end through Flask with the real ngspice binary."""

    def setUp(self):
        try:
            spice_engine.find_ngspice()
        except spice_engine.NgspiceNotFound:
            self.skipTest("ngspice not installed")
        self.client = app.test_client()

    def test_dc_request_returns_real_operating_point(self):
        response = self.client.post("/api/simulate", data=simulate_payload())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["analysis"], "dc")
        self.assertGreater(data["operating_point"]["vce_v"], 7.0)
        self.assertIn("Q1 coll base emit T2N2222", data["netlist"])
        self.assertIn("ngspice", data["engine"]["version"])

    def test_ac_request_returns_bode_data(self):
        response = self.client.post(
            "/api/simulate", data=simulate_payload(analysis="ac")
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertGreater(len(data["frequency_hz"]), 100)
        self.assertEqual(len(data["frequency_hz"]), len(data["gain_db"]))
        self.assertLess(data["midband"]["phase_deg"], -150.0)

    def test_tran_request_returns_waveform(self):
        response = self.client.post(
            "/api/simulate", data=simulate_payload(analysis="tran")
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertGreater(len(data["time_s"]), 100)
        self.assertEqual(len(data["time_s"]), len(data["vout_v"]))
        self.assertTrue(data["summary"]["inverted"])


if __name__ == "__main__":
    unittest.main()
