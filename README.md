# BJT DC Bias Web App

Flask Web Application สำหรับคำนวณ **DC Operating Point** ของวงจร BJT NPN
Common-Emitter ที่เลือกวงจรไบอัสได้ 3 แบบ (Lab 03 — ENG29 2121)

| โหมด | ค่า `mode` | สมการกระแส Base |
|---|---|---|
| Voltage Divider Bias | `divider` | IB = (VTH − VBE) / [RTH + (β+1)·RE] |
| Fixed Bias | `fixed` | IB = (VCC − VBE) / RB |
| Emitter Bias | `emitter` | IB = (VCC − VBE) / [RB + (β+1)·RE] |

- Frontend: ฟอร์ม HTML + vanilla JavaScript (`fetch`) — ไม่ reload หน้า
- Backend: Python/Flask รับ `mode` จากฟอร์ม เลือกฟังก์ชันด้วย `if/elif`
  แปลงหน่วย และตรวจเฉพาะช่องที่โหมดนั้นใช้จริง
- ผลลัพธ์: `IB, IC, IE, VB, VE, VC, VCE, VBC` พร้อมหน่วย, `VTH/RTH`
  (เฉพาะ Voltage Divider), Operating Region และคำเตือนเมื่อแบบจำลอง
  Forward-Active ใช้ไม่ได้

## ความต้องการของระบบ

- Python 3.10 ขึ้นไป (ทดสอบบน 3.15.2)
- Flask 3.x (ดู `requirements.txt`)
- ไม่ต้องใช้อินเทอร์เน็ตในการรัน (ไม่มี CDN)

## วิธีติดตั้งและรัน

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m flask --app app run --debug
```

จากนั้นเปิด <http://127.0.0.1:5000/>

macOS / Linux ใช้ `python3 -m venv .venv` และ `.venv/bin/python` แทน

> Flask debug server ใช้สำหรับเครื่องพัฒนาของตนเองเท่านั้น ไม่ควรเปิดให้
> เครือข่ายสาธารณะเข้าถึง

## วิธีรันเทสต์

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

ต้องได้ `Ran 38 tests ... OK` (21 tests ของสมการ/หน่วย/validation/region
และ 17 tests ผ่าน Flask test client)

## ค่าตัวอย่างสำหรับทดลอง

ค่ากลางของทุกโหมด: VCC = 12 V, RC = 2.2 kΩ, β = 100, VBE = 0.70 V

| กรณี | โหมด | ค่าที่กรอกเพิ่ม | ผลที่ควรได้ |
|---|---|---|---|
| A1 | Voltage Divider | R1 = 100 kΩ, R2 = 22 kΩ, RE = 1 kΩ | IC 1.22986 mA · VCE 8.05216 V |
| A2 | Fixed | RB = 1 MΩ | IB 11.3000 µA · IC 1.13000 mA · VE 0 V · VCE 9.51400 V |
| A3 | Emitter | RB = 1 MΩ, RE = 1 kΩ | IC 1.02634 mA · VE 1.03660 V · VCE 8.70545 V |
| A4 | Emitter | RB = 1 MΩ, RE = 2 kΩ | IC 0.94010 mA · VE 1.89900 V · VCE 8.03278 V |

A3 → A4: RE เพิ่มเป็นสองเท่า → ตัวส่วนของ IB ใหญ่ขึ้น → **IC ลดลง**
(0.94010 < 1.02634 mA) — ใช้ตรวจว่าค่าที่ส่งจากฟอร์มเข้าสมการจริง

## โครงสร้างไฟล์

```
app.py                # Flask routes: GET /, POST /calculate (mode dispatch)
dc_bias.py            # parse_inputs(mode) + calculate_dc_bias / calculate_fixed_bias / calculate_emitter_bias
templates/index.html  # ฟอร์ม + dropdown โหมด + containers สำหรับผลลัพธ์
static/app.js         # fetch + สลับช่องตามโหมด + render ผล/error (ไม่คำนวณ DC bias)
static/style.css      # layout, responsive, region badge
tests/                # unittest (engineering logic + HTTP)
docs/                 # design note, validation (A1–A5), evidence, reflection
```

## แบบจำลองและข้อจำกัด

ใช้ Forward-Active approximation โดยถือว่า β และ VBE คงที่:

```
Divider:  VTH = VCC·R2/(R1+R2)   RTH = R1·R2/(R1+R2)
          IB  = (VTH−VBE)/(RTH+(β+1)·RE)
Fixed:    IB  = (VCC−VBE)/RB
Emitter:  IB  = (VCC−VBE)/(RB+(β+1)·RE)

ทุกโหมด:  IC = β·IB      IE = (β+1)·IB
          VE = IE·RE     VB = VE+VBE        (Fixed: RE = 0 → VE = 0)
          VC = VCC−IC·RC     VCE = VC−VE
```

- `IB ≤ 0` → Region = **Cutoff** + warning (สมการ Forward-Active ใช้ไม่ได้)
- `VCE ≤ 0.2 V` → Region = **Saturation** + warning (แบบจำลองไม่แม่นยำ)
- สำหรับ Voltage Divider เงื่อนไข `IB ≤ 0` สมมูลกับ `VTH ≤ VBE`

ไม่มี SPICE, DC Load Line, AC/Transient หรือ bypass capacitor ในเวอร์ชันนี้

## AI ช่วยส่วนไหน / นักศึกษาตรวจอะไร

- **AI ช่วย:** ร่างโครงฟังก์ชันคำนวณและ validation, เขียน unittest,
  ปรับฟอร์ม/`app.js`, และกรอกฟอร์มจริงผ่าน OpenCode Browser tools
  เพื่อเก็บผล A1–A5 (ดู `docs/validation.md`)
- **นักศึกษาตรวจ:** อ่านสมการใน `dc_bias.py`, คำนวณมือ A2/A3 ด้วยตนเอง
  (แสดงทีละบรรทัดใน `docs/validation.md`), กดฟอร์มซ้ำในเบราว์เซอร์ของตนเอง
  และยืนยันว่า Commit SHA ที่ส่งตรงกับ branch นี้

## License / การใช้งาน

เอกสารและโค้ดนี้จัดทำเพื่อการศึกษาในรายวิชา ENG29 2121
