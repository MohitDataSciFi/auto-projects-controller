"""
main.py — LangGraph DS/DE Project Automation Engine v2.0

Daily workflow:
  ┌─ Has active project? ──YES──► build_next_phase ──► push ──► report
  │                                                               │
  └─ No ──► research ──► plan ──► propose ──► approve           ├─ More phases? ──► END (resumes tomorrow)
                                                │                └─ Done? ──► finalize ──► END
                              rejected ──► research (loop)
"""

import os
import json
from langgraph.graph import StateGraph, END

from graph.state import ProjectState
from graph.nodes import (
    research_trending_tech,
    generate_project_plan,
    send_plan_to_user,
    wait_for_plan_approval,
    handle_plan_rejection,
    check_ongoing_project,
    setup_new_project,
    build_next_phase,
    push_phase,
    finalize_project,
    send_daily_progress_report,
)
from graph.edges import route_after_check, route_after_approval, route_after_phase


def build_graph() -> StateGraph:
    builder = StateGraph(ProjectState)

    # ── Register all nodes ────────────────────────────────────────────────
    builder.add_node("check_ongoing_project",   check_ongoing_project)
    builder.add_node("research_trending_tech",  research_trending_tech)
    builder.add_node("generate_project_plan",   generate_project_plan)
    builder.add_node("send_plan_to_user",       send_plan_to_user)
    builder.add_node("wait_for_plan_approval",  wait_for_plan_approval)
    builder.add_node("handle_plan_rejection",   handle_plan_rejection)
    builder.add_node("setup_new_project",       setup_new_project)
    builder.add_node("build_next_phase",        build_next_phase)
    builder.add_node("push_phase",              push_phase)
    builder.add_node("send_daily_progress_report", send_daily_progress_report)
    builder.add_node("finalize_project",        finalize_project)

    # ── Entry point ───────────────────────────────────────────────────────
    builder.set_entry_point("check_ongoing_project")

    # ── Conditional: ongoing vs. new research ─────────────────────────────
    builder.add_conditional_edges(
        "check_ongoing_project",
        route_after_check,
        {
            "build_next_phase":       "build_next_phase",
            "research_trending_tech": "research_trending_tech",
        },
    )

    # ── Research → Plan → Propose → Approve ───────────────────────────────
    builder.add_edge("research_trending_tech", "generate_project_plan")
    builder.add_edge("generate_project_plan",  "send_plan_to_user")
    builder.add_edge("send_plan_to_user",      "wait_for_plan_approval")

    builder.add_conditional_edges(
        "wait_for_plan_approval",
        route_after_approval,
        {
            "setup_new_project":    "setup_new_project",
            "handle_plan_rejection": "handle_plan_rejection",
        },
    )

    # Rejection loops back to fresh research
    builder.add_edge("handle_plan_rejection",  "research_trending_tech")

    # Approved → setup → first phase build
    builder.add_edge("setup_new_project",      "build_next_phase")

    # ── Phase pipeline ────────────────────────────────────────────────────
    builder.add_edge("build_next_phase",            "push_phase")
    builder.add_edge("push_phase",                  "send_daily_progress_report")

    builder.add_conditional_edges(
        "send_daily_progress_report",
        route_after_phase,
        {
            "finalize_project": "finalize_project",
            END:                END,
        },
    )

    builder.add_edge("finalize_project", END)

    return builder.compile()


def main():
    api_key  = os.environ.get("DEEPSEEK_API_KEY")
    gh_token = os.environ.get("GH_TOKEN")
    if not api_key:  raise ValueError("DEEPSEEK_API_KEY not set")
    if not gh_token: raise ValueError("GH_TOKEN not set")

    with open("state.json") as f:
        persisted = json.load(f)

    initial_state: ProjectState = {
        # Research (empty until nodes populate)
        "tech_research":   "",
        "project_plan":    {},

        # Active project (populated by check_ongoing_project)
        "active_project":  {},

        # Approval
        "approval_status": "pending",
        "tg_offset":       0,

        # Phase build
        "commit_log":     [],
        "num_commits":    0,
        "phase_summary":  "",

        # Runtime
        "api_key":   api_key,
        "gh_token":  gh_token,
        "error":     None,

        # Internal (used by research node for dedup)
        "_used_slugs_for_research": persisted.get("used_slugs", []),
    }

    graph = build_graph()
    print("⚡ SYSTEM ONLINE. Initiating daily automation sequence...")
    graph.invoke(initial_state)
    print("✅ Sequence complete.")


if __name__ == "__main__":
    main()
