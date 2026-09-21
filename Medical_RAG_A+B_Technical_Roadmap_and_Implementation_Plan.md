# Project 2: Trustworthy Medical RAG Question-Answering System

## A+B Technical Roadmap, Work Breakdown, and Implementation Plan

- **Version:** v0.3
- **Date:** 21 September 2026
- **Duration:** 12 weeks
- **Team:** 4 people
- **Primary environment:** macOS with 24 GB RAM; use Apple Silicon MPS where supported and fall back to CPU otherwise
- **Generative model:** Qwen API; no local LLM deployment is required
- **Server/GPU:** optional acceleration only, not a dependency for project completion

---

## 1. Project Positioning

The project combines two complementary approaches:

- **Track A — Chinese medical hybrid-retrieval RAG baseline.** Retrieve evidence in parallel with keyword/BM25 and dense-vector search, fuse the results, rerank them with a cross-encoder, and use Qwen to produce evidence-grounded answers with citations. Questions with inadequate evidence should receive a calibrated refusal.
- **Track B — Hierarchical medical-document retrieval and claim-level citation verification.** Preserve the document hierarchy (document → chapter → section → paragraph/table); retrieve fine-grained passages first and add parent-section context when needed. Split an answer into medical claims and verify the support for each claim. Remove, revise, or refuse answers when critical claims lack support, omit qualifying conditions, or conflict with the evidence.

The final deliverable is a runnable Chinese medical-QA web application with:

1. Chinese-language medical question answering;
2. verifiable citations for each key conclusion;
3. document upload and indexing for guidelines and drug labels;
4. multi-turn chat and streaming output;
5. proactive refusal when evidence is insufficient; and
6. ablations covering no-RAG, standard RAG, hybrid retrieval, reranking, hierarchical retrieval, and refusal policies.

> This system is for coursework research and engineering validation only. It is not a clinical diagnosis or treatment tool, and demonstrations must not use real patient-identifiable data.

## 2. Scope and Objectives

### 2.1 Required work

- [ ] Build a versioned, traceable Chinese medical document collection.
- [ ] Implement parsing, cleaning, hierarchical chunking, and indexing.
- [ ] Establish no-RAG, BM25/keyword, and BGE-M3 dense-retrieval baselines.
- [ ] Implement BM25+dense Reciprocal Rank Fusion (RRF) and `bge-reranker-v2-m3` reranking.
- [ ] Implement parent-child retrieval and parent-section context expansion.
- [ ] Generate evidence-based answers through the Qwen API.
- [ ] Produce passage-level citations linked back to source text.
- [ ] Implement claim-level citation verification and calibrated insufficient-evidence refusal.
- [ ] Run ablations on fixed CMB/CMExam subsets and create an in-house answerable/unanswerable test set.
- [ ] Deliver a web demonstration, deployment guide, and experiment report.

### 2.2 Optional enhancements

- [ ] Dedicated chunking rules for tables, dosages, and contraindications.
- [ ] Metadata filters for diseases, medicines, and special populations.
- [ ] Conflict detection across evidence sources.
- [ ] Quality/cost comparison across Qwen API model versions.
- [ ] Comparison with other Chinese medical retrieval or domain-adapted embedding models.
- [ ] Markdown/PDF export of answers and citations.

### 2.3 Explicitly out of scope

- Training or fine-tuning an LLM; deploying and maintaining an LLM on the Mac.
- Building a large medical knowledge graph, multi-agent workflow, or complex agent system.
- Using real, non-de-identified medical records or claiming clinical diagnostic capability.
- Treating visual polish as a substitute for retrieval, citation, and refusal evaluation.

## 3. System Architecture

```text
Offline processing
Guidelines / labels / PDF / HTML
  → parsing and normalization
  → hierarchy extraction: document → chapter → section → child passage/table
  → BM25 index + BGE-M3 vector index

Online QA
Question → normalization / conversational rewrite
  → BM25 Top-N + dense Top-N → RRF → cross-encoder reranker
  → child-passage hits + parent-context expansion → evidence-sufficiency check
  → insufficient: refuse
  → sufficient: Qwen evidence-grounded generation → claim-level citation verification
  → revise/refuse on critical issues, otherwise return cited answer
```

## 4. Recommended Stack and Initial Configuration

| Area | Recommended choice | Rationale |
|---|---|---|
| Language | Python 3.11/3.12 | One language for backend, data pipeline, and evaluation |
| Generation | Qwen API | Fast development without local LLM operations |
| Embeddings | `BAAI/bge-m3` | Batched dense embeddings on MPS or CPU |
| Reranking | `BAAI/bge-reranker-v2-m3` | Small-batch MPS/CPU inference |
| Lexical retrieval | `bm25s` plus Chinese tokenization | Simple and reproducible at this corpus scale |
| Vector store | Qdrant | Vectors, hierarchy, and provenance metadata |
| Parsing | Docling/PyMuPDF, with manual correction as needed | PDF, table, and heading extraction |
| Orchestration | Custom modules; LlamaIndex for reference only | Keeps core experiments transparent |
| API / UI | FastAPI / Streamlit | Efficient for a course demonstration |
| Experiment tracking | JSONL/CSV plus TensorBoard or MLflow | Fixed configs, results, and run records |
| Deployment / tests | Docker Compose / pytest | Reproducible startup and regression coverage |

On the 24 GB Mac, parsing, chunking, BM25, RRF, Qdrant, API, and UI run locally. Generate only BGE-M3 dense vectors in the first version (not sparse or ColBERT vectors), starting with batch size 8. Rerank 30–40 candidates in small batches. Persist embeddings every 500–2,000 chunks and record completed `chunk_id`s so interrupted jobs resume safely. Index only A/B-tier core sources and 2–3 medical domains initially; do not embed the entire 530k+ web corpus. Record API model ID, date, temperature, prompt version, input/output tokens, and request ID; load keys only from environment variables. All Mac-produced manifests, chunks, and vectors must be portable to a later server run.

```yaml
generation:
  provider: qwen_api
  model: ${QWEN_MODEL}
  temperature: 0
  max_output_tokens: 1200
retrieval:
  dense_model: BAAI/bge-m3
  device: auto                 # mps -> cpu
  embedding_batch_size: 8
  embedding_max_length: 512
  bm25_top_k: 30
  dense_top_k: 30
  fusion: rrf
  fused_top_k: 40
  reranker_model: BAAI/bge-reranker-v2-m3
  reranker_batch_size: 4
  final_top_k: 8
chunking:
  strategy: source_aware_hierarchical
  child_target_chars: 300-600
  child_max_chars: 800
  child_overlap_chars: 50-100
  parent_target_chars: 1000-2000
  preserve_tables: true
  never_cross_section: true
indexing:
  initial_sources: [clinical_guidance, expert_consensus, textbook]
  evidence_authority_tiers: [A, B]
  child_index: bm25_and_dense
  parent_index: metadata_first
  index_version: corpus_v1
verification:
  require_citation_for_medical_claims: true
  max_unsupported_critical_claims: 0
```

These are starting values only; select final settings on the validation set.

## 5. Data, Corpus, and Evaluation Sets

### 5.1 Corpus policy

The current Medical Corpus is a heterogeneous collection of plain text, not a unified library with complete publication metadata. Do not index it indiscriminately. First classify sources by authority and structural quality.

| Directory | Observed structure and scale | First-version role | Indexing decision |
|---|---|---|---|
| `Clinical Guidance` | 34 large TXT files; some contain multiple chapters | A-tier core evidence | Recover chapters/sections; split logical documents where necessary |
| `Expert Consensus` | 121 files, usually one consensus per file | A-tier core evidence | Hierarchical headings and recommendation items |
| `Textbook` | 6,726 topic files; some `neikexue/text (n).txt` book volumes | B-tier supplementary evidence | Use book+filename as document identity; mark contents/index pages separately |
| `Web Article` | 534,853 one-article files, often long single-line bodies | C-tier, not final evidence by default | Separate optional experimental index only |
| `Wiki` | one ~438 MB file with non-medical entries | excluded initially | Reconstruct article boundaries and filter medical topics first |
| `EMR` | 11,622 mixed task, note, and imaging-report files | excluded initially | Not normative evidence; requires separate privacy/governance review |

Select only 2–3 domains for version one (for example common chronic disease, antimicrobials and special-population medication, or common respiratory/cardiovascular disease). Never invent missing dates, versions, institutions, or URLs: store `null`/`unknown` until they are manually verified from reliable originals.

### 5.2 Required metadata

Every document schema must contain: `document_id`, title, authoring institution/author, document type, publication date/version, original URL or path, acquisition date, disease/specialty and population scope, licence/use notes, content hash, parent-child relationships, dataset category, relative path and filename, authority tier (`A/B/C`), final-evidence eligibility, metadata status (verified/provided/unknown), parser version, index version, and ingestion time. Missing but unverified values may be null; fields may not be omitted or guessed.

### 5.3 Public benchmarks and in-house trust set

Use [CMB](https://github.com/FreedomIntelligence/CMB) (CMB-Exam and CMB-Clin) and [CMExam](https://github.com/williamliujl/CMExam). Benchmark questions, answers, and explanations must never enter the retrieval corpus. Use fixed, stratified development subsets, preserve question IDs rather than rewriting questions, and run the final locked test only once. Document the limitation that public answers may have appeared in model pretraining.

Create an approximately 300-question in-house set: 150 directly answerable questions, 50 requiring two passages, 70 unanswerable questions, and 30 questions with missing conditions, false premises, or leading wording. Each item records answerability, reference answer/key points, required and acceptable alternative evidence IDs, critical qualifiers, expected behavior (answer/partial/refusal), annotator, and reviewer.

## 6. Source-Aware Hierarchical Chunking

Child passages must be short enough to retrieve medicine names, doses, symptoms, and contraindications precisely. Parent nodes must retain population scope, prerequisites, recommendation strength, and negation boundaries. Retain a fixed-length chunking baseline for comparison.

### 6.1 Preparation and source routing

- Preserve original TXT files read-only. Create normalized copies, UTF-8/LF normalized, while retaining the original hash.
- Merge only confirmed layout line breaks. Preserve headings, list items, paragraph boundaries, numbers, units, ranges, percentages, signs, and comparison operators. Do not automatically convert doses.
- Protect negation/qualification terms (for example *not*, *no*, *contraindicated*, *not recommended*, *use with caution*) with before/after count checks.
- Store `raw_text` and retrieval-only `normalized_text`; displayed citations always come from `raw_text`.
- Detect contents pages, author lists, and reference sections; exclude them from the evidence index by default.

| Source | Document boundary | Parent node | Child atom | Fallback |
|---|---|---|---|---|
| Clinical guidance | one guideline/standard; multiple logical documents permitted | chapter/section | paragraph, numbered recommendation, complete list item | blank lines + sentence boundaries; mark low structural confidence |
| Expert consensus | normally one TXT per consensus | numbered heading and subheading | discussion paragraph, diagnostic criterion, recommendation | paragraph-based parent candidates |
| Textbook topic file | book directory + topic filename | internal subsection | logical definition/etiology/diagnosis/treatment paragraph | full topic file as parent, then length-limited splitting |
| `neikexue` volumes | recover part/chapter before indexing | chapter/section | paragraph/list under subsection | leave out if chapter recovery fails |
| Optional web article | file is article; first nonblank line is title candidate | article | reconstructed paragraph | discard short, repetitive, or advertising-like samples |

### 6.2 Chunk rules and traceability

1. Segment by structure before length. Split an oversized atomic unit only on sentence boundaries.
2. Child chunks target 300–600 Chinese characters (maximum 800); merge undersized adjacent paragraphs within the same subsection.
3. Use the original subsection as the parent where possible (target 1,000–2,000 characters). Long sections may become multiple windows with the same section path.
4. Overlap 50–100 characters only within the same subsection. Never overlap across headings or documents.
5. Do not split a complete recommendation, dosage+route+frequency+population condition, contraindication, list lead-in with its list, or table heading from its row.
6. Permit an oversized indivisible item and record `oversize_reason`; medical meaning outranks length targets.
7. Embed `document_title + title_path + passage` for retrieval, but show only original text in citations.

Use deterministic IDs based on dataset category, normalized relative path, logical-document ordinal, and node ordinal. Detect changed content with a separate `content_hash`, never random IDs. For files without pages, cite relative path, line range, and character offsets; add `source_page` only when the original PDF is later verified.

```json
{
  "chunk_id": "expert_consensus/001/doc00/sec03/ch02",
  "document_id": "expert_consensus/001/doc00",
  "parent_id": "expert_consensus/001/doc00/sec03",
  "authority_tier": "A",
  "eligible_as_final_evidence": true,
  "document_title": "Chinese Expert Consensus on Diagnosis and Treatment of Post-traumatic Hydrocephalus",
  "title_path": ["Diagnosis and Differential Diagnosis", "Diagnostic Criteria"],
  "raw_text": "…",
  "normalized_text": "…",
  "source_path": "Medical Corpus/Expert Consensus/expert_consensus (1).txt",
  "source_line_start": 42,
  "source_line_end": 44,
  "source_char_start": 3180,
  "source_char_end": 3876,
  "content_hash": "sha256:…",
  "parser_version": "source_parser_v1",
  "structure_confidence": "high",
  "index_version": "corpus_v1"
}
```

Deduplicate exact documents by file hash, then identify near-duplicate candidates by title/body signatures. Keep distinct guideline editions, group them with `duplicate_group_id`, and prefer a verified current edition by default. Keep all source links for exact duplicate chunks; only group near duplicates to avoid deleting medically meaningful qualifications. Required quality flags include structural confidence, metadata completeness, dosage/negation presence, reference/index-page status, and manual-review status.

### 6.3 Chunking acceptance criteria

- [ ] Manually stratify and inspect at least 200 child chunks: 60 guidelines, 60 consensus documents, 60 textbooks, and 20 optional web items; at least five files per class.
- [ ] A-tier logical-document boundary accuracy ≥98% and heading-path accuracy ≥95%.
- [ ] Preserve dosage, route, frequency, special populations, contraindications, and negation semantics at 100%.
- [ ] Every retrievable chunk has document/parent IDs, source path, offsets, hash, authority tier, and index version.
- [ ] Any retrieved result replays exactly to the original TXT; ineligible content never passes the final-evidence filter.

## 7. Indexing, Retrieval, and Hierarchy Expansion

Maintain separate logical layers: document/parent storage for provenance and context; a BM25 child-passage index for exact terms; a Qdrant dense child-passage index for semantic retrieval and filtering; and an optional parent-vector index for ablation. BM25 and Qdrant must use the same `chunk_id`. A/B/C sources must be separated or strictly filtered; generation accepts only `eligible_as_final_evidence=true` A/B evidence by default.

### 7.1 Build process

1. Freeze a corpus manifest recording path, size, hash, category, and inclusion decision.
2. Create documents, parent nodes, and child passages using the source router.
3. Validate schema, citation replay, length, orphan parents, empty text, and duplicate hashes; quarantine failures.
4. Build BM25 and dense vectors from the same valid children and save a `chunk_id`–BM25-docid–Qdrant-point-ID mapping.
5. Record embedding model/revision, tokenizer/dictionary version, dimension, distance metric, build parameters, and timestamp.
6. Run fixed smoke queries for retrieval, authority filtering, parent fill-in, and source replay before publishing the index.

### 7.2 Online retrieval

1. Lightly normalize the question while preserving the original wording, numbers, units, and negation.
2. Apply metadata filters only when domain, document type, or population is identified reliably; low-confidence classifications must not impose hard filters.
3. Retrieve Top-30 from BM25 and BGE-M3 separately and retain both rankings.
4. Fuse using RRF, exact-deduplicate by `chunk_id`, limit near-duplicate clusters, and retain Top-40.
5. Rerank question–child-passage pairs; take the top 12 for hierarchy expansion.
6. Group hits by `parent_id`, reward repeated hits from a parent, and merge adjacent children.
7. Add title path plus neighbouring atomic units first; add the full parent only if qualifications remain incomplete.
8. Within the context budget, retain at most two evidence windows per parent and three per document, then keep 6–8 final windows.
9. Recheck authority, source diversity, and coverage of critical entities/conditions. Route inadequate evidence to refusal pre-check.

All Top-K and budget values are validation-set parameters, never tuned on the final test. Each index version is immutable and linked to its corpus manifest, parser/chunker version, BM25 configuration, and embedding revision. A changed document rebuilds only its nodes and marks old nodes stale. Changes to chunking, tokenization, or embeddings require a new index version; publish only after regression tests pass.

Log original/normalized questions, filters, index version, rankings and scores at every retrieval stage, expansion/deduplication/truncation decisions, final evidence IDs and offsets, authority tiers, token use, latency, annotated-evidence hits, and refusal triggers. Measure Recall@5/10, MRR, nDCG@10, parent coverage, qualifier coverage, source diversity, authority-filter violations, mean/P95 latency, and context tokens. Require matching BM25/Qdrant retrievable ID sets, 100% parent backfill, zero ineligible final citations, and an honest comparison with fixed-length chunking—even if hierarchy does not improve a preregistered primary metric.

## 8. Generation, Citations, and Refusal

The Qwen prompt includes the user question, necessary chat context, numbered evidence passages, a strict output schema, the instruction to answer only from evidence, and an explicit insufficient-evidence condition.

```json
{
  "answer": "…[S1]…[S3]",
  "claims": [
    {"claim": "…", "citation_ids": ["S1"], "importance": "critical"}
  ],
  "insufficient_evidence": false,
  "limitations": ["…"]
}
```

The interface resolves citations to document title, section path, supporting original text, version/date, and source link or page. Verify every generated claim against its cited passages as `supported`, `partially_supported`, `unsupported`, or `conflicting`. Delete an unsupported noncritical claim and disclose the limitation. For an unsupported critical claim, revise or regenerate once, then refuse if the issue remains. Include manual audit results in the final report; [ALCE](https://github.com/princeton-nlp/ALCE) and [SourceCheckup](https://github.com/kevinwu23/SourceCheckup) are useful evaluation references.

Refusal uses multiple validation-calibrated signals: low reranker scores; diffuse top results; missing critical entity/condition coverage; no direct support for a core claim; conflicts among high-quality sources; or an individualized diagnostic request when the corpus provides only general information. Report refusal precision, recall, F1, false-refusal rate, wrong-answer rate, and coverage–risk curves.

## 9. Experimental Matrix

Keep the test set, Qwen model, core prompt, and output parser fixed across experiments.

| ID | Setting | Purpose |
|---|---|---|
| E0 | Qwen, no RAG | generation baseline |
| E1 | Dense RAG | dense retrieval baseline |
| E2 | BM25 RAG | lexical retrieval baseline |
| E3 | BM25 + dense + RRF | hybrid-retrieval contribution |
| E4 | E3 + reranker | reranking contribution |
| E5 | E4 + parent-child retrieval | hierarchical contribution |
| E6 | E5 + claim-level verification | citation-reliability contribution |
| E7 | E6 + calibrated refusal | complete trustworthy system |

Also ablate chunk size/overlap, Top-K, child-only versus parent context, fixed versus structure-aware chunks, verification on/off, and single-threshold versus multi-signal refusal.

| Dimension | Metrics |
|---|---|
| QA | CMB/CMExam accuracy; open-question F1/manual correctness |
| Retrieval | Recall@K, MRR, nDCG@10 |
| Citations | citation precision/recall, claim coverage |
| Refusal | precision, recall, F1, false-refusal rate |
| Robustness | correct behavior on noisy evidence, false premises, missing conditions |
| System | P50/P95 latency, failure rate, peak memory, MPS/CPU usage, API tokens/cost |

Engineering targets—not claimed results—are Recall@10 ≥0.80, critical-claim citation coverage ≥0.95, manually audited citation support ≥0.85, unanswerable-set refusal F1 ≥0.75, no loss versus E0 in full-system accuracy, and reproducibility of E3–E7 with one script. Report negative results and error types transparently.

## 10. Web Application and Safety Requirements

The user interface must accept Chinese questions, stream answers, expand and locate citations, upload PDF/Markdown/TXT files, show upload/indexing progress, delete user uploads and indexes, support session-scoped follow-up questions, show insufficient-evidence/source-conflict states, and export answers. Administration/debug tools expose top-10 results, E0–E7 configuration switching, stage latency, Qwen token use, prompt/model versions, and downloadable retrieval/answer/verification logs.

Restrict file type and size, validate filenames and parsed content, isolate each session namespace, avoid sending real patient data to Qwen, redact possible personal information in logs, and display a research-only/non-diagnostic notice.

## 11. Suggested Repository Layout

```text
medical-rag/
├── README.md  ├── pyproject.toml  ├── docker-compose.yml  ├── .env.example
├── configs/{base.yaml,experiments/,prompts/}
├── data/{manifests/,raw/,processed/,eval/}
├── src/{ingestion/,chunking/,indexing/,retrieval/,reranking/,generation/,verification/,refusal/,api/}
├── web/  ├── eval/  ├── tests/  ├── scripts/
└── docs/{architecture.md,data_card.md,evaluation_protocol.md,deployment.md}
```

Do not commit restricted original data under `data/raw/`.

## 12. Twelve-Week Implementation Plan

| Week | Main work | Milestone |
|---|---|---|
| 1 | Freeze 2–3 topics; establish source/licence/version rules, repository, config/logging, macOS PyTorch/MPS fallback, BGE/reranker/Qwen smoke tests; read MedRAG, BGE-M3, ClinicalRAG. | Dependencies run; scope and interfaces fixed. |
| 2 | Freeze corpus inventory and hash manifest; sample parsers for guidance, consensus, textbook, and volumes; define A/B/C policy and node/citation schema; audit cleaning. | Structured, replayable samples; out-of-scope data cannot enter evidence store. |
| 3 | Build fixed-length and structure-aware chunks with parent-child links; protect recommendations/doses/contraindications/negations; group duplicates; lock benchmark subset; annotate first 50–100 questions; implement E0. | `corpus_v1` frozen after audit; all chunks have parents and offsets. |
| 4 | Build BM25 and BGE-M3/Qdrant; validate ID mapping, filters, context backfill, replay; implement E1/E2 and retrieval metrics. | Independent lexical and dense retrieval are evaluated. |
| 5 | Implement deduplication/RRF and E3; tune validation Top-K/fusion; compare keyword/semantic queries and A vs A+B vs optional C retrieval. | Hybrid retrieval stable on validation. |
| 6 | Add reranker, E4, fixed candidate/final K, complete retrieval traces, and failure analysis. | Track-A baseline complete. |
| 7 | Add parent context, parent clustering, adjacent merge, document quotas/budget, E5; test tables, special populations, contraindications; compare quality/latency/cost. | Track-B hierarchy complete. |
| 8 | Define answer schema, citation numbering/replay, API cache/retry/cost tracking, citation UI, and basic conversational rewriting. | Clickable evidence-backed answers work. |
| 9 | Extract/verify claims, implement E6, construct unanswerable/leading validation set, calibrate refusal, implement E7. | Complete A+B route refuses insufficient-evidence questions. |
| 10 | Build FastAPI, Streamlit, upload/parse/index/delete/namespace isolation, streaming/errors, and Docker Compose. | Full live demo is possible. |
| 11 | Lock test/config/prompt versions; run E0–E7 and ablations; audit ≥100 answers/citations; profile latency, memory, MPS/CPU, token use, and cost. | Reproducible result and error-analysis tables. |
| 12 | Clean repository; finalize README, deployment guide, data card, reports, demo script/cases; reproduce once on a clean machine. | Code, results, reports, and demo ready to submit. |

## 13. Team Responsibilities

- **Member 1 — Data and documents:** source collection/licences, PDF parsing, cleaning, hierarchical chunking, data card.
- **Member 2 — Retrieval and reranking:** BM25, BGE-M3, RRF, reranker, Qdrant, retrieval evaluation.
- **Member 3 — Generation and trust:** Qwen API, prompting, citation generation, claim verification, refusal policy.
- **Member 4 — System and evaluation:** FastAPI, UI, uploads, unified experiment scripts, deployment, demonstration.

Everyone contributes to reading, manual audits, error analysis, and the final report.

## 14. Key Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Unclear corpus licence/provenance | Maintain a manifest; prioritize public authoritative materials; do not publish restricted originals. |
| Errors recovering plain-text structure | Preserve source path/offsets, audit targeted cases, manually correct key documents. |
| Test leakage | Strict corpus/evaluation separation and document-hash duplicate checks. |
| RAG reduces accuracy or citations do not entail claims | Evaluate retrieval independently; rerank, expand hierarchy, verify claims, and manually audit. |
| Excessive refusal | Calibrate on validation and report false refusals alongside coverage. |
| API drift, cost, throttling, or outages | Log model/date/settings, cache results, resume jobs, retry with rate limiting, evaluate in batches. |
| MPS incompatibility / insufficient Mac throughput | CPU fallback, smaller batches/lengths, on-disk batches, and A/B-only initial corpus. |
| Server remains unavailable | Keep core workflow Mac-native; defer or sample web-scale experiments. |
| Twelve-week scope creep | Limit v1 to 2–3 domains and prioritize E0–E7 plus trust evaluation. |
| Sparse publishing metadata / low-authority material overwhelms evidence | Mark unknown explicitly; manually verify critical A-tier records; isolate/filter C-tier sources. |

## 15. Deliverables and Definition of Done

Deliver: runnable code; Docker Compose/startup instructions; parsing and indexing scripts; unified E0–E7 scripts; web app and deployment notes; model/prompt/data configs; tests; corpus manifest/data card; in-house trust set and audit protocol; retrieval/QA/citation/refusal tables; ablations, errors, per-question outputs, and logs; technical/reporting materials, diagrams, demo script, and defense slides.

The project is complete only when a new machine can start the system from the README; uploaded documents can be parsed, indexed, queried, and cited; E0–E7 produce result tables with a unified command; fixed public subsets and the trust set are evaluated; every critical medical claim is cited or the system refuses; citation/refusal metrics receive manual audit; and all code, configurations, logs, results, reports, and demonstrations—including reproducible negative-result analysis—are submitted.

## 16. Essential References

1. [Benchmarking Retrieval-Augmented Generation for Medicine (MedRAG/MIRAGE)](https://aclanthology.org/2024.findings-acl.372/)
2. [BGE M3-Embedding](https://arxiv.org/abs/2402.03216) and [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding)
3. [ClinicalRAG](https://ojs.aaai.org/index.php/AAAI/article/view/35384)
4. [ALCE: Enabling LLMs to Generate Text with Citations](https://github.com/princeton-nlp/ALCE)
5. [SourceCheckup](https://github.com/kevinwu23/SourceCheckup)
6. [CMB](https://github.com/FreedomIntelligence/CMB), [CMExam](https://github.com/williamliujl/CMExam), [Qdrant](https://github.com/qdrant/qdrant), [LlamaIndex](https://github.com/run-llama/llama_index), and [Qwen](https://github.com/QwenLM/Qwen)
