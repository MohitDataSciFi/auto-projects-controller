"""
Nodes: update_state, send_report
Saves progress to state.json and sends the Telegram daily report.
"""

import json
import shutil
import datetime
import requests
from graph.state import ProjectState

TELEGRAM_BOT_TOKEN = "***TELEGRAM_TOKEN_REDACTED***"
TELEGRAM_CHAT_ID   = "***CHAT_ID_REDACTED***"
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _tg_send(text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    })


# ── Node 1: update_state ──────────────────────────────────────────────────────

def update_state(state: ProjectState) -> dict:
    slug      = state["selected_project"]["slug"]
    repo_name = state["repo_name"]
    date_str  = datetime.datetime.now().strftime("%Y%m%d")

    with open("state.json") as f:
        persisted = json.load(f)

    persisted.setdefault("used_slugs", []).append(slug)
    persisted.setdefault("run_history", []).append({
        "date":         date_str,
        "repo":         repo_name,
        "slug":         slug,
        "commits_made": state["num_commits"],
        "repo_url":     state["repo_url"],
    })

    with open("state.json", "w") as f:
        json.dump(persisted, f, indent=2)

    # Clean up the locally cloned repo directory
    if os.path.exists(repo_name):
        shutil.rmtree(repo_name)

    print(f"[update_state] state.json updated. Cleaned up {repo_name}/")
    return {}


# ── Node 2: send_report ───────────────────────────────────────────────────────

def send_report(state: ProjectState) -> dict:
    slug        = state["selected_project"]["slug"]
    lang        = state["selected_project"]["language"].capitalize()
    repo_url    = state["repo_url"]
    num_commits = state["num_commits"]
    summary     = state["summary_text"]
    commit_log  = state["commit_log"]   # [[time_str, message], ...]
    date_label  = datetime.datetime.now().strftime("%b %d, %Y")

    # Count remaining ideas
    with open("projects.json") as f:
        all_projects = json.load(f)
    with open("state.json") as f:
        persisted = json.load(f)
    used    = set(persisted.get("used_slugs", []))
    remaining = len([p for p in all_projects if p["slug"] not in used])

    commit_lines = "\n".join(
        f"  • {time_str} — {msg}"
        for time_str, msg in commit_log
    )

    report = (
        f"📊 <b>Daily Project Report — {date_label}</b>\n\n"
        f"✅ <b>Project Created:</b> <code>{slug}</code>\n"
        f"🔗 <b>Repo:</b> {repo_url}\n"
        f"🌐 <b>Language:</b> {lang}\n"
        f"💬 <b>Commits Made:</b> {num_commits}\n\n"
        f"📝 <b>What this project does:</b>\n{summary}\n\n"
        f"🕐 <b>Commit Timeline:</b>\n{commit_lines}\n\n"
        f"✅ PR opened and merged successfully\n"
        f"📁 <b>Projects remaining in bank:</b> {remaining}"
    )

    _tg_send(report)
    print(f"[send_report] Daily report sent to Telegram.")
    return {}


# Fix missing import
import os
