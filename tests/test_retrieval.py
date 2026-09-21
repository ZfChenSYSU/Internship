import json
from pathlib import Path

from medical_rag.indexing.bm25_sqlite import build_bm25
from medical_rag.model_utils import resolve_cached_model
from medical_rag.reranking.bge import BGEReranker
from medical_rag.retrieval.fusion import reciprocal_rank_fusion
from medical_rag.retrieval.hierarchy import HierarchyConfig, expand_parent_context
from medical_rag.retrieval.hybrid import HybridRetriever


def _write_jsonl(path: Path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture_index(tmp_path: Path) -> Path:
    parent_text = "诊断总则。\n需要结合症状。\n影像学检查可支持诊断。"
    pieces = ["诊断总则。", "需要结合症状。", "影像学检查可支持诊断。"]
    starts = [parent_text.index(piece) for piece in pieces]
    chunks = []
    child_ids = []
    for index, (piece, start) in enumerate(zip(pieces, starts)):
        chunk_id = f"doc/sec/ch{index:05d}"
        child_ids.append(chunk_id)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": "doc",
                "parent_id": "doc/sec",
                "authority_tier": "A",
                "eligible_as_final_evidence": True,
                "source_path": "source.txt",
                "document_title": "脑积水共识",
                "title_path": ["诊断"],
                "normalized_text": piece,
                "raw_text": piece,
                "retrieval_text": f"脑积水共识 诊断 {piece}",
                "source_char_start": start,
                "source_char_end": start + len(piece),
                "content_hash": f"hash-{index}",
            }
        )
    parents = [
        {
            "parent_id": "doc/sec",
            "document_id": "doc",
            "document_title": "脑积水共识",
            "title_path": ["诊断"],
            "source_path": "source.txt",
            "source_char_start": 0,
            "source_char_end": len(parent_text),
            "raw_text": parent_text,
            "normalized_text": parent_text,
            "child_ids": child_ids,
        }
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    parents_path = tmp_path / "parents.jsonl"
    _write_jsonl(chunks_path, chunks)
    _write_jsonl(parents_path, parents)
    index_path = tmp_path / "bm25.sqlite3"
    build_bm25(chunks_path, index_path, parents_path=parents_path)
    return index_path


def test_rrf_preserves_ranks_scores_and_deduplicates():
    bm25 = [
        {"chunk_id": "a", "score": 8.0, "document_id": "d", "parent_id": "p"},
        {"chunk_id": "b", "score": 7.0, "document_id": "d", "parent_id": "p"},
    ]
    dense = [
        {"chunk_id": "b", "score": 0.9, "document_id": "d", "parent_id": "p"},
        {"chunk_id": "c", "score": 0.8, "document_id": "d", "parent_id": "p"},
    ]
    hits = reciprocal_rank_fusion({"bm25": bm25, "dense": dense}, rrf_k=60, limit=10)
    assert [hit.chunk_id for hit in hits] == ["b", "a", "c"]
    assert hits[0].ranks == {"bm25": 2, "dense": 1}
    assert hits[0].scores == {"bm25": 7.0, "dense": 0.9}
    assert hits[0].rrf_score == 1 / 62 + 1 / 61


def test_model_cache_resolves_snapshot_without_ref(tmp_path: Path):
    snapshot = tmp_path / "models--BAAI--bge-m3" / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    assert resolve_cached_model("BAAI/bge-m3", tmp_path) == str(snapshot)


class _FakeCrossEncoder:
    def predict(self, pairs, **kwargs):
        return [float(len(passage)) for _, passage in pairs]


def test_bge_wrapper_reranks_without_loading_a_model():
    hits = reciprocal_rank_fusion(
        {
            "bm25": [
                {"chunk_id": "short", "document_id": "d", "parent_id": "p", "raw_text": "短"},
                {"chunk_id": "long", "document_id": "d", "parent_id": "p", "raw_text": "更长的证据"},
            ]
        }
    )
    reranked = BGEReranker(model=_FakeCrossEncoder()).rerank("问题", hits)
    assert [hit.chunk_id for hit in reranked] == ["long", "short"]
    assert reranked[0].reranker_score > reranked[1].reranker_score


def test_parent_expansion_adds_neighbours_and_exact_offsets(tmp_path: Path):
    index_path = _fixture_index(tmp_path)
    raw = [
        {
            "chunk_id": "doc/sec/ch00001",
            "score": 1.0,
            "document_id": "doc",
            "parent_id": "doc/sec",
            "authority_tier": "A",
            "source_path": "source.txt",
            "raw_text": "需要结合症状。",
        }
    ]
    hit = reciprocal_rank_fusion({"bm25": raw})[0]
    windows = expand_parent_context(
        index_path,
        [hit],
        HierarchyConfig(neighbour_children=1, min_window_chars=0),
    )
    assert len(windows) == 1
    assert windows[0].text == "诊断总则。\n需要结合症状。\n影像学检查可支持诊断。"
    assert windows[0].child_ids == [
        "doc/sec/ch00000",
        "doc/sec/ch00001",
        "doc/sec/ch00002",
    ]
    assert windows[0].source_char_start == 0
    assert windows[0].source_char_end == len(windows[0].text)


class _FakeDense:
    def search(self, query, limit, tiers):
        return [
            {
                "chunk_id": "doc/sec/ch00002",
                "score": 0.95,
                "document_id": "doc",
                "parent_id": "doc/sec",
                "authority_tier": "A",
                "source_path": "source.txt",
                "raw_text": "影像学检查可支持诊断。",
                "payload": {"content_hash": "hash-2"},
            }
        ]


def test_hybrid_pipeline_runs_all_stages(tmp_path: Path):
    index_path = _fixture_index(tmp_path)
    retriever = HybridRetriever(
        index_path,
        dense_retriever=_FakeDense(),
        reranker=BGEReranker(model=_FakeCrossEncoder()),
    )
    result = retriever.retrieve("脑积水如何诊断？")
    assert result.trace["candidate_counts"]["bm25"] >= 1
    assert result.trace["candidate_counts"]["dense"] == 1
    assert result.trace["degraded"] is False
    assert result.hits
    assert result.evidence
    assert any("dense" in hit.ranks for hit in result.hits)
