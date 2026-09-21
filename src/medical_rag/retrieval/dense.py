from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from medical_rag.indexing.bm25_sqlite import get_chunks
from medical_rag.indexing.dense_qdrant import _device
from medical_rag.model_utils import resolve_cached_model


class DenseRetriever:
    """Reusable BGE-M3 encoder plus Qdrant child-passage search."""

    def __init__(
        self,
        qdrant_path: Path,
        metadata_index_path: Path,
        collection: str = "corpus_v1_children",
        model_name: str = "BAAI/bge-m3",
        device: str = "auto",
        max_length: int = 512,
        cache_dir: Optional[Union[str, Path]] = Path("models/huggingface"),
        client: Optional[Any] = None,
        encoder: Optional[Any] = None,
    ) -> None:
        self.metadata_index_path = Path(metadata_index_path)
        self.collection = collection
        if client is None or encoder is None:
            try:
                from qdrant_client import QdrantClient
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("Dense retrieval requires: pip install -e '.[dense]'") from exc
        self.client = client or QdrantClient(path=str(qdrant_path))
        self.encoder = encoder or SentenceTransformer(
            resolve_cached_model(model_name, cache_dir),
            device=_device(device),
            trust_remote_code=True,
            cache_folder=str(cache_dir) if cache_dir is not None else None,
        )
        if hasattr(self.encoder, "max_seq_length"):
            self.encoder.max_seq_length = max_length

    def search(self, query: str, limit: int = 30, tiers: Sequence[str] = ("A", "B")) -> List[Dict]:
        from qdrant_client import models

        if not query.strip() or limit < 1:
            return []
        vector = self.encoder.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="eligible_as_final_evidence",
                    match=models.MatchValue(value=True),
                ),
                models.FieldCondition(
                    key="authority_tier",
                    match=models.MatchAny(any=list(tiers)),
                ),
            ]
        )
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector.tolist() if hasattr(vector, "tolist") else vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        points = list(response.points)
        hydrated = {
            item["chunk_id"]: item
            for item in get_chunks(
                self.metadata_index_path,
                [str(point.payload["chunk_id"]) for point in points],
            )
        }
        results = []
        for point in points:
            payload = dict(point.payload or {})
            chunk_id = str(payload["chunk_id"])
            stored = hydrated.get(chunk_id, {})
            results.append(
                {
                    "chunk_id": chunk_id,
                    "score": float(point.score),
                    "document_id": stored.get("document_id", payload.get("document_id", "")),
                    "parent_id": stored.get("parent_id", payload.get("parent_id", "")),
                    "authority_tier": stored.get("authority_tier", payload.get("authority_tier", "")),
                    "source_path": stored.get("source_path", payload.get("source_path", "")),
                    "raw_text": stored.get("raw_text", ""),
                    "payload": stored.get("payload", payload),
                }
            )
        return results

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            close()
