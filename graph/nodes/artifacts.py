"""
Node: generate_artifacts
Calls DeepSeek to generate: implementation code, README, and project summary.
All three calls run concurrently via ThreadPoolExecutor.
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from graph.state import ProjectState

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _llm(system: str, user: str, api_key: str, temperature: float = 0.2) -> str:
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
    content = resp.json()["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```") and lines[-1].startswith("```"):
            content = "\n".join(lines[1:-1])
    return content


def _gen_code(language: str, description: str, api_key: str) -> str:
    print(f"[generate_artifacts] Generating {language} code...")
    return _llm(
        "You are an expert developer. Follow instructions exactly.",
        f"Write complete, production-ready {language} code for: {description}. "
        "Output ONLY raw code. No markdown fences, no explanations.",
        api_key,
        temperature=0.2,
    )


def _gen_readme(language: str, slug: str, description: str, api_key: str) -> str:
    lang_label   = "Python" if language == "python" else "Rust"
    install_hint = "pip install -r requirements.txt" if language == "python" else "cargo build --release"
    run_hint     = "python src/main.py" if language == "python" else "cargo run"
    print(f"[generate_artifacts] Generating README for {slug}...")
    return _llm(
        "You are a technical writer who writes clean, professional GitHub READMEs.",
        f"""Write a professional GitHub README.md for a {lang_label} project.

Project name: {slug}
Description: {description}

Include these sections in order:
1. Title (# {slug}) with a one-line tagline
2. Shields.io badges: language, MIT license, status active
3. ## Overview — 3-4 sentences on the problem it solves
4. ## Features — 4-6 bullet points
5. ## Requirements — Python 3.8+ or Rust 1.70+, key libraries
6. ## Installation — steps with code blocks ({install_hint})
7. ## Usage — example with code block ({run_hint})
8. ## Example Output — realistic sample output
9. ## Contributing — one short paragraph
10. ## License — MIT

Output ONLY raw markdown.""",
        api_key,
        temperature=0.4,
    )


def _gen_summary(language: str, slug: str, description: str, api_key: str) -> str:
    print(f"[generate_artifacts] Generating summary for {slug}...")
    return _llm(
        "You write concise plain-text project summaries.",
        f"In exactly 3 sentences, explain what '{slug}' does and why it's useful. "
        f"Description: {description}. Language: {language}. No bullet points, no markdown.",
        api_key,
        temperature=0.3,
    )


def generate_artifacts(state: ProjectState) -> dict:
    project  = state["selected_project"]
    slug     = project["slug"]
    desc     = project["description"]
    lang     = project["language"].lower()
    api_key  = state["api_key"]

    # Run all 3 LLM calls concurrently
    results = {}
    tasks = {
        "code":    lambda: _gen_code(lang, desc, api_key),
        "readme":  lambda: _gen_readme(lang, slug, desc, api_key),
        "summary": lambda: _gen_summary(lang, slug, desc, api_key),
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()

    print("[generate_artifacts] All LLM calls complete.")
    return {
        "code_content":   results["code"],
        "readme_content": results["readme"],
        "summary_text":   results["summary"],
    }
