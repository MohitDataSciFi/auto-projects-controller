"""
Conditional edge router functions for the redesigned LangGraph.
"""

from langgraph.graph import END


def route_after_check(state: dict) -> str:
    """
    After check_ongoing_project:
      - active project exists  →  build_next_phase
      - no active project      →  select_from_curriculum
    """
    active = state.get("active_project")
    if active and active.get("slug"):
        return "build_next_phase"
    return "select_from_curriculum"


def route_after_approval(state: dict) -> str:
    """
    After wait_for_plan_approval:
      - approved / timeout  →  setup_new_project
      - rejected            →  handle_plan_rejection (re-research)
    """
    status = state.get("approval_status", "")
    if status in ("approved", "timeout"):
        return "setup_new_project"
    return "handle_plan_rejection"


def route_after_phase(state: dict) -> str:
    """
    After build_next_phase + push_phase + report:
      - more phases remain  →  END (resume tomorrow via cron)
      - all phases done     →  finalize_project (PR merge)
    """
    active      = state.get("active_project", {})
    phase_idx   = active.get("current_phase_idx", 0)
    total       = len(active.get("phases", []))

    if phase_idx >= total:
        return "finalize_project"
    return END
