"""
Conditional edge router functions for the LangGraph project automation graph.
Each function inspects state and returns the name of the next node to execute.
"""

from langgraph.graph import END


def route_after_approval(state: dict) -> str:
    """
    After wait_for_approval:
      - approved / timeout  →  generate_artifacts
      - rejected            →  handle_rejection
    """
    if state["approval_status"] in ("approved", "timeout"):
        return "generate_artifacts"
    return "handle_rejection"


def route_after_rejection(state: dict) -> str:
    """
    After handle_rejection:
      - ideas still available  →  select_project  (loop)
      - nothing left           →  END
    """
    remaining = [
        p for p in state["available_projects"]
        if p["slug"] not in state["skipped_slugs"]
    ]
    if remaining:
        return "select_project"
    return END
