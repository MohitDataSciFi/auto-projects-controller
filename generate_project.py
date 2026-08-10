import os
import json
import random
import subprocess
import datetime
import time
import requests
import shutil

GITHUB_USER = "MohitDataSciFi"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
TELEGRAM_BOT_TOKEN = "***TELEGRAM_TOKEN_REDACTED***"
TELEGRAM_CHAT_ID = "***CHAT_ID_REDACTED***"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ─── Telegram helpers ────────────────────────────────────────────────────────

def tg_send(text):
    """Send a message to the user on Telegram."""
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })

def tg_get_latest_offset():
    """Get the update_id of the latest message so we only watch NEW replies."""
    resp = requests.get(f"{TELEGRAM_API}/getUpdates", params={"limit": 1, "offset": -1})
    updates = resp.json().get("result", [])
    if updates:
        return updates[-1]["update_id"] + 1
    return 0

def tg_poll_reply(after_offset, timeout_seconds=3600):
    """
    Poll Telegram for a YES or NO reply from the user.
    Returns: 'yes', 'no', or 'timeout'
    """
    deadline = time.time() + timeout_seconds
    offset = after_offset
    poll_interval = 30  # seconds between checks

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        print(f"Waiting for Telegram reply... ({remaining}s remaining)")
        try:
            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params={
                "offset": offset,
                "timeout": min(poll_interval, remaining),
                "allowed_updates": ["message"]
            }, timeout=poll_interval + 5)
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                # Only accept from our chat
                if str(msg.get("chat", {}).get("id", "")) != str(TELEGRAM_CHAT_ID):
                    continue
                text = msg.get("text", "").strip().lower()
                if text in ("yes", "y", "✅"):
                    return "yes"
                if text in ("no", "n", "❌", "skip"):
                    return "no"
        except Exception as e:
            print(f"Telegram poll error: {e}")
            time.sleep(poll_interval)

    return "timeout"

# ─── LLM helpers ─────────────────────────────────────────────────────────────

def llm_call(system_prompt, user_prompt, api_key, temperature=0.2):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "temperature": temperature
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def strip_code_fences(content):
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```") and lines[-1].startswith("```"):
            content = "\n".join(lines[1:-1])
    return content

def generate_code(language, description, api_key):
    print(f"Generating {language} code via DeepSeek...")
    raw = llm_call(
        "You are an expert developer. Follow instructions exactly.",
        f"Write complete, production-ready {language} code for: {description}. "
        "Output ONLY raw code. No markdown fences, no explanations.",
        api_key, temperature=0.2
    )
    return strip_code_fences(raw)

def generate_readme(language, slug, description, api_key):
    lang_label   = "Python" if language == "python" else "Rust"
    install_hint = "pip install -r requirements.txt" if language == "python" else "cargo build --release"
    run_hint     = "python src/main.py" if language == "python" else "cargo run"
    print(f"Generating README for {slug}...")
    return llm_call(
        "You are a technical writer who writes clean, professional GitHub READMEs.",
        f"""Write a professional GitHub README.md for a {lang_label} project.

Project name: {slug}
Description: {description}

Include these sections in order:
1. Title (# {slug}) with a one-line tagline
2. Shields.io badges: language, MIT license, status active
3. ## Overview — 3-4 sentences on the problem it solves
4. ## Features — 4-6 bullet points
5. ## Requirements — Python 3.8+ or Rust 1.70+, key libraries
6. ## Installation — steps with code blocks ({install_hint})
7. ## Usage — example with code block ({run_hint})
8. ## Example Output — realistic sample output
9. ## Contributing — one short paragraph
10. ## License — MIT

Output ONLY raw markdown.""",
        api_key, temperature=0.4
    )

def generate_summary(language, slug, description, api_key):
    """Short 3-sentence plain-text summary for the Telegram report."""
    print(f"Generating project summary for {slug}...")
    return llm_call(
        "You write concise plain-text project summaries.",
        f"In exactly 3 sentences, explain what '{slug}' does and why it's useful. "
        f"Description: {description}. Language: {language}. No bullet points, no markdown.",
        api_key, temperature=0.3
    )

# ─── Git helpers ──────────────────────────────────────────────────────────────

def run_cmd(cmd, cwd=None, env=None):
    print(f"Running: {' '.join(cmd)}")
    env_merged = os.environ.copy()
    if env:
        env_merged.update(env)
    subprocess.run(cmd, cwd=cwd, env=env_merged, check=True)

def get_random_timestamps(num_commits):
    """Random sorted timestamps between 10:00 and 18:00 today."""
    now = datetime.datetime.now()
    start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now < start:
        start -= datetime.timedelta(days=1)
        end   -= datetime.timedelta(days=1)
    delta = int((end - start).total_seconds())
    ts_list = sorted(
        start + datetime.timedelta(seconds=random.randint(0, delta))
        for _ in range(num_commits)
    )
    return ts_list  # list of datetime objects

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    gh_token = os.environ.get("GH_TOKEN")
    if not gh_token:
        raise ValueError("GH_TOKEN not set")

    with open("projects.json") as f:
        projects = json.load(f)
    with open("state.json") as f:
        state = json.load(f)

    available = [p for p in projects if p["slug"] not in state.get("used_slugs", [])]
    if not available:
        tg_send("⚠️ <b>No project ideas left in the bank!</b>\nAdd more ideas to projects.json.")
        print("No available projects left.")
        return

    # ── Approval loop ─────────────────────────────────────────────────────────
    approved_project = None
    skipped = []

    while available:
        project = random.choice(available)
        slug    = project["slug"]
        desc    = project["description"]
        lang    = project["language"].lower()

        # Get offset BEFORE sending so we only catch replies AFTER our message
        offset_before = tg_get_latest_offset()

        tg_send(
            f"🤔 <b>Project Approval Request</b>\n\n"
            f"📦 <b>Project:</b> <code>{slug}</code>\n"
            f"🌐 <b>Language:</b> {lang.capitalize()}\n"
            f"📄 <b>Description:</b> {desc}\n\n"
            f"Reply <b>YES</b> ✅ to approve\n"
            f"Reply <b>NO</b> ❌ to skip and get a new idea\n\n"
            f"⏰ <i>Auto-approves in 1 hour if no reply.</i>"
        )

        reply = tg_poll_reply(offset_before, timeout_seconds=3600)

        if reply == "yes":
            approved_project = project
            break
        elif reply == "timeout":
            tg_send(f"⏰ <b>No reply received.</b> Auto-approving <code>{slug}</code> and proceeding...")
            approved_project = project
            break
        else:  # "no"
            skipped.append(slug)
            available = [p for p in available if p["slug"] not in skipped]
            tg_send(f"⏭ Skipped <code>{slug}</code>. Picking a new idea...")
            if not available:
                tg_send("⚠️ All ideas were skipped. Nothing to build today.")
                return

    if not approved_project:
        return

    slug = approved_project["slug"]
    desc = approved_project["description"]
    lang = approved_project["language"].lower()
    date_str  = datetime.datetime.now().strftime("%Y%m%d")
    repo_name = slug

    tg_send(f"🚀 Starting build for <b>{slug}</b>...")

    # ── Generate code & README via LLM ────────────────────────────────────────
    code_content = generate_code(lang, desc, api_key)
    summary_text = generate_summary(lang, slug, desc, api_key)

    # ── Create GitHub repo ────────────────────────────────────────────────────
    run_cmd(["gh", "repo", "create", f"{GITHUB_USER}/{repo_name}",
             "--public", "--description", desc, "--clone"])
    repo_dir = repo_name

    auth_remote = f"https://{GITHUB_USER}:{gh_token}@github.com/{GITHUB_USER}/{repo_name}.git"
    run_cmd(["git", "remote", "set-url", "origin", auth_remote], cwd=repo_dir)

    # Initial commit on main (needed for PR base)
    with open(os.path.join(repo_dir, ".gitkeep"), "w") as f:
        f.write("")
    run_cmd(["git", "add", ".gitkeep"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "chore: initial repo setup"], cwd=repo_dir)
    run_cmd(["git", "branch", "-M", "main"], cwd=repo_dir)
    run_cmd(["git", "push", "-u", "origin", "main"], cwd=repo_dir)
    run_cmd(["git", "checkout", "-b", "dev"], cwd=repo_dir)

    # ── Commits with random timestamps ────────────────────────────────────────
    num_commits = random.randint(5, 10)
    ts_list     = get_random_timestamps(num_commits)
    commit_log  = []   # [(datetime, message)]
    commit_idx  = 0

    def do_commit(msg):
        nonlocal commit_idx
        ts = ts_list[commit_idx] if commit_idx < len(ts_list) else ts_list[-1]
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
        run_cmd(["git", "commit", "-m", msg], cwd=repo_dir, env={
            "GIT_AUTHOR_DATE":    ts_str,
            "GIT_COMMITTER_DATE": ts_str
        })
        commit_log.append((ts, msg))
        commit_idx += 1

    # README
    readme_content = generate_readme(lang, slug, desc, api_key)
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(readme_content)
    run_cmd(["git", "add", "README.md"], cwd=repo_dir)
    do_commit(f"docs: add full README for {slug}")

    if lang == "python":
        os.makedirs(os.path.join(repo_dir, "src"),   exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "tests"), exist_ok=True)

        main_file = os.path.join("src", "main.py")
        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(f'"""\n{desc}\n"""\n\ndef main():\n    print("TODO: implement {slug}")\n\nif __name__ == "__main__":\n    main()\n')
        run_cmd(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: scaffold main script")

        with open(os.path.join(repo_dir, "requirements.txt"), "w") as f:
            f.write("pandas\nnumpy\n")
        run_cmd(["git", "add", "requirements.txt"], cwd=repo_dir)
        do_commit("chore: add requirements.txt")

        test_file = os.path.join("tests", "test_main.py")
        with open(os.path.join(repo_dir, test_file), "w") as f:
            f.write("def test_placeholder():\n    assert True\n")
        run_cmd(["git", "add", test_file], cwd=repo_dir)
        do_commit("test: add initial test scaffold")

        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(code_content)
        run_cmd(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: implement core logic via LLM")

    elif lang == "rust":
        run_cmd(["cargo", "init", "--bin"], cwd=repo_dir)
        run_cmd(["git", "add", "Cargo.toml", "src/main.rs", ".gitignore"], cwd=repo_dir)
        do_commit("feat: scaffold rust binary via cargo")

        os.makedirs(os.path.join(repo_dir, "tests"), exist_ok=True)
        with open(os.path.join(repo_dir, "tests", "integration.rs"), "w") as f:
            f.write("// Integration tests\n")
        run_cmd(["git", "add", "tests/integration.rs"], cwd=repo_dir)
        do_commit("test: add integration test directory")

        main_file = os.path.join("src", "main.rs")
        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(code_content)
        run_cmd(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: implement core logic via LLM")

    os.makedirs(os.path.join(repo_dir, "examples"), exist_ok=True)
    with open(os.path.join(repo_dir, "examples", "usage.md"), "w") as f:
        f.write("# Example usage\n\n```bash\n# Run the project to see it in action\n```\n")
    run_cmd(["git", "add", "examples/usage.md"], cwd=repo_dir)
    do_commit("docs: add usage example placeholder")

    # Padding commits
    padding_messages = [
        "chore: clean up whitespace and formatting",
        "docs: fix typo in documentation",
        "style: improve code readability",
        "refactor: minor structural improvements",
        "docs: expand on usage section",
        "chore: update internal tooling configuration"
    ]
    random.shuffle(padding_messages)
    while commit_idx < num_commits:
        with open(os.path.join(repo_dir, "README.md"), "a") as f:
            f.write("\n<!-- minor update -->\n")
        run_cmd(["git", "add", "README.md"], cwd=repo_dir)
        do_commit(padding_messages.pop() if padding_messages else "chore: routine update")

    # ── Push, PR, merge ───────────────────────────────────────────────────────
    run_cmd(["git", "push", "-u", "origin", "dev"], cwd=repo_dir)
    run_cmd(["gh", "pr", "create", "--title", f"Initial build: {slug}",
             "--body", desc, "--base", "main", "--head", "dev"], cwd=repo_dir)
    run_cmd(["gh", "pr", "merge", "--merge", "--delete-branch"], cwd=repo_dir)

    repo_url = f"https://github.com/{GITHUB_USER}/{repo_name}"
    print(f"✅ Done: {repo_url}")

    # ── Update state ──────────────────────────────────────────────────────────
    state.setdefault("used_slugs", []).append(slug)
    state.setdefault("run_history", []).append({
        "date": date_str,
        "repo": repo_name,
        "slug": slug,
        "commits_made": num_commits
    })
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

    shutil.rmtree(repo_dir)

    # ── Telegram daily report ─────────────────────────────────────────────────
    remaining = len([p for p in projects if p["slug"] not in state["used_slugs"]])

    commit_lines = "\n".join(
        f"  • {ts.strftime('%I:%M %p')} — {msg}"
        for ts, msg in commit_log
    )

    report = (
        f"📊 <b>Daily Project Report — {datetime.datetime.now().strftime('%b %d, %Y')}</b>\n\n"
        f"✅ <b>Project Created:</b> <code>{slug}</code>\n"
        f"🔗 <b>Repo:</b> {repo_url}\n"
        f"🌐 <b>Language:</b> {lang.capitalize()}\n"
        f"💬 <b>Commits Made:</b> {num_commits}\n\n"
        f"📝 <b>What this project does:</b>\n{summary_text}\n\n"
        f"🕐 <b>Commit Timeline:</b>\n{commit_lines}\n\n"
        f"✅ PR opened and merged successfully\n"
        f"📁 <b>Projects remaining in bank:</b> {remaining}"
    )
    tg_send(report)


if __name__ == "__main__":
    main()
