# Lab 03 — Three Bias Modes (Fixed / Emitter / Divider) — Design

Date: 2026-11-17
Base: `feature/lab02-dc-bias` @ `8800360` (Lab 2 web app, 16 tests green)
Brief: `ENG29_2121_Lab03_BJT_Bias_Web_App.html` (instructor draft)

## 1. Intent

ต่อยอดเว็บ Flask จาก Lab 2 ให้เลือกวงจรไบอัสได้ 3 แบบ (Voltage Divider เดิม, Fixed Bias,
Emitter Bias แหล่งจ่ายเดียว) โดยยังใช้ Python เป็นที่คำนวณทั้งหมด ฟอร์มเดิมยังต้องให้ผลเดิม
เมื่อกรอกค่าเดิม และต้องพิสูจน์ผลด้วยการกรอกจริงในเบราว์เซอร์ตามตาราง A1–A5 ของใบงาน

เหตุผล: ใบงานให้คะแนน 3 ด้าน (โครงสร้าง/Python, ความถูกต้อง+คงผลเดิม, การตรวจผ่าน Browser)
และ 1 คะแนนด้านการส่งงาน/ทำซ้ำได้ — ทุกด้านต้องมีหลักฐานใน repo

## 2. Goals

- G1 `Fixed Bias` คำนวณถูกตาม IB = (VCC − VBE)/RB, VE = 0
- G2 `Emitter Bias` คำนวณถูกตาม IB = (VCC − VBE)/[RB + (β+1)RE]
- G3 `Voltage Divider` ให้ผลเหมือน Lab 2 ทุกหลัก (A1)
- G4 `app.py` เลือกฟังก์ชันด้วย `if/elif` ตาม `mode`; โหมดไม่รู้จัก → HTTP 400
- G5 ตรวจเฉพาะช่องที่โหมดนั้นใช้ (Fixed ไม่ต้องมี RE, ไม่ใช้ R1/R2)
- G6 ฟอร์มมีตัวเลือกโหมด, แสดงเฉพาะช่องที่เกี่ยว, ผล/error ระบุโหมด, ไม่มีผลค้างจากรอบก่อน
- G7 แยก "อินพุตผิด" (error) ออกจาก "แบบจำลองใช้ไม่ได้" (warning ตาม IB ≤ 0 หรือ VCE ≤ 0.2 V)
- G8 มีตาราง A1–A5 + หลักฐานจากเบราว์เซอร์ + ค่าอ้างอิงอิสระในเอกสาร

## 3. Non-goals

- ไม่ทำ SPICE, DC Load Line, AC/Transient, ตัวเก็บประจุ Bypass
- ไม่ตั้ง Playwright MCP ในรอบนี้ (ใช้ OpenCode Browser tools และระบุวิธีจริงในรายงาน)
- ไม่รื้อสถาปัตยกรรม JSON + fetch ของ Lab 2
- ไม่ต้องเขียน unittest ใหม่ตามใบงาน (แต่ทำ เพราะ AGENTS.md บังคับ TDD เมื่อแก้สมการ)

## 4. Anti-goals (ถ้าเกิดขึ้นถือว่าไม่ผ่าน)

- ย้ายสมการไปไว้ใน HTML/JS หรือ hardcode ผลลัพธ์
- โหมดไม่รู้จักแล้วเงียบ ๆ คำนวณเป็น Divider
- ผล A1 เปลี่ยนจาก Lab 2
- tests เดิม 16 ตัวพัง
- แสดงผลรอบก่อนเป็นผลของรอบที่กรอกผิด

## 5. Approaches

| | ทาง | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A (เลือก)** | คง JSON + `fetch` เดิม เพิ่ม `mode` ใน FormData, `app.js` ซ่อน/ปิดช่องที่ไม่ใช้ | แก้ส่วนที่ผ่านการตรวจแล้วน้อยสุด, ไม่ reload, ตรง "ไม่ต้องทำเว็บใหม่" | พึ่ง JS ในการสลับช่อง (มี `<noscript>` อยู่แล้ว) |
| B | server-rendered ล้วน (`GET /?mode=`, `POST` คืน HTML) | ใช้ได้แม้ปิด JS | ต้องรื้อ JSON contract + `app.js` ทั้งชุด เสี่ยง regression |
| C | dropdown ยิง `GET /?mode=` reload ฟอร์ม แต่ผลยัง `fetch` | สลับช่องได้โดยไม่พึ่ง JS | มีสองเส้นทางในหน้าเดียว debug ยากขึ้น |

เลือก A: ใบงานระบุว่าไม่ต้องทำเว็บใหม่ และโครง JSON/fetch เดิมผ่านการตรวจ Lab 2 มาแล้ว

## 6. Design — ชั้น Python (`dc_bias.py`)

### 6.1 อินพุตแยกตามโหมด (frozen dataclass)

```python
FixedBiasInputs(vcc_v, rb_ohm, rc_ohm, beta, vbe_v)
EmitterBiasInputs(vcc_v, rb_ohm, rc_ohm, re_ohm, beta, vbe_v)
DcBiasInputs(vcc_v, r1_ohm, r2_ohm, rc_ohm, re_ohm, beta, vbe_v)   # เดิม ไม่แก้
```

### 6.2 ผลลัพธ์

`DcBiasResult` เพิ่ม/ปรับ:

```python
mode: str                       # "divider" | "fixed" | "emitter"
inputs_si: DcBiasInputs | FixedBiasInputs | EmitterBiasInputs
vth_v: float | None             # None สำหรับ fixed/emitter
rth_ohm: float | None
... ฟิลด์เดิม ib_a, ic_a, ie_a, vb_v, ve_v, vc_v, vce_v, vbc_v, region, warnings
```

### 6.3 ฟังก์ชันคำนวณ (แยกกันตามใบงาน)

```python
calculate_dc_bias(inputs)       # divider — สมการเดิมไม่เปลี่ยน
calculate_fixed_bias(inputs)    # ib=(vcc-vbe)/rb ; ve=0
calculate_emitter_bias(inputs)  # ib=(vcc-vbe)/(rb+(beta+1)*re)
```

ร่วมกันทุกโหมด: `ic = β·ib`, `ie = (β+1)·ib`, `vb = ve + vbe`,
`vc = vcc − ic·rc`, `vce = vc − ve`, `vbc = vb − vc`

### 6.4 Region / warning (เปลี่ยนเกณฑ์ตามใบงาน)

```python
VCE_SATURATION_THRESHOLD_V = 0.2   # เดิม 0.3

def _classify_region(ib_a, vce_v):
    if ib_a <= 0:      -> "cutoff"      + warning (IB ≤ 0)
    if vce_v <= 0.2:   -> "saturation"  + warning (VCE ≤ 0.2 V)
    else               -> "forward_active", []
```

**หลักฐานว่า tests เดิมยังผ่าน** (วัดจากโค้ดปัจจุบัน):

| เคสเดิม | ค่าที่วัดได้ | เกณฑ์ใหม่ |
|---|---|---|
| `r2=1 kΩ` (cutoff) | IB = −5.698 µA | IB ≤ 0 → cutoff ✓ |
| `rc=8.6 kΩ` (saturation) | VCE = 0.1811 V | ≤ 0.2 → saturation ✓ |
| `rc=20 kΩ` (deep) | VCE = −13.84 V | ≤ 0.2 → saturation ✓ |
| ค่าอ้างอิง A1 | IB = 12.299 µA, VCE = 8.052 V | forward_active ✓ |

สำหรับ Divider เงื่อนไข `IB ≤ 0` สมมูลกับ `VTH ≤ VBE` เพราะตัวส่วน > 0 เสมอ

### 6.5 Parsing / validation

```python
parse_inputs(raw, mode="divider") -> (inputs | None, errors)
```

- `mode` default `"divider"` → **tests เดิมเรียกแบบไม่มี mode ยังผ่าน**
- โหมดไม่รู้จัก → `errors["mode"] = "โหมดไม่รู้จัก ..."`, คืน `(None, errors)`
- ฟิลด์ร่วม: `vcc, rc, beta, vbe`
- ต่อโหมด: divider → `r1, r2, re`; fixed → `rb`; emitter → `rb, re`
- หน่วย: `ohm` / `kohm` ผ่านคีย์ `<field>_unit` (เพิ่ม `rb_unit`)
- **ฟิลด์ที่ไม่เกี่ยวถูกเมิน** (ไม่ parse, ไม่ error) — เช่น fixed ที่มี `r1="abc"` ยังผ่าน
- กฎค่า: vcc > 0, rc > 0, R ทุกตัว > 0, β > 0, 0 ≤ VBE ≤ 2, ตัวเลขต้อง finite
- error key = ชื่อฟิลด์ฐาน (`rb`, `re`, ...) ตามสัญญาเดิม

## 7. Design — ชั้น HTTP (`app.py`)

```python
mode = (request.form.get("mode") or "divider").strip().lower()
inputs, errors = parse_inputs(request.form, mode)
if errors:
    return 400 {"ok": false, "mode": mode, "errors": errors, "message": "..."}
if   mode == "divider": result = calculate_dc_bias(inputs)
elif mode == "fixed":   result = calculate_fixed_bias(inputs)
elif mode == "emitter": result = calculate_emitter_bias(inputs)
else: return 400 {"mode": mode, "errors": {"mode": ...}}   # defensive
return 200 {"ok": true, "data": _serialize(result)}        # data.mode ตาม §6.2
```

**ผลฝั่ง error ก็มี `mode` เช่นกัน** เพื่อให้ UI ระบุโหมดได้แม้คำนวณไม่สำเร็จ (G6):
`app.js` ใช้ `body.mode` เติมหัวข้อ error summary และ `errors["mode"]` แสดงใต้ช่องเลือกโหมด

`_serialize()` เพิ่ม `"mode"` และสร้าง `inputs_si` ตามชนิดอินพุต
(`intermediate` = `{}` เมื่อไม่มี VTH/RTH) — **ตัวเลขทุกตัวยังเป็น SI** ตาม AGENTS.md
(ไม่ส่ง `ic_ma`; การแปลงเป็น mA เป็นหน้าที่ `app.js` — ใบงานอนุญาตให้ใช้ชื่อคีย์เดิมของ Lab 2)

## 8. Design — UI (`templates/index.html`, `static/app.js`, `static/style.css`)

### 8.1 ฟอร์ม

- เพิ่มบนสุดของฟอร์ม: `<select id="mode" name="mode">` → `divider` (Voltage Divider Bias),
  `fixed` (Fixed Bias), `emitter` (Emitter Bias)
  ต้องอยู่ใน `<div class="field">` เพราะ `showErrors()` ใน `app.js` หา `input.closest(".field")`
  เพื่อวางข้อความ `errors["mode"]` — ถ้าไม่ห่อ ข้อความโหมดผิดจะไม่แสดง
- แต่ละ `.field` มี `data-modes="divider fixed emitter"` ฯลฯ:

| ฟิลด์ | โหมดที่ใช้ |
|---|---|
| vcc, rc, beta, vbe | ทั้งสาม |
| r1, r2 | divider |
| re | divider, emitter |
| rb (ใหม่) | fixed, emitter |

- `app.js` ตอน `change` ของ `mode`: ซ่อน (`hidden`) + `disabled` ช่องที่ไม่ใช้
  (disabled ไม่ถูกส่งไปกับ FormData), เคลียร์ error/ผลเดิม, เปลี่ยนข้อความ placeholder
- เรียกใช้ฟังก์ชันเดียวกันตอน `DOMContentLoaded` เพื่อให้สถานะเริ่มต้นถูกต้อง
- ช่อง `rb` ใช้รูปแบบเดิม (input + select หน่วย Ω/kΩ)

### 8.2 ผลลัพธ์

- เพิ่ม `<p id="result-mode">` แสดง "โหมด: Fixed Bias" ฯลฯ
- ตาราง Inputs สร้างตามโหมด (แสดงเฉพาะค่าที่โหมดนั้นใช้ + RB เมื่อมี)
- ตาราง Intermediate แสดงเฉพาะเมื่อ `vth_v` ไม่เป็น null
- Operating point แสดงครบ 8 ค่าเหมือนเดิม
- badge/warnings ใช้ของเดิม (region label 3 ค่า)

### 8.3 หลักการ

`app.js` ไม่คำนวณ DC bias — ทำแค่จัดรูปแบบหน่วย (V, mA, µA, kΩ) ตามข้อมูล JSON

## 9. Tests (TDD — เขียนก่อนแก้, รวม 30 ตัว = 16 เดิม + 14 ใหม่)

เพิ่มใน `tests/test_dc_bias.py`:

| # | test | ยืนยัน |
|---|---|---|
| 1 | `test_fixed_reference_case` | A2: IB 11.3000 µA, IC 1.13000 mA, IE 1.14130 mA, VE 0, VB 0.70000, VC 9.51400, VCE 9.51400 |
| 2 | `test_emitter_reference_case` | A3: IC 1.02634 mA, VE 1.03660 V, VCE 8.70545 V |
| 3 | `test_emitter_re_bigger_lowers_ic` | A4 (RE 2 kΩ) → IC < A3 และ VCE ≈ 8.03278 V |
| 4 | `test_fixed_ignores_divider_fields` | fixed + `r1="abc"` → ไม่มี error |
| 5 | `test_fixed_requires_rb` | ไม่ส่ง `rb` → `errors["rb"]` |
| 6 | `test_unknown_mode_is_rejected` | `mode="bridge"` → `errors["mode"]` |

เพิ่มใน `tests/test_web.py`:

| # | test | ยืนยัน |
|---|---|---|
| 7 | `test_post_fixed_returns_mode_and_values` | 200, `mode="fixed"`, `intermediate == {}`, IC/VCE ตรง A2 |
| 8 | `test_post_emitter_uses_re` | 200, `mode="emitter"`, VCE ตรง A3 |
| 9 | `test_post_unknown_mode_returns_400` | 400 + `errors["mode"]` + echo `mode` |

เพิ่มใน `tests/test_dc_bias.py` (pin เกณฑ์ใหม่):

| # | test | ยืนยัน |
|---|---|---|
| 10 | `test_vce_between_0_2_and_0_3_is_forward_active` | `rc=8.55 kΩ` → VCE 0.2426 V → **forward_active** (โค้ดเดิมให้ saturation เพราะเกณฑ์ 0.3) |

test นี้ **ล้มเหลวก่อนแก้** จึงเป็นตัวพิสูจน์การเปลี่ยนเกณฑ์ตาม TDD
ส่วน `assertLess(result.vce_v, 0.3)` ใน test เดิม **ไม่แก้** (ยังจริงที่ VCE 0.1811 V)
และไม่มีการแก้ assertion ใด ๆ ใน 16 tests เดิม

tests เดิม 16 ตัวต้องผ่านโดยไม่แก้ (ยกเว้นค่าคงที่ 0.3→0.2 ที่ยังทำให้ผ่านตาม §6.4)

## 10. Acceptance A1–A5 (ค่าอ้างอิง + เกณฑ์)

ค่ากลาง: VCC = 12 V, RC = 2.2 kΩ, β = 100, VBE = 0.70 V
Tolerance: IC ±0.01 mA, VCE ±0.02 V

| ID | โหมด/อินพุต | ค่าอ้างอิง (คำนวณมือ) |
|---|---|---|
| A1 | Divider: R1 100k, R2 22k, RE 1k | IB 12.2986 µA · IC 1.22986 mA · VCE 8.05216 V |
| A2 | Fixed: RB 1 MΩ | IB 11.3000 µA · IC 1.13000 mA · VE 0 V · VC 9.51400 V · VCE 9.51400 V |
| A3 | Emitter: RB 1 MΩ, RE 1 kΩ | IB 10.2634 µA · IC 1.02634 mA · VE 1.03660 V · VCE 8.70545 V |
| A4 | Emitter: RB 1 MΩ, RE 2 kΩ | IB 9.4010 µA · IC 0.94010 mA · VE 1.89900 V · VCE 8.03278 V |
| A5 | Fixed: RB = 0 | 400 + ข้อความให้แก้ RB, ไม่มีผลค้าง |

ทิศทาง A3→A4: RE เพิ่ม → ตัวส่วน IB โต → **IC ลดลง** (0.940 < 1.026 mA)

> นักศึกษาต้องตรวจค่าอ้างอิงเหล่านี้ด้วยสมการเองก่อนรัน (ใบงานห้ามใช้ค่าจากโค้ดเป็นคำตอบอ้างอิง)

## 11. เอกสาร / หลักฐาน

โครงสร้างไฟล์ `docs/validation.md` (ตัดสินใจ): **เก็บ Lab 2 ไว้เป็นภาคผนวก** เพื่อรักษาหลักฐาน
"ผล A1 ไม่เปลี่ยน" แต่ไม่ให้ตาราง A1–A5 สองชุดปนกัน

```
docs/validation.md
├── 1. Lab 3 — A1–A5            ← ตารางใหม่ (ส่วนหลัก)
├── 2. ค่าอ้างอิงอิสระ A2/A3    ← คำนวณมือทีละบรรทัด
├── 3. วิธีตรวจ + หลักฐาน        ← OpenCode Browser tools + screenshot
├── 4. ผล unittest ล่าสุด
└── 5. ภาคผนวก: Lab 2 (A1–A7)   ← ของเดิม คงไว้เป็นประวัติ
```

ต้องแก้ถ้อยคำที่เก่าและเป็นเท็จหลังเปลี่ยนเกณฑ์: `README.md` และ `docs/validation.md`
ที่ยังเขียน `VCE < 0.3 V` หรือ `VTH ≤ VBE` → เปลี่ยนเป็น `IB ≤ 0` / `VCE ≤ 0.2 V`

- `README.md`: 3 โหมด, วิธีรัน, ค่าตัวอย่าง A1–A4, หัวข้อ "AI ช่วยส่วนไหน / นักศึกษาตรวจอะไร"
- `docs/evidence/`: screenshot อย่างน้อย 1 กรณี (ใบงาน: "ข้อความจากหน้าเว็บ **หรือ**
  screenshot อย่างน้อยหนึ่งกรณี") — แนบ 2 รูป (A1 สำเร็จ, A5 ผิดพลาด) เพื่อความชัด
- `docs/design-note.md`: อัปเดต data flow ให้มี mode dispatch
- `docs/reflection.md`: **ไม่แก้** (ใบงาน Lab 3 ไม่ได้ขอ และ AGENTS.md ห้ามเขียนคำตอบ)

## 12. Branch / commits

- branch ใหม่ `feature/lab03-three-bias-modes` จาก `8800360`
- 4 commits (นักศึกษา commit เองผ่าน GitHub Desktop):
  1. `feat: add fixed and emitter bias calculations`
  2. `feat: select bias mode in the calculate API`
  3. `feat: choose bias mode in the form`
  4. `docs: add lab 3 acceptance results and references`

## 13. ความเสี่ยง

| ความเสี่ยง | ทางลด |
|---|---|
| tests เดิมพังเพราะเปลี่ยน signature | `parse_inputs(raw, mode="divider")` default + dataclass เดิมไม่แก้ |
| `disabled` ช่องแล้ว FormData หายค่าที่ต้องใช้ | ซ่อน/ปิดเฉพาะช่องที่ `data-modes` ไม่มีโหมดปัจจุบัน |
| ผลค้างจากรอบก่อน | `resetMessages()` ทุกครั้งก่อน submit + on mode change |
| ผลต่างจากปัดเศษ | JSON ส่งค่าเต็ม, `app.js` แสดง 3 ตำแหน่ง; เกณฑ์ ±0.01 mA / ±0.02 V |

## 14. ภาคผนวก A — สรุปใบงาน (แหล่งที่มา: `ENG29_2121_Lab03_BJT_Bias_Web_App.html`)

ไฟล์ใบงานอยู่นอก repo (`C:\Users\B6809157\Downloads\`) ข้อกำหนดที่เกี่ยวกับงานนี้ครบถ้วนดังนี้

| หัวข้อ | ข้อกำหนด |
|---|---|
| ขอบเขต | DC Operating Point เท่านั้น; ไม่มี SPICE, Load Line, AC/Transient, Bypass capacitor |
| สิ่งที่ต้องแก้ | `dc_bias.py` (ฟังก์ชันแยก), `app.py` (เลือกด้วย if/elif + ตรวจตามโหมด), `templates/index.html` (เลือกโหมด/เห็นเฉพาะช่องที่ใช้) |
| สัญญาผลลัพธ์ | ชื่อคีย์/หน่วยตรงกันระหว่าง Flask กับฟังก์ชัน; ใช้ชื่อเดิมของ Lab 2 ได้ |
| ข้อผิดพลาด | ฟิลด์ไม่ครบ/ไม่ใช่ตัวเลข/non-finite/ค่าที่ต้องบวกแต่ ≤ 0 → error; อินพุตถูกแต่ IB ≤ 0 หรือ VCE ≤ 0.2 V → warning |
| การตรวจ | A1–A5 ผ่านเบราว์เซอร์จริง, tolerance IC ±0.01 mA / VCE ±0.02 V, สถานะ PASS/FAIL/NOT RUN |
| หลักฐาน | "ข้อความจากหน้าเว็บ **หรือ** screenshot อย่างน้อยหนึ่งกรณี" — 1 กรณีพอ (แผนแนบ 2) |
| ห้าม | ห้ามใช้ค่าจากโค้ดเป็นคำตอบอ้างอิง, ห้ามใช้ curl แทนการรันเบราว์เซอร์, ห้ามแก้โค้ดก่อนส่งรายงานรอบแรก |
| MCP | Playwright MCP เป็นเส้นทางหลัก แต่ถ้าใช้ไม่ได้ให้บันทึก NOT RUN + ใช้ OpenCode Browser tools หรือทำมือ และระบุวิธีจริง |
| คะแนน | โครงสร้าง/Python 3 · วิศวกรรม+คงผลเดิม 3 · ตรวจ Browser 3 · ส่งงาน/ทำซ้ำได้ 1 |
| สิ่งที่ต้องส่ง | GitHub URL + Commit SHA, README, ตาราง A1–A5, ค่าอ้างอิงอิสระ ≥1 กรณีของโหมดใหม่, ระบุส่วนที่ AI ช่วยและสิ่งที่นักศึกษาตรวจ |
| ไม่ถูกขอ | `docs/reflection.md` ไม่มีในข้อกำหนด Lab 3 (คงของเดิมไว้ ไม่แตะ) |
| คำถามปิด Lab | "ถ้าคำนวณมือถูก แต่เปลี่ยน RE แล้วผลบนเว็บไม่เปลี่ยน จะตรวจค่าที่ส่งจากฟอร์มและค่าที่เข้าไปในฟังก์ชันอย่างไร?" — นักศึกษาเขียนเอง |

