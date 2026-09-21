from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

from medical_rag.indexing.dense_qdrant import _device
from medical_rag.model_utils import resolve_cached_model
from medical_rag.retrieval.models import RetrievalHit


class BGEReranker:
    """Small-batch cross-encoder wrapper for BGE reranker v2 M3."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "auto",
        batch_size: int = 4,
        max_length: int = 512,
        cache_dir: Optional[Union[str, Path]] = Path("models/huggingface"),
        model: Optional[Any] = None,
    ) -> None:
        self.batch_size = batch_size
        if model is not None:
            self.model = model
        else:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError("BGE reranking requires: pip install -e '.[dense]'") from exc
            self.model = CrossEncoder(
                resolve_cached_model(model_name, cache_dir),
                device=_device(device),
                max_length=max_length,
                trust_remote_code=True,
                cache_folder=str(cache_dir) if cache_dir is not None else None,
            )

    @staticmethod
    def _passage(hit: RetrievalHit) -> str:
        title = str(hit.payload.get("document_title") or "")
        title_path = hit.payload.get("title_path") or []
        heading = " > ".join(str(item) for item in title_path)
        return "\n".join(item for item in (title, heading, hit.raw_text) if item)

    def rerank(self, query: str, hits: Sequence[RetrievalHit], limit: int = 12) -> List[RetrievalHit]:
        if not hits or limit < 1:
            return []
        pairs = [(query, self._passage(hit)) for hit in hits]
        values = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        for hit, value in zip(hits, values):
            if hasattr(value, "item"):
                value = value.item()
            hit.reranker_score = float(value)
        original_order = {hit.chunk_id: rank for rank, hit in enumerate(hits)}
        return sorted(
            hits,
            key=lambda hit: (
                -float(hit.reranker_score),
                original_order[hit.chunk_id],
                hit.chunk_id,
            ),
        )[:limit]
