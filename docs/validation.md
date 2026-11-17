# Validation — การตรวจสอบผลคำนวณ DC Bias

เอกสารนี้บันทึก (1) ตารางตรวจรับ A1–A5 ของ Lab 03 (2) ค่าอ้างอิงที่คำนวณมือ
อย่างอิสระ (3) วิธีและหลักฐานการตรวจในเบราว์เซอร์ (4) ผล unittest
และ (5) ภาคผนวกผลตรวจของ Lab 02 ที่คงไว้เป็นประวัติ

> ค่าอ้างอิงในเอกสารนี้คำนวณจากสมการในใบงาน/ตำรา ไม่ได้คัดลอกจาก output
> ของแอป — ตัวเลข "เห็นจริง" คือค่าที่อ่านจากหน้าเว็บในเบราว์เซอร์

## 1. ตารางตรวจรับ Lab 03 (A1–A5)

ค่ากลางของทุกกรณี: VCC = 12 V, RC = 2.2 kΩ, β = 100, VBE = 0.70 V
เกณฑ์ผ่าน: IC ±0.01 mA และ VCE ±0.02 V

| ข้อ | โหมด / อินพุต | ค่าอ้างอิง (คำนวณมือ) | เห็นจริงบนหน้าเว็บ | สถานะ |
|---|---|---|---|---|
| A1 | Voltage Divider — R1 100 kΩ, R2 22 kΩ, RE 1 kΩ | IB 12.2986 µA · IC 1.22986 mA · VCE 8.05216 V | IB 12.30 µA · IC 1.230 mA · VCE 8.052 V · Forward-Active | **PASS** |
| A2 | Fixed — RB 1 MΩ | IB 11.3000 µA · IC 1.13000 mA · IE 1.14130 mA · VE 0 V · VB 0.70000 V · VC 9.51400 V · VCE 9.51400 V | IB 11.30 µA · IC 1.130 mA · IE 1.141 mA · VE 0.000 V · VB 0.700 V · VC 9.514 V · VCE 9.514 V · Forward-Active | **PASS** |
| A3 | Emitter — RB 1 MΩ, RE 1 kΩ | IB 10.2634 µA · IC 1.02634 mA · IE 1.03660 mA · VE 1.03660 V · VB 1.73660 V · VC 9.74205 V · VCE 8.70545 V | IB 10.26 µA · IC 1.026 mA · IE 1.037 mA · VE 1.037 V · VB 1.737 V · VC 9.742 V · VCE 8.705 V · Forward-Active | **PASS** |
| A4 | Emitter — RB 1 MΩ, RE 2 kΩ | IB 9.4010 µA · IC 0.94010 mA · IE 0.94950 mA · VE 1.89900 V · VB 2.59900 V · VC 9.93178 V · VCE 8.03278 V | IB 9.40 µA · IC 940.10 µA · IE 949.50 µA · VE 1.899 V · VB 2.599 V · VC 9.932 V · VCE 8.033 V (IC ลดลงจาก A3) | **PASS** |
| A5 | Fixed — RB = 0 kΩ | HTTP 400 + ข้อความให้แก้ RB และต้องไม่มีผลของรอบก่อนค้างอยู่ | summary "โหมด: Fixed Bias — กรุณาตรวจสอบค่าที่ป้อน" · ใต้ช่อง RB: "RB ต้องมากกว่า 0 Ω" · แผงผลลัพธ์ว่าง | **PASS** |

บันทึกเพิ่มเติม

- A4 แสดง IC เป็น `940.10 µA` เพราะ `app.js` แสดงหน่วย µA เมื่อค่าน้อยกว่า 1 mA
  (เท่ากับ 0.94010 mA ตามค่าอ้างอิง)
- ตรวจ `mode` ที่ไม่รู้จักเพิ่มด้วย unittest (ไม่ได้อยู่ใน A1–A5):
  `POST /calculate` ด้วย `mode=bridge` → HTTP 400 + `errors["mode"]`
  และไม่ fallback ไปคำนวณเป็น Voltage Divider

## 2. ค่าอ้างอิงอิสระ — คำนวณมือทีละบรรทัด

### 2.1 A2 Fixed Bias (RB = 1 MΩ)

```
IB = (VCC − VBE) / RB = (12 − 0.70) / 1,000,000
   = 11.3 / 1,000,000 = 1.13000 × 10⁻⁵ A = 11.3000 µA
IC = β·IB            = 100 × 11.3000 µA = 1.13000 mA
IE = (β+1)·IB        = 101 × 11.3000 µA = 1.14130 mA
VE = IE·RE           = 0 (โหมด Fixed ไม่มี RE)
VB = VE + VBE        = 0 + 0.70 = 0.70000 V
VC = VCC − IC·RC     = 12 − (1.13000 mA × 2.2 kΩ) = 12 − 2.486 = 9.51400 V
VCE = VC − VE        = 9.51400 − 0 = 9.51400 V
```

**Cross-check:** `VCC = IC·RC + VCE + IE·RE` → 2.486 + 9.51400 + 0 = **12.00000 V** ✓

### 2.2 A3 Emitter Bias (RB = 1 MΩ, RE = 1 kΩ)

```
ตัวส่วน = RB + (β+1)·RE = 1,000,000 + 101 × 1,000 = 1,101,000 Ω
IB = (12 − 0.70) / 1,101,000 = 11.3 / 1,101,000 = 1.0263397 × 10⁻⁵ A
   = 10.2634 µA
IC = 100 × 10.2634 µA = 1.02634 mA
IE = 101 × 10.2634 µA = 1.03660 mA
VE = 1.03660 mA × 1 kΩ = 1.03660 V
VB = 1.03660 + 0.70   = 1.73660 V
VC = 12 − (1.02634 mA × 2.2 kΩ) = 12 − 2.257948 = 9.74205 V
VCE = 9.74205 − 1.03660 = 8.70545 V
```

**Cross-check:** `VCC = IC·RC + VCE + IE·RE` → 2.25795 + 8.70545 + 1.03660
= **12.00000 V** ✓

### 2.3 A4 Emitter Bias (RB = 1 MΩ, RE = 2 kΩ) — ตรวจทิศทาง

```
ตัวส่วน = 1,000,000 + 101 × 2,000 = 1,202,000 Ω  (ใหญ่กว่า A3)
IB = 11.3 / 1,202,000 = 9.40100 µA  (< 10.2634 µA)
IC = 0.94010 mA                      (< 1.02634 mA)
IE = 101 × 9.40100 µA = 0.94950 mA
VE = 0.94950 mA × 2 kΩ = 1.89900 V
VB = 2.59900 V
VC = 12 − (0.94010 × 2.2) = 9.93178 V
VCE = 8.03278 V
```

สรุปทิศทาง: **RE เพิ่ม → ตัวส่วนของ IB ใหญ่ขึ้น → IB และ IC ลดลง**
ส่วน VE เพิ่มขึ้นมากกว่าที่ VC เพิ่ม จึงทำให้ VCE ลดลงจาก 8.70545 V (A3)
เหลือ 8.03278 V (A4) ค่าที่วัดได้บนหน้าเว็บ (IC 940.10 µA, VCE 8.033 V)
ตรงกับทิศทางนี้

## 3. วิธีตรวจและหลักฐาน

### 3.1 วิธีจริง

- เครื่องมือ: **OpenCode Browser tools** (Chromium ภายในแอป OpenCode) —
  เปิด `http://127.0.0.1:5000/`, เลือกโหมดจาก dropdown, กรอกค่าด้วยการพิมพ์จริง,
  กดปุ่ม **Calculate DC Bias** แล้วอ่านค่าจากตารางผลลัพธ์ด้วย accessibility
  snapshot และ `innerText` ของ DOM
- Flask dev server รันด้วย `--no-reload` และรีสตาร์ตใหม่หลังแก้โค้ดทุกครั้ง
  เพื่อไม่ให้ตรวจโค้ดเก่า
- ไม่ได้ใช้ `curl` เป็นหลักฐานของ A1–A5 (ใช้ตรวจสัญญา JSON ระหว่างพัฒนาเท่านั้น)
- Playwright MCP: **NOT RUN** ในรอบนี้ (ตามใบงานให้บันทึกไว้) — ใช้ OpenCode
  Browser tools เป็นเส้นทางจริง

### 3.2 ข้อความจากหน้าเว็บ (page text)

A5 (ตัวอย่างหลักฐานข้อความ):

```
summary  : โหมด: Fixed Bias — กรุณาตรวจสอบค่าที่ป้อน
field    : RB ต้องมากกว่า 0 Ω   (aria-invalid ที่ช่อง RB)
ผลลัพธ์  : แผง DC Bias Results ว่าง (results.hidden = true)
```

A1–A4 อ่านค่าจากตาราง `Inputs (normalized)` และ `Operating point`
ตรงกับคอลัมน์ "เห็นจริง" ใน §1

### 3.3 ภาพหน้าจอ

| ไฟล์ | เนื้อหา |
|---|---|
| `docs/evidence/a1-divider.jpeg` | A1 Voltage Divider: IC 1.230 mA, VCE 8.052 V, Forward-Active |
| `docs/evidence/a5-fixed-invalid.jpeg` | A5 Fixed Bias, RB = 0: error ใต้ช่อง RB, summary ระบุโหมด, ไม่มีผลค้าง |

## 4. ผลการรันเทสต์

คำสั่ง:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

ผลล่าสุด:

```
Ran 38 tests in 0.083s

OK
```

แยกเป็น

- `tests/test_dc_bias.py` 21 tests — ค่าอ้างอิง Divider 1, unit/validation 5,
  region 4, เกณฑ์ 0.2 V + warning IB 2, Fixed 2, Emitter 2, mode parsing 5
- `tests/test_web.py` 17 tests — GET / 3, POST สำเร็จ 1, error 400 2,
  region warning 2, mode dispatch 9 (fixed, emitter, unknown, blank,
  missing→divider, uppercase, RB ≤ 0, β ≤ 0, overflow)

## 5. ภาคผนวก — ผลตรวจของ Lab 02 (Voltage Divider)

ส่วนนี้คงไว้เป็นประวัติว่าโหมด Voltage Divider ให้ผลเหมือน Lab 02 หลังเพิ่ม
สองโหมดใหม่ (A1 ใน §1 คือหลักฐานว่าไม่เปลี่ยน)

### A.1 ค่าอ้างอิงเดิม (Divider)

```
VTH = 12 × 22,000 / 122,000 = 2.163934 V
RTH = (100,000 × 22,000) / 122,000 = 18,032.787 Ω
IB  = (2.163934 − 0.70) / (18,032.787 + 101 × 1,000) = 12.2986 µA
IC  = 1.22986 mA · IE = 1.24216 mA
VE  = 1.24216 V · VB = 1.94216 V
VC  = 9.29431 V · VCE = 8.05216 V · VBC = −7.35216 V
```

**Cross-check:** `VTH − IB·RTH = 2.163934 − 12.29858 µA × 18.0328 kΩ = 1.942157 V`
เท่ากับ `VB` ที่คำนวณจาก `VE + VBE` ✓

### A.2 ตารางตรวจรับของ Lab 02

| ข้อ | วิธีตรวจ | ผล |
|---|---|---|
| A1 · GET / | เปิด `http://127.0.0.1:5000/` | 200 + ฟอร์ม + dropdown หน่วย |
| A2 · POST /calculate | กด Calculate ใน Browser ด้วยค่าตัวอย่าง | IC = 1.230 mA, VCE = 8.052 V |
| A3 · Engineering reference | เทียบกับค่าคำนวณมือ | ตรงทุกค่า |
| A4 · Validation | ใส่ β = −1 | HTTP 400 + "β ต้องมากกว่า 0" ใต้ช่อง β |
| A5 · Region warning | R2 = 1 kΩ (VTH = 0.119 V) | Region = Cutoff + warning (เกณฑ์ Lab 03: IB ≤ 0) |
| A6 · Tests | รัน unittest | 16 tests ผ่าน (ณ ตอนนั้น) |
| A7 · Reproducibility | ทำตาม README | ติดตั้ง venv + รันเว็บ + รันเทสต์ได้ |

## 6. ข้อจำกัด

- ผลทั้งหมดอยู่ภายใต้ Forward-Active approximation (β, VBE คงที่)
- ไม่ได้เทียบกับ ngspice หรือการวัดจริง — เป็นการตรวจสอบเชิงสมการ
- ค่าที่ Region = Cutoff/Saturation ถูกส่งกลับตามสมการแต่ติดป้ายว่าเชื่อถือไม่ได้
- เกณฑ์ Saturation ใช้ `VCE ≤ 0.2 V` ตามใบงาน Lab 03 (Lab 02 เดิมใช้ 0.3 V)
