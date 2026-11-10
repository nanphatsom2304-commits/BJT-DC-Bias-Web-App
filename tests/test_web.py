import unittest

from app import app


RAW = {
    "vcc": "12", "r1": "100", "r1_unit": "kohm", "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm", "re": "1", "re_unit": "kohm",
    "beta": "100", "vbe": "0.7",
}


class IndexPageTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_returns_200_with_all_input_fields(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for name in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{name}"', html)
        for name in ("r1_unit", "r2_unit", "rc_unit", "re_unit"):
            self.assertIn(f'name="{name}"', html)

    def test_index_links_static_assets_and_has_result_containers(self):
        html = self.client.get("/").get_data(as_text=True)
        for asset in ("/static/app.js", "/static/style.css"):
            self.assertIn(asset, html)
        for element_id in ("form-errors", "results", "region-badge",
                           "warnings", "submit-btn"):
            self.assertIn(f'id="{element_id}"', html)


class CalculateApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_post_calculate_returns_json_reference_case(self):
        response = self.client.post("/calculate", data=RAW)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        data = body["data"]
        self.assertEqual(data["region"], "forward_active")
        self.assertEqual(data["warnings"], [])
        self.assertAlmostEqual(data["intermediate"]["vth_v"], 2.163934, places=4)
        self.assertAlmostEqual(
            data["operating_point"]["ic_a"] * 1e3, 1.22986, places=4)
        self.assertAlmostEqual(data["operating_point"]["vce_v"], 8.05215, places=3)
        self.assertAlmostEqual(data["inputs_si"]["r1_ohm"], 100_000.0)


class CalculateApiErrorTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_post_calculate_returns_400_with_field_errors(self):
        for key, bad in (("beta", "-1"), ("r1", "abc"), ("vcc", "0")):
            data = dict(RAW)
            data[key] = bad
            response = self.client.post("/calculate", data=data)
            self.assertEqual(response.status_code, 400, key)
            body = response.get_json()
            self.assertFalse(body["ok"])
            self.assertIn(key, body["errors"])

    def test_missing_or_bad_unit_is_reported_on_base_field(self):
        data = dict(RAW)
        del data["r1_unit"]
        response = self.client.post("/calculate", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("r1", response.get_json()["errors"])

        data = dict(RAW, rc_unit="M")
        response = self.client.post("/calculate", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("rc", response.get_json()["errors"])


class CalculateApiRegionTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_post_calculate_cutoff_includes_warning(self):
        response = self.client.post(
            "/calculate", data=dict(RAW, r2="1", r2_unit="kohm"))
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["region"], "cutoff")
        self.assertTrue(body["data"]["warnings"])

    def test_post_calculate_saturation_includes_warning(self):
        response = self.client.post(
            "/calculate", data=dict(RAW, rc="20", rc_unit="kohm"))
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["region"], "saturation")
        self.assertLess(body["data"]["operating_point"]["vce_v"], 0.3)
        self.assertTrue(body["data"]["warnings"])
