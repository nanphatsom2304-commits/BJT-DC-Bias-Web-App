# BJT DC Bias Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ส่งมอบ Flask Web App หลายไฟล์ที่คำนวณ DC Operating Point ของ BJT Voltage-Divider Bias ด้วย Python backend พร้อม validation, region warning และ automated tests 10 รายการ

**Architecture:** ฟอร์มยิง `fetch POST /calculate` → Flask route (`app.py`) → `parse_inputs()` + `calculate_dc_bias()` ใน `dc_bias.py` (Python ล้วน, SI units) → JSON → `static/app.js` วาดผลโดยไม่ reload

**Tech Stack:** Python 3.15.2, Flask 3.x, Jinja2, vanilla JS, `unittest`

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-dc-bias-web-app-design.md`

## Global Constraints

- Python 3.15.2, venv ที่ `.venv`; ใช้ `.venv\Scripts\python.exe` เรียกทุกคำสั่ง (ไม่ต้อง activate)
- Flask `>=3.0,<4.0`; ห้ามใช้ CDN/CSS framework ภายนอก (ต้องรันได้ offline)
- JSON ทุกค่าอยู่ใน SI base units (V, A, Ω); การจัดรูปแบบ mA/µA/kΩ เป็นหน้าที่ `app.js`
- คีย์ของ `errors` = ชื่อฟิลด์ฐานเท่านั้น: `vcc, r1, r2, rc, re, beta, vbe`
- Region: `VTH ≤ VBE` → `cutoff`; `VCE < 0.3` → `saturation`; นอกนั้น `forward_active`
- คำสั่งเทสต์มาตรฐาน: `.venv\Scripts\python.exe -m unittest discover -s tests -v` (ต้องผ่านครบ 10 tests)
- **Agent ห้ามรัน `git commit` / `git push` / `git add`** — ทุก task จบด้วยการส่ง working tree ให้นักศึกษา commit ใน GitHub Desktop
- ห้าม commit `.venv/`, `__pycache__/`, `.env`, credential
- Error ต้องเป็น HTTP 400 + ข้อความภาษาไทยที่อ่านรู้เรื่อง ห้ามหลุด stack trace

## Review Focus

1. **ช่องหน่วยถูกเว้นว่างหรือถูกแก้ค่า** → ต้องได้ `errors["r1"]` และ HTTP 400 ไม่ใช่ 500
2. **ค่าสุดขั้วแต่ยังถูกกติกา** (R ระดับ 1e-3 ถึง 1e12 Ω) → ผลต้องเป็นจำนวนจริงจำกัด ไม่มี `inf`/`nan`
3. **กด Calculate ซ้ำหรือเซิร์ฟเวอร์ล่ม** → ปุ่มต้องกลับมาใช้ได้ ไม่ค้าง "กำลังคำนวณ…"
4. **โหลดหน้าใหม่หรือคำนวณรอบสอง** → ผล/error รอบก่อนต้องถูกเคลียร์ ไม่ค้างจอ
5. **ค่าที่ทำให้ VCE ติดลบ (deep saturation)** → ต้องเตือน saturation ไม่ crash และไม่อ้างว่าแบบจำลองใช้ได้

## File Structure

| ไฟล์ | ความรับผิดชอบ |
|------|----------------|
| `dc_bias.py` | dataclasses + `parse_inputs()` + `calculate_dc_bias()` — ไม่ import Flask |
| `app.py` | Flask app, `GET /`, `POST /calculate`, JSON serialization |
| `templates/index.html` | ฟอร์ม 7 ช่อง + containers สำหรับผล/error (ไม่มีสมการ) |
| `static/app.js` | fetch, render ผล/error, loading state |
| `static/style.css` | layout, responsive, region badge |
| `tests/test_dc_bias.py` | 6 tests ของ logic (ไม่ต้องมี Flask) |
| `tests/test_web.py` | 4 tests ผ่าน Flask test client |
| `README.md`, `AGENTS.md`, `docs/*.md` | เอกสารส่งมอบ |

---

### Task 1: Scaffold + core calculation (reference case)

**Files:**
- Create: `.gitignore`, `requirements.txt`, `dc_bias.py`, `tests/test_dc_bias.py`

**Interfaces:**
- Produces: `DcBiasInputs(vcc_v, r1_ohm, r2_ohm, rc_ohm, re_ohm, beta, vbe_v)`;
  `DcBiasResult(inputs_si, vth_v, rth_ohm, ib_a, ic_a, ie_a, vb_v, ve_v, vc_v, vce_v, vbc_v, region, warnings)`;
  `calculate_dc_bias(inputs: DcBiasInputs) -> DcBiasResult`

- [ ] **Step 1: สร้าง venv และติดตั้ง dependency**

```powershell
python -m venv .venv
```
สร้าง `requirements.txt`:
```
Flask>=3.0,<4.0
```
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: `Successfully installed ... flask-3.x ...`

- [ ] **Step 2: สร้าง `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
```

- [ ] **Step 3: เขียน failing test**

`tests/test_dc_bias.py`:
```python
import unittest

from dc_bias import DcBiasInputs, calculate_dc_bias


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
```

- [ ] **Step 4: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dc_bias'`

- [ ] **Step 5: สร้าง `dc_bias.py`**

ประกาศ `@dataclass(frozen=True)` ทั้งสองตัวตาม Interfaces และเขียน `calculate_dc_bias`
ตามสมการใน spec §10; Task นี้ให้ `region="forward_active"` และ `warnings=[]` ไปก่อน
(ตัดสิน region จริงใน Task 3); เก็บ `inputs_si=inputs` ไว้ในผลลัพธ์

- [ ] **Step 6: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (1 test)

- [ ] **Step 7: ส่งงานให้นักศึกษา commit**

Run: `git status --short`
Expected: เห็น `.gitignore`, `requirements.txt`, `dc_bias.py`, `tests/` เป็นไฟล์ใหม่ (`.venv/` ต้องไม่โผล่)
แจ้งนักศึกษา: เปิด GitHub Desktop → commit ด้วย Summary `feat: add DC bias core calculation`

---

### Task 2: `parse_inputs()` — unit conversion + validation

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `DcBiasInputs` (Task 1)
- Produces: `parse_inputs(raw: Mapping[str, str]) -> tuple[DcBiasInputs | None, dict[str, str]]`
  โดย `raw` มีคีย์ `vcc, r1, r1_unit, r2, r2_unit, rc, rc_unit, re, re_unit, beta, vbe`
  หน่วย R ที่รับ: `"ohm"`, `"kohm"`

- [ ] **Step 1: เขียน failing tests**

เพิ่มใน `tests/test_dc_bias.py`:
```python
from dc_bias import parse_inputs

RAW = {
    "vcc": "12", "r1": "100", "r1_unit": "kohm", "r2": "22", "r2_unit": "kohm",
    "rc": "2.2", "rc_unit": "kohm", "re": "1", "re_unit": "kohm",
    "beta": "100", "vbe": "0.7",
}


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
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: FAIL — `ImportError: cannot import name 'parse_inputs'`

- [ ] **Step 3: เขียน `parse_inputs`**

- ตรวจคีย์ที่ขาด/ว่างก่อน แล้วค่อยแปลง (`float()`); ใช้ `math.isfinite` ปฏิเสธ `inf`/`nan`
- ตัวคูณหน่วย: `ohm` = 1, `kohm` = 1_000; หน่วยอื่นหรือค่าว่าง → error ที่คีย์ฐานของ R ตัวนั้น
- กฎช่วงค่าตาม spec §11 (R > 0, VCC > 0, β > 0, 0 ≤ VBE ≤ 2)
- คืน `(None, errors)` เมื่อมี error อย่างน้อยหนึ่งรายการ; `errors` เป็น dict คีย์ฐาน
- ข้อความ error ภาษาไทยตาม spec §11

- [ ] **Step 4: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (5 tests)

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: parse and validate form inputs with unit conversion`

---

### Task 3: Region logic (cutoff / saturation / finite guard)

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `parse_inputs()`, `calculate_dc_bias()` (Tasks 1–2)
- Produces: `DcBiasResult.region` ∈ `forward_active|cutoff|saturation` และ `warnings: list[str]`

- [ ] **Step 1: เขียน failing tests**

```python
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
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: FAIL ที่ `test_cutoff_when_vth_not_above_vbe` (ได้ `forward_active`)

- [ ] **Step 3: เพิ่ม logic ตัดสิน region ใน `calculate_dc_bias`**

ตาม spec §12: `VTH <= VBE` → `cutoff` + warning ที่ระบุค่าทั้งสอง;
มิฉะนั้น `VCE < 0.3` → `saturation` + warning ที่ระบุ VCE; มิฉะนั้น `forward_active`
และ `warnings=[]` — ข้อความ warning ต้องบอกว่า approximation ใช้ไม่ได้/ไม่แม่นยำ

- [ ] **Step 4: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (9 tests)

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: warn when bias leaves forward-active region`

---

### Task 4: Flask app + index template (GET /)

**Files:**
- Create: `app.py`, `templates/index.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_inputs()`, `DcBiasInputs` (Tasks 1–2)
- Produces: Flask object `app` ที่ import ได้จาก `app.py`; route `GET /` คืน HTML 200

- [ ] **Step 1: เขียน failing test**

`tests/test_web.py`:
```python
import unittest

from app import app


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
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: สร้าง `app.py` และ `templates/index.html`**

`app.py`: `Flask(__name__)`, route `GET /` → `render_template("index.html")`
`templates/index.html`: ฟอร์ม 7 ช่อง (`type="number"` + `step="any"`), select หน่วย
`ohm/kohm` สำหรับ R แต่ละตัว, ปุ่ม `Calculate DC Bias`, `id="form-errors"`,
`id="results"`, `id="region-badge"`, `id="warnings"` — ยังไม่ต้องมีผลลัพธ์หรือ JS

- [ ] **Step 4: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (10 tests)

- [ ] **Step 5: ตรวจด้วยตาเปล่า**

Run: `.venv\Scripts\python.exe -m flask --app app run --debug`
Expected: เปิด `http://127.0.0.1:5000/` เห็นฟอร์มครบ 7 ช่อง (หยุดเซิร์ฟเวอร์ด้วย Ctrl+C)

- [ ] **Step 6: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: add Flask app and input form`

---

### Task 5: `POST /calculate` — JSON success path

**Files:**
- Modify: `app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_inputs()`, `calculate_dc_bias()` (Tasks 1–3)
- Produces: route `POST /calculate` → JSON ตาม spec §9 (`ok`, `data.inputs_si`,
  `data.intermediate`, `data.operating_point`, `data.region`, `data.warnings`)

- [ ] **Step 1: เขียน failing test**

```python
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
        self.assertAlmostEqual(data["intermediate"]["vth_v"], 2.163934, places=4)
        self.assertAlmostEqual(
            data["operating_point"]["ic_a"] * 1e3, 1.22986, places=4)
        self.assertAlmostEqual(data["operating_point"]["vce_v"], 8.05215, places=3)
        self.assertAlmostEqual(data["inputs_si"]["r1_ohm"], 100_000.0)
```
(นำ `RAW` จาก `tests/test_dc_bias.py` มาวางซ้ำในไฟล์นี้ หรือ import ก็ได้)

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v`
Expected: FAIL — 404 (route ยังไม่มี)

- [ ] **Step 3: เพิ่ม route ใน `app.py`**

อ่าน `request.form` → `parse_inputs` → ถ้า error ให้ `(jsonify({"ok": False, ...}), 400)`
(ทำเต็มใน Task 6) → ไม่งั้น `calculate_dc_bias` แล้วประกอบ JSON ตาม spec §9
(map field ของ dataclass เป็นคีย์ JSON ตามสัญญา; ค่า SI ไม่ปัดเศษ)

- [ ] **Step 4: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (11 tests)

- [ ] **Step 5: ตรวจด้วย `curl`**

```powershell
curl.exe -s -X POST http://127.0.0.1:5000/calculate `
  -d "vcc=12&r1=100&r1_unit=kohm&r2=22&r2_unit=kohm&rc=2.2&rc_unit=kohm&re=1&re_unit=kohm&beta=100&vbe=0.7"
```
Expected: JSON มี `"ok":true`, `"ic_a":0.00122986...`, `"region":"forward_active"`

- [ ] **Step 6: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: add calculate API endpoint`

---

### Task 6: Error responses (400 + per-field errors)

**Files:**
- Modify: `app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_inputs()` (Task 2)
- Produces: `POST /calculate` คืน HTTP 400 พร้อม `{"ok": false, "errors": {...}, "message": "..."}`

- [ ] **Step 1: เขียน failing tests**

```python
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
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v`
Expected: FAIL — ได้ 200 หรือ 500 แทน 400

- [ ] **Step 3: ทำ error branch ให้สมบูรณ์ใน `app.py`**

คืน `(jsonify({"ok": False, "errors": errors, "message": "กรุณาตรวจสอบค่าที่ป้อน"}), 400)`
โดยไม่เรียก `calculate_dc_bias` เมื่อ `inputs is None`

- [ ] **Step 4: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (13 tests)

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: return field-level validation errors`

---

### Task 7: Front end — fetch, render, badge, warnings

**Files:**
- Create: `static/app.js`, `static/style.css`
- Modify: `templates/index.html`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `POST /calculate` JSON ตาม spec §9
- Produces: DOM ids ที่ JS ใช้: `form-errors`, `results`, `region-badge`, `warnings`,
  `submit-btn`; ไฟล์ static ที่ผูกผ่าน `url_for('static', ...)`

- [ ] **Step 1: เขียน failing test**

```python
    def test_index_links_static_assets_and_has_result_containers(self):
        html = self.client.get("/").get_data(as_text=True)
        for asset in ("/static/app.js", "/static/style.css"):
            self.assertIn(asset, html)
        for element_id in ("form-errors", "results", "region-badge",
                           "warnings", "submit-btn"):
            self.assertIn(f'id="{element_id}"', html)
```

- [ ] **Step 2: รันเทสต์ให้เห็นว่าล้มเหลว**

Run: `.venv\Scripts\python.exe -m unittest tests.test_web -v`
Expected: FAIL — ไม่พบ `/static/app.js`

- [ ] **Step 3: ผูก asset + เพิ่ม container ใน template**

เพิ่ม `<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">`,
`<script src="{{ url_for('static', filename='app.js') }}" defer></script>`,
`id="submit-btn"` ที่ปุ่ม, container เปล่าสำหรับผล/คำเตือน และ `<noscript>`
แจ้งว่าต้องเปิด JavaScript

- [ ] **Step 4: เขียน `static/app.js`**

- `submit` handler: `preventDefault()` → เคลียร์ error/ผลเดิม → disable ปุ่ม + ข้อความ "กำลังคำนวณ…"
- `fetch('/calculate', {method: 'POST', body: new FormData(form)})` ใน `try/finally` เพื่อ re-enable ปุ่มเสมอ
- `response.ok` → วาด Inputs (normalized), VTH/RTH, Operating Point, badge, warnings
- `!response.ok` → แสดง `errors` ใต้ช่องที่ตรงกัน + summary ที่ `#form-errors`
- `catch` → "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้"
- ตัวจัดรูปแบบ: V ทศนิยม 3 ตำแหน่ง, mA 3, µA 2, kΩ 2; badge class ตาม region
- ห้ามคำนวณ DC bias ใน JS — แสดงค่าที่ได้จาก JSON เท่านั้น

- [ ] **Step 5: เขียน `static/style.css`**

สองคอลัมน์บนจอกว้าง (ฟอร์ม | ผล) และคอลัมน์เดียวต่ำกว่า 800px;
badge สีเขียว/เทา/ส้มตาม region; ใช้ฟอนต์ `Tahoma, "Leelawadee UI", sans-serif`

- [ ] **Step 6: รันเทสต์ให้ผ่าน**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `OK` (14 tests)

- [ ] **Step 7: ตรวจด้วยตาเปล่า (Review Focus ข้อ 3–4)**

Run: `.venv\Scripts\python.exe -m flask --app app run --debug`
ตรวจ: (ก) ค่าตัวอย่าง → เห็นผลครบและ badge เขียว (ข) `beta=-1` → error ใต้ช่อง β
(ค) กด Calculate สองครั้งรัว ๆ → ปุ่มกลับมาใช้งานได้ (ง) กด F5 → ผลเก่าหาย

- [ ] **Step 8: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `feat: render DC bias results without page reload`

---

### Task 8: Documentation + acceptance verification

**Files:**
- Create: `README.md`, `AGENTS.md`, `docs/design-note.md`, `docs/validation.md`,
  `docs/reflection.md`

**Interfaces:**
- Consumes: ทุก task ก่อนหน้า

- [ ] **Step 1: เขียน `README.md`**

ต้องมีคำสั่ง: `python -m venv .venv`, `.venv\Scripts\python.exe -m pip install -r requirements.txt`,
`.venv\Scripts\python.exe -m flask --app app run --debug`, URL
`http://127.0.0.1:5000/`, คำสั่งเทสต์, หมายเหตุว่า debug server ใช้เฉพาะเครื่องตัวเอง

- [ ] **Step 2: เขียน `AGENTS.md`**

กติกา: ห้าม commit แทนนักศึกษา, ห้าม hardcode ผลลัพธ์, ห้ามใส่ secret, รักษาการแยก
`dc_bias.py` (ไม่ import Flask), รันเทสต์ก่อนทุกครั้งที่บอกว่างานเสร็จ

- [ ] **Step 3: เขียน `docs/design-note.md` และ `docs/validation.md`**

design-note: สรุป data flow + เหตุผลการแยกไฟล์
validation: ตารางค่าอ้างอิง spec §10 + วิธีคำนวณอิสระ (สมการ VTH/RTH/IB ไล่ทีละบรรทัด)
+ ผล `unittest` ล่าสุด

- [ ] **Step 4: สร้าง `docs/reflection.md` แบบโครงเปล่า**

ใส่คำถาม 4 ข้อ + หัวข้อ `### คำตอบ` ใต้แต่ละข้อ **ห้ามเขียนคำตอบ** — นักศึกษาเขียนเอง

- [ ] **Step 5: รัน verification เต็มชุด**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
Expected: `Ran 14 tests ... OK`

Run: `.venv\Scripts\python.exe -m flask --app app run --debug`
ตรวจ Acceptance A1–A5 ตาม spec §16 แล้วจดผลลง `docs/validation.md`

- [ ] **Step 6: ตรวจสิ่งที่จะ commit**

Run: `git status --short`
Expected: ไม่มี `.venv/`, `__pycache__/`, `.env`; มีเฉพาะไฟล์โปรเจกต์ + docs

- [ ] **Step 7: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit Summary `docs: add README, validation and reflection template`
แล้วกด **Push origin**; ตรวจว่า Actions/หน้า repo แสดงไฟล์ครบ

---

## Definition of Done

- [ ] `GET /` 200 และมีฟิลด์ครบ 7 ตัว + หน่วย
- [ ] `POST /calculate` คืนค่าตรงค่าอ้างอิง (IC = 1.22986 mA, VCE = 8.05215 V)
- [ ] `VTH ≤ VBE` → `cutoff` + warning; `VCE < 0.3` → `saturation` + warning
- [ ] `beta=-1`, `r1=abc`, `vcc=0`, unit หาย → 400 + `errors` คีย์ถูกต้อง
- [ ] `Ran 14 tests ... OK` (เกินเกณฑ์ขั้นต่ำ 10 tests ของ spec §14)
- [ ] `README.md` ทำให้คนอื่น clone แล้วรันได้
- [ ] `docs/reflection.md` ยังเป็นโครงเปล่า (นักศึกษาเติมเอง)
- [ ] ไม่มี `.venv/` หรือ secret ใน commit
