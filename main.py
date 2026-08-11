"""
main.py — LangGraph AI/ML Curriculum Automation Engine v3.0

Daily workflow:
  ┌─ Has active project? ──YES──► build_next_phase ──► push ──► create_issues
  │                                                               ──► report ──► finalize? ──► update_profile ──► END
  └─ No ──► select_from_curriculum ──► propose ──► approve
                                                    │
                              rejected ──► curriculum (next level)
"""

import os
import json
import traceback
import requests
from langgraph.graph import StateGraph, END

from graph.state import ProjectState
from graph.nodes import (
    select_from_curriculum,
    send_plan_to_user,
    wait_for_plan_approval,
    handle_plan_rejection,
    check_ongoing_project,
    setup_new_project,
    build_next_phase,
    push_phase,
    create_github_issues,
    finalize_project,
    update_profile_readme,
    send_daily_progress_report,
)
from graph.edges import route_after_check, route_after_approval, route_after_phase


def _tg_error_alert(error_msg: str):
    """Send error alert to Telegram if credentials are available."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    import datetime
    now = datetime.datetime.now().strftime("%b %d, %Y — %H:%M")
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id":    chat_id,
                "text": (
                    f"⚠️ <b>SYSTEM ALERT — {now}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"❌ <b>Automation pipeline failed!</b>\n\n"
                    f"<b>Error:</b>\n<code>{error_msg[:800]}</code>\n\n"
                    f"🛡️ Streak Guard will run as fallback."
                ),
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        pass


def build_graph() -> StateGraph:
    builder = StateGraph(ProjectState)

    # ── Register all nodes ────────────────────────────────────────────────
    builder.add_node("check_ongoing_project",      check_ongoing_project)
    builder.add_node("select_from_curriculum",     select_from_curriculum)
    builder.add_node("send_plan_to_user",          send_plan_to_user)
    builder.add_node("wait_for_plan_approval",     wait_for_plan_approval)
    builder.add_node("handle_plan_rejection",      handle_plan_rejection)
    builder.add_node("setup_new_project",          setup_new_project)
    builder.add_node("build_next_phase",           build_next_phase)
    builder.add_node("push_phase",                 push_phase)
    builder.add_node("create_github_issues",       create_github_issues)
    builder.add_node("send_daily_progress_report", send_daily_progress_report)
    builder.add_node("finalize_project",           finalize_project)
    builder.add_node("update_profile_readme",      update_profile_readme)

    # ── Entry point ───────────────────────────────────────────────────────
    builder.set_entry_point("check_ongoing_project")

    # ── Conditional: ongoing vs. curriculum ───────────────────────────────
    builder.add_conditional_edges(
        "check_ongoing_project",
        route_after_check,
        {
            "build_next_phase":       "build_next_phase",
            "select_from_curriculum": "select_from_curriculum",
        },
    )

    # ── Curriculum → Propose → Approve ────────────────────────────────────
    builder.add_edge("select_from_curriculum", "send_plan_to_user")
    builder.add_edge("send_plan_to_user",      "wait_for_plan_approval")

    builder.add_conditional_edges(
        "wait_for_plan_approval",
        route_after_approval,
        {
            "setup_new_project":     "setup_new_project",
            "handle_plan_rejection": "handle_plan_rejection",
        },
    )

    # Rejection → next curriculum level
    builder.add_edge("handle_plan_rejection", "select_from_curriculum")

    # Approved → setup → first phase
    builder.add_edge("setup_new_project", "build_next_phase")

    # ── Phase pipeline ─────────────────────────────────────────────────────
    builder.add_edge("build_next_phase",            "push_phase")
    builder.add_edge("push_phase",                  "create_github_issues")
    builder.add_edge("create_github_issues",        "send_daily_progress_report")

    builder.add_conditional_edges(
        "send_daily_progress_report",
        route_after_phase,
        {
            "finalize_project": "finalize_project",
            END:                END,
        },
    )

    # Finalize → update profile → END
    builder.add_edge("finalize_project",   "update_profile_readme")
    builder.add_edge("update_profile_readme", END)

    return builder.compile()


def main():
    api_key  = os.environ.get("DEEPSEEK_API_KEY")
    gh_token = os.environ.get("GH_TOKEN")
    if not api_key:  raise ValueError("DEEPSEEK_API_KEY not set")
    if not gh_token: raise ValueError("GH_TOKEN not set")

    with open("state.json") as f:
        persisted = json.load(f)

    initial_state: ProjectState = {
        "tech_research":   "",
        "project_plan":    {},
        "active_project":  {},
        "approval_status": "pending",
        "tg_offset":       0,
        "commit_log":     [],
        "num_commits":    0,
        "phase_summary":  "",
        "api_key":   api_key,
        "gh_token":  gh_token,
        "error":     None,
        "_used_slugs_for_research": persisted.get("used_slugs", []),
    }

    graph = build_graph()
    print("⚡ SYSTEM ONLINE — AI/ML Curriculum Engine v3.0")
    print(f"📚 Curriculum state: {persisted.get('curriculum_state', {})}")

    try:
        graph.invoke(initial_state)
        print("✅ Sequence complete.")
    except Exception as e:
        err = traceback.format_exc()
        print(f"❌ Pipeline failed:\n{err}")
        _tg_error_alert(err)
        raise  # Re-raise so GitHub Actions marks as failed → streak_guard runs


if __name__ == "__main__":
    main()
