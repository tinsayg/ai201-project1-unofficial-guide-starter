"""
Cleans raw copy-pasted review documents in documents/.
Strips UI chrome, vote buttons, metadata, ads, owner responses, and emoji reactions.
Overwrites each file in place. Run once before chunking.
"""

import re
import os
from pathlib import Path

DOCUMENTS_DIR = Path("documents")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def collapse_blank_lines(lines: list[str]) -> list[str]:
    result, prev_blank = [], False
    for line in lines:
        blank = line.strip() == ""
        if blank and prev_blank:
            continue
        result.append(line)
        prev_blank = blank
    return result


# ---------------------------------------------------------------------------
# Reddit cleaner
# ---------------------------------------------------------------------------

REDDIT_UI_EXACT = {
    "Upvote", "Downvote", "Reply", "Award", "Share", "OP", "•",
    "Go to comments", "Sort by:", "Best", "Search Comments",
    "Expand comment search", "Comments Section", "Join the conversation",
    "Promoted", "Sign Up", "Learn More", "Collapse video player",
    "0:00 / 0:00", "[deleted]", "[removed]",
    "Sorry, this post was deleted by the person who originally posted it.",
}

REDDIT_UI_CONTAINS = [
    "avatar", "bilt.com", "claude.com", "Thumbnail image",
    "Clickable image", "will reveal the video player",
]

REDDIT_TIMESTAMP = re.compile(r"^\d+[ymwdh]o?\s+ago$")
REDDIT_VOTE_COUNT = re.compile(r"^-?\d+$")
REDDIT_USERNAME = re.compile(r"^u/\w")
REDDIT_EDITED = re.compile(r"^Edited \d+[ymwdh]o?\s+ago$")


def is_reddit_noise(line: str) -> bool:
    s = line.strip()
    if s in REDDIT_UI_EXACT:
        return True
    if REDDIT_TIMESTAMP.match(s) or REDDIT_VOTE_COUNT.match(s):
        return True
    if REDDIT_USERNAME.match(s) or REDDIT_EDITED.match(s):
        return True
    if any(tok in s for tok in REDDIT_UI_CONTAINS):
        return True
    return False


def clean_reddit(text: str) -> str:
    lines = [l.rstrip() for l in text.splitlines()]
    cleaned = [l for l in lines if not is_reddit_noise(l)]
    return "\n".join(collapse_blank_lines(cleaned)).strip()


# ---------------------------------------------------------------------------
# Google Reviews cleaner
# ---------------------------------------------------------------------------

GOOGLE_HEADER_DONE = re.compile(
    r"^(Most relevant|Newest|Highest rating|Lowest rating|Yelp Sort)$"
)
YELP_NOISE_EXACT = {
    "Recommended Reviews", "Yelp Sort", "Filter by rating", "Search reviews",
    "Read more", "Overall rating", "Select your rating", "Start your review of",
    "Your trust is our priority, so businesses can't pay to alter or remove their reviews. Learn more about reviews.",
    "Ask the Community", "Ask a question", "People also searched for",
    "Amenities and More", "About the Business", "Location & Hours",
    "Suggest an edit", "Walk-ins welcome", "Accepts credit cards",
    "Accepts cryptocurrency", "Open now", "Claimed",
    "Do you recommend this business?",
    "Business owner information", "Business Owner",
    "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Closed",
    "Open10:00 AM - 5:00 PM",
}
YELP_STARS = re.compile(r"^\d+ stars?$")
YELP_RATING_LINE = re.compile(r"^0\d{1,3}$")               # "010", "0155" etc.
YELP_DATE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+,\s+\d{4}$")
YELP_HOURS = re.compile(r"^\d{1,2}:\d{2}\s+(AM|PM)\s+-\s+\d{1,2}:\d{2}\s+(AM|PM)$")
YELP_PHONE = re.compile(r"^\d{3}-\d{3}-\d{4}$|\*\*\d{3}")
YELP_LOCATION = re.compile(r"^[A-Za-z ,]+,\s+[A-Z]{2}$")   # "Mankato, MN"
GOOGLE_SKIP_EXACT = {
    "All", "Sort by", "Most relevant", "Newest",
    "Highest rating", "Lowest rating",
}
GOOGLE_FILTER_TAG = re.compile(r"^[a-z ]+\d+$")          # e.g. "helpful staff58"
GOOGLE_MORE_TAG = re.compile(r"^\+\d+$")                   # "+6"
GOOGLE_PHOTO_VIDEO = re.compile(r"^(Photo|Video) \d+ in review by")
GOOGLE_REACTION = re.compile(r"^[❤️🙏🤯👍😮\U0001F600-\U0001FFFF\s]+\d*$")
GOOGLE_REVIEWER_META = re.compile(
    r"^(Local Guide·|\d+ reviews?|\d+ photos?|Edited (a |\d+)(year|month|week|day))"
)
GOOGLE_TIME_AGO = re.compile(
    r"^(a |an )?(few )?\d* ?(year|month|week|day|hour)s? ago$|^a (year|month|week|day) ago$"
)
GOOGLE_EDITED_AGO = re.compile(r"^Edited (a |\d+\s*)(year|month|week|day)s?")
GOOGLE_OWNER = re.compile(r"\(Owner\)|(Business Owner)")
GOOGLE_OWNER_BOILERPLATE = re.compile(
    r"^(Thank you (for|so much)|We (are|appreciate|hope|strive|value|understand|take)|"
    r"Dear |If you.d like to discuss|Please (feel free|contact|reach out)|"
    r"We('re| are) (sorry|glad|happy|thrilled|disappointed|committed)|"
    r"Your (feedback|review|trust)|We wish you|appreciate the review|"
    r"We look forward|We sincerely|We want to|We would love|"
    r"you changed your mind|It sounds as though|Please reach out|"
    r"and we (would|can|will) (like|work|help)|Customer Service)",
    re.I,
)
GOOGLE_STAR_LINE = re.compile(r"^\d\.\d$")                 # "4.4"
GOOGLE_REVIEW_COUNT = re.compile(r"^\d+ reviews$")
# Reviewer name lines: short, title-case words only, no sentence punctuation
GOOGLE_NAME_LINE = re.compile(r"^[A-Z][a-zA-ZÀ-ÿ''\- ]{1,45}$")
GOOGLE_TRUNCATED = re.compile(r"[…\.]{1,3}\s*More\s*$")


def clean_google(text: str) -> str:
    lines = [l.rstrip() for l in text.splitlines()]

    # Drop the header block up to and including the sort-order line
    start = 0
    for i, line in enumerate(lines):
        if GOOGLE_HEADER_DONE.match(line.strip()):
            start = i + 1
            break

    lines = lines[start:]

    cleaned = []
    skip_owner_block = False

    owner_lines_skipped = 0

    for line in lines:
        s = line.strip()

        # Owner response blocks: skip from "[Property] (Owner)" until we see
        # a blank line OR have skipped enough lines that the response is done.
        if GOOGLE_OWNER.search(s):
            skip_owner_block = True
            owner_lines_skipped = 0
            continue

        if skip_owner_block:
            owner_lines_skipped += 1
            if s == "" or owner_lines_skipped >= 10:
                skip_owner_block = False
                owner_lines_skipped = 0
            continue

        # Skip owner boilerplate that leaked past the state machine
        if GOOGLE_OWNER_BOILERPLATE.match(s):
            continue

        # Skip Yelp-specific noise
        if s in YELP_NOISE_EXACT:
            continue
        if YELP_STARS.match(s) or YELP_RATING_LINE.match(s):
            continue
        if YELP_DATE.match(s) or YELP_HOURS.match(s) or YELP_PHONE.search(s):
            continue
        if YELP_LOCATION.match(s) and len(s) < 35:
            continue

        # Skip known UI noise
        if s in GOOGLE_SKIP_EXACT:
            continue
        if GOOGLE_FILTER_TAG.match(s) or GOOGLE_MORE_TAG.match(s):
            continue
        if GOOGLE_PHOTO_VIDEO.match(s):
            continue
        if GOOGLE_REACTION.match(s) and len(s) < 20:
            continue
        if GOOGLE_REVIEWER_META.match(s):
            continue
        if GOOGLE_TIME_AGO.match(s) or GOOGLE_EDITED_AGO.match(s):
            continue
        if GOOGLE_STAR_LINE.match(s) or GOOGLE_REVIEW_COUNT.match(s):
            continue
        # Drop lines that are just an address (contain ", MN " pattern after a name line)
        if re.search(r",\s*(MN|Minnesota)\s+\d{5}", s):
            continue
        # Drop standalone "… More" lines
        if s in ("… More", "... More", "…More"):
            continue

        # Strip inline "… More" from end of truncated reviews
        if GOOGLE_TRUNCATED.search(s):
            line = GOOGLE_TRUNCATED.sub("", line).rstrip()
            s = line.strip()

        # Skip reviewer name lines: short, only name-like characters, no sentence punctuation
        if len(s) <= 45 and not any(c in s for c in ".,!?;:@#$%&*=+<>/\\\"") and \
                re.match(r"^[A-Za-zÀ-ÿ0-9 ''\-_()一-鿿]+$", s) and \
                not re.search(r"\b(the|is|are|was|were|have|had|has|not|but|and|for|with|this|they|their|here|very|bad|good|great|poor|place|rent|apart|campus|staff|maint)\b", s, re.I):
            continue

        if not s:
            cleaned.append("")
            continue

        cleaned.append(line)

    return "\n".join(collapse_blank_lines(cleaned)).strip()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def clean_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return 0

    name = path.name.lower()
    if name.startswith("reddit"):
        cleaned = clean_reddit(text)
    elif name.startswith("google") or name.startswith("yelp") or name.startswith("apartmentratings"):
        cleaned = clean_google(text)
    else:
        cleaned = text  # leave unknown files untouched

    path.write_text(cleaned + "\n", encoding="utf-8")
    return len(cleaned.splitlines())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    files = sorted(DOCUMENTS_DIR.glob("*.txt"))
    if not files:
        print("No .txt files found in documents/")
        return

    for path in files:
        lines_out = clean_file(path)
        status = f"{lines_out} lines" if lines_out else "empty — skipped"
        print(f"  {path.name}: {status}")

    # Print one document for spot-check
    sample = DOCUMENTS_DIR / "google-2.txt"
    if sample.exists() and sample.stat().st_size > 0:
        print(f"\n--- Sample: {sample.name} (first 60 lines) ---")
        content = sample.read_text(encoding="utf-8").splitlines()
        for line in content[:60]:
            print(line)
        print(f"... ({len(content)} lines total)")


if __name__ == "__main__":
    main()
