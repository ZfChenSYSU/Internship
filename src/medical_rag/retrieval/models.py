from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalHit:
    chunk_id: str
    document_id: str
    parent_id: str
    authority_tier: str
    source_path: str
    raw_text: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ranks: Dict[str, int] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    rrf_score: float = 0.0
    reranker_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceWindow:
    window_id: str
    document_id: str
    parent_id: str
    child_ids: List[str]
    text: str
    document_title: str
    title_path: List[str]
    authority_tier: str
    source_path: str
    source_char_start: Optional[int]
    source_char_end: Optional[int]
    score: float
    used_full_parent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    query: str
    hits: List[RetrievalHit]
    evidence: List[EvidenceWindow]
    trace: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "hits": [hit.to_dict() for hit in self.hits],
            "evidence": [window.to_dict() for window in self.evidence],
            "trace": self.trace,
        }
