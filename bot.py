# -*- coding: utf-8 -*-
"""
🦅 AI CLAW DISCORD BOT — Render.com Web Service Edition
• 24/7 Hosting on Render.com (FastAPI Keepalive on $PORT)
• Direct unblocked connection to Discord Gateway (Zero blocks / Zero ConnectionResetError)
• Automated Key Rotation every MONDAY, WEDNESDAY, FRIDAY at 00:00 (Vietnam Time / UTC+7)
• Automated SFTP Upload to HidenCloud (theo.hidencloud.com:2022/apitoken.js)
• Instant Discord DM Notification to Owner with full telemetry report
• On-Demand Commands: .testkey (thử nghiệm) & .genkey (xoay thật)
• Powered by Hugging Face AI Gateway (https://aegix-claw.prmgvyt.xyz)
"""

import os
import sys
import time
import secrets
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import aiohttp
import discord
from discord.ext import commands, tasks
from fastapi import FastAPI
import uvicorn
import paramiko
from dotenv import load_dotenv

from turso_db import TursoDB

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("aiclaw_render_bot")

turso = TursoDB()

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", os.getenv("DISCORD_TOKEN", "MTU0MjkyMzkwODMyNjYyMTM5NQ.GAX6dL.8DNoJu5shJY3FBPTeKEzynBtQU0rvpTY3XOlzk")).strip()
OWNER_ID = int(os.getenv("NOTIFY_USER_ID", os.getenv("OWNER_ID", "1262304052361035857")))
MASTER_KEY = os.getenv("MASTER_OWNER_KEY", os.getenv("AIO_RESET_TOKEN", "Iamprmgvyt2013@")).strip()
AIO_GATEWAY_URL = os.getenv("AIO_GATEWAY_URL", "https://aegix-claw.prmgvyt.xyz").rstrip("/")
BOT_PREFIX = os.getenv("BOT_PREFIX", "?").strip()
PORT = int(os.getenv("PORT", 10000))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "1494907926815445023"))
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# SFTP Credentials (HidenCloud)
SFTP_HOST = os.getenv("SFTP_HOST", "theo.hidencloud.com")
SFTP_PORT = int(os.getenv("SFTP_PORT", 2022))
SFTP_USER = os.getenv("SFTP_USER", "prmgvyt-109674.e22ee400")
SFTP_PASS = os.getenv("SFTP_PASS", "Iamprmgvyt2013@")
SFTP_FILE = os.getenv("SFTP_FILE", "apitoken.js")

# Schedule settings (Vietnam Time UTC+7)
VN_TZ = timezone(timedelta(hours=7))
ROTATION_HOUR_VN = int(os.getenv("ROTATION_HOUR_VN", 0))  # 00:00 AM VN Time
ROTATION_DAYS_VN = [0, 2, 4]  # 0 = Thứ 2 (Mon), 2 = Thứ 4 (Wed), 4 = Thứ 6 (Fri)

# Runtime State
cached_active_key = os.getenv("AIO_API_KEY", "")
last_rotation_date_vn = ""
last_daily_digest_date_vn = ""
bot_start_time = time.time()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
HF_ROUTER_MODEL = os.getenv("HF_ROUTER_MODEL", "Qwen/Qwen2.5-72B-Instruct").strip()
current_ai_model = os.getenv("DEFAULT_AI_MODEL", "Qwen/Qwen2.5-72B-Instruct").strip()

# ──────────────────────────────────────────────
# TIME & SCHEDULER HELPERS (VIETNAM TIME UTC+7)
# ──────────────────────────────────────────────
def get_now_vn() -> datetime:
    """Returns current datetime in Vietnam Time (UTC+7)."""
    return datetime.now(VN_TZ)

def format_vn_time(dt: datetime = None) -> str:
    if dt is None:
        dt = get_now_vn()
    days_vi = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    day_name = days_vi[dt.weekday()]
    return f"{day_name}, {dt.strftime('%d/%m/%Y %H:%M:%S')} (Giờ VN)"

def calculate_next_rotation_vn(now: datetime = None) -> str:
    """Calculates the next upcoming rotation date (Mon, Wed, or Fri at ROTATION_HOUR_VN:00 VN)."""
    if now is None:
        now = get_now_vn()
    
    current = now.replace(minute=0, second=0, microsecond=0)
    for i in range(1, 14):
        candidate = current + timedelta(days=i)
        candidate = candidate.replace(hour=ROTATION_HOUR_VN)
        if candidate.weekday() in ROTATION_DAYS_VN and candidate > now:
            return format_vn_time(candidate)
    return "Thứ 2 tuần tới"

# ──────────────────────────────────────────────
# SFTP ENGINE (HIDENCLOUD)
# ──────────────────────────────────────────────
def upload_sftp_token(key: str, is_test: bool = False) -> tuple:
    """
    Connects to HidenCloud SFTP and writes apitoken.js (or apitoken_test.js for test).
    Returns (success: bool, detail: str, latency_ms: float).
    """
    t0 = time.monotonic()
    target_filename = "apitoken_test.js" if is_test else SFTP_FILE

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SFTP_HOST,
            port=SFTP_PORT,
            username=SFTP_USER,
            password=SFTP_PASS,
            timeout=10
        )
        sftp = ssh.open_sftp()

        now_str = format_vn_time()
        next_str = calculate_next_rotation_vn()
        js_content = (
            f"// Auto-generated by AIO Claw Security Rotator ({'TEST MODE' if is_test else 'PRODUCTION'})\n"
            f"// Updated: {now_str}\n"
            f"// Schedule: Thứ 2, Thứ 4, Thứ 6 lúc 00:00 (Giờ VN)\n"
            f"module.exports = {{\n"
            f"    AIO_API_KEY: \"{key}\",\n"
            f"    UPDATED_AT: \"{now_str}\",\n"
            f"    NEXT_ROTATION: \"{next_str}\"\n"
            f"}};\n"
        )

        with sftp.file(target_filename, "w") as f:
            f.write(js_content)

        sftp.close()
        ssh.close()
        latency = round((time.monotonic() - t0) * 1000, 1)
        log.info(f"✅ SFTP Uploaded to {SFTP_HOST}:{SFTP_PORT}/{target_filename} ({latency}ms)")
        return True, f"Thành công ghi file `{target_filename}` ({latency} ms)", latency
    except Exception as e:
        latency = round((time.monotonic() - t0) * 1000, 1)
        log.error(f"❌ SFTP Error ({SFTP_HOST}:{SFTP_PORT}): {e}")
        return False, f"Lỗi SFTP: {e}", latency

# ──────────────────────────────────────────────
# CORE KEY ROTATION & NOTIFICATION LOGIC
# ──────────────────────────────────────────────
async def execute_unified_rotation(is_test: bool = False, trigger_source: str = "Tự động (Lịch Thứ 2-4-6)") -> dict:
    """
    Executes key rotation:
    1. Generates test/production token
    2. Uploads via SFTP to HidenCloud
    3. Syncs with Hugging Face Gateway
    4. Sends comprehensive Discord DM to Owner
    """
    global cached_active_key
    start_time = time.monotonic()
    
    prefix_type = "aio_sec_test_" if is_test else "aio_sec_"
    new_token = f"{prefix_type}{secrets.token_hex(16)}"

    if not is_test:
        cached_active_key = new_token

    # 1. SFTP Upload to HidenCloud
    sftp_ok, sftp_msg, sftp_lat = upload_sftp_token(new_token, is_test=is_test)

    # 2. Sync to Hugging Face AI Gateway (if not test)
    hf_ok = False
    hf_msg = "Không áp dụng cho bản thử nghiệm"
    if not is_test:
        try:
            payload = {"reset_token": MASTER_KEY, "new_key": new_token, "reason": f"Auto Rotation ({trigger_source})"}
            headers = {"User-Agent": BROWSER_UA, "Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(f"{AIO_GATEWAY_URL}/api/v1/reset-token", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        hf_ok = True
                        hf_msg = "Đã đồng bộ vào bộ nhớ Hugging Face Space"
                    else:
                        hf_msg = f"HF Gateway trả về HTTP {resp.status}"
        except Exception as e:
            hf_msg = f"Lỗi kết nối HF Gateway: {e}"

    # 3. Send Discord DM to Owner
    dm_ok = False
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        if owner:
            now_vn_str = format_vn_time()
            next_rot_str = calculate_next_rotation_vn()
            color = 0xF59E0B if is_test else 0x22C55E
            title = "🧪 [THỬ NGHIỆM] TEST GENERATE KEY & SFTP" if is_test else "🔑 [TỰ ĐỘNG] ĐÃ XOAY API KEY MỚI — THỨ 2, 4, 6"

            embed = discord.Embed(
                title=title,
                description=f"Hệ thống bảo mật **AIO Claw Security Shield** vừa hoàn tất chu trình gen key!",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="🔑 API Token Mới", value=f"```{new_token}```", inline=False)
            
            sftp_status_icon = "🟢" if sftp_ok else "🔴"
            embed.add_field(name=f"{sftp_status_icon} Máy chủ SFTP (HidenCloud)", value=f"• Host: `{SFTP_HOST}:{SFTP_PORT}`\n• Trạng thái: {sftp_msg}", inline=False)
            
            if not is_test:
                hf_status_icon = "🟢" if hf_ok else "🟡"
                embed.add_field(name=f"{hf_status_icon} Cụm AI Hugging Face", value=f"• URL: `{AIO_GATEWAY_URL}`\n• Trạng thái: {hf_msg}", inline=False)

            embed.add_field(name="⏰ Thời gian thực hiện (Giờ VN)", value=f"`{now_vn_str}`", inline=True)
            embed.add_field(name="📅 Lịch xoay key kế tiếp", value=f"`{next_rot_str}`", inline=True)
            embed.add_field(name="🎯 Nguồn kích hoạt", value=f"`{trigger_source}`", inline=False)

            if is_test:
                embed.set_footer(text="⚠️ Đây là bản test kết nối. File apitoken.js chính không bị thay đổi.")
            else:
                embed.set_footer(text="Bot HidenCloud sẽ tự động nạp key mới 24/7 không gián đoạn.")

            await owner.send(embed=embed)
            dm_ok = True
            log.info(f"✅ Sent rotation DM to Owner {OWNER_ID} successfully!")
    except Exception as e:
        log.error(f"❌ Failed to send DM to owner {OWNER_ID}: {e}")

    total_time = round((time.monotonic() - start_time) * 1000, 1)
    return {
        "ok": sftp_ok,
        "is_test": is_test,
        "token": new_token,
        "sftp_ok": sftp_ok,
        "sftp_msg": sftp_msg,
        "hf_ok": hf_ok,
        "hf_msg": hf_msg,
        "dm_ok": dm_ok,
        "total_ms": total_time,
        "time_vn": format_vn_time(),
        "next_rotation_vn": calculate_next_rotation_vn()
    }

# ──────────────────────────────────────────────
# BACKGROUND WORKER (MONDAY, WEDNESDAY, FRIDAY)
# ──────────────────────────────────────────────
async def scheduler_vn_worker():
    """
    Checks every 30 seconds for Vietnam Time (UTC+7).
    Executes automated key rotation on:
    • Monday (Thứ 2)
    • Wednesday (Thứ 4)
    • Friday (Thứ 6)
    at ROTATION_HOUR_VN (default 00:00 VN Time).
    """
    global last_rotation_date_vn
    await bot.wait_until_ready()
    log.info(f"⏰ VN-Time Scheduler Worker activated: Schedule Mon/Wed/Fri at {ROTATION_HOUR_VN:02d}:00 (Giờ VN)")

    while not bot.is_closed():
        try:
            now_vn = get_now_vn()
            today_str = now_vn.strftime("%Y-%m-%d")
            weekday = now_vn.weekday()  # 0=Mon, 2=Wed, 4=Fri

            # Check if today is Mon/Wed/Fri, reached target hour, and not yet run today
            if weekday in ROTATION_DAYS_VN and now_vn.hour >= ROTATION_HOUR_VN and last_rotation_date_vn != today_str:
                days_vi = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
                day_name = days_vi[weekday]
                log.info(f"🔔 [TỰ ĐỘNG THEO LỊCH] Đến giờ xoay key ngày {day_name} ({today_str})! Đang khởi tạo...")
                last_rotation_date_vn = today_str

                # Execute rotation
                res = await execute_unified_rotation(is_test=False, trigger_source=f"Tự động định kỳ {day_name} (Giờ VN)")
                log.info(f"🎉 Auto-Rotation completed: SFTP={res['sftp_ok']}, DM={res['dm_ok']}")

        except Exception as e:
            log.error(f"Scheduler worker exception: {e}")

        await asyncio.sleep(30)

# ──────────────────────────────────────────────
# FASTAPI KEEPALIVE WEB SERVER (Render.com)
# ──────────────────────────────────────────────
app = FastAPI(title="AIClaw Render Keepalive", version="2.3.0")

@app.get("/")
@app.get("/health")
async def health_check():
    now_vn = get_now_vn()
    return {
        "status": "online",
        "service": "AIClaw Discord Bot on Render.com",
        "bot_user": str(bot.user) if bot.is_ready() else "Connecting...",
        "vietnam_time": format_vn_time(now_vn),
        "next_scheduled_rotation": calculate_next_rotation_vn(now_vn),
        "sftp_server": f"{SFTP_HOST}:{SFTP_PORT}",
        "gateway": AIO_GATEWAY_URL,
        "uptime_sec": int(time.time() - bot_start_time)
    }

# ──────────────────────────────────────────────
# DISCORD BOT CLIENT
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

@bot.event
async def on_ready():
    log.info(f"🎉 SUCCESS: AIClaw Bot logged in as {bot.user} (ID: {bot.user.id}) on Render.com!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Threats & AutoMod | .help"))
    
    # Start Scheduler Task
    asyncio.create_task(scheduler_vn_worker())

    # Initialize Turso DB Schema
    try:
        await turso.init_schema()
        log.info("✅ Turso DB schema initialized and seeded!")
    except Exception as e:
        log.error(f"Failed to initialize Turso DB: {e}")

    # Start Auto Reminder Loop
    if not auto_reminder_loop.is_running():
        auto_reminder_loop.start()

    # Initialize/Update Single Channel Reminder Message (Channel ID: 1494907926815445023)
    asyncio.create_task(update_channel_reminder_message())

    # Startup DM to Owner
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        if owner:
            embed = discord.Embed(
                title="🟢 AIClaw Bot Đã Online (Render.com)",
                description=f"Bot đã khởi động thành công trên **Render.com** và kết nối trực tiếp đến **HidenCloud SFTP** & **Hugging Face AI**!",
                color=0x22C55E,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="📅 Lịch Auto Gen Key", value="`Mỗi Thứ 2, Thứ 4, Thứ 6 lúc 00:00 (Giờ VN)`", inline=False)
            embed.add_field(name="⏰ Giờ Việt Nam hiện tại", value=f"`{format_vn_time()}`", inline=True)
            embed.add_field(name="📅 Lần xoay kế tiếp", value=f"`{calculate_next_rotation_vn()}`", inline=True)
            embed.add_field(name="🖥️ SFTP Server", value=f"`{SFTP_HOST}:{SFTP_PORT}`", inline=False)
            embed.add_field(name="Lệnh quản lý", value=f"• `{BOT_PREFIX}testkey`: Test thử nghiệm gen key + SFTP + DM\n• `{BOT_PREFIX}genkey`: Xoay key thật ngay lập tức\n• `{BOT_PREFIX}status`: Xem trạng thái hệ thống", inline=False)
            await owner.send(embed=embed)
    except Exception as e:
        log.warning(f"Could not send startup DM to owner: {e}")

# ──────────────────────────────────────────────
# INTERACTIVE VIEWS & AUTO REMINDER (TURSO DB)
# ──────────────────────────────────────────────

class RenewServiceView(discord.ui.View):
    def __init__(self, service_id: str, service_name: str, service_url: str, db: TursoDB):
        super().__init__(timeout=None)
        self.service_id = service_id
        self.service_name = service_name
        self.db = db

        # Link button to the service dashboard
        self.add_item(discord.ui.Button(
            label=f"🔗 Mở {service_name[:15]}",
            url=service_url,
            style=discord.ButtonStyle.link,
            row=0
        ))

        # Action button to renew (+7 days)
        done_btn = discord.ui.Button(
            label="✅ Đã gia hạn",
            style=discord.ButtonStyle.success,
            custom_id=f"renew_btn_{service_id}",
            row=0
        )
        done_btn.callback = self.on_done_clicked
        self.add_item(done_btn)

    async def on_done_clicked(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Chỉ Owner mới có quyền bấm xác nhận gia hạn!", ephemeral=True)

        await interaction.response.defer()
        new_dt = await self.db.add_days_to_reminder(self.service_id, 7)
        if new_dt:
            new_date_str = new_dt.strftime("%d %b %Y")
            for child in self.children:
                if getattr(child, "custom_id", "") == f"renew_btn_{self.service_id}":
                    child.disabled = True
                    child.label = "✅ Đã gia hạn"
                    child.style = discord.ButtonStyle.secondary

            embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Gia hạn dịch vụ")
            embed.color = 0x10B981
            embed.add_field(
                name="🎉 Đã cập nhật thành công!",
                value=f"Đã cộng **+7 ngày** vào Turso DB!\n📅 **Hạn thanh toán mới:** `{new_date_str}`",
                inline=False
            )
            try:
                await update_channel_reminder_message()
            except Exception:
                pass
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send(f"✅ Đã gia hạn thành công dịch vụ **{self.service_name}**! Hạn mới: **`{new_date_str}`**", ephemeral=True)


class DuolingoView(discord.ui.View):
    def __init__(self, db: TursoDB):
        super().__init__(timeout=None)
        self.db = db

        self.add_item(discord.ui.Button(
            label="📖 Mở Duolingo",
            url="https://www.duolingo.com",
            style=discord.ButtonStyle.link,
            row=0
        ))

        done_btn = discord.ui.Button(
            label="🔥 Đã học xong hôm nay (+1 Streak)",
            style=discord.ButtonStyle.success,
            custom_id="duo_done_btn",
            row=0
        )
        done_btn.callback = self.on_duo_done
        self.add_item(done_btn)

    async def on_duo_done(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Chỉ Owner mới có quyền xác nhận Streak!", ephemeral=True)

        await interaction.response.defer()
        now_vn = datetime.now(VN_TZ)
        tomorrow_str = (now_vn + timedelta(days=1)).strftime("%Y-%m-%d 20:00:00")
        await self.db.upsert_reminder("duolingo", "Duolingo Học Tiếng", "https://www.duolingo.com", tomorrow_str, category="duolingo")
        await self.db.update_last_notified("duolingo", now_vn.strftime("%Y-%m-%d %H:%M:%S"))

        for child in self.children:
            if getattr(child, "custom_id", "") == "duo_done_btn":
                child.disabled = True
                child.label = "🔥 Đã bảo vệ Streak thành công!"
                child.style = discord.ButtonStyle.secondary

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Duolingo")
        embed.color = 0x10B981
        embed.add_field(
            name="🔥 Streak được bảo vệ!",
            value="🎉 Chúc mừng bạn đã hoàn thành bài học Duolingo hôm nay! Nhắc nhở kế tiếp: Ngày mai lúc 20:00.",
            inline=False
        )
        try:
            await update_channel_reminder_message()
        except Exception:
            pass
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("🎉 Tuyệt vời! Bạn đã giữ vững ngọn lửa Streak hôm nay!", ephemeral=True)


def build_reminders_embed(items: List[Dict[str, Any]]) -> discord.Embed:
    now_vn = datetime.now(VN_TZ).replace(tzinfo=None)
    embed = discord.Embed(
        title="🔔 AIClaw — Bảng Theo Dõi Gia Hạn & Lịch Trình (Turso DB)",
        description=(
            "Quản lý danh sách dịch vụ HidenCloud, OptikLink & Duolingo:\n"
            "*(Tin nhắn được tự động cập nhật & chỉnh sửa trực tiếp • Không gửi trùng lặp)*"
        ),
        color=0x6366F1,
        timestamp=discord.utils.utcnow()
    )

    for item in items:
        s_id = item["id"]
        s_name = item["name"]
        s_url = item["url"]
        s_date_str = item["next_invoice"]
        category = item.get("category", "service")

        target_dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %b %Y %H:%M:%S"):
            try:
                target_dt = datetime.strptime(s_date_str.strip(), fmt)
                break
            except Exception:
                pass

        if target_dt:
            diff = (target_dt - now_vn).total_seconds()
            days_left = diff / 86400
            if diff <= 0:
                status_icon = "🚨 **[ĐÃ QUÁ HẠN]**"
            elif diff <= 1.5 * 86400:
                hours_left = max(0, int(diff // 3600))
                mins_left = max(0, int((diff % 3600) // 60))
                status_icon = f"⚠️ **[CẦN GIA HẠN NGAY (còn ~{hours_left}h {mins_left}m)]**"
            else:
                status_icon = f"🟢 Còn ~{int(days_left)} ngày"
            date_display = target_dt.strftime("%d %b %Y")
        else:
            status_icon = "❓ Chưa xác định"
            date_display = s_date_str

        if category == "duolingo":
            embed.add_field(
                name=f"🦉 {s_name} (`{s_id}`)",
                value=f"• Link: [duolingo.com]({s_url})\n• Lịch nhắc: Hàng ngày lúc 20:00 VN\n• Trạng thái: {status_icon}",
                inline=False
            )
        else:
            embed.add_field(
                name=f"🖥️ {s_name} (`{s_id}`)",
                value=f"• Next Invoice Date: `{date_display}` ({status_icon})\n• Quản lý: [Mở bảng điều khiển]({s_url})\n• Lệnh nhanh: `{BOT_PREFIX}done {s_id}` (để +7 ngày)",
                inline=False
            )

    embed.set_footer(text=f"Turso DB: libsql://ai-claw-iamprmgvyt... • Tự động cập nhật • Cập nhật lúc {datetime.now(VN_TZ).strftime('%H:%M:%S %d/%m/%Y')}")
    return embed


class ServiceSelectDropdown(discord.ui.Select):
    def __init__(self, services: List[Dict[str, Any]], db: TursoDB):
        options = []
        for s in services:
            if s.get("category") == "duolingo":
                continue
            options.append(discord.SelectOption(
                label=f"{s['name'][:25]}",
                description=f"Hạn: {s['next_invoice'][:11]} • Bấm để Đã gia hạn",
                value=s["id"],
                emoji="⚡"
            ))
        super().__init__(placeholder="👉 Chọn dịch vụ để xác nhận Đã gia hạn...", min_values=1, max_values=1, options=options[:25])
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ Chỉ Owner mới có thể thực hiện thao tác này!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        chosen_id = self.values[0]
        new_dt = await self.db.add_days_to_reminder(chosen_id, 7)
        new_date_str = new_dt.strftime("%d %b %Y") if new_dt else "N/A"
        
        await update_channel_reminder_message()
        await interaction.followup.send(f"✅ Đã cộng **+7 ngày** cho dịch vụ **{chosen_id.upper()}**! Hạn mới: **`{new_date_str}`**", ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self, services: List[Dict[str, Any]], db: TursoDB):
        super().__init__(timeout=None)
        self.db = db
        self.services = services

        # 1. Dropdown chọn dịch vụ để gia hạn
        service_options = [s for s in services if s.get("category") != "duolingo"]
        if service_options:
            self.add_item(ServiceSelectDropdown(services=services, db=db))

        # 2. Quick buttons cho dịch vụ đang cần gia hạn (< 1.5 ngày)
        now_vn = datetime.now(VN_TZ).replace(tzinfo=None)
        urgent = []
        for s in service_options:
            t_dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %b %Y %H:%M:%S"):
                try:
                    t_dt = datetime.strptime(s["next_invoice"].strip(), fmt)
                    break
                except Exception:
                    pass
            if t_dt:
                diff = (t_dt - now_vn).total_seconds()
                if diff <= 1.5 * 86400:
                    urgent.append(s)

        for idx, urg in enumerate(urgent[:2]):
            row_idx = 1 + idx
            self.add_item(discord.ui.Button(
                label=f"🔗 Mở {urg['name'][:12]}",
                url=urg["url"],
                style=discord.ButtonStyle.link,
                row=row_idx
            ))
            
            renew_btn = discord.ui.Button(
                label="✅ Đã gia hạn",
                style=discord.ButtonStyle.success,
                custom_id=f"dash_renew_{urg['id']}",
                row=row_idx
            )
            
            def make_callback(svc_id, svc_name):
                async def btn_callback(interaction: discord.Interaction):
                    if interaction.user.id != OWNER_ID:
                        return await interaction.response.send_message("❌ Chỉ Owner mới có thể thực hiện thao tác này!", ephemeral=True)
                    await interaction.response.defer(ephemeral=True)
                    new_dt = await db.add_days_to_reminder(svc_id, 7)
                    new_str = new_dt.strftime("%d %b %Y") if new_dt else "N/A"
                    await update_channel_reminder_message()
                    await interaction.followup.send(f"✅ Đã gia hạn thành công dịch vụ **{svc_name}**! Hạn mới: **`{new_str}`** (+7 ngày).", ephemeral=True)
                return btn_callback

            renew_btn.callback = make_callback(urg["id"], urg["name"])
            self.add_item(renew_btn)

        # 3. Hàng Duolingo
        duo_item = next((s for s in services if s.get("category") == "duolingo"), None)
        duo_row = min(4, 1 + len(urgent[:2]))
        self.add_item(discord.ui.Button(
            label="🦉 Mở Duolingo",
            url=duo_item["url"] if duo_item else "https://www.duolingo.com",
            style=discord.ButtonStyle.link,
            row=duo_row
        ))
        
        duo_btn = discord.ui.Button(
            label="🔥 Đã học xong hôm nay",
            style=discord.ButtonStyle.primary,
            custom_id="dash_duo_done",
            row=duo_row
        )
        
        async def duo_callback(interaction: discord.Interaction):
            if interaction.user.id != OWNER_ID:
                return await interaction.response.send_message("❌ Chỉ Owner mới có thể xác nhận Streak!", ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            now_dt = datetime.now(VN_TZ)
            tomorrow_str = (now_dt + timedelta(days=1)).strftime("%Y-%m-%d 20:00:00")
            await db.upsert_reminder("duolingo", "Duolingo Học Tiếng", "https://www.duolingo.com", tomorrow_str, category="duolingo")
            await db.update_last_notified("duolingo", now_dt.strftime("%Y-%m-%d %H:%M:%S"))
            await update_channel_reminder_message()
            await interaction.followup.send("🎉 Tuyệt vời! Bạn đã giữ vững ngọn lửa Streak hôm nay!", ephemeral=True)

        duo_btn.callback = duo_callback
        self.add_item(duo_btn)


async def update_channel_reminder_message():
    """
    Quản lý và cập nhật DUY NHẤT 1 tin nhắn trong kênh REMINDER_CHANNEL_ID (1494907926815445023).
    Chỉ thực hiện CHỈNH SỬA (edit), không gửi nhiều tin nhắn để tránh spam / trùng lặp.
    Message ID được lưu cố định trong Turso DB (bảng bot_config: 'channel_reminder_message_id').
    """
    try:
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if not channel:
            try:
                channel = await bot.fetch_channel(REMINDER_CHANNEL_ID)
            except Exception as e:
                log.error(f"Cannot access reminder channel {REMINDER_CHANNEL_ID}: {e}")
                return

        items = await turso.get_all_reminders()
        embed = build_reminders_embed(items)
        view = DashboardView(services=items, db=turso)

        now_vn = datetime.now(VN_TZ).replace(tzinfo=None)
        urgent_services = []
        for it in items:
            if it.get("category") == "duolingo":
                continue
            t_dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %b %Y %H:%M:%S"):
                try:
                    t_dt = datetime.strptime(it["next_invoice"].strip(), fmt)
                    break
                except Exception:
                    pass
            if t_dt:
                diff = (t_dt - now_vn).total_seconds()
                if diff <= 1.5 * 86400:
                    urgent_services.append(it["name"])

        if urgent_services:
            content = f"<@{OWNER_ID}> ⚠️ **Đến giờ check và gia hạn dịch vụ rồi nha!** 🔥 *(Cần gia hạn: {', '.join(urgent_services)})*"
        else:
            content = f"<@{OWNER_ID}> 🔔 **Bảng theo dõi dịch vụ & gia hạn tự động (Turso DB)**"

        saved_msg_id = await turso.get_config("channel_reminder_message_id")
        msg = None
        if saved_msg_id:
            try:
                msg = await channel.fetch_message(int(saved_msg_id))
            except discord.NotFound:
                log.info("Reminder message not found on Discord (deleted). Creating a new one...")
                msg = None
            except Exception as e:
                log.warning(f"Error fetching reminder message {saved_msg_id}: {e}")
                msg = None

        if msg:
            await msg.edit(content=content, embed=embed, view=view)
            log.info(f"Edited existing reminder message {msg.id} in channel {REMINDER_CHANNEL_ID}")
        else:
            new_msg = await channel.send(content=content, embed=embed, view=view)
            await turso.set_config("channel_reminder_message_id", str(new_msg.id))
            log.info(f"Created initial reminder message {new_msg.id} in channel {REMINDER_CHANNEL_ID} and saved to Turso DB")
    except Exception as e:
        log.error(f"Error in update_channel_reminder_message: {e}", exc_info=True)


@tasks.loop(minutes=15)
async def auto_reminder_loop():
    """Tự động quét các dịch vụ trên Turso DB và cập nhật tin nhắn duy nhất trong channel reminder mỗi 15 phút."""
    try:
        await update_channel_reminder_message()
    except Exception as e:
        log.error(f"Error in auto_reminder_loop: {e}", exc_info=True)


# ── COMMAND: ?help (DYNAMIC AUTO-IMPORT) ──
@bot.command(name="help")
async def help_cmd(ctx):
    """Hiển thị bảng trợ giúp lệnh tự động nạp từ hệ thống."""
    embed = discord.Embed(
        title="🦅 AIClaw Bot — Bảng điều khiển lệnh tự động",
        description="Toàn bộ danh sách lệnh đang hoạt động trên bot (tự động nạp từ hệ thống, không cần thêm thủ công):",
        color=0x6366F1
    )
    for cmd in sorted(bot.commands, key=lambda c: c.name):
        if cmd.hidden:
            continue
        aliases_str = f" (hoặc `{'`, `'.join([BOT_PREFIX + a for a in cmd.aliases])}`)" if cmd.aliases else ""
        help_text = cmd.help or "Chưa có mô tả chi tiết."
        embed.add_field(
            name=f"`{BOT_PREFIX}{cmd.name}`{aliases_str}",
            value=help_text,
            inline=False
        )
    embed.set_footer(text=f"AIClaw v2.0 • Prefix: {BOT_PREFIX} • Turso DB Connected • Auto Commands Discovery")
    await ctx.send(embed=embed)


# ── COMMAND: ?reminder ──
@bot.command(name="reminder", aliases=["remind", "services", "renew"])
async def reminder_cmd(ctx):
    """Xem và cập nhật tin nhắn theo dõi dịch vụ trong channel reminder."""
    await update_channel_reminder_message()
    saved_msg_id = await turso.get_config("channel_reminder_message_id")
    jump_link = f"https://discord.com/channels/{ctx.guild.id if ctx.guild else '@me'}/{REMINDER_CHANNEL_ID}/{saved_msg_id}" if saved_msg_id else f"<#{REMINDER_CHANNEL_ID}>"
    await ctx.send(f"🔔 Bảng nhắc nhở gia hạn duy nhất đang được hiển thị và cập nhật tại: {jump_link} (Kênh <#{REMINDER_CHANNEL_ID}>).")


# ── COMMAND: ?done ──
@bot.command(name="done", aliases=["renewservice", "doneservice"])
async def done_cmd(ctx, service_id: str = None):
    """Xác nhận đã gia hạn một dịch vụ và cộng thêm +7 ngày vào Turso DB."""
    if not service_id:
        return await ctx.send(f"⚠️ Cách dùng: `{BOT_PREFIX}done <id_dịch_vụ>`\nVí dụ: `{BOT_PREFIX}done h2` hoặc `{BOT_PREFIX}done h1`")
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối: Chỉ Owner mới có thể gia hạn dịch vụ.")
    
    new_dt = await turso.add_days_to_reminder(service_id.lower().strip(), 7)
    if not new_dt:
        return await ctx.send(f"❌ Không tìm thấy dịch vụ nào có ID là `{service_id}`. Dùng `{BOT_PREFIX}reminder` để xem danh sách.")
    
    await update_channel_reminder_message()
    await ctx.send(f"✅ Đã gia hạn thành công dịch vụ **`{service_id.upper()}`**! Next Invoice Date mới: **`{new_dt.strftime('%d %b %Y')}`** (+7 ngày).\nTin nhắn trong kênh <#{REMINDER_CHANNEL_ID}> đã được tự động cập nhật!")


# ── COMMAND: ?duolingo ──
@bot.command(name="duolingo", aliases=["duo", "streak"])
async def duolingo_cmd(ctx):
    """Mở bảng nhắc nhở học Duolingo và xác nhận Streak hàng ngày."""
    now_dt = datetime.now(VN_TZ)
    tomorrow_str = (now_dt + timedelta(days=1)).strftime("%Y-%m-%d 20:00:00")
    await turso.upsert_reminder("duolingo", "Duolingo Học Tiếng", "https://www.duolingo.com", tomorrow_str, category="duolingo")
    await turso.update_last_notified("duolingo", now_dt.strftime("%Y-%m-%d %H:%M:%S"))
    await update_channel_reminder_message()
    await ctx.send(f"🔥 Đã ghi nhận Streak hôm nay thành công! Lịch nhắc Duolingo kế tiếp: Ngày mai lúc 20:00.\nBảng theo dõi tại <#{REMINDER_CHANNEL_ID}> đã được cập nhật.")


# ── COMMAND: ?checkreminders ──
@bot.command(name="checkreminders", aliases=["testreminder", "runreminder"])
async def check_reminders_cmd(ctx):
    """Kiểm tra ngay lập tức các dịch vụ và cập nhật tin nhắn duy nhất trong channel reminder."""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Chỉ Owner mới có quyền chạy kiểm tra.")
    msg = await ctx.send(f"🔍 Đang quét dịch vụ trong Turso DB và cập nhật kênh <#{REMINDER_CHANNEL_ID}>...")
    await update_channel_reminder_message()
    await msg.edit(content=f"✅ Đã cập nhật thành công tin nhắn duy nhất trong kênh <#{REMINDER_CHANNEL_ID}>!")


# ── COMMAND: ?addservice ──
@bot.command(name="addservice", aliases=["setservice"])
async def addservice_cmd(ctx, s_id: str = None, date_str: str = None, *, details: str = None):
    """Thêm hoặc cập nhật một dịch vụ mới vào hệ thống nhắc nhở Turso DB."""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Chỉ Owner mới có quyền thêm dịch vụ.")
    if not s_id or not date_str or not details:
        return await ctx.send(f"⚠️ Cách dùng: `{BOT_PREFIX}addservice <id> <YYYY-MM-DD> <tên | link>`\nVí dụ: `{BOT_PREFIX}addservice h6 2026-09-20 HidenCloud 6 | https://dash.hidencloud.com/...`")
    
    parts = [p.strip() for p in details.split("|", 1)]
    name = parts[0]
    url = parts[1] if len(parts) > 1 else "https://dash.hidencloud.com"
    await turso.upsert_reminder(s_id.lower().strip(), name, url, f"{date_str.strip()} 00:00:00")
    await update_channel_reminder_message()
    await ctx.send(f"✅ Đã thêm/cập nhật dịch vụ **`{s_id.upper()}`** ({name}) với hạn thanh toán: `{date_str}`!\nBảng nhắc nhở trong kênh <#{REMINDER_CHANNEL_ID}> đã được cập nhật.")

# ── COMMAND: .testkey (TEST GEN KEY) ──
@bot.command(name="testkey", aliases=["testgenkey", "testrotation"])
async def testkey_cmd(ctx):
    """Generates a mock key, tests SFTP upload and sends test DM to Owner."""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối: Chỉ Owner mới có thể chạy test gen key.")

    msg = await ctx.send("🧪 **Đang tiến hành TEST GEN KEY...** (Kiểm tra SFTP HidenCloud & gửi DM kết quả)")
    res = await execute_unified_rotation(is_test=True, trigger_source=f"Lệnh thủ công {BOT_PREFIX}testkey từ <@{ctx.author.id}>")

    sftp_icon = "🟢" if res["sftp_ok"] else "🔴"
    dm_icon = "🟢" if res["dm_ok"] else "🔴"

    result_text = (
        f"✅ **KẾT QUẢ TEST GEN KEY:**\n"
        f"• **Key thử nghiệm:** `{res['token']}`\n"
        f"• **Kết nối SFTP HidenCloud:** {sftp_icon} {res['sftp_msg']}\n"
        f"• **Gửi DM báo cáo:** {dm_icon} {'Đã gửi tin nhắn riêng cho bạn' if res['dm_ok'] else 'Lỗi gửi DM'}\n"
        f"• **Thời gian thực thi:** `{res['total_ms']} ms`\n"
        f"• **Lịch xoay tự động kế tiếp:** `{res['next_rotation_vn']}`\n"
        f"*(Lưu ý: File chính `apitoken.js` không bị ảnh hưởng khi test)*"
    )
    await msg.edit(content=result_text)

# ── COMMAND: .genkey (REAL KEY ROTATION) ──
@bot.command(name="genkey", aliases=["rotatekey", "resetkey"])
async def genkey_cmd(ctx):
    """Generates a real key, pushes to apitoken.js via SFTP, updates Hugging Face, and DMs Owner."""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối: Chỉ Owner mới có quyền xoay key thật.")

    msg = await ctx.send("⏳ **Đang xoay API KEY THẬT...** (Đang ghi `apitoken.js` qua SFTP HidenCloud & gửi DM)")
    res = await execute_unified_rotation(is_test=False, trigger_source=f"Lệnh thủ công {BOT_PREFIX}genkey từ <@{ctx.author.id}>")

    sftp_icon = "🟢" if res["sftp_ok"] else "🔴"
    dm_icon = "🟢" if res["dm_ok"] else "🔴"

    result_text = (
        f"🎉 **ĐÃ XOAY API KEY THẬT THÀNH CÔNG!**\n"
        f"• **Key mới:** `{res['token']}`\n"
        f"• **Đẩy SFTP HidenCloud (`apitoken.js`):** {sftp_icon} {res['sftp_msg']}\n"
        f"• **Gửi DM báo cáo:** {dm_icon} {'Đã gửi DM riêng đầy đủ cho bạn' if res['dm_ok'] else 'Lỗi gửi DM'}\n"
        f"• **Lịch tự động kế tiếp:** `{res['next_rotation_vn']}`\n"
        f"*(Server Discord bot của bạn trên HidenCloud sẽ tự động auto-reload key này 24/7)*"
    )
    await msg.edit(content=result_text)

# ── COMMAND: .status ──
@bot.command(name="status", aliases=["ping", "health"])
async def status_cmd(ctx):
    uptime_sec = int(time.time() - bot_start_time)
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"
    ws_ping = round(bot.latency * 1000)

    # Test SFTP Latency
    _, sftp_detail, sftp_latency = upload_sftp_token("ping_test", is_test=True)

    # Test Hugging Face Gateway Ping
    gw_status = "🔴 Offline"
    try:
        t0 = time.monotonic()
        headers = {"User-Agent": BROWSER_UA}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get(f"{AIO_GATEWAY_URL}/", headers=headers) as resp:
                gw_ping = round((time.monotonic() - t0) * 1000)
                if resp.status == 200:
                    gw_status = f"🟢 Online ({gw_ping} ms)"
                else:
                    gw_status = f"🟡 HTTP {resp.status}"
    except Exception:
        gw_status = "🔴 Unreachable"

    embed = discord.Embed(title="🛡️ AIClaw Telemetry & Lịch Trình", color=0x22C55E)
    embed.add_field(name="Discord Ping", value=f"`{ws_ping} ms`", inline=True)
    embed.add_field(name="SFTP HidenCloud Ping", value=f"`{sftp_latency} ms`", inline=True)
    embed.add_field(name="Bot Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="Giờ Việt Nam (UTC+7)", value=f"`{format_vn_time()}`", inline=False)
    embed.add_field(name="📅 Lịch Auto Gen Key", value="`Mỗi Thứ 2, Thứ 4, Thứ 6 lúc 00:00 (Giờ VN)`", inline=False)
    embed.add_field(name="⏰ Lần Xoay Tiếp Theo", value=f"`{calculate_next_rotation_vn()}`", inline=True)
    embed.add_field(name="Hugging Face AI Gateway", value=f"`{AIO_GATEWAY_URL}`\n{gw_status}", inline=False)
    embed.set_footer(text="Hệ thống giám sát bảo mật AIO Claw v2.3")
    await ctx.send(embed=embed)

# ── COMMAND: .key ──
@bot.command(name="key", aliases=["token"])
async def key_cmd(ctx):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối: Chỉ Owner mới có thể xem key.")

    embed = discord.Embed(
        title="🔑 AIClaw — Khóa API Hiện Tại",
        description="Khóa bảo mật đang đồng bộ với file `apitoken.js` trên HidenCloud.",
        color=0x22C55E,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Current Key", value=f"```{cached_active_key or 'aio_sec_...'}```", inline=False)
    embed.add_field(name="Lịch xoay tự động", value="`Thứ 2, Thứ 4, Thứ 6 lúc 00:00 (Giờ VN)`", inline=False)
    embed.add_field(name="Lần xoay kế tiếp", value=f"`{calculate_next_rotation_vn()}`", inline=False)
    await ctx.author.send(embed=embed)
    await ctx.send("📬 **Khóa API đã được gửi vào Direct Messages của bạn!**")

# ── COMMAND: .scan ──
@bot.command(name="scan")
async def scan_cmd(ctx, *, url: str = None):
    if not url:
        return await ctx.send(f"⚠️ Cách dùng: `{BOT_PREFIX}scan <url>`")

    clean_url = url.strip().strip("<>")
    if not clean_url.lower().startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    msg = await ctx.send(f"🔍 Đang chuyển URL `{clean_url}` tới Cụm AI Sandbox trên Hugging Face để phân tích...")
    try:
        headers = {
            "User-Agent": BROWSER_UA,
            "X-API-Key": MASTER_KEY,
            "Content-Type": "application/json"
        }
        payload = {"url": clean_url}

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(f"{AIO_GATEWAY_URL}/scan", headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    danger = data.get("danger") or (data.get("verdict") == "THREAT_BLOCKED") or data.get("is_phishing")
                    embed = discord.Embed(
                        title="🛡️ Kết quả phân tích mối đe dọa (AI Sandbox)",
                        color=0xEF4444 if danger else 0x22C55E,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.add_field(name="URL mục tiêu", value=f"`{clean_url}`", inline=False)
                    embed.add_field(name="URL chuyển hướng", value=f"`{data.get('final_url', clean_url)}`", inline=False)
                    embed.add_field(name="Tiêu đề trang", value=f"{data.get('title', 'N/A')}", inline=True)
                    embed.add_field(name="Đánh giá an toàn", value="⚠️ **PHÁT HIỆN MỐI ĐE DỌA (Phishing / Scam)**" if danger else "✅ **AN TOÀN / SẠCH**", inline=True)
                    await msg.edit(content=None, embed=embed)
                else:
                    await msg.edit(content=f"⚠️ Cụm Scanner Hugging Face trả về HTTP {resp.status}")
    except Exception as e:
        await msg.edit(content=f"❌ Quét thất bại: `{e}`")

# ── COMMAND: ?model ──
@bot.command(name="model", aliases=["models", "setmodel"])
async def model_cmd(ctx, *, model_name: str = None):
    """Xem hoặc đổi mô hình AI đang sử dụng (GPT-OSS 120B, Llama 3.3 70B, Qwen)."""
    global current_ai_model
    if not model_name:
        embed = discord.Embed(
            title="🧠 AIClaw — Cấu hình Mô hình Trí Tuệ Nhân Tạo",
            description=f"Mô hình đang hoạt động hiện tại: **`{current_ai_model}`**",
            color=0x6366F1
        )
        embed.add_field(
            name="💡 Các Model Miễn Phí (Free Tier) đề xuất:",
            value=(
                "• **`openai/gpt-oss-120b:free`**: Model 117B MoE từ OpenAI, suy luận logic mạnh mẽ\n"
                "• **`meta-llama/llama-3.3-70b-instruct:free`**: Llama 3.3 70B, thông minh vượt trội, tiếng Việt mượt mà\n"
                "• **`openrouter/free`**: Bộ định tuyến tự động chọn model free mạnh nhất\n"
                "• **`deepseek/deepseek-r1:free`**: Siêu mô hình suy luận chuyên sâu\n"
                "• **`qwen-local`**: Mô hình local chạy trên Hugging Face CPU Space"
            ),
            inline=False
        )
        embed.add_field(
            name="📝 Cách đổi mô hình:",
            value=f"`{BOT_PREFIX}model <tên_model>`\nVí dụ: `{BOT_PREFIX}model openai/gpt-oss-120b:free`\nHoặc: `{BOT_PREFIX}model meta-llama/llama-3.3-70b-instruct:free`",
            inline=False
        )
        return await ctx.send(embed=embed)

    clean_model = model_name.strip()
    if clean_model.lower() in ("default", "reset", "gpt", "gpt-oss", "120b", "gpt-oss-120b"):
        current_ai_model = "openai/gpt-oss-120b:free"
    elif clean_model.lower() in ("llama", "llama-70b", "llama-3.3", "70b"):
        current_ai_model = "meta-llama/llama-3.3-70b-instruct:free"
    elif clean_model.lower() in ("free", "auto", "router"):
        current_ai_model = "openrouter/free"
    elif clean_model.lower() in ("local", "qwen", "cpu"):
        current_ai_model = "qwen-local"
    else:
        current_ai_model = clean_model

    await ctx.send(f"✅ Đã chuyển mô hình AI sang: **`{current_ai_model}`**!\nHãy thử trò chuyện ngay bằng lệnh: `{BOT_PREFIX}chat <câu hỏi>`")

# ── COMMAND: ?chat (AI MULTI-ENGINE INTEGRATION) ──
@bot.command(name="chat", aliases=["ask", "ai", "qwen", "gpt"])
async def chat_cmd(ctx, *, prompt: str = None):
    """Trò chuyện trực tiếp với AI thông minh (GPT-OSS 120B / Llama 70B / Qwen)."""
    if not prompt:
        return await ctx.send(f"⚠️ Cách dùng: `{BOT_PREFIX}chat <câu hỏi/tin nhắn>`\nVí dụ: `{BOT_PREFIX}chat Xin chào, hãy giải thích cho tôi về lượng tử!`")

    async with ctx.typing():
        t0 = time.monotonic()

        # 1. Direct Hugging Face High-Performance GPU Router
        if HF_TOKEN and ("Qwen" in current_ai_model or "72B" in current_ai_model or "default" in current_ai_model.lower()):
            try:
                headers = {
                    "Authorization": f"Bearer {HF_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "Qwen/Qwen2.5-72B-Instruct",
                    "messages": [
                        {"role": "system", "content": "You are AIClaw, a highly intelligent and helpful AI assistant powered by Hugging Face GPU Cluster and Qwen 2.5 72B. Answer clearly and informatively in Vietnamese if user writes in Vietnamese."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 768,
                    "temperature": 0.7
                }
                connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.post("https://router.huggingface.co/v1/chat/completions", headers=headers, json=payload) as resp:
                        latency = round((time.monotonic() - t0) * 1000)
                        if resp.status == 200:
                            data = await resp.json()
                            reply = data["choices"][0]["message"]["content"]
                            footer = f"\n\n*(⚡ {latency} ms · Qwen 2.5 72B on Hugging Face GPU)*"
                            if len(reply) + len(footer) > 1950:
                                chunks = [reply[i:i+1850] for i in range(0, len(reply), 1850)]
                                for idx, chunk in enumerate(chunks):
                                    if idx == len(chunks) - 1:
                                        await ctx.reply(f"{chunk}{footer}")
                                    else:
                                        await ctx.reply(chunk)
                            else:
                                await ctx.reply(f"{reply}{footer}")
                            return
            except Exception as e:
                log.warning(f"Direct HF Router call error, attempting fallback: {e}")

        # 2. Direct OpenRouter query if OPENROUTER_API_KEY is configured directly on bot
        if OPENROUTER_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://aegix-claw.prmgvyt.xyz",
                    "X-Title": "AI Claw Security"
                }
                payload = {
                    "model": current_ai_model,
                    "messages": [
                        {"role": "system", "content": "You are AIClaw, a highly intelligent and helpful AI assistant. Answer clearly and comprehensively in Vietnamese if the user writes in Vietnamese."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 768,
                    "temperature": 0.7
                }
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as session:
                    async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as resp:
                        latency = round((time.monotonic() - t0) * 1000)
                        if resp.status == 200:
                            data = await resp.json()
                            reply = data["choices"][0]["message"]["content"]
                            model_used = data.get("model", current_ai_model)
                            footer = f"\n\n*(⚡ {latency} ms · {model_used})*"
                            if len(reply) + len(footer) > 1950:
                                chunks = [reply[i:i+1850] for i in range(0, len(reply), 1850)]
                                for idx, chunk in enumerate(chunks):
                                    if idx == len(chunks) - 1:
                                        await ctx.reply(f"{chunk}{footer}")
                                    else:
                                        await ctx.reply(chunk)
                            else:
                                await ctx.reply(f"{reply}{footer}")
                            return
            except Exception as e:
                log.warning(f"Direct OpenRouter call error, falling back: {e}")

        # 2. Fallback to Hugging Face AI Gateway
        try:
            headers = {
                "User-Agent": BROWSER_UA,
                "X-API-Key": MASTER_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "messages": [
                    {"role": "system", "content": "You are AIClaw, a highly intelligent and helpful AI assistant. Answer clearly and informatively."},
                    {"role": "user", "content": prompt}
                ],
                "author_id": str(ctx.author.id),
                "guild_id": str(ctx.guild.id if ctx.guild else ""),
                "max_tokens": 512,
                "temperature": 0.7,
                "model": current_ai_model,
                "openrouter_api_key": OPENROUTER_API_KEY or None,
                "hf_token": HF_TOKEN or None
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
                async with session.post(f"{AIO_GATEWAY_URL}/api/v1/chat", headers=headers, json=payload) as resp:
                    latency = round((time.monotonic() - t0) * 1000)
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data.get("response", "Không nhận được phản hồi từ AI.")
                        model_name = data.get("model", current_ai_model)

                        footer = f"\n\n*(⚡ {latency} ms · {model_name})*"
                        if len(reply) + len(footer) > 1950:
                            chunks = [reply[i:i+1850] for i in range(0, len(reply), 1850)]
                            for idx, chunk in enumerate(chunks):
                                if idx == len(chunks) - 1:
                                    await ctx.reply(f"{chunk}{footer}")
                                else:
                                    await ctx.reply(chunk)
                        else:
                            await ctx.reply(f"{reply}{footer}")
                    else:
                        await ctx.reply(f"⚠️ Hugging Face AI Gateway báo lỗi HTTP {resp.status} (Ping: {latency} ms).")
        except asyncio.TimeoutError:
            await ctx.reply("⏱️ Yêu cầu tới AI Gateway bị quá thời gian (Timeout).")
        except Exception as e:
            await ctx.reply(f"❌ Không thể kết nối tới AI Gateway: `{e}`")

# ──────────────────────────────────────────────
# AUTOMOD REAL-TIME INSPECTION
# ──────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Trigger AI Chat if bot is mentioned
    if bot.user and bot.user.mentioned_in(message) and not message.mention_everyone:
        clean_text = message.clean_content.replace(f"@{bot.user.name}", "").strip()
        if clean_text:
            ctx = await bot.get_context(message)
            return await chat_cmd(ctx, prompt=clean_text)

    if not message.guild:
        await bot.process_commands(message)
        return

    content = message.content.strip()
    if any(k in content.lower() for k in ["http://", "https://", "discord.gift", "nitro", "steamcommunity", "airdrop"]):
        try:
            headers = {
                "User-Agent": BROWSER_UA,
                "X-API-Key": MASTER_KEY,
                "Content-Type": "application/json"
            }
            payload = {"content": content, "author_id": str(message.author.id), "guild_id": str(message.guild.id)}

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                async with session.post(f"{AIO_GATEWAY_URL}/api/v1/automod", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        d = await resp.json()
                        verdict = d.get("verdict", "ALLOW").upper()
                        if verdict in ["DELETE", "BAN", "WARN", "MUTE"]:
                            await message.delete()
                            flags = ", ".join(d.get("flags", ["Liên kết độc hại/lừa đảo"]))
                            embed = discord.Embed(
                                title="🛡️ AIClaw AutoMod — Đã chặn mối đe dọa",
                                description=f"Đã gỡ tin nhắn chứa liên kết độc hại từ {message.author.mention}.\n**Lý do:** `{flags}`",
                                color=0xEF4444
                            )
                            await message.channel.send(embed=embed, delete_after=10)
        except Exception:
            pass

    await bot.process_commands(message)

# ──────────────────────────────────────────────
# MAIN RUNNER (FastAPI + Discord Bot)
# ──────────────────────────────────────────────
def run_web_server():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        log.error("❌ DISCORD_BOT_TOKEN is missing! Please configure DISCORD_BOT_TOKEN in Render Environment Variables.")
        sys.exit(1)

    # 1. Start Keepalive Web Server in daemon thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    log.info(f"🚀 Render Web Server Keepalive listening on port {PORT}")

    # 2. Run Discord Bot on main thread
    log.info("🤖 Starting Discord Bot on Render.com with Mon/Wed/Fri VN Rotation Schedule...")
    bot.run(DISCORD_TOKEN)
