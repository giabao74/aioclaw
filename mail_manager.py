# -*- coding: utf-8 -*-
"""
🦅 AIClaw Email Management System (support@aegixbot.xyz)
• Resend Inbound Webhook Handler & Email Parsing
• Outbound Resend API Mail Sender
• Hidden Web Management Portal (/manage) with Password Protection (Iamprmgvyt2013@)
• Discord Interactive Notification View & Modal for Instant In-Discord Replies
• Automatic Thread & Reply Detection (Re: / Follow-up tracking)
"""

import os
import time
import secrets
import logging
import asyncio
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import parse_qs

import aiohttp
import discord
from discord.ext import commands
from fastapi import APIRouter, Request, Response, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

log = logging.getLogger("aiclaw_mail_manager")

async def get_form_data(request: Request) -> Dict[str, str]:
    """Safely extracts form data without requiring python-multipart."""
    try:
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
    except Exception:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8", errors="replace"))
        return {k: v[0] if v else "" for k, v in parsed.items()}

VN_TZ = timezone(timedelta(hours=7))

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@aegixbot.xyz").strip()
BASE_URL = os.getenv("BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "https://aio-claw-render.onrender.com")).rstrip("/")
MASTER_KEY = os.getenv("MASTER_OWNER_KEY", os.getenv("AIO_RESET_TOKEN", "")).strip()
MANAGE_PASSWORD = os.getenv("MANAGE_PASSWORD", MASTER_KEY or "Iamprmgvyt2013@").strip()
OWNER_ID = int(os.getenv("NOTIFY_USER_ID", os.getenv("OWNER_ID", "1262304052361035857")))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "1494907926815445023"))
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "whsec_LGjyqnw9YrD7zho856EnGw3tPgOK7zHI").strip()

# References to parent bot & DB
bot_ref: Optional[commands.Bot] = None
turso_ref: Any = None

mail_router = APIRouter(tags=["Email Manager"])

def format_vn_time(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now(VN_TZ)
    days_vi = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    day_name = days_vi[dt.weekday()]
    return f"{day_name}, {dt.strftime('%d/%m/%Y %H:%M:%S')} (Giờ VN)"

# ──────────────────────────────────────────────
# RESEND EMAIL CLIENT (OUTBOUND)
# ──────────────────────────────────────────────
async def send_resend_email(to_email: str, subject: str, text: str, html: str = None) -> tuple[bool, str]:
    """
    Sends an email from support@aegixbot.xyz using Resend API.
    Returns (success: bool, message: str).
    """
    current_key = os.getenv("RESEND_API_KEY", RESEND_API_KEY).strip()
    if not current_key:
        err = "⚠️ Chưa cấu hình RESEND_API_KEY! Hãy thêm RESEND_API_KEY vào .env (lấy tại resend.com/api-keys)."
        log.warning(err)
        return False, err

    headers = {
        "Authorization": f"Bearer {current_key}",
        "Content-Type": "application/json"
    }

    formatted_html = html or f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:24px;background-color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
    <div style="background:linear-gradient(135deg,#4f46e5,#3b82f6);padding:24px;color:#ffffff;">
      <h2 style="margin:0;font-size:20px;font-weight:700;letter-spacing:-0.02em;">AEGIX SUPPORT TEAM</h2>
      <p style="margin:6px 0 0 0;font-size:13px;opacity:0.85;">Trung tâm phản hồi hỗ trợ • {SUPPORT_EMAIL}</p>
    </div>
    <div style="padding:28px;line-height:1.7;font-size:15px;color:#334155;">
      {text.replace(chr(10), '<br>')}
    </div>
    <div style="background:#f1f5f9;padding:16px 28px;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;">
      <p style="margin:0;">Email này được gửi chính thức từ <strong>{SUPPORT_EMAIL}</strong>. Bạn có thể bấm Trả lời (Reply) trực tiếp email này nếu cần hỗ trợ thêm.</p>
    </div>
  </div>
</body>
</html>"""

    payload = {
        "from": f"AEGIX Support <{SUPPORT_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "text": text,
        "html": formatted_html
    }

    try:
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post("https://api.resend.com/emails", headers=headers, json=payload) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    mail_id = data.get("id", "OK")
                    log.info(f"✅ Resend email sent to {to_email}: ID={mail_id}")
                    return True, f"Đã gửi thành công (ID: {mail_id})"
                else:
                    err_msg = data.get("message", f"HTTP {resp.status}")
                    log.error(f"❌ Resend API Error ({resp.status}): {err_msg}")
                    return False, f"Lỗi Resend ({resp.status}): {err_msg}"
    except Exception as e:
        log.error(f"❌ Exception calling Resend API: {e}")
        return False, f"Lỗi kết nối Resend: {e}"

# ──────────────────────────────────────────────
# AUTHENTICATION HELPERS FOR /manage
# ──────────────────────────────────────────────
def get_auth_token() -> str:
    pwd = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD).strip()
    return hmac.new(pwd.encode(), b"aiclaw_manage_auth_v1", hashlib.sha256).hexdigest()

def is_manage_authenticated(request: Request) -> bool:
    cookie = request.cookies.get("aiclaw_manage_session", "")
    if not cookie:
        return False
    return hmac.compare_digest(cookie, get_auth_token())

# ──────────────────────────────────────────────
# DISCORD UI (BUTTONS & MODAL)
# ──────────────────────────────────────────────
class EmailReplyModal(discord.ui.Modal):
    def __init__(self, email_id: str, sender: str, original_subject: str, parent_msg: Optional[discord.Message] = None):
        super().__init__(title=f"Phản Hồi Thư #{email_id}")
        self.email_id = email_id
        self.sender = sender
        self.original_subject = original_subject
        self.parent_msg = parent_msg

        default_subj = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"
        self.subject_input = discord.ui.TextInput(
            label="Tiêu đề email",
            default=default_subj[:150],
            max_length=150,
            required=True
        )
        self.body_input = discord.ui.TextInput(
            label=f"Nội dung phản hồi (Gửi tới {sender[:30]})",
            style=discord.TextStyle.paragraph,
            placeholder="Nhập nội dung câu trả lời hỗ trợ khách hàng...",
            max_length=2000,
            required=True
        )
        self.add_item(self.subject_input)
        self.add_item(self.body_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reply_subject = self.subject_input.value.strip()
        reply_body = self.body_input.value.strip()

        ok, msg = await send_resend_email(to_email=self.sender, subject=reply_subject, text=reply_body)

        if ok:
            # Update DB status
            if turso_ref:
                await turso_ref.update_email_status(self.email_id, "replied")
                # Save outgoing reply as well
                reply_id = f"OUT-{secrets.token_hex(3).upper()}"
                await turso_ref.save_support_email(
                    email_id=reply_id,
                    thread_id=self.email_id,
                    sender=SUPPORT_EMAIL,
                    recipient=self.sender,
                    subject=reply_subject,
                    body_text=reply_body,
                    status="replied",
                    is_reply=1
                )

            # Update parent message embed if available
            try:
                if self.parent_msg and self.parent_msg.embeds:
                    embed = self.parent_msg.embeds[0]
                    embed.color = 0x22C55E  # Green
                    embed.title = f"✅ [Đã phản hồi #{self.email_id}] {self.original_subject}"
                    embed.set_footer(text=f"⚡ Phản hồi bởi {interaction.user.name} lúc {format_vn_time()} • {SUPPORT_EMAIL}")
                    await self.parent_msg.edit(embed=embed)
            except Exception as e:
                log.debug(f"Could not update parent message embed: {e}")

            await interaction.followup.send(
                f"✅ **Đã gửi email phản hồi thành công!**\n"
                f"• **Gửi đến:** `{self.sender}`\n"
                f"• **Tiêu đề:** `{reply_subject}`\n"
                f"• **Mã thư:** `#{self.email_id}`\n"
                f"• **Tài khoản gửi:** `{SUPPORT_EMAIL}` (qua Resend)",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ **Không thể gửi email qua Resend:**\n`{msg}`\n\n"
                f"💡 *Hãy kiểm tra lại biến `RESEND_API_KEY` trong file .env hoặc vào trang web quản lý `/manage`.*",
                ephemeral=True
            )

class EmailNotificationView(discord.ui.View):
    def __init__(self, email_item: dict):
        super().__init__(timeout=None)
        self.email_item = email_item

        # Link button directly to hidden web /manage
        web_url = f"{BASE_URL}/manage"
        self.add_item(discord.ui.Button(
            label="🌐 Mở Web Quản Lý",
            style=discord.ButtonStyle.link,
            url=web_url
        ))

    @discord.ui.button(label="✉️ Trả lời nhanh", style=discord.ButtonStyle.primary, custom_id="btn_email_reply")
    async def reply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EmailReplyModal(
            email_id=self.email_item["id"],
            sender=self.email_item["sender"],
            original_subject=self.email_item["subject"],
            parent_msg=interaction.message
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="✅ Đánh dấu đã xử lý", style=discord.ButtonStyle.secondary, custom_id="btn_email_done")
    async def done_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        email_id = self.email_item["id"]
        if turso_ref:
            await turso_ref.update_email_status(email_id, "read")

        button.disabled = True
        button.label = "Đã xử lý xong"
        try:
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.color = 0x64748B  # Slate
                embed.title = f"📁 [Đã xử lý #{email_id}] {self.email_item['subject']}"
                await interaction.response.edit_message(embed=embed, view=self)
                return
        except Exception:
            pass

        await interaction.response.send_message(f"✅ Đã đánh dấu thư `#{email_id}` là đã xử lý.", ephemeral=True)

async def dispatch_email_to_discord(email_item: dict):
    """Sends notification with interactive buttons to Owner DM and Reminder Channel."""
    if not bot_ref:
        log.warning("bot_ref is None, skipping Discord dispatch.")
        return

    await bot_ref.wait_until_ready()
    email_id = email_item["id"]
    sender = email_item["sender"]
    subject = email_item["subject"]
    body = email_item.get("body_text", "") or "(Không có nội dung văn bản)"
    status = email_item.get("status", "unread")
    is_reply = email_item.get("is_reply", 0)

    preview = body[:800] + ("..." if len(body) > 800 else "")
    is_followup = (status == "user_replied" or is_reply)

    color = 0xA855F7 if is_followup else 0x3B82F6
    title = f"↩️ [KHÁCH PHẢN HỒI #{email_id}] Khách đã trả lời email!" if is_followup else f"📬 [EMAIL MỚI #{email_id}] Hỗ trợ khách hàng"

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 Người gửi", value=f"`{sender}`", inline=True)
    embed.add_field(name="🆔 Mã thư (ID)", value=f"`{email_id}`", inline=True)
    embed.add_field(name="📌 Tiêu đề", value=f"**{subject}**", inline=False)
    embed.add_field(name="📝 Nội dung tóm tắt", value=f"```\n{preview}\n```", inline=False)

    if is_followup:
        embed.set_footer(text=f"⚡ Khách hàng gửi tiếp trong luồng hội thoại cũ • {SUPPORT_EMAIL}")
    else:
        embed.set_footer(text=f"⚡ Nhận thư từ {SUPPORT_EMAIL} qua Resend Inbound Webhook")

    # 1. Send DM to Owner
    try:
        owner = bot_ref.get_user(OWNER_ID) or await bot_ref.fetch_user(OWNER_ID)
        if owner:
            view_dm = EmailNotificationView(email_item=email_item)
            await owner.send(embed=embed, view=view_dm)
            log.info(f"📩 Email DM sent to Owner ({OWNER_ID}) for email #{email_id}")
    except Exception as e:
        log.warning(f"Could not send email DM to owner: {e}")

    # 2. Also send to Reminder Channel if configured
    try:
        if REMINDER_CHANNEL_ID:
            channel = bot_ref.get_channel(REMINDER_CHANNEL_ID)
            if channel:
                view_ch = EmailNotificationView(email_item=email_item)
                await channel.send(embed=embed, view=view_ch)
    except Exception as e:
        log.warning(f"Could not send email to channel {REMINDER_CHANNEL_ID}: {e}")

# ──────────────────────────────────────────────
# RESEND INBOUND WEBHOOK ENDPOINT
# ──────────────────────────────────────────────
@mail_router.post("/api/webhook/resend")
@mail_router.post("/api/email-webhook")
async def handle_resend_webhook(request: Request):
    """
    Receives incoming emails from Resend Inbound Webhook.
    Extracts sender, subject, body, determines if it's a thread reply,
    stores in DB, and dispatches interactive alert to Discord bot.
    """
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

        # Optional Svix / Resend Webhook Signature Verification
        svix_id = request.headers.get("svix-id")
        svix_timestamp = request.headers.get("svix-timestamp")
        svix_sig = request.headers.get("svix-signature")
        secret = os.getenv("RESEND_WEBHOOK_SECRET", RESEND_WEBHOOK_SECRET).strip()

        if secret and svix_id and svix_timestamp and svix_sig:
            try:
                import base64
                raw_sec = secret[6:] if secret.startswith("whsec_") else secret
                key_bytes = base64.b64decode(raw_sec)
                to_sign = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + body_bytes
                computed_sig = base64.b64encode(hmac.new(key_bytes, to_sign, hashlib.sha256).digest()).decode("utf-8")
                if any(part.split(",", 1)[-1] == computed_sig for part in svix_sig.split(" ")):
                    log.info(f"🔐 Verified authentic Resend webhook signature (ID: {svix_id})")
                else:
                    log.warning(f"⚠️ Webhook signature mismatch for svix-id {svix_id}")
            except Exception as sig_err:
                log.warning(f"Signature check warning: {sig_err}")

        data = await request.json()
    except Exception as e:
        log.error(f"Error reading webhook JSON: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

    # Resend webhook payload format can be wrapped in `data` or direct
    payload = data.get("data", data)

    # Extract sender
    raw_from = payload.get("from") or payload.get("sender") or ""
    sender = str(raw_from).strip()
    if "<" in sender and ">" in sender:
        sender = sender.split("<")[-1].split(">")[0].strip()

    raw_to = payload.get("to") or [SUPPORT_EMAIL]
    recipient = raw_to[0] if isinstance(raw_to, list) and raw_to else str(raw_to)

    subject = str(payload.get("subject", "(Không có tiêu đề)")).strip()
    body_text = str(payload.get("text", "")).strip()
    body_html = str(payload.get("html", "")).strip()

    if not body_text and body_html:
        # Minimal text fallback
        body_text = body_html.replace("<br>", "\n").replace("</p>", "\n")

    # Generate unique ID for this email
    email_id = f"EM-{secrets.token_hex(3).upper()}"

    # Check if this is a reply to an existing email / thread
    status = "unread"
    thread_id = email_id
    is_reply = 0

    if turso_ref:
        existing_thread = await turso_ref.find_existing_thread(sender=sender, subject=subject)
        if existing_thread or subject.lower().startswith("re:"):
            status = "user_replied"
            is_reply = 1
            if existing_thread:
                thread_id = existing_thread.get("thread_id", existing_thread.get("id", email_id))
                # Update status of previous email to reflect user replied
                await turso_ref.update_email_status(existing_thread.get("id"), "user_replied")
            log.info(f"🔄 Detected conversation reply from {sender} on thread {thread_id}")

        saved_item = await turso_ref.save_support_email(
            email_id=email_id,
            thread_id=thread_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            status=status,
            is_reply=is_reply
        )
    else:
        saved_item = {
            "id": email_id,
            "thread_id": thread_id,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "status": status,
            "is_reply": is_reply,
            "created_at": format_vn_time()
        }

    # Dispatch to Discord Bot
    if bot_ref and bot_ref.is_ready():
        asyncio.run_coroutine_threadsafe(dispatch_email_to_discord(saved_item), bot_ref.loop)

    log.info(f"📥 Received incoming email #{email_id} from {sender} -> {subject}")
    return JSONResponse({"status": "received", "id": email_id, "thread_id": thread_id, "mode": status})

# ──────────────────────────────────────────────
# WEB MANAGEMENT PORTAL (/manage)
# ──────────────────────────────────────────────
def render_login_html(error: str = "") -> str:
    err_block = f'<div style="background:rgba(239,68,68,0.15);border:1px solid #ef4444;color:#fca5a5;padding:12px;border-radius:8px;margin-bottom:20px;font-size:14px;text-align:center;">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đăng Nhập Quản Lý · AIClaw Sentinel</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #080a10;
      color: #f8fafc;
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .card {{
      background: #0f121d;
      border: 1px solid rgba(99, 102, 241, 0.25);
      box-shadow: 0 20px 40px -15px rgba(0,0,0,0.7), 0 0 30px rgba(99, 102, 241, 0.1);
      border-radius: 16px;
      width: 100%;
      max-width: 420px;
      padding: 36px 32px;
    }}
    .logo {{
      font-size: 32px;
      text-align: center;
      margin-bottom: 12px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      text-align: center;
      margin-bottom: 6px;
      color: #ffffff;
      letter-spacing: -0.02em;
    }}
    p.sub {{
      font-size: 13px;
      color: #94a3b8;
      text-align: center;
      margin-bottom: 24px;
    }}
    .input-group {{
      margin-bottom: 20px;
    }}
    label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #cbd5e1;
      margin-bottom: 8px;
    }}
    input[type="password"] {{
      width: 100%;
      padding: 12px 14px;
      background: #181c2b;
      border: 1px solid #2e354f;
      border-radius: 10px;
      color: #f8fafc;
      font-size: 14px;
      font-family: 'JetBrains Mono', monospace;
      outline: none;
      transition: all 0.2s;
    }}
    input[type="password"]:focus {{
      border-color: #6366f1;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
    }}
    button {{
      width: 100%;
      padding: 13px;
      background: linear-gradient(135deg, #4f46e5, #6366f1);
      border: none;
      border-radius: 10px;
      color: #ffffff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
    }}
    button:hover {{
      background: linear-gradient(135deg, #4338ca, #4f46e5);
      transform: translateY(-1px);
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🦅</div>
    <h1>AIClaw Mail Sentinel</h1>
    <p class="sub">Quản trị email bảo mật • {SUPPORT_EMAIL}</p>
    {err_block}
    <form method="POST" action="/manage/login">
      <div class="input-group">
        <label for="password">Mật khẩu xác thực</label>
        <input type="password" id="password" name="password" placeholder="••••••••••••••••" autofocus required>
      </div>
      <button type="submit">Mở Khóa Quản Lý ➔</button>
    </form>
  </div>
</body>
</html>"""

def render_dashboard_html(emails: List[Dict[str, Any]], success_msg: str = "", error_msg: str = "") -> str:
    has_resend_key = bool(os.getenv("RESEND_API_KEY", RESEND_API_KEY).strip())

    total = len(emails)
    unread = sum(1 for e in emails if e.get("status") == "unread")
    replied = sum(1 for e in emails if e.get("status") == "replied")
    user_replied = sum(1 for e in emails if e.get("status") == "user_replied")

    key_badge = '<span class="status-pill green">🟢 Resend API Ready</span>' if has_resend_key else '<span class="status-pill yellow">🟠 Thiếu RESEND_API_KEY</span>'

    warning_banner = ""
    if not has_resend_key:
        warning_banner = """
        <div class="banner-warn">
          <strong>⚠️ Chưa thiết lập RESEND_API_KEY:</strong> Bạn vẫn có thể theo dõi và nhận email bình thường. Nhưng để gửi phản hồi, hãy đăng ký miễn phí tại <a href="https://resend.com/api-keys" target="_blank">resend.com/api-keys</a> và thêm biến <code>RESEND_API_KEY</code> vào file <code>.env</code> (hoặc Environment của Render).
        </div>
        """

    feedback_html = ""
    if success_msg:
        feedback_html += f'<div class="banner-success">✅ {success_msg}</div>'
    if error_msg:
        feedback_html += f'<div class="banner-error">❌ {error_msg}</div>'

    # Build Email Rows
    email_cards_html = ""
    if not emails:
        email_cards_html = '<div class="empty-box">📭 Chưa có email nào được gửi đến support@aegixbot.xyz</div>'
    else:
        for em in emails:
            eid = em.get("id", "EM-???")
            st = em.get("status", "unread")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "(Không có tiêu đề)")
            created_at = em.get("created_at", "")
            body = em.get("body_text") or em.get("body_html") or "(Nội dung trống)"
            is_reply = em.get("is_reply", 0)

            if st == "unread":
                badge = '<span class="badge badge-unread">MỚI</span>'
            elif st == "user_replied":
                badge = '<span class="badge badge-purple">KHÁCH ĐÃ REPLY</span>'
            elif st == "replied":
                badge = '<span class="badge badge-green">ĐÃ TRẢ LỜI</span>'
            else:
                badge = '<span class="badge badge-gray">ĐÃ ĐỌC</span>'

            # Clean display for body
            safe_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            email_cards_html += f"""
            <div class="mail-item" id="item-{eid}">
              <div class="mail-header" onclick="toggleMail('{eid}')">
                <div class="mail-title-group">
                  {badge}
                  <span class="mail-sender">{sender}</span>
                  <span class="mail-id">#{eid}</span>
                </div>
                <div class="mail-date">{created_at}</div>
              </div>
              <div class="mail-subject" onclick="toggleMail('{eid}')">{subject}</div>
              
              <div class="mail-body-container" id="body-{eid}">
                <div class="mail-body-text">{safe_body}</div>
                <div class="mail-actions">
                  <button type="button" class="btn-reply-fill" onclick="prefillReply('{sender}', '{subject}')">
                    ✍️ Phản hồi thư này
                  </button>
                  <form method="POST" action="/manage/status" style="display:inline;">
                    <input type="hidden" name="email_id" value="{eid}">
                    <input type="hidden" name="status" value="{'read' if st != 'read' else 'unread'}">
                    <button type="submit" class="btn-secondary-sm">
                      {'Đánh dấu đã đọc' if st != 'read' else 'Đánh dấu chưa đọc'}
                    </button>
                  </form>
                </div>
              </div>
            </div>
            """

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quản Lý Email · support@aegixbot.xyz</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #07090e;
      --card: #0f121d;
      --border: #1f263d;
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      padding: 24px 20px;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-logo {{
      font-size: 28px;
    }}
    .brand-info h1 {{
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }}
    .brand-info p {{
      font-size: 13px;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }}
    .header-right {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }}
    .status-pill.green {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }}
    .status-pill.yellow {{ background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }}
    .btn-logout {{
      padding: 8px 14px;
      background: #181d2e;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.2s;
    }}
    .btn-logout:hover {{ color: #f8fafc; border-color: #ef4444; }}

    /* Alerts */
    .banner-warn {{
      background: rgba(234, 179, 8, 0.1);
      border: 1px solid #eab308;
      color: #fef08a;
      padding: 14px 18px;
      border-radius: 10px;
      margin-bottom: 20px;
      font-size: 14px;
      line-height: 1.5;
    }}
    .banner-warn a {{ color: #38bdf8; text-decoration: underline; }}
    .banner-success {{
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid #22c55e;
      color: #86efac;
      padding: 12px 18px;
      border-radius: 10px;
      margin-bottom: 20px;
      font-size: 14px;
    }}
    .banner-error {{
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid #ef4444;
      color: #fca5a5;
      padding: 12px 18px;
      border-radius: 10px;
      margin-bottom: 20px;
      font-size: 14px;
    }}

    /* Metrics */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }}
    .metric-card {{
      background: var(--card);
      border: 1px solid var(--border);
      padding: 18px 20px;
      border-radius: 12px;
    }}
    .metric-num {{
      font-size: 26px;
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .metric-label {{
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }}

    /* Layout Split */
    .main-grid {{
      display: grid;
      grid-template-columns: 1fr 420px;
      gap: 24px;
      align-items: start;
    }}
    @media (max-width: 900px) {{
      .main-grid {{ grid-template-columns: 1fr; }}
    }}

    .section-title {{
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    /* Email Items */
    .mail-item {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
      transition: border-color 0.2s;
    }}
    .mail-item:hover {{
      border-color: rgba(99, 102, 241, 0.4);
    }}
    .mail-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      margin-bottom: 8px;
      gap: 10px;
    }}
    .mail-title-group {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .mail-sender {{
      font-weight: 600;
      font-size: 14px;
      color: #ffffff;
    }}
    .mail-id {{
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      background: #181d2e;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .mail-date {{
      font-size: 12px;
      color: var(--text-muted);
      white-space: nowrap;
    }}
    .mail-subject {{
      font-size: 14px;
      font-weight: 500;
      color: #cbd5e1;
      cursor: pointer;
    }}

    .mail-body-container {{
      display: none;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border);
    }}
    .mail-body-text {{
      font-size: 14px;
      line-height: 1.6;
      color: #94a3b8;
      white-space: pre-wrap;
      word-break: break-word;
      background: #080a10;
      padding: 14px;
      border-radius: 8px;
      border: 1px solid #1a1f33;
      margin-bottom: 12px;
    }}
    .mail-actions {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .btn-reply-fill {{
      padding: 7px 14px;
      background: var(--primary);
      border: none;
      border-radius: 6px;
      color: #ffffff;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn-reply-fill:hover {{ background: var(--primary-hover); }}
    .btn-secondary-sm {{
      padding: 7px 12px;
      background: #181d2e;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text-muted);
      font-size: 12px;
      cursor: pointer;
    }}
    .btn-secondary-sm:hover {{ color: #ffffff; }}

    /* Badges */
    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .badge-unread {{ background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }}
    .badge-purple {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }}
    .badge-green {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }}
    .badge-gray {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.25); }}

    /* Compose Box */
    .compose-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 22px;
      position: sticky;
      top: 24px;
    }}
    .form-group {{
      margin-bottom: 14px;
    }}
    .form-group label {{
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: #94a3b8;
      margin-bottom: 6px;
    }}
    .form-group input, .form-group textarea {{
      width: 100%;
      background: #080a10;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: #ffffff;
      padding: 10px 12px;
      font-size: 13px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s;
    }}
    .form-group input:focus, .form-group textarea:focus {{
      border-color: var(--primary);
    }}
    .btn-submit {{
      width: 100%;
      padding: 12px;
      background: linear-gradient(135deg, var(--primary), #3b82f6);
      border: none;
      border-radius: 8px;
      color: #ffffff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
      transition: all 0.2s;
    }}
    .btn-submit:hover {{
      transform: translateY(-1px);
      box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
    }}
    .empty-box {{
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
      background: var(--card);
      border: 1px dashed var(--border);
      border-radius: 12px;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div class="brand">
        <div class="brand-logo">🦅</div>
        <div class="brand-info">
          <h1>AIClaw Mail Management Sentinel</h1>
          <p>{SUPPORT_EMAIL} • Render Web Service</p>
        </div>
      </div>
      <div class="header-right">
        {key_badge}
        <a href="/manage/logout" class="btn-logout">Đăng Xuất</a>
      </div>
    </header>

    {warning_banner}
    {feedback_html}

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-num" style="color: #60a5fa;">{total}</div>
        <div class="metric-label">Tổng Thư Đã Nhận</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" style="color: #facc15;">{unread}</div>
        <div class="metric-label">Thư Mới Chưa Đọc</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" style="color: #c084fc;">{user_replied}</div>
        <div class="metric-label">Khách Đã Reply Lại</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" style="color: #4ade80;">{replied}</div>
        <div class="metric-label">Đã Gửi Phản Hồi</div>
      </div>
    </div>

    <div class="main-grid">
      <!-- Left: Mail Feed -->
      <div>
        <div class="section-title">📬 Hòm Thư Hỗ Trợ Khách Hàng ({total})</div>
        <div class="mail-list">
          {email_cards_html}
        </div>
      </div>

      <!-- Right: Compose Form -->
      <div>
        <div class="compose-card">
          <div class="section-title">✍️ Soạn Thư / Trả Lời Khách</div>
          <form method="POST" action="/manage/send">
            <div class="form-group">
              <label>Người gửi (Từ hệ thống)</label>
              <input type="text" value="{SUPPORT_EMAIL}" disabled style="opacity:0.7;cursor:not-allowed;">
            </div>
            <div class="form-group">
              <label for="recipient">Người nhận (Email khách hàng)</label>
              <input type="email" id="recipient" name="recipient" placeholder="khachhang@gmail.com" required>
            </div>
            <div class="form-group">
              <label for="subject">Tiêu đề</label>
              <input type="text" id="subject" name="subject" placeholder="Hỗ trợ yêu cầu tài khoản Aegix..." required>
            </div>
            <div class="form-group">
              <label for="body">Nội dung email</label>
              <textarea id="body" name="body" rows="7" placeholder="Chào bạn, cảm ơn bạn đã liên hệ Aegix Support..." required></textarea>
            </div>
            <button type="submit" class="btn-submit">✉️ Gửi Thư Qua Resend</button>
          </form>
        </div>
      </div>
    </div>
  </div>

  <script>
    function toggleMail(id) {{
      const el = document.getElementById('body-' + id);
      if (el) {{
        el.style.display = el.style.display === 'block' ? 'none' : 'block';
      }}
    }}

    function prefillReply(sender, subject) {{
      const recipientInput = document.getElementById('recipient');
      const subjectInput = document.getElementById('subject');
      const bodyInput = document.getElementById('body');

      if (recipientInput) recipientInput.value = sender;
      if (subjectInput) {{
        subjectInput.value = subject.toLowerCase().startsWith('re:') ? subject : 'Re: ' + subject;
      }}
      if (bodyInput) {{
        bodyInput.focus();
        bodyInput.placeholder = 'Nhập nội dung phản hồi cho ' + sender + '...';
      }}
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}
  </script>
</body>
</html>"""

# ──────────────────────────────────────────────
# FASTAPI ROUTES FOR /manage
# ──────────────────────────────────────────────
@mail_router.get("/manage", response_class=HTMLResponse)
async def manage_portal(request: Request, msg: str = "", err: str = ""):
    """Hidden management interface for support emails."""
    if not is_manage_authenticated(request):
        return HTMLResponse(render_login_html(error="Vui lòng nhập mật khẩu quản trị để tiếp tục." if err == "1" else ""))

    emails = []
    if turso_ref:
        emails = await turso_ref.get_all_emails(limit=100)

    return HTMLResponse(render_dashboard_html(emails=emails, success_msg=msg, error_msg=err))

@mail_router.post("/manage/login")
async def manage_login(request: Request):
    """Validates management password (Iamprmgvyt2013@)."""
    form_data = await get_form_data(request)
    password = form_data.get("password", "").strip()
    expected = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD).strip()
    if hmac.compare_digest(password, expected):
        token = get_auth_token()
        resp = RedirectResponse(url="/manage", status_code=303)
        resp.set_cookie(
            key="aiclaw_manage_session",
            value=token,
            max_age=2592000,  # 30 days
            httponly=True,
            samesite="lax"
        )
        return resp
    else:
        return HTMLResponse(render_login_html(error="Mật khẩu quản trị không chính xác! Vui lòng thử lại."), status_code=401)

@mail_router.get("/manage/logout")
async def manage_logout():
    """Logs out and clears session cookie."""
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("aiclaw_manage_session")
    return resp

@mail_router.post("/manage/send")
async def manage_send(request: Request):
    """Sends an email directly from the web interface using Resend."""
    if not is_manage_authenticated(request):
        return RedirectResponse(url="/manage?err=1", status_code=303)

    form_data = await get_form_data(request)
    recipient_clean = form_data.get("recipient", "").strip()
    subject_clean = form_data.get("subject", "").strip()
    body_clean = form_data.get("body", "").strip()

    if not recipient_clean or not subject_clean or not body_clean:
        return RedirectResponse(url="/manage?err=Vui+lòng+điền+đầy+đủ+thông+tin+email", status_code=303)

    ok, message = await send_resend_email(to_email=recipient_clean, subject=subject_clean, text=body_clean)

    if ok:
        # Save outgoing email to DB
        if turso_ref:
            out_id = f"OUT-{secrets.token_hex(3).upper()}"
            await turso_ref.save_support_email(
                email_id=out_id,
                thread_id=out_id,
                sender=SUPPORT_EMAIL,
                recipient=recipient_clean,
                subject=subject_clean,
                body_text=body_clean,
                status="replied",
                is_reply=1
            )
        return RedirectResponse(url=f"/manage?msg=Đã+gửi+thành+công+tới+{recipient_clean}", status_code=303)
    else:
        return RedirectResponse(url=f"/manage?err={message}", status_code=303)

@mail_router.post("/manage/status")
async def manage_update_status(request: Request):
    """Updates status of an email (unread, read, replied)."""
    if not is_manage_authenticated(request):
        return RedirectResponse(url="/manage?err=1", status_code=303)

    form_data = await get_form_data(request)
    email_id = form_data.get("email_id", "").strip()
    status = form_data.get("status", "").strip()

    if turso_ref and email_id:
        await turso_ref.update_email_status(email_id, status)

    return RedirectResponse(url="/manage", status_code=303)

# ──────────────────────────────────────────────
# ATTACH TO MAIN RUNNER
# ──────────────────────────────────────────────
def setup_mail_system(bot_instance: commands.Bot, turso_instance: Any, app_instance: Any):
    """Binds bot, turso DB, and FastAPI app to the mail manager."""
    global bot_ref, turso_ref
    bot_ref = bot_instance
    turso_ref = turso_instance
    app_instance.include_router(mail_router)
    log.info(f"📧 AIClaw Mail System attached: /manage (Protected) & Webhook /api/webhook/resend for {SUPPORT_EMAIL}")
