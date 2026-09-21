import bisect
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from medical_rag.constants import INDEX_VERSION, PARSER_VERSION
from medical_rag.io_utils import content_hash, read_text_canonical


HEADING_PATTERNS = [
    (1, re.compile(r"^第[一二三四五六七八九十百千万〇零\d]+[篇卷部章]\s*")),
    (2, re.compile(r"^第[一二三四五六七八九十百千万〇零\d]+节\s*")),
    (2, re.compile(r"^[一二三四五六七八九十百千万〇零]+[、．.]\s*")),
    (3, re.compile(r"^[（(][一二三四五六七八九十百千万〇零\d]+[）)]\s*")),
]
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；!?;])")
INDEX_LINE = re.compile(r"^.{1,70}(?:\t|\s{2,})\d{1,4}$")
DOSAGE = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|g|μg|ug|ml|mL|L|mmol|U|IU|次|片|粒|滴|%)", re.I)
NEGATION = re.compile(r"不推荐|禁忌|慎用|不得|不能|不宜|无|未|不")
SHORT_HEADING = re.compile(
    r"^(?:\d{1,3}[、．.]\s*)?.{0,18}"
    r"(?:目的|指征|症状|体征|检查|诊断|鉴别|治疗|预防|健康教育|原则|方法|评估|"
    r"病因|机制|机理|分类|概述|定义|临床表现|并发症|处理|护理|用法|用量|相关因素)$"
)
LOW_INFORMATION = re.compile(r"^(?:同上|略|无|—|-|\d+|[，。；：、.\s])+$")


@dataclass
class Atom:
    text: str
    start: int
    end: int
    line_start: int
    line_end: int
    heading_level: Optional[int] = None
    is_index: bool = False
    is_reference: bool = False


def normalize_for_search(text: str) -> str:
    value = unicodedata.normalize("NFKC", text)
    value = re.sub(r"[ \t\u3000]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def line_starts(text: str) -> List[int]:
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return starts


def line_number(starts: Sequence[int], offset: int) -> int:
    return bisect.bisect_right(starts, offset)


def heading_level(value: str) -> Optional[int]:
    stripped = value.strip()
    if not stripped or len(stripped) > 80:
        return None
    for level, pattern in HEADING_PATTERNS:
        if pattern.match(stripped):
            # Chinese/parenthesized numbering is also used for complete list
            # statements.  Only short, title-like lines establish structure.
            if level in {2, 3} and (len(stripped) > 40 or re.search(r"[。！？；!?;]$", stripped)):
                return None
            return level
    if SHORT_HEADING.match(stripped):
        return 3
    if len(stripped) <= 24 and not re.search(r"[。！？；!?;]$", stripped):
        if stripped in {"前言", "概述", "摘要", "目录", "参考文献", "诊断标准", "鉴别诊断", "治疗", "预防", "疗效评估", "治疗策略"}:
            return 2
    return None


def extract_atoms(text: str) -> List[Atom]:
    starts = line_starts(text)
    atoms: List[Atom] = []
    reference_mode = False
    for match in re.finditer(r"[^\n]+", text):
        raw = match.group(0)
        stripped = raw.strip()
        if not stripped:
            continue
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())
        start = match.start() + leading
        end = match.end() - trailing
        level = heading_level(stripped)
        if stripped.startswith("参考文献") and len(stripped) <= 30:
            reference_mode = True
        atoms.append(
            Atom(
                text=text[start:end],
                start=start,
                end=end,
                line_start=line_number(starts, start),
                line_end=line_number(starts, max(start, end - 1)),
                heading_level=level,
                is_index=stripped == "目录" or bool(INDEX_LINE.match(stripped)),
                is_reference=reference_mode,
            )
        )
    return atoms


def infer_title(path: Path, category: str, atoms: Sequence[Atom]) -> str:
    if category == "textbook" and path.stem.lower().startswith("text ("):
        for atom in atoms[:80]:
            if atom.heading_level and atom.text.strip() not in {"目录", "前言"}:
                return atom.text.strip()
    if category == "textbook":
        return path.stem
    for atom in atoms[:15]:
        candidate = atom.text.strip()
        if 4 <= len(candidate) <= 100 and candidate not in {"前言", "目录"}:
            return candidate
    return path.stem


def split_oversize(atom: Atom, max_chars: int, overlap: int) -> List[Atom]:
    if len(atom.text) <= max_chars:
        return [atom]
    local_starts = [0]
    for match in SENTENCE_BOUNDARY.finditer(atom.text):
        local_starts.append(match.end())
    local_starts.append(len(atom.text))
    pieces: List[Atom] = []
    cursor = 0
    while cursor < len(atom.text):
        desired = min(cursor + max_chars, len(atom.text))
        candidates = [point for point in local_starts if cursor < point <= desired]
        end = max(candidates) if candidates else desired
        if end <= cursor:
            end = desired
        start = atom.start + cursor
        finish = atom.start + end
        pieces.append(
            Atom(
                text=atom.text[cursor:end],
                start=start,
                end=finish,
                line_start=atom.line_start,
                line_end=atom.line_end,
                is_index=atom.is_index,
                is_reference=atom.is_reference,
            )
        )
        if end >= len(atom.text):
            break
        next_cursor = max(cursor + 1, end - overlap)
        after = [point for point in local_starts if next_cursor <= point < end]
        cursor = min(after) if after else next_cursor
    return pieces


def _section_groups(atoms: Sequence[Atom]) -> Iterator[Tuple[List[str], List[Atom]]]:
    title_stack: List[str] = []
    current_path: List[str] = []
    current: List[Atom] = []
    for atom in atoms:
        if atom.heading_level is not None:
            if current:
                yield current_path, current
            level = atom.heading_level
            title_stack = title_stack[: max(0, level - 1)]
            while len(title_stack) < level - 1:
                title_stack.append("")
            title_stack.append(atom.text.strip())
            current_path = [item for item in title_stack if item]
            # Heading text is carried in title_path/retrieval_text.  Keeping it
            # out of the body prevents heading-only evidence chunks when two
            # headings are adjacent or the first paragraph is very long.
            current = []
        else:
            current.append(atom)
    if current:
        yield current_path, current


def _window_atoms(atoms: Sequence[Atom], target: int) -> Iterator[List[Atom]]:
    current: List[Atom] = []
    for atom in atoms:
        if current and atom.end - current[0].start > target:
            yield current
            current = []
        current.append(atom)
    if current:
        yield current


def _child_groups(atoms: Sequence[Atom], target: int, max_chars: int, overlap: int) -> Iterator[List[Atom]]:
    expanded: List[Atom] = []
    for atom in atoms:
        expanded.extend(split_oversize(atom, max_chars, overlap))
    current: List[Atom] = []
    for atom in expanded:
        prospective = atom.end - current[0].start if current else len(atom.text)
        if current and prospective > target:
            yield current
            current = []
        current.append(atom)
        if len(atom.text) >= max_chars:
            yield current
            current = []
    if current:
        yield current


def chunk_document(
    corpus_parent: Path,
    manifest: Dict,
    child_target: int = 500,
    child_max: int = 800,
    overlap: int = 80,
    parent_target: int = 1600,
) -> Tuple[Dict, List[Dict], List[Dict]]:
    path = corpus_parent / manifest["source_path"]
    text, _ = read_text_canonical(path)
    atoms = extract_atoms(text)
    title = infer_title(path, manifest["dataset_category"], atoms)
    document_id = f'{manifest["dataset_category"]}/{manifest["source_id"]}/doc00'
    document = {
        "document_id": document_id,
        "document_title": title,
        "dataset_category": manifest["dataset_category"],
        "authority_tier": manifest["authority_tier"],
        "eligible_as_final_evidence": manifest["eligible_as_final_evidence"],
        "source_path": manifest["source_path"],
        "source_url": None,
        "published_at": None,
        "publisher_or_author": None,
        "metadata_status": "unknown",
        "content_hash": manifest["content_hash"],
        "canonical_chars": len(text),
        "parser_version": PARSER_VERSION,
        "index_version": INDEX_VERSION,
    }
    parents: List[Dict] = []
    chunks: List[Dict] = []
    section_number = 0
    chunk_number = 0
    for title_path, section_atoms in _section_groups(atoms):
        for parent_atoms in _window_atoms(section_atoms, parent_target):
            parent_id = f"{document_id}/sec{section_number:04d}"
            parent_start, parent_end = parent_atoms[0].start, parent_atoms[-1].end
            parent_raw = text[parent_start:parent_end]
            parent = {
                "parent_id": parent_id,
                "document_id": document_id,
                "document_title": title,
                "title_path": title_path,
                "raw_text": parent_raw,
                "normalized_text": normalize_for_search(parent_raw),
                "source_path": manifest["source_path"],
                "source_char_start": parent_start,
                "source_char_end": parent_end,
                "source_line_start": parent_atoms[0].line_start,
                "source_line_end": parent_atoms[-1].line_end,
                "content_hash": content_hash(parent_raw),
                "parser_version": PARSER_VERSION,
                "index_version": INDEX_VERSION,
                "child_ids": [],
            }
            for child_atoms in _child_groups(parent_atoms, child_target, child_max, overlap):
                start, end = child_atoms[0].start, child_atoms[-1].end
                raw = text[start:end]
                normalized = normalize_for_search(raw)
                low_information = len(normalized) < 3 or bool(LOW_INFORMATION.fullmatch(normalized))
                node_eligible = (
                    manifest["eligible_as_final_evidence"]
                    and not all(item.is_index or item.is_reference for item in child_atoms)
                    and not low_information
                )
                chunk_id = f"{parent_id}/ch{chunk_number:05d}"
                has_reliable_structure = bool(title_path) or (
                    manifest["dataset_category"] == "textbook" and not path.stem.lower().startswith("text (")
                )
                chunk = {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "parent_id": parent_id,
                    "dataset_category": manifest["dataset_category"],
                    "authority_tier": manifest["authority_tier"],
                    "eligible_as_final_evidence": node_eligible,
                    "document_title": title,
                    "title_path": title_path,
                    "raw_text": raw,
                    "normalized_text": normalized,
                    "retrieval_text": "\n".join(filter(None, [title, " > ".join(title_path), normalized])),
                    "source_path": manifest["source_path"],
                    "source_url": None,
                    "published_at": None,
                    "source_line_start": child_atoms[0].line_start,
                    "source_line_end": child_atoms[-1].line_end,
                    "source_char_start": start,
                    "source_char_end": end,
                    "content_hash": content_hash(raw),
                    "parser_version": PARSER_VERSION,
                    "structure_confidence": "high" if has_reliable_structure else "low",
                    "index_version": INDEX_VERSION,
                    "contains_dosage": bool(DOSAGE.search(raw)),
                    "contains_negation": bool(NEGATION.search(raw)),
                    "is_reference_section": all(item.is_reference for item in child_atoms),
                    "is_index_page": all(item.is_index for item in child_atoms),
                    "needs_manual_review": not has_reliable_structure or not node_eligible or len(normalized) < 20,
                    "oversize_reason": "indivisible_or_sentence_split" if len(raw) > child_max else None,
                }
                parent["child_ids"].append(chunk_id)
                chunks.append(chunk)
                chunk_number += 1
            parents.append(parent)
            section_number += 1
    return document, parents, chunks
