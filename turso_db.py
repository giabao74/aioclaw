"""
Turso Database Client for AIClaw (Async HTTP Pipeline API)
Connects directly to Turso / LibSQL over HTTPS with zero native C dependencies.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import aiohttp

log = logging.getLogger("turso_db")

VN_TZ = timezone(timedelta(hours=7))

class TursoDB:
    def __init__(self, url: str = None, token: str = None):
        raw_url = url or os.getenv("TURSO_DATABASE_URL", "")
        self.token = token or os.getenv("TURSO_AUTH_TOKEN", "")
        
        clean_url = raw_url.replace("libsql://", "https://").rstrip("/")
        if not clean_url.endswith("/v2/pipeline"):
            clean_url += "/v2/pipeline"
        self.pipeline_url = clean_url
        self._initialized = False
        self._email_cache: List[Dict[str, Any]] = []

    async def _execute_pipeline(self, statements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        requests_payload = []
        for stmt in statements:
            req_item = {
                "type": "execute",
                "stmt": {
                    "sql": stmt["sql"]
                }
            }
            if "args" in stmt and stmt["args"]:
                formatted_args = []
                for arg in stmt["args"]:
                    if arg is None:
                        formatted_args.append({"type": "null"})
                    elif isinstance(arg, (int, float)):
                        formatted_args.append({"type": "integer" if isinstance(arg, int) else "float", "value": str(arg)})
                    else:
                        formatted_args.append({"type": "text", "value": str(arg)})
                req_item["stmt"]["args"] = formatted_args
            requests_payload.append(req_item)

        requests_payload.append({"type": "close"})

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(self.pipeline_url, headers=headers, json={"requests": requests_payload}) as resp:
                if resp.status != 200:
                    err_txt = await resp.text()
                    raise RuntimeError(f"Turso API error (HTTP {resp.status}): {err_txt}")
                data = await resp.json()
                return data.get("results", [])

    async def execute(self, sql: str, args: list = None) -> List[Dict[str, Any]]:
        results = await self._execute_pipeline([{"sql": sql, "args": args or []}])
        rows = []
        if results and results[0].get("type") == "ok":
            resp_data = results[0].get("response", {})
            result_obj = resp_data.get("result", {})
            cols = [c["name"] for c in result_obj.get("cols", [])]
            raw_rows = result_obj.get("rows", [])
            for r in raw_rows:
                row_dict = {}
                for idx, cell in enumerate(r):
                    col_name = cols[idx] if idx < len(cols) else f"col_{idx}"
                    row_dict[col_name] = cell.get("value") if isinstance(cell, dict) else cell
                rows.append(row_dict)
        elif results and results[0].get("type") == "error":
            raise RuntimeError(f"Turso query error: {results[0].get('error')}")
        return rows

    async def init_schema(self):
        if self._initialized:
            return
        
        await self.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                next_invoice TEXT NOT NULL,
                last_notified TEXT DEFAULT '',
                category TEXT DEFAULT 'service'
            )
        """)
        try:
            await self.execute("ALTER TABLE reminders ADD COLUMN category TEXT DEFAULT 'service'")
        except Exception:
            pass

        await self.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await self.execute("""
            CREATE TABLE IF NOT EXISTS support_emails (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_text TEXT DEFAULT '',
                body_html TEXT DEFAULT '',
                status TEXT DEFAULT 'unread',
                is_reply INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        existing = await self.get_all_reminders()
        existing_ids = {r["id"] for r in existing}

        initial_services = [
            ("h1", "H1 (HiddenCloud 1)", "https://dash.hidencloud.com/service/209311/manage", "2026-09-12 00:00:00", "service"),
            ("h2", "H2 (HiddenCloud 2)", "https://dash.hidencloud.com/service/209463/manage", "2026-09-05 00:00:00", "service"),
            ("h3", "H3 (HiddenCloud 3)", "https://dash.hidencloud.com/service/212141/manage", "2026-09-10 00:00:00", "service"),
            ("h4", "H4 (HiddenCloud 4)", "https://dash.hidencloud.com/service/221741/manage", "2026-09-11 00:00:00", "service"),
            ("h5", "H5 (HiddenCloud 5)", "https://dash.hidencloud.com/service/230079/manage", "2026-09-15 00:00:00", "service"),
            ("optik", "OptikLink", "https://optiklink.net/auth", "2026-09-15 00:00:00", "service"),
            ("duolingo", "Duolingo Học Tiếng", "https://www.duolingo.com", "2026-09-04 20:00:00", "duolingo")
        ]

        for s_id, s_name, s_url, s_date, s_cat in initial_services:
            if s_id not in existing_ids:
                await self.upsert_reminder(s_id, s_name, s_url, s_date, category=s_cat)
                log.info(f"Seeded reminder service: {s_name} -> {s_date}")

        self._initialized = True

    async def get_all_reminders(self) -> List[Dict[str, Any]]:
        return await self.execute("SELECT id, name, url, next_invoice, last_notified, category FROM reminders ORDER BY next_invoice ASC")

    async def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        rows = await self.execute("SELECT id, name, url, next_invoice, last_notified, category FROM reminders WHERE id = ?", [reminder_id.lower()])
        return rows[0] if rows else None

    async def upsert_reminder(self, reminder_id: str, name: str, url: str, next_invoice: str, category: str = "service"):
        await self.execute("""
            INSERT OR REPLACE INTO reminders (id, name, url, next_invoice, last_notified, category)
            VALUES (?, ?, ?, ?, COALESCE((SELECT last_notified FROM reminders WHERE id = ?), ''), ?)
        """, [reminder_id.lower(), name, url, next_invoice, reminder_id.lower(), category])

    async def update_last_notified(self, reminder_id: str, timestamp_str: str):
        await self.execute("UPDATE reminders SET last_notified = ? WHERE id = ?", [timestamp_str, reminder_id.lower()])

    async def add_days_to_reminder(self, reminder_id: str, days: int = 7) -> Optional[datetime]:
        item = await self.get_reminder(reminder_id)
        if not item:
            return None

        current_str = item.get("next_invoice", "")
        parsed_dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%d %b %Y %H:%M:%S"):
            try:
                parsed_dt = datetime.strptime(current_str.strip(), fmt)
                break
            except Exception:
                pass

        if parsed_dt is None:
            parsed_dt = datetime.now(VN_TZ).replace(tzinfo=None)

        new_dt = parsed_dt + timedelta(days=days)
        new_str = new_dt.strftime("%Y-%m-%d %H:%M:%S")

        await self.execute("UPDATE reminders SET next_invoice = ?, last_notified = '' WHERE id = ?", [new_str, reminder_id.lower()])
        return new_dt

    async def get_config(self, key: str) -> Optional[str]:
        rows = await self.execute("SELECT value FROM bot_config WHERE key = ?", [key])
        return rows[0]["value"] if rows else None

    async def set_config(self, key: str, value: str):
        await self.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", [key, str(value)])

    # ──────────────────────────────────────────────
    # SUPPORT EMAILS MANAGEMENT (support@aegixbot.xyz)
    # ──────────────────────────────────────────────
    async def find_existing_thread(self, sender: str, subject: str) -> Optional[Dict[str, Any]]:
        """Finds if an incoming email belongs to an existing conversation thread."""
        clean_subj = subject.lower().replace("re:", "").replace("fwd:", "").strip()
        try:
            rows = await self.execute("""
                SELECT id, thread_id, status FROM support_emails
                WHERE (sender = ? OR recipient = ?) AND lower(subject) LIKE ?
                ORDER BY created_at DESC LIMIT 1
            """, [sender, sender, f"%{clean_subj}%"])
            if rows:
                return rows[0]
        except Exception as e:
            log.warning(f"Turso find_existing_thread fallback to cache: {e}")
        
        # Fallback to in-memory cache
        for item in reversed(self._email_cache):
            if (item.get("sender") == sender or item.get("recipient") == sender) and clean_subj in item.get("subject", "").lower():
                return item
        return None

    async def save_support_email(
        self,
        email_id: str,
        thread_id: str,
        sender: str,
        recipient: str,
        subject: str,
        body_text: str = "",
        body_html: str = "",
        status: str = "unread",
        is_reply: int = 0,
        created_at: str = None
    ) -> Dict[str, Any]:
        """Saves incoming or outgoing email to Turso DB and memory cache."""
        now_str = created_at or datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        email_item = {
            "id": email_id,
            "thread_id": thread_id,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "status": status,
            "is_reply": is_reply,
            "created_at": now_str
        }

        # Keep in local memory cache
        # If ID already exists in cache, update it
        existing_idx = next((i for i, em in enumerate(self._email_cache) if em["id"] == email_id), None)
        if existing_idx is not None:
            self._email_cache[existing_idx] = email_item
        else:
            self._email_cache.insert(0, email_item)
            if len(self._email_cache) > 200:
                self._email_cache.pop()

        try:
            await self.execute("""
                INSERT OR REPLACE INTO support_emails
                (id, thread_id, sender, recipient, subject, body_text, body_html, status, is_reply, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [email_id, thread_id, sender, recipient, subject, body_text, body_html, status, is_reply, now_str])
        except Exception as e:
            log.warning(f"Turso save_support_email error, saved to in-memory cache: {e}")

        return email_item

    async def get_all_emails(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves support emails sorted by most recent first."""
        try:
            rows = await self.execute("""
                SELECT id, thread_id, sender, recipient, subject, body_text, body_html, status, is_reply, created_at
                FROM support_emails
                ORDER BY created_at DESC LIMIT ?
            """, [limit])
            if rows:
                # Merge with cache if any new items are in cache
                cached_ids = {r["id"] for r in rows}
                for item in self._email_cache:
                    if item["id"] not in cached_ids:
                        rows.insert(0, item)
                return rows[:limit]
        except Exception as e:
            log.warning(f"Turso get_all_emails error, falling back to cache: {e}")
        
        return self._email_cache[:limit]

    async def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single email by ID."""
        for item in self._email_cache:
            if item["id"] == email_id:
                return item
        try:
            rows = await self.execute("""
                SELECT id, thread_id, sender, recipient, subject, body_text, body_html, status, is_reply, created_at
                FROM support_emails WHERE id = ?
            """, [email_id])
            return rows[0] if rows else None
        except Exception:
            return None

    async def update_email_status(self, email_id: str, status: str):
        """Updates email status: 'unread', 'read', 'replied', 'user_replied'."""
        for item in self._email_cache:
            if item["id"] == email_id:
                item["status"] = status
        try:
            await self.execute("UPDATE support_emails SET status = ? WHERE id = ?", [status, email_id])
        except Exception as e:
            log.warning(f"Turso update_email_status error: {e}")
