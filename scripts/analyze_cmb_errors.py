"""Draw a reproducible sample of incorrect CMB answers for manual review.

The dossier is written beside ignored evaluation results because it contains
benchmark questions and excerpts from the local corpus.
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

from medical_rag.evaluation.cmb import load_cmb


def _rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _evidence(conn: sqlite3.Connection, chunk_ids: list, excerpt_chars: int) -> list:
    result = []
    seen_parents = set()
    for chunk_id in chunk_ids:
        row = conn.execute(
            "SELECT parent_id, payload_json FROM chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Missing evidence chunk: {chunk_id}")
        parent_id, payload_json = row
        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)
        parent = conn.execute(
            "SELECT raw_text FROM parents WHERE parent_id = ?", (parent_id,)
        ).fetchone()
        if parent is None:
            raise ValueError(f"Missing evidence parent: {parent_id}")
        payload = json.loads(payload_json)
        result.append({
            "parent_id": parent_id,
            "title": payload.get("document_title") or "",
            "section": " > ".join(payload.get("title_path") or []),
            "excerpt": parent[0][:excerpt_chars].replace("\n", " "),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample CMB errors and build a review dossier")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--bm25-index", type=Path, required=True)
    parser.add_argument("--experiment", default="E5")
    parser.add_argument("--fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--excerpt-chars", type=int, default=350)
    args = parser.parse_args()
    if not 0 < args.fraction <= 1:
        raise ValueError("--fraction must be in (0, 1]")
    if args.excerpt_chars < 1:
        raise ValueError("--excerpt-chars must be positive")

    manifest = json.loads((args.results / "manifest.json").read_text(encoding="utf-8"))
    selected_ids = manifest["selected_ids"]
    questions = {item.source_id: item for item in load_cmb(args.questions, args.answers)}
    rows = _rows(args.results / "predictions.jsonl")
    by_key = {}
    for row in rows:
        key = (row["source_id"], row["experiment"])
        if key in by_key:
            raise ValueError(f"Duplicate result: {key}")
        by_key[key] = row
    if any((source_id, args.experiment) not in by_key for source_id in selected_ids):
        raise ValueError(f"Incomplete {args.experiment} results; finish the run before sampling")

    errors = [by_key[source_id, args.experiment] for source_id in selected_ids
              if not by_key[source_id, args.experiment]["correct"]]
    count = round(len(errors) * args.fraction)
    sampled_ids = set(random.Random(args.seed).sample([row["source_id"] for row in errors], count))
    sampled = [row for row in errors if row["source_id"] in sampled_ids]

    conn = sqlite3.connect(f"file:{args.bm25_index.resolve()}?mode=ro", uri=True)
    try:
        cases = []
        for row in sampled:
            source_id = row["source_id"]
            question = questions[source_id]
            cases.append({
                "source_id": source_id,
                "question": question.question,
                "options": question.options,
                "gold": question.gold,
                "is_multiple": question.is_multiple,
                "exam_type": question.exam_type,
                "exam_subject": question.exam_subject,
                "answers_by_experiment": {
                    group: by_key[source_id, group].get("prediction")
                    for group in manifest["groups"] if (source_id, group) in by_key
                },
                "evidence": _evidence(conn, row.get("evidence_chunk_ids") or [], args.excerpt_chars),
            })
    finally:
        conn.close()

    payload = {
        "experiment": args.experiment,
        "population_questions": len(selected_ids),
        "error_population": len(errors),
        "sample_fraction_requested": args.fraction,
        "sample_size": len(cases),
        "sample_fraction_actual": len(cases) / len(errors) if errors else 0,
        "seed": args.seed,
        "sampled_ids": [case["source_id"] for case in cases],
        "cases": cases,
    }
    (args.results / "error_sample.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# {args.experiment} 错题复核样本",
        "",
        f"错题总体：{len(errors)}；固定种子：{args.seed}；抽样：{len(cases)} 题"
        f"（{payload['sample_fraction_actual']:.1%}）。",
        "",
        "以下证据摘要由已记录的 chunk ID 回查父节点索引，用于人工判因；它不是模型推理过程。",
    ]
    for case in cases:
        lines += [
            "",
            f"## ID {case['source_id']} · {case['exam_type']} · {case['exam_subject']}",
            "",
            case["question"],
            "",
            *[f"- {letter}. {value or '〔原始选项为空〕'}" for letter, value in case["options"].items()],
            "",
            f"标准答案：{case['gold']}；各组答案：{case['answers_by_experiment']}",
            "",
            "检索证据：",
            "",
        ]
        for index, item in enumerate(case["evidence"], start=1):
            lines.append(f"{index}. {item['title']} / {item['section']} — {item['excerpt']}")
    (args.results / "error_sample_dossier.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{args.experiment}: {len(errors)} errors; sampled {len(cases)} ({payload['sample_fraction_actual']:.1%})")
    print("sampled IDs:", ",".join(payload["sampled_ids"]))


if __name__ == "__main__":
    main()
