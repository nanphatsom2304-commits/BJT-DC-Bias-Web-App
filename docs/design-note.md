# Design Note — BJT DC Bias Web App

## ภาพรวม

Web Application หลายไฟล์ที่แยก "สมการวิศวกรรม" ออกจาก "HTTP/UI" อย่างชัดเจน
ผู้ใช้กรอกค่าอุปกรณ์ใน Browser แล้วกด **Calculate DC Bias** ระบบส่งค่าไปยัง
Flask ซึ่งแปลงหน่วย ตรวจสอบ และคำนวณด้วย Python จากนั้นตอบกลับเป็น JSON
ให้ JavaScript วาดผลโดยไม่ reload หน้า

```
Browser (form)
   │  fetch POST /calculate (FormData)
   ▼
app.py  ── HTTP layer ──► parse_inputs() ──► calculate_dc_bias()
   │                                            │
   └──────────── JSON (SI units) ◄──────────────┘
   ▼
static/app.js  → จัดรูปแบบหน่วย (mV/mA/µA/kΩ) → แสดงผล
```

## เหตุผลการแยกไฟล์

| ไฟล์ | เหตุผล |
|---|---|
| `dc_bias.py` | สมการเป็นความรู้ทางวิศวกรรม ต้องเทสต์ได้โดยไม่ต้องมี Flask — ใช้ซ้ำกับ CLI/โน้ตบุ๊กได้ |
| `app.py` | เปลี่ยนเฉพาะเมื่อสัญญา HTTP เปลี่ยน; ไม่มีสมการอยู่เลย |
| `templates/index.html` | เป็นเพียงโครงฟอร์ม ไม่มีทั้งสมการและค่าคงที่ของผลลัพธ์ |
| `static/app.js` | รับผิดชอบเฉพาะการแสดงผลและสถานะ UI |
| `tests/` | แยกเทสต์ logic (เร็ว) ออกจากเทสต์ HTTP (ตรวจ contract) |

## สัญญาข้อมูล (Data Contract)

- Request: `application/x-www-form-urlencoded` มี `vcc, r1..re, *_unit, beta, vbe`
- Response สำเร็จ: `{ok: true, data: {inputs_si, intermediate, operating_point, region, warnings}}`
- Response ผิดพลาด: HTTP 400 + `{ok: false, errors: {field: message}, message}`
- ค่าตัวเลขใน JSON เป็น SI base units เสมอ; หน่วยที่แสดงผลเป็นความรับผิดชอบของ UI

## การตัดสินใจสำคัญ

1. **เลือก JSON API + fetch แทนการ render ฝั่ง server** เพื่อให้แสดงผลได้ละเอียด
   และต่อยอด AC/knob ในสัปดาห์ถัดไปโดยไม่ต้องรื้อโครง
2. **ให้ `dc_bias.py` เป็นเจ้าของการแปลงหน่วยและ validation** เพื่อให้กฎ
   วิศวกรรมอยู่ที่เดียวและเทสต์ได้โดยไม่พึ่ง Flask
3. **คีย์ error ใช้ชื่อฟิลด์ฐาน** (`r1` ไม่ใช่ `r1_unit`) ทำให้ UI มีช่อง error
   หนึ่งช่องต่อแถว และทดสอบได้ง่าย
4. **Warning ไม่ใช่ Error** สำหรับ Cutoff/Saturation — ผู้ใช้ยังเห็นตัวเลขและ
   หน่วย แต่มีป้ายบอกว่าแบบจำลองใช้ไม่ได้/ไม่แม่นยำ

## ข้อจำกัดที่รู้ตัว

- ไม่รองรับ Early effect, β ที่แปรตามกระแส, หรืออุณหภูมิ
- ไม่มีการจำลอง SPICE; ค่าที่ได้เป็นผลของสมการ Forward-Active เท่านั้น
- ยังไม่มี authentication/ฐานข้อมูล เพราะอยู่นอกขอบเขต Lab 2
