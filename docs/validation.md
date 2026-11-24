# Validation — Lab 04 BJT CE Amplifier Simulator

เอกสารนี้บันทึกผลตรวจรับ **B1–B8** สำหรับ Lab 04 (ต่อยอดจาก Lab 3) ตามโจทย์ `Lab04_BJT_Amplifier_Simulator_2-2569`.

## สภาพแวดล้อมที่ตรวจ

| รายการ | ค่า |
|---|---|
| วันที่ตรวจ | 2026-11-24 (local run) |
| App URL | `http://127.0.0.1:5001/` (Flask dev server) |
| Python | 3.14.3 (`.venv`) |
| Flask | 3.1.3 |
| ngspice | **ngspice-47** (portable, `tools/ngspice47/Spice64/bin/ngspice_con.exe`) |
| BJT model | **T2N2222** (generic NPN; profile from ngspice example `examples/noise/bipolar-noise.cir`, `BF=150`) — ไม่ใช่ model เฉพาะของ kit ผู้สอน |
| Browser automation | **Playwright MCP: NOT RUN** (ไม่ได้ตั้งค่าใน harness). ใช้ OpenCode browser tool + Playwright-core + Edge channel (headless) รันสคริปต์เก็บภาพ/วัด layout จริง |
| Test command | `.venv\Scripts\python.exe -m unittest discover -s tests -v` |
| Test result | **Ran 76 tests in 0.548s — OK** |

## วิธีตรวจ

1. เปิดหน้าเว็บจริงที่ Flask local และรอ `engine badge = ngspice-47 · T2N2222`
2. กรอกค่า/เลือกโหมดตามแต่ละ case แล้วกดรันจริง
3. อ่านค่าจาก DOM (`#results`, `#sim-summary`, `#sim-tables`, `#sim-errors`, netlist)
4. เทียบกับค่าอ้างอิงเชิงสมการ/พฤติกรรมที่คาด และตรวจความสอดคล้องกับ ngspice output ที่แสดงใน UI
5. เก็บ screenshot และบันทึกผลเป็น PASS/FAIL/NOT RUN พร้อมหลักฐาน

> หมายเหตุ: Screenshot อย่างเดียวไม่พอเป็นหลักฐานเชิงตัวเลข — ทุก case ที่ PASS มีค่าที่อ่านได้จริงจากหน้าเว็บหรือผลรันจริงประกอบ

## ตารางผล B1–B8

| Case | Method | Input / Action | Expected / Reference | Observed (จริง) | Evidence | Status |
|---|---|---|---|---|---|---|
| B1 · Regression Lab 3 | Browser automation (Playwright-core/Edge headless) + DOM read | เลือก Divider/Fixed/Emitter ในฟอร์ม Lab 3 แล้วคำนวณชุดค่ามาตรฐาน | ผล Lab 3 ตรงค่าอ้างอิงและสลับโหมดได้ | Divider: `IC 1.230 mA, VCE 8.052 V, VTH 2.164 V, RTH 18.03 kΩ`. Fixed: `IB 11.300 µA, IC 1.130 mA, VCE 9.514 V, VE 0 V`. Emitter: `IB 10.263 µA, IC 1.026 mA, VCE 8.705 V, VE 1.037 V` | `docs/evidence/b1-divider.png`, `docs/evidence/run-output.json` | **PASS** |
| B2 · DC SPICE `.op` | Browser run + DOM read + netlist provenance | กด Run ngspice โหมด DC บนวงจรอ้างอิง | แสดง VB/VE/VC/VCE/IC จาก ngspice จริง, มี model/run status/netlist | `IC 1.321 mA, VCE 7.762 V, IB 10.251 µA, VBE 647.746 mV` (summary). ตารางเปรียบเทียบแสดง VB/VE/VC/VCE/IC/IB/IE เทียบ analytical และ delta. Netlist แสดง `Q1 ... T2N2222` + `.model T2N2222 ...` + `.op/.print op @q1[ic] @q1[ib] @q1[ie]` | `docs/evidence/b2-dc.png`, `docs/evidence/b2-netlist.png` | **PASS** |
| B3 · Change RE | Browser run เปรียบเทียบก่อน/หลัง | เปลี่ยน `RE` จาก `1 kΩ` เป็น `2 kΩ` แล้วรัน DC ซ้ำ | Operating point เปลี่ยนตามกฎ bias (RE เพิ่ม → IC ลด) ไม่ใช่ค่าค้าง | RE=1k: `IC 1.321 mA, VCE 7.762 V`. RE=2k: `IC 711.291 µA, VCE 9.008 V, IB 5.686 µA, VBE 630.761 mV` | `docs/evidence/b3-re-2k.png`, `docs/evidence/run-output.json` | **PASS** |
| B4 · AC Bode | Browser run + chart/table read | โหมด AC, baseline RE=1k, กวาดความถี่ | ได้ magnitude/phase/frequency จากรันจริง พร้อมหน่วย/จุดตัด −3 dB | `Gain @1kHz = +4.87 dB (1.752 V/V), Phase = -179.9°`, `Lower -3dB = 1.803 Hz`, `Upper -3dB = 33.603 MHz`, sweep `1 Hz–100 MHz` ในตาราง | `docs/evidence/b4-ac-charts.png`, `docs/evidence/b4-ac-table.png` | **PASS** |
| B5 · Transient | Browser run + chart read | `.tran`, `10 mV peak, 1 kHz`, RE=1k | เห็น Vin/Vout ตามเวลา, กลับเฟส, มีหน่วยเวลา/แรงดัน | `Vin(pp)=19.999 mV, Vout(pp)=35.048 mV, Gain=1.752, เฟสกลับเฟส (~180°), ช่วงเวลา 5.00 ms, 1,008 จุด` | `docs/evidence/b5-tran-10mv-1khz.png` | **PASS** |
| B6 · Change source | Browser run เปรียบเทียบกับ B5 | เปลี่ยน source เป็น `20 mV peak, 2 kHz` แล้วรัน transient ซ้ำ | Waveform/สเกลเปลี่ยนตามค่าที่ตั้ง ไม่ใช่กราฟ hard-code | `Vin(pp)=39.998 mV, Vout(pp)=70.096 mV, Gain=1.752, กลับเฟส (~180°), ช่วงเวลา 2.50 ms, 1,008 จุด` (gain คงที่ใกล้เคียงแต่ amplitude/frequency/time window เปลี่ยน) | `docs/evidence/b6-source-20mv-2khz.png` | **PASS** |
| B7 · Invalid / fail | Browser run (input invalid) + browser run (engine missing) | (a) ใส่ `RE=0` แล้ว Run DC; (b) ปิด ngspice ชั่วคราวแล้ว reload/run | แจ้ง error ชัด, ไม่ค้างผลสำเร็จปลอม | (a) `กรุณาตรวจสอบค่าที่ป้อน`, field `RE ต้องไม่น้อยกว่า 1`, `resultsHidden=true`, placeholder แจ้งให้แก้ไข. (b) badge `ไม่พบ ngspice`, error บอกให้ติดตั้ง/ตั้ง `NGSPICE_BIN`, `resultsHidden=true` (ทดสอบด้วยการ rename tools/ngspice47 ชั่วคราวแล้ว restore) | `docs/evidence/b7-invalid-re0.png`; ngspice-missing ตรวจใน session (ข้อความ/สถานะบันทึกตามจริง) | **PASS** |
| B8 · UI responsive | Playwright-core/Edge headless วัด layout + screenshots | Desktop 1280×900 และ Mobile 390×844; รัน DC/AC | กราฟ/หน่วย/ปุ่มอ่านง่าย ไม่มี overflow แนวนอนสำคัญ | Desktop: `innerWidth=1280, scrollWidth=1280, overflowX=0, columns=430px 710px`. Mobile: `innerWidth=390, scrollWidth=390, overflowX=0, charts 302x173, buttonWidth=328, buttonVisible=true` | `docs/evidence/b8-desktop-dc.png`, `docs/evidence/b8-mobile-ac.png`, `docs/evidence/b8-mobile-dc.png`, `docs/evidence/b8-desktop-1280.png` | **PASS** |

## หลักฐานเชิงตัวเลข (สรุป)

- **B2 (.op)**: `IC=1.321194 mA, IB=10.25072 µA, VCE=7.762226 V, VB=1.979097 V, VE=1.331445 V, VC=9.093671 V` (จาก ngspice; UI แสดงค่าปัดอ่านง่าย)
- **B4 (.ac, RE=1k)**: `+4.873 dB (1.752483 V/V) @1kHz`, phase `-179.874°`, lower `1.803 Hz`, upper `33.603 MHz`
- **B5 (.tran, 10mV/1kHz)**: `Vin pp 19.999 mV, Vout pp 35.048 mV, gain 1.7525, corr -1.0, inverted`
- **B6 (.tran, 20mV/2kHz)**: `Vin pp 39.998 mV, Vout pp 70.096 mV, gain 1.7525, corr -1.0, 2.5 ms window`

## ข้อสังเกต / ข้อจำกัด

- **AC upper −3 dB** ขึ้นกับโหลด/โมเดล parasitic และช่วง sweep; ที่ RE=1k พบ upper cutoff ในช่วง sweep แต่ที่ RE=2k gain peak ต่ำกว่า midband reference ทำให้ upper cutoff ไม่ถูกประกาศในช่วงที่ทดสอบ (กรณีนี้เป็นพฤติกรรมจริงจากข้อมูล ไม่ใช่การซ่อน error)
- **Analytical vs SPICE ต่างกันได้** เพราะ analytical ใช้ `β` คงที่และ `VBE=0.7V` ส่วน SPICE ใช้ non-linear model
- **Playwright MCP ไม่ได้รัน** ตามข้อจำกัดเครื่องมือ; หลักฐาน browser เป็นการรันจริงผ่าน browser automation อื่นและบันทึกไว้อย่างตรงไปตรงมา
- **B7 ngspice-missing** ทดสอบโดย rename โฟลเดอร์ `tools/ngspice47` ชั่วคราวแล้ว restore; เป็นการจำลอง engine unavailable ตามที่ยอมรับได้เมื่อไม่ได้เปลี่ยนระบบติดตั้งจริงของเครื่อง

## คำสั่งทดสอบ

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m unittest discover -s tests -v
# Ran 76 tests in 0.548s — OK
```