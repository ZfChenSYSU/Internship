import json
from pathlib import Path

from medical_rag.indexing.bm25_sqlite import build_bm25, search_bm25


def test_bm25_build_and_filter(tmp_path: Path):
    chunks = tmp_path / "chunks.jsonl"
    rows = [
        {
            "chunk_id": "a/1",
            "document_id": "a",
            "parent_id": "p1",
            "authority_tier": "A",
            "eligible_as_final_evidence": True,
            "source_path": "a.txt",
            "document_title": "脑积水指南",
            "title_path": ["诊断"],
            "normalized_text": "脑积水的诊断需要结合影像学检查。",
            "raw_text": "脑积水的诊断需要结合影像学检查。",
            "retrieval_text": "脑积水指南 诊断 脑积水的诊断需要结合影像学检查。",
        },
        {
            "chunk_id": "c/1",
            "document_id": "c",
            "parent_id": "p2",
            "authority_tier": "C",
            "eligible_as_final_evidence": False,
            "source_path": "c.txt",
            "document_title": "网页",
            "title_path": [],
            "normalized_text": "脑积水广告。",
            "raw_text": "脑积水广告。",
            "retrieval_text": "网页 脑积水广告。",
        },
    ]
    chunks.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
    index = tmp_path / "bm25.sqlite3"
    result = build_bm25(chunks, index)
    assert result["chunk_count"] == 2
    hits = search_bm25(index, "如何诊断脑积水？")
    assert [item["chunk_id"] for item in hits] == ["a/1"]
    assert hits[0]["raw_text"] == "脑积水的诊断需要结合影像学检查。"
