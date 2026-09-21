from pathlib import Path
from typing import Optional, Union


def resolve_cached_model(
    model_name: str,
    cache_dir: Optional[Union[str, Path]] = None,
) -> str:
    """Prefer an existing local Hugging Face snapshot without network access."""
    if Path(model_name).exists() or cache_dir is None:
        return model_name
    cache_root = Path(cache_dir)
    repository = cache_root / ("models--" + model_name.replace("/", "--"))
    snapshots = repository / "snapshots"
    if not snapshots.exists():
        return model_name

    ref = repository / "refs" / "main"
    if ref.exists():
        candidate = snapshots / ref.read_text(encoding="utf-8").strip()
        if (candidate / "config.json").exists():
            return str(candidate)
    candidates = sorted(
        (path for path in snapshots.iterdir() if (path / "config.json").exists()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0]) if candidates else model_name
