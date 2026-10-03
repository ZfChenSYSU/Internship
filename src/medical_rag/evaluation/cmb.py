"""CMB-Exam loading and strict multiple-choice scoring."""

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CMBQuestion:
    source_id: str
    question: str
    options: Dict[str, str]
    gold: str
    question_type: str
    exam_type: str
    exam_class: str
    exam_subject: str

    @property
    def is_multiple(self) -> bool:
        return "多" in self.question_type or len(self.gold) > 1

    def prompt_question(self) -> str:
        options = "\n".join(f"{key}. {value}" for key, value in self.options.items())
        label = "多选题" if self.is_multiple else "单选题"
        return f"{label}：{self.question}\n{options}"


def _answer_letters(value: object, allowed: str) -> str:
    if isinstance(value, list):
        value = "".join(str(item) for item in value)
    raw = str(value or "").upper().strip()
    letters = re.sub(r"[\s,，、;/；.。]+", "", raw)
    if not letters or any(letter not in allowed for letter in letters):
        raise ValueError(f"Invalid answer: {raw!r}")
    if len(set(letters)) != len(letters):
        raise ValueError(f"Repeated answer option: {raw!r}")
    return "".join(sorted(letters))


def load_cmb(path: Path, answer_path: Optional[Path] = None) -> List[CMBQuestion]:
    """Read an official CMB-Exam merged JSON file, optionally with a key file."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("CMB exam file must contain a JSON list")
    answer_by_id = {}
    if answer_path is not None:
        answers = json.loads(Path(answer_path).read_text(encoding="utf-8"))
        if isinstance(answers, list):
            answer_by_id = {str(item["id"]): item["answer"] for item in answers}
        elif isinstance(answers, dict):
            answer_by_id = {str(key): value for key, value in answers.items()}
        else:
            raise ValueError("CMB answer file must contain a JSON list or object")

    questions = []
    seen = set()
    for position, item in enumerate(records):
        source_id = str(item.get("id", position))
        if source_id in seen:
            raise ValueError(f"Duplicate CMB id: {source_id}")
        seen.add(source_id)
        options = item.get("option") or item.get("options")
        if not isinstance(options, dict) or len(options) < 2:
            raise ValueError(f"Missing options for CMB id {source_id}")
        clean_options = {str(key).upper(): str(value).strip() for key, value in options.items()}
        # The official CMB files contain some blank option texts. Preserve
        # their labels so the official denominator and answer key stay intact.
        if any(not re.fullmatch(r"[A-Z]", key) for key in clean_options):
            raise ValueError(f"Invalid options for CMB id {source_id}")
        question = str(item.get("question") or "").strip()
        if not question:
            raise ValueError(f"Missing question for CMB id {source_id}")
        gold_value = answer_by_id.get(source_id, item.get("answer"))
        gold = _answer_letters(gold_value, "".join(clean_options))
        questions.append(
            CMBQuestion(
                source_id=source_id,
                question=question,
                options=clean_options,
                gold=gold,
                question_type=str(item.get("question_type") or ""),
                exam_type=str(item.get("exam_type") or ""),
                exam_class=str(item.get("exam_class") or ""),
                exam_subject=str(item.get("exam_subject") or ""),
            )
        )
    return questions


_FINAL_LINE = re.compile(r"(?im)^\s*FINAL_ANSWER\s*:\s*(.*?)\s*$")


def parse_prediction(text: str, question: CMBQuestion, allow_abstain: bool = False) -> Optional[str]:
    """Only the explicit final line is scored; explanations cannot supply letters."""
    matches = _FINAL_LINE.findall(text or "")
    if len(matches) != 1:
        return None
    value = matches[0].strip().upper()
    if allow_abstain and value == "ABSTAIN":
        return value
    try:
        answer = _answer_letters(value, "".join(question.options))
    except ValueError:
        return None
    if not question.is_multiple and len(answer) != 1:
        return None
    return answer


def score_rows(rows: List[dict]) -> dict:
    """Count all requested questions, including invalid output and failures."""
    summary = {}
    for row in rows:
        group = row["experiment"]
        kind = "multiple" if row["is_multiple"] else "single"
        for label in (kind, "all"):
            cell = summary.setdefault(
                (group, label),
                {"total": 0, "correct": 0, "answered": 0, "invalid": 0, "abstained": 0, "failed": 0},
            )
            cell["total"] += 1
            cell["correct"] += int(bool(row.get("correct")))
            cell["answered"] += int(row.get("status") == "answered")
            cell["invalid"] += int(row.get("status") == "invalid")
            cell["abstained"] += int(row.get("status") == "abstained")
            cell["failed"] += int(row.get("status") == "failed")
    return {
        group: {
            kind: {
                **cell,
                "accuracy": cell["correct"] / cell["total"],
                "coverage": cell["answered"] / cell["total"],
                "answered_accuracy": cell["correct"] / cell["answered"] if cell["answered"] else None,
            }
            for (name, kind), cell in summary.items()
            if name == group
        }
        for group in sorted({group for group, _ in summary})
    }


def paired_comparisons(rows: List[dict], seed: int = 20260930, bootstrap_samples: int = 2000) -> List[dict]:
    """Compare stages on identical question IDs, with paired bootstrap intervals."""
    by_group = {}
    for row in rows:
        by_group.setdefault(row["experiment"], {})[row["source_id"]] = bool(row.get("correct"))
    pairs = [
        ("E0", "E1"), ("E0", "E2"), ("E1", "E3"), ("E2", "E3"),
        ("E3", "E4"), ("E4", "E5"), ("E5", "E6"), ("E6", "E7"),
    ]
    result = []
    for left, right in pairs:
        if left not in by_group or right not in by_group:
            continue
        ids = sorted(set(by_group[left]) & set(by_group[right]))
        if not ids:
            continue
        left_values = [int(by_group[left][item]) for item in ids]
        right_values = [int(by_group[right][item]) for item in ids]
        differences = [b - a for a, b in zip(left_values, right_values)]
        rng = random.Random(f"{seed}:{left}:{right}")
        deltas = sorted(
            sum(differences[rng.randrange(len(ids))] for _ in ids) / len(ids)
            for _ in range(bootstrap_samples)
        )
        result.append({
            "from": left,
            "to": right,
            "paired_total": len(ids),
            "from_accuracy": sum(left_values) / len(ids),
            "to_accuracy": sum(right_values) / len(ids),
            "delta": sum(differences) / len(ids),
            "wrong_to_right": sum(value == 1 for value in differences),
            "right_to_wrong": sum(value == -1 for value in differences),
            "delta_ci95_low": deltas[int(0.025 * bootstrap_samples)],
            "delta_ci95_high": deltas[min(len(deltas) - 1, int(0.975 * bootstrap_samples))],
        })
    return result
