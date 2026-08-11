"""
Nodes: research_trending_tech, generate_project_plan
Scans for the latest trending tech daily and generates a complex,
multi-phase project blueprint using DeepSeek.
"""

import json
import datetime
import requests
from graph.state import ProjectState

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _llm(system: str, user: str, api_key: str, temperature: float = 0.7) -> str:
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
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Node 1: research_trending_tech ────────────────────────────────────────────

def research_trending_tech(state: ProjectState) -> dict:
    api_key    = state["api_key"]
    today      = datetime.datetime.now().strftime("%B %d, %Y")
    used_slugs = state.get("_used_slugs_for_research", [])

    avoided = ", ".join(used_slugs[-10:]) if used_slugs else "none"

    print("[research_trending_tech] Scanning for trending tech...")
    research = _llm(
        "You are a senior tech trend analyst with real-time awareness of GitHub, "
        "HackerNews, ArXiv, and engineering blogs. You identify the most exciting, "
        "cutting-edge software engineering opportunities of TODAY.",
        f"""Today is {today}.

Identify the SINGLE hottest, most exciting technology trend in software engineering RIGHT NOW.
Think about: agentic AI systems, edge inference, durable execution engines, TinyML,
context engineering, RAG architectures, autonomous coding agents, WebAssembly, eBPF,
LLM observability, multi-agent coordination, Rust for AI, etc.

Avoid trends already covered in these past projects: {avoided}

Respond with a focused 3-4 sentence research brief on the trend, including:
- What the technology is
- Why it's exciting right now (recent developments, adoption)  
- What kind of project would showcase it best
- What tech stack would be used

Be highly specific — name actual libraries, frameworks, and tools.""",
        api_key,
        temperature=0.8,
    )

    print(f"[research_trending_tech] Research complete:\n{research[:200]}...")
    return {"tech_research": research}


# ── Node 2: generate_project_plan ─────────────────────────────────────────────

def generate_project_plan(state: ProjectState) -> dict:
    api_key  = state["api_key"]
    research = state["tech_research"]
    today    = datetime.datetime.now().strftime("%B %d, %Y")

    print("[generate_project_plan] Generating multi-phase project plan...")
    raw_plan = _llm(
        "You are a principal software architect who designs production-grade, "
        "impressive open-source projects. You always design for real-world use, "
        "not toy examples.",
        f"""Today is {today}.

Based on this tech research brief:
---
{research}
---

Design a complex, impressive, multi-phase open-source project.

Return ONLY a valid JSON object with this exact schema (no markdown, no explanation):
{{
  "slug": "kebab-case-project-name",
  "description": "One-sentence description for the GitHub repo",
  "language": "python",
  "tech_stack": ["lib1", "lib2", "lib3"],
  "duration_days": 4,
  "complexity": "Advanced",
  "trend_tag": "The trending tech this targets",
  "phases": [
    {{
      "name": "Phase 1: [Short Title]",
      "goal": "Detailed description of what gets built in this phase (2-3 sentences). Be specific about which modules, classes, APIs get implemented.",
      "key_files": ["src/module.py", "config/settings.py"],
      "commit_prefix": "feat(core)"
    }}
  ]
}}

Rules:
- slug must be lowercase, hyphenated, descriptive (e.g., "neural-loop-agent", "edge-inference-engine")
- duration_days must be between 3 and 7 (= number of phases)
- Each phase must build on the previous — Day 1 = foundation, final day = polish + integration
- tech_stack should have 4-6 real, specific libraries
- complexity must be "Advanced" or "Expert"
- language must be "python" or "rust"
""",
        api_key,
        temperature=0.6,
    )

    # Strip markdown fences if present
    raw_plan = raw_plan.strip()
    if raw_plan.startswith("```"):
        lines = raw_plan.split("\n")
        raw_plan = "\n".join(lines[1:-1])

    plan = json.loads(raw_plan)
    print(f"[generate_project_plan] Plan: {plan['slug']} ({plan['duration_days']} days)")
    return {"project_plan": plan}
