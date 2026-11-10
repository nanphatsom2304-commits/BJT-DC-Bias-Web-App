# BJT Common-Emitter DC Bias Web App — Design

**Version:** 1.0 · **Date:** 2026-11-10
**Course:** ENG29 2121 Computer Programming for Electrical Engineers (2/2569)
**Lab:** 02 — First DC Bias Web App

## 1. Intent and Why

นักศึกษาต้องส่ง Flask Web Application หลายไฟล์ที่รับค่าอุปกรณ์ของวงจร NPN Common
Emitter แบบ Voltage-Divider Bias แล้วให้ **Python Backend คำนวณ DC Operating
Point จริง** (ไม่ใช่ค่าคงที่ใน HTML) พร้อม Validation, Region Warning, Automated
Tests และประวัติ Git ผ่าน GitHub Desktop

เหตุผลเชิงการเรียนรู้: ให้เห็นว่าไฟล์ `.html` เป็นเพียง Template ที่ Server ส่งมา
ไม่ใช่ตัวโปรแกรมคำนวณ, และให้แยก "สมการวิศวกรรม" ออกจาก "HTTP/UI" ได้

## 2. Goals

- G1: เปิดผ่าน `http://127.0.0.1:5000/` ได้จริง และแสดงฟอร์มกรอกค่า 7 ตัว
- G2: `POST /calculate` คำนวณใน Python แล้วตอบ JSON; หน้าเว็บแสดงผลโดยไม่ reload
- G3: แสดงผลละเอียดครบ: `VTH, RTH, IB, IC, IE, VB, VE, VC, VCE, VBC` + Region
- G4: Validation ฝั่ง Server ครบ (ค่าผิด/หาย/ไม่ใช่ตัวเลข) และแจ้ง error รายช่อง
- G5: Warning เมื่อแบบจำลอง forward-active ใช้ไม่ได้ (Cutoff / Saturation)
- G6: Automated Tests: ≥3 unit tests ของสมการ + ≥1 Flask test client test
- G7: README ที่ทำให้ clone แล้วรันได้, .gitignore กัน `.venv/` หลุดเข้า commit

## 3. Non-Goals

- AC small-signal, gain, Bode plot, transient, signal generator
- Bias type อื่น (Fixed, Emitter bias), FET, SPICE/ngspice
- Interactive schematic editor, DC/AC overlay animation
- ระบบ login, ฐานข้อมูล, deploy ขึ้น cloud
- รองรับหน่วยอื่นนอกจาก Ω/kΩ และ V

## 4. Anti-Goals (ถือว่าล้มเหลวแม้โปรแกรมรันได้)

- ตัวเลขผลลัพธ์ถูก hardcode ใน HTML/JS แทนการคำนวณจาก backend
- เปิดด้วย `file://` แล้วใช้งานได้ (โปรแกรมต้องพึ่ง Flask server)
- แสดงผลใน Region ที่แบบจำลองใช้ไม่ได้ โดยไม่มี warning
- Test ที่ผ่านเพราะ assert ค่าที่เขียนตามผลลัพธ์จริง (ไม่มีค่าอ้างอิงอิสระ)
- Commit ไฟล์ `.venv/`, `__pycache__/`, `.env` หรือ credential ใด ๆ

## 5. Constraints

- Python 3.15.2 (64-bit) บน Windows, ใช้ `venv`
- Flask 3.x + Jinja2, ไม่ใช้ CSS framework ภายนอก (ต้องรันได้แบบ offline)
- เทสต์ใช้ `unittest` ตามคำสั่งในเอกสาร: `python -m unittest discover -s tests -v`
- โฟลเดอร์โปรเจกต์: `C:\Users\B6809157\Documents\GitHub\BJT DC Bias Web App`
- **ห้าม agent รัน `git commit` / `git push`** — นักศึกษา commit ผ่าน GitHub Desktop เท่านั้น
- Repo ยังไม่มี remote; นักศึกษากด Publish repository ก่อน push ครั้งแรก

## 6. Approaches Considered

| # | แนวทาง | Trade-off | ผล |
|---|--------|-----------|-----|
| 1 | Server-rendered POST + Jinja | ชิ้นส่วนน้อย เทสต์ง่าย แต่หน้าจอ reload ทุกครั้ง | ไม่เลือก |
| 2 | **JSON API + `fetch()`** | โค้ดเพิ่ม (JS + JSON contract) แต่แสดงผลได้ละเอียด ไม่ reload และต่อยอด AC/knob ได้ | **เลือก** |
| 3 | คำนวณใน JavaScript ล้วน | ขัดเงื่อนไข Lab ที่บังคับ Python backend | ตัดทิ้ง |

**เหตุผลที่เลือก 2:** นักศึกษาต้องการผลลัพธ์ที่แสดงได้ละเอียดครบถ้วนและปรับปรุง
หน้าจอได้ยืดหยุ่นกว่า; API แยกสัญญาข้อมูลชัดเจน ทำให้เทสต์ backend ได้ตรงไปตรงมา
และเป็นฐานที่ดีสำหรับ Lab สัปดาห์ถัดไป

## 7. Architecture

```
BJT DC Bias Web App/
├── app.py                  # Flask routes: GET /, POST /calculate
├── dc_bias.py              # pure engineering logic (ไม่ import flask)
├── templates/index.html    # ฟอร์ม + containers สำหรับผล/error (Jinja)
├── static/style.css        # layout, responsive, region badge
├── static/app.js           # fetch → render ผล/error, loading state
├── tests/
│   ├── test_dc_bias.py     # สมการ, unit conversion, region, validation
│   └── test_web.py         # GET /, POST /calculate (Flask test client)
├── requirements.txt
├── README.md
├── AGENTS.md
├── .gitignore
└── docs/
    ├── design-note.md
    ├── validation.md
    └── reflection.md
```

**Data flow:** Browser form → `fetch('/calculate')` → Flask route → validate →
`dc_bias.calculate_dc_bias()` → JSON response → JS render (ไม่ reload)

**Public API ของ `dc_bias.py`** (Flask-free — เทสต์ได้โดยไม่ต้องมี Flask)

```python
@dataclass(frozen=True)
class DcBiasInputs:          # ค่า SI ทั้งหมด
    vcc_v: float; r1_ohm: float; r2_ohm: float
    rc_ohm: float; re_ohm: float; beta: float; vbe_v: float

@dataclass(frozen=True)
class DcBiasResult:
    inputs_si: DcBiasInputs
    vth_v: float; rth_ohm: float
    ib_a: float; ic_a: float; ie_a: float
    vb_v: float; ve_v: float; vc_v: float; vce_v: float; vbc_v: float
    region: str              # "forward_active" | "cutoff" | "saturation"
    warnings: list[str]

def parse_inputs(raw: Mapping[str, str]) -> tuple[DcBiasInputs | None, dict[str, str]]:
    """ค่าดิบจากฟอร์ม (string) → แปลงหน่วยเป็น SI + validate; คืน (inputs, errors)"""

def calculate_dc_bias(inputs: DcBiasInputs) -> DcBiasResult:
    """คำนวณตาม §10 + ตัดสิน region/warnings ตาม §12; ไม่ raise สำหรับค่าที่ผ่าน parse_inputs"""
```

**Layering rules**
- `dc_bias.py` ไม่ import Flask/Jinja/HTTP; รับ/คืนเฉพาะ SI + ผลลัพธ์ (§9)
- `app.py` ทำ HTTP เท่านั้น: `request.form` → `parse_inputs()` → `calculate_dc_bias()` → `jsonify`
- `templates/index.html` ไม่มีสมการฟิสิกส์ และไม่ hardcode ผลลัพธ์
- `static/app.js` แสดงผล/error เท่านั้น ไม่คำนวณ DC bias

## 8. Input Contract

ฟอร์มใช้ **ช่องตัวเลข + dropdown หน่วยต่อช่อง** (ตัดสินใจร่วมกับนักศึกษา)

| Field | ชนิด | หน่วยที่เลือกได้ | ตัวอย่าง |
|-------|------|------------------|----------|
| `vcc` | number | V | 12 |
| `r1`, `r2`, `rc`, `re` | number | `ohm` / `kohm` | 100 + kohm |
| `beta` | number | – (unitless) | 100 |
| `vbe` | number | V | 0.70 |

`POST /calculate` รับ `application/x-www-form-urlencoded` (FormData) โดยมีฟิลด์
`<name>` และ `<name>_unit` สำหรับ R1/R2/RC/RE:

```
vcc=12&r1=100&r1_unit=kohm&r2=22&r2_unit=kohm&rc=2.2&rc_unit=kohm
&re=1&re_unit=kohm&beta=100&vbe=0.7
```

## 9. JSON Response Contract

**สำเร็จ (HTTP 200)**

```json
{
  "ok": true,
  "data": {
    "inputs_si": {
      "vcc_v": 12.0, "r1_ohm": 100000.0, "r2_ohm": 22000.0,
      "rc_ohm": 2200.0, "re_ohm": 1000.0, "beta": 100.0, "vbe_v": 0.7
    },
    "intermediate": { "vth_v": 2.1639, "rth_ohm": 18032.8 },
    "operating_point": {
      "ib_a": 1.22986e-05, "ic_a": 0.0012299, "ie_a": 0.0012422,
      "vb_v": 1.9422, "ve_v": 1.2422, "vc_v": 9.2943,
      "vce_v": 8.0522, "vbc_v": -7.3521
    },
    "region": "forward_active",
    "warnings": []
  }
}
```

**ผิดพลาด (HTTP 400)**

```json
{
  "ok": false,
  "errors": {
    "r1": "R1 ต้องมากกว่า 0 Ω",
    "beta": "β ต้องเป็นตัวเลขและมากกว่า 0"
  },
  "message": "กรุณาตรวจสอบค่าที่ป้อน"
}
```

- ค่าทั้งหมดใน JSON เป็น **SI base units** (V, A, Ω); การจัดรูปแบบ (mA, µA, kΩ)
  เป็นหน้าที่ของ `app.js`
- `region` ∈ `forward_active` | `cutoff` | `saturation`
- `warnings` เป็น array ของข้อความภาษาไทย; ว่างเมื่ออยู่ใน forward-active
- **คีย์ของ `errors` ใช้ชื่อฟิลด์ฐานเสมอ** (`vcc`, `r1`, `r2`, `rc`, `re`, `beta`,
  `vbe`) แม้ต้นเหตุจะอยู่ที่หน่วย (`*_unit` หาย/ไม่รู้จัก) — UI จึงมีช่อง error
  หนึ่งช่องต่อหนึ่งแถว และเทสต์ตรวจคีย์ได้ตรงไปตรงมา

## 10. Engineering Model (Forward-Active Approximation)

```
VTH = VCC · R2 / (R1 + R2)
RTH = R1 · R2 / (R1 + R2)
IB  = (VTH − VBE) / (RTH + (β + 1)·RE)
IC  = β · IB
IE  = (β + 1) · IB
VE  = IE · RE
VB  = VE + VBE
VC  = VCC − IC · RC
VCE = VC − VE
VBC = VB − VC
```

**ค่าอ้างอิงสำหรับตรวจรับ** (VCC=12 V, R1=100 kΩ, R2=22 kΩ, RC=2.2 kΩ,
RE=1 kΩ, β=100, VBE=0.70 V)

| ปริมาณ | ค่า |
|--------|-----|
| VTH | 2.1639 V |
| RTH | 18.0328 kΩ |
| IB | 12.299 µA |
| IC | 1.2299 mA |
| IE | 1.2422 mA |
| VB | 1.9422 V |
| VE | 1.2422 V |
| VC | 9.2943 V |
| VCE | 8.0522 V |
| VBC | −7.3521 V |

Cross-check อิสระ: `VTH − IB·RTH = 1.9422 V` ต้องเท่ากับ `VE + VBE`

## 11. Validation Rules (Server เป็นผู้ตัดสิน)

| เงื่อนไข | ผล |
|----------|-----|
| ฟิลด์หาย / ว่าง | error รายฟิลด์ "กรุณากรอกค่านี้" |
| แปลงเป็นตัวเลขไม่ได้ | error "ต้องเป็นตัวเลข" |
| R1, R2, RC, RE ≤ 0 | error "ต้องมากกว่า 0 Ω" |
| VCC ≤ 0 | error "VCC ต้องมากกว่า 0 V" |
| β ≤ 0 | error "β ต้องมากกว่า 0" |
| VBE < 0 หรือ VBE > 2 V | error "VBE ต้องอยู่ระหว่าง 0 ถึง 2 V" |
| หน่วยของ R ไม่ใช่ `ohm`/`kohm` | error "หน่วยไม่ถูกต้อง" |
| ค่าที่ไม่ใช่จำนวนจริง (nan/inf) | error "ต้องเป็นจำนวนจริง" |

UI ใช้ `type="number"` + `min` เป็นเพียงตัวช่วย; **ห้ามพึ่ง HTML validation
เพียงอย่างเดียว** เพราะ acceptance test ยิง HTTP ตรง

> ไม่มีสคริปต์ตรวจรับภายนอกใน repo — **เอกสารนี้คือสัญญาเดียว** ที่ใช้ตัดสิน
> (status code, ชื่อคีย์ `errors`, รูปแบบ body `application/x-www-form-urlencoded`)

## 12. Region Logic and Warnings

1. ถ้า `VTH ≤ VBE` → `region = "cutoff"`; warning:
   "VTH (…) ≤ VBE (…) — ทรานซิสเตอร์ไม่อยู่ใน Forward-Active; ค่าที่คำนวณจาก
   สมการนี้ใช้ไม่ได้" และยังคืนค่าตัวเลขที่คำนวณได้พร้อมป้ายกำกับว่าไม่น่าเชื่อถือ
2. มิฉะนั้นถ้า `VCE < 0.3 V` → `region = "saturation"`; warning:
   "VCE (…) < 0.3 V — ใกล้/อยู่ใน Saturation; forward-active approximation
   ไม่แม่นยำ"
3. มิฉะนั้น → `region = "forward_active"`; `warnings = []`

`VCE < 0` ให้ถือเป็น saturation และ warning เดียวกัน (ไม่ crash)

## 13. UI Behavior (templates + static)

- `GET /` แสดงฟอร์ม 7 ช่อง; ค่าเริ่มต้นว่าง (ไม่ pre-fill คำตอบ)
- กด **Calculate DC Bias** → `fetch('/calculate', {method:'POST', body:FormData})`
- ระหว่างรอ: ปุ่ม disabled + ข้อความ "กำลังคำนวณ…"
- สำเร็จ: แสดง
  - **Inputs (normalized)** — ค่าที่แปลงเป็น Ω/V แล้ว เพื่อตรวจการแปลงหน่วย
  - **Intermediate** — VTH, RTH
  - **Operating Point** — IB, IC, IE, VB, VE, VC, VCE, VBC พร้อมหน่วย
  - **Region badge** — Forward-Active (เขียว) / Cutoff (เทา) / Saturation (ส้ม)
  - **Warnings** — กล่องเตือนใต้ badge
- ผิดพลาด: แสดงข้อความใต้ช่องที่ผิด + สรุปด้านบน; ไม่ลบค่าที่ผู้ใช้พิมพ์
- เครือข่ายล่ม/JSON ผิดรูป: แสดง "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้" (ไม่ throw เงียบ)
- `<noscript>` แจ้งว่าต้องเปิด JavaScript (Lab นี้ไม่ทำ no-JS fallback)

## 14. Tests

**`tests/test_dc_bias.py`** (pure logic, ไม่ต้องมี Flask)
1. `test_reference_case_matches_independent_calculation` — ตรวจครบทุกค่าตาม §10 (rtol 1e-3)
2. `test_ohm_and_kohm_inputs_give_same_result` — แปลงหน่วยแล้วผลตรงกัน
3. `test_cutoff_when_vth_not_above_vbe` — R1/R2 ทำให้ VTH ≤ VBE → `cutoff` + warning
4. `test_saturation_when_vce_below_threshold` — เลือก RC ให้ VCE < 0.3 V → `saturation`
5. `test_rejects_nonpositive_resistance_beta_vcc`
6. `test_rejects_nonnumeric_and_missing_fields`

**`tests/test_web.py`** (Flask test client)
7. `test_get_index_returns_200_with_all_input_fields`
8. `test_post_calculate_returns_json_reference_case` — ตรวจ `ok`, `region`, ค่า IC/VCE
9. `test_post_calculate_returns_400_with_field_errors` — `beta=-1` และ `r1=abc`
10. `test_post_calculate_cutoff_includes_warning`

**หลักฐาน A3:** ค่าอ้างอิงใน §10 คำนวณแยกด้วยมือ/สคริปต์นอกโปรเจกต์
(บันทึกวิธีไว้ใน `docs/validation.md`) ไม่ได้คัดลอกจาก output ของแอป

> ตัวเลข 6 + 4 ข้างต้นเป็น **เกณฑ์ขั้นต่ำ**; implementation plan เพิ่มอีก 4 tests
> (deep saturation, extreme-value finite guard, unit หาย/ผิด, static asset wiring)
> รวมเป็น 14 tests

## 15. Deliverable Documentation

- `README.md` — วิธีติดตั้ง venv, `pip install -r requirements.txt`,
  `python -m flask --app app run --debug`, `python -m unittest discover -s tests -v`,
  port 5000, หมายเหตุว่า Flask debug server ใช้เฉพาะเครื่องตัวเอง
- `docs/design-note.md` — สรุปสถาปัตยกรรมและเหตุผลการแยกไฟล์
- `docs/validation.md` — ตารางค่าอ้างอิง + วิธีคำนวณอิสระ + ผลทดสอบ
- `docs/reflection.md` — โครงคำถามรายบุคคล 4 ข้อท้ายเอกสาร Lab พร้อมหัวข้อ
  และคำใบ้ว่าคำตอบควรแตะประเด็นใด **แต่ไม่มีคำตอบสำเร็จรูป**; นักศึกษาเขียนเอง
  ทั้งหมด (งานประเมินรายบุคคล) — คำถาม: (1) ทำไมเปิด `templates/index.html`
  ตรง ๆ จึงไม่เท่ากับรัน Flask (2) ฟอร์มส่งข้อมูลไป Python อย่างไร
  (3) แก้สมการใน `dc_bias.py` แล้วต้องแก้ HTML หรือไม่ (4) ทำไม Region ที่
  แบบจำลองใช้ไม่ได้จึงต้องมี Warning
- `AGENTS.md` — กติกา: ห้าม commit แทนนักศึกษา, ห้าม hardcode ผล, ห้ามใส่ secret

## 16. Acceptance Mapping

| ข้อ | สิ่งที่ทำให้ผ่าน |
|-----|------------------|
| A1 GET / | route คืน 200 + template มี input ครบ 7 ตัว |
| A2 POST /calculate | คำนวณใน `dc_bias.py` แล้วคืน JSON; JS render |
| A3 Reference | unit test ข้อ 1–2 เทียบ §10 |
| A4 Validation | 400 + `errors` รายฟิลด์ (คีย์ = ชื่อฟิลด์ฐาน); UI แสดงโดยไม่ล้ม |
| A5 Region | `cutoff`/`saturation` + warnings (§12) |
| A6 Tests | 6 engineering + 4 web tests (§14) |
| A7 Reproducibility | README + requirements.txt + .gitignore |

## 17. Left to the Builder

- รายละเอียด CSS: สี, ระยะห่าง, ฟอนต์ (ใช้ Tahoma/Leelawadee UI ให้เข้ากับเอกสาร Lab)
- ถ้อยคำภาษาไทยของ label/ข้อความ warning นอกเหนือจากที่ระบุใน §11–§13
- ลำดับการ์ดผลลัพธ์บนหน้าจอ และการจัดวางสองคอลัมน์/คอลัมน์เดียวบนมือถือ
- จำนวนตำแหน่งทศนิยมในการแสดงผล (แนะนำ V = 3 ตำแหน่ง, mA = 3, µA = 2, kΩ = 2)
- โครงสร้าง HTML ภายในของการ์ดแต่ละใบ

## 18. Definition of Done

1. `python -m flask --app app run --debug` เปิดเว็บได้ และคำนวณค่าตัวอย่างถูกต้อง
2. `python -m unittest discover -s tests -v` ผ่านทั้งหมด (10 tests)
3. กรอกค่าผิดเห็น error; กรอกค่า cutoff/saturation เห็น warning
4. นักศึกษา commit + push ผ่าน GitHub Desktop สำเร็จ และ README รันซ้ำได้
5. ไม่มี `.venv/`, `__pycache__/`, secret ใน commit
6. `docs/reflection.md` ถูกเติมคำตอบโดยนักศึกษาเอง (agent ห้ามเขียนคำตอบ)
