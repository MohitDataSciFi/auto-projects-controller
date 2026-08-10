from typing import TypedDict, Optional


class ProjectState(TypedDict):
    # ── Idea bank ──────────────────────────────────────────────────────────
    available_projects: list   # list of {slug, description, language}
    skipped_slugs: list        # slugs rejected by user this run

    # ── Selected project ───────────────────────────────────────────────────
    selected_project: dict     # {slug, description, language}
    approval_status: str       # "pending" | "approved" | "rejected" | "timeout"
    tg_offset: int             # Telegram update_id offset for fresh reply polling

    # ── LLM outputs ────────────────────────────────────────────────────────
    code_content: str
    readme_content: str
    summary_text: str

    # ── Repo & commits ─────────────────────────────────────────────────────
    repo_name: str
    repo_url: str
    num_commits: int
    commit_log: list           # list of [timestamp_str, message]

    # ── Runtime credentials (injected at start) ────────────────────────────
    api_key: str
    gh_token: str

    # ── Error tracking ─────────────────────────────────────────────────────
    error: Optional[str]
