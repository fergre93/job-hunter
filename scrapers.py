"""
Scraper-Module für LinkedIn, StepStone, Indeed, Xing
"""

import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Optional

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def _get(url: str, params: dict = None) -> Optional[BeautifulSoup]:
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            if resp.status_code == 429:
                time.sleep(30 * (attempt + 1))
        except Exception as e:
            print(f"  ⚠️  Request fehlgeschlagen ({url}): {e}")
            time.sleep(5)
    return None


def scrape_indeed(query: str) -> list[dict]:
    jobs  = []
    parts = query.rsplit(" ", 1)
    what  = parts[0] if len(parts) > 1 else query
    where = parts[1] if len(parts) > 1 else "Deutschland"

    soup = _get("https://de.indeed.com/jobs", params={"q": what, "l": where, "fromage": "1"})
    if not soup:
        return jobs

    for card in soup.select("div.job_seen_beacon")[:8]:
        try:
            title_el   = card.select_one("h2.jobTitle span[title]")
            company_el = card.select_one("span.companyName")
            loc_el     = card.select_one("div.companyLocation")
            link_el    = card.select_one("a[data-jk]")
            desc_el    = card.select_one("div.job-snippet")
            if not title_el or not link_el:
                continue
            job_id = link_el.get("data-jk", "")
            jobs.append({
                "platform":    "Indeed",
                "title":       title_el.get("title", title_el.text).strip(),
                "company":     company_el.text.strip() if company_el else "k.A.",
                "location":    loc_el.text.strip() if loc_el else where,
                "url":         f"https://de.indeed.com/viewjob?jk={job_id}",
                "description": desc_el.text.strip() if desc_el else "",
            })
        except Exception:
            continue

    time.sleep(random.uniform(2, 4))
    return jobs


def scrape_stepstone(query: str) -> list[dict]:
    jobs       = []
    parts      = query.rsplit(" ", 1)
    title_part = parts[0].replace(" ", "-").lower() if len(parts) > 1 else query.replace(" ", "-").lower()
    loc_part   = parts[1].lower() if len(parts) > 1 else "deutschland"

    soup = _get(f"https://www.stepstone.de/jobs/{title_part}/in-{loc_part}")
    if not soup:
        soup = _get("https://www.stepstone.de/jobs", params={"q": query})
    if not soup:
        return jobs

    for card in soup.select("article[data-job-id]")[:8]:
        try:
            title_el   = card.select_one("h2[data-at='job-item-title']") or card.select_one("h2")
            company_el = card.select_one("span[data-at='job-item-company-name']")
            loc_el     = card.select_one("[data-at='job-item-location']")
            link_el    = card.select_one("a[href*='/stellenangebote']") or card.select_one("a[href]")
            if not title_el:
                continue
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.stepstone.de" + href
            jobs.append({
                "platform":    "StepStone",
                "title":       title_el.text.strip(),
                "company":     company_el.text.strip() if company_el else "k.A.",
                "location":    loc_el.text.strip() if loc_el else query,
                "url":         href,
                "description": "",
            })
        except Exception:
            continue

    time.sleep(random.uniform(2, 4))
    return jobs


def scrape_linkedin(query: str) -> list[dict]:
    jobs     = []
    parts    = query.rsplit(" ", 1)
    keywords = parts[0] if len(parts) > 1 else query
    location = parts[1] if len(parts) > 1 else "Germany"

    soup = _get("https://www.linkedin.com/jobs/search/", params={
        "keywords": keywords,
        "location": location,
        "f_TPR":    "r86400",
        "position": 1,
        "pageNum":  0,
    })
    if not soup:
        return jobs

    for card in soup.select("div.base-card")[:8]:
        try:
            title_el   = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            loc_el     = card.select_one("span.job-search-card__location")
            link_el    = card.select_one("a.base-card__full-link")
            if not title_el or not link_el:
                continue
            jobs.append({
                "platform":    "LinkedIn",
                "title":       title_el.text.strip(),
                "company":     company_el.text.strip() if company_el else "k.A.",
                "location":    loc_el.text.strip() if loc_el else location,
                "url":         link_el["href"].split("?")[0],
                "description": "",
            })
        except Exception:
            continue

    time.sleep(random.uniform(3, 6))
    return jobs


def scrape_xing(query: str) -> list[dict]:
    jobs     = []
    parts    = query.rsplit(" ", 1)
    keywords = parts[0] if len(parts) > 1 else query
    location = parts[1] if len(parts) > 1 else "Deutschland"

    soup = _get("https://www.xing.com/jobs/search/rss",
                params={"keywords": keywords, "location": location})
    if not soup:
        return jobs

    for item in soup.select("item")[:8]:
        try:
            title   = item.select_one("title")
            link    = item.select_one("link")
            company = item.select_one("xing\\:company") or item.select_one("company")
            loc     = item.select_one("xing\\:location") or item.select_one("location")
            desc    = item.select_one("description")
            if not title:
                continue
            jobs.append({
                "platform":    "Xing",
                "title":       title.text.strip(),
                "company":     company.text.strip() if company else "k.A.",
                "location":    loc.text.strip() if loc else location,
                "url":         link.next_sibling.strip() if link else "",
                "description": BeautifulSoup(desc.text, "html.parser").get_text()[:300] if desc else "",
            })
        except Exception:
            continue

    time.sleep(random.uniform(2, 4))
    return jobs


def scrape_all_platforms(queries: list[str]) -> list[dict]:
    all_jobs = []
    seen     = set()

    scrapers = [
        ("Indeed",    scrape_indeed),
        ("StepStone", scrape_stepstone),
        ("LinkedIn",  scrape_linkedin),
        ("Xing",      scrape_xing),
    ]

    for query in queries:
        print(f"  🔎 Query: '{query}'")
        for platform_name, fn in scrapers:
            try:
                jobs = fn(query)
                for job in jobs:
                    key = f"{job['title'].lower()}|{job['company'].lower()}"
                    if key not in seen:
                        seen.add(key)
                        all_jobs.append(job)
                print(f"     ✓ {platform_name}: {len(jobs)} Stellen")
            except Exception as e:
                print(f"     ✗ {platform_name} Fehler: {e}")

    return all_jobs
