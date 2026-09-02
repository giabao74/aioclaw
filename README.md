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
| **`DISCORD_BOT_TOKEN`** | Token bot Discord của bạn *(kết thúc bằng `N-68`)* |
| **`OWNER_ID`** | `1262304052361035857` |
| **`AIO_GATEWAY_URL`** | `https://aegix-claw.prmgvyt.xyz` *(hoặc link direct của HF)* |
| **`MASTER_OWNER_KEY`** | `Iamprmgvyt2013@` |
| **`BOT_PREFIX`** | `.` |
| **`SFTP_HOST`** | `theo.hidencloud.com` |
| **`SFTP_PORT`** | `2022` |
| **`SFTP_USER`** | `prmgvyt-109674.e22ee400` |
| **`SFTP_PASS`** | `Iamprmgvyt2013@` |

5. Bấm **Create Web Service**.

---

### ⚙️ Tính năng Quản lý Token & Lịch trình:
- **Tự động Auto Gen Key:** Chạy ngầm định kỳ vào mỗi **Thứ 2, Thứ 4, Thứ 6 lúc 00:00 (Giờ Việt Nam)**:
  1. Tự sinh API Key mới `aio_sec_...`
  2. Ghi đè file `apitoken.js` trên HidenCloud qua SFTP
  3. Gửi DM riêng cho Owner (`1262304052361035857`) với Embed báo cáo chi tiết!
- **Lệnh Discord:**
  - `.testkey`: Chạy thử chu trình gen key, kiểm tra SFTP và gửi DM báo cáo (không làm thay đổi file `apitoken.js` chính).
  - `.genkey`: Xoay key thật ngay lập tức, đẩy SFTP vào `apitoken.js` và gửi DM báo cáo.
  - `.status`: Kiểm tra ping Discord, ping SFTP HidenCloud, giờ Việt Nam hiện tại và lần xoay key kế tiếp.

