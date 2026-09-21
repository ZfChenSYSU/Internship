import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Iterable, Iterator, Tuple


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def stable_short_id(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def content_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_text_canonical(path: Path) -> Tuple[str, str]:
    raw = path.read_bytes()
    encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = "gb18030"
        text = raw.decode(encoding)
    return text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff"), encoding


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(str(temporary), str(path))


def write_jsonl(path: Path, rows: Iterable[Dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    os.replace(str(temporary), str(path))
    return count


def iter_jsonl(path: Path) -> Iterator[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)

