"""
Nodes: send_daily_progress_report
JARVIS-style Telegram progress report with phase status, commit timeline,
build summary, and progress bar.
"""

import os
import json
import datetime
import requests
from graph.state import ProjectState

def _bot_token(): return os.environ["TELEGRAM_BOT_TOKEN"]
def _chat_id():   return os.environ["TELEGRAM_CHAT_ID"]
def _api_url():   return f"https://api.telegram.org/bot{_bot_token()}"


def _tg_send(text: str):
    requests.post(f"{_api_url()}/sendMessage", json={
        "chat_id":    _chat_id(),
        "text":       text,
        "parse_mode": "HTML",
    })


def _progress_bar(current: int, total: int, width: int = 10) -> str:
    filled = round((current / total) * width)
    bar    = "▓" * filled + "░" * (width - filled)
    pct    = round((current / total) * 100)
    return f"{bar} {pct}%"


def send_daily_progress_report(state: ProjectState) -> dict:
    active       = state["active_project"]
    commit_log   = state.get("commit_log", [])
    phase_summary = state.get("phase_summary", "")

    slug         = active["slug"]
    repo_url     = active["repo_url"]
    phases       = active["phases"]
    phase_idx    = active["current_phase_idx"]   # already incremented
    total_phases = len(phases)
    completed    = phase_idx                       # phases done so far
    prev_phase   = phases[phase_idx - 1]           # the one we just built

    today = datetime.datetime.now().strftime("%b %d, %Y").upper()

    commit_lines = "\n".join(
        f"  {t} · {msg}" for t, msg in commit_log
    )

    progress = _progress_bar(completed, total_phases)

    if completed < total_phases:
        next_phase_info = (
            f"\n⏭ <b>NEXT:</b> {phases[phase_idx]['name']} (tomorrow)\n"
        )
        status_line = f"◈ <b>Status:</b> {completed}/{total_phases} phases complete"
    else:
        next_phase_info = "\n🎉 <b>ALL PHASES COMPLETE — Project finalized!</b>\n"
        status_line = "◈ <b>Status:</b> ✅ FULLY COMPLETE"

    report = (
        f"📡 <b>BUILD PROGRESS REPORT — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 <b>Project:</b> <code>{slug}</code>\n"
        f"🔗 <b>Repo:</b> {repo_url}\n"
        f"{status_line}\n\n"
        f"✅ <b>Phase Completed:</b>\n"
        f"   {prev_phase['name']}\n\n"
        f"📝 <b>Build Summary:</b>\n"
        f"{phase_summary}\n\n"
        f"🕐 <b>Commit Timeline:</b>\n"
        f"{commit_lines}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Overall Progress:</b> {progress}"
        f"{next_phase_info}"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    _tg_send(report)
    print(f"[send_daily_progress_report] Report sent for phase {completed}/{total_phases}")
    return {}
