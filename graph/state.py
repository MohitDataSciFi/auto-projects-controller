from typing import TypedDict, Optional


class ProjectState(TypedDict):
    # ── Research output ────────────────────────────────────────────────────
    tech_research:  str    # Raw LLM research output on trending tech
    project_plan:   dict   # {slug, description, language, tech_stack, duration_days, phases}
                           # phases: [{name, goal, status}]

    # ── Active project (loaded from state.json or newly created) ───────────
    active_project: dict   # {slug, repo_name, repo_url, language,
                           #  current_phase_idx, phases: [{name, goal, status}]}

    # ── Approval flow ──────────────────────────────────────────────────────
    approval_status: str   # "pending" | "approved" | "rejected" | "timeout"
    tg_offset:       int   # Telegram update_id offset for fresh reply polling

    # ── Phase build results ────────────────────────────────────────────────
    commit_log:    list    # [[time_str, message], ...]
    num_commits:   int
    phase_summary: str     # LLM-generated summary of what was built this phase

    # ── Runtime credentials ────────────────────────────────────────────────
    api_key:  str
    gh_token: str

    # ── Error tracking ─────────────────────────────────────────────────────
    error: Optional[str]
