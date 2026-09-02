# -*- coding: utf-8 -*-
"""
🦅 AI CLAW DISCORD BOT — Render.com Web Service Edition
• 24/7 Hosting on Render.com (FastAPI Keepalive on $PORT)
• Direct unblocked connection to Discord Gateway (Zero blocks / Zero ConnectionResetError)
• Powered by Hugging Face AI Gateway (https://aegix-claw.prmgvyt.xyz)
• Real-time AI AutoMod & Domain Scanning
• Owner DM Token Management & Key Rotation
"""

import os
import sys
import time
import asyncio
import logging
import threading
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("aiclaw_render_bot")

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", os.getenv("DISCORD_TOKEN", "")).strip()
OWNER_ID = int(os.getenv("NOTIFY_USER_ID", os.getenv("OWNER_ID", "1262304052361035857")))
MASTER_KEY = os.getenv("MASTER_OWNER_KEY", os.getenv("AIO_RESET_TOKEN", "Iamprmgvyt2013@")).strip()
AIO_GATEWAY_URL = os.getenv("AIO_GATEWAY_URL", "https://aegix-claw.prmgvyt.xyz").rstrip("/")
BOT_PREFIX = os.getenv("BOT_PREFIX", ".").strip()
PORT = int(os.getenv("PORT", 10000))

# Fallback active key holder (cached from HF)
cached_active_key = os.getenv("AIO_API_KEY", "")

async def get_latest_api_key() -> str:
    """Fetches the latest active API key from Hugging Face AI Gateway."""
    global cached_active_key
    try:
        headers = {"X-Reset-Token": MASTER_KEY}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get(f"{AIO_GATEWAY_URL}/api/v1/active-token", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    key = data.get("api_key")
                    if key:
                        cached_active_key = key
                        return key
    except Exception as e:
        log.warning(f"Could not fetch active token from HF gateway: {e}")
    return cached_active_key or MASTER_KEY

# ──────────────────────────────────────────────
# FASTAPI KEEPALIVE WEB SERVER (For Render.com)
# ──────────────────────────────────────────────
app = FastAPI(title="AIClaw Render Keepalive", version="2.2.0")

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": "AIClaw Discord Bot on Render.com",
        "port": PORT,
        "gateway": AIO_GATEWAY_URL,
        "bot_online": bot.is_ready() if "bot" in globals() else False,
        "uptime_sec": int(time.time() - bot_start_time) if "bot_start_time" in globals() else 0
    }

# ──────────────────────────────────────────────
# DISCORD BOT CLIENT
# ──────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)
bot_start_time = time.time()

@bot.event
async def on_ready():
    log.info(f"🎉 SUCCESS: AIClaw Bot logged in as {bot.user} (ID: {bot.user.id}) on Render.com!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Threats & AutoMod | .help"))
    
    # Notify Owner on startup
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        if owner:
            embed = discord.Embed(
                title="🟢 AIClaw Bot Online (Render.com)",
                description=f"Bot đã khởi động thành công trên **Render.com** và kết nối trực tiếp đến **Cụm AI Hugging Face**!",
                color=0x22C55E,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="AI Gateway", value=f"`{AIO_GATEWAY_URL}`", inline=False)
            embed.add_field(name="Hosting Platform", value="`Render.com (Zero Blocks)`", inline=True)
            embed.add_field(name="Prefix", value=f"`{BOT_PREFIX}`", inline=True)
            await owner.send(embed=embed)
    except Exception as e:
        log.warning(f"Could not send startup DM to owner: {e}")

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="🦅 AIClaw Bot — Danh sách lệnh",
        description="Bot Bảo mật & AutoMod 24/7 host trên Render.com kết nối Hugging Face AI.",
        color=0x6366F1
    )
    embed.add_field(name=f"`{BOT_PREFIX}status`", value="Kiểm tra ping Discord, Render uptime & trạng thái AI Gateway", inline=False)
    embed.add_field(name=f"`{BOT_PREFIX}scan <url>`", value="Quét phân tích mối đe dọa URL/Website trong sandbox", inline=False)
    embed.add_field(name=f"`{BOT_PREFIX}key`", value="[Owner Only] Nhận `X-API-Key` đang hoạt động qua DM", inline=False)
    embed.add_field(name=f"`{BOT_PREFIX}resetkey <master_token>`", value="[Owner Only] Ép xoay key mới trên Hugging Face & đẩy qua SFTP HidenCloud", inline=False)
    embed.set_footer(text="AIClaw Unified Security Shield v2.2")
    await ctx.send(embed=embed)

@bot.command(name="status", aliases=["ping", "health"])
async def status_cmd(ctx):
    uptime_sec = int(time.time() - bot_start_time)
    uptime_str = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"
    ws_ping = round(bot.latency * 1000)

    # Check Hugging Face AI Gateway health
    gw_status = "🔴 Offline"
    gw_ping = 0
    try:
        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get(f"{AIO_GATEWAY_URL}/") as resp:
                gw_ping = round((time.monotonic() - t0) * 1000)
                if resp.status == 200:
                    gw_status = f"🟢 Online ({gw_ping} ms)"
                else:
                    gw_status = f"🟡 HTTP {resp.status}"
    except Exception:
        gw_status = "🔴 Unreachable"

    embed = discord.Embed(title="🛡️ AIClaw Telemetry Status", color=0x22C55E)
    embed.add_field(name="Discord Ping", value=f"`{ws_ping} ms`", inline=True)
    embed.add_field(name="Bot Uptime", value=f"`{uptime_str}`", inline=True)
    embed.add_field(name="Host Platform", value="`Render.com`", inline=True)
    embed.add_field(name="Hugging Face AI Gateway", value=f"`{AIO_GATEWAY_URL}`\n{gw_status}", inline=False)
    embed.set_footer(text="AIO Claw Security Shield")
    await ctx.send(embed=embed)

@bot.command(name="key", aliases=["token", "getkey"])
async def key_cmd(ctx):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối: Chỉ Bot Owner mới có quyền xem API Key.")

    active_key = await get_latest_api_key()
    try:
        embed = discord.Embed(
            title="🔑 AIClaw — Active API Key",
            description=f"Khóa bảo mật hiện tại được nạp từ Hugging Face AI Gateway.",
            color=0x22C55E,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Current `X-API-Key`", value=f"```{active_key}```", inline=False)
        embed.add_field(name="AI Gateway Endpoint", value=f"`{AIO_GATEWAY_URL}`", inline=False)
        embed.set_footer(text="Master Key: Iamprmgvyt2013@ (Admin Only)")
        await ctx.author.send(embed=embed)
        await ctx.send("📬 **Khóa API hiện tại đã được gửi vào Direct Messages của bạn!**")
    except Exception as e:
        await ctx.send(f"⚠️ Không thể gửi DM: `{e}` (Hãy mở chặn tin nhắn từ thành viên server).")

@bot.command(name="resetkey", aliases=["rotatekey", "forcerotate"])
async def resetkey_cmd(ctx, *, master_token: str = None):
    if ctx.author.id != OWNER_ID:
        return await ctx.send("❌ Quyền truy cập bị từ chối.")

    if not master_token or master_token.strip() != MASTER_KEY:
        return await ctx.send(f"❌ **Sai Master Reset Token!**\nCách dùng: `{BOT_PREFIX}resetkey <master_token>`")

    msg = await ctx.send("⏳ Đang gửi lệnh xoay key tới Hugging Face Space & đẩy SFTP tới HidenCloud...")
    try:
        payload = {"reset_token": master_token.strip(), "reason": f"Manual Reset by Owner <@{OWNER_ID}> via Render Bot"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(f"{AIO_GATEWAY_URL}/api/v1/reset-token", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    new_key = data.get("new_api_key", "N/A")
                    sftp_ok = data.get("sftp_synced", False)
                    sftp_detail = data.get("sftp_detail", "SFTP Sync Success")
                    sftp_icon = "🟢 Đã đồng bộ SFTP" if sftp_ok else "⚠️ Lỗi SFTP"

                    await msg.edit(content=f"✅ **Đã xoay API Key thành công!**\n• Key mới: `aio_sec_...`\n• Trạng thái: {sftp_icon} ({sftp_detail})\n• Server HidenCloud đã auto-reload token mới!")
                else:
                    await msg.edit(content=f"❌ Hugging Face Gateway báo lỗi HTTP {resp.status}")
    except Exception as e:
        await msg.edit(content=f"❌ Lỗi gửi request tới Hugging Face Gateway: `{e}`")

@bot.command(name="scan")
async def scan_cmd(ctx, *, url: str = None):
    if not url:
        return await ctx.send(f"⚠️ Cách dùng: `{BOT_PREFIX}scan <url>`\nVí dụ: `{BOT_PREFIX}scan https://example.com`")

    clean_url = url.strip().strip("<>")
    if not clean_url.lower().startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    msg = await ctx.send(f"🔍 Đang chuyển URL `{clean_url}` tới Cụm AI Sandbox trên Hugging Face để phân tích...")
    try:
        active_key = await get_latest_api_key()
        headers = {"X-API-Key": active_key, "Content-Type": "application/json"}
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
                    embed.add_field(name="URL chuyển hướng đến", value=f"`{data.get('final_url', clean_url)}`", inline=False)
                    embed.add_field(name="Tiêu đề trang", value=f"{data.get('title', 'N/A')}", inline=True)
                    embed.add_field(name="Đánh giá an toàn", value="⚠️ **PHÁT HIỆN MỐI ĐE DỌA (Phishing / Scam)**" if danger else "✅ **AN TOÀN / SẠCH**", inline=True)
                    await msg.edit(content=None, embed=embed)
                else:
                    await msg.edit(content=f"⚠️ Cụm Scanner Hugging Face trả về mã HTTP {resp.status}")
    except Exception as e:
        await msg.edit(content=f"❌ Quét thất bại: `{e}`")

# ──────────────────────────────────────────────
# AUTOMOD REAL-TIME INSPECTION
# ──────────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    content = message.content.strip()
    if any(k in content.lower() for k in ["http://", "https://", "discord.gift", "nitro", "steamcommunity", "airdrop"]):
        try:
            active_key = await get_latest_api_key()
            headers = {"X-API-Key": active_key, "Content-Type": "application/json"}
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
    log.info("🤖 Starting Discord Bot on Render.com...")
    bot.run(DISCORD_TOKEN)
