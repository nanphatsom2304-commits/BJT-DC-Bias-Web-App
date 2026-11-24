# BJT CE Amplifier Simulator v1 (Lab 04)

Flask web app สำหรับรายวิชา **ENG29 2121 — Lab 04 BJT Amplifier Simulator**  
ต่อยอดจาก Lab 3 (DC bias 3 โหมด) โดยเพิ่มการจำลองวงจร **CE voltage-divider amplifier** ด้วย **ngspice จริง** (`.op`, `.ac`, `.tran`) พร้อม UI แสดงผล, กราฟ, ตาราง, และ provenance ของการรัน

> **Playwright MCP:** `NOT RUN` ในสภาพแวดล้อมนี้ (ไม่ได้ตั้งค่า MCP) — การตรวจ B1–B8 ใช้ OpenCode browser tool + สคริปต์ Playwright/Edge headless เพื่อจับภาพ/วัด layout โดยระบุวิธีชัดเจนใน `docs/validation.md`

## สิ่งที่ทำได้

### Lab 3 (คงไว้เดิม)
- คำนวณ DC Operating Point เชิงวิเคราะห์ 3 โหมด: `Voltage Divider`, `Fixed Bias`, `Emitter Bias`
- แสดง `IB, IC, IE, VB, VE, VC, VCE, VBC`, region, warning, validation แบบ field-level
- ชุดทดสอบ Lab 3 เดิมยังผ่าน (รวม 76 tests หลังเพิ่ม Lab 4)

### Lab 4 (เพิ่มใหม่)
- **ngspice engine จริง** ผ่าน `subprocess.run` (argument list, no `shell=True`, timeout, temp working dir ต่อรัน, `CREATE_NO_WINDOW` บน Windows)
- โหมดวิเคราะห์: **DC `.op`**, **AC `.ac`**, **Transient `.tran`**
- ฟอร์มรับค่าอุปกรณ์/แหล่งสัญญาณ: `VCC, R1, R2, RC, RE, RL, Cin, Cout, source amplitude (mV peak), frequency (Hz)` พร้อมหน่วย
- แสดงผลแยกชัดเจน: `ngspice result` vs `Analytical reference (Lab 3, β=100, VBE=0.7V)`
- กราฟ SVG ในหน้าเว็บ (ไม่มี CDN): Bode magnitude/phase, transient waveform
- Error handling จริง: input validation, ngspice not found, parse/run error, stale result clearing
- แสดง provenance: engine version, model, run status, timestamp, netlist ที่สร้างจริง

## วงจรอ้างอิง (Reference CE)

ค่าเริ่มต้นตามโจทย์:
- `VCC=12V, R1=100kΩ, R2=22kΩ, RC=2.2kΩ, RE=1kΩ, RL=10kΩ`
- `Cin=10µF, Cout=10µF`, source `10 mV peak, 1 kHz`
- NPN model: `T2N2222` (generic educational model; โปรไฟล์อิงจากตัวอย่าง ngspice `examples/noise/bipolar-noise.cir`, `BF=150` — **ไม่ใช่ kit/model เฉพาะของผู้สอน**)

## การติดตั้ง

### 1) Python env
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2) ติดตั้ง ngspice
ต้องมี `ngspice` (แนะนำ ngspice 47)

**วิธี A — ใช้ PATH ระบบ**  
ติดตั้ง ngspice แล้วให้คำสั่ง `ngspice_con`/`ngspice` หาได้จาก PATH

**วิธี B — ตั้ง `NGSPICE_BIN`**  
ชี้ไปที่ executable โดยตรง เช่น `ngspice_con.exe`

```powershell
$env:NGSPICE_BIN="C:\path\to\Spice64\bin\ngspice_con.exe"
```

**วิธี C — วาง portable ใน repo (gitignored)**  
วางไว้ที่ `tools/ngspice47/.../ngspice_con.exe` (repo มี `.gitignore` สำหรับ `tools/`)

แอปจะค้นหาแบบ: `NGSPICE_BIN` → `tools/ngspice47/**/ngspice_con(.exe)` → PATH

## รันแอป

```powershell
.venv\Scripts\python.exe -m flask --app app run --debug
```
เปิด <http://127.0.0.1:5001/>

> Flask dev server ใช้สำหรับพัฒนา/ทดสอบในเครื่องเท่านั้น

## รันเทสต์

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

ผลล่าสุด: **Ran 76 tests in ~0.55s — OK** (รวม integration tests ที่ใช้ ngspice จริง; บาง test จะ skip ถ้าไม่พบ ngspice)

## โครงสร้างสำคัญ

```
app.py                 # Flask routes: /, /calculate, /api/engine, /api/simulate
dc_bias.py             # Lab 3 analytical DC bias (3 modes)
spice_engine.py        # ngspice adapter: validation, netlist, run, parse, errors
templates/index.html    # UI (Lab 4 simulator + Lab 3 form)
static/app.js          # Frontend logic, SVG charts, fetch, stale-result clearing
static/style.css       # Responsive styling
tests/                 # unittest: dc_bias, web, spice_engine, simulate_web
docs/validation.md     # B1-B8 evidence and acceptance record
docs/evidence/         # Screenshots / run artifacts
```

## พฤติกรรมสำคัญ / ข้อจำกัด

- **AC normalization**: `.ac` รันด้วยแหล่ง `AC 1` เพื่อให้อ่าน gain ได้ตรงจาก `V(out)/V(in)`; **amplitude ที่กรอกมีผลกับ `.tran` เท่านั้น** (แสดงหมายเหตุใน UI)
- **AC sweep**: กวาด `1 Hz – 1 GHz` (`dec 20`) เพื่อให้เห็นพฤติกรรม high-frequency ของโมเดล; upper −3 dB อาจอยู่นอกย่าน midband ที่คาดจากสูตรง่ายหรือถูกจำกัดโดย parasitic ของโมเดล
- **Analytical reference**: ใช้สมการ Lab 3 แบบ ideal/BJT large-signal simple model (`β=100`, `VBE=0.7V`, ไม่รวม Early/capacitance/load effect แบบ SPICE) ดังนั้นค่า SPICE กับ analytical **ต่างกันได้** และแสดง delta ให้เห็น
- **Transient summary**: วัดจากช่วงหลังเริ่มต้น (steady-state window) เพื่อเลี่ยง startup transient
- **Model provenance**: `T2N2222` เป็นโมเดล generic เพื่อการศึกษา ไม่ใช่ part เฉพาะจาก kit ผู้สอน; ผลเชิงตัวเลขควรตีความร่วมกับข้อจำกัดโมเดล
- **ไม่ hardcode ผลสำเร็จ**: กราฟ/ตารางสร้างจากผลรันจริง; ถ้า engine fail/invalid input จะล้างผลเก่าและแสดง error

## B1–B8 สรุป (รายละเอียดใน `docs/validation.md`)

| Case | Status | หมายเหตุ |
|---|---|---|
| B1 Regression Lab 3 | PASS | Divider/Fixed/Emitter คำนวณและสลับโหมดได้ |
| B2 DC SPICE `.op` | PASS | ได้ค่า VB/VE/VC/VCE/IC/IB จาก ngspice จริง |
| B3 Change RE | PASS | RE 1k→2k ทำให้ IC ลด, VCE เปลี่ยน |
| B4 AC Bode | PASS | มี magnitude/phase/frequency จากรันจริง |
| B5 Transient 10mV/1kHz | PASS | เห็น Vin/Vout, กลับเฟส, คาบเวลา |
| B6 Change source | PASS | 20mV/2kHz เปลี่ยน waveform/ช่วงเวลา |
| B7 Invalid/fail | PASS | RE=0 error ชัด, ไม่ค้างผลเก่า; ngspice-missing แสดง error จริง |
| B8 UI desktop/mobile | PASS | ตรวจ 1280px และ 390px, ไม่ล้นแนวนอน |

## AI assistance / สิ่งที่นักศึกษาต้องตรวจ

- AI ช่วย: ร่างโค้ด, parser, UI, เทสต์, รัน browser automation เก็บหลักฐาน
- นักศึกษาตรวจ: อ่าน netlist/สมการ/ผลที่ได้, รันซ้ำในเครื่องตัวเอง, ตรวจว่า commit SHA ตรงกับงานที่ส่ง, และยืนยันว่าหลักฐานเป็นผลรันจริง (ไม่ใช่ mock/hardcode)
