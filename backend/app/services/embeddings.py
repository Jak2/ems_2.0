"""Embeddings helper using sentence-transformers.

Provides a small wrapper to compute normalized embeddings for a list of texts.
This keeps embedding-related code in one place and allows swapping models later.
"""

from typing import List
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


class Embeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers not installed")
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Return L2-normalized embeddings as a numpy array (float32).

        The caller may pass multiple texts. Result shape = (len(texts), dim)
        """
        emb = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # normalize to unit length (useful for cosine search with inner product)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        emb = emb / norms
        return emb.astype("float32")
