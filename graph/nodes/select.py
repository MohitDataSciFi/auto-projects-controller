"""
Node: select_project
Picks a random unused, non-skipped project from the idea bank.
"""

import random
from graph.state import ProjectState


def select_project(state: ProjectState) -> dict:
    skipped = state.get("skipped_slugs", [])
    available = [
        p for p in state["available_projects"]
        if p["slug"] not in skipped
    ]

    if not available:
        print("No available projects left.")
        return {"selected_project": {}, "approval_status": "no_projects"}

    project = random.choice(available)
    print(f"[select_project] Selected: {project['slug']} ({project['language']})")
    return {
        "selected_project": project,
        "approval_status": "pending",
    }
