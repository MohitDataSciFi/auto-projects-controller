"""
main.py — Entry point for the LangGraph DS/DE project automation system.

Builds and runs the StateGraph:

  START
    └─► select_project
          └─► send_approval_request
                └─► wait_for_approval
                      ├─ approved/timeout ─► generate_artifacts ─► create_repo
                      │                         └─► scaffold_project
                      │                               └─► push_and_merge_pr
                      │                                     └─► update_state
                      │                                           └─► send_report ─► END
                      └─ rejected ─► handle_rejection
                                          ├─ ideas left ─► select_project  (loop)
                                          └─ none left  ─► END
"""

import os
import json
from langgraph.graph import StateGraph, END

from graph.state import ProjectState
from graph.nodes import (
    select_project,
    send_approval_request,
    wait_for_approval,
    handle_rejection,
    generate_artifacts,
    create_repo,
    scaffold_project,
    push_and_merge_pr,
    update_state,
    send_report,
)
from graph.edges import route_after_approval, route_after_rejection


def build_graph() -> StateGraph:
    builder = StateGraph(ProjectState)

    # ── Register nodes ────────────────────────────────────────────────────
    builder.add_node("select_project",          select_project)
    builder.add_node("send_approval_request",   send_approval_request)
    builder.add_node("wait_for_approval",       wait_for_approval)
    builder.add_node("handle_rejection",        handle_rejection)
    builder.add_node("generate_artifacts",      generate_artifacts)
    builder.add_node("create_repo",             create_repo)
    builder.add_node("scaffold_project",        scaffold_project)
    builder.add_node("push_and_merge_pr",       push_and_merge_pr)
    builder.add_node("update_state",            update_state)
    builder.add_node("send_report",             send_report)

    # ── Linear edges ──────────────────────────────────────────────────────
    builder.add_edge("select_project",        "send_approval_request")
    builder.add_edge("send_approval_request", "wait_for_approval")
    builder.add_edge("generate_artifacts",    "create_repo")
    builder.add_edge("create_repo",           "scaffold_project")
    builder.add_edge("scaffold_project",      "push_and_merge_pr")
    builder.add_edge("push_and_merge_pr",     "update_state")
    builder.add_edge("update_state",          "send_report")
    builder.add_edge("send_report",           END)

    # ── Conditional edges ─────────────────────────────────────────────────
    builder.add_conditional_edges(
        "wait_for_approval",
        route_after_approval,
        {
            "generate_artifacts": "generate_artifacts",
            "handle_rejection":   "handle_rejection",
        },
    )
    builder.add_conditional_edges(
        "handle_rejection",
        route_after_rejection,
        {
            "select_project": "select_project",
            END:              END,
        },
    )

    builder.set_entry_point("select_project")
    return builder.compile()


def main():
    api_key  = os.environ.get("DEEPSEEK_API_KEY")
    gh_token = os.environ.get("GH_TOKEN")

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable not set")
    if not gh_token:
        raise ValueError("GH_TOKEN environment variable not set")

    with open("projects.json") as f:
        all_projects = json.load(f)
    with open("state.json") as f:
        state_data = json.load(f)

    used_slugs = state_data.get("used_slugs", [])
    available  = [p for p in all_projects if p["slug"] not in used_slugs]

    if not available:
        print("No available projects left. Add more ideas to projects.json.")
        return

    # Build initial state
    initial_state: ProjectState = {
        "available_projects": all_projects,
        "skipped_slugs":      used_slugs,   # treat already-used as skipped too
        "selected_project":   {},
        "approval_status":    "pending",
        "tg_offset":          0,
        "code_content":       "",
        "readme_content":     "",
        "summary_text":       "",
        "repo_name":          "",
        "repo_url":           "",
        "num_commits":        0,
        "commit_log":         [],
        "api_key":            api_key,
        "gh_token":           gh_token,
        "error":              None,
    }

    graph = build_graph()
    print("🚀 Starting LangGraph automation...")
    graph.invoke(initial_state)
    print("✅ Graph completed.")


if __name__ == "__main__":
    main()
