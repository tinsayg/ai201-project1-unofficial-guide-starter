"""
Milestone 4 — Retrieval

Pipeline position (from planning.md):
  Vector Store (ChromaDB) → Retrieval (top-k=5) → Generation

What this script does:
  1. Loads the same embedding model used in embed.py
  2. Connects to the existing ChromaDB collection
  3. Embeds the user's query and finds the top-k most similar chunks
  4. Returns each chunk's text + source metadata

ChromaDB query API note:
  collection.query() takes:
    - query_embeddings: the embedded query vector (list of lists)
    - n_results:        how many chunks to return
  It returns a dict with parallel lists:
    - "documents":  [[chunk_text, ...]]   — outer list is per query
    - "metadatas":  [[{...}, ...]]
    - "distances":  [[float, ...]]        — cosine distance (lower = more similar)
    - "ids":        [[chunk_id, ...]]
"""

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "housing_reviews"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K = 5


def load_retriever():
    """Return (model, collection) — call once and reuse in generate.py."""
    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)
    return model, collection


def retrieve(query: str, model, collection, k: int = TOP_K) -> list[dict]:
    """
    Embed query and return the top-k most relevant chunks.

    Returns a list of dicts, each with:
        text          — the chunk content
        property_name — which apartment complex
        source        — Reddit | Google Reviews | Yelp | ApartmentRatings
        url           — original source URL
        distance      — cosine distance (0 = identical, 2 = opposite)
    """
    query_embedding = model.encode(query, convert_to_numpy=True).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
    )

    # results["documents"] is [[text1, text2, ...]] — one list per query
    chunks = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":          text,
            "property_name": meta["property_name"],
            "source":        meta["source"],
            "url":           meta["url"],
            "distance":      round(dist, 4),
        })

    return chunks


# ---------------------------------------------------------------------------
# Quick test — run directly to verify retrieval is working
# ---------------------------------------------------------------------------

# Evaluation plan queries from planning.md
EVAL_QUERIES = [
    ("Q1", "What are affordable off-campus housing options close to Minnesota State University, Mankato?"),
    ("Q2", "What do students say about maintenance at Highland Hills?"),
    ("Q3", "What do students say about cleanliness at The Grove?"),
    ("Q4", "What do students say about move-in conditions and fees at The Summit?"),
    ("Q5", "Is College Station Apartments a good option for students near MNSU?"),
]

if __name__ == "__main__":
    print("Loading model and ChromaDB collection...")
    model, collection = load_retriever()
    print(f"Collection has {collection.count()} chunks\n")

    for label, query in EVAL_QUERIES:
        print("=" * 72)
        print(f"[{label}] {query}")
        print("=" * 72)
        chunks = retrieve(query, model, collection)
        for i, c in enumerate(chunks, 1):
            print(f"\n  [{i}] property={c['property_name']} | source={c['source']} | dist={c['distance']}")
            print(f"  {c['text'].encode('ascii', errors='replace').decode()}")
        print()
