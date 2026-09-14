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
        "Bạn là Chuyên viên Hỗ trợ Kỹ thuật Cấp cao của hệ thống AEGIX & AIClaw (Autonomous Discord Security & Threat Intelligence). "
        "Nhiệm vụ của bạn là soạn một thư phản hồi hỗ trợ khách hàng thật lịch sự, thấu cảm, rõ ràng và chuyên nghiệp. "
        "Nguyên tắc soạn thư:\n"
        "1. Ngôn ngữ: Nếu khách viết tiếng Việt thì trả lời bằng tiếng Việt; nếu khách viết tiếng Anh thì trả lời bằng tiếng Anh.\n"
        "2. Cấu trúc:\n"
        "   - Lời chào trang trọng (ví dụ: 'Kính gửi Quý khách / Chào bạn,')\n"
        "   - Xác nhận đã nhận được yêu cầu về [chủ đề câu hỏi]\n"
        "   - Hướng dẫn hoặc giải đáp chi tiết theo từng bước hoặc gạch đầu dòng ngắn gọn, dễ hiểu.\n"
        "   - Lời dặn dò sẵn sàng giải đáp thêm nếu khách cần hỗ trợ.\n"
        "   - Ký tên trang trọng:\n"
        "     Trân trọng,\n"
        "     Đội ngũ Hỗ trợ Kỹ thuật AEGIX & AIClaw\n"
        "     support@aegixbot.xyz | https://aegixbot.xyz\n"
        "3. ĐẶC BIỆT: Chỉ xuất DUY NHẤT nội dung bức thư để gửi đi, không thêm ghi chú, không đóng khung code markdown."
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
            f"Kính gửi Quý khách,\n\n"
            f"Đội ngũ Hỗ trợ AEGIX đã nhận được email của bạn liên quan đến: '{subject}'.\n\n"
            f"Chúng tôi đang xem xét chi tiết yêu cầu này và sẽ phản hồi sớm nhất có thể. "
            f"Nếu bạn có thêm thông tin bổ sung, vui lòng phản hồi trực tiếp vào email này.\n\n"
            f"Trân trọng,\n"
            f"Đội ngũ Hỗ trợ Kỹ thuật AEGIX & AIClaw\n"
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
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    a {{ color: #2563eb; text-decoration: none; }}
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
              <span style="opacity:0.95;">Chăm Sóc & Hỗ Trợ Kỹ Thuật</span>
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
      <div>Đây là email phản hồi chính thức từ hệ thống bảo mật <strong>AEGIX & AIClaw</strong>.</div>
      <div style="margin-top:4px;">Nếu bạn có thêm thắc mắc, bạn có thể trả lời trực tiếp email này hoặc truy cập <a href="https://aegixbot.xyz" style="color:#38bdf8;">aegixbot.xyz</a>.</div>
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
    err_box = f'<div class="login-err">⚠️ {error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đăng Nhập Cổng Email · support@aegixbot.xyz</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: radial-gradient(circle at top, #1e1b4b, #090d16 60%);
      color: #f8fafc;
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .login-card {{
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 20px;
      padding: 40px;
      width: 100%;
      max-width: 440px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      text-align: center;
    }}
    .logo {{
      width: 64px;
      height: 64px;
      border-radius: 50%;
      margin: 0 auto 18px;
      display: block;
      border: 2px solid rgba(99, 102, 241, 0.6);
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
    }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; letter-spacing: -0.02em; }}
    p.sub {{ color: #94a3b8; font-size: 14px; margin-bottom: 28px; line-height: 1.5; }}
    .login-err {{
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
      padding: 12px 16px;
      border-radius: 10px;
      font-size: 13px;
      margin-bottom: 20px;
      text-align: left;
    }}
    .input-group {{ margin-bottom: 24px; text-align: left; }}
    label {{ display: block; font-size: 13px; font-weight: 500; color: #cbd5e1; margin-bottom: 8px; }}
    input[type="password"] {{
      width: 100%;
      background: #0b0f19;
      border: 1px solid #2d3748;
      padding: 13px 16px;
      border-radius: 10px;
      color: #ffffff;
      font-size: 15px;
      outline: none;
      transition: all 0.2s ease;
    }}
    input[type="password"]:focus {{
      border-color: #6366f1;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
    }}
    button.btn-submit {{
      width: 100%;
      background: linear-gradient(135deg, #6366f1, #4f46e5);
      color: #ffffff;
      border: none;
      padding: 13px;
      border-radius: 10px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }}
    button.btn-submit:hover {{
      opacity: 0.95;
      transform: translateY(-1px);
    }}
    .footer-text {{ margin-top: 24px; font-size: 12px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="login-card">
    <img src="https://aegixbot.xyz/static/aegix.png" alt="AEGIX" class="logo">
    <h1>Cổng Quản Lý Email</h1>
    <p class="sub">Hộp thư hỗ trợ <strong>{SUPPORT_EMAIL}</strong><br>Bảo mật bởi hệ thống AIClaw</p>
    {err_box}
    <form method="POST" action="/manage/login">
      <div class="input-group">
        <label for="password">Mật khẩu xác thực (Master Password)</label>
        <input type="password" id="password" name="password" placeholder="Nhập mật khẩu quản trị..." required autofocus>
      </div>
      <button type="submit" class="btn-submit">Mở Hộp Thư ➔</button>
    </form>
    <div class="footer-text">AEGIX Security Operations • Phiên bản 2.5</div>
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
    ai_badge = '<span class="status-pill purple">✨ AI Auto-Draft Active</span>'

    warning_banner = ""
    if not has_resend_key:
        warning_banner = """
        <div class="banner-warn">
          <strong>⚠️ Chưa thiết lập RESEND_API_KEY:</strong> Bạn vẫn có thể nhận email và dùng AI soạn bản nháp bình thường. Để gửi email phản hồi, hãy đăng ký miễn phí tại <a href="https://resend.com/api-keys" target="_blank">resend.com/api-keys</a> và thêm biến <code>RESEND_API_KEY</code>.
        </div>
        """

    feedback_html = ""
    if success_msg:
        feedback_html += f'<div class="banner-success">✅ {success_msg}</div>'
    if error_msg:
        feedback_html += f'<div class="banner-error">❌ {error_msg}</div>'

    # Build Email Cards HTML
    email_cards_html = ""
    if not emails:
        email_cards_html = '<div class="empty-box">📭 Chưa có email nào được gửi đến support@aegixbot.xyz</div>'
    else:
        for em in emails:
            eid = em.get("id", "EM-???")
            tid = em.get("thread_id", eid)
            st = em.get("status", "unread")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "(Không có tiêu đề)")
            created_at = em.get("created_at", "")
            body = em.get("body_text") or em.get("body_html") or "(Nội dung trống)"
            ai_draft = em.get("ai_draft", "")
            ai_summary = em.get("ai_summary", "")

            # Attachments
            att_raw = em.get("attachments", "[]")
            try:
                att_list = json.loads(att_raw) if isinstance(att_raw, str) else (att_raw or [])
            except Exception:
                att_list = []

            has_att = len(att_list) > 0

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
            safe_ai_draft = ai_draft.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

            # Attachment pill badges
            att_html = ""
            if att_list:
                pills = "".join(f'<span class="att-pill">📎 {a.get("filename", "attachment")}</span>' for a in att_list)
                att_html = f'<div class="att-container">{pills}</div>'

            # AI Summary container
            ai_summary_html = ""
            if ai_summary:
                ai_summary_html = f'<div class="ai-summary-tag">🤖 <strong>Tóm tắt AI:</strong> {ai_summary}</div>'

            # AI Draft preview block
            ai_draft_block = ""
            if ai_draft:
                ai_draft_block = f"""
                <div class="ai-draft-box">
                  <div class="ai-draft-header">
                    <span>✨ Gợi ý câu trả lời từ AI (Đã sẵn sàng)</span>
                    <button type="button" class="btn-use-ai" onclick="useAiDraft('{eid}')">📋 Điền vào form trả lời</button>
                  </div>
                  <div class="ai-draft-content" id="aidraft-text-{eid}">{safe_ai_draft}</div>
                </div>
                """

            email_cards_html += f"""
            <div class="mail-item" id="item-{eid}" data-status="{st}" data-sender="{sender.lower()}" data-subject="{subject.lower()}" data-id="{eid.lower()}" data-has-att="{'1' if has_att else '0'}">
              <div class="mail-header" onclick="toggleMail('{eid}')">
                <div class="mail-title-group">
                  {badge}
                  <span class="mail-sender">{sender}</span>
                  <span class="mail-id">#{eid}</span>
                  {'<span class="att-icon">📎</span>' if has_att else ''}
                </div>
                <div class="mail-date">{created_at}</div>
              </div>

              <div class="mail-subject" onclick="toggleMail('{eid}')">{subject}</div>
              {ai_summary_html}

              <div class="mail-body-container" id="body-{eid}">
                <div class="mail-body-text">{safe_body}</div>
                {att_html}
                {ai_draft_block}

                <div class="mail-actions">
                  <button type="button" class="btn-reply-fill" onclick="prefillReply('{sender}', '{subject}', '{eid}')">
                    ✍️ Soạn phản hồi
                  </button>
                  <button type="button" class="btn-view-thread" onclick="viewThread('{tid}')">
                    💬 Lịch sử luồng (Thread)
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
  <title>Cổng Quản Trị Email · support@aegixbot.xyz</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #07090e;
      --card: #0f1422;
      --card-hover: #141c30;
      --border: #1e263d;
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --accent-cyan: #38bdf8;
      --accent-green: #22c55e;
      --accent-purple: #a855f7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100vh;
      padding: 24px 20px;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}

    /* Header */
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
    .brand {{ display: flex; align-items: center; gap: 14px; }}
    .brand img {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 2px solid var(--primary);
      box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
    }}
    .brand h1 {{ font-size: 20px; font-weight: 800; letter-spacing: -0.02em; }}
    .brand-sub {{ font-size: 13px; color: var(--text-muted); }}

    .status-group {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 20px;
    }}
    .status-pill.green {{ background: rgba(34, 197, 94, 0.15); color: #86efac; border: 1px solid rgba(34, 197, 94, 0.3); }}
    .status-pill.purple {{ background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3); }}
    .status-pill.yellow {{ background: rgba(234, 179, 8, 0.15); color: #fde047; border: 1px solid rgba(234, 179, 8, 0.3); }}
    .btn-logout {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 7px 14px;
      border-radius: 8px;
      text-decoration: none;
      font-size: 12px;
      font-weight: 600;
      transition: all 0.2s;
    }}
    .btn-logout:hover {{ background: rgba(239, 68, 68, 0.15); color: #fca5a5; border-color: rgba(239, 68, 68, 0.3); }}

    /* Stat Cards */
    .stat-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }}
    .stat-card .num {{ font-size: 28px; font-weight: 800; letter-spacing: -0.02em; }}
    .stat-card .label {{ font-size: 13px; color: var(--text-muted); font-weight: 500; }}

    /* Search & Filter Toolbar */
    .toolbar {{
      display: flex;
      gap: 14px;
      margin-bottom: 20px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
    }}
    .search-box {{
      flex: 1;
      min-width: 280px;
      position: relative;
    }}
    .search-box input {{
      width: 100%;
      background: var(--card);
      border: 1px solid var(--border);
      padding: 12px 18px;
      border-radius: 10px;
      color: #fff;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }}
    .search-box input:focus {{ border-color: var(--primary); }}

    .filter-tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .tab-btn {{
      background: var(--card);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 9px 16px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .tab-btn.active, .tab-btn:hover {{
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }}

    /* Layout: 2 Columns on desktop */
    .content-grid {{
      display: grid;
      grid-template-columns: 1fr 440px;
      gap: 24px;
    }}
    @media (max-width: 980px) {{
      .content-grid {{ grid-template-columns: 1fr; }}
    }}

    /* Email Items List */
    .mail-item {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      margin-bottom: 14px;
      overflow: hidden;
      transition: all 0.2s;
    }}
    .mail-item:hover {{ border-color: rgba(99, 102, 241, 0.4); background: var(--card-hover); }}
    .mail-header {{
      padding: 16px 20px 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      user-select: none;
    }}
    .mail-title-group {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    .mail-sender {{ font-weight: 700; font-size: 14px; color: #fff; }}
    .mail-id {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; }}
    .mail-date {{ font-size: 12px; color: var(--text-muted); }}
    .mail-subject {{
      padding: 0 20px 14px;
      font-size: 15px;
      font-weight: 600;
      color: #e2e8f0;
      cursor: pointer;
    }}

    .ai-summary-tag {{
      margin: 0 20px 12px;
      background: rgba(168, 85, 247, 0.12);
      border: 1px solid rgba(168, 85, 247, 0.25);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: 13px;
      color: #e9d5ff;
    }}

    .mail-body-container {{
      display: none;
      padding: 18px 20px;
      border-top: 1px solid var(--border);
      background: rgba(7, 9, 14, 0.6);
    }}
    .mail-body-text {{
      font-size: 14px;
      line-height: 1.6;
      color: #cbd5e1;
      white-space: pre-wrap;
      word-break: break-word;
      margin-bottom: 16px;
      max-height: 400px;
      overflow-y: auto;
      padding-right: 6px;
    }}

    /* AI Draft Box */
    .ai-draft-box {{
      background: rgba(99, 102, 241, 0.08);
      border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 10px;
      padding: 14px 16px;
      margin-bottom: 16px;
    }}
    .ai-draft-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 13px;
      font-weight: 700;
      color: #a5b4fc;
    }}
    .btn-use-ai {{
      background: var(--primary);
      border: none;
      color: #fff;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }}
    .ai-draft-content {{
      font-size: 13px;
      line-height: 1.6;
      color: #e0e7ff;
      max-height: 200px;
      overflow-y: auto;
    }}

    /* Attachments */
    .att-container {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }}
    .att-pill {{
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.25);
      color: #7dd3fc;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 6px;
    }}

    .mail-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .btn-reply-fill {{
      background: var(--primary);
      border: none;
      color: #fff;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn-view-thread {{
      background: rgba(168, 85, 247, 0.2);
      border: 1px solid rgba(168, 85, 247, 0.35);
      color: #e9d5ff;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn-secondary-sm {{
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 13px;
      cursor: pointer;
    }}

    /* Badges */
    .badge {{ font-size: 10px; font-weight: 800; padding: 3px 8px; border-radius: 6px; letter-spacing: 0.04em; text-transform: uppercase; }}
    .badge-unread {{ background: rgba(56, 189, 248, 0.18); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.4); }}
    .badge-purple {{ background: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }}
    .badge-green {{ background: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); }}
    .badge-gray {{ background: rgba(148, 163, 184, 0.1); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); }}

    /* Send Form */
    .reply-pane {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 24px;
      height: fit-content;
      position: sticky;
      top: 24px;
    }}
    .pane-title {{ font-size: 17px; font-weight: 700; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; }}
    .form-group {{ margin-bottom: 16px; }}
    .form-group label {{ display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; }}
    .form-group input, .form-group textarea {{
      width: 100%;
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-size: 14px;
      font-family: inherit;
      outline: none;
    }}
    .form-group input:focus, .form-group textarea:focus {{ border-color: var(--primary); }}
    .btn-send-main {{
      width: 100%;
      background: linear-gradient(135deg, var(--primary), #4338ca);
      border: none;
      color: #fff;
      padding: 12px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .btn-send-main:hover {{ opacity: 0.95; transform: translateY(-1px); }}

    /* Thread Modal */
    .modal-overlay {{
      display: none;
      position: fixed;
      top:0; left:0; right:0; bottom:0;
      background: rgba(0,0,0,0.75);
      backdrop-filter: blur(8px);
      z-index: 9999;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-card {{
      background: #0f1422;
      border: 1px solid var(--border);
      border-radius: 16px;
      width: 100%;
      max-width: 680px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7);
    }}
    .modal-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .modal-header h3 {{ font-size: 16px; font-weight: 700; }}
    .btn-close {{ background: none; border: none; color: var(--text-muted); font-size: 20px; cursor: pointer; }}
    .modal-body {{ padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }}
    .timeline-msg {{
      padding: 14px 18px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.6;
    }}
    .timeline-msg.inbound {{ background: #131b2e; border: 1px solid #1e293b; color: #e2e8f0; align-self: flex-start; max-width: 90%; }}
    .timeline-msg.outbound {{ background: #2e1065; border: 1px solid #4c1d95; color: #f5f3ff; align-self: flex-end; max-width: 90%; }}
    .timeline-meta {{ font-size: 11px; opacity: 0.7; margin-bottom: 6px; }}

    /* Banners */
    .banner-warn {{ background: rgba(234, 179, 8, 0.12); border: 1px solid rgba(234, 179, 8, 0.3); color: #fef08a; padding: 14px 20px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; }}
    .banner-success {{ background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); color: #86efac; padding: 14px 20px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; }}
    .banner-error {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #fca5a5; padding: 14px 20px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; }}
    .empty-box {{ padding: 60px 20px; text-align: center; color: var(--text-muted); font-size: 15px; background: var(--card); border: 1px dashed var(--border); border-radius: 14px; }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div class="brand">
        <img src="https://aegixbot.xyz/static/aegix.png" alt="AEGIX">
        <div>
          <h1>Hộp Thư Quản Trị {SUPPORT_EMAIL}</h1>
          <div class="brand-sub">Trung Tâm Phản Hồi & Hỗ Trợ Khách Hàng AEGIX • AIClaw</div>
        </div>
      </div>
      <div class="status-group">
        {key_badge}
        {ai_badge}
        <a href="/manage/logout" class="btn-logout">Đăng Xuất</a>
      </div>
    </div>

    {warning_banner}
    {feedback_html}

    <!-- Stat Row -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="num" style="color: var(--accent-cyan);">{unread}</div>
        <div class="label">Thư mới chưa đọc</div>
      </div>
      <div class="stat-card">
        <div class="num" style="color: var(--accent-purple);">{user_replied}</div>
        <div class="label">Khách đã phản hồi (Follow-up)</div>
      </div>
      <div class="stat-card">
        <div class="num" style="color: var(--accent-green);">{replied}</div>
        <div class="label">Đã gửi câu trả lời</div>
      </div>
      <div class="stat-card">
        <div class="num" style="color: #fff;">{total}</div>
        <div class="label">Tổng số thư trong hệ thống</div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-box">
        <input type="text" id="mailSearch" placeholder="🔍 Tìm kiếm theo email người gửi, tiêu đề, mã thư..." onkeyup="filterMails()">
      </div>
      <div class="filter-tabs">
        <button class="tab-btn active" onclick="setFilter('all', this)">Tất cả ({total})</button>
        <button class="tab-btn" onclick="setFilter('unread', this)">Mới ({unread})</button>
        <button class="tab-btn" onclick="setFilter('user_replied', this)">Khách reply ({user_replied})</button>
        <button class="tab-btn" onclick="setFilter('replied', this)">Đã trả lời ({replied})</button>
        <button class="tab-btn" onclick="setFilter('att', this)">Có đính kèm 📎</button>
      </div>
    </div>

    <!-- Content Grid -->
    <div class="content-grid">
      <!-- Left: Email Cards List -->
      <div id="emailList">
        {email_cards_html}
      </div>

      <!-- Right: Send Reply Composer -->
      <div class="reply-pane">
        <div class="pane-title">
          <span>✍️ Soạn Thư Trực Tiếp</span>
          <span style="font-size:12px;color:var(--text-muted);">qua Resend</span>
        </div>
        <form method="POST" action="/manage/send">
          <div class="form-group">
            <label for="recipient">Người nhận (To)</label>
            <input type="email" id="recipient" name="recipient" placeholder="customer@example.com" required>
          </div>
          <div class="form-group">
            <label for="subject">Tiêu đề (Subject)</label>
            <input type="text" id="subject" name="subject" placeholder="Re: Tiêu đề yêu cầu hỗ trợ" required>
          </div>
          <div class="form-group">
            <label for="body">Nội dung thư phản hồi</label>
            <textarea id="body" name="body" rows="11" placeholder="Nhập nội dung thư phản hồi tại đây hoặc nhấn '✍️ Soạn phản hồi' từ email khách hàng..." required></textarea>
          </div>
          <button type="submit" class="btn-send-main">Gửi Email Phản Hồi Ngay 🚀</button>
        </form>
      </div>
    </div>
  </div>

  <!-- Thread History Modal -->
  <div class="modal-overlay" id="threadModal" onclick="closeThreadModal(event)">
    <div class="modal-card" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h3 id="modalThreadTitle">💬 Lịch sử luồng trao đổi (Thread)</h3>
        <button class="btn-close" onclick="closeThreadModal()">&times;</button>
      </div>
      <div class="modal-body" id="modalThreadContent">
        <div style="text-align:center;color:var(--text-muted);">Đang tải lịch sử...</div>
      </div>
    </div>
  </div>

  <script>
    let currentFilter = 'all';

    function toggleMail(id) {{
      const el = document.getElementById('body-' + id);
      if (!el) return;
      el.style.display = (el.style.display === 'block') ? 'none' : 'block';
    }}

    function prefillReply(sender, subject, eid) {{
      document.getElementById('recipient').value = sender;
      const subEl = document.getElementById('subject');
      subEl.value = subject.toLowerCase().startsWith('re:') ? subject : 'Re: ' + subject;

      // If AI draft text exists in the item, use it
      const aiDraftEl = document.getElementById('aidraft-text-' + eid);
      if (aiDraftEl && aiDraftEl.innerText.trim()) {{
        document.getElementById('body').value = aiDraftEl.innerText.trim();
      }} else {{
        document.getElementById('body').focus();
      }}
      window.scrollTo({{ top: document.querySelector('.reply-pane').offsetTop - 20, behavior: 'smooth' }});
    }}

    function useAiDraft(eid) {{
      const el = document.getElementById('aidraft-text-' + eid);
      if (el) {{
        document.getElementById('body').value = el.innerText.trim();
        window.scrollTo({{ top: document.querySelector('.reply-pane').offsetTop - 20, behavior: 'smooth' }});
      }}
    }}

    function setFilter(type, btn) {{
      currentFilter = type;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      filterMails();
    }}

    function filterMails() {{
      const q = document.getElementById('mailSearch').value.toLowerCase().trim();
      const items = document.querySelectorAll('.mail-item');

      items.forEach(item => {{
        const st = item.getAttribute('data-status');
        const s = item.getAttribute('data-sender');
        const sub = item.getAttribute('data-subject');
        const eid = item.getAttribute('data-id');
        const hasAtt = item.getAttribute('data-has-att') === '1';

        // Filter tab match
        let matchTab = false;
        if (currentFilter === 'all') matchTab = true;
        else if (currentFilter === 'att') matchTab = hasAtt;
        else matchTab = (st === currentFilter);

        // Search text match
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
      content.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">⏳ Đang tải toàn bộ luồng hội thoại...</div>';

      try {{
        const res = await fetch('/manage/api/thread/' + tid);
        const data = await res.json();
        if (data.ok && data.thread && data.thread.length > 0) {{
          let html = '';
          data.thread.forEach(msg => {{
            const isOut = msg.is_reply === 1;
            const cls = isOut ? 'outbound' : 'inbound';
            const author = isOut ? '🛡️ Ban Quản Trị AEGIX (' + msg.sender + ')' : '👤 Khách Hàng (' + msg.sender + ')';
            html += `
              <div class="timeline-msg ${{cls}}">
                <div class="timeline-meta">${{author}} • ${{msg.created_at}}</div>
                <div style="font-weight:600;margin-bottom:4px;">${{msg.subject}}</div>
                <div style="white-space:pre-wrap;">${{msg.body_text || msg.body_html || '(Không có nội dung)'}}</div>
              </div>
            `;
          }});
          content.innerHTML = html;
        }} else {{
          content.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted);">Không tìm thấy thêm tin nhắn nào trong luồng này.</div>';
        }}
      }} catch (e) {{
        content.innerHTML = '<div style="color:#f87171;text-align:center;">Lỗi khi tải dữ liệu luồng: ' + e.message + '</div>';
      }}
    }}

    function closeThreadModal() {{
      document.getElementById('threadModal').style.display = 'none';
    }}
  </script>
</body>
</html>"""

# ──────────────────────────────────────────────
# WEB MANAGEMENT PORTAL API ROUTES
# ──────────────────────────────────────────────
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
