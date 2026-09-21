import json
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from medical_rag.chunking.source_aware import chunk_document
from medical_rag.ingestion.manifest import build_manifest, build_scope
from medical_rag.io_utils import iter_jsonl, read_text_canonical, write_json, write_jsonl


def prepare_corpus(corpus_root: Path, data_root: Path) -> Dict:
    manifests = data_root / "manifests"
    processed = data_root / "processed" / "corpus_v1"
    manifests.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    scope = build_scope(corpus_root)
    write_json(manifests / "corpus_scope.json", scope)
    records, manifest_summary = build_manifest(corpus_root, manifests / "corpus_v1.jsonl")

    documents: List[Dict] = []
    parents: List[Dict] = []
    chunks: List[Dict] = []
    errors = []
    for index, record in enumerate(records, start=1):
        try:
            document, new_parents, new_chunks = chunk_document(corpus_root.parent, record)
            documents.append(document)
            parents.extend(new_parents)
            chunks.extend(new_chunks)
        except Exception as exc:
            errors.append({"source_path": record["source_path"], "error": type(exc).__name__, "message": str(exc)})

    documents_path = processed / "documents.jsonl"
    parents_path = processed / "parents.jsonl"
    chunks_path = processed / "chunks.jsonl"
    write_jsonl(documents_path, documents)
    write_jsonl(parents_path, parents)
    write_jsonl(chunks_path, chunks)

    parent_ids = {item["parent_id"] for item in parents}
    lengths = sorted(len(item["raw_text"]) for item in chunks)
    replay_errors = 0
    corpus_parent = corpus_root.parent
    source_cache = {}
    for chunk in chunks:
        path = corpus_parent / chunk["source_path"]
        if path not in source_cache:
            source_cache[path] = read_text_canonical(path)[0]
        replayed = source_cache[path][chunk["source_char_start"] : chunk["source_char_end"]]
        if replayed != chunk["raw_text"]:
            replay_errors += 1

    def percentile(values: List[int], ratio: float) -> int:
        if not values:
            return 0
        return values[min(len(values) - 1, int((len(values) - 1) * ratio))]

    report = {
        "manifest": manifest_summary,
        "documents": len(documents),
        "parents": len(parents),
        "chunks": len(chunks),
        "eligible_chunks": sum(bool(item["eligible_as_final_evidence"]) for item in chunks),
        "chunks_by_tier": {
            tier: sum(item["authority_tier"] == tier for item in chunks) for tier in ("A", "B")
        },
        "chunk_length": {
            "min": lengths[0] if lengths else 0,
            "p50": percentile(lengths, 0.5),
            "p95": percentile(lengths, 0.95),
            "max": lengths[-1] if lengths else 0,
        },
        "orphan_chunks": sum(item["parent_id"] not in parent_ids for item in chunks),
        "replay_errors": replay_errors,
        "empty_chunks": sum(not item["normalized_text"] for item in chunks),
        "manual_review_chunks": sum(bool(item["needs_manual_review"]) for item in chunks),
        "processing_errors": errors,
    }
    write_json(processed / "quality_report.json", report)
    return report

