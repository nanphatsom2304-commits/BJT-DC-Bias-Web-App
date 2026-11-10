# AGENTS.md — กติกาสำหรับ AI Coding Agent

โปรเจกต์นี้เป็นงาน Lab ของรายวิชา ENG29 2121 นักศึกษาเป็นเจ้าของงานและเป็น
ผู้รับผิดชอบการตรวจสอบทั้งหมด

## กติกาที่ห้ามละเมิด

1. **ห้ามรัน `git commit` หรือ `git push` แทนนักศึกษา** — นักศึกษา commit
   ผ่าน GitHub Desktop เท่านั้น (agent อาจตรวจ `git status` / `git diff` ได้)
2. **ห้าม hardcode ผลลัพธ์ DC Bias** ลงใน HTML/JS/เทมเพลต ทุกค่าต้องมาจาก
   `calculate_dc_bias()` ใน `dc_bias.py`
3. **ห้ามใส่ secret** (API key, token, password) ลงในไฟล์ที่ commit;
   ห้าม commit `.venv/`, `__pycache__/`, `.env`
4. **รักษาการแยกชั้น**: `dc_bias.py` ต้องไม่ import Flask/Jinja/HTTP;
   `app.py` ทำหน้าที่ HTTP เท่านั้น; `app.js` ไม่คำนวณ DC bias
5. **ห้ามเขียนคำตอบใน `docs/reflection.md`** — เป็นคำถามรายบุคคล นักศึกษาเขียนเอง

## ก่อนบอกว่างานเสร็จ

- รัน `.venv\Scripts\python.exe -m unittest discover -s tests -v` และอ่านผลจริง
- ถ้าแก้สมการหรือ validation ต้องมี test ที่ล้มเหลวก่อนแก้ (TDD)
- รายงานผลด้วย output จริง ไม่ใช่คำว่า "น่าจะผ่าน"

## รูปแบบโค้ด

- Python: มาตรฐาน PEP 8, ฟังก์ชันสั้น, type hints, ข้อความ error ภาษาไทย
- ตัวเลขใน JSON เป็น SI base units (V, A, Ω); การจัดรูปแบบทำที่ `app.js`
- CSS/JS: vanilla ไม่มี dependency ภายนอก
