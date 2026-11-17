# Design Note — BJT DC Bias Web App

## ภาพรวม

Web Application หลายไฟล์ที่แยก "สมการวิศวกรรม" ออกจาก "HTTP/UI" อย่างชัดเจน
ผู้ใช้เลือกโหมดไบอัส (Voltage Divider / Fixed / Emitter) กรอกค่าอุปกรณ์
แล้วกด **Calculate DC Bias** ระบบส่งค่าไปยัง Flask ซึ่งเลือกฟังก์ชันตาม
`mode` แปลงหน่วย ตรวจเฉพาะช่องที่โหมดนั้นใช้ และคำนวณด้วย Python จากนั้น
ตอบกลับเป็น JSON ให้ JavaScript วาดผลโดยไม่ reload หน้า

```
Browser (form: mode + ค่าอุปกรณ์)
   │  fetch POST /calculate (FormData)
   ▼
app.py  ── HTTP layer ──► parse_inputs(raw, mode)  ──►  if   mode == "divider": calculate_dc_bias()
   │                                                   elif mode == "fixed":   calculate_fixed_bias()
   │                                                   elif mode == "emitter": calculate_emitter_bias()
   │                                                   else: HTTP 400 errors["mode"]
   └──────────── JSON (SI units + mode) ◄──────────────┘
   ▼
static/app.js  → สลับช่องตามโหมด → จัดรูปแบบหน่วย (mA/µA/kΩ) → แสดงผล
```

## เหตุผลการแยกไฟล์

| ไฟล์ | เหตุผล |
|---|---|
| `dc_bias.py` | สมการเป็นความรู้ทางวิศวกรรม ต้องเทสต์ได้โดยไม่ต้องมี Flask — มีฟังก์ชันแยกต่อโหมดและใช้ซ้ำกับ CLI/โน้ตบุ๊กได้ |
| `app.py` | เปลี่ยนเฉพาะเมื่อสัญญา HTTP เปลี่ยน; ทำหน้าที่เลือกฟังก์ชันและ serialize เท่านั้น ไม่มีสมการ |
| `templates/index.html` | เป็นเพียงโครงฟอร์ม + `data-modes` บอกว่าช่องใดใช้กับโหมดใด ไม่มีทั้งสมการและค่าคงที่ของผลลัพธ์ |
| `static/app.js` | รับผิดชอบเฉพาะการแสดงผล การซ่อน/ปิดช่อง และสถานะ UI — ไม่คำนวณ DC bias |
| `tests/` | แยกเทสต์ logic (เร็ว) ออกจากเทสต์ HTTP (ตรวจ contract) |

## สัญญาข้อมูล (Data Contract)

- Request: `application/x-www-form-urlencoded`
  - ร่วมทุกโหมด: `mode, vcc, rc, rc_unit, beta, vbe`
  - Divider: `r1, r1_unit, r2, r2_unit, re, re_unit`
  - Fixed: `rb, rb_unit`
  - Emitter: `rb, rb_unit, re, re_unit`
  - ช่องที่ไม่เกี่ยวกับโหมดจะถูก `disabled` จึงไม่ถูกส่งมา และฝั่ง Python
    จะไม่ parse ช่องนั้น (ค่าขยะในช่องที่ซ่อนอยู่จึงไม่ทำให้เกิด error)
- Response สำเร็จ: `{ok: true, data: {mode, inputs_si, intermediate, operating_point, region, warnings}}`
  - `intermediate` = `{vth_v, rth_ohm}` สำหรับ Divider, `{}` สำหรับ Fixed/Emitter
- Response ผิดพลาด: HTTP 400 + `{ok: false, mode, errors: {field: message}, message}`
  - `mode` ส่งกลับทั้งกรณีสำเร็จและผิดพลาด เพื่อให้ UI ระบุโหมดได้เสมอ
- ค่าตัวเลขใน JSON เป็น SI base units เสมอ; หน่วยที่แสดงผลเป็นความรับผิดชอบของ UI

## การตัดสินใจสำคัญ

1. **เลือก JSON API + fetch แทนการ render ฝั่ง server** เพื่อให้แสดงผลได้ละเอียด
   และต่อยอด AC/knob ในสัปดาห์ถัดไปโดยไม่ต้องรื้อโครง
2. **แยกฟังก์ชันคำนวณต่อโหมด** (`calculate_dc_bias`, `calculate_fixed_bias`,
   `calculate_emitter_bias`) ตามที่ใบงานกำหนด แล้วใช้ `_assemble()` ร่วมกัน
   เฉพาะขั้นตอนพีชคณิตท้ายน้ำ (IC, IE, VE, VB, VC, VCE, VBC) — สมการกระแส Base
   ของแต่ละโหมดยังแยกกันชัดเจนและตรวจง่าย
3. **`app.py` เลือกฟังก์ชันด้วย `if/elif`** ตาม `mode`; โหมดที่ไม่รู้จักได้
   HTTP 400 + `errors["mode"]` — ไม่มี fallback เงียบ ๆ ไปเป็น Divider
   - ไม่ส่ง `mode` มาเลย (client เดิม/Lab 02) → ใช้ `divider`
   - ส่ง `mode` มาแต่เป็นค่าว่างหรือช่องว่าง → HTTP 400 + `errors["mode"]`
4. **`parse_inputs(raw, mode="divider")`** ตรวจเฉพาะช่องของโหมดนั้น
   (ค่า default `divider` ทำให้ผู้เรียกเดิมและเทสต์เดิมไม่ต้องแก้)
   คีย์ error ใช้ชื่อฟิลด์ฐาน (`rb` ไม่ใช่ `rb_unit`)
5. **Warning ไม่ใช่ Error** — เกณฑ์ Lab 03 คือ `IB ≤ 0` → Cutoff และ
   `VCE ≤ 0.2 V` → Saturation ผู้ใช้ยังเห็นตัวเลขแต่มีป้ายบอกว่าแบบจำลอง
   ใช้ไม่ได้/ไม่แม่นยำ (Lab 02 เดิมใช้ `VTH ≤ VBE` และ `VCE < 0.3 V`;
   สำหรับ Divider `IB ≤ 0` สมมูลกับ `VTH ≤ VBE` เพราะตัวส่วนเป็นบวกเสมอ)
6. **UI ซ่อนและ `disabled` ช่องที่ไม่ใช้** เพื่อให้ FormData มีเฉพาะค่าที่โหมด
   นั้นต้องการ และเรียก `resetMessages()` ทุกครั้งที่เปลี่ยนโหมด/ก่อน submit
   เพื่อไม่ให้ผลของรอบก่อนค้างอยู่เมื่อรอบใหม่ผิดพลาด พร้อมปิด dropdown โหมด
   ระหว่างรอผล (`setBusy`) กันคำตอบเก่ามาวาดทับสถานะใหม่
7. **การ์ด JSON contract** — `Infinity`/`NaN` ไม่ใช่ JSON ที่ถูกต้อง จึงตรวจ
   ค่าหลังแปลงหน่วยใน `parse_inputs` และตรวจผลลัพธ์ทุกค่าหลังคำนวณใน `app.py`;
   ถ้าล้นจะตอบ HTTP 400 พร้อม `mode` แทนการส่ง JSON ที่ `response.json()`
   ฝั่งเบราว์เซอร์ parse ไม่ได้ (ซึ่งจะทำให้ผู้ใช้เข้าใจผิดว่าเซิร์ฟเวอร์ล่ม)

## ข้อจำกัดที่รู้ตัว

- ไม่รองรับ Early effect, β ที่แปรตามกระแส, หรืออุณหภูมิ
- ไม่มีการจำลอง SPICE; ค่าที่ได้เป็นผลของสมการ Forward-Active เท่านั้น
- การสลับช่องตามโหมดพึ่ง JavaScript (มี `<noscript>` แจ้งเตือนแล้ว)
- ยังไม่มี authentication/ฐานข้อมูล เพราะอยู่นอกขอบเขต Lab
