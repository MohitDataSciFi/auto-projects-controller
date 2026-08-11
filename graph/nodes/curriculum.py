"""
Node: select_from_curriculum
Replaces research_trending_tech + generate_project_plan.
Reads curriculum.json and state.json to determine:
  - Which topic we're currently on
  - Which level (1-7) within that topic
  - Generates a specific, production-grade project blueprint using LLM
  - Handles skill combinations at higher levels
"""

import json
import random
import datetime
import requests
from graph.state import ProjectState

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
GITHUB_API       = "https://api.github.com"


def _search_github_references(topic_name: str, skill_tags: list, gh_token: str) -> str:
    """Search GitHub for top repos related to the current topic for LLM reference."""
    query = f"{' '.join(skill_tags[:3])} language:python stars:>50"
    try:
        resp = requests.get(
            f"{GITHUB_API}/search/repositories",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
            timeout=10,
        )
        if resp.status_code != 200:
            return ""
        items = resp.json().get("items", [])
        if not items:
            return ""
        lines = [f"Top GitHub repos for '{topic_name}' (use as structural reference):"]
        for item in items[:5]:
            lines.append(
                f"  - {item['full_name']} ⭐{item['stargazers_count']:,}: {item['description'] or 'No description'}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[github_search] Warning: {e}")
        return ""


def _llm(system: str, user: str, api_key: str, temperature: float = 0.5) -> str:
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "temperature": temperature,
        },
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])
    return content


def _get_curriculum_position(state_data: dict) -> dict:
    """Determine current topic index and level from state.json."""
    curriculum_state = state_data.get("curriculum_state", {})
    return {
        "topic_order": curriculum_state.get("topic_order", 1),       # 1-20
        "level":       curriculum_state.get("level", 1),             # 1-7
        "week_number": curriculum_state.get("week_number", 1),
        "projects_done_in_topic": curriculum_state.get("projects_done_in_topic", 0),
    }


def _advance_position(pos: dict, total_topics: int) -> dict:
    """After a project completes, advance the curriculum position."""
    projects_done = pos["projects_done_in_topic"] + 1

    if projects_done >= 7:
        # Completed all 7 levels for this topic → next topic
        next_topic_order = pos["topic_order"] + 1
        if next_topic_order > total_topics:
            next_topic_order = 1  # restart with combinations
        return {
            "topic_order": next_topic_order,
            "level": 1,
            "week_number": pos["week_number"] + 1,
            "projects_done_in_topic": 0,
        }
    else:
        return {
            "topic_order": pos["topic_order"],
            "level": projects_done + 1,  # level = project index + 1
            "week_number": pos["week_number"],
            "projects_done_in_topic": projects_done,
        }


def select_from_curriculum(state: ProjectState) -> dict:
    api_key = state["api_key"]
    today   = datetime.datetime.now().strftime("%B %d, %Y")

    # Load curriculum and state
    with open("curriculum.json") as f:
        curriculum = json.load(f)
    with open("state.json") as f:
        state_data = json.load(f)

    topics      = curriculum["topics"]
    total_topics = len(topics)
    used_slugs  = state_data.get("used_slugs", [])

    pos         = _get_curriculum_position(state_data)
    topic_order = pos["topic_order"]
    level       = pos["level"]
    week_number = pos["week_number"]

    # Find the topic by order
    topic = next((t for t in topics if t["order"] == topic_order), topics[0])
    topic_name  = topic["name"]
    skill_tags  = topic["skill_tags"]
    level_goal  = topic["levels"].get(str(level), topic["levels"]["7"])

    # Determine which previous skills to combine (levels 4+ incorporate prior topics)
    combined_skills = []
    if level >= 4:
        prev_topics = [t for t in topics if t["order"] < topic_order]
        # Pick 1-2 complementary previous topics to combine
        k = min(len(prev_topics), level - 3)  # 1 at level 4, up to 2 at level 5+
        if prev_topics:
            sampled = random.sample(prev_topics, min(k, len(prev_topics)))
            combined_skills = [t["name"] for t in sampled]

    combined_str = (
        f"\nIMPORTANT: This is a combined-skills project. It must integrate:\n"
        + "\n".join(f"  - {s}" for s in combined_skills)
        if combined_skills else ""
    )

    difficulty_map = {
        1: "Beginner", 2: "Applied", 3: "Production",
        4: "Advanced", 5: "Combined", 6: "Enterprise", 7: "Expert"
    }
    difficulty = difficulty_map.get(level, "Expert")

    print(f"[select_from_curriculum] Topic: {topic_name} | Level: {level} ({difficulty}) | Week: {week_number}")

    # Search GitHub for real reference repos on this topic
    gh_token        = state.get("gh_token", "")
    github_refs_str = _search_github_references(topic_name, skill_tags, gh_token)
    if github_refs_str:
        print(f"[select_from_curriculum] Found GitHub references for context.")

    # Determine duration: simple projects 1 day, complex 3-5 days
    duration_map = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 5, 7: 7}
    duration_days = duration_map.get(level, 3)

    # Generate specific project blueprint
    raw_plan = _llm(
        "You are a principal ML engineer who designs production-grade open-source AI/ML projects. "
        "You always build real, usable systems — never toy examples.",
        f"""Today is {today}. You are designing project #{pos['projects_done_in_topic'] + 1} of 7
for the curriculum topic: {topic_name}

Difficulty level: {level}/7 — {difficulty}
Level goal: {level_goal}
Main skills: {', '.join(skill_tags)}{combined_str}

Already completed slugs (avoid these): {', '.join(used_slugs[-20:]) if used_slugs else 'none'}

{github_refs_str}

Design a SPECIFIC, production-grade open-source project for this level.

Return ONLY a valid JSON object:
{{
  "slug": "specific-kebab-case-name",
  "description": "One-sentence GitHub repo description",
  "language": "python",
  "tech_stack": ["lib1", "lib2", "lib3", "lib4"],
  "duration_days": {duration_days},
  "complexity": "{difficulty}",
  "trend_tag": "{topic_name} — Level {level}/7",
  "topic": "{topic_name}",
  "level": {level},
  "combined_skills": {json.dumps(combined_skills)},
  "phases": [
    {{
      "name": "Phase N: Title",
      "goal": "Detailed description of what gets built (2-3 sentences, specific modules/classes/APIs).",
      "key_files": ["src/module.py"],
      "commit_prefix": "feat"
    }}
  ]
}}

Rules:
- duration_days = {duration_days}, so phases array must have exactly {duration_days} element(s)
- slug must be unique, descriptive, and not in the already-completed list
- tech_stack must be real Python/Rust libraries appropriate for this topic and level
- Each phase builds progressively on the previous
- For level 1-2: single phase. For level 3+: multiple phases
""",
        api_key,
        temperature=0.6,
    )

    plan = json.loads(raw_plan)

    # Save the advanced curriculum position to state.json
    new_pos = _advance_position(pos, total_topics)
    with open("state.json") as f:
        persisted = json.load(f)
    persisted["curriculum_state"] = new_pos
    with open("state.json", "w") as f:
        json.dump(persisted, f, indent=2)

    print(f"[select_from_curriculum] Plan generated: {plan['slug']} ({plan['duration_days']} day(s))")
    return {
        "project_plan":  plan,
        "tech_research": f"{topic_name} — Level {level}/7 ({difficulty}): {level_goal}",
    }
