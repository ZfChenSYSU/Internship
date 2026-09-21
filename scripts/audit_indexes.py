#!/usr/bin/env python3
"""Audit corpus_v1 BM25/Qdrant identity and payload consistency."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bm25", type=Path, default=Path("data/indexes/corpus_v1/bm25.sqlite3"))
    parser.add_argument("--qdrant", type=Path, default=Path("data/indexes/corpus_v1/qdrant"))
    parser.add_argument("--collection", default="corpus_v1_children")
    args = parser.parse_args()

    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise SystemExit("请使用 .venv/bin/python 运行，或安装 qdrant-client。") from exc

    database = sqlite3.connect(str(args.bm25))
    try:
        expected = {
            row[0]: row[1]
            for row in database.execute(
                "SELECT chunk_id, qdrant_point_id FROM chunks WHERE eligible_as_final_evidence = 1"
            )
        }
        metadata = dict(database.execute("SELECT key, value FROM metadata"))
    finally:
        database.close()

    client = QdrantClient(path=str(args.qdrant.resolve()))
    seen = {}
    bad_payload = []
    bad_point_ids = []
    offset = None
    try:
        info = client.get_collection(args.collection)
        while True:
            points, offset = client.scroll(
                args.collection,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                chunk_id = payload.get("chunk_id")
                point_id = str(point.id)
                if (
                    not chunk_id
                    or payload.get("eligible_as_final_evidence") is not True
                    or payload.get("authority_tier") not in {"A", "B"}
                    or payload.get("index_version") != "corpus_v1"
                ):
                    bad_payload.append(point_id)
                if chunk_id and expected.get(chunk_id) != point_id:
                    bad_point_ids.append(point_id)
                if chunk_id:
                    seen[chunk_id] = point_id
            if offset is None:
                break
    finally:
        client.close()

    missing = sorted(set(expected) - set(seen))
    extra = sorted(set(seen) - set(expected))
    vectors = info.config.params.vectors
    report = {
        "collection": args.collection,
        "collection_status": str(info.status),
        "vector_dimension": vectors.size,
        "distance": str(vectors.distance),
        "bm25_metadata": metadata,
        "expected_eligible_chunks": len(expected),
        "qdrant_points": len(seen),
        "missing": len(missing),
        "extra": len(extra),
        "bad_payload": len(bad_payload),
        "bad_point_ids": len(bad_point_ids),
        "passed": not (missing or extra or bad_payload or bad_point_ids) and vectors.size == 1024,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

