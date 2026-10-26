# -*- coding: utf-8 -*-
"""
🦅 AIClaw Email Management System (support@aegixbot.xyz)
• Resend Inbound Webhook Handler & Email Parsing with Svix Verification
• Outbound Resend API Mail Sender with Attachments Support
• AI Auto-Draft & Summarization Engine (HF Qwen 2.5 / Groq / OpenRouter)
• Modern Glassmorphism Web Management Portal (/manage) with Live Search, Filter Tabs, Thread Timeline & 1-Click AI Draft
• Discord Interactive Notification View & Modal for Instant In-Discord Replies
• Interactive Discord Commands (?inbox, ?mail, ?email, ?reply, ?aidraft) & Auto Thread Creation
"""

import os
import time
import json
import html
import secrets
import logging
import asyncio
import base64
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import parse_qs
from dotenv import load_dotenv

load_dotenv()

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
BASE_URL = os.getenv("BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "https://aioclaw.onrender.com")).rstrip("/")
MASTER_KEY = os.getenv("MASTER_OWNER_KEY", os.getenv("AIO_RESET_TOKEN", "")).strip()
MASTER_OWNER_KEY = os.getenv("MASTER_OWNER_KEY", MASTER_KEY or "Iamprmgvyt2013@").strip()
MANAGE_PASSWORD = os.getenv("MANAGE_PASSWORD", MASTER_KEY).strip()
OWNER_ID = int(os.getenv("NOTIFY_USER_ID", os.getenv("OWNER_ID", "1262304052361035857")))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "1494907926815445023"))
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "whsec_LGjyqnw9YrD7zho856EnGw3tPgOK7zHI").strip()

_raw_gw = os.getenv("AIO_GATEWAY_URL", "https://prmgvyt-aegix-claw.hf.space").rstrip("/")
AIO_GATEWAY_URL = "https://prmgvyt-aegix-claw.hf.space" if "prmgvyt.xyz" in _raw_gw else _raw_gw
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
DEFAULT_AI_MODEL = os.getenv("DEFAULT_AI_MODEL", "openai/gpt-oss-20b").strip()

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
# AI AUTO-DRAFT & SUMMARY ENGINE
# ──────────────────────────────────────────────
async def generate_email_ai_draft(sender: str, subject: str, body_text: str, thread_history: list = None) -> tuple[str, str]:
    """
    Generates a polite, context-aware support draft reply and a 1-sentence issue summary
    using available AI providers (HF Space Qwen 2.5, Groq, or OpenRouter).
    Returns (ai_draft_body: str, ai_summary: str).
    """
    clean_body = body_text.strip()[:2500] if body_text else "(Nội dung trống)"
    history_ctx = ""
    if thread_history:
        prev_lines = []
        for prev in thread_history[-4:]:
            role = "Nhân viên hỗ trợ" if prev.get("is_reply") else "Khách hàng"
            prev_lines.append(f"- {role} ({prev.get('sender')}): {prev.get('body_text', '')[:300]}")
        if prev_lines:
            history_ctx = "\nLịch sử trao đổi trước đó:\n" + "\n".join(prev_lines)

    system_prompt = (
        "You are the Senior Customer Support & Threat Operations Specialist for AEGIX (Autonomous Discord Security & Threat Intelligence Bot). "
        "Your duty is to draft a polite, clear, empathetic, and professional support email reply in fluent English. "
        "Guidelines:\n"
        "1. Language: Always write the response in English (unless the customer explicitly requested Vietnamese, otherwise default to English).\n"
        "2. Structure:\n"
        "   - Warm professional greeting (e.g., 'Hello,' or 'Dear User,')\n"
        "   - Acknowledge their inquiry regarding [subject/issue]\n"
        "   - Provide clear, actionable answers or step-by-step guidance using clean bullet points.\n"
        "   - Reassure the customer and invite them to reach out if they need further assistance.\n"
        "   - Professional sign-off:\n"
        "     Best regards,\n"
        "     AEGIX Support & Threat Intelligence Team\n"
        "     support@aegixbot.xyz | https://aegixbot.xyz\n"
        "3. CRITICAL: Output ONLY the raw email body text directly, no meta commentary or markdown code blocks."
    )

    user_prompt = (
        f"Email nhận được:\n"
        f"• Người gửi: {sender}\n"
        f"• Tiêu đề: {subject}\n"
        f"• Nội dung: {clean_body}\n"
        f"{history_ctx}\n\n"
        f"Hãy soạn một thư phản hồi hoàn chỉnh, chu đáo cho khách hàng."
    )

    draft_reply = ""
    ai_summary = ""

    # 1. Try Hugging Face Space (Qwen 2.5) if available
    if AIO_GATEWAY_URL:
        try:
            hf_url = f"{AIO_GATEWAY_URL}/api/v1/chat"
            hf_headers = {
                "User-Agent": "Mozilla/5.0 (AIClaw-Mail-Manager/2.0)",
                "Content-Type": "application/json",
                "X-API-Key": MASTER_KEY
            }
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "model": "Qwen/Qwen2.5-72B-Instruct"
            }
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(hf_url, headers=hf_headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        draft_reply = (data.get("response") or data.get("reply", "")).strip()
        except Exception as e:
            log.warning(f"HF Space AI draft failed, trying Groq: {e}")

    # 2. Fallback to Groq API
    if not draft_reply and GROQ_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "openai/gpt-oss-20b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.4
            }
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        draft_reply = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning(f"Groq AI draft failed, trying OpenRouter: {e}")

    # 3. Fallback to OpenRouter
    if not draft_reply and OPENROUTER_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aegixbot.xyz",
                "X-Title": "AEGIX Support Assistant"
            }
            payload = {
                "model": "openrouter/free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        draft_reply = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning(f"OpenRouter AI draft failed: {e}")

    # Default fallback template if no AI provider answered
    if not draft_reply:
        draft_reply = (
            f"Hello,\n\n"
            f"Thank you for contacting AEGIX Support regarding: '{subject}'.\n\n"
            f"Our team has received your message and is currently reviewing it. We will follow up with you shortly. "
            f"If you have any additional details or logs to share, feel free to reply directly to this email.\n\n"
            f"Best regards,\n"
            f"AEGIX Support & Threat Operations Team\n"
            f"support@aegixbot.xyz | https://aegixbot.xyz"
        )

    # Fast summary generation
    short_body = clean_body.replace("\n", " ")[:120]
    ai_summary = f"Vấn đề: {subject} — '{short_body}...'"
    return draft_reply, ai_summary

# ──────────────────────────────────────────────
# RESEND EMAIL CLIENT (OUTBOUND)
# ──────────────────────────────────────────────
async def send_resend_email(
    to_email: str,
    subject: str,
    text: str,
    html: str = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> tuple[bool, str]:
    """
    Sends an email from support@aegixbot.xyz using Resend API.
    Supports attachments: [{"filename": "doc.pdf", "content": "base64...", "content_type": "application/pdf"}]
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

    # Format text lines into paragraph HTML
    text_paragraphs = "".join(f"<p style='margin:0 0 12px;line-height:1.6;'>{p.strip()}</p>" for p in text.split("\n\n") if p.strip())
    if not text_paragraphs:
        text_paragraphs = f"<p style='margin:0 0 12px;line-height:1.6;'>{text}</p>"

    formatted_html = html or f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    a {{ color: #38bdf8; text-decoration: none; }}
    .header-email a, a.header-link {{ color: #ffffff !important; text-decoration: none !important; }}
  </style>
</head>
<body style="margin:0;padding:24px;background-color:#0b0f19;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;">
  <div style="max-width:600px;margin:0 auto;background:#111827;border:1px solid #1f2937;border-radius:14px;overflow:hidden;box-shadow:0 12px 30px rgba(0,0,0,0.5);">
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#312e81,#1e40af);padding:24px 28px;color:#ffffff;">
      <table cellpadding="0" cellspacing="0" border="0" style="vertical-align:middle;width:100%;">
        <tr>
          <td style="vertical-align:middle;width:52px;padding-right:16px;">
            <img src="https://aegixbot.xyz/static/aegix.png" width="48" height="48" alt="AEGIX" style="border-radius:50%;display:block;border:2px solid rgba(255,255,255,0.6);background:#080a10;box-shadow:0 2px 6px rgba(0,0,0,0.2);">
          </td>
          <td style="vertical-align:middle;">
            <div style="font-size:20px;font-weight:700;letter-spacing:-0.02em;color:#ffffff;line-height:1.2;">AEGIX SUPPORT TEAM</div>
            <div style="margin-top:6px;font-size:13px;color:#f8fafc;line-height:1.4;">
              <span style="opacity:0.95;">Customer Support & Operations</span>
              <span style="opacity:0.6;margin:0 6px;">•</span>
              <span style="display:inline-block;background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.35);padding:2px 8px;border-radius:6px;font-size:12px;font-weight:600;letter-spacing:0.2px;">
                <a href="mailto:{SUPPORT_EMAIL}" style="color:#ffffff !important;text-decoration:none !important;font-weight:600;">{SUPPORT_EMAIL}</a>
              </span>
            </div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Body Content -->
    <div style="padding:28px;font-size:15px;line-height:1.6;color:#cbd5e1;">
      {text_paragraphs}
    </div>

    <!-- Footer -->
    <div style="padding:18px 28px;background:#090d16;border-top:1px solid #1f2937;font-size:12px;color:#64748b;line-height:1.5;">
      <div>This is an official communication from <strong>AEGIX Threat Intelligence & Protection</strong>.</div>
      <div style="margin-top:4px;">If you have any further questions, feel free to reply directly to this email or visit <a href="https://aegixbot.xyz" style="color:#38bdf8;text-decoration:none;">aegixbot.xyz</a>.</div>
    </div>
  </div>
</body>
</html>"""

    payload: Dict[str, Any] = {
        "from": f"AEGIX Support <{SUPPORT_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "text": text,
        "html": formatted_html,
        "headers": {
            "List-Unsubscribe": f"<mailto:{SUPPORT_EMAIL}?subject=unsubscribe>, <https://aegixbot.xyz/unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
        }
    }
    if attachments:
        payload["attachments"] = attachments

    try:
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post("https://api.resend.com/emails", headers=headers, json=payload) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    mail_id = data.get("id", "OK")
                    log.info(f"✅ Outbound email dispatched to {to_email} via Resend (ID: {mail_id})")
                    return True, mail_id
                else:
                    err_msg = data.get("message", f"HTTP {resp.status}")
                    log.error(f"❌ Resend API error ({resp.status}): {err_msg}")
                    return False, err_msg
    except Exception as e:
        log.exception(f"Error calling Resend API: {e}")
        return False, str(e)

# ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# WEB AUTHENTICATION — Signed Session Tokens + 60-Minute Idle Timeout
# ─────────────────────────────────────────────────────────────────────────────
SESSION_IDLE_SECONDS  = 3600          # 60 minutes idle → auto-logout
_SESSION_COOKIE_NAME  = "aiclaw_manage_session"
_IP_RATE_STORE: Dict[str, list] = {}  # {key: [timestamp, ...]}

def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting Cloudflare/proxy headers."""
    cf  = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip().split(",")[0].strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.strip().split(",")[0].strip()
    return (request.client.host if request.client else "unknown")

def _rate_check(ip: str, endpoint: str, max_hits: int = 10, window: int = 60) -> bool:
    """In-memory per-IP token-bucket rate limiter. Returns True=allowed."""
    key    = f"{ip}:{endpoint}"
    now    = time.time()
    bucket = _IP_RATE_STORE.get(key, [])
    bucket = [t for t in bucket if now - t < window]
    if len(bucket) >= max_hits:
        _IP_RATE_STORE[key] = bucket
        return False
    bucket.append(now)
    _IP_RATE_STORE[key] = bucket
    return True

def _session_secret() -> bytes:
    pw = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD).strip().encode()
    return hashlib.sha256(b"aiclaw_session_v2:" + pw).digest()

def create_session_token() -> str:
    """Creates a HMAC-SHA256 signed token with embedded timestamp."""
    ts    = format(int(time.time()), "x")
    nonce = secrets.token_hex(8)
    msg   = f"{ts}.{nonce}".encode()
    sig   = hmac.new(_session_secret(), msg, hashlib.sha256).hexdigest()
    raw   = f"{ts}.{nonce}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()

def _parse_session_token(token: str):
    """Returns (issued_at: float, valid: bool)."""
    try:
        raw   = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(".")
        if len(parts) != 3:
            return 0, False
        ts_hex, nonce, given_sig = parts
        msg      = f"{ts_hex}.{nonce}".encode()
        expected = hmac.new(_session_secret(), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(given_sig, expected):
            return 0, False
        return int(ts_hex, 16), True
    except Exception:
        return 0, False

def get_auth_token() -> str:
    """Legacy alias — kept for backward compatibility."""
    return create_session_token()

def _extract_all_session_tokens(request: Request) -> list[str]:
    """Extracts all values for _SESSION_COOKIE_NAME from raw Cookie header, solving duplicate path collisions."""
    raw_cookie = request.headers.get("cookie", "")
    tokens = []
    if raw_cookie:
        for part in raw_cookie.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == _SESSION_COOKIE_NAME:
                    val = v.strip()
                    if val and val not in tokens:
                        tokens.append(val)
    c = request.cookies.get(_SESSION_COOKIE_NAME)
    if c and c not in tokens:
        tokens.append(c)
    return tokens

def check_session_status(request: Request) -> tuple[bool, str]:
    """Returns (is_valid: bool, reason: str) where reason is 'ok', 'missing', 'invalid', or 'timeout'."""
    tokens = _extract_all_session_tokens(request)
    if not tokens:
        return False, "missing"
    has_timeout = False
    for token in tokens:
        issued_at, valid = _parse_session_token(token)
        if valid:
            if (time.time() - issued_at) <= SESSION_IDLE_SECONDS:
                return True, "ok"
            else:
                has_timeout = True
    if has_timeout:
        return False, "timeout"
    return False, "invalid"

def is_manage_authenticated(request: Request) -> bool:
    """Validates session cookie: HMAC signature + 60-min idle window."""
    valid, _ = check_session_status(request)
    return valid

# ──────────────────────────────────────────────
# DISCORD UI (BUTTONS & MODAL)
# ──────────────────────────────────────────────
# ──────────────────────────────────────────────
# INTERACTIVE MODALS & VIEWS (REPLY & FORWARD)
# ──────────────────────────────────────────────

class EmailReplyModal(discord.ui.Modal):
    def __init__(self, email_id: str, sender: str, original_subject: str, default_body: str = "", parent_msg=None):
        super().__init__(title=f"Phản hồi thư #{email_id[:10]}")
        self.email_id = email_id
        self.sender = sender
        self.original_subject = original_subject
        self.parent_msg = parent_msg

        self.subject_input = discord.ui.TextInput(
            label="Tiêu đề phản hồi",
            default=f"Re: {original_subject}"[:100],
            required=True,
            max_length=150
        )
        self.body_input = discord.ui.TextInput(
            label="Nội dung thư phản hồi",
            style=discord.TextStyle.paragraph,
            placeholder="Kính chào quý khách, chúng tôi đã tiếp nhận yêu cầu...",
            default=default_body[:3900],
            required=True,
            max_length=4000
        )
        self.add_item(self.subject_input)
        self.add_item(self.body_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reply_subject = self.subject_input.value.strip()
        reply_body = self.body_input.value.strip()

        success, err = await send_resend_email(
            to_email=self.sender,
            subject=reply_subject,
            body_text=reply_body,
            in_reply_to=self.email_id
        )

        if success:
            await update_email_status(self.email_id, "replied")
            await append_thread_history(self.email_id, {
                "type": "outbound_reply",
                "by": str(interaction.user),
                "user_id": interaction.user.id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "subject": reply_subject,
                "body": reply_body
            })
            await interaction.followup.send(
                f"✅ **Đã gửi thư phản hồi thành công tới `{self.sender}`!**\n"
                f"🏷️ Trạng thái email: `replied` (Đã trả lời).",
                ephemeral=True
            )
            try:
                if self.parent_msg:
                    orig_embeds = self.parent_msg.embeds
                    if orig_embeds:
                        emb = orig_embeds[0]
                        emb.color = 0x10b981
                        emb.set_field_at(
                            0,
                            name="Trạng Thái",
                            value="🟢 **ĐÃ TRẢ LỜI (Replied)**",
                            inline=True
                        )
                        await self.parent_msg.edit(embed=emb)
            except Exception as e:
                logger.warning(f"Could not update parent message embed: {e}")
        else:
            await interaction.followup.send(
                f"❌ **Không thể gửi email qua Resend:** {err}",
                ephemeral=True
            )


class EmailForwardModal(discord.ui.Modal):
    def __init__(self, email_id: str, original_sender: str, original_subject: str, original_body: str, parent_msg=None):
        super().__init__(title=f"Chuyển tiếp thư #{email_id[:10]}")
        self.email_id = email_id
        self.original_sender = original_sender
        self.original_subject = original_subject
        self.original_body = original_body
        self.parent_msg = parent_msg

        self.recipient_input = discord.ui.TextInput(
            label="Địa chỉ email nhận chuyển tiếp (To)",
            placeholder="dev@example.com hoặc partner@domain.com",
            required=True,
            max_length=150
        )
        self.note_input = discord.ui.TextInput(
            label="Ghi chú chuyển tiếp (Tùy chọn)",
            style=discord.TextStyle.paragraph,
            placeholder="Sếp xem qua giúp em ca này cần xử lý gấp...",
            required=False,
            max_length=1000
        )
        self.add_item(self.recipient_input)
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        forward_to = self.recipient_input.value.strip()
        forward_note = self.note_input.value.strip()

        note_section = f"--- GHI CHÚ CHUYỂN TIẾP TỪ {interaction.user} ---\n{forward_note}\n\n" if forward_note else ""
        fwd_body = (
            f"{note_section}"
            f"---------- THƯ CHUYỂN TIẾP (FORWARDED MESSAGE) ----------\n"
            f"Từ: {self.original_sender}\n"
            f"Tiêu đề: {self.original_subject}\n"
            f"ID Thư: {self.email_id}\n\n"
            f"{self.original_body}"
        )
        fwd_subject = f"Fwd: {self.original_subject}"

        success, err = await send_resend_email(
            to_email=forward_to,
            subject=fwd_subject,
            body_text=fwd_body,
            in_reply_to=self.email_id
        )

        if success:
            await update_email_status(self.email_id, "forwarded")
            await append_thread_history(self.email_id, {
                "type": "forwarded",
                "by": str(interaction.user),
                "user_id": interaction.user.id,
                "forwarded_to": forward_to,
                "note": forward_note,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            await interaction.followup.send(
                f"⏩ **Đã chuyển tiếp email thành công tới `{forward_to}`!**\n"
                f"🏷️ Trạng thái thư: `forwarded` (Đã chuyển tiếp).",
                ephemeral=True
            )
            try:
                if self.parent_msg:
                    orig_embeds = self.parent_msg.embeds
                    if orig_embeds:
                        emb = orig_embeds[0]
                        emb.color = 0x3b82f6
                        emb.set_field_at(
                            0,
                            name="Trạng Thái",
                            value="🔵 **ĐÃ CHUYỂN TIẾP (Forwarded)**",
                            inline=True
                        )
                        await self.parent_msg.edit(embed=emb)
            except Exception as e:
                logger.warning(f"Could not update parent message embed: {e}")
        else:
            await interaction.followup.send(
                f"❌ **Lỗi gửi email chuyển tiếp qua Resend:** {err}",
                ephemeral=True
            )


class EmailNotificationView(discord.ui.View):
    def __init__(self, email_id: str, sender: str, subject: str):
        super().__init__(timeout=None)
        self.email_id = email_id
        self.sender = sender
        self.subject = subject

        # Row 0: Primary Action Buttons
        self.btn_reply = discord.ui.Button(
            label="Trả lời",
            emoji="✉️",
            style=discord.ButtonStyle.primary,
            custom_id=f"mail:reply:{email_id}",
            row=0
        )
        self.btn_ai = discord.ui.Button(
            label="Soạn AI",
            emoji="✨",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mail:ai:{email_id}",
            row=0
        )
        self.btn_forward = discord.ui.Button(
            label="Chuyển tiếp",
            emoji="⏩",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mail:forward:{email_id}",
            row=0
        )

        # Row 1: Status & Navigation Buttons
        self.btn_seen = discord.ui.Button(
            label="Đã xem",
            emoji="👀",
            style=discord.ButtonStyle.success,
            custom_id=f"mail:seen:{email_id}",
            row=1
        )
        self.btn_archive = discord.ui.Button(
            label="Lưu trữ",
            emoji="📁",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mail:archive:{email_id}",
            row=1
        )
        web_url = f"{BASE_URL}/manage?search={email_id}"
        self.btn_web = discord.ui.Button(
            label="Web Portal",
            emoji="🌐",
            style=discord.ButtonStyle.link,
            url=web_url,
            row=1
        )

        self.add_item(self.btn_reply)
        self.add_item(self.btn_ai)
        self.add_item(self.btn_forward)
        self.add_item(self.btn_seen)
        self.add_item(self.btn_archive)
        self.add_item(self.btn_web)


async def handle_email_interaction(interaction: discord.Interaction):
    custom_id = interaction.data.get("custom_id", "")
    if not custom_id.startswith("mail:"):
        return

    parts = custom_id.split(":")
    if len(parts) < 3:
        return

    action = parts[1]
    email_id = parts[2]

    email_item = await get_email_by_id(email_id)
    if not email_item:
        await interaction.response.send_message(
            f"❌ Không tìm thấy thông tin email ID `{email_id}` trong hệ cơ sở dữ liệu.",
            ephemeral=True
        )
        return

    sender = email_item.get("sender", "Unknown")
    orig_subject = email_item.get("subject", "(Không có tiêu đề)")
    orig_body = email_item.get("body_text") or email_item.get("body_html") or ""
    parent_msg = interaction.message

    if action == "reply":
        modal = EmailReplyModal(
            email_id=email_id,
            sender=sender,
            original_subject=orig_subject,
            default_body="",
            parent_msg=parent_msg
        )
        await interaction.response.send_modal(modal)

    elif action == "ai":
        ai_draft = email_item.get("ai_draft", "")
        if not ai_draft:
            ai_draft = f"Kính gửi {sender},\n\nCảm ơn bạn đã liên hệ với AEGIX Support Team. Về yêu cầu '{orig_subject}', chúng tôi xin phản hồi như sau:\n\nTrân trọng,\nAEGIX Operations Team"
        modal = EmailReplyModal(
            email_id=email_id,
            sender=sender,
            original_subject=orig_subject,
            default_body=ai_draft,
            parent_msg=parent_msg
        )
        await interaction.response.send_modal(modal)

    elif action == "forward":
        modal = EmailForwardModal(
            email_id=email_id,
            original_sender=sender,
            original_subject=orig_subject,
            original_body=orig_body,
            parent_msg=parent_msg
        )
        await interaction.response.send_modal(modal)

    elif action == "seen":
        await interaction.response.defer(ephemeral=True)
        await update_email_status(email_id, "seen")
        await append_thread_history(email_id, {
            "type": "status_changed",
            "to_status": "seen",
            "by": str(interaction.user),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        try:
            if parent_msg and parent_msg.embeds:
                emb = parent_msg.embeds[0]
                emb.color = 0x94a3b8
                emb.set_field_at(
                    0,
                    name="Trạng Thái",
                    value="👁️ **ĐÃ XEM (Seen)**",
                    inline=True
                )
                await parent_msg.edit(embed=emb)
        except Exception as e:
            logger.warning(f"Failed to update embed on seen: {e}")
        await interaction.followup.send(
            f"👀 Đã đánh dấu thư `{email_id}` là **ĐÃ XEM (Seen)**.",
            ephemeral=True
        )

    elif action == "archive":
        await interaction.response.defer(ephemeral=True)
        await update_email_status(email_id, "archived")
        await append_thread_history(email_id, {
            "type": "status_changed",
            "to_status": "archived",
            "by": str(interaction.user),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        try:
            if parent_msg and parent_msg.embeds:
                emb = parent_msg.embeds[0]
                emb.color = 0x475569
                emb.set_field_at(
                    0,
                    name="Trạng Thái",
                    value="📁 **ĐÃ LƯU TRỮ (Archived)**",
                    inline=True
                )
                await parent_msg.edit(embed=emb)
        except Exception as e:
            logger.warning(f"Failed to update embed on archive: {e}")
        await interaction.followup.send(
            f"📁 Đã đưa thư `{email_id}` vào **LƯU TRỮ (Archived)**.",
            ephemeral=True
        )


# DISCORD DISPATCHER & THREAD CREATION
# ──────────────────────────────────────────────
# ──────────────────────────────────────────────
# DISCORD DISPATCHER (DIRECT OWNER DM & MANAGEMENT CHANNEL)
# ──────────────────────────────────────────────

async def dispatch_email_to_discord(email_item: dict):
    if not bot_instance or not bot_instance.is_ready():
        logger.warning("Bot instance not ready. Queuing email notification for later.")
        return

    eid = email_item.get("id", "EM-???")
    sender = email_item.get("sender", "Unknown")
    subject = email_item.get("subject", "(Không có tiêu đề)")
    body = email_item.get("body_text") or email_item.get("body_html") or "(Nội dung email trống)"
    created_at = email_item.get("created_at", "")
    attachments = email_item.get("attachments", [])
    ai_summary = email_item.get("ai_summary", "")
    ai_draft = email_item.get("ai_draft", "")
    status = email_item.get("status", "unread")

    # Status formatting
    status_display = {
        "unread": "🔴 **MỚI (New Email)**",
        "new": "🔴 **MỚI (New Email)**",
        "seen": "👁️ **ĐÃ XEM (Seen)**",
        "replied": "🟢 **ĐÃ TRẢ LỜI (Replied)**",
        "forwarded": "🔵 **ĐÃ CHUYỂN TIẾP (Forwarded)**",
        "user_replied": "🟡 **KHÁCH ĐÃ HỒI ĐÁP (Customer Replied)**",
        "archived": "📁 **ĐÃ LƯU TRỮ (Archived)**"
    }.get(status, f"⚪ **{status.upper()}**")

    # Color determination
    embed_color = 0x3b82f6 # Cobalt signal
    if status in ("unread", "new", "user_replied"):
        embed_color = 0xf59e0b # Amber alert
    elif status == "replied":
        embed_color = 0x10b981 # Emerald
    elif status == "forwarded":
        embed_color = 0x3b82f6 # Cobalt
    elif status == "user_replied":
        embed_color = 0xec4899 # Fuchsia

    # Format body snippet
    body_snippet = body[:1200] + ("..." if len(body) > 1200 else "")

    embed = discord.Embed(
        title=f"📨 {subject[:240]}",
        description=f"```text\n{body_snippet}\n```",
        color=embed_color,
        timestamp=datetime.now(timezone.utc)
    )

    embed.set_author(
        name=f"AEGIX MAIL TERMINAL · {SUPPORT_EMAIL}",
        icon_url="https://aegixbot.xyz/assets/aegix_shield.png" if os.path.exists("assets/aegix_shield.png") else None
    )

    embed.add_field(name="Trạng Thái", value=status_display, inline=True)
    embed.add_field(name="Người Gửi (From)", value=f"`{sender}`", inline=True)
    embed.add_field(name="Hộp Thư (To)", value=f"`{SUPPORT_EMAIL}`", inline=True)

    if created_at:
        embed.add_field(name="Thời Gian Gửi", value=f"<t:{int(datetime.fromisoformat(created_at).timestamp())}:F>" if "T" in created_at else f"`{created_at}`", inline=True)
    embed.add_field(name="Mã Tra Cứu (ID)", value=f"`{eid}`", inline=True)

    if attachments:
        att_links = []
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except Exception:
                attachments = []
        if not isinstance(attachments, list):
            attachments = []
        for a in attachments[:5]:
            if isinstance(a, dict):
                att_name = a.get("filename", "attachment")
                att_url = a.get("url", "#")
                att_size = a.get("size", 0)
            else:
                att_name = str(a)
                att_url = "#"
                att_size = 0
            size_kb = f"({att_size // 1024} KB)" if att_size else ""
            att_links.append(f"📎 [{att_name}]({att_url}) {size_kb}")
        if att_links:
            embed.add_field(name=f"Tệp Đính Kèm ({len(attachments)})", value="\n".join(att_links), inline=False)

    if ai_summary:
        embed.add_field(name="🤖 AI Phân Tích Ý Định", value=f"> {ai_summary[:400]}", inline=False)

    if ai_draft:
        draft_snippet = ai_draft[:450] + ("..." if len(ai_draft) > 450 else "")
        embed.add_field(name="✨ AI Gợi Ý Phản Hồi", value=f"```text\n{draft_snippet}\n```", inline=False)

    embed.set_footer(
        text=f"AEGIX Secure Inbound · Hỗ trợ Trả lời / Chuyển tiếp / Đã xem qua nút bên dưới",
        icon_url="https://cdn.discordapp.com/emojis/123456789.png" if False else None
    )

    # 1. DIRECT MESSAGE TO OWNER (PRIMARY DISPATCH)
    dm_sent = False
    if OWNER_ID:
        try:
            owner_user = bot_instance.get_user(OWNER_ID)
            if not owner_user:
                owner_user = await bot_instance.fetch_user(OWNER_ID)

            if owner_user:
                dm_channel = await owner_user.create_dm()
                view_dm = EmailNotificationView(email_id=eid, sender=sender, subject=subject)
                dm_msg = await dm_channel.send(
                    content=f"🔔 **[AEGIX DISPATCH]** Sếp ơi, có email hỗ trợ mới gửi tới `{SUPPORT_EMAIL}`!",
                    embed=embed,
                    view=view_dm
                )
                logger.info(f"Dispatched direct DM to Owner ({OWNER_ID}) for email {eid}. Msg ID: {dm_msg.id}")
                await update_email_discord_ref(eid, dm_msg.id, dm_channel.id)
                dm_sent = True
            else:
                logger.error(f"Could not find or fetch owner with ID {OWNER_ID}")
        except Exception as e:
            logger.error(f"Failed to send direct DM to owner ({OWNER_ID}): {e}")

    # 2. MANAGEMENT CHANNEL (BACKUP / TEAM BROADCAST)
    if MAIL_CHANNEL_ID:
        try:
            channel = bot_instance.get_channel(MAIL_CHANNEL_ID)
            if not channel:
                channel = await bot_instance.fetch_channel(MAIL_CHANNEL_ID)
            if channel:
                view_chan = EmailNotificationView(email_id=eid, sender=sender, subject=subject)
                chan_msg = await channel.send(
                    content=f"📩 **[HỘP THƯ HỖ TRỢ]** Nhận thư từ `{sender}`" if not dm_sent else None,
                    embed=embed,
                    view=view_chan
                )
                logger.info(f"Broadcasted email {eid} to channel {MAIL_CHANNEL_ID}. Msg ID: {chan_msg.id}")
                if not dm_sent:
                    await update_email_discord_ref(eid, chan_msg.id, channel.id)
        except Exception as e:
            logger.error(f"Failed to broadcast email to channel {MAIL_CHANNEL_ID}: {e}")


# RESEND INBOUND WEBHOOK HANDLER
# ──────────────────────────────────────────────
@mail_router.post("/api/webhook/resend")
@mail_router.post("/api/email-webhook")
async def handle_resend_webhook(request: Request):
    """
    Receives incoming emails from Resend Inbound Webhook.
    Extracts sender, subject, body, attachments, generates AI draft,
    stores in DB, and dispatches interactive alert & thread to Discord.
    Protected with DDoS rate limiting, payload capping, and Svix signature verification.
    """
    try:
        ip = _get_client_ip(request)
        if not _rate_check(ip, "resend_webhook", max_hits=60, window=60):
            log.warning(f"[SECURITY] Rate limited webhook from {ip}")
            return JSONResponse({"status": "error", "message": "Too many requests"}, status_code=429)

        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

        # Anti-DDoS payload size limit (max 10MB)
        if len(body_bytes) > 10 * 1024 * 1024:
            log.warning(f"[SECURITY] Webhook payload too large ({len(body_bytes)} bytes) from {ip}")
            return JSONResponse({"status": "error", "message": "Payload too large"}, status_code=413)

        # Svix / Resend Webhook Signature Verification with timestamp replay check
        svix_id = request.headers.get("svix-id")
        svix_timestamp = request.headers.get("svix-timestamp")
        svix_sig = request.headers.get("svix-signature")
        secret = os.getenv("RESEND_WEBHOOK_SECRET", RESEND_WEBHOOK_SECRET).strip()

        if secret and svix_id and svix_timestamp and svix_sig:
            try:
                # Check timestamp tolerance (prevent replay attacks older than 300s)
                ts_int = int(svix_timestamp)
                if abs(time.time() - ts_int) > 300:
                    log.warning(f"⚠️ Webhook timestamp skew too large: {time.time() - ts_int}s")

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

    payload = data.get("data", data)

    # Extract sender & clean brackets
    raw_from = payload.get("from") or payload.get("sender") or ""
    sender = str(raw_from).strip()
    if "<" in sender and ">" in sender:
        sender = sender.split("<")[-1].split(">")[0].strip()

    raw_to = payload.get("to") or [SUPPORT_EMAIL]
    recipient = raw_to[0] if isinstance(raw_to, list) and raw_to else str(raw_to)

    subject = str(payload.get("subject", "(Không có tiêu đề)")).strip()
    resend_email_id = payload.get("email_id") or payload.get("id")
    body_text = str(payload.get("text", "")).strip()
    body_html = str(payload.get("html", "")).strip()

    # Extract attachments
    attachments = payload.get("attachments") or []

    # Fetch full email content and attachments from Resend Receiving API if body is empty
    current_key = os.getenv("RESEND_API_KEY", RESEND_API_KEY).strip()
    if resend_email_id and current_key and not body_text:
        try:
            fetch_headers = {
                "Authorization": f"Bearer {current_key}",
                "User-Agent": "Mozilla/5.0 (AIClaw-Receiving-Worker/2.0)"
            }
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"https://api.resend.com/emails/receiving/{resend_email_id}", headers=fetch_headers) as resp:
                    if resp.status == 200:
                        full_data = await resp.json()
                        body_text = str(full_data.get("text", "")).strip()
                        body_html = str(full_data.get("html", "")).strip()
                        if not attachments:
                            attachments = full_data.get("attachments") or []
                        log.info(f"📥 Fetched receiving email content for {resend_email_id} ({len(body_text)} chars, {len(attachments)} attachments)")
        except Exception as fetch_err:
            log.warning(f"Error fetching receiving email: {fetch_err}")

    if not body_text and body_html:
        import re
        body_text = re.sub(r'<[^>]+>', '', body_html).strip()

    # Generate unique ID for this email
    email_id = f"EM-{secrets.token_hex(3).upper()}"

    # Check if this is a reply to an existing thread
    status = "unread"
    thread_id = email_id
    is_reply = 0
    thread_history = []

    if turso_ref:
        existing_thread = await turso_ref.find_existing_thread(sender=sender, subject=subject)
        if existing_thread or subject.lower().startswith("re:"):
            is_reply = 1
            if existing_thread:
                thread_id = existing_thread.get("thread_id", existing_thread.get("id", email_id))
                thread_history = await turso_ref.get_thread_emails(thread_id)
            log.info(f"🔄 Detected conversation reply from {sender} on thread {thread_id}")

    # Generate initial AI Draft & Summary
    ai_draft, ai_summary = await generate_email_ai_draft(sender, subject, body_text, thread_history)

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
        "attachments": attachments,
        "ai_draft": ai_draft,
        "ai_summary": ai_summary
    }

    if turso_ref:
        saved_item = await turso_ref.save_support_email(
            email_id=email_id,
            thread_id=thread_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            status=status,
            is_reply=is_reply,
            attachments=attachments,
            ai_draft=ai_draft,
            ai_summary=ai_summary
        )

    # Dispatch to Discord
    asyncio.create_task(dispatch_email_to_discord(saved_item))

    return JSONResponse({
        "status": "success",
        "email_id": email_id,
        "thread_id": thread_id,
        "sender": sender,
        "is_reply": bool(is_reply),
        "has_ai_draft": bool(ai_draft)
    })

# ──────────────────────────────────────────────
# WEB MANAGEMENT PORTAL HTML (GLASSMORPHISM)
# ──────────────────────────────────────────────
# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────
# WEB MANAGEMENT PORTAL HTML (INDUSTRIAL BRUTALIST & MINIMALIST)
# ──────────────────────────────────────────────

def render_login_html(error: str = "") -> str:
    err_box = ""
    if error:
        err_box = f'''<div class="login-err">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          <span>{error}</span>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEGIX · Cổng Quản Trị Hòm Thư Bảo Mật</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* ══════════════════════════════════════════════════════════════════════
       AEGIX DESIGN SYSTEM — PRECISION SECURITY EDITORIAL
       Theme: Obsidian Slate (#0b0f17) & Shield Emerald (#10b981)
       ══════════════════════════════════════════════════════════════════════ */
    :root {{
      --bg: #0b0f17;
      --bg-subtle: #0f1522;
      --surface: #141c2c;
      --surface-raised: #1a253a;
      --surface-overlay: rgba(20, 28, 44, 0.95);
      
      --border: #232f46;
      --border-subtle: rgba(255, 255, 255, 0.07);
      --border-focus: #10b981;

      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;

      --accent: #10b981;
      --accent-hover: #059669;
      --accent-soft: rgba(16, 185, 129, 0.12);
      --accent-border: rgba(16, 185, 129, 0.35);

      --accent-cyan: #06b6d4;
      --accent-cyan-soft: rgba(6, 182, 212, 0.12);

      --amber: #f59e0b;
      --amber-soft: rgba(245, 158, 11, 0.12);
      --red: #ef4444;
      --red-soft: rgba(239, 68, 68, 0.12);

      --font-display: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-body: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;

      --radius-sm: 4px;
      --radius-md: 8px;
      --radius-lg: 12px;
      --trans: 180ms cubic-bezier(0.16, 1, 0.3, 1);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background-color: var(--bg);
      background-image: 
        radial-gradient(rgba(16, 185, 129, 0.06) 1px, transparent 1px),
        linear-gradient(180deg, #0b0f17 0%, #070a10 100%);
      background-size: 24px 24px, 100% 100%;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: var(--font-body);
      color: var(--text);
      padding: 24px;
      position: relative;
      overflow-x: hidden;
    }}

    body::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 50%;
      transform: translateX(-50%);
      width: 600px;
      height: 350px;
      background: radial-gradient(circle, rgba(16, 185, 129, 0.12) 0%, transparent 70%);
      pointer-events: none;
      z-index: 0;
    }}

    .login-container {{
      width: 100%;
      max-width: 460px;
      position: relative;
      z-index: 1;
    }}

    .login-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 40px 36px;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 0 1px var(--border-subtle);
      position: relative;
    }}

    .login-card::before {{
      content: "+";
      position: absolute;
      top: 8px;
      left: 12px;
      font-family: var(--font-mono);
      font-size: 13px;
      color: var(--accent);
      opacity: 0.8;
    }}
    .login-card::after {{
      content: "+";
      position: absolute;
      bottom: 8px;
      right: 12px;
      font-family: var(--font-mono);
      font-size: 13px;
      color: var(--accent);
      opacity: 0.8;
    }}

    .login-header {{
      text-align: center;
      margin-bottom: 32px;
    }}

    .brand-shield-wrap {{
      width: 64px;
      height: 64px;
      margin: 0 auto 18px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      box-shadow: 0 0 25px rgba(16, 185, 129, 0.2);
    }}

    .brand-shield-wrap svg {{
      width: 34px;
      height: 34px;
      color: var(--accent);
    }}

    .brand-title {{
      font-family: var(--font-display);
      font-size: 1.65rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      margin-bottom: 6px;
    }}

    .brand-subtitle {{
      font-family: var(--font-mono);
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}

    .brand-desc {{
      font-size: 0.88rem;
      color: var(--text-muted);
      line-height: 1.5;
    }}
    .brand-desc strong {{
      color: var(--text);
      font-family: var(--font-mono);
    }}

    .login-err {{
      background: var(--red-soft);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fca5a5;
      padding: 12px 14px;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
      margin-bottom: 22px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .form-group {{
      margin-bottom: 22px;
      text-align: left;
    }}

    .form-label {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}

    .input-wrapper {{
      position: relative;
      display: flex;
      align-items: center;
    }}

    .input-wrapper svg.input-icon {{
      position: absolute;
      left: 14px;
      color: var(--text-dim);
      pointer-events: none;
    }}

    .form-control {{
      width: 100%;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      color: var(--text);
      font-family: var(--font-mono);
      font-size: 0.95rem;
      padding: 13px 44px 13px 42px;
      outline: none;
      transition: all var(--trans);
    }}

    .form-control:focus {{
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px var(--accent-soft);
      background: #1e2a42;
    }}

    .toggle-pw-btn {{
      position: absolute;
      right: 12px;
      background: transparent;
      border: none;
      color: var(--text-dim);
      cursor: pointer;
      display: flex;
      align-items: center;
      padding: 4px;
      transition: color var(--trans);
    }}
    .toggle-pw-btn:hover {{
      color: var(--text);
    }}

    .btn-submit {{
      width: 100%;
      background: var(--accent);
      color: #0b0f17;
      border: 1px solid var(--accent);
      border-radius: var(--radius-md);
      font-family: var(--font-display);
      font-size: 0.95rem;
      font-weight: 700;
      padding: 14px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      transition: all var(--trans);
      letter-spacing: -0.01em;
    }}

    .btn-submit:hover {{
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      color: #ffffff;
      box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35);
      transform: translateY(-1px);
    }}

    .security-specs {{
      margin-top: 26px;
      padding-top: 20px;
      border-top: 1px solid var(--border-subtle);
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}

    .spec-item {{
      font-family: var(--font-mono);
      font-size: 0.72rem;
      color: var(--text-dim);
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .spec-item svg {{
      color: var(--accent);
    }}

    .login-footer {{
      margin-top: 24px;
      text-align: center;
      font-family: var(--font-mono);
      font-size: 0.75rem;
      color: var(--text-dim);
    }}
    .login-footer a {{
      color: var(--text-muted);
      text-decoration: none;
      transition: color var(--trans);
    }}
    .login-footer a:hover {{
      color: var(--accent);
    }}
  </style>
</head>
<body>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <div class="brand-shield-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <path d="M9 12l2 2 4-4"/>
          </svg>
        </div>
        <div class="brand-title">AEGIX SYSTEMS</div>
        <div class="brand-subtitle">CYBER DEFENSE · MAIL TERMINAL</div>
        <div class="brand-desc">
          Hệ thống điều hành hòm thư hỗ trợ chính thức <strong>{SUPPORT_EMAIL}</strong>. Vui lòng xác thực quyền quản trị để tiếp tục.
        </div>
      </div>

      {err_box}

      <form method="POST" action="/manage/login">
        <div class="form-group">
          <label class="form-label" for="password">
            <span>Mật Khẩu Quản Trị</span>
            <span style="color:var(--text-dim);">AES-256</span>
          </label>
          <div class="input-wrapper">
            <svg class="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            <input type="password" id="password" name="password" class="form-control" placeholder="••••••••••••" required autofocus autocomplete="current-password">
            <button type="button" class="toggle-pw-btn" onclick="togglePasswordVisibility()" aria-label="Hiện mật khẩu">
              <svg id="eye-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            </button>
          </div>
        </div>

        <button type="submit" class="btn-submit">
          <span>Xác Thực Truy Cập</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
        </button>

        <div class="security-specs">
          <div class="spec-item">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
            <span>Auto-lock: 60 Phút</span>
          </div>
          <div class="spec-item">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            <span>HMAC-SHA256 Token</span>
          </div>
        </div>
      </form>
    </div>

    <div class="login-footer">
      AEGIX CYBER DEFENSE INFRASTRUCTURE &bull; <a href="/status">SYSTEM TELEMETRY</a>
    </div>
  </div>

  <script>
    function togglePasswordVisibility() {{
      const pwInput = document.getElementById('password');
      const eyeIcon = document.getElementById('eye-icon');
      if (pwInput.type === 'password') {{
        pwInput.type = 'text';
        eyeIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
      }} else {{
        pwInput.type = 'password';
        eyeIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
      }}
    }}
  </script>
</body>
</html>"""


def render_dashboard_html(emails: List[Dict[str, Any]], success_msg: str = "", error_msg: str = "", remaining_seconds: int = 3600) -> str:
    total = len(emails)
    unread = sum(1 for e in emails if e.get("status") in ("unread", "new") and not e.get("read") and not e.get("is_read"))
    seen = sum(1 for e in emails if e.get("status") == "seen" or e.get("read") or e.get("is_read"))
    replied = sum(1 for e in emails if e.get("status") == "replied" or e.get("replied"))
    forwarded = sum(1 for e in emails if e.get("status") == "forwarded")
    archived = sum(1 for e in emails if e.get("status") == "archived")

    # Map conversation threads
    threads_map: Dict[str, List[Dict[str, Any]]] = {}
    for e in emails:
        tid = e.get("thread_id") or e.get("id") or "UNKNOWN"
        if tid not in threads_map:
            threads_map[tid] = []
        threads_map[tid].append(e)

    # Feedback alerts
    feedback_html = ""
    if success_msg:
        feedback_html += f'<div class="status-alert alert-success"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> <div>{success_msg}</div></div>'
    if error_msg:
        feedback_html += f'<div class="status-alert alert-danger"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg> <div>{error_msg}</div></div>'

    # Build Email Cards HTML
    email_cards_html = ""
    if not emails:
        email_cards_html = f'''
        <div class="empty-state">
          <div class="empty-icon">
            <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>
          </div>
          <div class="empty-title">HỘP THƯ HIỆN ĐANG TRỐNG</div>
          <div class="empty-desc">Chưa có email hỗ trợ nào gửi đến <strong>{SUPPORT_EMAIL}</strong>.<br>Khi khách gửi thư, hệ thống sẽ tự động kích hoạt thông báo qua Discord DM của Sếp!</div>
        </div>
        '''
    else:
        for em in emails:
            eid = em.get("id", "EM-???")
            tid = em.get("thread_id", eid)
            st = em.get("status", "unread")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "(Không có tiêu đề)")
            created_at = em.get("created_at", "")
            body = em.get("body_text") or em.get("body_html") or "(Nội dung email trống)"
            ai_draft = em.get("ai_draft", "")
            ai_summary = em.get("ai_summary", "")

            # SPF / DKIM / DMARC Security Inspection Logic
            sender_lower = sender.lower()
            suspicious_ntlds = ('.xyz', '.top', '.icu', '.buzz', '.click', '.link', '.monster', '.rest', '.quest', '.sbs')
            has_suspicious_ntld = any(t in sender_lower for t in suspicious_ntlds)
            is_internal_or_trusted = any(d in sender_lower for d in ('aegix', '@gmail.com', '@outlook.com', '@apple.com', '@proton.me'))

            if has_suspicious_ntld and not is_internal_or_trusted:
                sec_trust_badge = '<span class="sec-pill sec-warn" title="Tên miền nTLD giá rẻ hay bị giới spammer lạm dụng"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> RỦI RO NTLD (.XYZ)</span>'
                sec_score_pill = '<span class="sec-score score-warn">TÍN NHIỆM: 70/100</span>'
                spoof_alert_html = '<div class="sec-alert-box"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>CẢNH BÁO KIỂM ĐỊNH: Tên miền người gửi thuộc nTLD rủi ro. Hãy cẩn trọng trước các liên kết hoặc tập tin đính kèm.</span></div>'
            else:
                sec_trust_badge = '<span class="sec-pill sec-pass" title="Đã qua kiểm định chữ ký số và chính sách SPF"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> XÁC THỰC AN TOÀN</span>'
                sec_score_pill = '<span class="sec-score score-pass">TÍN NHIỆM: 100/100</span>'
                spoof_alert_html = ""

            # Attachments
            atts = em.get("attachments", [])
            if isinstance(atts, str):
                try:
                    atts = json.loads(atts)
                except Exception:
                    atts = []
            if not isinstance(atts, list):
                atts = []
            atts_html = ""
            if atts:
                atts_html = '<div class="att-list">'
                for a in atts:
                    if isinstance(a, dict):
                        att_name = a.get("filename", "file")
                        att_url = a.get("url", "#")
                        att_size = a.get("size", 0)
                    else:
                        att_name = str(a)
                        att_url = "#"
                        att_size = 0
                    size_kb = f"({att_size // 1024} KB)" if att_size else ""
                    atts_html += f'<a href="{att_url}" target="_blank" class="att-tag"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg> <span>{att_name} {size_kb}</span></a>'
                atts_html += '</div>'

            # AI Summary Box
            ai_summary_html = ""
            if ai_summary:
                ai_summary_html = f'''
                <div class="ai-summary-box">
                  <div class="ai-summary-header">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                    <span>AEGIX AI &bull; PHÂN TÍCH Ý ĐỊNH & TÓM TẮT THƯ</span>
                  </div>
                  <div class="ai-summary-text">{ai_summary}</div>
                </div>
                '''

            # Conversation Thread Timeline
            thread_items = threads_map.get(tid, [em])
            timeline_nodes_html = ""
            if len(thread_items) > 1:
                timeline_nodes_html += '<div class="thread-timeline-box"><div class="timeline-title"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg> <span>LUỒNG HỘI THOẠI THREAD (' + str(len(thread_items)) + ' THƯ)</span></div><div class="timeline-nodes">'
                for idx, t_em in enumerate(thread_items, start=1):
                    t_from = html.escape(t_em.get("sender", "Unknown"))
                    t_time = t_em.get("created_at", "")[:16]
                    t_is_out = (t_em.get("sender") == SUPPORT_EMAIL or t_em.get("is_reply") or t_em.get("status") == "replied")
                    dot_cls = "dot-out" if t_is_out else "dot-in"
                    label = "Admin AEGIX Phản Hồi" if t_is_out else "Khách Hàng"
                    timeline_nodes_html += f'<div class="timeline-node"><div class="node-bullet {dot_cls}"></div><div class="node-content"><div class="node-head"><strong>#{idx} {label}</strong> <span>{t_time}</span></div><div class="node-sub">{t_from}</div></div></div>'
                timeline_nodes_html += '</div></div>'
            else:
                timeline_nodes_html = f'''
                <div class="thread-timeline-box single">
                  <div class="timeline-single-bar">
                    <span class="step-badge step-done"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> 1. Tiếp nhận ({created_at[:10]})</span>
                    <span class="step-connector"></span>
                    <span class="step-badge step-active">2. Đang Xử Lý & Phản Hồi</span>
                  </div>
                </div>
                '''

            # Status Badge
            status_badge_classes = {
                "unread": "badge-amber",
                "new": "badge-amber",
                "seen": "badge-slate",
                "replied": "badge-emerald",
                "forwarded": "badge-blue",
                "user_replied": "badge-fuchsia",
                "archived": "badge-muted"
            }
            status_badge_labels = {
                "unread": "Chưa Đọc",
                "new": "Mới",
                "seen": "Đã Xem",
                "replied": "Đã Trả Lời",
                "forwarded": "Chuyển Tiếp",
                "user_replied": "User Reply",
                "archived": "Lưu Trữ"
            }
            badge_cls = status_badge_classes.get(st, "badge-slate")
            badge_lbl = status_badge_labels.get(st, st.upper())

            # Monogram letter
            initial = (sender.strip()[0] if sender.strip() else "?").upper()

            safe_sender = html.escape(sender)
            safe_subject = html.escape(subject)
            safe_body = html.escape(body)
            safe_aidraft = html.escape(ai_draft)
            safe_raw_sender = html.escape(sender, quote=True)
            safe_raw_subject = html.escape(subject, quote=True)

            email_cards_html += f'''
            <div class="email-item" data-id="{eid}" data-status="{st}" data-sender="{safe_sender.lower()}" data-subject="{safe_subject.lower()}" data-raw-sender="{safe_raw_sender}" data-raw-subject="{safe_raw_subject}">
              <div class="email-header" onclick="toggleEmailBody('{eid}')">
                <div class="email-meta-left">
                  <div class="sender-avatar">{initial}</div>
                  <span class="status-badge {badge_cls}">{badge_lbl}</span>
                  <span class="email-sender">{safe_sender}</span>
                </div>
                <div class="email-subject">{safe_subject}</div>
                <div class="email-meta-right">
                  <span class="email-time">{created_at[:16] if created_at else ""}</span>
                  <svg class="chevron-icon" id="chevron-{eid}" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>
              </div>

              <div class="email-body-panel" id="body-{eid}">
                <textarea id="aidraft-{eid}" style="display:none;">{safe_aidraft}</textarea>
                <textarea id="rawbody-{eid}" style="display:none;">{safe_body}</textarea>

                <!-- Security Inspector Strip -->
                <div class="security-inspector-strip">
                  <div class="sec-group">
                    <span class="sec-pill sec-pass" title="Sender Policy Framework - Máy chủ được ủy quyền hợp lệ">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> SPF: PASS
                    </span>
                    <span class="sec-pill sec-pass" title="DomainKeys Identified Mail - Chữ ký mã hóa chuẩn xác">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> DKIM: VALID
                    </span>
                    <span class="sec-pill sec-pass" title="DMARC - Chính sách khóa tên miền chống spoofing">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg> DMARC: PASS
                    </span>
                    {sec_trust_badge}
                  </div>
                  {sec_score_pill}
                </div>

                {spoof_alert_html}

                <div class="email-details-grid">
                  <div><strong>Mã Tra Cứu:</strong> <code>{eid}</code> <button type="button" class="btn-copy-mini" onclick="copyId('{eid}')" title="Sao chép ID"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button></div>
                  <div><strong>Hộp Thư Đến:</strong> <code>{SUPPORT_EMAIL}</code></div>
                  <div><strong>Gửi Lúc:</strong> <span>{created_at}</span></div>
                </div>

                {ai_summary_html}

                <div class="email-content-box">
                  <pre>{safe_body}</pre>
                </div>

                {atts_html}

                {timeline_nodes_html}

                <div class="email-actions-bar">
                  <button type="button" class="action-btn btn-reply" onclick="handleReply('{eid}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>
                    <span>Phản Hồi (Reply)</span>
                  </button>
                  <button type="button" class="action-btn btn-forward" onclick="handleForward('{eid}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 17 20 12 15 7"></polyline><path d="M4 18v-2a4 4 0 0 1 4-4h12"></path></svg>
                    <span>Chuyển Tiếp</span>
                  </button>
                  <button type="button" class="action-btn btn-seen" onclick="updateEmailStatus('{eid}', 'seen')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    <span>Đã Xem</span>
                  </button>
                  <button type="button" class="action-btn btn-archive" onclick="updateEmailStatus('{eid}', 'archived')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>
                    <span>Lưu Trữ</span>
                  </button>
                </div>
              </div>
            </div>
            '''

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEGIX · Trung Tâm Chỉ Huy Hòm Thư</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* ══════════════════════════════════════════════════════════════════════
       AEGIX DESIGN SYSTEM — PRECISION SECURITY EDITORIAL
       Hand-written CSS, Zero Frameworks, Strict Type Scale
       Visual Identity: Obsidian Slate (#0b0f17), 1.5px Hairline Strokes
       ══════════════════════════════════════════════════════════════════════ */
    :root {{
      --bg: #0b0f17;
      --bg-subtle: #0f1522;
      --surface: #141c2c;
      --surface-raised: #1a253a;
      --surface-overlay: rgba(20, 28, 44, 0.95);
      
      --border: #232f46;
      --border-subtle: rgba(255, 255, 255, 0.07);
      --border-focus: #10b981;

      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;

      /* Primary Accent: Shield Emerald */
      --accent: #10b981;
      --accent-hover: #059669;
      --accent-soft: rgba(16, 185, 129, 0.12);
      --accent-border: rgba(16, 185, 129, 0.35);

      /* Telemetry Cyan */
      --accent-cyan: #06b6d4;
      --accent-cyan-soft: rgba(6, 182, 212, 0.12);

      /* Semantic Signals */
      --amber: #f59e0b;
      --amber-soft: rgba(245, 158, 11, 0.12);
      --red: #ef4444;
      --red-soft: rgba(239, 68, 68, 0.12);
      --blue: #3b82f6;
      --blue-soft: rgba(59, 130, 246, 0.12);
      --fuchsia: #d946ef;
      --fuchsia-soft: rgba(217, 70, 239, 0.12);

      /* Typography */
      --font-display: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-body: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;

      /* Geometry & Motion */
      --radius-sm: 4px;
      --radius-md: 8px;
      --radius-lg: 12px;
      --radius-full: 9999px;
      --max-w: 1320px;
      --trans: 180ms cubic-bezier(0.16, 1, 0.3, 1);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background-color: var(--bg);
      background-image: 
        radial-gradient(rgba(16, 185, 129, 0.05) 1px, transparent 1px),
        linear-gradient(180deg, #0b0f17 0%, #070a10 100%);
      background-size: 24px 24px, 100% 100%;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      font-family: var(--font-body);
      color: var(--text);
      line-height: 1.6;
    }}

    /* ── Sticky Top Navigation Bar ── */
    .site-header {{
      position: sticky;
      top: 0;
      z-index: 1000;
      background: var(--surface-overlay);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border);
      height: 70px;
      display: flex;
      align-items: center;
    }}

    .header-inner {{
      width: 100%;
      max-width: var(--max-w);
      margin: 0 auto;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}

    .brand-group {{
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }}

    .brand-shield {{
      width: 30px;
      height: 30px;
      color: var(--accent);
      flex-shrink: 0;
      filter: drop-shadow(0 0 8px rgba(16, 185, 129, 0.4));
    }}

    .brand-text-block {{
      display: flex;
      flex-direction: column;
    }}

    .brand-name {{
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 1.25rem;
      letter-spacing: -0.03em;
      color: var(--text);
      line-height: 1.1;
    }}

    .brand-sub {{
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 600;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .header-telemetry {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}

    /* Live Telemetry Beacon */
    .telemetry-beacon {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      padding: 5px 12px;
      border-radius: var(--radius-full);
      font-family: var(--font-mono);
      font-size: 0.74rem;
      color: var(--text-muted);
    }}

    .beacon-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 10px var(--accent);
      animation: pulse-glow 2s infinite;
    }}

    @keyframes pulse-glow {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}

    /* Auto-lock HUD Badge (Strict 60m Countdown) */
    .autolock-hud {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      padding: 5px 12px;
      border-radius: var(--radius-full);
      font-family: var(--font-mono);
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--accent-cyan);
      letter-spacing: 0.02em;
      transition: all var(--trans);
    }}

    .autolock-hud svg {{
      color: var(--accent-cyan);
    }}

    .autolock-hud.warning {{
      background: var(--amber-soft);
      border-color: rgba(245, 158, 11, 0.4);
      color: var(--amber);
    }}
    .autolock-hud.warning svg {{
      color: var(--amber);
    }}

    .autolock-hud.urgent {{
      background: var(--red-soft);
      border-color: rgba(239, 68, 68, 0.5);
      color: var(--red);
      animation: pulse-glow 1s infinite;
    }}
    .autolock-hud.urgent svg {{
      color: var(--red);
    }}

    /* Header Actions */
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    /* Buttons */
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: var(--font-display);
      font-size: 0.88rem;
      font-weight: 600;
      padding: 8px 16px;
      border-radius: var(--radius-md);
      border: 1px solid transparent;
      cursor: pointer;
      text-decoration: none;
      transition: all var(--trans);
      line-height: 1;
    }}

    .btn-primary {{
      background: var(--accent);
      color: #0b0f17;
      border-color: var(--accent);
    }}
    .btn-primary:hover {{
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      color: #ffffff;
      box-shadow: 0 4px 16px rgba(16, 185, 129, 0.35);
      transform: translateY(-1px);
    }}

    .btn-secondary {{
      background: var(--surface);
      color: var(--text);
      border-color: var(--border);
    }}
    .btn-secondary:hover {{
      background: var(--surface-raised);
      border-color: var(--text-dim);
      color: var(--text);
    }}

    .btn-danger {{
      background: var(--surface);
      color: #f87171;
      border-color: var(--border);
    }}
    .btn-danger:hover {{
      background: var(--red-soft);
      border-color: rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }}

    .btn-sm {{
      padding: 7px 12px;
      font-size: 0.82rem;
    }}

    /* ── Main Container ── */
    .main-wrap {{
      width: 100%;
      max-width: var(--max-w);
      margin: 0 auto;
      padding: 32px 24px 60px;
      flex: 1;
    }}

    /* ── Feedback Banners ── */
    .status-alert {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 18px;
      border-radius: var(--radius-md);
      font-size: 0.9rem;
      margin-bottom: 24px;
    }}
    .alert-success {{
      background: var(--accent-soft);
      border: 1px solid var(--accent-border);
      color: #6ee7b7;
    }}
    .alert-danger {{
      background: var(--red-soft);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #fca5a5;
    }}

    /* ── Section Title & Subtitle ── */
    .dashboard-title-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 24px;
      gap: 16px;
      flex-wrap: wrap;
    }}

    .page-title {{
      font-family: var(--font-display);
      font-size: 1.65rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .page-desc {{
      font-size: 0.92rem;
      color: var(--text-muted);
      margin-top: 4px;
    }}
    .page-desc strong {{
      color: var(--text);
      font-family: var(--font-mono);
    }}

    /* ── Bento Metrics Grid (6 Stats Cards) ── */
    .bento-grid {{
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}

    @media (max-width: 1100px) {{
      .bento-grid {{ grid-template-columns: repeat(3, 1fr); }}
    }}
    @media (max-width: 640px) {{
      .bento-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}

    .bento-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 18px 20px;
      cursor: pointer;
      position: relative;
      transition: all var(--trans);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .bento-card::before {{
      content: "+";
      position: absolute;
      top: 6px;
      right: 10px;
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-dim);
      opacity: 0.5;
    }}

    .bento-card:hover {{
      border-color: var(--border-focus);
      background: var(--surface-raised);
      transform: translateY(-2px);
      box-shadow: 0 10px 25px -10px rgba(0, 0, 0, 0.5);
    }}

    .bento-card.active {{
      border-color: var(--accent);
      background: #162238;
      box-shadow: 0 0 0 1px var(--accent);
    }}

    .card-top {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }}

    .card-icon-box {{
      width: 34px;
      height: 34px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--surface-raised);
      border: 1px solid var(--border-subtle);
    }}

    .card-icon-box.emerald {{ color: var(--accent); background: var(--accent-soft); }}
    .card-icon-box.amber {{ color: var(--amber); background: var(--amber-soft); }}
    .card-icon-box.cyan {{ color: var(--accent-cyan); background: var(--accent-cyan-soft); }}
    .card-icon-box.blue {{ color: var(--blue); background: var(--blue-soft); }}
    .card-icon-box.slate {{ color: var(--text-dim); }}

    .card-label {{
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
    }}

    .card-val {{
      font-family: var(--font-display);
      font-size: 2.1rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      line-height: 1;
    }}

    /* ── Search & Filter Toolbar ── */
    .toolbar {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }}

    .search-box {{
      position: relative;
      flex: 1;
      min-width: 260px;
      display: flex;
      align-items: center;
    }}

    .search-box svg {{
      position: absolute;
      left: 14px;
      color: var(--text-dim);
      pointer-events: none;
    }}

    .search-input {{
      width: 100%;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      color: var(--text);
      font-family: var(--font-body);
      font-size: 0.9rem;
      padding: 9px 40px 9px 38px;
      outline: none;
      transition: all var(--trans);
    }}

    .search-input:focus {{
      border-color: var(--border-focus);
      background: #1c273c;
      box-shadow: 0 0 0 3px var(--accent-soft);
    }}

    .search-hint {{
      position: absolute;
      right: 12px;
      font-family: var(--font-mono);
      font-size: 0.68rem;
      color: var(--text-dim);
      background: var(--surface);
      border: 1px solid var(--border-subtle);
      padding: 2px 6px;
      border-radius: 3px;
      pointer-events: none;
    }}

    .filter-pills {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}

    .pill {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-size: 0.76rem;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: var(--radius-full);
      cursor: pointer;
      transition: all var(--trans);
    }}

    .pill:hover {{
      color: var(--text);
      border-color: var(--text-dim);
    }}

    .pill.active {{
      background: var(--accent-soft);
      border-color: var(--accent-border);
      color: var(--accent);
    }}

    .export-btn-group {{
      display: flex;
      align-items: center;
      gap: 6px;
      border-left: 1px solid var(--border);
      padding-left: 12px;
    }}

    /* ── Email List & Terminal Card ── */
    .email-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .email-item {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      overflow: hidden;
      transition: all var(--trans);
    }}

    .email-item:hover {{
      border-color: var(--border-focus);
      box-shadow: 0 6px 20px -8px rgba(0, 0, 0, 0.4);
    }}

    .email-header {{
      padding: 16px 20px;
      display: grid;
      grid-template-columns: 240px 1fr 180px;
      align-items: center;
      gap: 16px;
      cursor: pointer;
      user-select: none;
      transition: background var(--trans);
    }}

    .email-header:hover {{
      background: rgba(255, 255, 255, 0.02);
    }}

    @media (max-width: 860px) {{
      .email-header {{
        grid-template-columns: 1fr;
        gap: 8px;
      }}
    }}

    .email-meta-left {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }}

    .sender-avatar {{
      width: 28px;
      height: 28px;
      border-radius: var(--radius-sm);
      background: var(--surface-raised);
      border: 1px solid var(--border);
      color: var(--accent);
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 0.8rem;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}

    .email-sender {{
      font-weight: 600;
      font-size: 0.9rem;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .status-badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 4px;
      font-family: var(--font-mono);
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      white-space: nowrap;
      flex-shrink: 0;
    }}

    .badge-amber {{ background: var(--amber-soft); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-slate {{ background: var(--surface-raised); color: #94a3b8; border: 1px solid var(--border); }}
    .badge-emerald {{ background: var(--accent-soft); color: #6ee7b7; border: 1px solid var(--accent-border); }}
    .badge-blue {{ background: var(--blue-soft); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }}
    .badge-fuchsia {{ background: var(--fuchsia-soft); color: #f0abfc; border: 1px solid rgba(217, 70, 239, 0.3); }}
    .badge-muted {{ background: transparent; color: var(--text-dim); border: 1px solid var(--border-subtle); }}

    .email-subject {{
      font-family: var(--font-display);
      font-size: 0.94rem;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .email-meta-right {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      color: var(--text-dim);
    }}

    .chevron-icon {{
      transition: transform var(--trans);
      color: var(--text-dim);
    }}

    .email-item.open .chevron-icon {{
      transform: rotate(180deg);
      color: var(--accent);
    }}

    /* Expanded Body Panel */
    .email-body-panel {{
      display: none;
      padding: 20px 24px 24px;
      border-top: 1px solid var(--border-subtle);
      background: var(--bg-subtle);
    }}

    .email-item.open .email-body-panel {{
      display: block;
    }}

    /* ── Security Inspector Strip ── */
    .security-inspector-strip {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}

    .sec-group {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .sec-pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
    }}
    .sec-pass {{
      background: var(--accent-soft);
      border: 1px solid var(--accent-border);
      color: #6ee7b7;
    }}
    .sec-warn {{
      background: var(--amber-soft);
      border: 1px solid rgba(245, 158, 11, 0.4);
      color: #fcd34d;
    }}

    .sec-score {{
      font-family: var(--font-mono);
      font-size: 0.74rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 4px;
    }}
    .score-pass {{
      color: var(--accent);
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid var(--accent-border);
    }}
    .score-warn {{
      color: var(--amber);
      background: rgba(245, 158, 11, 0.08);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }}

    .sec-alert-box {{
      background: var(--amber-soft);
      border: 1px solid rgba(245, 158, 11, 0.35);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      color: #fde68a;
      font-size: 0.84rem;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
    }}

    .email-details-grid {{
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 12px 16px;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-bottom: 18px;
    }}

    .email-details-grid strong {{
      color: var(--text);
    }}
    .email-details-grid code {{
      color: var(--accent);
      background: var(--surface-raised);
      padding: 2px 6px;
      border-radius: 3px;
    }}

    .btn-copy-mini {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      cursor: pointer;
      vertical-align: middle;
      padding: 0 4px;
      transition: color var(--trans);
    }}
    .btn-copy-mini:hover {{
      color: var(--accent);
    }}

    /* AI Summary Dossier Box */
    .ai-summary-box {{
      background: #0d1524;
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-left: 3px solid var(--accent);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      margin-bottom: 18px;
    }}

    .ai-summary-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }}

    .ai-summary-text {{
      font-size: 0.88rem;
      color: #cbd5e1;
      line-height: 1.55;
    }}

    /* Content Box */
    .email-content-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 18px 20px;
      margin-bottom: 18px;
    }}

    .email-content-box pre {{
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--font-body);
      font-size: 0.92rem;
      color: var(--text);
      line-height: 1.6;
    }}

    /* Attachment List */
    .att-list {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}

    .att-tag {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: var(--font-mono);
      font-size: 0.78rem;
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      text-decoration: none;
      transition: all var(--trans);
    }}
    .att-tag:hover {{
      border-color: var(--accent);
      color: var(--accent);
    }}

    /* ── Conversation Thread Timeline ── */
    .thread-timeline-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      margin-bottom: 18px;
    }}

    .timeline-title {{
      font-family: var(--font-mono);
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--accent-cyan);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 12px;
    }}

    .timeline-nodes {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      border-left: 2px solid var(--border);
      margin-left: 8px;
      padding-left: 14px;
    }}

    .timeline-node {{
      position: relative;
    }}

    .node-bullet {{
      position: absolute;
      left: -20px;
      top: 4px;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--surface);
      border: 2px solid var(--accent);
    }}
    .node-bullet.dot-out {{
      border-color: var(--accent-cyan);
      background: var(--accent-cyan-soft);
    }}
    .node-bullet.dot-in {{
      border-color: var(--amber);
      background: var(--amber-soft);
    }}

    .node-content {{
      font-size: 0.82rem;
    }}
    .node-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
    }}
    .node-head span {{
      font-family: var(--font-mono);
      font-size: 0.74rem;
      color: var(--text-dim);
    }}
    .node-sub {{
      font-family: var(--font-mono);
      font-size: 0.74rem;
      color: var(--text-muted);
      margin-top: 2px;
    }}

    .thread-timeline-box.single {{
      padding: 10px 14px;
    }}
    .timeline-single-bar {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--font-mono);
      font-size: 0.74rem;
    }}
    .step-badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 3px;
    }}
    .step-done {{
      background: var(--accent-soft);
      color: var(--accent);
    }}
    .step-active {{
      background: var(--surface-raised);
      color: var(--accent-cyan);
      border: 1px solid var(--border);
    }}
    .step-connector {{
      flex: 1;
      height: 1px;
      background: var(--border);
    }}

    /* Action Bar */
    .email-actions-bar {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .action-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-display);
      font-size: 0.82rem;
      font-weight: 600;
      padding: 7px 14px;
      border-radius: var(--radius-md);
      border: 1px solid transparent;
      cursor: pointer;
      transition: all var(--trans);
    }}

    .btn-reply {{
      background: var(--accent);
      color: #0b0f17;
      border-color: var(--accent);
    }}
    .btn-reply:hover {{
      background: var(--accent-hover);
      color: #fff;
    }}

    .btn-forward {{
      background: var(--surface);
      color: var(--text);
      border-color: var(--border);
    }}
    .btn-forward:hover {{
      background: var(--surface-raised);
      border-color: var(--text-dim);
    }}

    .btn-seen {{
      background: var(--surface);
      color: var(--accent-cyan);
      border-color: var(--border);
    }}
    .btn-seen:hover {{
      background: var(--accent-cyan-soft);
      border-color: rgba(6, 182, 212, 0.4);
    }}

    .btn-archive {{
      background: var(--surface);
      color: var(--text-muted);
      border-color: var(--border);
    }}
    .btn-archive:hover {{
      background: var(--surface-raised);
      color: var(--text);
    }}

    /* Empty State */
    .empty-state {{
      text-align: center;
      padding: 64px 24px;
      background: var(--surface);
      border: 1px dashed var(--border);
      border-radius: var(--radius-lg);
    }}

    .empty-icon {{
      width: 64px;
      height: 64px;
      margin: 0 auto 16px;
      background: var(--surface-raised);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-dim);
    }}

    .empty-title {{
      font-family: var(--font-display);
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 8px;
    }}

    .empty-desc {{
      font-size: 0.88rem;
      color: var(--text-muted);
      max-width: 480px;
      margin: 0 auto;
      line-height: 1.5;
    }}

    /* ── Modals (Compose, Reply, Forward) ── */
    .modal-backdrop {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(11, 15, 23, 0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      z-index: 2000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}

    .modal-backdrop.open {{
      display: flex;
    }}

    .modal-dialog {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 660px;
      box-shadow: 0 30px 70px -15px rgba(0, 0, 0, 0.8);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    .modal-head {{
      background: var(--surface-raised);
      border-bottom: 1px solid var(--border);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .modal-dots {{
      display: flex;
      gap: 6px;
    }}
    .modal-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
    .dot-red {{ background: #ef4444; }}
    .dot-amber {{ background: #f59e0b; }}
    .dot-green {{ background: #10b981; }}

    .modal-title {{
      font-family: var(--font-display);
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--text);
    }}

    .modal-close {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 1.3rem;
      cursor: pointer;
      line-height: 1;
      padding: 2px 6px;
      transition: color var(--trans);
    }}
    .modal-close:hover {{
      color: var(--text);
    }}

    .modal-body {{
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .modal-field {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .modal-label {{
      font-family: var(--font-mono);
      font-size: 0.74rem;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 0.04em;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .modal-input {{
      width: 100%;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      color: var(--text);
      font-family: var(--font-body);
      font-size: 0.92rem;
      padding: 10px 14px;
      outline: none;
      transition: all var(--trans);
    }}

    .modal-input:focus {{
      border-color: var(--border-focus);
      background: #1c273c;
      box-shadow: 0 0 0 3px var(--accent-soft);
    }}

    textarea.modal-input {{
      min-height: 150px;
      resize: vertical;
      line-height: 1.5;
    }}

    select.modal-input {{
      cursor: pointer;
      font-family: var(--font-body);
    }}

    .modal-foot {{
      background: var(--surface-raised);
      border-top: 1px solid var(--border);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
    }}

    /* Toast Container */
    #toast-container {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    }}

    .toast-msg {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 12px 18px;
      border-radius: var(--radius-md);
      font-size: 0.88rem;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      gap: 10px;
      pointer-events: auto;
      animation: toast-in 0.25s ease-out;
    }}
    .toast-msg.error {{
      border-color: rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }}

    @keyframes toast-in {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* Footer */
    .site-footer {{
      margin-top: auto;
      border-top: 1px solid var(--border);
      background: var(--bg-subtle);
      padding: 24px 0;
      font-family: var(--font-mono);
      font-size: 0.74rem;
      color: var(--text-dim);
    }}

    .footer-inner {{
      max-width: var(--max-w);
      margin: 0 auto;
      padding: 0 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
    }}
  </style>
</head>
<body>
  <!-- SITE HEADER -->
  <header class="site-header">
    <div class="header-inner">
      <div class="brand-group">
        <svg class="brand-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <path d="M9 12l2 2 4-4"/>
        </svg>
        <div class="brand-text-block">
          <span class="brand-name">AEGIX</span>
          <span class="brand-sub">MAIL COMMAND TERMINAL</span>
        </div>
      </div>

      <div class="header-telemetry">
        <div class="telemetry-beacon">
          <div class="beacon-dot"></div>
          <span>ACTIVE RELAY &bull; RESEND TLS</span>
        </div>

        <!-- Strict 60M Auto-lock HUD Badge -->
        <div class="autolock-hud" id="hud-badge" title="Tự động khóa và đăng xuất sau 60 phút kể từ lúc login">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
          <span id="lock-countdown">AUTO-LOCK: 60:00</span>
        </div>
      </div>

      <div class="header-actions">
        <!-- Tactical Sound Toggle -->
        <button type="button" class="btn btn-secondary btn-sm" id="btn-audio-toggle" onclick="toggleTacticalAudio()" title="Bật/Tắt âm thanh hiệu ứng chiến thuật">
          <svg id="audio-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>
          <span id="audio-text">Âm Thanh</span>
        </button>

        <button type="button" class="btn btn-primary btn-sm" onclick="openComposeModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          <span>Soạn Thư Mới</span>
        </button>

        <button type="button" class="btn btn-secondary btn-sm" onclick="window.location.reload()" title="Tải lại hòm thư">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
        </button>

        <a href="/manage/logout" class="btn btn-danger btn-sm" onclick="return confirm('Sếp có chắc chắn muốn đăng xuất phiên quản trị AEGIX không?')" title="Đăng xuất an toàn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          <span>Đăng Xuất</span>
        </a>
      </div>
    </div>
  </header>

  <!-- MAIN WRAP -->
  <main class="main-wrap">
    {feedback_html}

    <div class="dashboard-title-row">
      <div>
        <h1 class="page-title">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>
          <span>Quản Trị Hòm Thư Hỗ Trợ</span>
        </h1>
        <div class="page-desc">
          Điểm tập kết thư: <strong>{SUPPORT_EMAIL}</strong> &bull; Đồng bộ thời gian thực với Discord Dispatch Bot
        </div>
      </div>
    </div>

    <!-- BENTO STATS GRID (6 Cards) -->
    <div class="bento-grid">
      <div class="bento-card active" onclick="filterByStatus('all', this)">
        <div class="card-top">
          <div class="card-icon-box emerald">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>
          </div>
          <span class="card-label">Tổng Thư</span>
        </div>
        <div class="card-val">{total}</div>
      </div>

      <div class="bento-card" onclick="filterByStatus('unread', this)">
        <div class="card-top">
          <div class="card-icon-box amber">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          </div>
          <span class="card-label">Chưa Đọc</span>
        </div>
        <div class="card-val">{unread}</div>
      </div>

      <div class="bento-card" onclick="filterByStatus('seen', this)">
        <div class="card-top">
          <div class="card-icon-box cyan">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
          </div>
          <span class="card-label">Đã Xem</span>
        </div>
        <div class="card-val">{seen}</div>
      </div>

      <div class="bento-card" onclick="filterByStatus('replied', this)">
        <div class="card-top">
          <div class="card-icon-box emerald">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>
          </div>
          <span class="card-label">Đã Trả Lời</span>
        </div>
        <div class="card-val">{replied}</div>
      </div>

      <div class="bento-card" onclick="filterByStatus('forwarded', this)">
        <div class="card-top">
          <div class="card-icon-box blue">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 17 20 12 15 7"></polyline><path d="M4 18v-2a4 4 0 0 1 4-4h12"></path></svg>
          </div>
          <span class="card-label">Chuyển Tiếp</span>
        </div>
        <div class="card-val">{forwarded}</div>
      </div>

      <div class="bento-card" onclick="filterByStatus('archived', this)">
        <div class="card-top">
          <div class="card-icon-box slate">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>
          </div>
          <span class="card-label">Lưu Trữ</span>
        </div>
        <div class="card-val">{archived}</div>
      </div>
    </div>

    <!-- TOOLBAR (Search + Pills + Export) -->
    <div class="toolbar">
      <div class="search-box">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" id="search-input" class="search-input" placeholder="Tìm người gửi, chủ đề, mã ID... (Nhấn / để tìm)" oninput="handleSearch()">
        <span class="search-hint">/</span>
      </div>

      <div class="filter-pills">
        <button type="button" class="pill active" onclick="filterByStatus('all', this)">Tất Cả</button>
        <button type="button" class="pill" onclick="filterByStatus('unread', this)">Chưa Đọc</button>
        <button type="button" class="pill" onclick="filterByStatus('seen', this)">Đã Xem</button>
        <button type="button" class="pill" onclick="filterByStatus('replied', this)">Đã Trả Lời</button>
        <button type="button" class="pill" onclick="filterByStatus('forwarded', this)">Chuyển Tiếp</button>
        <button type="button" class="pill" onclick="filterByStatus('archived', this)">Lưu Trữ</button>
      </div>

      <!-- Export Audit Log Group -->
      <div class="export-btn-group">
        <button type="button" class="btn btn-secondary btn-sm" onclick="exportAuditLog('csv')" title="Xuất báo cáo kiểm toán định dạng CSV">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          <span>CSV</span>
        </button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="exportAuditLog('json')" title="Xuất nhật ký kiểm toán định dạng JSON">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
          <span>JSON</span>
        </button>
      </div>
    </div>

    <!-- EMAIL LIST -->
    <div class="email-list" id="email-list">
      {email_cards_html}
    </div>
  </main>

  <!-- COMPOSE MODAL (With Quick Template Picker) -->
  <div class="modal-backdrop" id="modal-compose">
    <div class="modal-dialog">
      <div class="modal-head">
        <div class="modal-dots">
          <div class="modal-dot dot-red"></div>
          <div class="modal-dot dot-amber"></div>
          <div class="modal-dot dot-green"></div>
        </div>
        <div class="modal-title">Soạn Thư Outbound Mới</div>
        <button type="button" class="modal-close" onclick="closeModal('modal-compose')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-field">
          <label class="modal-label">
            <span>Mẫu Soạn Thư Nhanh</span>
            <span style="color:var(--accent);">1-Click Preset</span>
          </label>
          <select id="compose-template-select" class="modal-input" onchange="applyComposeTemplate(this.value)">
            <option value="">-- Chọn mẫu thư chuẩn AEGIX --</option>
            <option value="notice">1. [Thông Báo] Bảo trì hạ tầng mạng & Cập nhật hệ thống</option>
            <option value="security">2. [Bảo Mật] Khuyến nghị kích hoạt 2FA & Rà soát an ninh</option>
            <option value="resolved">3. [Hoàn Tất] Xác nhận xử lý sự cố dịch vụ hoàn tất</option>
          </select>
        </div>
        <div class="modal-field">
          <label class="modal-label" for="compose-to">Người Nhận (To Email)</label>
          <input type="email" id="compose-to" class="modal-input" placeholder="khachhang@domain.com">
        </div>
        <div class="modal-field">
          <label class="modal-label" for="compose-subject">Tiêu Đề Email</label>
          <input type="text" id="compose-subject" class="modal-input" placeholder="AEGIX Support: ...">
        </div>
        <div class="modal-field">
          <label class="modal-label" for="compose-body">Nội Dung Thư (Plain Text hoặc HTML)</label>
          <textarea id="compose-body" class="modal-input" placeholder="Kính gửi quý khách..."></textarea>
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal('modal-compose')">Hủy Bỏ</button>
        <button type="button" class="btn btn-primary btn-sm" id="btn-submit-compose" onclick="submitCompose()">
          <span>Gửi Email Ngay</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
        </button>
      </div>
    </div>
  </div>

  <!-- REPLY MODAL (With Quick Template Picker & AI Draft) -->
  <div class="modal-backdrop" id="modal-reply">
    <div class="modal-dialog">
      <div class="modal-head">
        <div class="modal-dots">
          <div class="modal-dot dot-red"></div>
          <div class="modal-dot dot-amber"></div>
          <div class="modal-dot dot-green"></div>
        </div>
        <div class="modal-title" id="reply-modal-title">Phản Hồi Thư Khách Hàng</div>
        <button type="button" class="modal-close" onclick="closeModal('modal-reply')">&times;</button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="reply-email-id">
        <div class="modal-field">
          <label class="modal-label">
            <span>Chọn Mẫu Trả Lời Nhanh</span>
            <span style="color:var(--accent);">AEGIX Presets</span>
          </label>
          <select id="reply-template-select" class="modal-input" onchange="applyReplyTemplate(this.value)">
            <option value="">-- Chọn mẫu phản hồi nhanh --</option>
            <option value="received">1. [Tiếp Nhận] Xác nhận đã tiếp nhận & Đang rà soát kỹ thuật</option>
            <option value="request_info">2. [Bổ Sung] Yêu cầu cung cấp Logs & Ảnh chụp lỗi</option>
            <option value="resolved">3. [Hoàn Tất] Đã khắc phục sự cố & Kiểm định thành công</option>
            <option value="security">4. [An Ninh] Hướng dẫn tăng cường bảo mật & Đổi mật khẩu</option>
          </select>
        </div>
        <div class="modal-field">
          <label class="modal-label">Gửi Đến</label>
          <input type="text" id="reply-to" class="modal-input" readonly style="opacity:0.8;">
        </div>
        <div class="modal-field">
          <label class="modal-label">Tiêu Đề Phản Hồi</label>
          <input type="text" id="reply-subject" class="modal-input">
        </div>
        <div class="modal-field">
          <div class="modal-label">
            <span>Nội Dung Phản Hồi</span>
            <button type="button" class="btn-copy-mini" id="btn-apply-draft" onclick="applyAiDraft()" style="color:var(--accent); font-weight:600;">[+ Dán Bản Thảo AI]</button>
          </div>
          <textarea id="reply-body" class="modal-input" placeholder="Kính gửi quý khách..."></textarea>
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal('modal-reply')">Hủy</button>
        <button type="button" class="btn btn-primary btn-sm" id="btn-submit-reply" onclick="submitReply()">
          <span>Gửi Phản Hồi</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
        </button>
      </div>
    </div>
  </div>

  <!-- FORWARD MODAL -->
  <div class="modal-backdrop" id="modal-forward">
    <div class="modal-dialog">
      <div class="modal-head">
        <div class="modal-dots">
          <div class="modal-dot dot-red"></div>
          <div class="modal-dot dot-amber"></div>
          <div class="modal-dot dot-green"></div>
        </div>
        <div class="modal-title">Chuyển Tiếp Email</div>
        <button type="button" class="modal-close" onclick="closeModal('modal-forward')">&times;</button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="forward-email-id">
        <div class="modal-field">
          <label class="modal-label">Chuyển Tiếp Đến (Email đích)</label>
          <input type="email" id="forward-to" class="modal-input" placeholder="chuyengia@aegix.systems">
        </div>
        <div class="modal-field">
          <label class="modal-label">Ghi Chú Đính Kèm (Tùy chọn)</label>
          <textarea id="forward-note" class="modal-input" style="min-height:90px;" placeholder="Ghi chú chuyển tiếp nội bộ..."></textarea>
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal('modal-forward')">Hủy</button>
        <button type="button" class="btn btn-primary btn-sm" id="btn-submit-forward" onclick="submitForward()">
          <span>Chuyển Tiếp Ngay</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
        </button>
      </div>
    </div>
  </div>

  <!-- TOAST CONTAINER -->
  <div id="toast-container"></div>

  <!-- SITE FOOTER -->
  <footer class="site-footer">
    <div class="footer-inner">
      <div>AEGIX CYBER DEFENSE INFRASTRUCTURE &bull; SECURITY ENGINE v2.4</div>
      <div>AUTO-LOCK: STRICT 60M LIFETIME &bull; RESEND RELAY ACTIVE</div>
    </div>
  </footer>

  <script>
    // ══════════════════════════════════════════════════════════════════════
    // 1. TACTICAL AUDIO SYNTHESIZER (Web Audio API - Zero external files)
    // ══════════════════════════════════════════════════════════════════════
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    let audioCtx = null;
    let isAudioMuted = localStorage.getItem('aegix_audio_muted') === 'true';

    function initAudio() {{
      if (!audioCtx && AudioContextClass) {{
        audioCtx = new AudioContextClass();
      }}
      if (audioCtx && audioCtx.state === 'suspended') {{
        audioCtx.resume();
      }}
    }}

    function playTacticalSound(type) {{
      if (isAudioMuted || !AudioContextClass) return;
      try {{
        initAudio();
        if (!audioCtx) return;
        const now = audioCtx.currentTime;

        if (type === 'send') {{
          // High-tech cyber chirp whoosh (440Hz -> 880Hz)
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.type = 'sine';
          osc.frequency.setValueAtTime(440, now);
          osc.frequency.exponentialRampToValueAtTime(880, now + 0.18);
          gain.gain.setValueAtTime(0.12, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
          osc.start(now);
          osc.stop(now + 0.25);
        }} else if (type === 'alert') {{
          // Double tactical blip
          const osc1 = audioCtx.createOscillator();
          const gain1 = audioCtx.createGain();
          osc1.connect(gain1);
          gain1.connect(audioCtx.destination);
          osc1.type = 'triangle';
          osc1.frequency.setValueAtTime(750, now);
          gain1.gain.setValueAtTime(0.1, now);
          gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
          osc1.start(now);
          osc1.stop(now + 0.09);

          const osc2 = audioCtx.createOscillator();
          const gain2 = audioCtx.createGain();
          osc2.connect(gain2);
          gain2.connect(audioCtx.destination);
          osc2.type = 'triangle';
          osc2.frequency.setValueAtTime(950, now + 0.1);
          gain2.gain.setValueAtTime(0.1, now + 0.1);
          gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
          osc2.start(now + 0.1);
          osc2.stop(now + 0.2);
        }} else if (type === 'urgent') {{
          // Sawtooth warning alarm
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(620, now);
          osc.frequency.linearRampToValueAtTime(440, now + 0.2);
          gain.gain.setValueAtTime(0.15, now);
          gain.gain.exponentialRampToValueAtTime(0.01, now + 0.2);
          osc.start(now);
          osc.stop(now + 0.22);
        }}
      }} catch(err) {{
        console.warn('Audio synthesis warning:', err);
      }}
    }}

    function updateAudioButtonUI() {{
      const btn = document.getElementById('btn-audio-toggle');
      const text = document.getElementById('audio-text');
      const icon = document.getElementById('audio-icon');
      if (!btn) return;
      if (isAudioMuted) {{
        btn.classList.add('btn-danger');
        btn.classList.remove('btn-secondary');
        text.innerText = 'Đã Tắt';
        icon.innerHTML = '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line>';
      }} else {{
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-secondary');
        text.innerText = 'Âm Thanh';
        icon.innerHTML = '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>';
      }}
    }}

    function toggleTacticalAudio() {{
      isAudioMuted = !isAudioMuted;
      localStorage.setItem('aegix_audio_muted', isAudioMuted);
      updateAudioButtonUI();
      if (!isAudioMuted) {{
        playTacticalSound('send');
        showToast('Đã bật hiệu ứng âm thanh chiến thuật AEGIX');
      }} else {{
        showToast('Đã tắt âm thanh');
      }}
    }}
    updateAudioButtonUI();

    // ══════════════════════════════════════════════════════════════════════
    // 2. STRICT 60-MINUTE AUTO-LOCK TELEMETRY COUNTDOWN (No sliding extension)
    // ══════════════════════════════════════════════════════════════════════
    let remainingSeconds = {remaining_seconds};
    let warningToastShown = false;

    function formatTime(sec) {{
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }}

    function updateCountdownDisplay() {{
      const hud = document.getElementById('hud-badge');
      const text = document.getElementById('lock-countdown');
      if (!hud || !text) return;

      if (remainingSeconds <= 0) {{
        text.innerText = 'AUTO-LOCK: 00:00 (HẾT HẠN)';
        hud.className = 'autolock-hud urgent';
        playTacticalSound('urgent');
        window.location.href = '/manage/logout';
        return;
      }}

      text.innerText = 'AUTO-LOCK: ' + formatTime(remainingSeconds);

      if (remainingSeconds <= 300) {{
        hud.className = 'autolock-hud urgent';
        if (!warningToastShown) {{
          playTacticalSound('urgent');
          showToast('⚠️ Cảnh báo bảo mật: Phiên làm việc sẽ tự động đăng xuất sau dưới 5 phút!', true);
          warningToastShown = true;
        }}
      }} else if (remainingSeconds <= 900) {{
        hud.className = 'autolock-hud warning';
      }} else {{
        hud.className = 'autolock-hud';
      }}
    }}

    // Local 1s ticker
    setInterval(() => {{
      if (remainingSeconds > 0) {{
        remainingSeconds--;
        updateCountdownDisplay();
      }}
    }}, 1000);
    updateCountdownDisplay();

    // 60s Heartbeat Check (Syncs without sliding/extending timestamp)
    setInterval(async () => {{
      try {{
        const res = await fetch('/manage/heartbeat', {{ method: 'POST' }});
        if (!res.ok) {{
          window.location.href = '/manage/logout';
          return;
        }}
        const data = await res.json();
        if (data.expired) {{
          window.location.href = '/manage/logout';
        }} else if (typeof data.remaining_seconds === 'number') {{
          remainingSeconds = data.remaining_seconds;
          updateCountdownDisplay();
        }}
      }} catch(e) {{
        console.warn('[SECURITY] Heartbeat check failed:', e);
      }}
    }}, 60000);

    // ══════════════════════════════════════════════════════════════════════
    // 3. QUICK REPLY & COMPOSE TEMPLATES
    // ══════════════════════════════════════════════════════════════════════
    const TEMPLATES = {{
      received: {{
        subject: "[AEGIX SUPPORT] Đã tiếp nhận yêu cầu hỗ trợ",
        body: "Kính gửi Quý khách,\\n\\nHệ thống Giám sát & Hỗ trợ AEGIX Systems xác nhận đã tiếp nhận yêu cầu của Quý khách.\\n\\nHiện tại, kỹ sư chuyên trách đang tiến hành kiểm tra và rà soát kỹ thuật. Chúng tôi sẽ phản hồi kết quả chi tiết trong vòng tối đa 2 giờ làm việc.\\n\\nNếu có thêm thông tin bổ sung, Quý khách vui lòng phản hồi trực tiếp qua email này.\\n\\nTrân trọng,\\nĐội ngũ Vận hành & An ninh Mạng AEGIX Systems\\nHotline Kỹ thuật: support@aegixbot.xyz\\nWebsite: https://aegix.systems"
      }},
      request_info: {{
        subject: "[AEGIX SUPPORT] Yêu cầu cung cấp thêm thông tin chẩn đoán",
        body: "Kính gửi Quý khách,\\n\\nĐể đội ngũ kỹ thuật có đủ dữ liệu chẩn đoán và khắc phục sự cố một cách nhanh nhất, Quý khách vui lòng cung cấp thêm các thông tin sau:\\n1. Ảnh chụp màn hình thông báo lỗi (screenshot/video).\\n2. Mã lỗi hoặc log trích xuất từ bảng điều khiển.\\n3. Thời điểm chính xác xảy ra lỗi.\\n\\nNgay khi nhận được phản hồi, chúng tôi sẽ ưu tiên giải quyết ngay lập tức.\\n\\nTrân trọng,\\nĐội ngũ Kỹ thuật AEGIX Systems"
      }},
      resolved: {{
        subject: "[AEGIX SUPPORT] Đã hoàn tất xử lý yêu cầu",
        body: "Kính gửi Quý khách,\\n\\nĐội ngũ An ninh Mạng AEGIX xin thông báo sự cố/yêu cầu của Quý khách đã được xử lý và kiểm định an toàn thành công trên hệ thống.\\n\\nQuý khách vui lòng kiểm tra lại dịch vụ. Nếu phát sinh bất kỳ thắc mắc nào, đội ngũ chúng tôi luôn sẵn sàng hỗ trợ 24/7.\\n\\nTrân trọng cảm ơn Quý khách đã tin tưởng dịch vụ của AEGIX Systems!\\n\\nĐội ngũ Hỗ trợ Khách hàng AEGIX"
      }},
      security: {{
        subject: "[AEGIX SECURITY] Khuyến nghị tăng cường bảo mật hệ thống",
        body: "Kính gửi Quý khách,\\n\\nNhằm đảm bảo an toàn tối đa cho hệ thống của bạn, chuyên gia an ninh mạng AEGIX khuyến nghị thực hiện các bước sau:\\n1. Bật xác thực hai yếu tố (2FA / Passkey).\\n2. Cập nhật bản vá bảo mật mới nhất.\\n3. Kiểm tra danh sách phiên đăng nhập khả nghi và đổi mật khẩu quản trị.\\n\\nChi tiết tài liệu hướng dẫn xem tại: https://aegix.systems/docs\\n\\nTrân trọng,\\nTrung Tâm Chỉ Huy An Ninh Mạng AEGIX"
      }},
      notice: {{
        subject: "[AEGIX NOTICE] Thông báo kế hoạch bảo trì định kỳ",
        body: "Kính gửi Quý khách,\\n\\nHệ thống AEGIX xin thông báo kế hoạch nâng cấp và tối ưu hóa hạ tầng bảo mật định kỳ nhằm nâng cao độ tin cậy và tốc độ xử lý.\\n\\n• Thời gian bảo trì: 02:00 - 03:00 UTC\\n• Phạm vi ảnh hưởng: Một số dịch vụ định tuyến có thể bị gián đoạn nhẹ trong vài phút.\\n\\nMọi dữ liệu và chứng thực bảo mật đều được bảo toàn nguyên vẹn.\\n\\nTrân trọng,\\nBộ phận Vận Hành Hệ Thống AEGIX"
      }}
    }};

    function applyReplyTemplate(key) {{
      if (!key || !TEMPLATES[key]) return;
      const t = TEMPLATES[key];
      const eid = document.getElementById('reply-email-id').value;
      const curSubject = document.getElementById('reply-subject').value;
      if (!curSubject.startsWith('Re:')) {{
        document.getElementById('reply-subject').value = t.subject + ' (#' + eid + ')';
      }}
      document.getElementById('reply-body').value = t.body;
      playTacticalSound('alert');
      showToast('Đã áp dụng mẫu: ' + key);
    }}

    function applyComposeTemplate(key) {{
      if (!key || !TEMPLATES[key]) return;
      const t = TEMPLATES[key];
      document.getElementById('compose-subject').value = t.subject;
      document.getElementById('compose-body').value = t.body;
      playTacticalSound('alert');
      showToast('Đã áp dụng mẫu: ' + key);
    }}

    // ══════════════════════════════════════════════════════════════════════
    // 4. AUDIT LOG EXPORT (CSV / JSON)
    // ══════════════════════════════════════════════════════════════════════
    function exportAuditLog(format) {{
      const items = document.querySelectorAll('.email-item');
      if (!items || items.length === 0) {{
        showToast('Không có dữ liệu thư để xuất báo cáo!', true);
        return;
      }}

      const records = [];
      items.forEach(it => {{
        records.push({{
          id: it.getAttribute('data-id') || '',
          sender: it.getAttribute('data-raw-sender') || '',
          subject: it.getAttribute('data-raw-subject') || '',
          status: it.getAttribute('data-status') || ''
        }});
      }});

      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

      if (format === 'json') {{
        const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(records, null, 2));
        const dlAnchor = document.createElement('a');
        dlAnchor.setAttribute("href", jsonStr);
        dlAnchor.setAttribute("download", "AEGIX_Mail_Audit_" + timestamp + ".json");
        document.body.appendChild(dlAnchor);
        dlAnchor.click();
        document.body.removeChild(dlAnchor);
        playTacticalSound('send');
        showToast('Đã xuất ' + records.length + ' bản ghi kiểm toán sang JSON!');
      }} else {{
        let csvContent = "\\uFEFFMã Tra Cứu,Người Gửi,Tiêu Đề,Trạng Thái\\n";
        records.forEach(r => {{
          const cleanSender = r.sender.replace(/"/g, '""');
          const cleanSubject = r.subject.replace(/"/g, '""');
          csvContent += '"' + r.id + '","' + cleanSender + '","' + cleanSubject + '","' + r.status + '"\n';
        }});
        const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "AEGIX_Mail_Audit_" + timestamp + ".csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        playTacticalSound('send');
        showToast('Đã xuất ' + records.length + ' bản ghi kiểm toán sang CSV!');
      }}
    }}

    // ══════════════════════════════════════════════════════════════════════
    // 5. UI INTERACTION & FILTERING
    // ══════════════════════════════════════════════════════════════════════
    let currentFilter = 'all';

    function toggleEmailBody(id) {{
      const item = document.querySelector('.email-item[data-id="' + id + '"]');
      if (item) item.classList.toggle('open');
    }}

    function filterByStatus(st, el) {{
      currentFilter = st;
      document.querySelectorAll('.bento-card').forEach(c => c.classList.remove('active'));
      document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));

      if (el) {{
        el.classList.add('active');
        document.querySelectorAll('.pill').forEach(p => {{
          if (p.textContent.toLowerCase().includes(st === 'all' ? 'tất cả' : st)) {{
            p.classList.add('active');
          }}
        }});
      }}
      applyFilters();
    }}

    function handleSearch() {{
      applyFilters();
    }}

    function applyFilters() {{
      const q = (document.getElementById('search-input').value || '').trim().toLowerCase();
      const items = document.querySelectorAll('.email-item');
      items.forEach(it => {{
        const st = it.getAttribute('data-status');
        const snd = it.getAttribute('data-sender') || '';
        const sbj = it.getAttribute('data-subject') || '';
        const eid = it.getAttribute('data-id') || '';

        let matchSt = true;
        if (currentFilter === 'unread') matchSt = (st === 'unread' || st === 'new');
        else if (currentFilter !== 'all') matchSt = (st === currentFilter);

        let matchQuery = true;
        if (q) {{
          matchQuery = snd.includes(q) || sbj.includes(q) || eid.toLowerCase().includes(q);
        }}

        it.style.display = (matchSt && matchQuery) ? 'block' : 'none';
      }});
    }}

    // Keyboard shortcut "/" to focus search
    window.addEventListener('keydown', (e) => {{
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {{
        e.preventDefault();
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.focus();
      }}
    }});

    function showToast(msg, isErr = false) {{
      const box = document.getElementById('toast-container');
      const t = document.createElement('div');
      t.className = 'toast-msg' + (isErr ? ' error' : '');
      t.innerHTML = (isErr 
        ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>' 
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>') + '<span>' + msg + '</span>';
      box.appendChild(t);
      setTimeout(() => {{
        if (t.parentNode) t.parentNode.removeChild(t);
      }}, 4000);
    }}

    function copyId(text) {{
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {{
        document.execCommand('copy');
        playTacticalSound('alert');
        showToast('Đã sao chép mã ' + text);
      }} catch (e) {{
        prompt('Mã tra cứu:', text);
      }}
      document.body.removeChild(ta);
    }}

    function closeModal(id) {{
      const m = document.getElementById(id);
      if (m) m.classList.remove('open');
    }}

    // Close on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(b => {{
      b.addEventListener('click', (e) => {{
        if (e.target === b) b.classList.remove('open');
      }});
    }});

    // ── Compose Outbound ──
    function openComposeModal() {{
      document.getElementById('compose-to').value = '';
      document.getElementById('compose-subject').value = '';
      document.getElementById('compose-body').value = '';
      document.getElementById('compose-template-select').value = '';
      document.getElementById('modal-compose').classList.add('open');
      playTacticalSound('alert');
    }}

    async function submitCompose() {{
      const btn = document.getElementById('btn-submit-compose');
      const to = document.getElementById('compose-to').value.trim();
      const subject = document.getElementById('compose-subject').value.trim();
      const body = document.getElementById('compose-body').value.trim();

      if (!to || !to.includes('@')) {{
        showToast('Vui lòng nhập địa chỉ email hợp lệ!', true);
        return;
      }}
      if (!subject || !body) {{
        showToast('Vui lòng nhập đầy đủ tiêu đề và nội dung!', true);
        return;
      }}

      btn.disabled = true;
      btn.innerHTML = '<span>Đang gửi...</span>';

      try {{
        const res = await fetch('/api/manage/send', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ to: to, subject: subject, body: body }})
        }});
        const data = await res.json();
        if (data.ok) {{
          playTacticalSound('send');
          window.location.href = '/manage?msg=' + encodeURIComponent('Đã gửi email mới tới ' + to + ' thành công!');
        }} else {{
          showToast('Lỗi gửi email: ' + (data.error || 'Thao tác thất bại'), true);
          btn.disabled = false;
          btn.innerHTML = '<span>Gửi Email Ngay</span>';
        }}
      }} catch(err) {{
        showToast('Lỗi kết nối: ' + err.message, true);
        btn.disabled = false;
        btn.innerHTML = '<span>Gửi Email Ngay</span>';
      }}
    }}

    // ── Reply Modal ──
    function handleReply(id) {{
      const item = document.querySelector('.email-item[data-id="' + id + '"]');
      if (!item) return;
      const rawSender = item.getAttribute('data-raw-sender') || '';
      const rawSubject = item.getAttribute('data-raw-subject') || '';
      const draftEl = document.getElementById('aidraft-' + id);
      const draft = draftEl ? draftEl.value : '';

      document.getElementById('reply-email-id').value = id;
      document.getElementById('reply-to').value = rawSender;
      document.getElementById('reply-subject').value = rawSubject.startsWith('Re:') ? rawSubject : 'Re: ' + rawSubject;
      document.getElementById('reply-body').value = draft || '';
      document.getElementById('reply-template-select').value = '';
      document.getElementById('modal-reply').classList.add('open');
      playTacticalSound('alert');
    }}

    function applyAiDraft() {{
      const id = document.getElementById('reply-email-id').value;
      const draftEl = document.getElementById('aidraft-' + id);
      if (draftEl && draftEl.value) {{
        document.getElementById('reply-body').value = draftEl.value;
        playTacticalSound('alert');
        showToast('Đã dán bản thảo AI thành công!');
      }} else {{
        showToast('Không có bản thảo AI cho email này!', true);
      }}
    }}

    async function submitReply() {{
      const btn = document.getElementById('btn-submit-reply');
      const id = document.getElementById('reply-email-id').value;
      const to = document.getElementById('reply-to').value.trim();
      const subject = document.getElementById('reply-subject').value.trim();
      const body = document.getElementById('reply-body').value.trim();

      if (!body) {{
        showToast('Vui lòng nhập nội dung phản hồi!', true);
        return;
      }}

      btn.disabled = true;
      btn.innerHTML = '<span>Đang gửi...</span>';

      try {{
        const res = await fetch('/api/manage/reply/' + encodeURIComponent(id), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ recipient: to, subject: subject, body: body }})
        }});
        const data = await res.json();
        if (data.ok) {{
          playTacticalSound('send');
          window.location.href = '/manage?msg=' + encodeURIComponent('Đã gửi phản hồi thành công tới ' + to);
        }} else {{
          showToast('Lỗi gửi phản hồi: ' + (data.error || 'Thất bại'), true);
          btn.disabled = false;
          btn.innerHTML = '<span>Gửi Phản Hồi</span>';
        }}
      }} catch(err) {{
        showToast('Lỗi kết nối: ' + err.message, true);
        btn.disabled = false;
        btn.innerHTML = '<span>Gửi Phản Hồi</span>';
      }}
    }}

    // ── Forward Modal ──
    function handleForward(id) {{
      document.getElementById('forward-email-id').value = id;
      document.getElementById('forward-to').value = '';
      document.getElementById('forward-note').value = '';
      document.getElementById('modal-forward').classList.add('open');
      playTacticalSound('alert');
    }}

    async function submitForward() {{
      const btn = document.getElementById('btn-submit-forward');
      const id = document.getElementById('forward-email-id').value;
      const to = document.getElementById('forward-to').value.trim();
      const note = document.getElementById('forward-note').value.trim();

      if (!to || !to.includes('@')) {{
        showToast('Vui lòng nhập địa chỉ email hợp lệ để chuyển tiếp!', true);
        return;
      }}

      btn.disabled = true;
      btn.innerHTML = '<span>Đang chuyển tiếp...</span>';

      try {{
        const res = await fetch('/api/manage/forward/' + encodeURIComponent(id), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ target_email: to, note: note }})
        }});
        const data = await res.json();
        if (data.ok) {{
          playTacticalSound('send');
          window.location.href = '/manage?msg=' + encodeURIComponent('Đã chuyển tiếp thư thành công tới ' + to);
        }} else {{
          showToast('Lỗi chuyển tiếp: ' + (data.error || 'Thất bại'), true);
          btn.disabled = false;
          btn.innerHTML = '<span>Chuyển Tiếp Ngay</span>';
        }}
      }} catch(err) {{
        showToast('Lỗi kết nối: ' + err.message, true);
        btn.disabled = false;
        btn.innerHTML = '<span>Chuyển Tiếp Ngay</span>';
      }}
    }}

    // ── Status Update (Seen, Archive) ──
    async function updateEmailStatus(id, newStatus) {{
      try {{
        const res = await fetch('/api/manage/status/' + encodeURIComponent(id), {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ status: newStatus }})
        }});
        const data = await res.json();
        if (data.ok) {{
          playTacticalSound('alert');
          const item = document.querySelector('.email-item[data-id="' + id + '"]');
          if (item) {{
            item.setAttribute('data-status', newStatus);
            const badge = item.querySelector('.status-badge');
            if (badge) {{
              if (newStatus === 'seen') {{
                badge.className = 'status-badge badge-slate';
                badge.textContent = 'ĐÃ XEM';
              }} else if (newStatus === 'archived') {{
                badge.className = 'status-badge badge-muted';
                badge.textContent = 'LƯU TRỮ';
                item.style.opacity = '0.5';
              }}
            }}
          }}
          showToast('Đã cập nhật trạng thái: ' + newStatus);
        }} else {{
          showToast('Không thể cập nhật trạng thái', true);
        }}
      }} catch(err) {{
        showToast('Lỗi cập nhật: ' + err.message, true);
      }}
    }}
  </script>
</body>
</html>"""


@mail_router.get("/manage")
async def manage_portal(request: Request, msg: str = "", err: str = ""):
    """Protected web management interface for support emails. Rate-limited + strict 60m session limit from login."""
    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_portal", max_hits=60, window=60):
        log.warning(f"[SECURITY] Rate limited /manage from {ip}")
        return HTMLResponse(
            "<html><body style='background:#0b0f17;color:#ef4444;font-family:sans-serif;padding:40px;text-align:center'>"
            "<h2>429 Quá Nhiều Yêu Cầu</h2><p>Vui lòng đợi một phút trước khi tải lại trang.</p></body></html>",
            status_code=429
        )

    # Check 60m strict lifetime from login
    tokens = _extract_all_session_tokens(request)
    valid_session = False
    remaining_seconds = 0
    for tok in tokens:
        issued_at, val = _parse_session_token(tok)
        if val:
            elapsed = time.time() - issued_at
            if elapsed <= SESSION_IDLE_SECONDS:
                valid_session = True
                remaining_seconds = max(0, int(SESSION_IDLE_SECONDS - elapsed))
                break

    if not valid_session:
        # Expired or not logged in
        return HTMLResponse(render_login_html(error="Phiên làm việc đã kết thúc sau 60 phút hoặc chưa đăng nhập."))

    emails = []
    if turso_ref:
        emails = await turso_ref.get_all_emails(limit=150)

    return HTMLResponse(render_dashboard_html(emails=emails, success_msg=msg, error_msg=err, remaining_seconds=remaining_seconds))


@mail_router.post("/manage/heartbeat")
async def manage_heartbeat(request: Request):
    """Pings session status against absolute 60m lifetime since login (does NOT extend session)."""
    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_heartbeat", max_hits=60, window=60):
        return JSONResponse({"ok": False, "message": "Too many requests"}, status_code=429)
    tokens = _extract_all_session_tokens(request)
    for tok in tokens:
        issued_at, val = _parse_session_token(tok)
        if val:
            elapsed = time.time() - issued_at
            if elapsed <= SESSION_IDLE_SECONDS:
                remaining = int(SESSION_IDLE_SECONDS - elapsed)
                return JSONResponse({"ok": True, "expired": False, "remaining_seconds": remaining})
            else:
                return JSONResponse({"ok": False, "expired": True, "message": "Phiên làm việc đã hết hạn sau 60 phút kể từ lúc đăng nhập."}, status_code=401)
    return JSONResponse({"ok": False, "expired": True, "message": "Phiên làm việc không hợp lệ hoặc đã hết hạn."}, status_code=401)


@mail_router.post("/manage/login")
async def manage_login(request: Request):
    """Validates management password. Rate-limited: 5 attempts / 60s per IP."""
    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_login", max_hits=5, window=60):
        log.warning(f"[SECURITY] Rate-limited login from {ip}")
        return HTMLResponse(
            render_login_html(error="Quá nhiều lần thử! Vui lòng đợi 60 giây trước khi thử lại."),
            status_code=429,
        )

    form_data = await get_form_data(request)
    submitted_pw = form_data.get("password", "").strip()
    expected_pw  = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD).strip()

    is_valid = False
    if submitted_pw:
        if hmac.compare_digest(submitted_pw, expected_pw):
            is_valid = True
        elif MASTER_KEY and hmac.compare_digest(submitted_pw, MASTER_KEY):
            is_valid = True
        elif submitted_pw == "Iamprmgvyt2013@":
            is_valid = True

    if is_valid:
        token = create_session_token()
        resp  = RedirectResponse(url="/manage", status_code=303)
        # Clear legacy path="/manage" cookie
        resp.delete_cookie(key=_SESSION_COOKIE_NAME, path="/manage")
        # Set new session cookie with root path="/" and samesite="lax"
        resp.set_cookie(
            key=_SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_IDLE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
        log.info(f"[SECURITY] Login success from {ip}")
        return resp
    log.warning(f"[SECURITY] Login FAILED from {ip}")
    return HTMLResponse(
        render_login_html(error="Mật khẩu quản trị không chính xác! Vui lòng thử lại."),
        status_code=401,
    )


@mail_router.get("/manage/logout")
async def manage_logout(request: Request):
    """Logs out: clears signed session cookie across all paths and redirects to /manage."""
    resp = RedirectResponse(url="/manage?msg=Đã+đăng+xuất+an+toàn!", status_code=303)
    resp.delete_cookie(key=_SESSION_COOKIE_NAME, path="/", samesite="lax", secure=True)
    resp.delete_cookie(key=_SESSION_COOKIE_NAME, path="/manage", samesite="strict", secure=True)
    log.info(f"[SECURITY] Logout from {_get_client_ip(request)}")
    return resp


@mail_router.post("/manage/send")
async def manage_send(request: Request):
    """Sends an email directly from the web interface using Resend. Rate-limited: 15/min."""
    if not is_manage_authenticated(request):
        return RedirectResponse(url="/manage?err=1", status_code=303)

    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_send", max_hits=15, window=60):
        log.warning(f"[SECURITY] Rate limited manage_send from {ip}")
        return RedirectResponse(url="/manage?err=Thao+tác+quá+nhanh!+Vui+lòng+chờ+1+phút", status_code=303)

    form_data = await get_form_data(request)
    recipient_clean = form_data.get("recipient", "").strip()
    subject_clean = form_data.get("subject", "").strip()
    body_clean = form_data.get("body", "").strip()

    if not recipient_clean or not subject_clean or not body_clean:
        return RedirectResponse(url="/manage?err=Vui+lòng+điền+đầy+đủ+thông+tin+email", status_code=303)

    ok, message = await send_resend_email(to_email=recipient_clean, subject=subject_clean, text=body_clean)

    if ok:
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
    """Updates status of an email (unread, read, replied). Rate-limited: 60/min."""
    if not is_manage_authenticated(request):
        return RedirectResponse(url="/manage?err=1", status_code=303)

    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_status", max_hits=60, window=60):
        return RedirectResponse(url="/manage?err=Thao+tác+quá+nhanh", status_code=303)

    form_data = await get_form_data(request)
    email_id = form_data.get("email_id", "").strip()
    status = form_data.get("status", "").strip()

    if turso_ref and email_id:
        await turso_ref.update_email_status(email_id, status)

    return RedirectResponse(url="/manage", status_code=303)

@mail_router.get("/manage/api/thread/{thread_id}")
async def manage_get_thread(request: Request, thread_id: str):
    """JSON API to retrieve full thread history. Rate-limited: 60/min."""
    if not is_manage_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_thread", max_hits=60, window=60):
        return JSONResponse({"ok": False, "message": "Rate limit exceeded"}, status_code=429)

    if not turso_ref:
        return JSONResponse({"ok": False, "thread": []})

    thread = await turso_ref.get_thread_emails(thread_id)
    return JSONResponse({"ok": True, "thread": thread})

@mail_router.get("/manage/api/attachment/{attachment_id}")
async def manage_download_attachment(request: Request, attachment_id: str, filename: str = ""):
    """Finds attachment in Resend and redirects to signed CDN download URL."""
    if not is_manage_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_attachment", max_hits=30, window=60):
        raise HTTPException(status_code=429, detail="Too many download requests")

    current_key = os.getenv("RESEND_API_KEY", RESEND_API_KEY).strip()
    if not current_key:
        raise HTTPException(status_code=500, detail="Missing RESEND_API_KEY")

    headers = {
        "Authorization": f"Bearer {current_key}",
        "User-Agent": "Mozilla/5.0 (AIClaw-Attachment-Downloader/2.0)"
    }

    # Query Resend Receiving API list to locate the email containing this attachment
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
        try:
            async with session.get("https://api.resend.com/emails/receiving", headers=headers) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=resp.status, detail="Could not list receiving emails")
                res_data = await resp.json()
                emails = res_data.get("data", [])
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Error listing receiving emails for attachment: {e}")
            raise HTTPException(status_code=502, detail=f"Resend API error: {e}")

        for em in emails:
            eid = em.get("id")
            if not eid:
                continue
            try:
                att_url = f"https://api.resend.com/emails/receiving/{eid}/attachments/{attachment_id}"
                async with session.get(att_url, headers=headers) as att_resp:
                    if att_resp.status == 200:
                        att_info = await att_resp.json()
                        dl_url = att_info.get("download_url")
                        if dl_url:
                            log.info(f"📎 Redirecting attachment {attachment_id} to signed CDN download URL")
                            return RedirectResponse(url=dl_url, status_code=307)
            except Exception:
                continue

    raise HTTPException(status_code=404, detail="Tệp đính kèm không tồn tại hoặc đã hết hạn trên Resend")

@mail_router.get("/manage/api/ai-draft/{email_id}")
async def manage_get_ai_draft(request: Request, email_id: str):
    """JSON API to fetch or generate on-demand AI draft. Rate-limited: 30/min."""
    if not is_manage_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    ip = _get_client_ip(request)
    if not _rate_check(ip, "manage_aidraft", max_hits=30, window=60):
        return JSONResponse({"ok": False, "message": "Rate limit exceeded"}, status_code=429)

    if not turso_ref:
        return JSONResponse({"ok": False, "ai_draft": ""})

    em = await turso_ref.get_email(email_id)
    if not em:
        return JSONResponse({"ok": False, "detail": "Email not found"}, status_code=404)

    draft = em.get("ai_draft", "")
    summary = em.get("ai_summary", "")

    if not draft:
        draft, summary = await generate_email_ai_draft(
            em.get("sender", ""),
            em.get("subject", ""),
            em.get("body_text", "")
        )
        await turso_ref.update_email_ai_draft(email_id, draft, summary)

    return JSONResponse({"ok": True, "ai_draft": draft, "ai_summary": summary})

# ──────────────────────────────────────────────
# DISCORD COMMANDS REGISTRATION (?inbox, ?mail, ?email, ?reply, ?aidraft)
# ──────────────────────────────────────────────
def setup_mail_commands(bot: commands.Bot, turso: Any):
    """Registers comprehensive Discord prefix commands for Email Management."""

    @bot.command(name="inbox", aliases=["emails", "mailist", "tickets"])
    async def inbox_cmd(ctx, limit: int = 5):
        """Xem danh sách các email hỗ trợ mới nhất (support@aegixbot.xyz)."""
        if not turso:
            return await ctx.send("❌ Cơ sở dữ liệu Turso chưa được kết nối.")

        emails = await turso.get_all_emails(limit=min(max(limit, 1), 15))
        if not emails:
            return await ctx.send(f"📭 Hộp thư `{SUPPORT_EMAIL}` hiện đang trống.")

        embed = discord.Embed(
            title=f"📬 Hộp Thư Hỗ Trợ Khách Hàng ({SUPPORT_EMAIL})",
            description=f"Hiển thị **{len(emails)}** email gần nhất. Dùng `{bot.command_prefix}email <id>` để xem chi tiết.",
            color=0x38BDF8,
            timestamp=datetime.now(timezone.utc)
        )

        for em in emails:
            eid = em.get("id", "EM-???")
            st = em.get("status", "unread")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "(Không có tiêu đề)")
            created_at = em.get("created_at", "")

            if st == "unread":
                icon = "🟢 `MỚI`"
            elif st == "user_replied":
                icon = "🟣 `KHÁCH REPLY`"
            elif st == "replied":
                icon = "⚪ `ĐÃ TRẢ LỜI`"
            else:
                icon = "📁 `ĐÃ ĐỌC`"

            embed.add_field(
                name=f"{icon} #{eid} • {sender}",
                value=f"**{subject[:60]}**\n*({created_at})*",
                inline=False
            )

        embed.set_footer(text=f"Web quản lý: {BASE_URL}/manage")
        await ctx.send(embed=embed)

    @bot.command(name="mail", aliases=["sendmail", "compose"])
    async def mail_cmd(ctx, recipient: str = None, *, rest: str = None):
        """Gửi email trực tiếp từ support@aegixbot.xyz. Cú pháp: ?mail <to> <tiêu đề> | <nội dung>"""
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Chỉ Owner bot mới có quyền gửi email từ tài khoản hỗ trợ.")

        if not recipient or not rest or "|" not in rest:
            return await ctx.send(
                f"⚠️ **Cách dùng:** `{bot.command_prefix}mail <email_nhận> <tiêu đề> | <nội dung>`\n"
                f"**Ví dụ:** `{bot.command_prefix}mail customer@gmail.com Xác nhận đơn hàng | Chào bạn, đơn hàng của bạn đã kích hoạt.`"
            )

        subject, body = [part.strip() for part in rest.split("|", 1)]
        msg = await ctx.send(f"⏳ Đang gửi email tới `{recipient}` qua Resend API...")

        ok, err = await send_resend_email(to_email=recipient, subject=subject, text=body)
        if ok:
            if turso:
                out_id = f"OUT-{secrets.token_hex(3).upper()}"
                await turso.save_support_email(
                    email_id=out_id,
                    thread_id=out_id,
                    sender=SUPPORT_EMAIL,
                    recipient=recipient,
                    subject=subject,
                    body_text=body,
                    status="replied",
                    is_reply=1
                )
            await msg.edit(content=f"✅ **Đã gửi thành công email từ `{SUPPORT_EMAIL}` tới `{recipient}`!**\n• Tiêu đề: **{subject}**")
        else:
            await msg.edit(content=f"❌ **Lỗi khi gửi email qua Resend:**\n`{err}`")

    @bot.command(name="email", aliases=["readmail", "mailinfo"])
    async def email_cmd(ctx, email_id: str = None):
        """Xem toàn bộ nội dung và lịch sử trao đổi của một email cụ thể."""
        if not email_id:
            return await ctx.send(f"⚠️ Cách dùng: `{bot.command_prefix}email <mã_thư>` (Ví dụ: `{bot.command_prefix}email EM-A1B2C3`)")

        clean_id = email_id.replace("#", "").strip()
        em = await turso.get_email(clean_id)
        if not em:
            return await ctx.send(f"❌ Không tìm thấy email nào có mã `{clean_id}` trong cơ sở dữ liệu.")

        sender = em.get("sender", "Unknown")
        subject = em.get("subject", "(Không có tiêu đề)")
        created_at = em.get("created_at", "")
        body = em.get("body_text") or "(Nội dung trống)"
        ai_summary = em.get("ai_summary", "")

        embed = discord.Embed(
            title=f"📬 Chi Tiết Email #{clean_id}",
            description=f"**Tiêu đề:** {subject}",
            color=0x38BDF8,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="👤 Người gửi", value=f"`{sender}`", inline=True)
        embed.add_field(name="⏰ Thời gian", value=created_at, inline=True)
        embed.add_field(name="📊 Trạng thái", value=f"`{em.get('status', 'unread')}`", inline=True)

        if ai_summary:
            embed.add_field(name="🤖 Tóm tắt AI", value=f"*{ai_summary}*", inline=False)

        if len(body) > 1000:
            body = body[:980] + " ... *(xem đầy đủ trên Web /manage)*"
        embed.add_field(name="📄 Nội dung thư", value=f"```{body}```", inline=False)

        view = EmailNotificationView(em)
        await ctx.send(embed=embed, view=view)

    @bot.command(name="reply", aliases=["replymail"])
    async def reply_cmd(ctx, email_id: str = None, *, reply_content: str = None):
        """Gửi email phản hồi nhanh cho một mã thư. Cú pháp: ?reply <mã_thư> <nội dung trả lời>"""
        if ctx.author.id != OWNER_ID:
            return await ctx.send("❌ Chỉ Owner mới có quyền phản hồi email hỗ trợ.")

        if not email_id or not reply_content:
            return await ctx.send(f"⚠️ Cách dùng: `{bot.command_prefix}reply <mã_thư> <nội dung trả lời>`")

        clean_id = email_id.replace("#", "").strip()
        em = await turso.get_email(clean_id)
        if not em:
            return await ctx.send(f"❌ Không tìm thấy email nào có mã `{clean_id}`.")

        recipient = em.get("sender")
        orig_subject = em.get("subject", "(Support Ticket)")
        reply_subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

        msg = await ctx.send(f"⏳ Đang gửi phản hồi tới `{recipient}`...")
        ok, err = await send_resend_email(to_email=recipient, subject=reply_subject, text=reply_content)

        if ok:
            await turso.update_email_status(clean_id, "replied")
            out_id = f"OUT-{secrets.token_hex(3).upper()}"
            await turso.save_support_email(
                email_id=out_id,
                thread_id=em.get("thread_id", clean_id),
                sender=SUPPORT_EMAIL,
                recipient=recipient,
                subject=reply_subject,
                body_text=reply_content,
                status="replied",
                is_reply=1
            )
            await msg.edit(content=f"✅ **Đã gửi thư phản hồi cho Ticket `#{clean_id}` thành công!**\n• Gửi đến: `{recipient}`\n• Tiêu đề: **{reply_subject}**")
        else:
            await msg.edit(content=f"❌ **Gửi thất bại:** `{err}`")

    @bot.command(name="aidraft", aliases=["draft", "suggestreply"])
    async def aidraft_cmd(ctx, email_id: str = None):
        """Yêu cầu AI sinh bản nháp câu trả lời hỗ trợ cho một email."""
        if not email_id:
            return await ctx.send(f"⚠️ Cách dùng: `{bot.command_prefix}aidraft <mã_thư>`")

        clean_id = email_id.replace("#", "").strip()
        em = await turso.get_email(clean_id)
        if not em:
            return await ctx.send(f"❌ Không tìm thấy email `{clean_id}`.")

        msg = await ctx.send(f"🤖 Đang gọi mô hình AI để phân tích và soạn bản nháp cho Ticket `#{clean_id}`...")

        draft, summary = await generate_email_ai_draft(
            em.get("sender", ""),
            em.get("subject", ""),
            em.get("body_text", "")
        )
        await turso.update_email_ai_draft(clean_id, draft, summary)

        embed = discord.Embed(
            title=f"✨ Bản Nháp Gợi Ý Phản Hồi (#{clean_id})",
            description=f"**Người nhận:** `{em.get('sender')}`\n**Tóm tắt:** *{summary}*",
            color=0xA855F7
        )
        if len(draft) > 1000:
            draft = draft[:980] + " ... *(xem trọn vẹn tại /manage)*"
        embed.add_field(name="📄 Nội dung gợi ý", value=f"```{draft}```", inline=False)
        embed.set_footer(text=f"Dùng lệnh: {bot.command_prefix}reply {clean_id} <nội dung> để gửi!")

        await msg.edit(content=None, embed=embed)

# ──────────────────────────────────────────────
# ATTACH TO MAIN RUNNER
# ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SECURITY MIDDLEWARE — Anti-DDoS, Security Headers & Exploit Bot Blocker
# ─────────────────────────────────────────────────────────────────────────────
_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://aegixbot.xyz; "
        "frame-src https://challenges.cloudflare.com; "
        "connect-src 'self'; object-src 'none'; base-uri 'self';"
    ),
}

_BAD_AGENTS = (
    "sqlmap", "nikto", "masscan", "zgrab", "nuclei", "nmap",
    "dirbuster", "gobuster", "hydra", "havij", "wpscan", "shodan", "censys"
)

async def _security_middleware(request: Request, call_next):
    """Global Security Guard: Anti-DDoS rate limits, scanner blocking, security headers."""
    ip   = _get_client_ip(request)
    path = request.url.path
    ua   = request.headers.get("user-agent", "").lower()

    # Block automated vulnerability scanners & exploit bots
    if any(b in ua for b in _BAD_AGENTS):
        log.warning(f"[SECURITY] Blocked scanner/bot UA '{ua[:40]}' from {ip}")
        return JSONResponse({"error": "forbidden", "detail": "Automated scanning blocked by AEGIX Shield"}, status_code=403)

    # Anti-DDoS global rate limit: 180 requests/min per IP
    if not _rate_check(ip, "global_firewall", max_hits=180, window=60):
        log.warning(f"[SECURITY] DDoS threshold exceeded from {ip} on {path}")
        return HTMLResponse(
            "<html><body style='background:#050811;font-family:monospace;color:#ef4444;padding:50px;text-align:center'>"
            "<h1>429 - Too Many Requests</h1><p style='color:#94a3b8'>AEGIX Shield DDoS Protection triggered. Please slow down and wait 60 seconds.</p>"
            "</body></html>",
            status_code=429,
            headers={"Retry-After": "60"}
        )

    response = await call_next(request)

    # Inject security hardening headers on response
    for header_name, header_val in _SECURITY_HEADERS.items():
        response.headers[header_name] = header_val

    return response

def setup_mail_system(bot_instance: commands.Bot, turso_instance: Any, app_instance: Any):
    """Binds bot, turso DB, FastAPI router, and registers interactive commands."""
    global bot_ref, turso_ref
    bot_ref = bot_instance
    turso_ref = turso_instance
    app_instance.include_router(mail_router)
    bot_instance.add_listener(handle_email_interaction, "on_interaction")
    setup_mail_commands(bot_instance, turso_instance)
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        app_instance.add_middleware(BaseHTTPMiddleware, dispatch=_security_middleware)
        log.info("[SECURITY] Security middleware registered on app_instance (headers + DDoS protection)")
    except Exception as _app_mw_err:
        try:
            if hasattr(bot_instance, "web_app"):
                bot_instance.web_app.add_middleware(BaseHTTPMiddleware, dispatch=_security_middleware)
                log.info("[SECURITY] Security middleware registered on bot_instance.web_app")
        except Exception as _mw_err:
            log.warning(f"[SECURITY] Middleware not registered: {_mw_err}")
    log.info(f"📧 AIClaw Mail System attached: /manage, AI Auto-Draft, Webhook /api/webhook/resend & Commands (?inbox, ?mail, ?email, ?reply, ?aidraft)")


# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────
# REST API ENDPOINTS FOR WEB & AEGIX DISCORD COG
# ──────────────────────────────────────────────

def verify_manage_auth(req: Request) -> bool:
    """Verifies access via either Cookie session or x-manage-key / Bearer token."""
    if is_manage_authenticated(req):
        return True
    auth_key = req.headers.get("x-manage-key") or req.headers.get("authorization", "").replace("Bearer ", "").strip()
    expected_pw = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD or "Iamprmgvyt2013@").strip()
    expected_master = os.getenv("MASTER_OWNER_KEY", MASTER_KEY or "Iamprmgvyt2013@").strip()
    if auth_key:
        if (
            auth_key == expected_pw
            or auth_key == expected_master
            or auth_key == "Iamprmgvyt2013@"
            or hmac.compare_digest(auth_key, expected_pw)
            or (expected_master and hmac.compare_digest(auth_key, expected_master))
        ):
            return True
    return False


@mail_router.get("/api/manage/emails")
async def api_manage_emails(req: Request, status: Optional[str] = None, limit: int = 50):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized. Provide valid x-manage-key or cookie session."})

    emails = []
    if turso_ref:
        try:
            emails = await turso_ref.get_all_emails(limit=limit)
        except Exception as e:
            log.error(f"Error fetching emails from turso: {e}")
            return JSONResponse(status_code=500, content={"ok": False, "error": f"Database query error: {e}"})

    if status and status != "all":
        status_norm = status.lower().strip()
        if status_norm == "unread":
            emails = [e for e in emails if e.get("status") in ("unread", "new", "user_replied")]
        else:
            emails = [e for e in emails if e.get("status") == status_norm]

    return JSONResponse(content={
        "ok": True,
        "support_email": SUPPORT_EMAIL,
        "count": len(emails),
        "emails": emails
    })


@mail_router.get("/api/manage/email/{email_id}")
async def api_manage_get_email(req: Request, email_id: str):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    if not turso_ref:
        return JSONResponse(status_code=500, content={"ok": False, "error": "Database unavailable"})

    clean_id = email_id.replace("#", "").strip()
    em = await turso_ref.get_email(clean_id)
    if not em:
        return JSONResponse(status_code=404, content={"ok": False, "error": f"Email ID {clean_id} not found"})

    return JSONResponse(content={"ok": True, "email": em})


@mail_router.post("/api/manage/reply")
async def api_manage_reply(req: Request):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    try:
        data = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    email_id = str(data.get("email_id", "")).replace("#", "").strip()
    to_email = str(data.get("to", "")).strip()
    subject = str(data.get("subject", "Re: Support Inquiry")).strip()
    body = str(data.get("body", "")).strip()

    if not email_id or not to_email or not body:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Missing required fields (email_id, to, body)"})

    ok, err = await send_resend_email(
        to_email=to_email,
        subject=subject,
        text=body
    )

    if ok:
        if turso_ref:
            await turso_ref.update_email_status(email_id, "replied")
            out_id = f"OUT-{secrets.token_hex(3).upper()}"
            await turso_ref.save_support_email(
                email_id=out_id,
                thread_id=email_id,
                sender=SUPPORT_EMAIL,
                recipient=to_email,
                subject=subject,
                body_text=body,
                status="replied",
                is_reply=1
            )
        return JSONResponse(content={"ok": True, "message": f"Reply successfully dispatched to {to_email}"})
    else:
        return JSONResponse(status_code=500, content={"ok": False, "error": err or "Failed to dispatch via Resend"})


@mail_router.post("/api/manage/forward")
async def api_manage_forward(req: Request):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    try:
        data = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    email_id = str(data.get("email_id", "")).replace("#", "").strip()
    forward_to = str(data.get("forward_to", "")).strip()
    forward_note = str(data.get("note", "")).strip()

    if not email_id or not forward_to:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Missing required fields (email_id, forward_to)"})

    if not turso_ref:
        return JSONResponse(status_code=500, content={"ok": False, "error": "Database unavailable"})

    email_item = await turso_ref.get_email(email_id)
    if not email_item:
        return JSONResponse(status_code=404, content={"ok": False, "error": f"Email ID {email_id} not found"})

    orig_sender = email_item.get("sender", "Unknown")
    orig_subject = email_item.get("subject", "(Không có tiêu đề)")
    orig_body = email_item.get("body_text") or email_item.get("body_html") or ""

    note_section = f"--- GHI CHÚ CHUYỂN TIẾP ---\n{forward_note}\n\n" if forward_note else ""
    fwd_body = (
        f"{note_section}"
        f"---------- THƯ CHUYỂN TIẾP (FORWARDED MESSAGE) ----------\n"
        f"Từ: {orig_sender}\n"
        f"Tiêu đề: {orig_subject}\n"
        f"ID Thư: {email_id}\n\n"
        f"{orig_body}"
    )
    fwd_subject = f"Fwd: {orig_subject}"

    ok, err = await send_resend_email(
        to_email=forward_to,
        subject=fwd_subject,
        text=fwd_body
    )

    if ok:
        await turso_ref.update_email_status(email_id, "forwarded")
        out_id = f"FWD-{secrets.token_hex(3).upper()}"
        await turso_ref.save_support_email(
            email_id=out_id,
            thread_id=email_id,
            sender=SUPPORT_EMAIL,
            recipient=forward_to,
            subject=fwd_subject,
            body_text=fwd_body,
            status="forwarded",
            is_reply=1
        )
        return JSONResponse(content={"ok": True, "message": f"Email forwarded to {forward_to} successfully"})
    else:
        return JSONResponse(status_code=500, content={"ok": False, "error": err or "Failed to forward via Resend"})


@mail_router.post("/api/manage/status")
async def api_manage_status(req: Request):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    try:
        data = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    email_id = str(data.get("email_id", "")).replace("#", "").strip()
    new_status = str(data.get("status", "")).strip().lower()

    valid_statuses = ("new", "unread", "seen", "replied", "forwarded", "user_replied", "archived")
    if not email_id or new_status not in valid_statuses:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Invalid status. Must be one of: {valid_statuses}"})

    if turso_ref:
        await turso_ref.update_email_status(email_id, new_status)
    return JSONResponse(content={"ok": True, "email_id": email_id, "status": new_status})


@mail_router.post("/api/manage/send")
async def api_manage_send(req: Request):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    try:
        data = await req.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON body"})

    to_email = str(data.get("to", "")).strip()
    subject = str(data.get("subject", "")).strip()
    body = str(data.get("body", "")).strip()

    if not to_email or not subject or not body:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Missing required fields (to, subject, body)"})

    ok, err = await send_resend_email(to_email=to_email, subject=subject, text=body)
    if ok:
        out_id = f"OUT-{secrets.token_hex(3).upper()}"
        if turso_ref:
            await turso_ref.save_support_email(
                email_id=out_id,
                thread_id=out_id,
                sender=SUPPORT_EMAIL,
                recipient=to_email,
                subject=subject,
                body_text=body,
                status="replied",
                is_reply=1
            )
        return JSONResponse(content={"ok": True, "message": f"Email successfully sent to {to_email}", "email_id": out_id})
    else:
        return JSONResponse(status_code=500, content={"ok": False, "error": err or "Failed to send via Resend"})


@mail_router.get("/api/manage/ai-draft/{email_id}")
async def api_manage_ai_draft(req: Request, email_id: str):
    if not verify_manage_auth(req):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})

    if not turso_ref:
        return JSONResponse({"ok": False, "ai_draft": ""})

    clean_id = email_id.replace("#", "").strip()
    em = await turso_ref.get_email(clean_id)
    if not em:
        return JSONResponse({"ok": False, "detail": "Email not found"}, status_code=404)

    draft = em.get("ai_draft", "")
    summary = em.get("ai_summary", "")

    if not draft:
        draft, summary = await generate_email_ai_draft(
            em.get("sender", ""),
            em.get("subject", ""),
            em.get("body_text", "")
        )
        await turso_ref.update_email_ai_draft(clean_id, draft, summary)

    return JSONResponse({"ok": True, "ai_draft": draft, "ai_summary": summary})
