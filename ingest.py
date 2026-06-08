"""
Milestone 1 — Document Ingestion

Scrapes student housing reviews into documents/.
Each review is saved as a JSON file with metadata (property_name, source, url, date).

Sources handled automatically:
  - Reddit threads via the public JSON API (no auth required)
  - ApartmentRatings pages via requests + BeautifulSoup

Sources requiring manual entry (JavaScript-rendered, block scraping):
  - Google Reviews → add to MANUAL_REVIEWS below
  - Yelp          → add to MANUAL_REVIEWS below
"""

import json
import time
import re
import os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

DOCUMENTS_DIR = "documents"

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

REDDIT_SOURCES = [
    {
        "url": "https://www.reddit.com/r/Mankato/comments/gyp9zv/moving_to_mankato_soon_looking_for_an_affordable/",
        "property_name": "General — Affordable Housing",
    },
    {
        "url": "https://www.reddit.com/r/Mankato/comments/1n0s58g/highland_hills_apartments/",
        "property_name": "Highland Hills",
    },
    {
        "url": "https://www.reddit.com/r/Mankato/comments/1qf3ngh/the_grove/",
        "property_name": "The Grove",
    },
]

APARTMENT_RATINGS_SOURCES = [
    {
        "url": "https://www.apartmentratings.com/mn/mankato/the-summit_507388254356001/?page=2#ratingsReviews",
        "property_name": "The Summit",
    },
]

# ---------------------------------------------------------------------------
# Paste Google Reviews and Yelp text here manually.
# Each entry: property_name, source, url, date (YYYY-MM-DD or ""), text.
# ---------------------------------------------------------------------------
MANUAL_REVIEWS = [
    # Example — replace with real copied review text:
    # {
    #     "property_name": "College Town",
    #     "source": "Google Reviews",
    #     "url": "https://www.google.com/...",
    #     "date": "2024-03-15",
    #     "text": "Great amenities and management is very responsive...",
    # },
]

# ---------------------------------------------------------------------------
# Reddit scraper
# ---------------------------------------------------------------------------

HEADERS = {"User-Agent": "mnsu-housing-rag/1.0 (course project)"}


def fetch_reddit_comments(reddit_url: str, property_name: str) -> list[dict]:
    """Return one dict per top-level comment in a Reddit thread."""
    json_url = reddit_url.rstrip("/") + ".json?limit=100"
    resp = requests.get(json_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # data[0] = post listing, data[1] = comments listing
    comments_data = data[1]["data"]["children"]
    post_url = reddit_url

    reviews = []
    for child in comments_data:
        if child["kind"] != "t1":
            continue
        body = child["data"].get("body", "").strip()
        if not body or body == "[deleted]" or body == "[removed]":
            continue
        created_utc = child["data"].get("created_utc", 0)
        date_str = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%d")
        reviews.append({
            "property_name": property_name,
            "source": "Reddit",
            "url": post_url,
            "date": date_str,
            "text": body,
        })
    return reviews


# ---------------------------------------------------------------------------
# ApartmentRatings scraper
# ---------------------------------------------------------------------------

def fetch_apartment_ratings(url: str, property_name: str) -> list[dict]:
    """Scrape individual review cards from an ApartmentRatings page."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    reviews = []

    # Review bodies sit in <p> tags inside elements with a review-text class or similar.
    # Inspect pattern: each review is wrapped in a section with class containing "review".
    review_sections = soup.find_all(
        lambda tag: tag.name in ("div", "section", "article")
        and any("review" in c.lower() for c in tag.get("class", []))
    )

    for section in review_sections:
        # Extract body text — the longest <p> in the section is usually the review
        paragraphs = [p.get_text(strip=True) for p in section.find_all("p") if p.get_text(strip=True)]
        if not paragraphs:
            continue
        body = max(paragraphs, key=len)
        if len(body) < 30:
            continue

        # Attempt to pull a date string
        date_str = ""
        date_tag = section.find(string=re.compile(r"\d{4}"))
        if date_tag:
            match = re.search(r"(\d{4})", date_tag)
            if match:
                date_str = match.group(1)

        reviews.append({
            "property_name": property_name,
            "source": "ApartmentRatings",
            "url": url,
            "date": date_str,
            "text": body,
        })

    return reviews


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def save_reviews(reviews: list[dict], source_slug: str) -> None:
    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    path = os.path.join(DOCUMENTS_DIR, f"{source_slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(reviews)} reviews → {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_counts = {}

    # Reddit
    for source in REDDIT_SOURCES:
        slug = slugify(source["property_name"])
        print(f"Fetching Reddit: {source['property_name']} ...")
        try:
            reviews = fetch_reddit_comments(source["url"], source["property_name"])
            save_reviews(reviews, f"reddit_{slug}")
            all_counts[source["property_name"]] = len(reviews)
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(1)  # be polite to Reddit's servers

    # ApartmentRatings
    for source in APARTMENT_RATINGS_SOURCES:
        slug = slugify(source["property_name"])
        print(f"Fetching ApartmentRatings: {source['property_name']} ...")
        try:
            reviews = fetch_apartment_ratings(source["url"], source["property_name"])
            save_reviews(reviews, f"apartmentratings_{slug}")
            all_counts[source["property_name"]] = len(reviews)
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(1)

    # Manual (Google Reviews, Yelp)
    if MANUAL_REVIEWS:
        save_reviews(MANUAL_REVIEWS, "manual_reviews")
        all_counts["Manual"] = len(MANUAL_REVIEWS)
    else:
        print("No manual reviews added yet — add Google/Yelp reviews to MANUAL_REVIEWS in ingest.py")

    print("\n--- Ingestion summary ---")
    total = 0
    for name, count in all_counts.items():
        print(f"  {name}: {count} reviews")
        total += count
    print(f"  Total: {total} reviews")


if __name__ == "__main__":
    main()
