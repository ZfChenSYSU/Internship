# 开发状态与项目内部记录

本文由原根目录 `README.md` 迁移整理而来，保留课程项目背景、当前语料统计、工程验收结果和
后续计划，主要供维护者和项目成员使用。面向外部使用者的安装与运行说明请查看
[公开 README](../README.md)。

## 项目背景与目标

本项目面向中文医疗知识问答，目标是构建一个**证据可追溯、引用可核验、证据不足时主动
拒答**的 RAG 系统。项目仅用于课程研究与工程验证，不用于真实临床诊断或治疗。

- 从权威中文医疗资料中进行关键词与语义混合检索；
- 通过重排和分层父子节点检索补全上下文；
- 仅依据检索证据生成回答，并给出可定位引用；
- 在证据缺失、条件不足或来源冲突时部分或完整拒答；
- 通过消融实验评估检索、引用核验与拒答模块贡献。

系统采用 A+B 组合路线：路线 A 负责 BM25/BGE-M3 混合检索、RRF、重排和证据生成；路线 B
保留文档层级、补充父章节限定条件，并计划完成陈述级引用支持度核验。

```text
医疗文档 → 解析、清洗、分层切分 → 关键词索引 + 向量索引

用户问题 → 混合检索 → 融合与重排 → 父节点上下文补充
        → 证据充分性检查 → 基于证据生成 → 陈述级引用核验
        → 带引用回答 / 拒答
```

## 当前进度

目前已经完成离线语料、双路索引、混合检索、真实模型端到端验收和本地 Web 原型。下一阶段
进入检索集标注、参数校准、E1–E5 评测、引用核验和拒答开发。

| 模块                        | 状态 | 当前结果                                                        |
| --------------------------- | :--: | --------------------------------------------------------------- |
| 数据范围与权威分级          |  ✅  | A 级指南/共识与 B 级教材进入`corpus_v1`；网页、Wiki、EMR 排除 |
| Manifest 与来源追踪         |  ✅  | 6,881 份文档均保存路径、哈希、类别和纳入决定                    |
| 来源感知父子分片            |  ✅  | 28,754 个父节点、47,039 个子片段                                |
| 分片质量检查                |  ✅  | 原文回放错误 0、孤儿节点 0、处理失败文件 0                      |
| BM25 索引                   |  ✅  | SQLite FTS5-BM25，46,516 条可检索证据                           |
| Dense 索引                  |  ✅  | BGE-M3 + MPS + Qdrant，46,516 个 1024 维向量                    |
| 双索引一致性验收            |  ✅  | 缺失、额外点、错误 ID 和错误 payload 均为 0                     |
| BM25 + Dense + RRF          |  ✅  | 统一命中结构、RRF k=60、单路降级与阶段追踪已实现                |
| BGE reranker 与父节点补全   |  ✅  | 真实模型 MPS 端到端通过；待校准 Top-K 与上下文预算              |
| DeepSeek 生成               |  ✅  | Flash、自然语言流式输出、10,000 max tokens、Reasoning 可选      |
| 本地 Web 演示               |  ✅  | 单页输入、流式回答、思考面板和引用证据列表                      |
| 引用核验与校准拒答          |  ⏳  | 尚未完成                                                        |
| FastAPI、正式部署与完整评测 |  ⏳  | 尚未开始                                                        |

正式 Qdrant 集合为 `corpus_v1_children`。Dense 冒烟查询“颅脑创伤后脑积水如何诊断？”
成功召回 A 级专家共识的“概述”和“诊断标准”。Dense 单路仍会召回治疗段落和作者信息，
因此不能直接把 Dense Top-K 交给生成模型。

## 当前资产

| 路径                                             | 内容                             |
| ------------------------------------------------ | -------------------------------- |
| `data/manifests/corpus_scope.json`             | 全来源纳入/排除策略和目录规模    |
| `data/manifests/corpus_v1.jsonl`               | A/B 文档 manifest、哈希和编码    |
| `data/processed/corpus_v1/documents.jsonl`     | 文档级元数据                     |
| `data/processed/corpus_v1/parents.jsonl`       | 父节点原文和子节点列表           |
| `data/processed/corpus_v1/chunks.jsonl`        | 子片段、偏移、质量标记和检索文本 |
| `data/processed/corpus_v1/quality_report.json` | 分片自动验收结果                 |
| `data/indexes/corpus_v1/bm25.sqlite3`          | BM25、父节点和引用原文           |
| `data/indexes/corpus_v1/qdrant/`               | 正式稠密向量集合                 |
| `models/huggingface/`                          | BGE-M3 与 BGE reranker 本地缓存  |

生成物、语料、索引、模型和日志均由 `.gitignore` 排除。对外发布时由维护者通过经过版权与
隐私复核的百度网盘包分发，并记录版本、文件哈希和许可信息。

## 当前验收基线

```text
documents = 6881
parents = 28754
all_children = 47039
eligible_children = 46516
bm25_rows = 46516
qdrant_points = 46516
missing = extra = bad_payload = bad_point_ids = 0
vector_dimension = 1024
passed = true
```

MPS 端到端查询“颅脑创伤后脑积水如何诊断？”：

```text
BM25 = 30
Dense = 30
RRF = 40
reranked = 12
final_evidence_windows = 4
degraded = false
```

父节点排序已从无界重复命中奖励改为“最佳子命中主导 + 有界重复奖励”，修复治疗父节点因
重复命中过多而压过“诊断标准”的问题。

DeepSeek Web 冒烟：

| 模式           | 结果                                                 |
| -------------- | ---------------------------------------------------- |
| Reasoning 关闭 | 4 条证据、0 字思考内容、1,334 字回答，约 10.1 秒     |
| Reasoning 开启 | 4 条证据、4,023 字思考内容、1,295 字回答，约 20.6 秒 |

上述耗时只是一轮本机冒烟值，不作为正式性能结论。

## 当前技术决策

- 运行环境为 macOS、24 GB 统一内存；本地模型优先使用 MPS，失败时回退 CPU；
- BM25 基线使用 SQLite FTS5 trigram，不静默替换为 `bm25s + 中文分词`；
- Dense 只使用 BGE-M3 的 1024 维 dense vector，不使用 sparse/ColBERT 输出；
- Qdrant 暂用 local mode，进入多进程服务前迁移 Qdrant Server；
- RRF 使用 `1 / (60 + rank)`，不直接相加 BM25 与 cosine 分数；
- reranker 使用 `BAAI/bge-reranker-v2-m3`，候选 Top-40 → Top-12；
- 最终生成最多使用 8 个窗口、每父节点最多 2 个、每文档最多 3 个；
- 当前 DeepSeek 配置为 `deepseek-flash`、temperature 0、max tokens 10,000；
- DeepSeek 输出是自然语言，内部传输协议才使用 NDJSON 流式事件。

## 数据与隐私记录

本地 `Medical Corpus/` 目录盘点的表观大小约 1.50 GB。`corpus_v1` 实际纳入约 39.1 MB
的 A/B 级资料：

- Clinical Guidance：34 份，A 级；
- Expert Consensus：121 份，A 级；
- Textbook：6,726 份，B 级；
- Web Article、Wiki 和 EMR：首版全部排除。

仍有 1,623 个片段带 `needs_manual_review=true`，主要来自结构置信度低、非正文或极短片段。
自动验收只能证明工程一致性，不能替代医学正确性、来源授权与出版版本核验。

## 当前限制

1. Qdrant local mode 超过 20,000 点会给出规模提示，且同一路径不能被多个进程安全打开。
2. 检索参数仍是路线文档的起始值，尚未使用正式标注开发集校准。
3. BM25 trigram 能召回中文医学词组，但没有显式中文医学分词。
4. 自动 claim-level citation verification 和校准拒答尚未实现。
5. 当前 Web 是单轮、单用户、本机原型，没有鉴权、上传、会话隔离和持久历史。
6. DeepSeek 会接收用户问题和最终证据窗口，只能发送允许交由第三方处理的内容。
7. 语料出版日期、版本、机构与 URL 的人工核验尚未全部完成。

## 下一阶段计划

1. 建立包含直接命中、跨两段、特殊人群、剂量/禁忌、不可回答问题的检索开发集；
2. 校准候选数、RRF k、rerank Top-K、相邻范围、文档配额和上下文预算；
3. 输出 E1–E5 的 Recall@5/10、MRR、nDCG@10、父节点覆盖和限定条件覆盖；
4. 实现陈述级引用支持度核验和多信号拒答；
5. 分层抽检 `needs_manual_review` 片段，并核验关键 A 级来源版本；
6. 迁移 Qdrant Server 后再建设多进程 API、文档上传和会话隔离；
7. 锁定开发集、测试集、模型、提示词和配置后运行 E0–E7。

## 内部常用命令

```bash
# MPS 诊断
.venv/bin/python scripts/corpus_pipeline.py doctor

# 双索引审计
.venv/bin/python scripts/audit_indexes.py

# 完整检索
scripts/run_hybrid_retrieval.command '颅脑创伤后脑积水如何诊断？'

# 本地 Web
scripts/run_local_web.command

# 测试
.venv/bin/python -m pytest -q
```

## 相关设计文档

- [公开 README](../README.md)
- [corpus_v1 数据卡](data_card.md)
- [索引交接说明](index_handoff.md)
- [检索流水线实现](retrieval_pipeline.md)
- [本地 Web 演示](local_web_demo.md)
- [完整英文技术路线](../Medical_RAG_A+B_Technical_Roadmap_and_Implementation_Plan.md)
- [中文技术路线](../题目2_A+B技术路线与实施计划.md)
