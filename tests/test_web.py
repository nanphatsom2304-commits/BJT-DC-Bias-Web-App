import unittest
from html.parser import HTMLParser

from app import app


RAW = {
    "vcc": "12", "r1": "100", "r1_unit": "kohm", "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm", "re": "1", "re_unit": "kohm",
    "beta": "100", "vbe": "0.7",
}


class _FieldParser(HTMLParser):
    """Collect each ``div.field`` together with the controls it contains."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.open_fields: list[tuple[int, dict]] = []
        self.fields: list[dict] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.depth += 1
            if "field" in (attrs.get("class") or "").split():
                field = {
                    "modes": attrs.get("data-modes", ""),
                    "hidden": "hidden" in attrs,
                    "controls": [],
                }
                self.fields.append(field)
                self.open_fields.append((self.depth, field))
        elif tag in ("input", "select") and self.open_fields:
            self.open_fields[-1][1]["controls"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "div":
            if self.open_fields and self.open_fields[-1][0] == self.depth:
                self.open_fields.pop()
            self.depth -= 1


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

    def test_index_has_mode_selector_and_rb_field(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('name="mode"', html)
        self.assertIn('id="mode"', html)
        self.assertIn('name="rb"', html)
        self.assertIn('name="rb_unit"', html)
        self.assertIn('id="result-mode"', html)

        parser = _FieldParser()
        parser.feed(html)
        fields = {}
        for field in parser.fields:
            for control in field["controls"]:
                key = control.get("id") or control.get("name")
                fields.setdefault(key, field)

        # showErrors() resolves a field error via input.closest(".field"),
        # so every control that can receive an error needs that ancestor.
        expected_modes = {
            "mode": {"divider", "fixed", "emitter"},
            "vcc": {"divider", "fixed", "emitter"},
            "r1": {"divider"},
            "r2": {"divider"},
            "rc": {"divider", "fixed", "emitter"},
            "re": {"divider", "emitter"},
            "rb": {"fixed", "emitter"},
            "beta": {"divider", "fixed", "emitter"},
            "vbe": {"divider", "fixed", "emitter"},
        }
        for key, modes in expected_modes.items():
            with self.subTest(field=key):
                self.assertIn(key, fields)
                self.assertEqual(set(fields[key]["modes"].split()), modes)

        self.assertTrue(fields["rb"]["hidden"])
        self.assertFalse(fields["re"]["hidden"])


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


class CalculateModeTest(unittest.TestCase):
    FIXED = {"mode": "fixed", "vcc": "12", "rc": "2.2", "rc_unit": "kohm",
             "rb": "1000", "rb_unit": "kohm", "beta": "100", "vbe": "0.7"}

    def setUp(self):
        self.client = app.test_client()

    def test_post_fixed_returns_mode_and_values(self):
        response = self.client.post("/calculate", data=self.FIXED)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        data = body["data"]
        self.assertEqual(data["mode"], "fixed")
        self.assertEqual(data["intermediate"], {})
        self.assertAlmostEqual(data["operating_point"]["ic_a"] * 1e3, 1.13000, places=4)
        self.assertAlmostEqual(data["operating_point"]["vce_v"], 9.51400, places=4)
        self.assertEqual(data["inputs_si"]["rb_ohm"], 1_000_000.0)

    def test_post_emitter_uses_re(self):
        raw = dict(self.FIXED, mode="emitter", re="1", re_unit="kohm")
        response = self.client.post("/calculate", data=raw)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["mode"], "emitter")
        self.assertAlmostEqual(data["operating_point"]["vce_v"], 8.70545, places=4)
        self.assertEqual(data["inputs_si"]["re_ohm"], 1_000.0)

    def test_post_unknown_mode_returns_400(self):
        raw = dict(self.FIXED, mode="bridge")
        response = self.client.post("/calculate", data=raw)
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["mode"], "bridge")
        self.assertIn("mode", body["errors"])

    def test_post_blank_mode_returns_400(self):
        response = self.client.post("/calculate", data=dict(self.FIXED, mode=""))
        self.assertEqual(response.status_code, 400)
        self.assertIn("mode", response.get_json()["errors"])

    def test_post_missing_mode_defaults_to_divider(self):
        response = self.client.post("/calculate", data=RAW)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["mode"], "divider")

    def test_post_uppercase_mode_is_normalized(self):
        response = self.client.post(
            "/calculate", data=dict(self.FIXED, mode="  FIXED  "))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["mode"], "fixed")

    def test_post_fixed_rb_zero_reports_field_error_with_mode(self):
        response = self.client.post(
            "/calculate", data=dict(self.FIXED, rb="0"))
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["mode"], "fixed")
        self.assertIn("rb", body["errors"])

    def test_post_fixed_negative_beta_reports_field_error_with_mode(self):
        response = self.client.post(
            "/calculate", data=dict(self.FIXED, beta="-1"))
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertEqual(body["mode"], "fixed")
        self.assertIn("beta", body["errors"])

    def test_post_overflowing_result_returns_400(self):
        raw = {"mode": "fixed", "vcc": "1e308", "rc": "1", "rc_unit": "ohm",
               "rb": "1", "rb_unit": "ohm", "beta": "1e308", "vbe": "0.7"}
        response = self.client.post("/calculate", data=raw)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["mode"], "fixed")

