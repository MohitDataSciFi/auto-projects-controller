"""
Nodes: send_approval_request, wait_for_approval, handle_rejection
Handles all Telegram interaction for the YES/NO approval loop.
"""

import time
import requests
from graph.state import ProjectState

TELEGRAM_BOT_TOKEN = "***TELEGRAM_TOKEN_REDACTED***"
TELEGRAM_CHAT_ID   = "***CHAT_ID_REDACTED***"
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ── Telegram helpers ──────────────────────────────────────────────────────────

def tg_send(text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    })


def tg_get_latest_offset() -> int:
    """Return the next update_id so we only read replies AFTER this call."""
    resp = requests.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 1, "offset": -1})
    updates = resp.json().get("result", [])
    return updates[-1]["update_id"] + 1 if updates else 0


def tg_poll_reply(after_offset: int, timeout_seconds: int = 3600) -> str:
    """
    Poll Telegram for YES / NO from the user.
    Returns: 'approved' | 'rejected' | 'timeout'
    """
    deadline      = time.time() + timeout_seconds
    offset        = after_offset
    poll_interval = 30

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        print(f"[wait_for_approval] Polling Telegram... ({remaining}s remaining)")
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={
                    "offset": offset,
                    "timeout": min(poll_interval, max(remaining, 1)),
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
                text = msg.get("text", "").strip().lower()
                if text in ("yes", "y", "✅"):
                    return "approved"
                if text in ("no", "n", "❌", "skip"):
                    return "rejected"
        except Exception as e:
            print(f"[wait_for_approval] Poll error: {e}")
            time.sleep(poll_interval)

    return "timeout"


# ── Nodes ─────────────────────────────────────────────────────────────────────

def send_approval_request(state: ProjectState) -> dict:
    project = state["selected_project"]
    slug    = project["slug"]
    desc    = project["description"]
    lang    = project["language"].capitalize()

    # Capture offset BEFORE sending so we only watch replies that come AFTER
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
    print(f"[send_approval_request] Sent approval request for {slug}")
    return {"tg_offset": offset}


def wait_for_approval(state: ProjectState) -> dict:
    reply = tg_poll_reply(state["tg_offset"], timeout_seconds=3600)
    print(f"[wait_for_approval] Reply: {reply}")

    if reply == "timeout":
        tg_send(
            f"⏰ <b>No reply received.</b>\n"
            f"Auto-approving <code>{state['selected_project']['slug']}</code> and proceeding..."
        )

    return {"approval_status": reply}


def handle_rejection(state: ProjectState) -> dict:
    slug     = state["selected_project"]["slug"]
    skipped  = state.get("skipped_slugs", []) + [slug]
    remaining = [
        p for p in state["available_projects"]
        if p["slug"] not in skipped
    ]

    tg_send(f"⏭ Skipped <code>{slug}</code>. Picking a new idea...")

    if not remaining:
        tg_send("⚠️ All ideas were skipped. Nothing to build today.")

    print(f"[handle_rejection] Skipped {slug}. {len(remaining)} ideas remaining.")
    return {"skipped_slugs": skipped}
