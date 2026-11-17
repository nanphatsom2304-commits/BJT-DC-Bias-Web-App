# Lab 03 — Three Bias Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่มโหมด Fixed Bias และ Emitter Bias ให้เว็บ Flask ของ Lab 2 โดยคงผล Voltage Divider เดิมไว้ และพิสูจน์ด้วยการกรอกจริงในเบราว์เซอร์ตามตาราง A1–A5

**Architecture:** ฟอร์มยิง `fetch POST /calculate` พร้อม `mode` → `app.py` เลือกฟังก์ชันด้วย `if/elif` → `parse_inputs(raw, mode)` แปลงหน่วย/ตรวจเฉพาะช่องของโหมดนั้น → `calculate_dc_bias` / `calculate_fixed_bias` / `calculate_emitter_bias` (Python ล้วน, SI) → JSON → `app.js` ซ่อนช่องที่ไม่ใช้และวาดผลตามโหมด

**Tech Stack:** Python 3.15.2, Flask 3.1.3, Jinja2, vanilla JS, `unittest`

**Spec:** `docs/superpowers/specs/2026-11-17-lab03-three-bias-modes-design.md`

## Global Constraints

- ใช้ `.venv\Scripts\python.exe` เรียกทุกคำสั่ง (ไม่ต้อง activate)
- JSON ทุกค่าเป็น SI base units (V, A, Ω); การจัดรูปแบบ mA/µA/kΩ เป็นหน้าที่ `app.js`
- `dc_bias.py` ห้าม import Flask/Jinja/HTTP; `app.js` ห้ามคำนวณ DC bias
- คีย์ error = ชื่อฟิลด์ฐาน: `mode, vcc, r1, r2, rc, re, rb, beta, vbe`
- เกณฑ์ region: `IB ≤ 0` → `cutoff`; `VCE ≤ 0.2 V` → `saturation`; นอกนั้น `forward_active`
- `parse_inputs(raw, mode="divider")` — default ต้องทำให้ tests เดิม 16 ตัวผ่านโดยไม่แก้
- โหมดไม่รู้จัก → HTTP 400 + `errors["mode"]` (ห้าม fallback เป็น Divider)
- ค่าอ้างอิง A1–A5 และ tolerance: IC ±0.01 mA, VCE ±0.02 V
- **Agent ห้ามรัน `git add` / `git commit` / `git push`** — ทุก task จบด้วยการส่ง working tree ให้นักศึกษา commit ใน GitHub Desktop
- คำสั่งเทสต์: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
- จำนวน test สุดท้าย: 16 เดิม + 14 ใหม่ = **30**

## Review Focus

1. **สลับโหมดแล้วช่องที่โหมดใหม่ต้องใช้ยังถูก disable อยู่** → FormData ไม่มีค่านั้น → ผู้ใช้เห็น error ทั้งที่กรอกแล้ว (ผิดที่ `data-modes` หรือลำดับ `applyMode()`)
2. **ส่งฟอร์มผิดแล้วยังเห็นผลรอบก่อน** (A5) → ผู้ใช้เข้าใจว่าเป็นผลของค่าที่เพิ่งกรอก
3. **โหมดไม่รู้จัก/ไม่มี `mode` จากแท็บเก่าหรือ client อื่น** → ต้องได้ 400 พร้อม `errors["mode"]` ไม่ใช่ 500 หรือเงียบ ๆ คิดเป็น Divider
4. **Fixed Bias ที่ RB ต่ำมาก/สูงมาก** (เช่น 1 Ω หรือ 1e12 Ω) → ผลต้องยังเป็นจำนวนจริงจำกัดและมี warning ที่เหมาะ ไม่ crash
5. **ตัวเลขที่แสดงถูกปัดจนดูไม่ตรงค่าอ้างอิง** (IC 3 ตำแหน่ง = 1.130 mA) → ต้องผ่าน tolerance ±0.01 mA / ±0.02 V และไม่ปัดจนทิศทาง A3→A4 หาย

---

### Task 1: Mode-aware result + เกณฑ์ region ของ Lab 3

**Files:**
- Modify: `dc_bias.py` (dataclass `DcBiasResult`, `calculate_dc_bias`, `_classify_region`, ค่าคงที่ threshold)
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Produces:
  - `DcBiasResult` มีฟิลด์เพิ่ม `mode: str`, `vth_v: float | None`, `rth_ohm: float | None`
  - `VCE_SATURATION_THRESHOLD_V = 0.2`
  - `_classify_region(ib_a: float, vce_v: float) -> tuple[str, list[str]]`
  - `calculate_dc_bias(inputs)` ยังรับ `DcBiasInputs` เดิม และคืน `mode="divider"`

- [ ] **Step 1: เขียน failing test**

เพิ่มใน `tests/test_dc_bias.py`:
```python
class Lab3RegionTest(unittest.TestCase):
    def test_vce_between_0_2_and_0_3_is_forward_active(self):
        inputs, errors = parse_inputs(dict(RAW, rc="8.55", rc_unit="kohm"))
        self.assertEqual(errors, {})
        result = calculate_dc_bias(inputs)
        self.assertAlmostEqual(result.vce_v, 0.2426, places=3)
        self.assertEqual(result.region, "forward_active")
        self.assertEqual(result.warnings, [])

    def test_cutoff_warning_reports_base_current(self):
        inputs, _ = parse_inputs(dict(RAW, r2="1", r2_unit="kohm"))
        result = calculate_dc_bias(inputs)
        self.assertLessEqual(result.ib_a, 0.0)
        self.assertEqual(result.region, "cutoff")
        self.assertTrue(any("IB" in text for text in result.warnings))
```

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_dc_bias.Lab3RegionTest -v 2>&1"`
Expected: FAIL — test แรกได้ `saturation` (เกณฑ์ 0.3 เดิม), test ที่สอง warning ไม่มีคำว่า `IB`

- [ ] **Step 3: แก้ `dc_bias.py`**

- เปลี่ยน `VCE_SATURATION_THRESHOLD_V = 0.3` → `0.2`
- เพิ่มฟิลด์ `mode: str = "divider"`, `vth_v: float | None`, `rth_ohm: float | None` ใน `DcBiasResult`
  (คงลำดับฟิลด์เดิมไว้ ลดความเสียหายกับผู้เรียก)
- `calculate_dc_bias` ส่ง `mode="divider"` และเรียก `_classify_region(ib, vce)`
- `_classify_region(ib_a, vce_v)`: `ib_a <= 0` → `cutoff` + warning ที่มีคำว่า `IB` และบอกว่าแบบจำลองใช้ไม่ได้;
  `vce_v <= 0.2` → `saturation` + warning ที่ระบุ VCE; มิฉะนั้น `forward_active`, `[]`

- [ ] **Step 4: รันทั้งชุดให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 18 tests ... OK` (16 เดิม + 2 ใหม่; tests เดิมห้ามแก้)

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

Run: `git status --short` (ตรวจว่ามีเฉพาะ `dc_bias.py`, `tests/test_dc_bias.py` ที่เปลี่ยน)
แจ้งนักศึกษา: **ยังไม่ต้อง commit** — Task 1–3 รวมเป็น commit เดียว (`feat: add fixed and emitter bias calculations`)

---

### Task 2: Fixed Bias calculation

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `DcBiasResult` (Task 1)
- Produces:
  - `@dataclass(frozen=True) class FixedBiasInputs(vcc_v, rb_ohm, rc_ohm, beta, vbe_v)` (ทุกฟิลด์ `float`)
  - `calculate_fixed_bias(inputs: FixedBiasInputs) -> DcBiasResult` โดย `mode="fixed"`, `vth_v=None`, `rth_ohm=None`

- [ ] **Step 1: เขียน failing test**

```python
class FixedBiasTest(unittest.TestCase):
    def test_reference_case(self):
        result = calculate_fixed_bias(FixedBiasInputs(
            vcc_v=12.0, rb_ohm=1_000_000.0, rc_ohm=2_200.0,
            beta=100.0, vbe_v=0.70,
        ))
        self.assertEqual(result.mode, "fixed")
        self.assertIsNone(result.vth_v)
        self.assertIsNone(result.rth_ohm)
        self.assertAlmostEqual(result.ib_a * 1e6, 11.3000, places=4)
        self.assertAlmostEqual(result.ic_a * 1e3, 1.13000, places=4)
        self.assertAlmostEqual(result.ie_a * 1e3, 1.14130, places=4)
        self.assertEqual(result.ve_v, 0.0)
        self.assertAlmostEqual(result.vb_v, 0.70000, places=4)
        self.assertAlmostEqual(result.vc_v, 9.51400, places=4)
        self.assertAlmostEqual(result.vce_v, 9.51400, places=4)
        self.assertEqual(result.region, "forward_active")
        self.assertEqual(result.warnings, [])

    def test_extreme_rb_stays_finite(self):
        import math
        for rb in (1.0, 1e12):
            result = calculate_fixed_bias(FixedBiasInputs(
                vcc_v=12.0, rb_ohm=rb, rc_ohm=2_200.0,
                beta=100.0, vbe_v=0.70,
            ))
            for value in (result.ib_a, result.ic_a, result.vce_v):
                self.assertTrue(math.isfinite(value), rb)
```

(เพิ่ม `FixedBiasInputs, calculate_fixed_bias` ใน import ของไฟล์ test)

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_dc_bias.FixedBiasTest -v 2>&1"`
Expected: FAIL — `ImportError: cannot import name 'FixedBiasInputs'`

- [ ] **Step 3: เพิ่ม `FixedBiasInputs` และ `calculate_fixed_bias`**

สมการ: `ib = (vcc − vbe) / rb`; `ic = β·ib`; `ie = (β+1)·ib`; `ve = 0.0`;
`vb = ve + vbe`; `vc = vcc − ic·rc`; `vce = vc − ve`; `vbc = vb − vc`
(from the spec §6.3 — the implementer writes the body)

- [ ] **Step 4: รันให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 20 tests ... OK`

- [ ] **Step 5: ส่งงานให้นักศึกษา commit** — ยังไม่ต้อง commit (รวมใน commit ที่ 1)

---

### Task 3: Emitter Bias calculation

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `DcBiasResult` (Task 1)
- Produces:
  - `@dataclass(frozen=True) class EmitterBiasInputs(vcc_v, rb_ohm, rc_ohm, re_ohm, beta, vbe_v)`
  - `calculate_emitter_bias(inputs: EmitterBiasInputs) -> DcBiasResult` โดย `mode="emitter"`, `vth_v=None`, `rth_ohm=None`

- [ ] **Step 1: เขียน failing tests**

```python
class EmitterBiasTest(unittest.TestCase):
    def test_reference_case(self):
        result = calculate_emitter_bias(EmitterBiasInputs(
            vcc_v=12.0, rb_ohm=1_000_000.0, rc_ohm=2_200.0,
            re_ohm=1_000.0, beta=100.0, vbe_v=0.70,
        ))
        self.assertEqual(result.mode, "emitter")
        self.assertAlmostEqual(result.ib_a * 1e6, 10.2634, places=4)
        self.assertAlmostEqual(result.ic_a * 1e3, 1.02634, places=4)
        self.assertAlmostEqual(result.ie_a * 1e3, 1.03660, places=4)
        self.assertAlmostEqual(result.ve_v, 1.03660, places=4)
        self.assertAlmostEqual(result.vb_v, 1.73660, places=4)
        self.assertAlmostEqual(result.vc_v, 9.74205, places=4)
        self.assertAlmostEqual(result.vce_v, 8.70545, places=4)
        self.assertEqual(result.region, "forward_active")

    def test_bigger_re_lowers_ic(self):
        small = calculate_emitter_bias(EmitterBiasInputs(
            vcc_v=12.0, rb_ohm=1_000_000.0, rc_ohm=2_200.0,
            re_ohm=1_000.0, beta=100.0, vbe_v=0.70,
        ))
        big = calculate_emitter_bias(EmitterBiasInputs(
            vcc_v=12.0, rb_ohm=1_000_000.0, rc_ohm=2_200.0,
            re_ohm=2_000.0, beta=100.0, vbe_v=0.70,
        ))
        self.assertLess(big.ic_a, small.ic_a)
        self.assertAlmostEqual(big.ic_a * 1e3, 0.94010, places=4)
        self.assertAlmostEqual(big.vce_v, 8.03278, places=4)
```

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_dc_bias.EmitterBiasTest -v 2>&1"`
Expected: FAIL — `ImportError: cannot import name 'EmitterBiasInputs'`

- [ ] **Step 3: เพิ่ม `EmitterBiasInputs` และ `calculate_emitter_bias`**

สมการ: `ib = (vcc − vbe) / (rb + (β+1)·re)`; ที่เหลือเหมือน Task 2 แต่ `ve = ie·re`

- [ ] **Step 4: รันให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 22 tests ... OK`

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit ที่ 1 — Summary `feat: add fixed and emitter bias calculations`
ไฟล์: `dc_bias.py`, `tests/test_dc_bias.py`

---

### Task 4: `parse_inputs(raw, mode)` — validation ตามโหมด

**Files:**
- Modify: `dc_bias.py`
- Test: `tests/test_dc_bias.py`

**Interfaces:**
- Consumes: `DcBiasInputs`, `FixedBiasInputs`, `EmitterBiasInputs` (Tasks 1–3)
- Produces:
  `parse_inputs(raw: Mapping[str, str], mode: str = "divider") -> tuple[DcBiasInputs | FixedBiasInputs | EmitterBiasInputs | None, dict[str, str]]`
- ฟิลด์ต่อโหมด: divider → `r1, r2, re`; fixed → `rb`; emitter → `rb, re`; ร่วมทุกโหมด → `vcc, rc, beta, vbe`
- หน่วย: `<field>_unit` ∈ {`ohm`, `kohm`}; เพิ่ม `rb_unit`

- [ ] **Step 1: เขียน failing tests**

```python
class ModeParsingTest(unittest.TestCase):
    FIXED = {"mode": "fixed", "vcc": "12", "rc": "2.2", "rc_unit": "kohm",
             "rb": "1000", "rb_unit": "kohm", "beta": "100", "vbe": "0.7"}
    EMITTER = dict(FIXED, mode="emitter", re="1", re_unit="kohm")

    def test_fixed_ignores_divider_fields(self):
        raw = dict(self.FIXED, r1="abc", r2="", re="oops", r1_unit="M")
        inputs, errors = parse_inputs(raw, "fixed")
        self.assertEqual(errors, {})
        self.assertIsInstance(inputs, FixedBiasInputs)
        self.assertEqual(inputs.rb_ohm, 1_000_000.0)

    def test_fixed_requires_rb(self):
        raw = dict(self.FIXED)
        del raw["rb"]
        inputs, errors = parse_inputs(raw, "fixed")
        self.assertIsNone(inputs)
        self.assertIn("rb", errors)

    def test_emitter_requires_re(self):
        raw = dict(self.EMITTER)
        del raw["re"]
        inputs, errors = parse_inputs(raw, "emitter")
        self.assertIsNone(inputs)
        self.assertIn("re", errors)

    def test_unknown_mode_is_rejected(self):
        inputs, errors = parse_inputs(dict(self.FIXED, mode="bridge"), "bridge")
        self.assertIsNone(inputs)
        self.assertIn("mode", errors)
```

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_dc_bias.ModeParsingTest -v 2>&1"`
Expected: FAIL — `TypeError: parse_inputs() takes 1 positional argument but 2 were given`

- [ ] **Step 3: แก้ `parse_inputs`**

- เพิ่มพารามิเตอร์ `mode: str = "divider"`; ถ้า `mode` ไม่อยู่ใน `{"divider", "fixed", "emitter"}` →
  `return None, {"mode": "โหมดไม่รู้จัก: ..."}` **ก่อน** parse ฟิลด์ใด ๆ
- ดึงรายการตัวต้านทานที่ต้องใช้ตามโหมด แล้ว reuse `_parse_number` + กติกาเดิม (finite, > 0, หน่วยถูก)
- ฟิลด์ที่ไม่เกี่ยว: ไม่เรียก `_parse_number`, ไม่ตรวจ `_unit` → ไม่เกิด error
- ประกอบ dataclass ตามโหมด (divider คงพฤติกรรมเดิมทุกอย่าง)
- ข้อความ error ภาษาไทยใช้รูปแบบเดิม (`กรุณากรอก RB`, `RB ต้องมากกว่า 0 Ω`, `หน่วยของ RB ต้องเป็น ohm หรือ kohm`)

- [ ] **Step 4: รันทั้งชุดให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 26 tests ... OK` (16 เดิม + 2 + 2 + 2 + 4)

- [ ] **Step 5: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit ที่ 1 ยังไม่ต้องกด — Task 5 ต่อใน commit ที่ 2

---

### Task 5: `app.py` — mode dispatch + serialization

**Files:**
- Modify: `app.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `parse_inputs(raw, mode)`, `calculate_fixed_bias`, `calculate_emitter_bias` (Tasks 3–4)
- Produces: `POST /calculate` รับ `mode` ใน FormData; success body มี `data.mode`, `data.inputs_si` ตามโหมด,
  `data.intermediate` = `{}` เมื่อไม่มี VTH/RTH; error body มี `mode` echo กลับ

- [ ] **Step 1: เขียน failing tests**

```python
class CalculateModeTest(unittest.TestCase):
    FIXED = {"mode": "fixed", "vcc": "12", "rc": "2.2", "rc_unit": "kohm",
             "rb": "1000", "rb_unit": "kohm", "beta": "100", "vbe": "0.7"}

    def setUp(self):
        self.client = app.test_client()

    def test_post_fixed_returns_mode_and_values(self):
        response = self.client.post("/calculate", data=self.FIXED)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
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
```

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_web.CalculateModeTest -v 2>&1"`
Expected: FAIL — fixed ได้ `200` แต่ `data.mode` ไม่มี (`KeyError`) และ unknown mode คืน 400 ที่ `errors` ไม่มี `mode`

- [ ] **Step 3: แก้ `app.py`**

- อ่าน `mode = (request.form.get("mode") or "divider").strip().lower()`
- เรียก `parse_inputs(request.form, mode)`; ถ้า error → 400 พร้อม `{"ok": False, "mode": mode, "errors": errors, "message": ...}`
- `if mode == "divider"` / `elif "fixed"` / `elif "emitter"` / `else` → 400 defensive
- `_serialize`: เพิ่ม `"mode": result.mode`; สร้าง `inputs_si` ตามชนิด (`FixedBiasInputs` → `rb_ohm`;
  `EmitterBiasInputs` → `rb_ohm` + `re_ohm`; divider → ฟิลด์เดิมทั้ง 7)
- `intermediate`: มี `vth_v`/`rth_ohm` เฉพาะเมื่อไม่เป็น `None` มิฉะนั้น `{}`

- [ ] **Step 4: รันทั้งชุดให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 29 tests ... OK`

- [ ] **Step 5: ตรวจ API ด้วยมือ (ยังไม่รันเบราว์เซอร์)**

> ใช้ตรวจสัญญา JSON เท่านั้น — **ไม่ใช่หลักฐาน A1–A5** (ใบงานห้ามใช้ curl แทนการรันเบราว์เซอร์)

Run (PowerShell, เซิร์ฟเวอร์รันอยู่ที่พอร์ต 5000):
`curl.exe -s -X POST http://127.0.0.1:5000/calculate -d "mode=fixed&vcc=12&rc=2.2&rc_unit=kohm&rb=1000&rb_unit=kohm&beta=100&vbe=0.7"`
Expected: `"mode":"fixed"`, `"ic_a":0.00113`, `"vce_v":9.514`, `"intermediate":{}`

- [ ] **Step 6: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit ที่ 2 — Summary `feat: select bias mode in the calculate API`
ไฟล์: `app.py`, `tests/test_web.py` (+ `dc_bias.py`, `tests/test_dc_bias.py` ถ้ายังไม่ commit รอบแรก)

---

### Task 6: ฟอร์มเลือกโหมด + ผลตามโหมด

**Files:**
- Modify: `templates/index.html`, `static/app.js`, `static/style.css`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: JSON ตาม Task 5 (`data.mode`, `data.intermediate`, `data.operating_point`, `data.inputs_si`)
- Produces: DOM ids `mode`, `rb`, `rb_unit`, `result-mode`; ทุก `.field` มี `data-modes` (ค่าคั่นด้วยช่องว่าง)

- [ ] **Step 1: เขียน failing test**

```python
    def test_index_has_mode_selector_and_rb_field(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('name="mode"', html)
        self.assertIn('id="mode"', html)
        self.assertIn('name="rb"', html)
        self.assertIn('name="rb_unit"', html)
        self.assertIn('id="result-mode"', html)
        self.assertIn('data-modes="divider"', html)
        self.assertIn('data-modes="fixed emitter"', html)
```

- [ ] **Step 2: รันให้เห็นว่าล้มเหลว**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest tests.test_web.IndexPageTest -v 2>&1"`
Expected: FAIL — ไม่พบ `name="mode"`

- [ ] **Step 3: แก้ `templates/index.html`**

- เพิ่มใน `<form>` ก่อนช่อง VCC:
  `<div class="field"><label for="mode">โหมดไบอัส</label><select id="mode" name="mode">` + 3 `<option>`
  (`divider` = Voltage Divider Bias, `fixed` = Fixed Bias, `emitter` = Emitter Bias)
- ใส่ `data-modes` ให้ทุก `.field`: `vcc`/`rc`/`beta`/`vbe` = `"divider fixed emitter"`;
  `r1`,`r2` = `"divider"`; `re` = `"divider emitter"`; `rb` ใหม่ = `"fixed emitter"`
- ช่อง `rb`: `<input id="rb" name="rb" ...>` + `<select name="rb_unit">` (kΩ/Ω) ใน `.input-row` เดิม
- เพิ่ม `<p id="result-mode" class="result-mode" hidden></p>` ใน `#results` ก่อน `#region-badge`
- ปรับ subtitle ใน header เป็น "Voltage Divider · Fixed · Emitter Bias"

- [ ] **Step 4: แก้ `static/app.js`**

- `const modeSelect = document.getElementById("mode"); const resultMode = document.getElementById("result-mode");`
- `MODE_LABELS = { divider: "Voltage Divider Bias", fixed: "Fixed Bias", emitter: "Emitter Bias" }`
- `applyMode()`: วน `.field[data-modes]` → `field.hidden = !modes.includes(modeSelect.value)`;
  ตั้ง `disabled` ให้ input/select ข้างในเท่ากับ `field.hidden`; อัปเดตข้อความ placeholder
- `modeSelect.addEventListener("change", ...)` → `applyMode(); resetMessages();`
- เรียก `applyMode()` ตอนสคริปต์เริ่มทำงาน
- `render(data)`: ตั้ง `resultMode.textContent = "โหมด: " + MODE_LABELS[data.mode]`, `hidden=false`
- ตาราง Inputs: สร้างแถวตามโหมด (`rb` เมื่อมี, `r1/r2` เฉพาะ divider, `re` เมื่อมี)
- ตาราง Intermediate: แสดงเฉพาะเมื่อ `data.intermediate.vth_v != null`
- `showErrors(errors, message, mode)`: รับ `mode` เพิ่ม และเรียกจาก submit handler เป็น
  `showErrors(body.errors || {}, body.message, body.mode)`; ถ้ามี `mode` ให้เติมหัวข้อ `โหมด: ...`
  ใน summary (ถ้า `mode` ไม่รู้จักให้แสดงค่าดิบ)

- [ ] **Step 5: เพิ่ม CSS เล็กน้อยใน `static/style.css`**

`.result-mode { font-weight: 700; color: #155a78; margin: 0 0 8px; }`

- [ ] **Step 6: รันทั้งชุดให้ผ่าน**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 30 tests ... OK`

- [ ] **Step 7: ตรวจด้วยตาในเบราว์เซอร์จริง**

เปิด `http://127.0.0.1:5000/` แล้วตรวจ:
(ก) โหมดเริ่มต้น Divider → เห็น R1/R2/RE, ไม่เห็น RB
(ข) เปลี่ยนเป็น Fixed → RB ปรากฏ, R1/R2/RE หายและ disabled, ผล/error เก่าถูกเคลียร์
(ค) Fixed RB 1000 kΩ → IC 1.130 mA, VCE 9.514 V, ไม่มี warning
(ง) เปลี่ยนเป็น Emitter RE 1 → 2 kΩ แล้วคำนวณซ้ำ → IC ลดจาก 1.026 เป็น 0.940 mA

- [ ] **Step 8: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit ที่ 3 — Summary `feat: choose bias mode in the form`
ไฟล์: `templates/index.html`, `static/app.js`, `static/style.css`

---

### Task 7: เอกสาร + หลักฐาน A1–A5

**Files:**
- Modify: `README.md`, `docs/validation.md`, `docs/design-note.md`
- Create: `docs/evidence/a1-divider.png`, `docs/evidence/a5-fixed-invalid.png`

**Interfaces:**
- Consumes: แอปที่ทำงานครบ 3 โหมด (Tasks 1–6)

- [ ] **Step 1: อัปเดต `README.md`**

- ระบุ 3 โหมด + ค่าอินพุตที่แต่ละโหมดใช้
- ตัวอย่างกรอกสำหรับ A1–A4 พร้อมค่าที่ควรได้
- หัวข้อ "AI ช่วยส่วนไหน / นักศึกษาตรวจอะไร" (สมการ, หน่วย, เกณฑ์ warning, ผล A1)
- เปลี่ยนคำอธิบาย region จาก `VCE < 0.3 V`/`VTH ≤ VBE` เป็น `IB ≤ 0`/`VCE ≤ 0.2 V`
- อัปเดตจำนวน test เป็น 30

- [ ] **Step 2: เขียน `docs/validation.md` ใหม่ตามโครงใน spec §11**

1) Lab 3 — ตาราง A1–A5 (คอลัมน์: กรณี, อินพุต, คาดหมาย, เห็นจริง, วิธีตรวจ, สถานะ)
2) ค่าอ้างอิงอิสระ: คำนวณมือ A2 และ A3 ทีละบรรทัด (IB → IC → VE → VB → VC → VCE)
3) วิธีตรวจ: `OpenCode Browser tools` (เปิดเว็บ/กรอก/อ่าน snapshot) + หลักฐาน 2 รูป
4) ผล `unittest` ล่าสุด
5) ภาคผนวก: ตาราง A1–A7 ของ Lab 2 (คงไว้เป็นประวัติ)

- [ ] **Step 3: อัปเดต `docs/design-note.md`**

เพิ่ม data flow ที่มี `mode` → `if/elif` → ฟังก์ชันตามโหมด และอธิบายว่าทำไมเกณฑ์ warning เปลี่ยน

- [ ] **Step 4: เก็บหลักฐานจากเบราว์เซอร์**

รัน A1–A5 ตามตาราง (โหมด/ค่า/ปุ่มจริง) แล้ว
- คัดลอก screenshot A1 และ A5 ไปที่ `docs/evidence/`
- บันทึกค่าที่เห็นจริงลงตาราง (ห้ามใช้ค่าจากโค้ดเป็นค่าอ้างอิง)

- [ ] **Step 5: รัน verification เต็มชุด**

Run: `cmd /c ".venv\Scripts\python.exe -m unittest discover -s tests -v 2>&1"`
Expected: `Ran 30 tests ... OK`

Run: `git status --short`
Expected: ไม่มี `.venv/`, `__pycache__/`, `.env`, `.superpowers/`

- [ ] **Step 6: ส่งงานให้นักศึกษา commit**

แจ้งนักศึกษา: commit ที่ 4 — Summary `docs: add lab 3 acceptance results and references`
ไฟล์: `README.md`, `docs/` (ยกเว้น `docs/superpowers/` ถ้าไม่ต้องการให้ขึ้น GitHub)
แล้ว Push origin

---

## Definition of Done

- [ ] `GET /` 200 และมี dropdown โหมด + ช่อง RB
- [ ] A1 Divider: IC 1.22986 mA, VCE 8.05216 V (เท่า Lab 2)
- [ ] A2 Fixed: IC 1.13000 mA, VCE 9.51400 V, VE = 0
- [ ] A3 Emitter: IC 1.02634 mA, VCE 8.70545 V
- [ ] A4 Emitter RE 2 kΩ: IC 0.94010 mA (ลดลงจาก A3)
- [ ] A5 Fixed RB = 0: 400 + ข้อความให้แก้ RB, ไม่มีผลค้าง
- [ ] `mode` ไม่รู้จัก → 400 + `errors["mode"]`
- [ ] `Ran 30 tests ... OK`
- [ ] `docs/validation.md` มีตาราง A1–A5 + หลักฐาน + ค่าอ้างอิงอิสระ
- [ ] `docs/reflection.md` ไม่ถูกแก้ (นักศึกษาเขียนเอง)
- [ ] ไม่มี `.venv/`, `.env`, secret ใน commit
