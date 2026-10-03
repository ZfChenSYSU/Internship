"""Run CMB-Exam E0-E7 accuracy ablations against the existing corpus_v1 index."""

import argparse
import csv
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from medical_rag.evaluation.cmb import CMBQuestion, load_cmb, paired_comparisons, parse_prediction, score_rows
from medical_rag.indexing.bm25_sqlite import search_bm25
from medical_rag.retrieval.fusion import reciprocal_rank_fusion
from medical_rag.retrieval.hierarchy import expand_parent_context
from medical_rag.retrieval.hybrid import _limit_duplicate_clusters


ROOT = Path(__file__).resolve().parents[3]
GROUPS = tuple(f"E{index}" for index in range(8))
PROMPT_VERSION = "cmb_accuracy_v2"
SYSTEM_PROMPT = (
    "你正在参加中文医学选择题评测。根据题目和选项选择正确答案；检索资料仅供参考，可能不相关。"
    "单选只选一个，多选选出全部正确项。请在内部完成判断，不展示推理、分析、解释、引用或标题。"
    "整个回复必须恰好只有一行，格式为 FINAL_ANSWER: A 或 FINAL_ANSWER: ABC。"
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class EvidencePipeline:
    """The same retrieval components as production, exposed at each ablation cut."""

    def __init__(self, bm25_path: Path, qdrant_path: Path, cache_dir: Path, device: str) -> None:
        from medical_rag.reranking.bge import BGEReranker
        from medical_rag.retrieval.dense import DenseRetriever

        self.bm25_path = bm25_path
        self.dense = DenseRetriever(qdrant_path, bm25_path, device=device, cache_dir=cache_dir)
        self.reranker = BGEReranker(device=device, cache_dir=cache_dir)
        self.query = ""
        self.cache: Dict[str, object] = {}

    def close(self) -> None:
        self.dense.close()

    def set_question(self, question: CMBQuestion) -> None:
        self.query = question.prompt_question()
        self.cache = {}

    def _bm25(self) -> list:
        if "bm25" not in self.cache:
            self.cache["bm25"] = search_bm25(self.bm25_path, self.query, limit=30)
        return self.cache["bm25"]

    def _dense(self) -> list:
        if "dense" not in self.cache:
            self.cache["dense"] = self.dense.search(self.query, limit=30)
        return self.cache["dense"]

    def _fused(self) -> list:
        if "fused" not in self.cache:
            fused = reciprocal_rank_fusion({"bm25": self._bm25(), "dense": self._dense()}, rrf_k=60, limit=40)
            self.cache["fused"] = _limit_duplicate_clusters(fused, maximum=2)
        return self.cache["fused"]

    def _reranked(self) -> list:
        if "reranked" not in self.cache:
            self.cache["reranked"] = self.reranker.rerank(self.query, self._fused(), limit=12)
        return self.cache["reranked"]

    @staticmethod
    def _children(hits: Sequence[object]) -> list:
        evidence = []
        used_chars = 0
        for hit in hits:
            if len(evidence) >= 8:
                break
            text = hit.raw_text.strip()
            if not text or (evidence and used_chars + len(text) > 12000):
                continue
            payload = hit.payload
            evidence.append({
                "id": f"S{len(evidence) + 1}",
                "text": text,
                "title": str(payload.get("document_title") or ""),
                "section": " > ".join(payload.get("title_path") or []),
                "chunk_ids": [hit.chunk_id],
            })
            used_chars += len(text)
        return evidence

    def evidence_for(self, group: str) -> list:
        if group == "E0":
            return []
        if group == "E1":
            hits = reciprocal_rank_fusion({"dense": self._dense()}, limit=8)
            return self._children(hits)
        if group == "E2":
            hits = reciprocal_rank_fusion({"bm25": self._bm25()}, limit=8)
            return self._children(hits)
        if group == "E3":
            return self._children(self._fused()[:8])
        if group == "E4":
            return self._children(self._reranked()[:8])
        if group in {"E5", "E6", "E7"}:
            if "parent_evidence" not in self.cache:
                windows = expand_parent_context(self.bm25_path, self._reranked())
                self.cache["parent_evidence"] = [
                    {
                        "id": f"S{index}",
                        "text": window.text,
                        "title": window.document_title,
                        "section": " > ".join(window.title_path),
                        "chunk_ids": window.child_ids,
                    }
                    for index, window in enumerate(windows, start=1)
                ]
            return self.cache["parent_evidence"]
        raise ValueError(f"Unknown experiment: {group}")


class DeepSeekClient:
    def __init__(self, key_file: Path, model: str, max_tokens: int) -> None:
        self.api_key = key_file.read_text(encoding="utf-8").strip()
        if not self.api_key:
            raise ValueError("DeepSeek API key file is empty")
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.load(response)
                choice = result["choices"][0]
                return {
                    "text": str(choice.get("message", {}).get("content") or ""),
                    "usage": result.get("usage") or {},
                    "request_id": result.get("id"),
                    "finish_reason": choice.get("finish_reason"),
                    "seconds": round(time.perf_counter() - started, 3),
                }
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f"DeepSeek HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"DeepSeek connection failed: {type(exc).__name__}") from exc
            time.sleep(2**attempt)
        raise RuntimeError("DeepSeek request failed")


def _evidence_text(evidence: list) -> str:
    if not evidence:
        return "（无检索资料）"
    return "\n\n".join(
        f"[{item['id']}] {item['title']} / {item['section']}\n{item['text']}"
        for item in evidence
    )


def make_messages(question: CMBQuestion, evidence: list, group: str, previous: Optional[str]) -> tuple:
    user = f"题目：\n{question.prompt_question()}\n\n检索资料：\n{_evidence_text(evidence)}"
    system = SYSTEM_PROMPT
    if group == "E6":
        system += " 请在内部复核上一轮答案与题意和检索资料是否一致；可以改选，仍只输出一行最终答案。"
        user += f"\n\n上一轮答案：{previous or '未解析'}"
    elif group == "E7":
        system += (
            " 请在内部判断是否有把握。若无法确定，可输出 FINAL_ANSWER: ABSTAIN；"
            "否则给出合法选项。仍只输出一行最终答案。"
        )
        user += f"\n\n上一轮答案：{previous or '未解析'}"
    user += "\n\n请只输出一行 FINAL_ANSWER，不要写分析。"
    return system, user


def _load_existing(path: Path) -> Dict[tuple, dict]:
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[(row["source_id"], row["experiment"])] = row
    return result


def _groups(value: str) -> List[str]:
    groups = [part.strip().upper() for part in value.split(",") if part.strip()]
    if not groups or len(set(groups)) != len(groups) or any(group not in GROUPS for group in groups):
        raise ValueError("--experiments must contain distinct E0...E7 group names")
    if "E6" in groups and "E5" not in groups:
        raise ValueError("E6 requires E5 in the same run")
    if "E7" in groups and "E6" not in groups:
        raise ValueError("E7 requires E6 in the same run")
    return sorted(groups, key=GROUPS.index)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CMB-Exam E0-E7 accuracy ablations")
    parser.add_argument("--questions", type=Path, required=True, help="Official CMB merged exam JSON")
    parser.add_argument("--answers", type=Path, help="Optional separate official answer JSON")
    parser.add_argument("--output", type=Path, default=Path("data/eval/results/cmb_smoke"))
    parser.add_argument("--experiments", default=",".join(GROUPS))
    parser.add_argument("--limit", type=int, help="Fixed seeded sample size; omit for all questions")
    parser.add_argument("--ids", help="Comma-separated official IDs; CMB-val uses zero-based row numbers")
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--api-key-file", type=Path, default=ROOT / "deepseek_apikey.txt")
    parser.add_argument("--max-output-tokens", type=int, default=128)
    parser.add_argument("--max-api-calls", type=int, help="Stop after this many new model completions")
    parser.add_argument("--bm25-index", type=Path, default=ROOT / "data/indexes/corpus_v1/bm25.sqlite3")
    parser.add_argument("--qdrant-path", type=Path, default=ROOT / "data/indexes/corpus_v1/qdrant")
    parser.add_argument("--model-cache", type=Path, default=ROOT / "models/huggingface")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    groups = _groups(args.experiments)
    if args.max_api_calls is not None and args.max_api_calls < 1:
        raise ValueError("--max-api-calls must be positive")
    questions = load_cmb(args.questions, args.answers)
    if args.ids and args.limit is not None:
        raise ValueError("Use either --ids or --limit")
    if args.ids:
        requested = [value.strip() for value in args.ids.split(",") if value.strip()]
        if len(set(requested)) != len(requested):
            raise ValueError("Duplicate --ids")
        selected = set(requested)
        questions = [question for question in questions if question.source_id in selected]
        if len(questions) != len(selected):
            raise ValueError("Some --ids were not found in the CMB input")
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        selected = set(random.Random(args.seed).sample(range(len(questions)), min(args.limit, len(questions))))
        questions = [question for index, question in enumerate(questions) if index in selected]
    if not questions:
        raise ValueError("No questions selected")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    corpus_manifest = ROOT / "data/manifests/corpus_v1.jsonl"
    manifest = {
        "questions_sha256": file_hash(args.questions),
        "answers_sha256": file_hash(args.answers) if args.answers else None,
        "corpus_manifest_sha256": file_hash(corpus_manifest) if corpus_manifest.exists() else None,
        "runner_sha256": file_hash(Path(__file__)),
        "scoring_sha256": file_hash(Path(__file__).with_name("cmb.py")),
        "selected_ids": [question.source_id for question in questions],
        "groups": groups,
        "model": args.model,
        "prompt_version": PROMPT_VERSION,
        "seed": args.seed,
        "max_output_tokens": args.max_output_tokens,
        "device": args.device,
        "bm25_index": str(args.bm25_index.resolve()),
        "qdrant_path": str(args.qdrant_path.resolve()),
    }
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if {key: value for key, value in existing_manifest.items() if key != "groups"} != {
            key: value for key, value in manifest.items() if key != "groups"
        }:
            raise ValueError("Run manifest differs; use a new --output directory")
        manifest["groups"] = sorted(set(existing_manifest["groups"]) | set(groups), key=GROUPS.index)
    manifest_path.write_text(_json(manifest) + "\n", encoding="utf-8")
    rows_path = output / "predictions.jsonl"
    completed = _load_existing(rows_path)
    client = DeepSeekClient(args.api_key_file, args.model, args.max_output_tokens)
    needs_retrieval = any(group != "E0" for group in groups)
    pipeline = EvidencePipeline(args.bm25_index, args.qdrant_path, args.model_cache, args.device) if needs_retrieval else None
    new_api_calls = 0
    try:
        with rows_path.open("a", encoding="utf-8") as stream:
            for index, question in enumerate(questions, start=1):
                if pipeline is not None:
                    pipeline.set_question(question)
                for group in groups:
                    key = (question.source_id, group)
                    if key in completed and completed[key].get("status") != "failed":
                        continue
                    evidence = pipeline.evidence_for(group) if pipeline is not None else []
                    previous_group = "E5" if group == "E6" else "E6" if group == "E7" else None
                    previous = completed.get((question.source_id, previous_group), {}).get("prediction") if previous_group else None
                    system, user = make_messages(question, evidence, group, previous)
                    try:
                        response = client.complete(system, user)
                    except Exception as exc:
                        row = {
                            "source_id": question.source_id,
                            "experiment": group,
                            "is_multiple": question.is_multiple,
                            "gold": question.gold,
                            "prediction": None,
                            "correct": False,
                            "status": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        stream.write(_json(row) + "\n")
                        stream.flush()
                        completed[key] = row
                        raise
                    prediction = parse_prediction(response["text"], question, allow_abstain=group == "E7")
                    status = "abstained" if prediction == "ABSTAIN" else "invalid" if prediction is None else "answered"
                    row = {
                        "source_id": question.source_id,
                        "experiment": group,
                        "is_multiple": question.is_multiple,
                        "exam_type": question.exam_type,
                        "exam_class": question.exam_class,
                        "exam_subject": question.exam_subject,
                        "gold": question.gold,
                        "prediction": prediction,
                        "correct": prediction == question.gold,
                        "status": status,
                        "raw_output": response["text"],
                        "evidence_chunk_ids": [chunk for item in evidence for chunk in item["chunk_ids"]],
                        "evidence_count": len(evidence),
                        "model_id": args.model,
                        "prompt_version": PROMPT_VERSION,
                        "usage": response["usage"],
                        "request_id": response["request_id"],
                        "finish_reason": response["finish_reason"],
                        "seconds": response["seconds"],
                    }
                    stream.write(_json(row) + "\n")
                    stream.flush()
                    completed[key] = row
                    new_api_calls += 1
                    print(f"[{index}/{len(questions)}] {group} id={question.source_id} {status} correct={row['correct']}", flush=True)
                    if args.max_api_calls is not None and new_api_calls >= args.max_api_calls:
                        print(f"Stopped at --max-api-calls={args.max_api_calls}; rerun the same command to resume.", flush=True)
                        return
    finally:
        if pipeline is not None:
            pipeline.close()
        selected_keys = {(question.source_id, group) for question in questions for group in groups}
        selected_rows = [row for key, row in completed.items() if key in selected_keys]
        summary = score_rows(selected_rows)
        comparisons = paired_comparisons(selected_rows, seed=args.seed)
        (output / "summary.json").write_text(_json(summary) + "\n", encoding="utf-8")
        (output / "comparisons.json").write_text(_json(comparisons) + "\n", encoding="utf-8")
        with (output / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["experiment", "question_type", "total", "correct", "accuracy", "answered", "coverage", "answered_accuracy", "abstained", "invalid", "failed"],
            )
            writer.writeheader()
            for group, cells in summary.items():
                for kind, values in cells.items():
                    writer.writerow({"experiment": group, "question_type": kind, **values})
        with (output / "comparisons.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["from", "to", "paired_total", "from_accuracy", "to_accuracy", "delta", "wrong_to_right", "right_to_wrong", "delta_ci95_low", "delta_ci95_high"],
            )
            writer.writeheader()
            writer.writerows(comparisons)
        print(_json(summary), flush=True)


if __name__ == "__main__":
    main()
