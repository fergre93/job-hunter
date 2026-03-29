"""
Job Hunter – täglich via GitHub Actions
Scrapt Jobs, bewertet mit Claude, speichert als JSON für GitHub Pages
"""

import os
import json
import hashlib
from datetime import datetime, date
from pathlib import Path
import anthropic
from scrapers import scrape_all_platforms

# ── Konfiguration ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Suchbegriffe – hier anpassen!
SEARCH_QUERIES = [
    "PMO Berlin",
    "Großanlagenbau Berlin",
    "Terminplanung Berlin",
    "Großprojekt Berlin",
    "Projektsteuerung Berlin",
    "Project controls Berlin",
]

MAX_JOBS_PER_RUN = 30
DOCS_DIR = Path("docs")   # GitHub Pages liest aus /docs
# ──────────────────────────────────────────────────────────────────────────────


def get_job_id(title: str, company: str, url: str) -> str:
    key = f"{title.lower().strip()}|{company.lower().strip()}|{url}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_existing_jobs() -> dict:
    jobs_file = DOCS_DIR / "jobs.json"
    if jobs_file.exists():
        return json.loads(jobs_file.read_text(encoding="utf-8"))
    return {"jobs": [], "last_updated": ""}


def load_feedback() -> dict:
    feedback_file = DOCS_DIR / "feedback.json"
    if feedback_file.exists():
        return json.loads(feedback_file.read_text(encoding="utf-8"))
    return {"feedback": {}}


def build_feedback_summary(feedback_data: dict) -> str:
    liked, disliked = [], []
    for job_id, entry in feedback_data.get("feedback", {}).items():
        label = f"{entry.get('title','?')} @ {entry.get('company','?')}"
        if entry.get("liked"):
            liked.append(label)
        else:
            disliked.append(label)

    summary = ""
    if liked:
        summary += f"Stellen die dem Nutzer gefallen haben: {', '.join(liked[-15:])}\n"
    if disliked:
        summary += f"Stellen die dem Nutzer NICHT gepasst haben: {', '.join(disliked[-15:])}\n"
    return summary or "Noch kein Feedback vorhanden."


def rate_jobs_with_claude(jobs: list[dict], feedback_summary: str) -> list[dict]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    jobs_text = "\n\n".join([
        f"[{i+1}] Titel: {j['title']}\n"
        f"    Firma: {j['company']}\n"
        f"    Ort: {j.get('location', 'k.A.')}\n"
        f"    Beschreibung: {j.get('description', '')[:300]}"
        for i, j in enumerate(jobs)
    ])

    prompt = f"""Du bist ein Job-Assistent. Bewerte jede Stelle mit einem Score von 1–10
und einer kurzen deutschen Begründung (max. 1 Satz), basierend auf dem Nutzer-Feedback.

Nutzer-Feedback-Historie:
{feedback_summary}

Stellenanzeigen:
{jobs_text}

Antworte NUR als JSON-Array:
[{{"index": 1, "score": 8, "reason": "Passt gut zu bisherigen Präferenzen"}}, ...]"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        ratings = json.loads(text.strip())
        rating_map = {r["index"]: r for r in ratings}
    except Exception as e:
        print(f"⚠️  Claude-Bewertung fehlgeschlagen: {e}")
        rating_map = {}

    for i, job in enumerate(jobs):
        rating = rating_map.get(i + 1, {})
        job["score"]  = rating.get("score", 5)
        job["reason"] = rating.get("reason", "")

    return sorted(jobs, key=lambda j: j["score"], reverse=True)


def main():
    print(f"🚀 Job Hunter – {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    DOCS_DIR.mkdir(exist_ok=True)

    # 1. Bestehende Daten laden
    existing    = load_existing_jobs()
    feedback    = load_feedback()
    known_ids   = {j["id"] for j in existing.get("jobs", [])}
    feedback_summary = build_feedback_summary(feedback)
    print(f"📊 {len(known_ids)} bekannte Jobs, Feedback: {feedback_summary[:80]}...")

    # 2. Scrapen
    print("🔍 Scrape Job-Plattformen...")
    raw_jobs = scrape_all_platforms(SEARCH_QUERIES)
    print(f"   → {len(raw_jobs)} Stellen gefunden")

    # 3. Nur neue Jobs filtern
    new_raw = []
    for job in raw_jobs:
        job["id"] = get_job_id(job["title"], job["company"], job["url"])
        if job["id"] not in known_ids:
            new_raw.append(job)

    print(f"   → {len(new_raw)} davon neu")

    if new_raw:
        # 4. Claude-Bewertung
        print("🤖 Claude bewertet neue Stellen...")
        rated = rate_jobs_with_claude(new_raw[:MAX_JOBS_PER_RUN], feedback_summary)

        # Timestamp hinzufügen
        today = date.today().isoformat()
        for job in rated:
            job["found_date"] = today

        # 5. Mit bestehenden Jobs zusammenführen (neueste zuerst)
        all_jobs = rated + existing.get("jobs", [])
        all_jobs = all_jobs[:200]   # Max. 200 Jobs behalten
    else:
        all_jobs = existing.get("jobs", [])

    # 6. jobs.json speichern
    output = {
        "jobs":         all_jobs,
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "new_today":    len(new_raw),
    }
    (DOCS_DIR / "jobs.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"💾 jobs.json gespeichert ({len(all_jobs)} Jobs total)")
    print("✅ Fertig!")


if __name__ == "__main__":
    main()
