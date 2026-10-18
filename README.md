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
| **`BOT_PREFIX`** | `?` |
| **`OPENROUTER_API_KEY`** | *(Tùy chọn)* Key OpenRouter để mở khóa **GPT-OSS 120B** & **Llama 3.3 70B** miễn phí (lấy tại `openrouter.ai/keys`) |
| **`DEFAULT_AI_MODEL`** | `openai/gpt-oss-120b:free` *(hoặc `meta-llama/llama-3.3-70b-instruct:free`)* |
| **`TURSO_DATABASE_URL`** | `libsql://ai-claw-iamprmgvyt.aws-ap-northeast-1.turso.io` |
| **`TURSO_AUTH_TOKEN`** | Token Turso DB của bạn *(đã tích hợp sẵn)* |
| **`SFTP_HOST`** | `theo.hidencloud.com` |
| **`SFTP_PORT`** | `2022` |
| **`SFTP_USER`** | `prmgvyt-109674.e22ee400` |
| **`SFTP_PASS`** | `Iamprmgvyt2013@` |

5. Bấm **Create Web Service**.

---

### ⏰ Tính năng Tự Động Nhắc Nhở & Gia Hạn Dịch Vụ (Turso Cloud DB):
- **Cơ sở dữ liệu đám mây Turso:** Lưu trữ danh sách dịch vụ HidenCloud (`h1`, `h2`, `h3`, `h4`, `h5`), OptikLink và Duolingo.
- **Tự động quét & Gửi DM:** Khi một dịch vụ còn **dưới 1.5 ngày** trước khi hết hạn (Next Invoice Date), bot sẽ tự động gửi DM riêng cho Owner:
  - Nút bấm `🔗 Mở trang quản lý`: Dẫn thẳng tới dashboard dịch vụ trên HidenCloud/OptikLink.
  - Nút bấm `✅ Đã gia hạn (+7 ngày)`: Tự động cộng thêm +7 ngày vào database Turso và cập nhật trạng thái ngay trên Discord!
- **Nhắc nhở học Duolingo:** Nhắc học hàng ngày lúc 20:00 VN để bảo vệ ngọn lửa Streak.
- **Lệnh quản lý gia hạn:**
  - `?reminder`: Xem bảng theo dõi tất cả dịch vụ, ngày hết hạn và menu dropdown gia hạn nhanh (+7 ngày).
  - `?done <id>`: Xác nhận gia hạn nhanh cho dịch vụ (VD: `?done h2` ➜ cộng +7 ngày).
  - `?duolingo`: Xem trạng thái học Duolingo và xác nhận Streak.
  - `?checkreminders`: Chạy quét kiểm tra ngay lập tức và gửi DM nếu có dịch vụ sắp hết hạn.
  - `?addservice`: Thêm hoặc chỉnh sửa dịch vụ mới vào database.
  - `?help`: Bảng trợ giúp tự động nạp tất cả các lệnh hiện có của bot.


