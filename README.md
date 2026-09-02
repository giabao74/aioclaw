# 🦅 AIClaw Discord Bot — Render.com Edition

Bot Discord chuyên trách cho hệ thống **AIClaw Unified Security Shield**:
- **Hosting:** Render.com (Gói Web Service Free 100%)
- **Mạng:** Mở 100%, không bị chặn cổng Discord (Zero `ConnectionResetError`)
- **Kết nối AI:** Gọi trực tiếp cụm AI trên Hugging Face (`https://aegix-claw.prmgvyt.xyz`)

---

## 🚀 Hướng dẫn triển khai lên Render trong 2 phút

### Bước 1: Tạo Git Repo
Tải toàn bộ thư mục `aio-claw-render` này lên một GitHub repository mới (có thể để Private hoặc Public).

### Bước 2: Tạo Web Service trên Render.com
1. Đăng nhập [render.com](https://dashboard.render.com).
2. Bấm **New +** ➜ chọn **Web Service**.
3. Chọn Repository GitHub vừa tạo.
4. Điền các thông số:
   - **Name:** `aiclaw-bot`
   - **Language:** `Python 3`
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** `Free`

### Bước 3: Cấu hình Environment Variables (Biến môi trường)
Cuộn xuống phần **Environment Variables**, thêm các biến sau:

| Tên biến | Giá trị |
| :--- | :--- |
| **`DISCORD_BOT_TOKEN`** | Token bot Discord của bạn (lấy từ Discord Dev Portal) |
| **`OWNER_ID`** | `1262304052361035857` |
| **`AIO_GATEWAY_URL`** | `https://aegix-claw.prmgvyt.xyz` (hoặc `https://prmgvyt-aegix-claw.hf.space`) |
| **`MASTER_OWNER_KEY`** | `Iamprmgvyt2013@` |
| **`BOT_PREFIX`** | `.` |

5. Bấm **Deploy Web Service**.

---

### 🎉 Kết quả
Sau 1-2 phút build, Render sẽ cấp link Web Service và bot Discord sẽ **Online 🟢 ngay lập tức**, đồng thời tự động gửi 1 tin nhắn DM xác nhận vào Discord của bạn!
