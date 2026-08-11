"""
Nodes: send_plan_to_user, wait_for_plan_approval, handle_plan_rejection
JARVIS-style Telegram approval flow with LLM reply interpretation.
"""

import os
import time
import requests
from graph.state import ProjectState

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# Credentials injected via GitHub Secrets / env vars
def _bot_token(): return os.environ["TELEGRAM_BOT_TOKEN"]
def _chat_id():   return os.environ["TELEGRAM_CHAT_ID"]
def _api_url():   return f"https://api.telegram.org/bot{_bot_token()}"


# ── Telegram helpers ──────────────────────────────────────────────────────────

def tg_send(text: str):
    requests.post(f"{_api_url()}/sendMessage", json={
        "chat_id":    _chat_id(),
        "text":       text,
        "parse_mode": "HTML",
    })


def tg_get_latest_offset() -> int:
    resp    = requests.get(f"{_api_url()}/getUpdates", params={"limit": 1, "offset": -1})
    updates = resp.json().get("result", [])
    return updates[-1]["update_id"] + 1 if updates else 0


# ── LLM reply interpreter ─────────────────────────────────────────────────────

def _interpret_reply(user_text: str, slug: str, api_key: str) -> str:
    """Returns: 'approved' | 'rejected' | 'unclear'"""
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You classify user intent as APPROVED, REJECTED, or UNCLEAR."},
                {"role": "user",   "content":
                    f"A user was asked to approve building a project called '{slug}'.\n"
                    f"They replied: \"{user_text}\"\n\n"
                    f"APPROVED = they want to proceed (yes, sure, ok, go ahead, do it, build it, sounds good, etc.)\n"
                    f"REJECTED = they want to skip (no, nope, skip, next, don't, pass, cancel, etc.)\n"
                    f"UNCLEAR = ambiguous or unrelated\n\n"
                    f"Reply with ONLY one word: APPROVED, REJECTED, or UNCLEAR."
                },
            ],
            "temperature": 0.0,
        },
    )
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
    if "APPROVED" in answer: return "approved"
    if "REJECTED" in answer: return "rejected"
    return "unclear"


def _poll_one_reply(after_offset: int, wait_seconds: int) -> tuple:
    offset   = after_offset
    deadline = time.time() + wait_seconds
    interval = 30
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        try:
            resp = requests.get(f"{_api_url()}/getUpdates", params={
                "offset": offset, "timeout": min(interval, max(remaining, 1)),
                "allowed_updates": ["message"],
            }, timeout=interval + 5)
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                msg    = update.get("message", {})
                if str(msg.get("chat", {}).get("id", "")) != str(_chat_id()):
                    continue
                text = msg.get("text", "").strip()
                if text:
                    return offset, text
        except Exception as e:
            print(f"[poll] Error: {e}")
            time.sleep(interval)
    return offset, None


# ── Nodes ─────────────────────────────────────────────────────────────────────

def send_plan_to_user(state: ProjectState) -> dict:
    plan = state["project_plan"]
    slug      = plan["slug"]
    lang      = plan["language"].capitalize()
    duration  = plan["duration_days"]
    tech      = " · ".join(plan.get("tech_stack", []))
    trend     = plan.get("trend_tag", "")
    complexity = plan.get("complexity", "Advanced")
    phases    = plan.get("phases", [])

    phase_lines = "\n".join(
        f"  [DAY {i+1}] {p['name']}"
        for i, p in enumerate(phases)
    )

    import datetime
    today = datetime.datetime.now().strftime("%b %d, %Y").upper()

    offset = tg_get_latest_offset()

    tg_send(
        f"⚡ <b>SYSTEM RESEARCH REPORT — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔬 <b>TREND IDENTIFIED</b>\n"
        f"{trend}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>PROJECT PROPOSAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"◈ <b>Name:</b> <code>{slug}</code>\n"
        f"◈ <b>Language:</b> {lang}\n"
        f"◈ <b>Duration:</b> {duration} Days\n"
        f"◈ <b>Complexity:</b> {complexity}\n\n"
        f"🔬 <b>Tech Stack:</b>\n"
        f"  ▸ {tech}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📐 <b>PHASE BREAKDOWN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{phase_lines}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Authorization required.\n"
        f"Reply <b>YES</b> ✅ to initiate build sequence\n"
        f"Reply <b>NO</b> ❌ to discard and research a new target\n"
        f"⏱ <i>Auto-initiates in 1 hour if no response received.</i>"
    )

    print(f"[send_plan_to_user] Plan sent for '{slug}'")
    return {"tg_offset": offset}


def wait_for_plan_approval(state: ProjectState) -> dict:
    api_key  = state["api_key"]
    slug     = state["project_plan"]["slug"]
    offset   = state["tg_offset"]
    deadline = time.time() + 3600

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            break
        print(f"[wait_for_plan_approval] Waiting for reply... ({remaining}s left)")
        offset, text = _poll_one_reply(offset, wait_seconds=min(300, remaining))

        if text is None:
            continue

        intent = _interpret_reply(text, slug, api_key)

        if intent == "approved":
            return {"approval_status": "approved", "tg_offset": offset}
        if intent == "rejected":
            return {"approval_status": "rejected", "tg_offset": offset}

        # Unclear — ask again
        tg_send(
            f"🤷 <b>Unclear response detected:</b> <i>\"{text}\"</i>\n\n"
            f"Please clarify:\n"
            f"◈ <b>YES</b> — Authorize build of <code>{slug}</code>\n"
            f"◈ <b>NO</b> — Discard and search a new target\n\n"
            f"⏱ <i>Auto-initiates if no clear response within remaining time.</i>"
        )

    tg_send(
        f"⏱ <b>TIMEOUT REACHED.</b>\n"
        f"No clear authorization received. Auto-initiating build of <code>{slug}</code>..."
    )
    return {"approval_status": "timeout", "tg_offset": offset}


def handle_plan_rejection(state: ProjectState) -> dict:
    slug = state["project_plan"]["slug"]
    tg_send(
        f"❌ <b>PROPOSAL REJECTED:</b> <code>{slug}</code>\n"
        f"Initiating new research scan..."
    )
    print(f"[handle_plan_rejection] Plan for '{slug}' rejected. Re-researching.")
    return {}
