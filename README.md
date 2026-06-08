# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

Off-campus student housing near Minnesota State University, Mankato (MNSU). The university's official housing page lists recommended properties but provides no student reviews, no aggregated ratings, and no way to compare options side by side. Students are left scraping Reddit, asking friends, or signing leases blind. This system aggregates real student reviews from Reddit, Google, Yelp, and ApartmentRatings into a single queryable knowledge base, so a prospective student can ask "What do students say about Highland Hills maintenance?" and get a grounded, source-cited answer rather than a generic LLM response drawn from training data.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | Reddit r/Mankato | Reddit thread | https://www.reddit.com/r/Mankato/comments/gyp9zv/moving_to_mankato_soon_looking_for_an_affordable/ |
| 2 | Reddit r/Mankato | Reddit thread | https://www.reddit.com/r/Mankato/comments/1n0s58g/highland_hills_apartments/ |
| 3 | Reddit r/Mankato | Reddit thread | https://www.reddit.com/r/Mankato/comments/1qf3ngh/the_grove/ |
| 4 | ApartmentRatings | Review site | https://www.apartmentratings.com/mn/mankato/the-summit_507388254356001/ |
| 5 | Google Reviews | Google Maps | College Town Mankato — google.com search |
| 6 | Google Reviews | Google Maps | Highland Hills — google.com search |
| 7 | Google Reviews | Google Maps | College Station — google.com search |
| 8 | Google Reviews | Google Maps | The Summit & Jacob Heights — google.com search |
| 9 | Yelp | Review site | The Summit & Jacob Heights — yelp.com |
| 10 | Yelp | Review site | General Mankato apartments — yelp.com |

---

## Chunking Strategy

**Chunk size:** One review per chunk — no fixed character or token limit. Reviews in this corpus are typically 50–200 words each. The final word count per chunk ranged from 15 to 399 words, averaging 70 words.

**Overlap:** None. Reviews are atomic units — a 75-word review is already the smallest meaningful signal. Splitting it mid-sentence to create overlap would destroy the only context it contains, and overlapping two unrelated reviews from different people would introduce noise rather than useful context.

**Why these choices fit your documents:** Student reviews are self-contained opinions. Unlike a long technical document where adjacent paragraphs share context, each review stands alone. Forcing a fixed-token chunker onto this corpus would either split single reviews mid-thought (losing meaning) or merge multiple reviews into one chunk (making attribution impossible). The one-review-per-chunk approach preserves the integrity of each reviewer's full opinion and makes source attribution exact.

**Preprocessing before chunking:** A `clean_documents.py` script ran before chunking to strip UI chrome from each source. For Reddit, this removed vote buttons, timestamps, usernames, and promoted content. For Google/Yelp, it removed star ratings, reviewer metadata, photo references, owner response blocks (detected by a state machine triggered on "American Campus Communities" and "(Owner)" lines), and any line containing an email address. Chunks shorter than 15 words were dropped as fragments.

**Final chunk count:** 344 chunks across 10 documents covering 7 properties.

---

## Embedding Model

**Model used:** `all-MiniLM-L6-v2` via `sentence-transformers`. This model runs locally with no API key, produces 384-dimensional vectors, and processes 344 short review chunks in under 5 seconds on CPU. It was the right choice for a student project where inference cost and setup complexity need to be minimal, and the text is plain English short reviews with no specialized vocabulary.

**Production tradeoff reflection:** For a real deployment serving students, I would evaluate two upgrades. First, `all-mpnet-base-v2` produces higher-quality embeddings for nuanced opinion language — it would better distinguish "maintenance is slow but eventually shows up" from "maintenance never responds," which `all-MiniLM-L6-v2` tends to score similarly. Second, a hybrid retrieval approach (BM25 keyword search combined with dense vector search) would help queries that include specific property names or amenity keywords that the embedding model sometimes under-weights relative to sentiment language. The bigger production lever, however, is metadata pre-filtering: letting users filter by `property_name` before the vector search would eliminate cross-property noise in the top-k results without requiring a more powerful model.

---

## Grounded Generation

**System prompt grounding instruction:** The system prompt explicitly prohibits the model from using training knowledge, not merely suggests grounding. The exact instruction given to llama-3.3-70b-versatile is:

> "Use ONLY the information in the provided review excerpts. Do NOT draw on your training knowledge about apartments, Mankato, or anything else. If the reviews do not contain enough information to answer the question, respond with exactly: 'I don't have enough information in the reviews to answer that.'"

The model is also instructed to cite the bracket number of supporting reviews (e.g. "according to review [2]") whenever it states a fact, and to present conflicting opinions explicitly rather than averaging them.

**How source attribution is surfaced in the response:** Source attribution is built programmatically from chunk metadata *before* the Groq API call — the LLM never generates citation strings. After retrieval, each chunk's `property_name`, `source`, and cosine distance are assembled into a deduplicated source list in Python. This list is returned alongside the LLM answer and displayed in a separate "Retrieved from" panel in the Gradio UI, so attribution is structurally guaranteed regardless of what the model writes.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What are affordable off-campus housing options close to Minnesota State University, Mankato? | Highland Hills, The Summit | Cited Highland Hills as affordable and close to campus from reviews [1]–[3],[5]; noted College Town as a good MNSU option | Relevant | Accurate |
| 2 | What do students say about maintenance at Highland Hills? | Mixed — some say they are happy with the timeliness while others are dissatisfied | Reported maintenance as generally prompt and efficient — missed negative maintenance reviews in the corpus | Partially relevant | Partially accurate |
| 3 | What do students say about cleanliness at The Grove? | Reports of dirty and untidy units on move-in | Noted apartment "was not very clean" on move-in with dog hair found (review [3]); 3 of 5 retrieved chunks were from other properties | Partially relevant | Partially accurate |
| 4 | What do students say about move-in conditions and fees at The Summit? | Same conditions as advertised | Retrieved only positive chunks about furnished units and included utilities; missed all negative fee/cleanliness reviews in the corpus | Off-target | Inaccurate |
| 5 | Is College Station Apartments a good option for students near MNSU? | Mixed — some praise responsive maintenance and great management, others report broken appliances on move-in, inconsistent heating, and noise issues | Returned positive reviews citing helpful management and quick maintenance; did not surface negative reviews | Partially relevant | Partially accurate |

---

## Failure Case Analysis

**Question that failed:** "What do students say about move-in conditions and fees at The Summit?"

**What the system returned:** The system retrieved five chunks that described The Summit positively — specifically that units are fully furnished, utilities are included in rent, and maintenance is responsive. The generated answer reflected only these positive aspects and said nothing about dirty move-in conditions or unexpected fees, even though such reviews exist in the corpus (yelp-1.txt and google-4.txt contain multiple reviews describing cockroaches, dirty units, bogus cleaning charges, and fee disputes).

**Root cause (tied to a specific pipeline stage):** This is a **retrieval failure** caused by a semantic mismatch at the embedding stage. The query "move-in conditions and fees" has a semantic neighborhood that includes words like "furnished," "utilities included," "rent," and "move-in ready" — which are exactly the words positive Summit reviews use. The negative reviews that would actually answer the query use different vocabulary: "dirty," "disgusting," "charged," "scam," "cleaning fee after move-out." The `all-MiniLM-L6-v2` embedding model encoded the query into a vector that was geometrically closer to positive move-in language than to the negative complaint vocabulary, so the top-5 results by cosine distance were all positive chunks. The negative reviews existed in ChromaDB but ranked outside the top-5.

**What you would change to fix it:** Two targeted fixes would help. First, rewrite the query to include complaint vocabulary: "dirty apartments fees charged Summit move-out" would embed closer to the negative reviews. Second, increase top-k from 5 to 10 and add a sentiment-diversity step — for example, retrieve 10 chunks and select the 5 with the most varied cosine distances from each other, which would force inclusion of both positive and negative semantic clusters rather than the 5 most similar chunks converging on one sentiment.

---

## Spec Reflection

**One way the spec helped you during implementation:** The chunking strategy section of planning.md — specifically the decision to use one review per chunk with no overlap — prevented a significant implementation mistake. My first instinct when writing chunk.py was to use a fixed 200-token sliding window with 50-token overlap, which is the standard approach for long documents. Reading back the spec's reasoning ("splitting a 75-word review mid-sentence destroys the only signal it contains") stopped me from implementing that. The spec forced me to think about what the atomic unit of meaning was for *this* corpus specifically, rather than applying a generic chunking recipe.

**One way your implementation diverged from the spec, and why:** The spec listed `date` as a metadata field per chunk ("management changes make old reviews misleading"). The implementation does not store dates. When cleaning the documents, reviewer dates were stripped as noise (they appeared in the same format as other UI chrome), and re-extracting them would have required per-source parsing logic for each of Reddit, Google, Yelp, and ApartmentRatings. Given that all source documents were collected at the same time and span roughly the same recent period, omitting dates did not meaningfully hurt retrieval quality for this project. In a production system handling a growing corpus over months, dates would be essential for filtering out stale reviews after a property changes management.

---

## AI Usage

**Instance 1 — Document cleaning pipeline**

- *What I gave the AI:* The raw copy-pasted text from Google Reviews and Yelp, a description of what constituted noise (vote buttons, star ratings, reviewer names, timestamps, owner response blocks, email addresses), and the requirement that the output preserve only substantive review text with blank-line separators between reviews.
- *What it produced:* `clean_documents.py` with regex-based noise filters and a state-machine for owner response blocks triggered on "(Owner)" lines.
- *What I changed or overrode:* The initial state machine only triggered on "(Owner)" — but Yelp owner responses used "American Campus Communities A." as the business name, not "(Owner)". I directed the AI to extend the trigger pattern to also match "American Campus Communities" and "Business owner information". I also had to direct it to add a maximum-line-skip of 10 as a fallback when owner responses had no blank-line terminator, because College Station's owner responses ran directly into the next review with no separator, causing the state machine to skip entire legitimate reviews.

**Instance 2 — Grounded generation and Gradio interface**

- *What I gave the AI:* The planning.md pipeline diagram, the `retrieve()` function signature from retrieve.py, and the requirement that answers must be grounded in retrieved chunks only, with source attribution structurally guaranteed rather than left to the LLM.
- *What it produced:* `generate.py` with a system prompt, a context block builder, and a Groq API call, plus `app.py` with a Gradio interface.
- *What I changed or overrode:* The first draft of the system prompt said "try to use only the provided documents" — a suggestion, not a constraint. I directed the AI to rewrite it as a hard prohibition: "Do NOT draw on your training knowledge" with an explicit fallback phrase ("I don't have enough information in the reviews to answer that") required when the documents don't cover the question. I also directed it to move source attribution entirely out of the LLM response and into a programmatic post-processing step so the model could never fabricate or omit citations.
