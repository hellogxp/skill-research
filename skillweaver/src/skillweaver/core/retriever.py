"""Skill retriever using bi-encoder embeddings + FAISS index.

Adapted from the Compositional Skill Routing paper's SkillRetriever.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

from skillweaver.core.models import Skill, SkillMatch

logger = logging.getLogger(__name__)

# Default embedding model — MiniLM for zero-config (80MB); BGE-large for best quality
DEFAULT_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
QUALITY_ENCODER = "BAAI/bge-large-en-v1.5"
FALLBACK_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"

# BGE models need a query instruction prefix for asymmetric retrieval
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Known HuggingFace mirror endpoints
HF_MIRRORS = [
    "https://hf-mirror.com",
]


def _check_hf_connectivity(timeout: float = 5.0) -> bool:
    """Quick check whether huggingface.co is reachable."""
    import urllib.request

    try:
        req = urllib.request.Request("https://huggingface.co", method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


class SkillRetriever:
    """Retrieves candidate skills for a query using semantic similarity."""

    def __init__(
        self,
        encoder_name: str = DEFAULT_ENCODER,
        use_body: bool = False,
        top_k: int = 10,
        cache_dir: Path | None = None,
    ):
        self.encoder_name = encoder_name
        self.use_body = use_body
        self.top_k = top_k
        self.cache_dir = cache_dir
        self._encoder = None
        self._index = None
        self._skills: list[Skill] = []

    def _load_encoder(self):
        if self._encoder is not None:
            return

        # Check for local cache first (no network needed)
        if self.cache_dir:
            local = self.cache_dir / self.encoder_name.replace("/", "_")
            if local.exists():
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading encoder from cache: {local}")
                self._encoder = SentenceTransformer(str(local))
                return

        # HF_ENDPOINT must be set BEFORE importing huggingface_hub/sentence_transformers,
        # because the library caches the endpoint URL at import time.
        if not os.environ.get("HF_ENDPOINT"):
            if not _check_hf_connectivity():
                logger.info(
                    "Cannot reach huggingface.co, switching to mirror: %s",
                    HF_MIRRORS[0],
                )
                os.environ["HF_ENDPOINT"] = HF_MIRRORS[0]

        from sentence_transformers import SentenceTransformer

        # Try primary model, then fallback
        models_to_try = [self.encoder_name]
        if self.encoder_name != FALLBACK_ENCODER:
            models_to_try.append(FALLBACK_ENCODER)

        for mp in models_to_try:
            try:
                logger.info(f"Loading encoder: {mp}")
                self._encoder = SentenceTransformer(mp)
                if mp != self.encoder_name:
                    logger.warning(
                        f"Using fallback encoder '{mp}' instead of '{self.encoder_name}'. "
                        "Quality may be slightly reduced."
                    )
                return
            except Exception as e:
                logger.warning(f"Failed to load {mp}: {e}")
                continue

        raise RuntimeError(
            f"Could not load any embedding model. Tried: {', '.join(models_to_try)}.\n"
            "Possible fixes:\n"
            "  1. Set HF_ENDPOINT=https://hf-mirror.com before running (China users)\n"
            "  2. Download model manually and pass cache_dir\n"
            "  3. Check your internet connection"
        )

    def build_index(self, skills: list[Skill]) -> None:
        """Build FAISS index from a list of skills."""
        import faiss

        self._load_encoder()
        self._skills = skills

        texts = [s.to_retrieval_text(use_body=self.use_body) for s in skills]

        logger.info(f"Encoding {len(texts)} skills (use_body={self.use_body})...")
        embeddings = self._encoder.encode(
            texts, show_progress_bar=True, batch_size=64
        ).astype(np.float32)

        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings)
        self._embeddings = embeddings

        logger.info(f"Index built: {self._index.ntotal} skills, dim={dim}")

    def _format_query(self, text: str) -> str:
        """Add model-specific prefix if needed (e.g. BGE instruction)."""
        if "bge" in self.encoder_name.lower():
            return BGE_QUERY_PREFIX + text
        return text

    def search(self, query: str, top_k: int | None = None) -> list[SkillMatch]:
        """Search for skills matching a query."""
        import faiss

        self._load_encoder()
        k = top_k or self.top_k

        q_emb = self._encoder.encode(
            [self._format_query(query)], show_progress_bar=False
        ).astype(np.float32)
        faiss.normalize_L2(q_emb)

        scores, indices = self._index.search(q_emb, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._skills):
                results.append(SkillMatch(skill=self._skills[idx], score=float(score)))
        return results

    def search_batch(
        self, queries: list[str], top_k: int | None = None
    ) -> list[list[SkillMatch]]:
        """Batch search for multiple queries."""
        import faiss

        self._load_encoder()
        k = top_k or self.top_k

        q_embs = self._encoder.encode(
            [self._format_query(q) for q in queries],
            show_progress_bar=False, batch_size=64
        ).astype(np.float32)
        faiss.normalize_L2(q_embs)

        scores, indices = self._index.search(q_embs, k)
        all_results = []
        for i in range(len(queries)):
            results = []
            for score, idx in zip(scores[i], indices[i]):
                if 0 <= idx < len(self._skills):
                    results.append(SkillMatch(skill=self._skills[idx], score=float(score)))
            all_results.append(results)
        return all_results

    def save_index(self, path: Path) -> None:
        """Save FAISS index to disk for fast loading."""
        import faiss

        path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path / "index.faiss"))
        np.save(str(path / "embeddings.npy"), self._embeddings)
        logger.info(f"Index saved to {path}")

    def load_index(self, path: Path, skills: list[Skill]) -> None:
        """Load FAISS index from disk."""
        import faiss

        self._skills = skills
        self._index = faiss.read_index(str(path / "index.faiss"))
        self._embeddings = np.load(str(path / "embeddings.npy"))
        logger.info(f"Index loaded: {self._index.ntotal} skills")
