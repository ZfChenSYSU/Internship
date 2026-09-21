# Medical RAG Terminology Guide

This short guide explains the main technical terms used in the project plan. The definitions are practical rather than formal standards.

| Term | Plain-language meaning |
|---|---|
| **RAG (Retrieval-Augmented Generation)** | A system that looks up relevant source passages before an LLM writes an answer. The retrieved passages are provided as evidence in the prompt. |
| **LLM** | Large language model: a model that generates or analyzes text. Qwen is the project’s LLM provider. |
| **BM25** | A classic keyword-search ranking method. It is especially useful for exact disease names, drug names, numbers, abbreviations, and rare terms. |
| **Dense retrieval / embedding** | Text is converted into a numerical vector (an embedding). Similar meanings tend to have nearby vectors, enabling semantic rather than exact-word matching. |
| **BGE-M3** | A multilingual embedding model used here to create dense vectors for Chinese medical passages and queries. |
| **Vector database** | A database optimized for storing vectors and finding similar vectors. Qdrant also stores useful metadata alongside each vector. |
| **Qdrant payload** | Metadata stored with a vector, such as `chunk_id`, authority tier, source path, or population scope. It supports filtering and traceability. |
| **Chunk / passage** | A small retrievable unit of source text. In this project, a child chunk is usually 300–600 Chinese characters. |
| **Parent-child chunking** | A hierarchical design: retrieve a precise child passage, then add its parent section when more context or conditions are needed. |
| **Title path** | The sequence of headings above a passage, such as *Treatment → Drug therapy → Dose adjustment*. It tells the reader where a passage sits in the source. |
| **Chunk overlap** | Text intentionally repeated at the boundary of neighboring chunks so a sentence or condition is not lost. It must not cross sections or documents. |
| **Reranker / cross-encoder** | A more accurate but slower model that scores each query–passage pair after initial retrieval. It reorders the candidate list. |
| **RRF (Reciprocal Rank Fusion)** | A method that combines ranked lists, such as BM25 and dense retrieval. A passage ranked highly by either or both methods receives a strong fused score. |
| **Top-K** | The number of highest-ranked results retained at a step, for example Top-30 retrieval candidates or Top-8 final evidence windows. |
| **Metadata filter** | A restriction applied during search, such as “A/B authority only” or “special-population documents only.” Hard filters should not be used when classification is uncertain. |
| **Authority tier** | A project-defined estimate of evidence suitability: A = core authoritative source, B = supplementary source, C = lower-priority/experimental source. Tier C is not final evidence by default. |
| **Evidence window** | The final source text supplied to the LLM. It can contain a hit passage plus carefully selected surrounding or parent context. |
| **Grounded generation** | Answer generation constrained by supplied evidence rather than unsupported model knowledge. |
| **Citation / provenance** | A link from an answer to the exact source that supports it. Provenance includes the document identity, location, version, and original text. |
| **Claim-level verification** | Breaking an answer into individual factual claims and checking whether each cited passage actually supports that claim. |
| **Entailment / citation support** | The cited source justifies the stated claim, rather than merely discussing a related topic. |
| **Critical claim** | A medically important conclusion whose lack of support makes the answer unsafe or misleading. No unsupported critical claims are allowed. |
| **Refusal / abstention** | The system deliberately declines to give a factual answer when the retrieved evidence is weak, incomplete, conflicting, or unsuitable for individualized diagnosis. |
| **Calibration** | Choosing score thresholds or decision rules using a validation set so that a refusal policy balances safety and usefulness. |
| **Recall@K** | Of all relevant source passages, the proportion found within the top K retrieved results. Higher recall means less evidence is missed. |
| **MRR (Mean Reciprocal Rank)** | Measures how early the first relevant result appears. A relevant first result gives the highest possible contribution. |
| **nDCG@10** | A ranking metric that rewards relevant results near the top ten positions and can use graded relevance labels. |
| **Citation precision / recall** | Precision asks whether supplied citations are correct; recall asks whether important answer claims received the citations they need. |
| **False refusal** | An answerable question that the system rejects. It is important to report alongside refusal F1. |
| **Ablation study** | An experiment that removes or adds one component at a time to measure its contribution, such as E3 versus E4 to isolate reranking. |
| **Baseline** | A reference system used for comparison. E0 (Qwen without RAG) is the generation baseline. |
| **Corpus manifest** | A versioned inventory of included files and their hashes, sizes, categories, and inclusion decisions. It makes the dataset reproducible. |
| **Content hash** | A fingerprint calculated from file or passage content. It detects changes and exact duplicates. |
| **Deterministic ID** | An identifier generated predictably from stable inputs such as path and node order. It remains reproducible across builds. |
| **Index version** | An immutable named build of the retrieval index, tied to a corpus snapshot, parser/chunker version, and embedding model revision. |
| **Smoke test** | A small, fast test confirming that essential functions—retrieval, filters, context expansion, and source replay—work after an index build. |
| **MPS** | Apple’s Metal Performance Shaders backend, which lets compatible PyTorch operations run on Apple Silicon GPUs. CPU fallback is still required. |
| **API token** | A unit of text processed by an LLM API. Tracking input and output tokens helps manage context limits and cost. |
| **Namespace isolation** | Keeping each user session’s uploaded documents and index separate so content cannot leak across sessions. |
| **Data card** | Documentation for a dataset: origin, intended use, licence, preprocessing, limitations, and known risks. |
| **PII** | Personally identifiable information. It must be removed or protected and must not be sent to external model APIs in this project. |

## Reading the Experiment Labels

- **E0:** Qwen only, no retrieval.
- **E1–E2:** dense and BM25 retrieval baselines.
- **E3:** hybrid retrieval with RRF.
- **E4:** E3 plus reranking.
- **E5:** E4 plus parent-child hierarchical retrieval.
- **E6:** E5 plus claim-level citation verification.
- **E7:** E6 plus calibrated refusal; the full trustworthy-system configuration.
