"""
Nodes: create_repo, scaffold_project, push_and_merge_pr
Handles all GitHub and git operations.
"""

import os
import random
import datetime
import subprocess
from graph.state import ProjectState

GITHUB_USER = "MohitDataSciFi"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list, cwd: str = None, env_extra: dict = None):
    print(f"  $ {' '.join(cmd)}")
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _random_timestamps(n: int) -> list:
    """Return n sorted datetime objects spread randomly between 10:00–18:00 today."""
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


# ── Node 1: create_repo ───────────────────────────────────────────────────────

def create_repo(state: ProjectState) -> dict:
    project  = state["selected_project"]
    slug     = project["slug"]
    desc     = project["description"]
    gh_token = state["gh_token"]
    repo_name = slug

    print(f"[create_repo] Creating GitHub repo: {repo_name}")
    _run(["gh", "repo", "create", f"{GITHUB_USER}/{repo_name}",
          "--public", "--description", desc, "--clone"])

    # Embed PAT in remote URL so git push never prompts for credentials
    auth_remote = f"https://{GITHUB_USER}:{gh_token}@github.com/{GITHUB_USER}/{repo_name}.git"
    _run(["git", "remote", "set-url", "origin", auth_remote], cwd=repo_name)

    # Initial commit on main — required so GitHub has a base branch for the PR
    with open(os.path.join(repo_name, ".gitkeep"), "w") as f:
        f.write("")
    _run(["git", "add", ".gitkeep"], cwd=repo_name)
    _run(["git", "commit", "-m", "chore: initial repo setup"], cwd=repo_name)
    _run(["git", "branch", "-M", "main"], cwd=repo_name)
    _run(["git", "push", "-u", "origin", "main"], cwd=repo_name)

    repo_url = f"https://github.com/{GITHUB_USER}/{repo_name}"
    print(f"[create_repo] Repo ready: {repo_url}")
    return {"repo_name": repo_name, "repo_url": repo_url}


# ── Node 2: scaffold_project ──────────────────────────────────────────────────

def scaffold_project(state: ProjectState) -> dict:
    project  = state["selected_project"]
    slug     = project["slug"]
    lang     = project["language"].lower()
    repo_dir = state["repo_name"]

    code_content   = state["code_content"]
    readme_content = state["readme_content"]

    num_commits = random.randint(5, 10)
    ts_list     = _random_timestamps(num_commits)
    commit_log  = []
    commit_idx  = 0

    _run(["git", "checkout", "-b", "dev"], cwd=repo_dir)

    def do_commit(msg: str):
        nonlocal commit_idx
        ts     = ts_list[commit_idx] if commit_idx < len(ts_list) else ts_list[-1]
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
        _run(["git", "commit", "-m", msg], cwd=repo_dir,
             env_extra={"GIT_AUTHOR_DATE": ts_str, "GIT_COMMITTER_DATE": ts_str})
        commit_log.append([ts.strftime("%I:%M %p"), msg])
        commit_idx += 1

    # ── README ────────────────────────────────────────────────────────────
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(readme_content)
    _run(["git", "add", "README.md"], cwd=repo_dir)
    do_commit(f"docs: add full README for {slug}")

    # ── Language-specific scaffold ────────────────────────────────────────
    if lang == "python":
        os.makedirs(os.path.join(repo_dir, "src"),   exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "tests"), exist_ok=True)

        main_file = os.path.join("src", "main.py")
        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(f'"""\n{project["description"]}\n"""\n\n'
                    f'def main():\n    print("TODO: implement {slug}")\n\n'
                    f'if __name__ == "__main__":\n    main()\n')
        _run(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: scaffold main script")

        with open(os.path.join(repo_dir, "requirements.txt"), "w") as f:
            f.write("pandas\nnumpy\n")
        _run(["git", "add", "requirements.txt"], cwd=repo_dir)
        do_commit("chore: add requirements.txt")

        test_file = os.path.join("tests", "test_main.py")
        with open(os.path.join(repo_dir, test_file), "w") as f:
            f.write("def test_placeholder():\n    assert True\n")
        _run(["git", "add", test_file], cwd=repo_dir)
        do_commit("test: add initial test scaffold")

        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(code_content)
        _run(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: implement core logic via LLM")

    elif lang == "rust":
        _run(["cargo", "init", "--bin"], cwd=repo_dir)
        _run(["git", "add", "Cargo.toml", "src/main.rs", ".gitignore"], cwd=repo_dir)
        do_commit("feat: scaffold rust binary via cargo")

        os.makedirs(os.path.join(repo_dir, "tests"), exist_ok=True)
        with open(os.path.join(repo_dir, "tests", "integration.rs"), "w") as f:
            f.write("// Integration tests\n")
        _run(["git", "add", "tests/integration.rs"], cwd=repo_dir)
        do_commit("test: add integration test directory")

        main_file = os.path.join("src", "main.rs")
        with open(os.path.join(repo_dir, main_file), "w") as f:
            f.write(code_content)
        _run(["git", "add", main_file], cwd=repo_dir)
        do_commit("feat: implement core logic via LLM")

    # ── Usage example ─────────────────────────────────────────────────────
    os.makedirs(os.path.join(repo_dir, "examples"), exist_ok=True)
    with open(os.path.join(repo_dir, "examples", "usage.md"), "w") as f:
        f.write("# Example usage\n\n```bash\n# Run the project\n```\n")
    _run(["git", "add", "examples/usage.md"], cwd=repo_dir)
    do_commit("docs: add usage example")

    # ── Padding commits ───────────────────────────────────────────────────
    padding = [
        "chore: clean up whitespace and formatting",
        "docs: fix typo in documentation",
        "style: improve code readability",
        "refactor: minor structural improvements",
        "docs: expand on usage section",
        "chore: update internal tooling configuration",
    ]
    random.shuffle(padding)
    while commit_idx < num_commits:
        with open(os.path.join(repo_dir, "README.md"), "a") as f:
            f.write("\n<!-- minor update -->\n")
        _run(["git", "add", "README.md"], cwd=repo_dir)
        do_commit(padding.pop() if padding else "chore: routine update")

    print(f"[scaffold_project] Done. {num_commits} commits made.")
    return {"num_commits": num_commits, "commit_log": commit_log}


# ── Node 3: push_and_merge_pr ─────────────────────────────────────────────────

def push_and_merge_pr(state: ProjectState) -> dict:
    repo_dir = state["repo_name"]
    slug     = state["selected_project"]["slug"]
    desc     = state["selected_project"]["description"]

    print(f"[push_and_merge_pr] Pushing dev and opening PR for {slug}")
    _run(["git", "push", "-u", "origin", "dev"], cwd=repo_dir)
    _run(["gh", "pr", "create",
          "--title", f"Initial build: {slug}",
          "--body",  desc,
          "--base",  "main",
          "--head",  "dev"], cwd=repo_dir)
    _run(["gh", "pr", "merge", "--merge", "--delete-branch"], cwd=repo_dir)

    print(f"[push_and_merge_pr] PR merged. ✅")
    return {}
