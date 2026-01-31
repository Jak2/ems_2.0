"""Simple FAISS-backed vector store for demo purposes.

This module provides a compact vectorstore implementation suitable for a PoC:
- Persists the FAISS index to disk (`index.faiss`).
- Persists metadata (mapping vector ids to employee_id and text) in `meta.json`.

Note: For production use consider a dedicated vector DB or sharded/per-employee indices.
"""

import os
import json
from typing import List, Dict, Optional
import numpy as np

try:
    import faiss
except Exception:
    faiss = None

from app.services.embeddings import Embeddings


class FaissVectorStore:
    """A simple single-index FAISS vector store with metadata persisted to disk.

    Metadata is kept as a list in `meta.json`. The FAISS index is stored as `index.faiss`.
    This implementation is small-scale and intended for demo/PoC usage.
    """

    def __init__(self, path: str):
        if faiss is None:
            raise RuntimeError("faiss not available")
        self.path = path
        os.makedirs(self.path, exist_ok=True)
        self.index_path = os.path.join(self.path, "index.faiss")
        self.meta_path = os.path.join(self.path, "meta.json")
        self.emb = Embeddings()
        self._load()

    def _load(self):
        self.meta: List[Dict] = []
        self.dim: Optional[int] = None
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            except Exception:
                self.meta = []
        if os.path.exists(self.index_path):
            try:
                self.index = faiss.read_index(self.index_path)
                self.dim = self.index.d
            except Exception:
                self.index = None
        else:
            self.index = None

    def _save_meta(self):
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False)

    def _save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)

    def add_chunks(self, employee_id: int, chunks: List[str]):
        """Compute embeddings for chunks and add them to the index with metadata.

        Returns the ids added.
        """
        if not chunks:
            return []
        vecs = self.emb.embed_texts(chunks)
        n, dim = vecs.shape
        if self.index is None:
            self.dim = dim
            # Use IndexFlatIP on normalized embeddings for cosine similarity
            self.index = faiss.IndexFlatIP(dim)
        elif dim != self.dim:
            raise RuntimeError("Embedding dimension mismatch")

        # append vectors
        start_id = len(self.meta)
        self.index.add(vecs)
        # update metadata
        for i, txt in enumerate(chunks):
            self.meta.append({"id": start_id + i, "employee_id": employee_id, "text": txt})
        self._save_meta()
        self._save_index()
        return list(range(start_id, start_id + n))

    def search(self, query: str, top_k: int = 5, employee_id: Optional[int] = None) -> List[Dict]:
        """Search with a text query and optionally filter by employee_id. Returns list of metadata dicts with score."""
        if self.index is None or len(self.meta) == 0:
            return []
        qvec = self.emb.embed_texts([query])
        D, I = self.index.search(qvec, min(top_k * 5, len(self.meta)))
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            m = self.meta[idx].copy()
            m["score"] = float(score)
            if employee_id is None or m.get("employee_id") == employee_id:
                results.append(m)
            if len(results) >= top_k:
                break
        return results
