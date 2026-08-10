"""
Nodes: send_approval_request, wait_for_approval, handle_rejection
Handles all Telegram interaction for the YES/NO approval loop.
- Uses LLM to interpret vague/natural language replies
- Re-asks if reply is unclear
- Auto-approves if no clear answer within 1 hour total
"""

import time
import requests
from graph.state import ProjectState

TELEGRAM_BOT_TOKEN = "***TELEGRAM_TOKEN_REDACTED***"
TELEGRAM_CHAT_ID   = "***CHAT_ID_REDACTED***"
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
DEEPSEEK_API_URL   = "https://api.deepseek.com/chat/completions"


# ── Telegram helpers ──────────────────────────────────────────────────────────

def tg_send(text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    })


def tg_get_latest_offset() -> int:
    resp    = requests.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 1, "offset": -1})
    updates = resp.json().get("result", [])
    return updates[-1]["update_id"] + 1 if updates else 0


# ── LLM reply interpreter ─────────────────────────────────────────────────────

def _interpret_reply(user_text: str, slug: str, api_key: str) -> str:
    """
    Use LLM to classify the user's reply in context.
    Returns: 'approved' | 'rejected' | 'unclear'
    """
    prompt = (
        f"A user was asked whether to approve building a software project called '{slug}'.\n"
        f"The user replied: \"{user_text}\"\n\n"
        f"Classify their intent as one of:\n"
        f"- APPROVED: they want to proceed (yes, sure, ok, go ahead, do it, sounds good, etc.)\n"
        f"- REJECTED: they want to skip it (no, nope, skip, don't, next, pass, etc.)\n"
        f"- UNCLEAR: the reply is ambiguous, unrelated, or unclear\n\n"
        f"Reply with ONLY one word: APPROVED, REJECTED, or UNCLEAR."
    )
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You classify user intents precisely and concisely."},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.0,
        },
    )
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
    print(f"[wait_for_approval] LLM classified reply '{user_text}' as: {answer}")

    if "APPROVED" in answer:
        return "approved"
    if "REJECTED" in answer:
        return "rejected"
    return "unclear"


# ── Polling helper ────────────────────────────────────────────────────────────

def _poll_one_reply(after_offset: int, wait_seconds: int) -> tuple:
    """
    Wait up to `wait_seconds` for a single new message.
    Returns (new_offset, message_text_or_None)
    """
    offset        = after_offset
    poll_interval = 30
    deadline      = time.time() + wait_seconds

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={
                    "offset":          offset,
                    "timeout":         min(poll_interval, max(remaining, 1)),
                    "allowed_updates": ["message"],
                },
                timeout=poll_interval + 5,
            )
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg    = update.get("message", {})
                if str(msg.get("chat", {}).get("id", "")) != str(TELEGRAM_CHAT_ID):
                    continue
                text = msg.get("text", "").strip()
                if text:
                    return offset, text
        except Exception as e:
            print(f"[wait_for_approval] Poll error: {e}")
            time.sleep(poll_interval)

    return offset, None


# ── Nodes ─────────────────────────────────────────────────────────────────────

def send_approval_request(state: ProjectState) -> dict:
    project = state["selected_project"]
    slug    = project["slug"]
    desc    = project["description"]
    lang    = project["language"].capitalize()

    offset = tg_get_latest_offset()

    tg_send(
        f"🤔 <b>Project Approval Request</b>\n\n"
        f"📦 <b>Project:</b> <code>{slug}</code>\n"
        f"🌐 <b>Language:</b> {lang}\n"
        f"📄 <b>Description:</b> {desc}\n\n"
        f"Reply <b>YES</b> ✅ to approve\n"
        f"Reply <b>NO</b> ❌ to skip and get a new idea\n\n"
        f"⏰ <i>Auto-approves in 1 hour if no reply.</i>"
    )
    print(f"[send_approval_request] Sent approval request for '{slug}'")
    return {"tg_offset": offset}


def wait_for_approval(state: ProjectState) -> dict:
    api_key  = state["api_key"]
    slug     = state["selected_project"]["slug"]
    offset   = state["tg_offset"]
    deadline = time.time() + 3600   # 1 hour hard deadline

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            break

        print(f"[wait_for_approval] Waiting for reply... ({remaining}s left)")
        offset, text = _poll_one_reply(offset, wait_seconds=min(300, remaining))

        if text is None:
            # No message received in this window — keep waiting
            continue

        # LLM interprets the reply
        intent = _interpret_reply(text, slug, api_key)

        if intent == "approved":
            return {"approval_status": "approved", "tg_offset": offset}

        if intent == "rejected":
            return {"approval_status": "rejected", "tg_offset": offset}

        # Unclear — ask the user to clarify and keep waiting
        tg_send(
            f"🤷 I didn't quite understand your reply: <i>\"{text}\"</i>\n\n"
            f"Please reply clearly:\n"
            f"• <b>YES</b> — to build <code>{slug}</code>\n"
            f"• <b>NO</b> — to skip and pick a different project\n\n"
            f"⏰ <i>Will auto-approve if no clear answer within the remaining time.</i>"
        )

    # 1-hour timeout reached with no clear answer
    tg_send(
        f"⏰ <b>1 hour passed with no clear reply.</b>\n"
        f"Auto-approving <code>{slug}</code> and proceeding..."
    )
    return {"approval_status": "timeout", "tg_offset": offset}


def handle_rejection(state: ProjectState) -> dict:
    slug    = state["selected_project"]["slug"]
    skipped = state.get("skipped_slugs", []) + [slug]

    remaining = [
        p for p in state["available_projects"]
        if p["slug"] not in skipped
    ]

    tg_send(f"⏭ Skipped <code>{slug}</code>. Picking a new idea...")

    if not remaining:
        tg_send("⚠️ All ideas were skipped. Nothing to build today.")

    print(f"[handle_rejection] Skipped '{slug}'. {len(remaining)} ideas remaining.")
    return {"skipped_slugs": skipped}
