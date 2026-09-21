# corpus_v1 分片与索引交接说明

更新日期：2026-09-21

## 1. 当前完成状态

`corpus_v1` 的语料分配、来源感知分片、父子节点存储、BM25 索引和 BGE-M3
稠密索引已经完成并通过一致性验收。

| 项目 | 结果 |
|---|---:|
| 纳入文档 | 6,881 |
| 父节点 | 28,754 |
| 全部子片段 | 47,039 |
| 可作为最终证据的子片段 | 46,516 |
| SQLite/BM25 可检索证据 | 46,516 |
| Qdrant 正式集合向量 | 46,516 |
| BM25/Qdrant ID 缺失或多余 | 0 |
| 错误 point ID / payload | 0 / 0 |
| 原文偏移回放错误 / 孤儿节点 | 0 / 0 |

正式向量集合为 `corpus_v1_children`：

- 模型：`BAAI/bge-m3`
- 设备：Mac MPS
- 精度：FP32
- 最大输入长度：512
- 维度：1024
- 距离：Cosine
- 向量归一化：是
- 构建 batch size：8
- 状态：green

端到端查询“颅脑创伤后脑积水如何诊断？”时，Dense Top-2 命中了 A 级专家共识的
“概述”和“诊断标准”，证明模型编码、Qdrant 查询和 payload 返回链路可用。

## 2. 资产位置

| 路径 | 内容 | 后续用途 |
|---|---|---|
| `data/manifests/corpus_scope.json` | 全部来源的纳入/排除策略与目录规模 | 数据范围审计 |
| `data/manifests/corpus_v1.jsonl` | A/B 文档 manifest、哈希和编码 | 增量更新判断 |
| `data/processed/corpus_v1/documents.jsonl` | 文档级元数据 | 数据检查与导出 |
| `data/processed/corpus_v1/parents.jsonl` | 父节点原文和子节点列表 | 离线复核 |
| `data/processed/corpus_v1/chunks.jsonl` | 子片段、偏移、质量标记和检索文本 | 重建索引 |
| `data/processed/corpus_v1/quality_report.json` | 分片自动验收结果 | 数据质量门禁 |
| `data/indexes/corpus_v1/bm25.sqlite3` | 文档、父节点、子片段原文与 FTS5-BM25 | 关键词召回和父节点补全 |
| `data/indexes/corpus_v1/qdrant/` | Qdrant local 持久化数据 | 稠密召回 |
| `logs/dense_index.log` | 正式稠密索引进度和完成配置 | 构建审计 |

以上目录均已在 `.gitignore` 中排除。代码和配置可提交，语料、索引、模型及运行日志不提交。

## 3. ID 与数据契约

两路索引必须以 `chunk_id` 精确合并，不按文本、标题或数组位置合并。

- SQLite `chunks.chunk_id`：子片段主键。
- SQLite `chunks.qdrant_point_id`：`uuid5(NAMESPACE_URL, chunk_id)`。
- Qdrant point ID：与上述 UUID 完全相同。
- Qdrant payload `chunk_id`：与 SQLite 主键完全相同。
- `parent_id`：命中后补充父章节的唯一键。
- `document_id`：文档限额、来源聚类和引用展示的唯一键。

最终生成阶段只允许：

```text
eligible_as_final_evidence = true
authority_tier in {A, B}
index_version = corpus_v1
```

不得把 smoke 集合、C 级网页、Wiki 或 EMR 作为最终证据。

## 4. 后续检索模块的调用约定

### 4.1 BM25

调用 `medical_rag.indexing.bm25_sqlite.search_bm25`，默认召回 Top-30。返回值已经按
BM25 相关度从高到低排列，并包含 `chunk_id`、原文、父节点、权威等级和来源路径。

```python
from pathlib import Path
from medical_rag.indexing.bm25_sqlite import search_bm25

hits = search_bm25(
    Path("data/indexes/corpus_v1/bm25.sqlite3"),
    "颅脑创伤后脑积水如何诊断？",
    limit=30,
)
```

### 4.2 Dense

查询必须使用同一模型和处理条件：`BAAI/bge-m3`、最大长度 512、输出 L2
归一化。Qdrant 查询正式集合 `corpus_v1_children`，取 Top-30，并保留 cosine score。

### 4.3 RRF 融合

下一阶段按以下契约实现：

1. BM25 和 Dense 各取 Top-30；
2. 仅以 `chunk_id` 去重；
3. 使用 `RRF(d) = Σ 1 / (60 + rank_i(d))`；
4. 保留两路原始排名和分数，不把 BM25 分数与 cosine score 直接相加；
5. 融合后取 Top-40 交给 reranker；
6. 任一路缺失时允许降级运行，并在检索日志记录降级原因。

### 4.4 父节点补全

Rerank 后通过 SQLite 获取父节点，避免扫描 JSONL：

```python
from pathlib import Path
from medical_rag.indexing.bm25_sqlite import get_parent

parent = get_parent(
    Path("data/indexes/corpus_v1/bm25.sqlite3"),
    hit["parent_id"],
)
```

后续应实现同父节点聚类、相邻片段合并、每文档最多 3 个窗口及最终 6–8 个证据窗口。

## 5. 验收与复现

运行完整 ID/payload 审计：

```bash
.venv/bin/python scripts/audit_indexes.py
```

预期 `passed=true`，并满足：

- `expected_eligible_chunks = qdrant_points = 46516`
- `missing = extra = bad_payload = bad_point_ids = 0`
- `vector_dimension = 1024`

运行 MPS 诊断和两路检索冒烟测试：

```bash
.venv/bin/python scripts/corpus_pipeline.py doctor
python3 scripts/corpus_pipeline.py search "颅脑创伤后脑积水如何诊断？" --limit 5
```

## 6. 已知问题与决策

1. **Qdrant local mode 容量提示**：正式集合超过 20,000 点，`qdrant-client` 会提示
   local mode 不适合更大集合。当前单机研究与离线实验可继续使用；进入 FastAPI、多进程或
   Docker 部署前，应迁移到 Qdrant server，并重新运行本页验收脚本。
2. **并发限制**：同一 local Qdrant 路径不能由多个进程同时打开。当前检索服务必须单进程，
   或统一通过一个持有 client 的服务访问。
3. **测试集合**：`corpus_v1_fp16_smoke`、`corpus_v1_fp16_b16_smoke`、
   `corpus_v1_fp16_b32_smoke` 各有 1,024 点，仅用于吞吐测试，不参与正式检索。确认无需保留
   后可单独删除，不要删除 `corpus_v1_children`。
4. **BM25 实现差异**：当前使用零依赖 SQLite FTS5 trigram BM25，而方案原推荐
   `bm25s + 中文分词`。它已能稳定召回中文医学词组，可作为 E2 基线；后续如加入 jieba/bm25s，
   应作为独立实验配置，不应静默覆盖当前基线。
5. **运行环境**：当前虚拟环境是 Python 3.9.6、PyTorch 2.8.0；MPS 已真实执行通过。
   进入 API 阶段前建议迁移到计划中的 Python 3.11/3.12 并重新跑回归测试。LibreSSL 警告
   不影响本地索引，但 API/HTTPS 阶段应改用新版 Python 的 OpenSSL 构建。
6. **人工复核**：仍有 1,623 个片段带 `needs_manual_review=true`，主要来自结构置信度低、
   非正文或极短片段。开始正式评测前应按来源分层抽检，不能把自动验收等同于医学正确性。

## 7. 建议的下一步顺序

1. 实现 Dense 检索封装和 BM25/Dense 统一 `RetrievalHit` Schema；
2. 实现 RRF、重复簇限额和检索日志；
3. 接入 `bge-reranker-v2-m3`，完成 Top-40 → Top-12；
4. 实现父节点补全和上下文预算；
5. 建立首批带必需 `chunk_id` 的检索评测题，再调 Top-K；
6. 迁移 Qdrant server 后再接 FastAPI，避免 local mode 多进程锁问题。

