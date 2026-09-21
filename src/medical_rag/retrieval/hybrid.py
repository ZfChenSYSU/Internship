from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from medical_rag.indexing.bm25_sqlite import search_bm25
from medical_rag.retrieval.fusion import reciprocal_rank_fusion
from medical_rag.retrieval.hierarchy import HierarchyConfig, expand_parent_context
from medical_rag.retrieval.models import RetrievalHit, RetrievalResult


def _limit_duplicate_clusters(hits: Sequence[RetrievalHit], maximum: int = 2) -> List[RetrievalHit]:
    counts: Dict[str, int] = {}
    kept = []
    for hit in hits:
        cluster = str(
            hit.payload.get("duplicate_group_id")
            or hit.payload.get("content_hash")
            or hit.chunk_id
        )
        if counts.get(cluster, 0) >= maximum:
            continue
        counts[cluster] = counts.get(cluster, 0) + 1
        kept.append(hit)
    return kept


class HybridRetriever:
    def __init__(
        self,
        bm25_index_path: Path,
        dense_retriever: Optional[Any] = None,
        reranker: Optional[Any] = None,
        bm25_search: Callable[..., List[Dict]] = search_bm25,
        hierarchy_config: Optional[HierarchyConfig] = None,
        bm25_top_k: int = 30,
        dense_top_k: int = 30,
        fused_top_k: int = 40,
        reranked_top_k: int = 12,
        rrf_k: int = 60,
        duplicate_cluster_limit: int = 2,
    ) -> None:
        self.bm25_index_path = Path(bm25_index_path)
        self.dense_retriever = dense_retriever
        self.reranker = reranker
        self.bm25_search = bm25_search
        self.hierarchy_config = hierarchy_config or HierarchyConfig()
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.fused_top_k = fused_top_k
        self.reranked_top_k = reranked_top_k
        self.rrf_k = rrf_k
        self.duplicate_cluster_limit = duplicate_cluster_limit

    def retrieve(
        self,
        query: str,
        tiers: Sequence[str] = ("A", "B"),
        expand_hierarchy: bool = True,
    ) -> RetrievalResult:
        rankings: Dict[str, List[Dict]] = {}
        errors: Dict[str, str] = {}
        try:
            rankings["bm25"] = self.bm25_search(
                self.bm25_index_path,
                query,
                limit=self.bm25_top_k,
                tiers=tiers,
            )
        except Exception as exc:
            errors["bm25"] = f"{type(exc).__name__}: {exc}"
        if self.dense_retriever is not None:
            try:
                rankings["dense"] = self.dense_retriever.search(
                    query,
                    limit=self.dense_top_k,
                    tiers=tiers,
                )
            except Exception as exc:
                errors["dense"] = f"{type(exc).__name__}: {exc}"
        else:
            errors["dense"] = "disabled"

        fused = reciprocal_rank_fusion(rankings, rrf_k=self.rrf_k, limit=self.fused_top_k)
        fused = _limit_duplicate_clusters(fused, self.duplicate_cluster_limit)
        if self.reranker is not None:
            try:
                final_hits = self.reranker.rerank(query, fused, limit=self.reranked_top_k)
            except Exception as exc:
                errors["reranker"] = f"{type(exc).__name__}: {exc}"
                final_hits = fused[: self.reranked_top_k]
        else:
            errors["reranker"] = "disabled"
            final_hits = fused[: self.reranked_top_k]

        evidence = []
        if expand_hierarchy and final_hits:
            try:
                evidence = expand_parent_context(
                    self.bm25_index_path,
                    final_hits,
                    self.hierarchy_config,
                )
            except Exception as exc:
                errors["hierarchy"] = f"{type(exc).__name__}: {exc}"

        trace = {
            "candidate_counts": {name: len(items) for name, items in rankings.items()},
            "fused_count": len(fused),
            "reranked_count": len(final_hits),
            "evidence_count": len(evidence),
            "degraded": bool(errors),
            "errors": errors,
            "parameters": {
                "bm25_top_k": self.bm25_top_k,
                "dense_top_k": self.dense_top_k,
                "rrf_k": self.rrf_k,
                "fused_top_k": self.fused_top_k,
                "reranked_top_k": self.reranked_top_k,
            },
            "rankings": {
                name: [
                    {"chunk_id": item["chunk_id"], "rank": rank, "score": item.get("score")}
                    for rank, item in enumerate(items, start=1)
                ]
                for name, items in rankings.items()
            },
        }
        return RetrievalResult(query=query, hits=final_hits, evidence=evidence, trace=trace)
