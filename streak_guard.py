"""
Standalone script: streak_guard.py
Emergency fallback — runs if main.py fails.
Makes 1-2 small maintenance commits to the most recent repo
to keep the GitHub contribution streak alive.
"""

import os
import json
import datetime
import subprocess
import requests

GITHUB_USER        = "MohitDataSciFi"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def tg_send(text: str):
    if not TELEGRAM_BOT_TOKEN:
        return
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    })


def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    gh_token = os.environ.get("GH_TOKEN", "")
    error_msg = os.environ.get("MAIN_ERROR", "Unknown error")

    # Send error alert immediately
    today = datetime.datetime.now().strftime("%b %d, %Y — %H:%M UTC")
    tg_send(
        f"⚠️ <b>SYSTEM ALERT — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❌ <b>Main automation failed!</b>\n\n"
        f"<b>Error:</b>\n<code>{error_msg[:500]}</code>\n\n"
        f"🛡️ <b>Streak Guard activated.</b>\n"
        f"Making maintenance commits to preserve contribution streak..."
    )

    with open("state.json") as f:
        state_data = json.load(f)

    run_history = state_data.get("run_history", [])
    if not run_history:
        tg_send("⚠️ No previous repos found. Streak Guard cannot act.")
        return

    # Find most recent repo
    recent = run_history[-1]
    slug   = recent.get("slug", recent.get("repo", ""))
    if not slug:
        tg_send("⚠️ Could not determine repo name. Streak Guard exiting.")
        return

    auth_url = f"https://{GITHUB_USER}:{gh_token}@github.com/{GITHUB_USER}/{slug}.git"

    try:
        run(["git", "clone", auth_url, slug])
        run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=slug)
        run(["git", "config", "user.name", "github-actions[bot]"], cwd=slug)

        # Make a small maintenance commit
        with open(os.path.join(slug, "MAINTENANCE.md"), "w") as f:
            f.write(
                f"# Maintenance Log\n\n"
                f"Last maintenance: {datetime.datetime.now().isoformat()}\n\n"
                f"This file tracks automated maintenance runs.\n"
            )

        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        run(["git", "add", "MAINTENANCE.md"], cwd=slug)
        run(["git", "commit", "-m", "chore: automated maintenance update",
             f"--date={ts}"], cwd=slug)
        run(["git", "push", "origin", "HEAD"], cwd=slug)

        tg_send(
            f"✅ <b>Streak Guard complete.</b>\n"
            f"Maintenance commit pushed to <code>{slug}</code>.\n"
            f"Your contribution streak is preserved. 🟩"
        )

    except Exception as e:
        tg_send(f"❌ <b>Streak Guard also failed:</b>\n<code>{str(e)[:300]}</code>")


if __name__ == "__main__":
    main()
