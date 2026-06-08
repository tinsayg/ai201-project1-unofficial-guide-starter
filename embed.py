"""
Milestone 3 — Embedding + Vector Store

Pipeline position (from planning.md):
  Chunking → Embedding (all-MiniLM-L6-v2) → Vector Store (ChromaDB)

What this script does:
  1. Loads all chunks from chunks.json (output of chunk.py)
  2. Embeds each chunk's text with sentence-transformers all-MiniLM-L6-v2
  3. Persists embeddings + metadata into a local ChromaDB collection

ChromaDB API notes:
  - PersistentClient writes the vector store to disk (chroma_db/).
  - get_or_create_collection is idempotent — safe to re-run; it won't
    duplicate records because we delete and recreate the collection first.
  - collection.add() takes parallel lists: ids, embeddings, documents
    (the raw text), and metadatas (dicts of string → string/int).
  - Embeddings are plain Python lists of floats — no special type needed.
"""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

CHUNKS_FILE = Path("chunks.json")
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "housing_reviews"
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 64  # embed this many chunks at once to avoid OOM on large corpora


def main():
    # --- 1. Load chunks ---
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}")

    # --- 2. Load embedding model (runs locally, no API key needed) ---
    print(f"Loading embedding model: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)

    # --- 3. Embed all chunk texts in batches ---
    texts = [c["text"] for c in chunks]
    print(f"Embedding {len(texts)} chunks in batches of {BATCH_SIZE} ...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    # embeddings shape: (num_chunks, 384)  — all-MiniLM-L6-v2 produces 384-dim vectors

    # --- 4. Connect to ChromaDB (creates chroma_db/ if it doesn't exist) ---
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection so re-runs start clean (no duplicate IDs)
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass  # collection didn't exist yet

    collection = client.create_collection(
        name=COLLECTION_NAME,
        # cosine similarity is more robust than L2 for sentence embeddings
        metadata={"hnsw:space": "cosine"},
    )
    print(f"Created collection '{COLLECTION_NAME}'")

    # --- 5. Add chunks to ChromaDB ---
    # ChromaDB requires all four parallel lists to have the same length.
    # - ids:        unique string identifier per chunk
    # - embeddings: the float vectors we just computed
    # - documents:  the raw text (stored so we can return it at query time)
    # - metadatas:  dict of extra fields attached to each chunk
    ids = [c["id"] for c in chunks]
    metadatas = [
        {
            "property_name": c["property_name"],
            "source":        c["source"],
            "url":           c["url"],
            "word_count":    c["word_count"],
        }
        for c in chunks
    ]

    # Add in batches — ChromaDB handles large inserts fine but batching is
    # good practice and gives a progress indicator.
    for start in range(0, len(chunks), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(chunks))
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end].tolist(),
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )

    print(f"\nStored {collection.count()} embeddings in ChromaDB ({CHROMA_DIR}/)")
    print("Embedding complete. Run retrieve.py to test retrieval.")


if __name__ == "__main__":
    main()
