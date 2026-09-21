import json
import uuid
from pathlib import Path
from typing import Dict, Iterable, List

from medical_rag.io_utils import iter_jsonl


def _device(requested: str) -> str:
    import torch

    if requested == "mps":
        if not torch.backends.mps.is_built():
            raise RuntimeError("当前 PyTorch wheel 未编译 MPS 支持，请重新安装 macOS arm64 版 PyTorch。")
        if not torch.backends.mps.is_available():
            raise RuntimeError(
                "PyTorch 已包含 MPS，但当前进程看不到 MPS 设备；请检查运行环境的 GPU/Metal 权限，"
                "并先运行 `python scripts/corpus_pipeline.py doctor`。"
            )
        return "mps"
    if requested != "auto":
        return requested
    return "mps" if torch.backends.mps.is_available() else "cpu"


def mps_diagnostics() -> Dict:
    import platform
    import sys
    import torch

    result = {
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "macos": platform.mac_ver()[0],
        "torch": torch.__version__,
        "mps_built": torch.backends.mps.is_built(),
        "mps_available": torch.backends.mps.is_available(),
        "tensor_test": False,
    }
    if result["mps_available"]:
        value = (torch.ones(4, device="mps") * 2).cpu().tolist()
        result["tensor_test"] = value == [2.0, 2.0, 2.0, 2.0]
        if hasattr(torch.backends.mps, "get_name"):
            result["device_name"] = torch.backends.mps.get_name()
    return result


def build_dense(
    chunks_path: Path,
    qdrant_path: Path,
    collection: str = "corpus_v1_children",
    model_name: str = "BAAI/bge-m3",
    device: str = "auto",
    batch_size: int = 8,
    max_length: int = 512,
    precision: str = "fp32",
    limit: int = None,
    recreate: bool = False,
) -> Dict:
    try:
        from qdrant_client import QdrantClient, models
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Dense indexing requires: pip install -e '.[dense]'") from exc

    selected_device = _device(device)
    model = SentenceTransformer(model_name, device=selected_device, trust_remote_code=True)
    model.max_seq_length = max_length
    if precision == "fp16":
        model.half()
    elif precision != "fp32":
        raise ValueError("precision must be fp16 or fp32")
    dimension = int(model.get_sentence_embedding_dimension())
    qdrant_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_path))
    existing = {item.name for item in client.get_collections().collections}
    if collection in existing and recreate:
        client.delete_collection(collection)
        existing.remove(collection)
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )

    completed = set()
    if collection in {item.name for item in client.get_collections().collections}:
        offset = None
        while True:
            points, offset = client.scroll(collection, limit=1000, offset=offset, with_payload=False, with_vectors=False)
            completed.update(str(point.id) for point in points)
            if offset is None:
                break

    pending: List[Dict] = []
    indexed = 0

    def flush(batch: List[Dict]) -> int:
        if not batch:
            return 0
        texts = [item["retrieval_text"] for item in batch]
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        points = []
        for item, vector in zip(batch, vectors):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item["chunk_id"]))
            payload = {key: value for key, value in item.items() if key not in {"raw_text", "normalized_text", "retrieval_text"}}
            points.append(models.PointStruct(id=point_id, vector=vector.tolist(), payload=payload))
        client.upsert(collection_name=collection, points=points, wait=True)
        return len(points)

    for chunk in iter_jsonl(chunks_path):
        if not chunk["eligible_as_final_evidence"]:
            continue
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"]))
        if point_id in completed:
            continue
        if limit is not None and indexed + len(pending) >= limit:
            break
        pending.append(chunk)
        if len(pending) >= max(100, batch_size * 16):
            indexed += flush(pending)
            pending.clear()
            if indexed % 1024 == 0:
                print(f"dense_index_progress={indexed}", flush=True)
    indexed += flush(pending)
    return {
        "collection": collection,
        "model": model_name,
        "dimension": dimension,
        "device": selected_device,
        "max_length": max_length,
        "precision": precision,
        "newly_indexed": indexed,
        "requested_limit": limit,
        "qdrant_path": str(qdrant_path),
    }
