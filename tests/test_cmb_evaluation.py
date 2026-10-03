import json
import sys

import pytest

from medical_rag.evaluation.cmb import load_cmb, paired_comparisons, parse_prediction, score_rows
from medical_rag.evaluation.run_cmb import _groups


def test_official_style_question_and_separate_answers(tmp_path):
    questions = [
        {
            "id": 7,
            "question": "选择正确说法",
            "question_type": "多项选择题",
            "option": {"A": "说法一", "B": "说法二", "C": "说法三"},
            "exam_type": "医师考试",
            "exam_class": "执业医师",
        }
    ]
    question_file = tmp_path / "questions.json"
    answer_file = tmp_path / "answers.json"
    question_file.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    answer_file.write_text(json.dumps([{"id": 7, "answer": "CA"}]), encoding="utf-8")
    question = load_cmb(question_file, answer_file)[0]

    assert question.gold == "AC"
    assert question.is_multiple
    assert parse_prediction("分析略\nFINAL_ANSWER: CA", question) == "AC"
    assert parse_prediction("FINAL_ANSWER: ABC", question) == "ABC"
    assert parse_prediction("FINAL_ANSWER: ABSTAIN", question) is None
    assert parse_prediction("FINAL_ANSWER: ABSTAIN", question, allow_abstain=True) == "ABSTAIN"
    assert parse_prediction("答案可能是 A", question) is None
    assert parse_prediction("FINAL_ANSWER: A\nFINAL_ANSWER: C", question) is None


def test_requested_denominator_includes_invalid_and_abstentions():
    rows = [
        {"experiment": "E7", "is_multiple": False, "correct": True, "status": "answered"},
        {"experiment": "E7", "is_multiple": False, "correct": False, "status": "abstained"},
        {"experiment": "E7", "is_multiple": False, "correct": False, "status": "invalid"},
    ]
    result = score_rows(rows)["E7"]["single"]
    assert result == {
        "total": 3,
        "correct": 1,
        "answered": 1,
        "invalid": 1,
        "abstained": 1,
        "failed": 0,
        "accuracy": 1 / 3,
        "coverage": 1 / 3,
        "answered_accuracy": 1.0,
    }


def test_later_ablation_requires_earlier_generation():
    with pytest.raises(ValueError, match="E6 requires E5"):
        _groups("E6")
    with pytest.raises(ValueError, match="E7 requires E6"):
        _groups("E5,E7")
    assert _groups("E7,E5,E6") == ["E5", "E6", "E7"]


def test_paired_comparison_tracks_each_changed_answer():
    rows = [
        {"source_id": "1", "experiment": "E3", "correct": False},
        {"source_id": "2", "experiment": "E3", "correct": True},
        {"source_id": "3", "experiment": "E3", "correct": True},
        {"source_id": "1", "experiment": "E4", "correct": True},
        {"source_id": "2", "experiment": "E4", "correct": False},
        {"source_id": "3", "experiment": "E4", "correct": True},
    ]
    result = paired_comparisons(rows, bootstrap_samples=100)[0]
    assert result["from"] == "E3" and result["to"] == "E4"
    assert result["paired_total"] == 3
    assert result["wrong_to_right"] == 1 and result["right_to_wrong"] == 1
    assert result["delta"] == 0


def test_batch_resume_and_extend_without_duplicate_api_calls(tmp_path, monkeypatch):
    from medical_rag.evaluation import run_cmb

    question_file = tmp_path / "questions.json"
    question_file.write_text(
        json.dumps([{"id": 1, "question": "测试", "option": {"A": "正确", "B": "错误"}, "answer": "A"}]),
        encoding="utf-8",
    )
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def complete(self, system, user):
            calls.append((system, user))
            return {"text": "FINAL_ANSWER: A", "usage": {}, "request_id": "fake", "finish_reason": "stop", "seconds": 0}

    class FakePipeline:
        def __init__(self, *args, **kwargs):
            pass

        def set_question(self, question):
            pass

        def evidence_for(self, group):
            return [{"id": "S1", "title": "测试资料", "section": "", "text": "正确", "chunk_ids": ["chunk-1"]}]

        def close(self):
            pass

    monkeypatch.setattr(run_cmb, "DeepSeekClient", FakeClient)
    monkeypatch.setattr(run_cmb, "EvidencePipeline", FakePipeline)
    output = tmp_path / "result"

    def invoke(groups, cap):
        monkeypatch.setattr(
            sys,
            "argv",
            ["run_cmb", "--questions", str(question_file), "--output", str(output),
             "--experiments", groups, "--max-api-calls", str(cap)],
        )
        run_cmb.main()

    invoke("E0,E1,E2,E3,E4,E5", 2)
    assert len(calls) == 2
    invoke("E0,E1,E2,E3,E4,E5", 5)
    assert len(calls) == 6
    invoke("E0,E1,E2,E3,E4,E5,E6,E7", 5)
    assert len(calls) == 8
    rows = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
    assert [row["experiment"] for row in rows] == [f"E{number}" for number in range(8)]
    assert (output / "summary.csv").exists()
    assert (output / "comparisons.csv").exists()
