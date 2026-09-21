import argparse
import json
from pathlib import Path

from medical_rag.indexing.bm25_sqlite import build_bm25, search_bm25
from medical_rag.pipeline import prepare_corpus


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Medical corpus preparation and indexing")
    commands = root.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="Build scope, manifest, documents, parents and chunks")
    prepare.add_argument("--corpus-root", type=Path, default=Path("Medical Corpus"))
    prepare.add_argument("--data-root", type=Path, default=Path("data"))

    bm25 = commands.add_parser("bm25", help="Build the SQLite FTS5 BM25 index")
    bm25.add_argument("--chunks", type=Path, default=Path("data/processed/corpus_v1/chunks.jsonl"))
    bm25.add_argument("--parents", type=Path, default=Path("data/processed/corpus_v1/parents.jsonl"))
    bm25.add_argument("--documents", type=Path, default=Path("data/processed/corpus_v1/documents.jsonl"))
    bm25.add_argument("--output", type=Path, default=Path("data/indexes/corpus_v1/bm25.sqlite3"))

    dense = commands.add_parser("dense", help="Build/resume the BGE-M3 Qdrant index")
    dense.add_argument("--chunks", type=Path, default=Path("data/processed/corpus_v1/chunks.jsonl"))
    dense.add_argument("--output", type=Path, default=Path("data/indexes/corpus_v1/qdrant"))
    dense.add_argument("--collection", default="corpus_v1_children")
    dense.add_argument("--model", default="BAAI/bge-m3")
    dense.add_argument("--device", default="auto", choices=("auto", "mps", "cpu"))
    dense.add_argument("--batch-size", type=int, default=8)
    dense.add_argument("--max-length", type=int, default=512)
    dense.add_argument("--precision", choices=("fp16", "fp32"), default="fp32")
    dense.add_argument("--limit", type=int, default=None, help="Only index N new chunks (smoke test)")
    dense.add_argument("--recreate", action="store_true")

    search = commands.add_parser("search", help="Smoke-test the BM25 index")
    search.add_argument("query")
    search.add_argument("--index", type=Path, default=Path("data/indexes/corpus_v1/bm25.sqlite3"))
    search.add_argument("--limit", type=int, default=5)

    hybrid = commands.add_parser("retrieve", help="Run BM25+dense RRF, BGE reranking and parent expansion")
    hybrid.add_argument("query")
    hybrid.add_argument("--bm25-index", type=Path, default=Path("data/indexes/corpus_v1/bm25.sqlite3"))
    hybrid.add_argument("--qdrant-path", type=Path, default=Path("data/indexes/corpus_v1/qdrant"))
    hybrid.add_argument("--collection", default="corpus_v1_children")
    hybrid.add_argument("--dense-model", default="BAAI/bge-m3")
    hybrid.add_argument("--reranker-model", default="BAAI/bge-reranker-v2-m3")
    hybrid.add_argument("--model-cache", type=Path, default=Path("models/huggingface"))
    hybrid.add_argument("--device", default="auto", choices=("auto", "mps", "cpu"))
    hybrid.add_argument("--no-dense", action="store_true", help="Use BM25 only (degraded-mode smoke test)")
    hybrid.add_argument("--no-reranker", action="store_true", help="Skip cross-encoder reranking")
    hybrid.add_argument("--no-parent", action="store_true", help="Return child hits without parent expansion")
    commands.add_parser("doctor", help="Check whether this process can execute an MPS tensor")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "prepare":
        _print(prepare_corpus(args.corpus_root.resolve(), args.data_root.resolve()))
    elif args.command == "bm25":
        _print(
            build_bm25(
                args.chunks.resolve(),
                args.output.resolve(),
                parents_path=args.parents.resolve(),
                documents_path=args.documents.resolve(),
            )
        )
    elif args.command == "dense":
        from medical_rag.indexing.dense_qdrant import build_dense

        _print(
            build_dense(
                args.chunks.resolve(),
                args.output.resolve(),
                collection=args.collection,
                model_name=args.model,
                device=args.device,
                batch_size=args.batch_size,
                max_length=args.max_length,
                precision=args.precision,
                limit=args.limit,
                recreate=args.recreate,
            )
        )
    elif args.command == "search":
        _print(search_bm25(args.index.resolve(), args.query, args.limit))
    elif args.command == "retrieve":
        from medical_rag.reranking.bge import BGEReranker
        from medical_rag.retrieval.dense import DenseRetriever
        from medical_rag.retrieval.hybrid import HybridRetriever

        dense_retriever = None
        if not args.no_dense:
            dense_retriever = DenseRetriever(
                args.qdrant_path.resolve(),
                args.bm25_index.resolve(),
                collection=args.collection,
                model_name=args.dense_model,
                device=args.device,
                cache_dir=args.model_cache.resolve(),
            )
        reranker = None
        if not args.no_reranker:
            reranker = BGEReranker(
                model_name=args.reranker_model,
                device=args.device,
                cache_dir=args.model_cache.resolve(),
            )
        try:
            result = HybridRetriever(
                args.bm25_index.resolve(),
                dense_retriever=dense_retriever,
                reranker=reranker,
            ).retrieve(args.query, expand_hierarchy=not args.no_parent)
            _print(result.to_dict())
        finally:
            if dense_retriever is not None:
                dense_retriever.close()
    elif args.command == "doctor":
        from medical_rag.indexing.dense_qdrant import mps_diagnostics

        _print(mps_diagnostics())


if __name__ == "__main__":
    main()
