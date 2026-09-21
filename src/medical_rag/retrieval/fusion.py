from typing import Any, Dict, Iterable, List, Mapping, Sequence

from medical_rag.retrieval.models import RetrievalHit


def _as_hit(item: Mapping[str, Any], source: str, rank: int) -> RetrievalHit:
    payload = dict(item.get("payload") or {})
    return RetrievalHit(
        chunk_id=str(item["chunk_id"]),
        document_id=str(item.get("document_id") or payload.get("document_id") or ""),
        parent_id=str(item.get("parent_id") or payload.get("parent_id") or ""),
        authority_tier=str(item.get("authority_tier") or payload.get("authority_tier") or ""),
        source_path=str(item.get("source_path") or payload.get("source_path") or ""),
        raw_text=str(item.get("raw_text") or ""),
        payload=payload,
        ranks={source: rank},
        scores={source: float(item.get("score", 0.0))},
    )


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
    rrf_k: int = 60,
    limit: int = 40,
) -> List[RetrievalHit]:
    """Fuse rankings without mixing incomparable source scores.

    Ranks are one-based, as in the original RRF definition.  Duplicate chunk
    IDs within one source contribute only once.  Ties are deterministic, which
    keeps offline experiment outputs reproducible.
    """
    if rrf_k < 0:
        raise ValueError("rrf_k must be non-negative")
    if limit < 1:
        return []

    fused: Dict[str, RetrievalHit] = {}
    for source, items in rankings.items():
        seen = set()
        source_rank = 0
        for item in items:
            chunk_id = str(item["chunk_id"])
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            source_rank += 1
            contribution = 1.0 / (rrf_k + source_rank)
            if chunk_id not in fused:
                fused[chunk_id] = _as_hit(item, source, source_rank)
            else:
                hit = fused[chunk_id]
                hit.ranks[source] = source_rank
                hit.scores[source] = float(item.get("score", 0.0))
                # Prefer hydrated citation text and metadata when only one
                # source (normally BM25/SQLite) supplied it.
                if not hit.raw_text and item.get("raw_text"):
                    hit.raw_text = str(item["raw_text"])
                if not hit.payload and item.get("payload"):
                    hit.payload = dict(item["payload"])
            fused[chunk_id].rrf_score += contribution

    return sorted(
        fused.values(),
        key=lambda hit: (
            -hit.rrf_score,
            min(hit.ranks.values()),
            hit.chunk_id,
        ),
    )[:limit]
