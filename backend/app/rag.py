import glob
import os
import re

import chromadb
import numpy as np
from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, EMBED_MODEL, KB_DIR, CHROMA_DIR

_client = genai.Client(api_key=GEMINI_API_KEY)
_chroma = chromadb.PersistentClient(path=CHROMA_DIR)
COLLECTION = "zari_kb"


def _slug(text):
    """'Delivery time' -> 'delivery-time'"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_chunks():
    """Split every kb/*.md file into one chunk per '## ' heading."""
    chunks = []
    for path in sorted(glob.glob(os.path.join(KB_DIR, "*.md"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for part in re.split(r"\n(?=## )", text):
            lines = part.strip().splitlines()
            if not lines or not lines[0].startswith("## "):
                continue  # skips the '# Title' line at the top of each file
            heading = lines[0][3:].strip()
            body = " ".join(l.strip() for l in lines[1:] if l.strip())
            chunks.append({
                "id": f"{stem}#{_slug(heading)}",
                "source": stem,
                "heading": heading,
                "text": f"{heading}: {body}",
            })
    return chunks


def _embed(texts, task_type):
    """Turn texts into unit-length embedding vectors."""
    res = _client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    vecs = np.array([e.values for e in res.embeddings], dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs.tolist()


def build_index():
    """(Re)build the vector database from the kb/ folder."""
    chunks = load_chunks()
    try:
        _chroma.delete_collection(COLLECTION)
    except Exception:
        pass  # first run: nothing to delete
    col = _chroma.create_collection(COLLECTION)
    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{"source": c["source"], "heading": c["heading"]} for c in chunks],
        embeddings=_embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT"),
    )
    return len(chunks)


def search(query, k=3):
    """Return the k most similar chunks, each with a similarity score from -1 to 1."""
    col = _chroma.get_collection(COLLECTION)
    res = col.query(
        query_embeddings=_embed([query], "RETRIEVAL_QUERY"),
        n_results=k,
    )
    results = []
    for chunk_id, doc, dist in zip(res["ids"][0], res["documents"][0], res["distances"][0]):
        results.append({
            "id": chunk_id,
            "text": doc,
            "score": round(1 - dist / 2, 3),
        })
    return results