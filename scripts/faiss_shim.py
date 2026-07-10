"""Numpy-based FAISS shim for SkillRetriever.

Provides the minimal API used by retriever.py:
  - normalize_L2(arr)
  - IndexFlatIP(dim) with add(), search(), ntotal
  - write_index(index, path)
  - read_index(path)

For 2209 skills this is trivially fast; no need for real FAISS.
"""
import numpy as np


def normalize_L2(arr):
    """Normalize vectors to unit length (in-place)."""
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1e-12, norms)
    arr /= norms


class IndexFlatIP:
    """Inner product index (cosine similarity after L2 normalization)."""

    def __init__(self, dim):
        self.dim = dim
        self._embeddings = None
        self.ntotal = 0

    def add(self, embeddings):
        self._embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)
        self.ntotal = len(embeddings)

    def search(self, queries, k):
        if self._embeddings is None:
            raise RuntimeError("Index is empty")

        queries = np.ascontiguousarray(queries, dtype=np.float32)
        k = min(k, self.ntotal)

        scores = queries @ self._embeddings.T  # (n_queries, n_skills)

        if k < scores.shape[1]:
            top_indices = np.argpartition(-scores, k, axis=1)[:, :k]
            for i in range(len(top_indices)):
                order = np.argsort(-scores[i, top_indices[i]])
                top_indices[i] = top_indices[i][order]
        else:
            top_indices = np.argsort(-scores, axis=1)[:, :k]

        top_scores = np.take_along_axis(scores, top_indices, axis=1)
        return top_scores.astype(np.float32), top_indices.astype(np.int64)


def write_index(index, path):
    np.save(path, index._embeddings)


def read_index(path):
    embeddings = np.load(path)
    index = IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return index
