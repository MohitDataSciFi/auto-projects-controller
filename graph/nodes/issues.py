"""
Node: create_github_issues
After each project phase push, auto-creates 3-5 GitHub enhancement
issues on the repo to make it look actively maintained and roadmapped.
"""

import os
import random
import requests
from graph.state import ProjectState

GITHUB_API = "https://api.github.com"
GITHUB_USER = "MohitDataSciFi"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _gh_headers(gh_token: str) -> dict:
    return {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _llm(system: str, user: str, api_key: str) -> str:
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": 0.7,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def create_github_issues(state: ProjectState) -> dict:
    active   = state["active_project"]
    api_key  = state["api_key"]
    gh_token = state["gh_token"]

    slug        = active["slug"]
    description = active["description"]
    tech_stack  = ", ".join(active.get("tech_stack", []))
    phase_idx   = active["current_phase_idx"]
    total       = len(active["phases"])

    # Only create issues on the FIRST phase (day 1) to avoid duplicates
    if phase_idx != 1:
        print(f"[create_github_issues] Skipping — only create on phase 1 (current: {phase_idx})")
        return {}

    print(f"[create_github_issues] Creating enhancement issues for {slug}...")

    raw = _llm(
        "You generate realistic GitHub issue titles and descriptions for open-source ML/AI projects.",
        f"""Generate exactly 5 GitHub enhancement issues for a project called '{slug}'.
Description: {description}
Tech stack: {tech_stack}

Each issue should be a realistic future improvement. Mix of:
- Performance optimizations
- New feature additions  
- Documentation improvements
- Testing enhancements
- Integration ideas

Return as a JSON array:
[
  {{"title": "...", "body": "## Summary\\n...\\n\\n## Implementation Notes\\n...", "labels": ["enhancement"]}},
  ...
]
Output ONLY the JSON array. No markdown.""",
        api_key,
    )

    # Strip fences
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    import json
    issues = json.loads(raw)

    # Ensure labels exist first
    label_url = f"{GITHUB_API}/repos/{GITHUB_USER}/{slug}/labels"
    requests.post(label_url, headers=_gh_headers(gh_token), json={
        "name": "enhancement", "color": "a2eeef", "description": "New feature or request"
    })
    requests.post(label_url, headers=_gh_headers(gh_token), json={
        "name": "good first issue", "color": "7057ff", "description": "Good for newcomers"
    })
    requests.post(label_url, headers=_gh_headers(gh_token), json={
        "name": "roadmap", "color": "e4e669", "description": "Future roadmap items"
    })

    # Create each issue
    created = 0
    for issue in issues[:5]:
        resp = requests.post(
            f"{GITHUB_API}/repos/{GITHUB_USER}/{slug}/issues",
            headers=_gh_headers(gh_token),
            json={
                "title": issue["title"],
                "body":  issue["body"],
                "labels": issue.get("labels", ["enhancement"]),
            },
        )
        if resp.status_code == 201:
            created += 1
            print(f"  Created issue: {issue['title']}")

    print(f"[create_github_issues] {created} issues created on {slug}")
    return {}
