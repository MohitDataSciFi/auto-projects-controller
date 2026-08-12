"""
Node: update_profile_readme
After project finalization, updates the GitHub profile README
(MohitDataSciFi/MohitDataSciFi) with current curriculum progress,
recent projects, and skill progress bars.
"""

import os
import json
import base64
import datetime
import requests
from graph.state import ProjectState

GITHUB_API  = "https://api.github.com"
GITHUB_USER = "MohitDataSciFi"


def _gh_headers(gh_token: str) -> dict:
    return {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    filled = round((done / total) * width) if total > 0 else 0
    bar    = "█" * filled + "░" * (width - filled)
    pct    = round((done / total) * 100) if total > 0 else 0
    return f"`[{bar}]` **{pct}%**"


def _build_readme(state_data: dict, curriculum: dict) -> str:
    used_slugs       = state_data.get("used_slugs", [])
    run_history      = state_data.get("run_history", [])
    curriculum_state = state_data.get("curriculum_state", {})
    topics           = curriculum["topics"]

    topic_order = curriculum_state.get("topic_order", 1)
    level       = curriculum_state.get("level", 1)
    week_number = curriculum_state.get("week_number", 1)
    total_projects = len(used_slugs)
    total_topics   = len(topics)

    current_topic = next((t for t in topics if t["order"] == topic_order), topics[0])

    # Recent projects (last 5)
    recent = run_history[-5:][::-1]
    recent_lines = "\n".join(
        f"| [{r['slug']}](https://github.com/{GITHUB_USER}/{r['slug']}) "
        f"| {r.get('date', 'N/A')} |"
        for r in recent
    ) or "| No projects yet | — |"

    # Topic progress table (first 10)
    topic_rows = []
    for t in topics[:10]:
        done = 7 if t["order"] < topic_order else (
            curriculum_state.get("projects_done_in_topic", 0)
            if t["order"] == topic_order else 0
        )
        bar  = _progress_bar(done, 7, width=10)
        status = "✅" if done == 7 else ("🔄" if t["order"] == topic_order else "⬜")
        topic_rows.append(f"| {status} | {t['name']} | {bar} | {done}/7 |")
    topic_table = "\n".join(topic_rows)

    overall_done  = sum(7 for t in topics if t["order"] < topic_order)
    overall_done += curriculum_state.get("projects_done_in_topic", 0)
    overall_total = total_topics * 7
    overall_bar   = _progress_bar(overall_done, overall_total)

    today = datetime.datetime.now().strftime("%B %d, %Y")

    return f"""<div align="center">

# ⚡ MohitDataSciFi — AI/ML Engineering Portfolio

*Systematically building from fundamentals to cutting-edge AI — one production project per day.*

![Last Updated](https://img.shields.io/badge/Last_Updated-{today.replace(' ', '_')}-blue)
![Projects](https://img.shields.io/badge/Projects_Built-{total_projects}-green)
![Week](https://img.shields.io/badge/Week-{week_number}-orange)

</div>

---

## 📊 Curriculum Progress

**Overall:** {overall_bar} ({overall_done}/{overall_total} projects)

**Current:** `{current_topic['name']}` — Level **{level}/7**

| Status | Topic | Progress | Done |
|--------|-------|----------|------|
{topic_table}

> *10 of {total_topics} topics shown. Full curriculum: Linear Regression → Statistics → Linear Algebra → PCA → Classification → Ensemble → Clustering → CV → NLP → Time Series → RecSys → Deep Learning → RL → OR → A/B Testing → Graph ML → MLOps → LLM/RAG → Multi-Agent AI*

---

## 🚀 Recent Projects

| Project | Date |
|---------|------|
{recent_lines}

[→ View all {total_projects} projects on GitHub](https://github.com/{GITHUB_USER}?tab=repositories)

---

## 🛠 Tech Stack

### Languages & Core
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?style=flat&logo=rust&logoColor=white)
![C++](https://img.shields.io/badge/C++-00599C?style=flat&logo=c%2B%2B&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-4479A1?style=flat&logo=postgresql&logoColor=white)

### Deep Learning & AI
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white)
![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?style=flat&logo=tensorflow&logoColor=white)
![Keras](https://img.shields.io/badge/Keras-D00000?style=flat&logo=keras&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging_Face-FFD21E?style=flat&logo=huggingface&logoColor=black)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat&logo=openai&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat&logo=langchain&logoColor=white)

### Machine Learning & Data Science
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat&logo=scikit-learn&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-1175C5?style=flat)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=flat&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=flat&logo=numpy&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=flat&logo=scipy&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat&logo=opencv&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-11557C?style=flat)
![Seaborn](https://img.shields.io/badge/Seaborn-4C72B0?style=flat)

### MLOps & Deployment
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-0194E2?style=flat&logo=mlflow&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white)

---

<div align="center">
<sub>Auto-updated by <a href="https://github.com/{GITHUB_USER}/auto-projects-controller">auto-projects-controller</a> · {today}</sub>
</div>
"""


def update_profile_readme(state: ProjectState) -> dict:
    gh_token = state["gh_token"]
    headers  = _gh_headers(gh_token)
    profile_repo = f"{GITHUB_USER}/{GITHUB_USER}"

    # Ensure profile repo exists
    check = requests.get(f"{GITHUB_API}/repos/{profile_repo}", headers=headers)
    if check.status_code == 404:
        print("[update_profile_readme] Creating profile repo...")
        requests.post(
            f"{GITHUB_API}/user/repos",
            headers=headers,
            json={"name": GITHUB_USER, "auto_init": True, "description": "GitHub Profile README"},
        )
        import time; time.sleep(3)

    # Load fresh state and curriculum
    with open("state.json") as f:
        state_data = json.load(f)
    with open("curriculum.json") as f:
        curriculum = json.load(f)

    readme_content = _build_readme(state_data, curriculum)
    encoded        = base64.b64encode(readme_content.encode()).decode()

    # Get current file SHA (needed for update)
    file_resp = requests.get(
        f"{GITHUB_API}/repos/{profile_repo}/contents/README.md",
        headers=headers,
    )
    sha = file_resp.json().get("sha") if file_resp.status_code == 200 else None

    payload = {
        "message": f"chore: update profile README — {datetime.datetime.now().strftime('%Y-%m-%d')}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(
        f"{GITHUB_API}/repos/{profile_repo}/contents/README.md",
        headers=headers,
        json=payload,
    )

    if resp.status_code in (200, 201):
        print("[update_profile_readme] Profile README updated successfully ✅")
    else:
        print(f"[update_profile_readme] Warning: {resp.status_code} — {resp.text[:200]}")

    return {}
