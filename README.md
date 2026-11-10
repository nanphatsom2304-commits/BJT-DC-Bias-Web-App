# BJT DC Bias Web App

Flask Web Application สำหรับคำนวณ **DC Operating Point** ของวงจร BJT NPN
Common-Emitter แบบ Voltage-Divider Bias (Lab 02 — ENG29 2121)

- Frontend: ฟอร์ม HTML + vanilla JavaScript (`fetch`) — ไม่ reload หน้า
- Backend: Python/Flask รับค่าจากฟอร์ม แปลงหน่วย ตรวจสอบ และคำนวณจริง
- ผลลัพธ์: `IB, IC, IE, VB, VE, VC, VCE, VBC` พร้อมหน่วย, `VTH/RTH`,
  Operating Region และคำเตือนเมื่อแบบจำลอง Forward-Active ใช้ไม่ได้

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

ต้องได้ `Ran 16 tests ... OK` (5 engineering tests ของสมการ/unit/validation,
4 tests ของ region, และ 7 tests ผ่าน Flask test client)

## ค่าตัวอย่างสำหรับทดลอง

| พารามิเตอร์ | ค่า |
|---|---|
| VCC | 12 V |
| R1 | 100 kΩ |
| R2 | 22 kΩ |
| RC | 2.2 kΩ |
| RE | 1 kΩ |
| β | 100 |
| VBE | 0.70 V |

ผลที่ควรได้: **IC ≈ 1.2299 mA, VB ≈ 1.9422 V, VE ≈ 1.2422 V,
VC ≈ 9.2943 V, VCE ≈ 8.0522 V** และ Region = Forward-Active

## โครงสร้างไฟล์

```
app.py                # Flask routes: GET /, POST /calculate
dc_bias.py            # parse_inputs() + calculate_dc_bias() — ไม่ import Flask
templates/index.html  # ฟอร์ม + containers สำหรับผลลัพธ์
static/app.js         # fetch + render ผล/error (ไม่คำนวณ DC bias)
static/style.css      # layout, responsive, region badge
tests/                # unittest (engineering logic + HTTP)
docs/                 # design note, validation, reflection
```

## แบบจำลองและข้อจำกัด

ใช้ Forward-Active approximation โดยถือว่า β และ VBE คงที่:

```
VTH = VCC·R2/(R1+R2)      RTH = R1·R2/(R1+R2)
IB  = (VTH−VBE)/(RTH+(β+1)·RE)
IC  = β·IB      IE = (β+1)·IB
VE  = IE·RE     VB = VE+VBE
VC  = VCC−IC·RC     VCE = VC−VE
```

แอปจะเตือนเมื่อ `VTH ≤ VBE` (Cutoff) หรือ `VCE < 0.3 V` (Saturation)
เพราะสมการข้างต้นใช้ไม่ได้/ไม่แม่นยำในสภาวะนั้น — ไม่ใช่การจำลอง SPICE

## License / การใช้งาน

เอกสารและโค้ดนี้จัดทำเพื่อการศึกษาในรายวิชา ENG29 2121
