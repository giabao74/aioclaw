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
MASTER_KEY = os.getenv("MASTER_OWNER_KEY", os.getenv("AIO_RESET_TOKEN", "Iamprmgvyt2013@")).strip()
MANAGE_PASSWORD = os.getenv("MANAGE_PASSWORD", MASTER_KEY or "Iamprmgvyt2013@").strip()
OWNER_ID = int(os.getenv("NOTIFY_USER_ID", os.getenv("OWNER_ID", "1262304052361035857")))
REMINDER_CHANNEL_ID = int(os.getenv("REMINDER_CHANNEL_ID", "1494907926815445023"))
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "whsec_LGjyqnw9YrD7zho856EnGw3tPgOK7zHI").strip()

AIO_GATEWAY_URL = os.getenv("AIO_GATEWAY_URL", "https://aegix-claw.prmgvyt.xyz").rstrip("/")
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
        "html": formatted_html
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
# WEB AUTHENTICATION HELPERS
# ──────────────────────────────────────────────
def get_auth_token() -> str:
    secret = os.getenv("MANAGE_PASSWORD", MANAGE_PASSWORD).strip()
    return hashlib.sha256(f"aiclaw_mail_portal_{secret}".encode()).hexdigest()

def is_manage_authenticated(request: Request) -> bool:
    cookie_token = request.cookies.get("aiclaw_manage_session")
    if not cookie_token:
        return False
    expected = get_auth_token()
    return hmac.compare_digest(cookie_token, expected)

# ──────────────────────────────────────────────
# DISCORD UI (BUTTONS & MODAL)
# ──────────────────────────────────────────────
class EmailReplyModal(discord.ui.Modal):
    def __init__(self, email_id: str, sender: str, original_subject: str, default_body: str = "", parent_msg: Optional[discord.Message] = None):
        super().__init__(title=f"Phản Hồi #{email_id[:12]}")
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
            label=f"Nội dung (Tới {sender[:25]})",
            style=discord.TextStyle.paragraph,
            placeholder="Nhập nội dung câu trả lời hoặc chỉnh sửa bản nháp AI...",
            default=default_body[:2000] if default_body else "",
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
            if turso_ref:
                await turso_ref.update_email_status(self.email_id, "replied")
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
        email_id = email_item.get("id", "UNKNOWN")

        # 1. Direct Web Portal Link
        web_url = f"{BASE_URL}/manage"
        self.add_item(discord.ui.Button(
            label="🌐 Mở Web Quản Lý",
            style=discord.ButtonStyle.link,
            url=web_url
        ))

        # 2. Reply manual modal
        self.add_item(discord.ui.Button(
            label="✉️ Trả lời",
            style=discord.ButtonStyle.primary,
            custom_id=f"reply_email:{email_id}",
            emoji="✉️"
        ))

        # 3. AI Draft button (Pre-fills reply with AI draft)
        self.add_item(discord.ui.Button(
            label="✨ Soạn bằng AI",
            style=discord.ButtonStyle.success,
            custom_id=f"ai_draft_email:{email_id}",
            emoji="✨"
        ))

        # 4. Mark resolved
        self.add_item(discord.ui.Button(
            label="✅ Đã xử lý",
            style=discord.ButtonStyle.secondary,
            custom_id=f"resolve_email:{email_id}",
            emoji="✅"
        ))

async def handle_email_interaction(interaction: discord.Interaction):
    """Global interaction handler ensuring buttons work 24/7 across bot restarts."""
    if interaction.type != discord.InteractionType.component:
        return False

    cid = interaction.data.get("custom_id", "")
    if not cid:
        return False

    # Extract email ID
    email_id = cid.split(":", 1)[1] if ":" in cid else "UNKNOWN"
    sender = "customer"
    subject = "(Support Ticket)"
    body_text = ""
    ai_draft = ""

    # Parse fallback from embed if needed
    if interaction.message and interaction.message.embeds:
        emb = interaction.message.embeds[0]
        if email_id == "UNKNOWN" and "#" in emb.title:
            try:
                email_id = emb.title.split("#", 1)[1].split("]")[0].strip()
            except Exception:
                pass
        for f in emb.fields:
            if "Người gửi" in f.name:
                sender = f.value.replace("`", "").strip()
            if "Mã thư" in f.name and email_id == "UNKNOWN":
                email_id = f.value.replace("`", "").strip()
            if "Tiêu đề" in f.name:
                subject = f.value.replace("**", "").strip()

    # Retrieve from DB for complete data
    if turso_ref and email_id != "UNKNOWN":
        item = await turso_ref.get_email(email_id)
        if item:
            sender = item.get("sender", sender)
            subject = item.get("subject", subject)
            body_text = item.get("body_text", "")
            ai_draft = item.get("ai_draft", "")

    # 1. Handle Quick Reply (Empty)
    if cid.startswith("reply_email:") or cid == "btn_email_reply":
        modal = EmailReplyModal(
            email_id=email_id,
            sender=sender,
            original_subject=subject,
            default_body="",
            parent_msg=interaction.message
        )
        await interaction.response.send_modal(modal)
        return True

    # 2. Handle AI Draft Reply (Pre-filled with AI draft)
    elif cid.startswith("ai_draft_email:"):
        if not ai_draft:
            # Generate on the fly if not ready
            ai_draft, _ = await generate_email_ai_draft(sender, subject, body_text)
            if turso_ref:
                await turso_ref.update_email_ai_draft(email_id, ai_draft)

        modal = EmailReplyModal(
            email_id=email_id,
            sender=sender,
            original_subject=subject,
            default_body=ai_draft,
            parent_msg=interaction.message
        )
        await interaction.response.send_modal(modal)
        return True

    # 3. Handle Mark Resolved
    elif cid.startswith("resolve_email:") or cid == "btn_email_done":
        if turso_ref and email_id != "UNKNOWN":
            await turso_ref.update_email_status(email_id, "read")

        try:
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                embed.color = 0x64748B  # Slate
                embed.title = f"📁 [Đã xử lý #{email_id}] " + embed.title.split("]", 1)[-1].strip()
                embed.set_footer(text=f"Đánh dấu đã xử lý bởi {interaction.user.name} lúc {format_vn_time()}")
                await interaction.response.edit_message(embed=embed)
                return True
        except Exception as e:
            log.warning(f"Could not update embed on resolve: {e}")

    return False

# ──────────────────────────────────────────────
# DISCORD DISPATCHER & THREAD CREATION
# ──────────────────────────────────────────────
async def dispatch_email_to_discord(email_item: dict):
    """Sends notification embed to Discord channel and spawns dedicated ticket thread."""
    if not bot_ref:
        log.warning("Bot instance not ready to dispatch email to Discord")
        return

    email_id = email_item.get("id", "EM-???")
    sender = email_item.get("sender", "Unknown")
    recipient = email_item.get("recipient", SUPPORT_EMAIL)
    subject = email_item.get("subject", "(Không có tiêu đề)")
    body_text = email_item.get("body_text", "")
    created_at = email_item.get("created_at", format_vn_time())
    is_reply = email_item.get("is_reply", 0)
    ai_summary = email_item.get("ai_summary", "")
    attachments_raw = email_item.get("attachments", "[]")

    try:
        att_list = json.loads(attachments_raw) if isinstance(attachments_raw, str) else (attachments_raw or [])
    except Exception:
        att_list = []

    channel = bot_ref.get_channel(REMINDER_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot_ref.fetch_channel(REMINDER_CHANNEL_ID)
        except Exception as e:
            log.warning(f"Cannot find notification channel {REMINDER_CHANNEL_ID}: {e}")
            return

    # Color coding
    if is_reply:
        color = 0xA855F7  # Purple: customer follow-up
        title_prefix = f"🟣 [Khách đã Reply #{email_id}]"
    else:
        color = 0x38BDF8  # Cyan: brand new ticket
        title_prefix = f"📬 [Email Mới #{email_id}]"

    embed = discord.Embed(
        title=f"{title_prefix} {subject[:200]}",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="👤 Người gửi", value=f"`{sender}`", inline=True)
    embed.add_field(name="🎯 Hộp thư nhận", value=f"`{recipient}`", inline=True)
    embed.add_field(name="🆔 Mã thư", value=f"`#{email_id}`", inline=True)

    if ai_summary:
        embed.add_field(name="🤖 Tóm tắt AI", value=f"*{ai_summary}*", inline=False)

    clean_preview = body_text.strip() if body_text else "(Nội dung email trống)"
    if len(clean_preview) > 800:
        clean_preview = clean_preview[:790] + " ... *(xem đầy đủ trên Web)*"
    embed.add_field(name="📄 Nội dung tóm tắt", value=f"```{clean_preview}```", inline=False)

    if att_list:
        att_text = "\n".join(f"• 📎 `{a.get('filename', 'file')}` ({a.get('content_type', 'unknown')})" for a in att_list[:5])
        embed.add_field(name="📎 Tệp đính kèm", value=att_text, inline=False)

    embed.set_footer(
        text=f"AIClaw Email Gate • {created_at} • support@aegixbot.xyz",
        icon_url="https://aegixbot.xyz/static/aegix.png"
    )

    view = EmailNotificationView(email_item)

    try:
        sent_msg = await channel.send(
            content=f"🔔 <@{OWNER_ID}> **Email hỗ trợ khách hàng mới cần xử lý!**",
            embed=embed,
            view=view
        )

        # Automatically spawn a private ticket thread in Discord for team discussion
        try:
            sender_tag = sender.split("@")[0][:18]
            thread_title = f"Ticket #{email_id} - {sender_tag}"[:95]
            ticket_thread = await sent_msg.create_thread(
                name=thread_title,
                auto_archive_duration=1440
            )
            await ticket_thread.send(
                f"💬 **Luồng xử lý nội bộ Ticket `#{email_id}`**\n"
                f"• Người gửi: `{sender}`\n"
                f"• Tiêu đề: **{subject}**\n"
                f"• Lệnh hỗ trợ nhanh: `{bot_ref.command_prefix or '?'}reply {email_id} <nội dung>` hoặc `{bot_ref.command_prefix or '?'}aidraft {email_id}`"
            )
        except Exception as th_err:
            log.debug(f"Could not create Discord thread for email {email_id}: {th_err}")

    except Exception as e:
        log.exception(f"Failed to dispatch email embed to Discord: {e}")

# ──────────────────────────────────────────────
# RESEND INBOUND WEBHOOK HANDLER
# ──────────────────────────────────────────────
@mail_router.post("/api/webhook/resend")
@mail_router.post("/api/email-webhook")
async def handle_resend_webhook(request: Request):
    """
    Receives incoming emails from Resend Inbound Webhook.
    Extracts sender, subject, body, attachments, generates AI draft,
    stores in DB, and dispatches interactive alert & thread to Discord.
    """
    try:
        body_bytes = await request.body()
        if not body_bytes:
            return JSONResponse({"status": "error", "message": "Empty body"}, status_code=400)

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
            status = "user_replied"
            is_reply = 1
            if existing_thread:
                thread_id = existing_thread.get("thread_id", existing_thread.get("id", email_id))
                await turso_ref.update_email_status(existing_thread.get("id"), "user_replied")
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
def render_login_html(error: str = "") -> str:
    err_box = f'<div class="login-err"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><span>{error}</span></div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEGIX Email Gateway · Authentication</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #050811;
      --card-bg: rgba(13, 19, 36, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --border-focus: #6366F1;
      --primary: #6366F1;
      --primary-hover: #4F46E5;
      --cyan: #06B6D4;
      --text: #F8FAFC;
      --text-muted: #94A3B8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg);
      background-image: 
        radial-gradient(1000px circle at 50% -20%, rgba(99, 102, 241, 0.2), transparent 60%),
        radial-gradient(800px circle at 85% 90%, rgba(6, 182, 212, 0.12), transparent 50%),
        radial-gradient(700px circle at 15% 85%, rgba(139, 92, 246, 0.15), transparent 50%);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      overflow: hidden;
      position: relative;
    }}
    body::before {{
      content: '';
      position: absolute;
      inset: 0;
      background-image: linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
    }}
    .login-container {{
      width: 100%;
      max-width: 440px;
      position: relative;
      z-index: 10;
    }}
    .login-card {{
      background: var(--card-bg);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 44px 38px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7),
                  0 0 40px rgba(99, 102, 241, 0.15);
      position: relative;
      overflow: hidden;
    }}
    .login-card::after {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--primary), var(--cyan), transparent);
    }}
    .logo-badge {{
      width: 68px;
      height: 68px;
      margin: 0 auto 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }}
    .logo-badge img {{
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 2px solid rgba(99, 102, 241, 0.5);
      box-shadow: 0 0 25px rgba(99, 102, 241, 0.4);
      background: #080A10;
    }}
    .brand-title {{
      font-family: 'Outfit', sans-serif;
      font-size: 24px;
      font-weight: 800;
      text-align: center;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
      background: linear-gradient(135deg, #FFFFFF, #CBD5E1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .brand-sub {{
      font-size: 13px;
      color: var(--text-muted);
      text-align: center;
      margin-bottom: 30px;
      line-height: 1.5;
    }}
    .brand-sub strong {{
      color: var(--cyan);
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
    }}
    .login-err {{
      background: rgba(244, 63, 94, 0.12);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #FECDD3;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 13px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 10px;
      line-height: 1.4;
    }}
    .form-group {{
      margin-bottom: 24px;
      text-align: left;
    }}
    .form-group label {{
      display: block;
      font-size: 12px;
      font-weight: 700;
      color: #CBD5E1;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .input-wrapper input {{
      width: 100%;
      background: rgba(7, 10, 20, 0.85);
      border: 1px solid var(--border);
      padding: 14px 18px;
      border-radius: 12px;
      color: #FFFFFF;
      font-size: 15px;
      outline: none;
      transition: all 0.25s ease;
      font-family: inherit;
    }}
    .input-wrapper input:focus {{
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25),
                  0 0 20px rgba(99, 102, 241, 0.15);
      background: rgba(7, 10, 20, 1);
    }}
    .btn-login {{
      width: 100%;
      background: linear-gradient(135deg, #6366F1, #4F46E5);
      color: #FFFFFF;
      border: none;
      padding: 14px;
      border-radius: 12px;
      font-size: 15px;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      letter-spacing: 0.01em;
      cursor: pointer;
      transition: all 0.25s ease;
      box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .btn-login:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 25px rgba(99, 102, 241, 0.6);
      filter: brightness(1.08);
    }}
    .footer-badges {{
      margin-top: 28px;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 16px;
      font-size: 11px;
      color: var(--text-muted);
    }}
    .badge-pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: rgba(255, 255, 255, 0.04);
      padding: 5px 10px;
      border-radius: 20px;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }}
  </style>
</head>
<body>
  <div class="login-container">
    <div class="login-card">
      <div class="logo-badge">
        <img src="https://aegixbot.xyz/static/aegix.png" alt="AEGIX">
      </div>
      <h1 class="brand-title">AEGIX Support Studio</h1>
      <p class="brand-sub">Secure Mail Gateway &amp; Dispatcher<br><strong>{SUPPORT_EMAIL}</strong></p>

      {err_box}

      <form method="POST" action="/manage/login">
        <div class="form-group">
          <label for="password">Master Security Key</label>
          <div class="input-wrapper">
            <input type="password" id="password" name="password" placeholder="Enter master access password..." required autofocus>
          </div>
        </div>
        <button type="submit" class="btn-login">
          <span>Authenticate &amp; Open Inbox</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </form>

      <div class="footer-badges">
        <div class="badge-pill">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span>256-Bit SSL</span>
        </div>
        <div class="badge-pill">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          <span>Zero-Log Session</span>
        </div>
      </div>
    </div>
  </div>
</body>
</html>"""


def render_dashboard_html(emails: List[Dict[str, Any]], success_msg: str = "", error_msg: str = "") -> str:
    has_resend_key = bool(os.getenv("RESEND_API_KEY", RESEND_API_KEY).strip())

    total = len(emails)
    unread = sum(1 for e in emails if e.get("status") == "unread")
    replied = sum(1 for e in emails if e.get("status") == "replied")
    user_replied = sum(1 for e in emails if e.get("status") == "user_replied")

    key_badge = '<span class="status-chip chip-green"><span class="dot"></span>Resend API Live</span>' if has_resend_key else '<span class="status-chip chip-amber"><span class="dot"></span>API Key Missing</span>'
    ai_badge = '<span class="status-chip chip-purple"><span class="dot"></span>AI Neural Draft Active</span>'

    warning_banner = ""
    if not has_resend_key:
        warning_banner = f"""
        <div class="glass-banner banner-warn">
          <div class="banner-icon">⚠️</div>
          <div>
            <strong>Missing RESEND_API_KEY Configuration:</strong> Incoming emails and AI drafting work normally. To dispatch outbound replies to customers, please add <code>RESEND_API_KEY</code> to your environment from <a href="https://resend.com/api-keys" target="_blank" rel="noopener">resend.com/api-keys</a>.
          </div>
        </div>
        """

    feedback_html = ""
    if success_msg:
        feedback_html += f'<div class="glass-banner banner-success"><div class="banner-icon">✅</div><div>{success_msg}</div></div>'
    if error_msg:
        feedback_html += f'<div class="glass-banner banner-danger"><div class="banner-icon">❌</div><div>{error_msg}</div></div>'

    # Build Email Cards HTML
    email_cards_html = ""
    if not emails:
        email_cards_html = f'''
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <h3>Your Inbox is Clean</h3>
          <p>No support inquiries have been received yet for <strong>{SUPPORT_EMAIL}</strong>.<br>Send a test email to this address to see it appear here in real time!</p>
        </div>
        '''
    else:
        for em in emails:
            eid = em.get("id", "EM-???")
            tid = em.get("thread_id", eid)
            st = em.get("status", "unread")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "(No Subject)")
            created_at = em.get("created_at", "")
            body = em.get("body_text") or em.get("body_html") or "(Empty email body)"
            ai_draft = em.get("ai_draft", "")
            ai_summary = em.get("ai_summary", "")

            # Attachments
            att_raw = em.get("attachments", "[]")
            try:
                att_list = json.loads(att_raw) if isinstance(att_raw, str) else (att_raw or [])
            except Exception:
                att_list = []

            has_att = len(att_list) > 0

            # Badge Styling
            if st == "unread":
                badge = '<span class="status-badge badge-unread"><span class="pulse-dot"></span>NEW TICKET</span>'
            elif st == "user_replied":
                badge = '<span class="status-badge badge-replied"><span class="pulse-dot-purple"></span>CUSTOMER FOLLOW-UP</span>'
            elif st == "replied":
                badge = '<span class="status-badge badge-resolved">RESOLVED</span>'
            else:
                badge = '<span class="status-badge badge-read">READ</span>'

            # Clean display for body
            safe_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_ai_draft = ai_draft.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\\n", "<br>")

            # Attachment Chips
            att_html = ""
            if att_list:
                pills = "".join(f'<span class="att-chip"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>{a.get("filename", "attachment")}</span>' for a in att_list)
                att_html = f'<div class="att-wrapper">{pills}</div>'

            # AI Summary banner
            ai_summary_html = ""
            if ai_summary:
                ai_summary_html = f'''
                <div class="ai-summary-card">
                  <div class="ai-summary-label">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C084FC" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                    <span>AI Context Analysis</span>
                  </div>
                  <div class="ai-summary-text">{ai_summary}</div>
                </div>
                '''

            # AI Pre-Draft Box
            ai_draft_block = ""
            if ai_draft:
                ai_draft_block = f'''
                <div class="ai-draft-card">
                  <div class="ai-draft-header">
                    <div class="ai-draft-title">
                      <span class="sparkle-icon">✨</span>
                      <span>AI Pre-Drafted Response (Ready to Dispatch)</span>
                    </div>
                    <button type="button" class="btn-insert-ai" onclick="useAiDraft('{eid}')">
                      <span>Insert into Composer</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </button>
                  </div>
                  <div class="ai-draft-preview" id="aidraft-text-{eid}">{safe_ai_draft}</div>
                </div>
                '''

            sender_initial = sender[0].upper() if sender else "U"

            email_cards_html += f"""
            <div class="ticket-card" id="item-{eid}" data-status="{st}" data-sender="{sender.lower()}" data-subject="{subject.lower()}" data-id="{eid.lower()}" data-has-att="{'1' if has_att else '0'}">
              <div class="ticket-top" onclick="toggleMail('{eid}')">
                <div class="sender-avatar">{sender_initial}</div>
                <div class="ticket-info">
                  <div class="ticket-meta-row">
                    <span class="sender-email">{sender}</span>
                    <span class="ticket-id">#{eid}</span>
                    {badge}
                    {'<span class="att-badge" title="Has attachments"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></span>' if has_att else ''}
                  </div>
                  <div class="ticket-subject">{subject}</div>
                </div>
                <div class="ticket-date-col">
                  <span class="ticket-date">{created_at}</span>
                  <div class="expand-icon" id="expand-icon-{eid}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                  </div>
                </div>
              </div>

              {ai_summary_html}

              <div class="ticket-expansion" id="body-{eid}">
                <div class="ticket-body-scroll">
                  <div class="body-label">Email Message Content:</div>
                  <div class="body-content">{safe_body}</div>
                </div>

                {att_html}
                {ai_draft_block}

                <div class="ticket-action-bar">
                  <button type="button" class="btn-action-primary" onclick="prefillReply('{sender}', '{subject}', '{eid}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10h10a5 5 0 0 1 5 5v2"/><path d="M7 6l-4 4 4 4"/></svg>
                    <span>Quick Reply</span>
                  </button>

                  <button type="button" class="btn-action-thread" onclick="viewThread('{tid}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    <span>Conversation Thread</span>
                  </button>

                  <form method="POST" action="/manage/status" style="display:inline;margin-left:auto;">
                    <input type="hidden" name="email_id" value="{eid}">
                    <input type="hidden" name="status" value="{'read' if st != 'read' else 'unread'}">
                    <button type="submit" class="btn-action-secondary">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                      <span>{'Mark as Read' if st != 'read' else 'Mark as Unread'}</span>
                    </button>
                  </form>
                </div>
              </div>
            </div>
            """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AEGIX Support Studio · Command Console</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #050811;
      --card-bg: rgba(13, 19, 36, 0.75);
      --card-hover: rgba(18, 26, 48, 0.85);
      --border: rgba(255, 255, 255, 0.08);
      --border-hover: rgba(99, 102, 241, 0.4);
      --primary: #6366F1;
      --primary-hover: #4F46E5;
      --cyan: #06B6D4;
      --purple: #A855F7;
      --green: #10B981;
      --amber: #F59E0B;
      --rose: #F43F5E;
      --text: #F8FAFC;
      --text-muted: #94A3B8;
      --text-sub: #64748B;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg);
      background-image: 
        radial-gradient(1200px circle at 15% -10%, rgba(99, 102, 241, 0.15), transparent 60%),
        radial-gradient(900px circle at 85% 10%, rgba(6, 182, 212, 0.12), transparent 50%),
        radial-gradient(800px circle at 50% 90%, rgba(139, 92, 246, 0.10), transparent 50%);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      padding: 24px 28px;
    }}
    .studio-container {{
      max-width: 1440px;
      margin: 0 auto;
    }}
    .studio-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 26px;
      flex-wrap: wrap;
      gap: 18px;
    }}
    .brand-cluster {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .brand-logo-frame img {{
      width: 48px;
      height: 48px;
      border-radius: 50%;
      border: 2px solid rgba(99, 102, 241, 0.6);
      background: #080A10;
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.35);
      display: block;
    }}
    .brand-titles h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #FFFFFF, #E2E8F0);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .brand-titles .tagline {{
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 2px;
    }}
    .brand-titles .tagline strong {{
      color: var(--cyan);
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .status-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 20px;
      border: 1px solid transparent;
      font-family: 'Outfit', sans-serif;
    }}
    .status-chip .dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }}
    .chip-green {{
      background: rgba(16, 185, 129, 0.12);
      color: #6EE7B7;
      border-color: rgba(16, 185, 129, 0.25);
    }}
    .chip-green .dot {{
      background: #10B981;
      box-shadow: 0 0 8px #10B981;
    }}
    .chip-purple {{
      background: rgba(168, 85, 247, 0.12);
      color: #D8B4FE;
      border-color: rgba(168, 85, 247, 0.25);
    }}
    .chip-purple .dot {{
      background: #A855F7;
      box-shadow: 0 0 8px #A855F7;
    }}
    .chip-amber {{
      background: rgba(245, 158, 11, 0.12);
      color: #FCD34D;
      border-color: rgba(245, 158, 11, 0.25);
    }}
    .chip-amber .dot {{
      background: #F59E0B;
    }}
    .btn-nav {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 8px 14px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }}
    .btn-nav:hover {{
      background: rgba(255, 255, 255, 0.1);
      color: #FFFFFF;
      border-color: rgba(255, 255, 255, 0.2);
    }}
    .btn-nav.btn-danger:hover {{
      background: rgba(244, 63, 94, 0.15);
      color: #FECDD3;
      border-color: rgba(244, 63, 94, 0.3);
    }}
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: relative;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
      transition: all 0.25s ease;
    }}
    .metric-card:hover {{
      transform: translateY(-2px);
      border-color: var(--border-hover);
    }}
    .metric-card .meta {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .metric-card .num {{
      font-family: 'Outfit', sans-serif;
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1;
    }}
    .metric-card .lbl {{
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 500;
    }}
    .metric-card .icon-box {{
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }}
    .mc-cyan .num {{ color: var(--cyan); }}
    .mc-cyan .icon-box {{ background: rgba(6, 182, 212, 0.12); color: var(--cyan); border: 1px solid rgba(6, 182, 212, 0.25); }}
    .mc-purple .num {{ color: #C084FC; }}
    .mc-purple .icon-box {{ background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); }}
    .mc-green .num {{ color: #34D399; }}
    .mc-green .icon-box {{ background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.25); }}
    .mc-indigo .num {{ color: #818CF8; }}
    .mc-indigo .icon-box {{ background: rgba(99, 102, 241, 0.12); color: #818CF8; border: 1px solid rgba(99, 102, 241, 0.25); }}
    .command-toolbar {{
      display: flex;
      gap: 16px;
      margin-bottom: 22px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
    }}
    .search-wrapper {{
      flex: 1;
      min-width: 320px;
      position: relative;
    }}
    .search-icon {{
      position: absolute;
      left: 16px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-sub);
      pointer-events: none;
    }}
    .search-wrapper input {{
      width: 100%;
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      padding: 13px 44px 13px 46px;
      border-radius: 14px;
      color: #FFFFFF;
      font-size: 14px;
      outline: none;
      transition: all 0.2s ease;
      font-family: inherit;
    }}
    .search-wrapper input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
    }}
    .search-shortcut {{
      position: absolute;
      right: 14px;
      top: 50%;
      transform: translateY(-50%);
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--text-muted);
      padding: 2px 7px;
      pointer-events: none;
    }}
    .filter-tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tab-pill {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 9px 16px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      font-family: 'Outfit', sans-serif;
      cursor: pointer;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .tab-pill:hover {{
      background: rgba(255, 255, 255, 0.06);
      color: #FFFFFF;
    }}
    .tab-pill.active {{
      background: var(--primary);
      color: #FFFFFF;
      border-color: var(--primary);
      box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
    }}
    .workspace-grid {{
      display: grid;
      grid-template-columns: 1fr 440px;
      gap: 24px;
      align-items: start;
    }}
    @media (max-width: 1040px) {{
      .workspace-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    .ticket-card {{
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      border-radius: 16px;
      margin-bottom: 14px;
      overflow: hidden;
      transition: all 0.2s ease;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }}
    .ticket-card:hover {{
      border-color: var(--border-hover);
      background: var(--card-hover);
    }}
    .ticket-top {{
      padding: 16px 20px;
      display: flex;
      align-items: flex-start;
      gap: 14px;
      cursor: pointer;
      user-select: none;
    }}
    .sender-avatar {{
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(6, 182, 212, 0.25));
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: #FFFFFF;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Outfit', sans-serif;
      font-size: 16px;
      font-weight: 700;
      flex-shrink: 0;
    }}
    .ticket-info {{
      flex: 1;
      min-width: 0;
    }}
    .ticket-meta-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 4px;
    }}
    .sender-email {{
      font-size: 14px;
      font-weight: 700;
      color: #FFFFFF;
    }}
    .ticket-id {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.06);
      padding: 2px 7px;
      border-radius: 6px;
    }}
    .ticket-subject {{
      font-size: 15px;
      font-weight: 600;
      color: #E2E8F0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .ticket-date-col {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }}
    .ticket-date {{
      font-size: 12px;
      color: var(--text-sub);
      font-family: 'JetBrains Mono', monospace;
    }}
    .expand-icon {{
      color: var(--text-sub);
      transition: transform 0.25s ease;
      display: flex;
      align-items: center;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 10px;
      font-weight: 800;
      font-family: 'Outfit', sans-serif;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .badge-unread {{
      background: rgba(6, 182, 212, 0.15);
      color: var(--cyan);
      border: 1px solid rgba(6, 182, 212, 0.35);
    }}
    .badge-replied {{
      background: rgba(168, 85, 247, 0.15);
      color: #C084FC;
      border: 1px solid rgba(168, 85, 247, 0.35);
    }}
    .badge-resolved {{
      background: rgba(16, 185, 129, 0.15);
      color: #34D399;
      border: 1px solid rgba(16, 185, 129, 0.35);
    }}
    .badge-read {{
      background: rgba(148, 163, 184, 0.10);
      color: var(--text-muted);
      border: 1px solid rgba(148, 163, 184, 0.2);
    }}
    .pulse-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--cyan);
      box-shadow: 0 0 6px var(--cyan);
      animation: pulse 1.8s infinite;
    }}
    .pulse-dot-purple {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #C084FC;
      box-shadow: 0 0 6px #C084FC;
      animation: pulse 1.8s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}
    .ai-summary-card {{
      margin: 0 20px 14px;
      background: rgba(168, 85, 247, 0.08);
      border: 1px solid rgba(168, 85, 247, 0.2);
      border-radius: 12px;
      padding: 10px 14px;
    }}
    .ai-summary-label {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 700;
      color: #C084FC;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-bottom: 4px;
      font-family: 'Outfit', sans-serif;
    }}
    .ai-summary-text {{
      font-size: 13px;
      color: #E9D5FF;
      line-height: 1.5;
    }}
    .ticket-expansion {{
      display: none;
      padding: 20px;
      border-top: 1px solid var(--border);
      background: rgba(5, 8, 17, 0.85);
    }}
    .ticket-body-scroll {{
      margin-bottom: 16px;
    }}
    .body-label {{
      font-size: 11px;
      font-weight: 700;
      color: var(--text-sub);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .body-content {{
      font-size: 14px;
      line-height: 1.65;
      color: #CBD5E1;
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(13, 19, 36, 0.6);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      max-height: 350px;
      overflow-y: auto;
    }}
    .ai-draft-card {{
      background: rgba(99, 102, 241, 0.08);
      border: 1px solid rgba(99, 102, 241, 0.28);
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 18px;
    }}
    .ai-draft-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .ai-draft-title {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: 'Outfit', sans-serif;
      font-size: 13px;
      font-weight: 700;
      color: #A5B4FC;
    }}
    .btn-insert-ai {{
      background: linear-gradient(135deg, #6366F1, #4F46E5);
      border: none;
      color: #FFFFFF;
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .btn-insert-ai:hover {{
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }}
    .ai-draft-preview {{
      font-size: 13px;
      line-height: 1.6;
      color: #E0E7FF;
      background: rgba(7, 10, 20, 0.6);
      border-radius: 10px;
      padding: 12px 14px;
      max-height: 220px;
      overflow-y: auto;
      border: 1px solid rgba(99, 102, 241, 0.15);
    }}
    .att-wrapper {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }}
    .att-chip {{
      background: rgba(6, 182, 212, 0.1);
      border: 1px solid rgba(6, 182, 212, 0.25);
      color: #67E8F9;
      font-size: 12px;
      font-weight: 500;
      padding: 5px 12px;
      border-radius: 8px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .att-badge {{
      color: var(--cyan);
      display: inline-flex;
      align-items: center;
    }}
    .ticket-action-bar {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      padding-top: 6px;
    }}
    .btn-action-primary {{
      background: var(--primary);
      border: none;
      color: #FFFFFF;
      padding: 9px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      font-family: 'Outfit', sans-serif;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .btn-action-primary:hover {{
      background: var(--primary-hover);
      transform: translateY(-1px);
    }}
    .btn-action-thread {{
      background: rgba(168, 85, 247, 0.15);
      border: 1px solid rgba(168, 85, 247, 0.3);
      color: #E9D5FF;
      padding: 9px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      font-family: 'Outfit', sans-serif;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .btn-action-thread:hover {{
      background: rgba(168, 85, 247, 0.25);
    }}
    .btn-action-secondary {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 9px 14px;
      border-radius: 10px;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .btn-action-secondary:hover {{
      background: rgba(255, 255, 255, 0.1);
      color: #FFFFFF;
    }}
    .studio-pane {{
      background: var(--card-bg);
      backdrop-filter: blur(20px);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 24px;
      position: sticky;
      top: 24px;
      box-shadow: 0 10px 35px rgba(0, 0, 0, 0.4);
      position: relative;
      overflow: hidden;
    }}
    .studio-pane::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--primary), var(--cyan));
    }}
    .pane-header {{
      margin-bottom: 20px;
    }}
    .pane-header h2 {{
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 800;
      color: #FFFFFF;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .pane-header .sub {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }}
    .studio-form .form-group {{
      margin-bottom: 16px;
    }}
    .studio-form label {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-weight: 700;
      color: #CBD5E1;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .studio-form input, .studio-form textarea {{
      width: 100%;
      background: rgba(7, 10, 20, 0.85);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 11px 14px;
      color: #FFFFFF;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      transition: all 0.2s;
    }}
    .studio-form input:focus, .studio-form textarea:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
      background: rgba(7, 10, 20, 1);
    }}
    .ai-helpers-bar {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .chip-helper {{
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.25);
      color: #A5B4FC;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 9px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .chip-helper:hover {{
      background: rgba(99, 102, 241, 0.25);
      color: #FFFFFF;
    }}
    .btn-send-dispatch {{
      width: 100%;
      background: linear-gradient(135deg, var(--primary), #4338CA);
      color: #FFFFFF;
      border: none;
      padding: 13px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      letter-spacing: 0.01em;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .btn-send-dispatch:hover {{
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
    }}
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      z-index: 99999;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .timeline-window {{
      background: #0D1324;
      border: 1px solid var(--border);
      border-radius: 20px;
      width: 100%;
      max-width: 720px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8);
    }}
    .window-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255, 255, 255, 0.02);
    }}
    .window-header h3 {{
      font-family: 'Outfit', sans-serif;
      font-size: 17px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .btn-window-close {{
      background: rgba(255, 255, 255, 0.05);
      border: none;
      color: var(--text-muted);
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.2s;
    }}
    .btn-window-close:hover {{
      background: rgba(255, 255, 255, 0.15);
      color: #FFFFFF;
    }}
    .timeline-stream {{
      padding: 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .chat-bubble {{
      padding: 16px 18px;
      border-radius: 14px;
      font-size: 13.5px;
      line-height: 1.6;
      max-width: 88%;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }}
    .chat-bubble.inbound {{
      background: #111827;
      border: 1px solid #1F2937;
      color: #E2E8F0;
      align-self: flex-start;
      border-bottom-left-radius: 4px;
    }}
    .chat-bubble.outbound {{
      background: linear-gradient(135deg, #312E81, #1E1B4B);
      border: 1px solid #4338CA;
      color: #F8FAFC;
      align-self: flex-end;
      border-bottom-right-radius: 4px;
    }}
    .bubble-author {{
      font-size: 11px;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      opacity: 0.8;
    }}
    .toast-box {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: rgba(16, 185, 129, 0.95);
      color: #FFFFFF;
      padding: 12px 20px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
      display: none;
      align-items: center;
      gap: 8px;
      z-index: 999999;
      animation: slideUp 0.3s ease;
    }}
    @keyframes slideUp {{
      from {{ transform: translateY(20px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
    .glass-banner {{
      border-radius: 14px;
      padding: 16px 20px;
      margin-bottom: 22px;
      display: flex;
      align-items: center;
      gap: 14px;
      font-size: 14px;
      line-height: 1.5;
    }}
    .banner-warn {{
      background: rgba(245, 158, 11, 0.12);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #FEF08A;
    }}
    .banner-success {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #A7F3D0;
    }}
    .banner-danger {{
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #FECDD3;
    }}
    .empty-state {{
      padding: 60px 20px;
      text-align: center;
      background: var(--card-bg);
      border: 1px dashed var(--border);
      border-radius: 18px;
    }}
    .empty-icon {{
      font-size: 40px;
      margin-bottom: 12px;
    }}
    .empty-state h3 {{
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .empty-state p {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="studio-container">
    <header class="studio-header">
      <div class="brand-cluster">
        <div class="brand-logo-frame">
          <img src="https://aegixbot.xyz/static/aegix.png" alt="AEGIX">
        </div>
        <div class="brand-titles">
          <h1>AEGIX Support Studio <span style="font-size:12px;font-weight:700;background:rgba(99,102,241,0.2);color:#A5B4FC;padding:2px 8px;border-radius:6px;border:1px solid rgba(99,102,241,0.3);">v2.5 Enterprise</span></h1>
          <div class="tagline">Official Mail Gateway &bull; <strong>{SUPPORT_EMAIL}</strong></div>
        </div>
      </div>

      <div class="header-actions">
        {key_badge}
        {ai_badge}
        <a href="https://aegixbot.xyz" target="_blank" rel="noopener" class="btn-nav">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          <span>aegixbot.xyz</span>
        </a>
        <button type="button" class="btn-nav" onclick="window.location.reload()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          <span>Refresh</span>
        </button>
        <a href="/manage/logout" class="btn-nav btn-danger">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>
          <span>Sign Out</span>
        </a>
      </div>
    </header>

    {warning_banner}
    {feedback_html}

    <div class="metrics-grid">
      <div class="metric-card mc-cyan">
        <div class="meta">
          <div class="num">{unread}</div>
          <div class="lbl">New Inbound</div>
        </div>
        <div class="icon-box">📬</div>
      </div>

      <div class="metric-card mc-purple">
        <div class="meta">
          <div class="num">{user_replied}</div>
          <div class="lbl">Customer Follow-ups</div>
        </div>
        <div class="icon-box">💬</div>
      </div>

      <div class="metric-card mc-green">
        <div class="meta">
          <div class="num">{replied}</div>
          <div class="lbl">Resolved &amp; Dispatched</div>
        </div>
        <div class="icon-box">🛡️</div>
      </div>

      <div class="metric-card mc-indigo">
        <div class="meta">
          <div class="num">{total}</div>
          <div class="lbl">Total Support Tickets</div>
        </div>
        <div class="icon-box">📊</div>
      </div>
    </div>

    <div class="command-toolbar">
      <div class="search-wrapper">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="mailSearch" placeholder="Filter tickets by sender email, subject, ID, or keyword..." onkeyup="filterMails()">
        <span class="search-shortcut">/</span>
      </div>

      <div class="filter-tabs">
        <button class="tab-pill active" onclick="setFilter('all', this)">All Tickets ({total})</button>
        <button class="tab-pill" onclick="setFilter('unread', this)">New ({unread})</button>
        <button class="tab-pill" onclick="setFilter('user_replied', this)">Follow-ups ({user_replied})</button>
        <button class="tab-pill" onclick="setFilter('replied', this)">Resolved ({replied})</button>
        <button class="tab-pill" onclick="setFilter('att', this)">Attachments 📎</button>
      </div>
    </div>

    <div class="workspace-grid">
      <div id="ticketStream">
        {email_cards_html}
      </div>

      <div class="studio-pane">
        <div class="pane-header">
          <h2>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366F1" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            <span>Response Studio</span>
          </h2>
          <div class="sub">Dispatched officially via Resend Cloud API</div>
        </div>

        <form method="POST" action="/manage/send" class="studio-form" id="replyForm">
          <div class="form-group">
            <label for="recipient">Customer Recipient (To)</label>
            <input type="email" id="recipient" name="recipient" placeholder="client@domain.com" required>
          </div>

          <div class="form-group">
            <label for="subject">Email Subject</label>
            <input type="text" id="subject" name="subject" placeholder="Re: Support Ticket..." required>
          </div>

          <div class="form-group">
            <label for="body">
              <span>Official Message Body</span>
              <span id="charCount" style="font-family:'JetBrains Mono',monospace;color:var(--text-sub);font-size:10px;">0 chars</span>
            </label>
            <textarea id="body" name="body" rows="12" placeholder="Write your professional response, or click 'Insert into Composer' from any ticket above..." required oninput="updateCharCount()"></textarea>
          </div>

          <div class="ai-helpers-bar">
            <span class="chip-helper" onclick="insertSnippet('greeting')">+ Add Greeting</span>
            <span class="chip-helper" onclick="insertSnippet('server_id')">+ Request Server ID</span>
            <span class="chip-helper" onclick="insertSnippet('logs')">+ Request Logs</span>
            <span class="chip-helper" onclick="insertSnippet('signoff')">+ Standard Sign-off</span>
          </div>

          <button type="submit" class="btn-send-dispatch">
            <span>Dispatch Response via Resend</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </form>
      </div>
    </div>
  </div>

  <div class="modal-backdrop" id="threadModal" onclick="closeThreadModal(event)">
    <div class="timeline-window" onclick="event.stopPropagation()">
      <div class="window-header">
        <h3 id="modalThreadTitle">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#A855F7" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span>Conversation History Timeline</span>
        </h3>
        <button class="btn-window-close" onclick="closeThreadModal()">&times;</button>
      </div>
      <div class="timeline-stream" id="modalThreadContent">
        <div style="text-align:center;padding:30px;color:var(--text-muted);">Loading conversation...</div>
      </div>
    </div>
  </div>

  <div class="toast-box" id="toastBox">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
    <span id="toastMsg">Action completed successfully</span>
  </div>

  <script>
    let currentFilter = 'all';

    function toggleMail(id) {{
      const el = document.getElementById('body-' + id);
      const icon = document.getElementById('expand-icon-' + id);
      if (!el) return;
      const isBlock = (el.style.display === 'block');
      el.style.display = isBlock ? 'none' : 'block';
      if (icon) {{
        icon.style.transform = isBlock ? 'rotate(0deg)' : 'rotate(180deg)';
      }}
    }}

    function prefillReply(sender, subject, eid) {{
      document.getElementById('recipient').value = sender;
      const subEl = document.getElementById('subject');
      subEl.value = subject.toLowerCase().startsWith('re:') ? subject : 'Re: ' + subject;

      const aiDraftEl = document.getElementById('aidraft-text-' + eid);
      if (aiDraftEl && aiDraftEl.innerText.trim()) {{
        document.getElementById('body').value = aiDraftEl.innerText.trim();
      }} else {{
        document.getElementById('body').focus();
      }}
      updateCharCount();
      showToast('Prefilled recipient & subject in Response Studio');
      window.scrollTo({{ top: document.querySelector('.studio-pane').offsetTop - 20, behavior: 'smooth' }});
    }}

    function useAiDraft(eid) {{
      const el = document.getElementById('aidraft-text-' + eid);
      if (el) {{
        document.getElementById('body').value = el.innerText.trim();
        updateCharCount();
        showToast('✨ AI draft inserted into composer!');
        window.scrollTo({{ top: document.querySelector('.studio-pane').offsetTop - 20, behavior: 'smooth' }});
      }}
    }}

    function updateCharCount() {{
      const val = document.getElementById('body').value;
      const counter = document.getElementById('charCount');
      if (counter) counter.innerText = val.length + ' chars';
    }}

    function insertSnippet(type) {{
      const bodyEl = document.getElementById('body');
      let snippet = '';
      if (type === 'greeting') {{
        snippet = 'Hello,\\n\\nThank you for reaching out to AEGIX Support.\\n';
      }} else if (type === 'server_id') {{
        snippet = '\\nCould you please provide your Discord Server ID (Guild ID) so our engineering team can inspect the audit telemetry?\\n';
      }} else if (type === 'logs') {{
        snippet = '\\nIf possible, please share any console logs or screenshots displaying the error code.\\n';
      }} else if (type === 'signoff') {{
        snippet = '\\nBest regards,\\nAEGIX Support & Threat Intelligence Team\\nsupport@aegixbot.xyz | https://aegixbot.xyz\\n';
      }}
      bodyEl.value += snippet;
      updateCharCount();
      showToast('Snippet appended to composer');
      bodyEl.focus();
    }}

    function setFilter(type, btn) {{
      currentFilter = type;
      document.querySelectorAll('.tab-pill').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      filterMails();
    }}

    function filterMails() {{
      const q = document.getElementById('mailSearch').value.toLowerCase().trim();
      const items = document.querySelectorAll('.ticket-card');

      items.forEach(item => {{
        const st = item.getAttribute('data-status');
        const s = item.getAttribute('data-sender');
        const sub = item.getAttribute('data-subject');
        const eid = item.getAttribute('data-id');
        const hasAtt = item.getAttribute('data-has-att') === '1';

        let matchTab = false;
        if (currentFilter === 'all') matchTab = true;
        else if (currentFilter === 'att') matchTab = hasAtt;
        else matchTab = (st === currentFilter);

        let matchText = true;
        if (q) {{
          matchText = s.includes(q) || sub.includes(q) || eid.includes(q);
        }}

        item.style.display = (matchTab && matchText) ? 'block' : 'none';
      }});
    }}

    async function viewThread(tid) {{
      const modal = document.getElementById('threadModal');
      const content = document.getElementById('modalThreadContent');
      modal.style.display = 'flex';
      content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);"><div style="margin-top:10px;">Loading complete conversation thread...</div></div>';

      try {{
        const res = await fetch('/manage/api/thread/' + tid);
        const data = await res.json();
        if (data.ok && data.thread && data.thread.length > 0) {{
          let html = '';
          data.thread.forEach(msg => {{
            const isOut = msg.is_reply === 1;
            const cls = isOut ? 'outbound' : 'inbound';
            const author = isOut ? '🛡️ AEGIX Support Team' : '👤 ' + msg.sender;
            html += `
              <div class="chat-bubble ${{cls}}">
                <div class="bubble-author">
                  <span>${{author}}</span>
                  <span>${{msg.created_at}}</span>
                </div>
                <div style="font-weight:700;margin-bottom:6px;font-family:'Outfit',sans-serif;">${{msg.subject}}</div>
                <div style="white-space:pre-wrap;">${{msg.body_text || msg.body_html || '(Empty content)'}}</div>
              </div>
            `;
          }});
          content.innerHTML = html;
        }} else {{
          content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted);">No further messages found for this thread.</div>';
        }}
      }} catch (e) {{
        content.innerHTML = '<div style="color:#F43F5E;text-align:center;padding:30px;">Error loading thread: ' + e.message + '</div>';
      }}
    }}

    function closeThreadModal(e) {{
      if (!e || e.target.id === 'threadModal' || e.target.classList.contains('btn-window-close')) {{
        document.getElementById('threadModal').style.display = 'none';
      }}
    }}

    function showToast(msg) {{
      const t = document.getElementById('toastBox');
      const tm = document.getElementById('toastMsg');
      if (t && tm) {{
        tm.innerText = msg;
        t.style.display = 'flex';
        setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
      }}
    }}

    document.addEventListener('keydown', (e) => {{
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {{
        e.preventDefault();
        document.getElementById('mailSearch').focus();
      }}
      if (e.key === 'Escape') {{
        document.getElementById('threadModal').style.display = 'none';
      }}
    }});
  </script>
</body>
</html>"""

@mail_router.get("/manage", response_class=HTMLResponse)
async def manage_portal(request: Request, msg: str = "", err: str = ""):
    """Protected web management interface for support emails."""
    if not is_manage_authenticated(request):
        return HTMLResponse(render_login_html(error="Vui lòng nhập mật khẩu quản trị để tiếp tục." if err == "1" else ""))

    emails = []
    if turso_ref:
        emails = await turso_ref.get_all_emails(limit=150)

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
            max_age=2592000,
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

@mail_router.get("/manage/api/thread/{thread_id}")
async def manage_get_thread(request: Request, thread_id: str):
    """JSON API to retrieve full thread history."""
    if not is_manage_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not turso_ref:
        return JSONResponse({"ok": False, "thread": []})

    thread = await turso_ref.get_thread_emails(thread_id)
    return JSONResponse({"ok": True, "thread": thread})

@mail_router.get("/manage/api/ai-draft/{email_id}")
async def manage_get_ai_draft(request: Request, email_id: str):
    """JSON API to fetch or generate on-demand AI draft."""
    if not is_manage_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

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
def setup_mail_system(bot_instance: commands.Bot, turso_instance: Any, app_instance: Any):
    """Binds bot, turso DB, FastAPI router, and registers interactive commands."""
    global bot_ref, turso_ref
    bot_ref = bot_instance
    turso_ref = turso_instance
    app_instance.include_router(mail_router)
    bot_instance.add_listener(handle_email_interaction, "on_interaction")
    setup_mail_commands(bot_instance, turso_instance)
    log.info(f"📧 AIClaw Mail System attached: /manage, AI Auto-Draft, Webhook /api/webhook/resend & Commands (?inbox, ?mail, ?email, ?reply, ?aidraft)")
