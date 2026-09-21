import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from medical_rag.indexing.bm25_sqlite import get_parent, get_parent_children
from medical_rag.retrieval.models import EvidenceWindow, RetrievalHit


@dataclass
class HierarchyConfig:
    neighbour_children: int = 1
    max_windows_per_parent: int = 2
    max_windows_per_document: int = 3
    final_windows: int = 8
    context_budget_chars: int = 12000
    min_window_chars: int = 240
    max_full_parent_chars: int = 2200


_CONTEXT_CUES = re.compile(
    r"(?:上述|如下|下列|见表|见图|前述|后者|其中|分别|本节|该方案|该药|其一|其二)"
)
_LEADING_CUE = re.compile(r"^(?:但|而|且|并且|此外|同时|因此|故|其|该|此|上述|对于|其中)")


def _requires_full_parent(seed_texts: Sequence[str], expanded_text: str, minimum: int) -> bool:
    if len(expanded_text.strip()) < minimum:
        return True
    return any(_CONTEXT_CUES.search(text) or _LEADING_CUE.search(text.strip()) for text in seed_texts)


def _merge_texts(texts: Sequence[str]) -> str:
    if not texts:
        return ""
    result = texts[0]
    for text in texts[1:]:
        max_overlap = min(200, len(result), len(text))
        overlap = next(
            (size for size in range(max_overlap, 15, -1) if result[-size:] == text[:size]),
            0,
        )
        separator = "" if overlap else "\n"
        result += separator + text[overlap:]
    return result


def _ranges(indices: Sequence[int], radius: int) -> List[Tuple[int, int]]:
    pending = sorted((max(0, index - radius), index + radius) for index in set(indices))
    merged: List[Tuple[int, int]] = []
    for start, end in pending:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _slice_parent(parent: Dict, children: Sequence[Dict], start: int, end: int) -> Tuple[str, Optional[int], Optional[int]]:
    chosen = children[start : end + 1]
    offsets = [
        (
            item["payload"].get("source_char_start"),
            item["payload"].get("source_char_end"),
        )
        for item in chosen
    ]
    parent_start = parent.get("source_char_start")
    parent_end = parent.get("source_char_end")
    if (
        parent_start is not None
        and parent_end is not None
        and offsets
        and all(left is not None and right is not None for left, right in offsets)
    ):
        source_start = min(left for left, _ in offsets)
        source_end = max(right for _, right in offsets)
        if parent_start <= source_start <= source_end <= parent_end:
            return (
                parent["raw_text"][source_start - parent_start : source_end - parent_start],
                source_start,
                source_end,
            )
    return _merge_texts([item["raw_text"] for item in chosen]), None, None


def expand_parent_context(
    index_path: Path,
    hits: Sequence[RetrievalHit],
    config: Optional[HierarchyConfig] = None,
) -> List[EvidenceWindow]:
    """Cluster reranked children and expand them to bounded evidence windows."""
    config = config or HierarchyConfig()
    grouped: Dict[str, List[Tuple[int, RetrievalHit]]] = {}
    for rank, hit in enumerate(hits, start=1):
        grouped.setdefault(hit.parent_id, []).append((rank, hit))

    candidates: List[EvidenceWindow] = []
    for parent_id, ranked_hits in grouped.items():
        parent = get_parent(index_path, parent_id)
        children = get_parent_children(index_path, parent_id)
        child_positions = {item["chunk_id"]: index for index, item in enumerate(children)}
        seeds = [child_positions[hit.chunk_id] for _, hit in ranked_hits if hit.chunk_id in child_positions]
        if not seeds:
            continue
        best_rank = min(rank for rank, _ in ranked_hits)
        # The best child should dominate parent ordering; repeated hits are a
        # bounded corroboration bonus, not permission for a broad but less
        # relevant parent to leapfrog the top diagnostic passage.
        group_score = 1.0 / best_rank + 0.05 * min(len(ranked_hits) - 1, 3)
        ranges = _ranges(seeds, config.neighbour_children)
        ranges = [
            (start, min(end, len(children) - 1))
            for start, end in ranges
        ]
        ranges.sort(
            key=lambda value: min(
                (
                    rank
                    for rank, hit in ranked_hits
                    if hit.chunk_id in child_positions
                    and value[0] <= child_positions[hit.chunk_id] <= value[1]
                ),
                default=10**9,
            )
        )
        for range_index, (start, end) in enumerate(ranges[: config.max_windows_per_parent]):
            chosen = children[start : end + 1]
            text, source_start, source_end = _slice_parent(parent, children, start, end)
            seed_texts = [
                hit.raw_text
                for _, hit in ranked_hits
                if hit.chunk_id in child_positions and start <= child_positions[hit.chunk_id] <= end
            ]
            use_full_parent = (
                len(parent["raw_text"]) <= config.max_full_parent_chars
                and _requires_full_parent(seed_texts, text, config.min_window_chars)
            )
            if use_full_parent:
                text = parent["raw_text"]
                source_start = parent.get("source_char_start")
                source_end = parent.get("source_char_end")
                chosen = children
            candidates.append(
                EvidenceWindow(
                    window_id=f"{parent_id}/window{range_index:02d}",
                    document_id=str(parent["document_id"]),
                    parent_id=parent_id,
                    child_ids=[item["chunk_id"] for item in chosen],
                    text=text,
                    document_title=str(parent.get("document_title") or ""),
                    title_path=list(parent.get("title_path") or []),
                    authority_tier=ranked_hits[0][1].authority_tier,
                    source_path=str(parent.get("source_path") or ranked_hits[0][1].source_path),
                    source_char_start=source_start,
                    source_char_end=source_end,
                    score=group_score - 0.001 * range_index,
                    used_full_parent=use_full_parent,
                )
            )

    candidates.sort(key=lambda window: (-window.score, window.window_id))
    selected: List[EvidenceWindow] = []
    parent_counts: Dict[str, int] = {}
    document_counts: Dict[str, int] = {}
    used_chars = 0
    for window in candidates:
        if len(selected) >= config.final_windows:
            break
        if parent_counts.get(window.parent_id, 0) >= config.max_windows_per_parent:
            continue
        if document_counts.get(window.document_id, 0) >= config.max_windows_per_document:
            continue
        if selected and used_chars + len(window.text) > config.context_budget_chars:
            continue
        selected.append(window)
        used_chars += len(window.text)
        parent_counts[window.parent_id] = parent_counts.get(window.parent_id, 0) + 1
        document_counts[window.document_id] = document_counts.get(window.document_id, 0) + 1
    return selected
