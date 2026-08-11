"""
Standalone script: weekly_report.py
Runs every Sunday via GitHub Actions.
Sends a comprehensive JARVIS-style weekly summary to Telegram
covering all projects built, total commits, skills progressed,
and curriculum advancement for the week.
"""

import os
import json
import datetime
import requests

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GITHUB_USER        = "MohitDataSciFi"
GITHUB_API         = "https://api.github.com"


def tg_send(text: str):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    })


def get_week_commits(gh_token: str, repo: str) -> int:
    """Count commits in the last 7 days for a repo."""
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat() + "Z"
    resp  = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_USER}/{repo}/commits",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"},
        params={"since": since, "per_page": 100},
    )
    if resp.status_code == 200:
        return len(resp.json())
    return 0


def main():
    gh_token = os.environ.get("GH_TOKEN", "")

    with open("state.json") as f:
        state_data = json.load(f)
    with open("curriculum.json") as f:
        curriculum = json.load(f)

    run_history      = state_data.get("run_history", [])
    curriculum_state = state_data.get("curriculum_state", {})
    topics           = curriculum["topics"]

    # Filter runs from this week
    today     = datetime.datetime.now()
    week_ago  = today - datetime.timedelta(days=7)
    week_runs = [
        r for r in run_history
        if datetime.datetime.strptime(str(r.get("date", "20000101")), "%Y%m%d") >= week_ago
    ]

    total_projects = len(week_runs)
    total_slugs    = len(state_data.get("used_slugs", []))

    # Count total commits this week across all new repos
    total_commits = 0
    if gh_token:
        for r in week_runs:
            total_commits += get_week_commits(gh_token, r.get("slug", r.get("repo", "")))

    # Curriculum position
    topic_order = curriculum_state.get("topic_order", 1)
    level       = curriculum_state.get("level", 1)
    week_number = curriculum_state.get("week_number", 1)
    current_topic = next((t for t in topics if t["order"] == topic_order), topics[0])

    # Projects this week
    project_lines = "\n".join(
        f"  ▸ <code>{r.get('slug', r.get('repo', 'unknown'))}</code>"
        for r in week_runs
    ) or "  ▸ No projects this week"

    # Topics completed (fully done)
    topics_completed = topic_order - 1

    # Overall progress
    overall_done  = topics_completed * 7 + curriculum_state.get("projects_done_in_topic", 0)
    overall_total = len(topics) * 7
    pct = round((overall_done / overall_total) * 100) if overall_total > 0 else 0
    bar_filled = round(pct / 10)
    progress_bar = "▓" * bar_filled + "░" * (10 - bar_filled)

    today_str = today.strftime("%b %d, %Y").upper()

    report = (
        f"📡 <b>WEEKLY INTELLIGENCE REPORT — {today_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>WEEK {week_number} STATISTICS</b>\n"
        f"◈ Projects Built: <b>{total_projects}</b>\n"
        f"◈ Total Commits: <b>{total_commits}</b>\n"
        f"◈ Lifetime Projects: <b>{total_slugs}</b>\n\n"
        f"📚 <b>CURRICULUM STATUS</b>\n"
        f"◈ Current Topic: <b>{current_topic['name']}</b>\n"
        f"◈ Level: <b>{level}/7</b>\n"
        f"◈ Topics Mastered: <b>{topics_completed}/{len(topics)}</b>\n\n"
        f"📈 <b>OVERALL PROGRESS</b>\n"
        f"[{progress_bar}] {pct}% ({overall_done}/{overall_total})\n\n"
        f"🚀 <b>PROJECTS THIS WEEK</b>\n"
        f"{project_lines}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href=\"https://github.com/{GITHUB_USER}\">View Portfolio on GitHub</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    tg_send(report)
    print("✅ Weekly report sent.")


if __name__ == "__main__":
    main()
