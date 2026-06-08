"""
Milestone 5 — Grounded Generation

Pipeline position (from planning.md):
  Retrieval (top-k=5) → Generation (Groq llama-3.3-70b) → Answer + Sources

What this module does:
  1. Retrieves the top-5 most relevant chunks for the user's query
  2. Builds a numbered context block from those chunks
  3. Sends a grounding-enforced prompt to Groq's llama-3.3-70b-versatile
  4. Returns the LLM answer AND a programmatically-built source list

Grounding design:
  - System prompt PROHIBITS the model from using training knowledge
  - "I don't have enough information" response is explicitly required when
    the retrieved chunks don't cover the question
  - Source attribution is assembled from chunk metadata BEFORE calling the
    LLM — it is never left to the model to generate or invent citations
"""

import os
from groq import Groq
from dotenv import load_dotenv
from retrieve import load_retriever, retrieve

load_dotenv()

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once, reused by app.py
# ---------------------------------------------------------------------------

_model = None
_collection = None
_groq_client = None


def _ensure_loaded():
    global _model, _collection, _groq_client
    if _model is None:
        print("Loading embedding model and ChromaDB...")
        _model, _collection = load_retriever()
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        print(f"Ready — {_collection.count()} chunks in vector store.")


# ---------------------------------------------------------------------------
# System prompt — grounding enforced, not merely suggested
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a student housing assistant for Minnesota State University, Mankato.
You answer questions about off-campus housing ONLY using the numbered student \
reviews provided in the user message.

RULES — you must follow all of these without exception:
1. Use ONLY the information in the provided review excerpts. Do NOT draw on \
your training knowledge about apartments, Mankato, or anything else.
2. If the reviews do not contain enough information to answer the question, \
respond with exactly: "I don't have enough information in the reviews to answer that."
3. When you state a fact, name which review(s) support it using its bracket \
number, e.g. "according to review [2]" or "reviews [1] and [4] both mention".
4. If the reviews contain conflicting opinions, present both sides explicitly \
rather than averaging them into one verdict.
5. Do not speculate, generalize, or add any information beyond what is in the reviews.
6. Keep your answer concise — a few sentences to a short paragraph is enough.\
"""

# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def ask(query: str, k: int = 5) -> dict:
    """
    Run end-to-end grounded Q&A.

    Returns:
        {
            "answer":  str   — LLM answer grounded in retrieved text
            "sources": list  — deduplicated source strings, built from metadata
            "chunks":  list  — raw retrieved chunks (for debugging / display)
        }
    """
    _ensure_loaded()

    # --- 1. Retrieve top-k chunks ---
    chunks = retrieve(query, _model, _collection, k=k)

    # --- 2. Build numbered context block ---
    context_parts = []
    for i, c in enumerate(chunks, 1):
        header = f"[{i}] Property: {c['property_name']} | Source: {c['source']}"
        context_parts.append(f"{header}\n{c['text']}")
    context_block = "\n\n".join(context_parts)

    user_message = (
        f"Student reviews:\n\n{context_block}\n\n"
        f"Question: {query}"
    )

    # --- 3. Call Groq ---
    response = _groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,   # low temperature for factual, consistent answers
        max_tokens=512,
    )
    answer = response.choices[0].message.content.strip()

    # --- 4. Build source list programmatically from metadata ---
    # Deduplicate while preserving order; never let the LLM fabricate citations.
    seen = set()
    sources = []
    for c in chunks:
        label = f"{c['property_name']} — {c['source']} (dist={c['distance']})"
        if label not in seen:
            seen.add(label)
            sources.append(label)

    return {"answer": answer, "sources": sources, "chunks": chunks}


# ---------------------------------------------------------------------------
# Standalone test — run directly to verify grounded generation
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What are affordable off-campus housing options close to MNSU?",
    "What do students say about maintenance at Highland Hills?",
    "What do students say about move-in conditions and fees at The Summit?",
    # Out-of-corpus query — system should say it doesn't have enough info
    "What is the average commute time from The Grove to downtown Minneapolis?",
]

if __name__ == "__main__":
    _ensure_loaded()

    for query in TEST_QUERIES:
        print("\n" + "=" * 72)
        print(f"QUERY: {query}")
        print("=" * 72)
        result = ask(query)
        print(f"\nANSWER:\n{result['answer']}")
        print("\nSOURCES:")
        for s in result["sources"]:
            print(f"  • {s}")
