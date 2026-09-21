import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from medical_rag.io_utils import iter_jsonl


def _query_terms(query: str) -> List[str]:
    terms: List[str] = []
    for sequence in re.findall(r"[\u3400-\u9fff]+", query):
        if len(sequence) < 3:
            continue
        terms.extend(sequence[index : index + 3] for index in range(len(sequence) - 2))
    terms.extend(token for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+-]{2,}", query.lower()))
    return list(dict.fromkeys(terms))[:64]


def build_bm25(
    chunks_path: Path,
    index_path: Path,
    batch_size: int = 2000,
    parents_path: Path = None,
    documents_path: Path = None,
) -> Dict:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = index_path.with_suffix(index_path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(str(temporary))
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=MEMORY;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE documents (
                document_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE parents (
                parent_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                parent_id TEXT NOT NULL,
                authority_tier TEXT NOT NULL,
                eligible_as_final_evidence INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                qdrant_point_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                document_title,
                title_path,
                body,
                chunk_id UNINDEXED,
                tokenize='trigram'
            );
            """
        )
        if documents_path and documents_path.exists():
            connection.executemany(
                "INSERT INTO documents VALUES (?,?)",
                (
                    (item["document_id"], json.dumps(item, ensure_ascii=False, separators=(",", ":")))
                    for item in iter_jsonl(documents_path)
                ),
            )
        if parents_path and parents_path.exists():
            connection.executemany(
                "INSERT INTO parents VALUES (?,?,?,?)",
                (
                    (
                        item["parent_id"],
                        item["document_id"],
                        item["raw_text"],
                        json.dumps(
                            {key: value for key, value in item.items() if key not in {"raw_text", "normalized_text"}},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    )
                    for item in iter_jsonl(parents_path)
                ),
            )
        rows = []
        fts_rows = []
        count = 0
        eligible_count = 0
        for chunk in iter_jsonl(chunks_path):
            count += 1
            eligible = int(bool(chunk["eligible_as_final_evidence"]))
            eligible_count += eligible
            payload = {key: value for key, value in chunk.items() if key not in {"raw_text", "normalized_text", "retrieval_text"}}
            rows.append(
                (
                    chunk["chunk_id"],
                    chunk["document_id"],
                    chunk["parent_id"],
                    chunk["authority_tier"],
                    eligible,
                    chunk["source_path"],
                    chunk["raw_text"],
                    chunk["normalized_text"],
                    str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"])),
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                )
            )
            if eligible:
                fts_rows.append(
                    (
                        chunk["document_title"],
                        " > ".join(chunk["title_path"]),
                        chunk["normalized_text"],
                        chunk["chunk_id"],
                    )
                )
            if len(rows) >= batch_size:
                connection.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
                connection.executemany("INSERT INTO chunks_fts VALUES (?,?,?,?)", fts_rows)
                connection.commit()
                rows.clear()
                fts_rows.clear()
        if rows:
            connection.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            connection.executemany("INSERT INTO chunks_fts VALUES (?,?,?,?)", fts_rows)
        connection.execute("CREATE INDEX idx_chunks_parent ON chunks(parent_id)")
        connection.execute("CREATE INDEX idx_chunks_evidence ON chunks(eligible_as_final_evidence, authority_tier)")
        metadata = {
            "backend": "sqlite_fts5",
            "tokenizer": "trigram",
            "chunk_count": str(count),
            "indexed_evidence_count": str(eligible_count),
            "document_count": str(connection.execute("SELECT count(*) FROM documents").fetchone()[0]),
            "parent_count": str(connection.execute("SELECT count(*) FROM parents").fetchone()[0]),
        }
        connection.executemany("INSERT INTO metadata VALUES (?,?)", metadata.items())
        connection.commit()
        connection.execute("PRAGMA optimize")
    finally:
        connection.close()
    os.replace(str(temporary), str(index_path))
    return {"index_path": str(index_path), "chunk_count": count, "indexed_evidence_count": eligible_count}


def search_bm25(index_path: Path, query: str, limit: int = 10, tiers=("A", "B")) -> List[Dict]:
    terms = _query_terms(query)
    if not terms:
        return []
    expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
    placeholders = ",".join("?" for _ in tiers)
    sql = f"""
        SELECT f.chunk_id, -bm25(chunks_fts, 4.0, 2.0, 1.0, 0.0) AS score,
               c.document_id, c.parent_id, c.authority_tier, c.source_path,
               c.raw_text, c.qdrant_point_id, c.payload_json
        FROM chunks_fts AS f
        JOIN chunks AS c ON c.chunk_id = f.chunk_id
        WHERE chunks_fts MATCH ?
          AND c.eligible_as_final_evidence = 1
          AND c.authority_tier IN ({placeholders})
        ORDER BY bm25(chunks_fts, 4.0, 2.0, 1.0, 0.0)
        LIMIT ?
    """
    connection = sqlite3.connect(str(index_path))
    try:
        rows = connection.execute(sql, [expression, *tiers, limit]).fetchall()
    finally:
        connection.close()
    return [
        {
            "chunk_id": row[0],
            "score": row[1],
            "document_id": row[2],
            "parent_id": row[3],
            "authority_tier": row[4],
            "source_path": row[5],
            "raw_text": row[6],
            "qdrant_point_id": row[7],
            "payload": json.loads(row[8]),
        }
        for row in rows
    ]


def get_parent(index_path: Path, parent_id: str) -> Dict:
    connection = sqlite3.connect(str(index_path))
    try:
        row = connection.execute(
            "SELECT raw_text, payload_json FROM parents WHERE parent_id = ?", (parent_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise KeyError(parent_id)
    result = json.loads(row[1])
    result["raw_text"] = row[0]
    return result


def get_chunks(index_path: Path, chunk_ids: Sequence[str]) -> List[Dict]:
    """Return chunks in caller-supplied order.

    Dense Qdrant payloads intentionally do not duplicate the citation text.  This
    helper hydrates dense hits from the authoritative SQLite copy and is also
    used by hierarchy expansion.  Querying in bounded batches avoids SQLite's
    parameter limit for future, larger candidate sets.
    """
    if not chunk_ids:
        return []
    unique_ids = list(dict.fromkeys(chunk_ids))
    found: Dict[str, Dict] = {}
    connection = sqlite3.connect(str(index_path))
    try:
        for start in range(0, len(unique_ids), 500):
            batch = unique_ids[start : start + 500]
            placeholders = ",".join("?" for _ in batch)
            rows = connection.execute(
                f"""
                SELECT chunk_id, document_id, parent_id, authority_tier,
                       eligible_as_final_evidence, source_path, raw_text,
                       qdrant_point_id, payload_json
                FROM chunks
                WHERE chunk_id IN ({placeholders})
                """,
                batch,
            ).fetchall()
            for row in rows:
                found[row[0]] = {
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "parent_id": row[2],
                    "authority_tier": row[3],
                    "eligible_as_final_evidence": bool(row[4]),
                    "source_path": row[5],
                    "raw_text": row[6],
                    "qdrant_point_id": row[7],
                    "payload": json.loads(row[8]),
                }
    finally:
        connection.close()
    return [found[chunk_id] for chunk_id in chunk_ids if chunk_id in found]


def get_parent_children(index_path: Path, parent_id: str) -> List[Dict]:
    """Return a parent's children in their deterministic source order."""
    parent = get_parent(index_path, parent_id)
    child_ids = parent.get("child_ids", [])
    if child_ids:
        return get_chunks(index_path, child_ids)

    # Compatibility fallback for an older index without child_ids in the
    # parent payload.  The chunk IDs contain zero-padded child ordinals.
    connection = sqlite3.connect(str(index_path))
    try:
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT chunk_id FROM chunks WHERE parent_id = ? ORDER BY chunk_id",
                (parent_id,),
            ).fetchall()
        ]
    finally:
        connection.close()
    return get_chunks(index_path, ids)
