from pathlib import Path

from medical_rag.chunking.source_aware import extract_atoms, heading_level, normalize_for_search, split_oversize


def test_heading_levels():
    assert heading_level("第一章 总论") == 1
    assert heading_level("二、诊断") == 2
    assert heading_level("（三）治疗") == 3
    assert heading_level("（5）可逆性：平喘药通常能够缓解症状，可有明显的缓解期。") is None
    assert heading_level("3.药物治疗") == 3
    assert heading_level("2. 随着研究进步，本共识将继续修改和完善。") is None
    assert heading_level("普通叙述句。") is None


def test_atoms_keep_offsets():
    text = "标题\n\n第一段。\n第二段。"
    atoms = extract_atoms(text)
    assert [text[item.start : item.end] for item in atoms] == [item.text for item in atoms]
    assert atoms[1].line_start == 3


def test_split_oversize_keeps_source_offsets():
    text = "第一句很长。第二句也很长。第三句仍然很长。"
    atom = extract_atoms(text)[0]
    pieces = split_oversize(atom, max_chars=10, overlap=2)
    assert len(pieces) >= 2
    assert all(text[item.start : item.end] == item.text for item in pieces)


def test_normalize_does_not_remove_medical_symbols():
    value = normalize_for_search("剂量  2.5 mg，血氧＜90%，不推荐。")
    assert "2.5 mg" in value
    assert "90%" in value
    assert "不推荐" in value
