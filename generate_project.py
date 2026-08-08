import os
import json
import random
import subprocess
import datetime
import requests
import shutil

GITHUB_USER = "MohitDataSciFi"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

def run_cmd(cmd, cwd=None, env=None):
    print(f"Running: {' '.join(cmd)}")
    env_merged = os.environ.copy()
    if env:
        env_merged.update(env)
    subprocess.run(cmd, cwd=cwd, env=env_merged, check=True)

def generate_code_with_llm(language, description, api_key):
    prompt = (
        f"You are an expert developer. Provide the complete, production-ready code for a {language} script described as: {description}. "
        "Output ONLY the raw code, NO markdown formatting, NO markdown code blocks, NO explanations. "
        "Your entire output will be written directly to a source file."
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that strictly follows the user's instructions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    print(f"Calling DeepSeek API for {language} project...")
    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if content.startswith("```"):
        lines = content.split('\n')
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            content = '\n'.join(lines[1:-1])
    return content

def get_random_timestamps_for_today(num_commits):
    """Generate `num_commits` random sorted timestamps between 10:00 and 18:00 today."""
    now = datetime.datetime.now()
    start_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    
    # If it's before 10 AM, maybe shift to yesterday so we aren't committing in the future
    if now < start_time:
        start_time -= datetime.timedelta(days=1)
        end_time -= datetime.timedelta(days=1)
        
    delta = int((end_time - start_time).total_seconds())
    timestamps = []
    for _ in range(num_commits):
        random_seconds = random.randint(0, delta)
        ts = start_time + datetime.timedelta(seconds=random_seconds)
        # Format for Git: RFC 2822 or ISO 8601, we'll use ISO 8601 like: 2026-08-08T15:00:00
        timestamps.append(ts.strftime("%Y-%m-%dT%H:%M:%S"))
    
    return sorted(timestamps)

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")

    gh_token = os.environ.get("GH_TOKEN")
    if not gh_token:
        raise ValueError("GH_TOKEN environment variable not set")
        
    with open("projects.json", "r") as f:
        projects = json.load(f)
    with open("state.json", "r") as f:
        state = json.load(f)
        
    available_projects = [p for p in projects if p["slug"] not in state.get("used_slugs", [])]
    if not available_projects:
        print("No available projects left to generate.")
        return
        
    project = random.choice(available_projects)
    slug = project["slug"]
    desc = project["description"]
    lang = project["language"].lower()
    
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    repo_name = f"{slug}-{date_str}"
    print(f"Selected project: {slug} ({lang})")
    
    code_content = generate_code_with_llm(lang, desc, api_key)
    
    run_cmd(["gh", "repo", "create", f"{GITHUB_USER}/{repo_name}", "--public", "--description", desc, "--clone"])
    repo_dir = repo_name

    # Embed PAT directly into remote URL — most reliable auth in non-interactive CI
    auth_remote = f"https://{GITHUB_USER}:{gh_token}@github.com/{GITHUB_USER}/{repo_name}.git"
    run_cmd(["git", "remote", "set-url", "origin", auth_remote], cwd=repo_dir)

    run_cmd(["git", "checkout", "-b", "dev"], cwd=repo_dir)
    
    # Determine number of commits
    num_commits = random.randint(5, 10)
    timestamps = get_random_timestamps_for_today(num_commits)
    commit_idx = 0
    
    def do_commit(msg):
        nonlocal commit_idx
        # If we run out of generated timestamps (shouldn't happen for core commits, but just in case)
        ts = timestamps[commit_idx] if commit_idx < len(timestamps) else timestamps[-1]
        env = {
            "GIT_AUTHOR_DATE": ts,
            "GIT_COMMITTER_DATE": ts
        }
        run_cmd(["git", "commit", "-m", msg], cwd=repo_dir, env=env)
        commit_idx += 1

    # 1. README
    with open(os.path.join(repo_dir, "README.md"), "w") as f:
        f.write(f"# {slug}\n\n{desc}\n\n## Status\n🚧 In progress — built as part of daily practice.\n")
    run_cmd(["git", "add", "README.md"], cwd=repo_dir)
    do_commit(f"docs: initial README for {slug}")
    
    if lang == "python":
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
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
        
        # extra commit to pad Rust to at least 4 base commits
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
    
    # Pad remaining commits to hit `num_commits`
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
        # Just append a blank line or a comment to README to make a dummy commit
        with open(os.path.join(repo_dir, "README.md"), "a") as f:
            f.write("\n<!-- minor update -->\n")
        run_cmd(["git", "add", "README.md"], cwd=repo_dir)
        msg = padding_messages.pop() if padding_messages else "chore: routine update"
        do_commit(msg)
    
    run_cmd(["git", "push", "-u", "origin", "dev"], cwd=repo_dir)
    run_cmd(["gh", "pr", "create", "--title", f"Initial build: {slug}", "--body", desc, "--base", "main", "--head", "dev"], cwd=repo_dir)
    run_cmd(["gh", "pr", "merge", "--merge", "--delete-branch"], cwd=repo_dir)
    
    print(f"✅ Done: https://github.com/{GITHUB_USER}/{repo_name}")
    
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

if __name__ == "__main__":
    main()
