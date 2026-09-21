import datetime as dt
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from medical_rag.constants import INDEX_VERSION, SOURCE_POLICIES
from medical_rag.io_utils import read_text_canonical, sha256_file, stable_short_id, write_json, write_jsonl


def _iter_files(root: Path) -> Iterable[Path]:
    yield from sorted((path for path in root.rglob("*.txt") if path.is_file()), key=lambda p: p.as_posix())


def build_scope(corpus_root: Path) -> Dict:
    sources = []
    for folder, policy in SOURCE_POLICIES.items():
        root = corpus_root / folder
        file_count = 0
        byte_count = 0
        if root.exists():
            for directory, _, filenames in __import__("os").walk(str(root)):
                for filename in filenames:
                    file_count += 1
                    try:
                        byte_count += (Path(directory) / filename).stat().st_size
                    except OSError:
                        pass
        sources.append({"folder": folder, "file_count": file_count, "bytes": byte_count, **policy})
    return {
        "index_version": INDEX_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "corpus_root": corpus_root.as_posix(),
        "sources": sources,
    }


def build_manifest(corpus_root: Path, output_path: Path) -> Tuple[List[Dict], Dict]:
    records: List[Dict] = []
    errors = []
    for folder, policy in SOURCE_POLICIES.items():
        if not policy["included"]:
            continue
        source_root = corpus_root / folder
        if not source_root.exists():
            errors.append({"path": source_root.as_posix(), "error": "missing_source_directory"})
            continue
        for path in _iter_files(source_root):
            relative = path.relative_to(corpus_root.parent).as_posix()
            corpus_relative = path.relative_to(corpus_root).as_posix()
            try:
                text, encoding = read_text_canonical(path)
                stat = path.stat()
                record = {
                    "source_id": stable_short_id(corpus_relative),
                    "source_path": relative,
                    "corpus_relative_path": corpus_relative,
                    "dataset_category": policy["category"],
                    "authority_tier": policy["authority_tier"],
                    "included": True,
                    "eligible_as_final_evidence": policy["eligible_as_final_evidence"],
                    "inclusion_reason": policy["reason"],
                    "size_bytes": stat.st_size,
                    "canonical_chars": len(text),
                    "line_count": text.count("\n") + 1,
                    "encoding": encoding,
                    "content_hash": sha256_file(path),
                    "metadata_status": "unknown",
                    "index_version": INDEX_VERSION,
                }
                records.append(record)
            except Exception as exc:
                errors.append({"path": relative, "error": type(exc).__name__, "message": str(exc)})
    records.sort(key=lambda item: item["corpus_relative_path"])
    write_jsonl(output_path, records)
    summary = {
        "index_version": INDEX_VERSION,
        "included_files": len(records),
        "included_bytes": sum(item["size_bytes"] for item in records),
        "by_category": {},
        "errors": errors,
    }
    for item in records:
        group = summary["by_category"].setdefault(item["dataset_category"], {"files": 0, "bytes": 0})
        group["files"] += 1
        group["bytes"] += item["size_bytes"]
    write_json(output_path.with_name("manifest_summary.json"), summary)
    return records, summary

