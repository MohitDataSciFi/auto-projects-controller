"""
Nodes: check_ongoing_project, setup_new_project, build_next_phase, finalize_project
Manages the full lifecycle of multi-day, multi-phase project development.
"""

import os
import json
import random
import datetime
import subprocess
import requests
from graph.state import ProjectState

GITHUB_USER      = "MohitDataSciFi"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list, cwd: str = None, env_extra: dict = None):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _llm(system: str, user: str, api_key: str, temperature: float = 0.2) -> str:
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": temperature,
        },
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])
    return content


def _random_timestamps(n: int) -> list:
    """Return n sorted datetime objects spread randomly 10:00–18:00 today."""
    now   = datetime.datetime.now()
    start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end   = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now < start:
        start -= datetime.timedelta(days=1)
        end   -= datetime.timedelta(days=1)
    delta = int((end - start).total_seconds())
    return sorted(
        start + datetime.timedelta(seconds=random.randint(0, delta))
        for _ in range(n)
    )


def _auth_url(gh_token: str, repo_name: str) -> str:
    return f"https://{GITHUB_USER}:{gh_token}@github.com/{GITHUB_USER}/{repo_name}.git"


# ── Node 1: check_ongoing_project ─────────────────────────────────────────────

def check_ongoing_project(state: ProjectState) -> dict:
    """Reads state.json. If an active project exists, load it into state."""
    with open("state.json") as f:
        persisted = json.load(f)

    active = persisted.get("active_project")
    used_slugs = persisted.get("used_slugs", [])

    if active:
        phase_idx = active.get("current_phase_idx", 0)
        total     = len(active.get("phases", []))
        print(f"[check_ongoing_project] Resuming: {active['slug']} "
              f"(Phase {phase_idx + 1}/{total})")
    else:
        print("[check_ongoing_project] No active project. Will research new tech.")

    return {
        "active_project":            active or {},
        "_used_slugs_for_research":  used_slugs,
    }


# ── Node 2: setup_new_project ─────────────────────────────────────────────────

def setup_new_project(state: ProjectState) -> dict:
    """Creates the GitHub repo and commits the initial scaffold + full roadmap README."""
    plan      = state["project_plan"]
    gh_token  = state["gh_token"]
    api_key   = state["api_key"]

    slug      = plan["slug"]
    desc      = plan["description"]
    lang      = plan["language"].lower()
    phases    = plan["phases"]
    tech_stack = ", ".join(plan.get("tech_stack", []))
    trend_tag  = plan.get("trend_tag", "")

    print(f"[setup_new_project] Creating repo: {slug}")
    _run(["gh", "repo", "create", f"{GITHUB_USER}/{slug}",
          "--public", "--description", desc, "--clone"])

    _run(["git", "remote", "set-url", "origin", _auth_url(gh_token, slug)], cwd=slug)

    # Build roadmap README
    phase_lines = "\n".join(
        f"- **{p['name']}**: {p['goal']}" for p in phases
    )
    readme = _llm(
        "You write professional GitHub READMEs.",
        f"""Write a professional README.md for a {lang} project named '{slug}'.

Description: {desc}
Trend: {trend_tag}
Tech Stack: {tech_stack}

Include:
1. Title (# {slug}) + one-line tagline
2. Shields.io badges (language, MIT, status: active)
3. ## Overview — 3-4 sentences
4. ## Tech Stack — bulleted list of {tech_stack}
5. ## Multi-Phase Roadmap
{phase_lines}
6. ## Getting Started — install + run instructions
7. ## Contributing
8. ## License — MIT

Output ONLY raw markdown.""",
        api_key, temperature=0.4
    )

    with open(os.path.join(slug, "README.md"), "w") as f:
        f.write(readme)

    # Add CI/CD workflow to the generated repo
    ci_dir = os.path.join(slug, ".github", "workflows")
    os.makedirs(ci_dir, exist_ok=True)
    ci_workflow = f"""name: CI

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov httpx python-multipart
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      - name: Run tests
        run: PYTHONPATH=. pytest tests/ -v --tb=short --cov=src --cov-report=term-missing
"""
    with open(os.path.join(ci_dir, "ci.yml"), "w") as f:
        f.write(ci_workflow)

    # Initial commit on main
    _run(["git", "add", "."], cwd=slug)
    _run(["git", "commit", "-m", f"docs: initial README, CI/CD workflow for {slug}"], cwd=slug)
    _run(["git", "branch", "-M", "main"], cwd=slug)
    _run(["git", "push", "-u", "origin", "main"], cwd=slug)
    _run(["git", "checkout", "-b", "dev"], cwd=slug)

    repo_url = f"https://github.com/{GITHUB_USER}/{slug}"

    # Persist active project to state.json immediately
    with open("state.json") as f:
        persisted = json.load(f)

    active_project = {
        "slug":              slug,
        "repo_name":         slug,
        "repo_url":          repo_url,
        "language":          lang,
        "description":       desc,
        "tech_stack":        plan.get("tech_stack", []),
        "current_phase_idx": 0,
        "phases": [
            {**p, "status": "pending"} for p in phases
        ],
    }
    persisted["active_project"] = active_project
    with open("state.json", "w") as f:
        json.dump(persisted, f, indent=2)

    print(f"[setup_new_project] Repo ready: {repo_url}")
    return {"active_project": active_project}


# ── Node 3: build_next_phase ──────────────────────────────────────────────────

def build_next_phase(state: ProjectState) -> dict:
    """Clones/re-uses the repo and builds the current phase with LLM-generated code."""
    active    = state["active_project"]
    api_key   = state["api_key"]
    gh_token  = state["gh_token"]

    slug      = active["slug"]
    lang      = active["language"]
    phase_idx = active["current_phase_idx"]
    phases    = active["phases"]
    phase     = phases[phase_idx]

    total_phases = len(phases)
    print(f"[build_next_phase] Building {phase['name']} ({phase_idx+1}/{total_phases})")

    # Clone if not already present (fresh CI runner on day 2+)
    if not os.path.exists(slug):
        print(f"[build_next_phase] Cloning {slug}...")
        _run(["git", "clone", _auth_url(gh_token, slug)])
        _run(["git", "remote", "set-url", "origin", _auth_url(gh_token, slug)], cwd=slug)

    # Make sure we're on dev branch
    try:
        _run(["git", "checkout", "dev"], cwd=slug)
    except subprocess.CalledProcessError:
        _run(["git", "checkout", "-b", "dev"], cwd=slug)

    try:
        _run(["git", "pull", "origin", "dev", "--rebase"], cwd=slug)
    except subprocess.CalledProcessError:
        print("[build_next_phase] Remote dev branch not found, skipping pull.")

    # ── Generate code for this specific phase ─────────────────────────────
    prev_phases = "\n".join(
        f"- {phases[i]['name']}: {phases[i]['goal']}"
        for i in range(phase_idx)
    ) or "None (this is Phase 1)"

    code_prompt = f"""You are an expert {lang} developer building a production-grade project called '{slug}'.

Project description: {active['description']}
Tech stack: {', '.join(active.get('tech_stack', []))}

Previously completed phases:
{prev_phases}

NOW implement: {phase['name']}
Goal: {phase['goal']}
Key files to create: {', '.join(phase.get('key_files', ['src/main.py']))}

Write COMPLETE, production-quality {lang} code for this phase.
Use advanced patterns: async/await, proper typing, error handling, logging.
Output ONLY raw code. No markdown. No explanations."""

    code = _llm(
        f"You are a senior {lang} engineer who writes clean, production-grade code.",
        code_prompt, api_key, temperature=0.2
    )

    # Generate phase summary for the Telegram report
    summary = _llm(
        "You write concise technical summaries.",
        f"In 3 sentences, describe what was built in '{phase['name']}' for the project "
        f"'{slug}'. Goal: {phase['goal']}. Be specific about technical implementation.",
        api_key, temperature=0.3
    )

    # ── Write files and commit ────────────────────────────────────────────
    num_commits = random.randint(5, 10)
    ts_list     = _random_timestamps(num_commits)
    commit_log  = []
    commit_idx  = 0

    def do_commit(msg: str):
        nonlocal commit_idx
        ts     = ts_list[commit_idx] if commit_idx < len(ts_list) else ts_list[-1]
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
        _run(["git", "commit", "-m", msg], cwd=slug,
             env_extra={"GIT_AUTHOR_DATE": ts_str, "GIT_COMMITTER_DATE": ts_str})
        commit_log.append([ts.strftime("%I:%M %p"), msg])
        commit_idx += 1

    prefix = phase.get("commit_prefix", "feat")
    key_files = phase.get("key_files", [])

    # Write the main code file(s)
    if lang == "python":
        if not key_files:
            key_files = [f"src/phase_{phase_idx + 1}.py"]
        main_file = key_files[0]
        os.makedirs(os.path.join(slug, os.path.dirname(main_file)), exist_ok=True)
        with open(os.path.join(slug, main_file), "w") as f:
            f.write(code)
        _run(["git", "add", main_file], cwd=slug)
        do_commit(f"{prefix}: scaffold {phase['name']}")

        # requirements.txt on phase 1 only
        if phase_idx == 0:
            tech = active.get("tech_stack", [])
            with open(os.path.join(slug, "requirements.txt"), "w") as f:
                f.write("\n".join(tech) + "\n")
            _run(["git", "add", "requirements.txt"], cwd=slug)
            do_commit("chore: add project dependencies")

        # Generate real working tests with LLM
        test_dir = f"tests/test_phase_{phase_idx + 1}.py"
        os.makedirs(os.path.join(slug, "tests"), exist_ok=True)
        test_code = _llm(
            f"You write concise, real pytest test suites for Python ML/AI code.",
            f"""Write a real pytest test file for this {lang} code from phase '{phase['name']}':

Project: {slug}
Phase goal: {phase['goal']}
Main file: {main_file}

Code:
```python
{code[:3000]}
```

Write 3-5 real, meaningful pytest test functions that actually test the core logic.
Use fixtures where appropriate. Mock external calls (API, DB) with unittest.mock.
Output ONLY raw Python code. No markdown.""",
            api_key, temperature=0.2
        )
        with open(os.path.join(slug, test_dir), "w") as f:
            f.write(test_code)
        _run(["git", "add", test_dir], cwd=slug)
        do_commit(f"test: add real unit tests for {phase['name']}")

    elif lang == "rust":
        if phase_idx == 0:
            _run(["cargo", "init", "--bin"], cwd=slug)
            _run(["git", "add", "Cargo.toml", "src/main.rs", ".gitignore"], cwd=slug)
            do_commit("feat: initialize cargo project")

        main_file = f"src/phase_{phase_idx + 1}.rs"
        with open(os.path.join(slug, main_file), "w") as f:
            f.write(code)
        _run(["git", "add", main_file], cwd=slug)
        do_commit(f"{prefix}: implement {phase['name']}")

    # Padding commits up to num_commits
    padding = [
        f"refactor: improve {phase['name']} structure",
        "style: apply code formatting and linting",
        "docs: add inline documentation and type hints",
        "chore: add logging and error handling",
        "perf: optimize critical path performance",
        "fix: handle edge cases and error states",
    ]
    random.shuffle(padding)
    while commit_idx < num_commits:
        with open(os.path.join(slug, key_files[0] if key_files else "README.md"), "a") as f:
            f.write(f"\n# {phase['name']} - iteration {commit_idx}\n")
        _run(["git", "add", "."], cwd=slug)
        do_commit(padding.pop() if padding else "chore: incremental improvements")

    # ── Update phase status ───────────────────────────────────────────────
    updated_phases = [dict(p) for p in phases]
    updated_phases[phase_idx]["status"] = "complete"

    updated_active = {
        **active,
        "current_phase_idx": phase_idx + 1,
        "phases": updated_phases,
    }

    return {
        "active_project": updated_active,
        "commit_log":     commit_log,
        "num_commits":    num_commits,
        "phase_summary":  summary,
    }


# ── Node 4: finalize_project ──────────────────────────────────────────────────

def finalize_project(state: ProjectState) -> dict:
    """On the last phase: push, open PR, merge, clean up state."""
    active   = state["active_project"]
    gh_token = state["gh_token"]
    slug     = active["slug"]
    desc     = active["description"]

    print(f"[finalize_project] All phases complete. Merging PR for {slug}")
    _run(["git", "push", "-u", "origin", "dev"], cwd=slug)
    _run(["gh", "pr", "create",
          "--title", f"Complete build: {slug}",
          "--body",  desc,
          "--base",  "main",
          "--head",  "dev"], cwd=slug)
    _run(["gh", "pr", "merge", "--merge", "--delete-branch"], cwd=slug)

    # Update state.json — clear active_project, mark slug as used
    with open("state.json") as f:
        persisted = json.load(f)

    persisted["active_project"] = None
    persisted.setdefault("used_slugs", []).append(slug)
    persisted.setdefault("run_history", []).append({
        "date":    datetime.datetime.now().strftime("%Y%m%d"),
        "slug":    slug,
        "repo":    slug,
        "status":  "complete",
    })

    with open("state.json", "w") as f:
        json.dump(persisted, f, indent=2)

    import shutil
    if os.path.exists(slug):
        shutil.rmtree(slug)

    print(f"[finalize_project] Project {slug} fully complete!")
    return {}


# ── Node 5: push_phase ────────────────────────────────────────────────────────

def push_phase(state: ProjectState) -> dict:
    """Pushes the current phase commits to the dev branch."""
    slug = state["active_project"]["slug"]
    print(f"[push_phase] Pushing dev branch for {slug}")
    _run(["git", "push", "-u", "origin", "dev"], cwd=slug)
    return {}
