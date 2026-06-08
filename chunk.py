"""
Milestone 2 — Chunking

Strategy (from planning.md):
  One review per chunk. No fixed token split, no overlap.
  Reviews are atomic units of meaning — splitting mid-sentence destroys the signal.
  Multi-comment Reddit threads are split at the paragraph/comment boundary (blank line).

Output: chunks.json — a list of chunk objects, each with:
  {
    "id":            unique string,
    "text":          review text,
    "property_name": which apartment complex,
    "source":        Reddit | Google Reviews | Yelp | ApartmentRatings,
    "url":           original source URL,
    "word_count":    int
  }
"""

import json
import re
from pathlib import Path

DOCUMENTS_DIR = Path("documents")
OUTPUT_FILE = Path("chunks.json")
MIN_WORDS = 15  # discard fragments with no standalone signal

# ---------------------------------------------------------------------------
# File → metadata mapping  (matches the 10 sources in planning.md)
# ---------------------------------------------------------------------------

FILE_META = {
    "reddit-1.txt": {
        "property_name": "General — Affordable Housing",
        "source": "Reddit",
        "url": "https://www.reddit.com/r/Mankato/comments/gyp9zv/moving_to_mankato_soon_looking_for_an_affordable/",
    },
    "reddit-2.txt": {
        "property_name": "Highland Hills",
        "source": "Reddit",
        "url": "https://www.reddit.com/r/Mankato/comments/1n0s58g/highland_hills_apartments/",
    },
    "reddit-3.txt": {
        "property_name": "The Grove",
        "source": "Reddit",
        "url": "https://www.reddit.com/r/Mankato/comments/1qf3ngh/the_grove/",
    },
    "apartmentratings-1.txt": {
        "property_name": "The Summit",
        "source": "ApartmentRatings",
        "url": "https://www.apartmentratings.com/mn/mankato/the-summit_507388254356001/?page=2",
    },
    "google-1.txt": {
        "property_name": "College Town",
        "source": "Google Reviews",
        "url": "https://www.google.com/maps/place/College+Town+Mankato",
    },
    "google-2.txt": {
        "property_name": "Highland Hills",
        "source": "Google Reviews",
        "url": "https://www.google.com/maps/place/Highland+Hills+Apartments+Mankato",
    },
    "google-3.txt": {
        "property_name": "College Station",
        "source": "Google Reviews",
        "url": "https://www.google.com/maps/place/College+Station+Mankato",
    },
    "google-4.txt": {
        "property_name": "The Summit & Jacob Heights",
        "source": "Google Reviews",
        "url": "https://www.google.com/maps/place/Summit+Jacob+Heights+Mankato",
    },
    "yelp-1.txt": {
        "property_name": "The Summit",
        "source": "Yelp",
        "url": "https://www.yelp.com/biz/the-summit-and-jacob-heights-mankato-2",
    },
    "yelp-2.txt": {
        "property_name": "General — Affordable Housing",
        "source": "Yelp",
        "url": "https://www.yelp.com/search?find_desc=Apartments&find_loc=Mankato%2C+MN",
    },
}

# ---------------------------------------------------------------------------
# Chunking logic
# ---------------------------------------------------------------------------

# Standalone Reddit username line at the top of a block (e.g. "Your_New_Dad16")
REDDIT_USERNAME_LINE = re.compile(r"^[A-Za-z0-9_\-]{3,30}$")

# Google review chunks that are suspiciously large are multiple reviews
# that lost their blank-line separator during cleaning — re-split them at
# sentence boundaries that look like the start of a new review.
NEW_REVIEW_START = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z](?:['\"(]|[a-z])|I (?:lived|had|love|would|don'|paid|moved|hate|used|was|am|have|only|can'|just|do |ve |'ve))"
)
MAX_WORDS_BEFORE_RESPLIT = 400


def strip_leading_username(block: str) -> str:
    """Remove a bare username line from the top of a Reddit chunk."""
    lines = block.split("\n", 1)
    if len(lines) == 2 and REDDIT_USERNAME_LINE.match(lines[0].strip()):
        return lines[1].strip()
    return block


def resplit_large_block(block: str) -> list[str]:
    """Break a suspiciously large block into individual review sentences."""
    sentences = NEW_REVIEW_START.split(block)
    result, buf = [], ""
    for sent in sentences:
        candidate = (buf + " " + sent).strip() if buf else sent.strip()
        if len(candidate.split()) > MAX_WORDS_BEFORE_RESPLIT and buf:
            result.append(buf.strip())
            buf = sent.strip()
        else:
            buf = candidate
    if buf.strip():
        result.append(buf.strip())
    return result if len(result) > 1 else [block]


def split_into_chunks(text: str) -> list[str]:
    """Split cleaned document text into individual review chunks.

    Blank lines separate reviews/comments.  Multi-paragraph reviews
    (paragraphs with no blank line between them) stay together as one chunk.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = re.split(r"\n{2,}", text)
    chunks = []
    for block in raw_blocks:
        block = strip_leading_username(block.strip())
        if not block:
            continue
        # Re-split mega-blocks that contain multiple merged reviews
        if len(block.split()) > MAX_WORDS_BEFORE_RESPLIT:
            sub = resplit_large_block(block)
        else:
            sub = [block]
        for s in sub:
            s = s.strip()
            if len(s.split()) >= MIN_WORDS:
                chunks.append(s)
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_chunks = []
    chunk_id = 0

    files = sorted(DOCUMENTS_DIR.glob("*.txt"))
    for path in files:
        if path.name not in FILE_META:
            print(f"  Skipping {path.name} (no metadata entry)")
            continue

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            print(f"  {path.name}: empty — skipped")
            continue

        meta = FILE_META[path.name]
        blocks = split_into_chunks(text)

        for block in blocks:
            all_chunks.append({
                "id": f"chunk_{chunk_id:04d}",
                "text": block,
                "property_name": meta["property_name"],
                "source": meta["source"],
                "url": meta["url"],
                "word_count": len(block.split()),
            })
            chunk_id += 1

        print(f"  {path.name}: {len(blocks)} chunks")

    OUTPUT_FILE.write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Summary
    print(f"\n--- Chunking summary ---")
    print(f"  Total chunks: {len(all_chunks)}")

    by_property: dict[str, int] = {}
    for c in all_chunks:
        by_property[c["property_name"]] = by_property.get(c["property_name"], 0) + 1
    for prop, count in sorted(by_property.items()):
        print(f"  {prop}: {count} chunks")

    word_counts = [c["word_count"] for c in all_chunks]
    if word_counts:
        print(f"\n  Word count per chunk — min: {min(word_counts)}, "
              f"max: {max(word_counts)}, "
              f"avg: {sum(word_counts) // len(word_counts)}")

    print(f"\n  Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
