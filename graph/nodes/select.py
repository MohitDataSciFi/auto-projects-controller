"""
Node: select_project
Picks a random unused project from the idea bank, then uses LLM to check if
it is semantically too similar to any already-built project. If too similar,
skips it and picks another one.
"""

import random
import requests
from graph.state import ProjectState

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _is_too_similar(candidate: dict, used_projects: list, api_key: str) -> bool:
    """Ask LLM if the candidate is conceptually too similar to any used project."""
    if not used_projects:
        return False

    used_summary = "\n".join(
        f"- {p['slug']}: {p['description']}" for p in used_projects
    )
    prompt = (
        f"You are evaluating whether a new software project idea is too similar to ones already built.\n\n"
        f"Already built projects:\n{used_summary}\n\n"
        f"New candidate:\n- {candidate['slug']}: {candidate['description']}\n\n"
        f"Is the candidate project conceptually the same or too similar to any already built project? "
        f"Consider the core purpose and functionality, not just the name.\n"
        f"Reply with ONLY one word: YES (too similar) or NO (different enough)."
    )
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a concise project similarity evaluator."},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.0,
        },
    )
    resp.raise_for_status()
    answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
    print(f"[select_project] Similarity check for '{candidate['slug']}': {answer}")
    return answer.startswith("YES")


def select_project(state: ProjectState) -> dict:
    api_key  = state["api_key"]
    skipped  = state.get("skipped_slugs", [])

    # Filter out already-skipped/used slugs by name first
    candidates = [
        p for p in state["available_projects"]
        if p["slug"] not in skipped
    ]

    if not candidates:
        print("[select_project] No available projects left.")
        return {"selected_project": {}, "approval_status": "no_projects"}

    # Build list of already-built projects for LLM similarity check
    used_slugs = skipped  # skipped_slugs includes used_slugs from previous runs
    used_projects = [
        p for p in state["available_projects"]
        if p["slug"] in used_slugs
    ]

    # Try candidates in random order until we find one that is different enough
    random.shuffle(candidates)
    chosen = None
    for candidate in candidates:
        if _is_too_similar(candidate, used_projects, api_key):
            print(f"[select_project] '{candidate['slug']}' is too similar to an existing project — skipping.")
            skipped = skipped + [candidate["slug"]]
        else:
            chosen = candidate
            break

    if not chosen:
        print("[select_project] All remaining candidates are too similar to existing projects.")
        return {"selected_project": {}, "approval_status": "no_projects"}

    print(f"[select_project] Selected: {chosen['slug']} ({chosen['language']})")
    return {
        "selected_project": chosen,
        "skipped_slugs":    skipped,
        "approval_status":  "pending",
    }
