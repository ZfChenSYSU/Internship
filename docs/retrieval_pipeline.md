# RRF、BGE 重排与父节点补全实现说明

更新日期：2026-09-21

## 1. 当前实现

在线检索链路已按技术路线 E3–E5 拆成可独立测试的阶段：

```text
BM25 Top-30 ─┐
             ├─ RRF(k=60) → 重复簇限额 → Top-40
Dense Top-30 ┘                         → BGE reranker Top-12
                                      → 同父节点聚类与相邻子片段补全
                                      → 父/文档配额与上下文预算 → 6–8 个窗口
```

- `retrieval/models.py`：统一 `RetrievalHit`、`EvidenceWindow` 与阶段追踪结果。
- `retrieval/dense.py`：复用 BGE-M3 编码器，查询正式 Qdrant 集合，再从 SQLite 补回引用原文。
- `retrieval/fusion.py`：仅按 `chunk_id` 合并；保留 BM25/cosine 原始分数与名次，不直接相加。
- `reranking/bge.py`：`bge-reranker-v2-m3` 小批量交叉编码重排。
- `retrieval/hierarchy.py`：按 `parent_id` 聚类，以最佳子命中排名为主、重复命中为有界奖励，
  再以相邻子节点构造精确原文窗口；短片段或存在指代线索时回退完整父节点，并执行每父节点
  2 窗口、每文档 3 窗口和总字符预算。
- `retrieval/hybrid.py`：端到端编排、重复簇限制、单路故障降级与阶段日志。

## 2. 起始参数

起始参数写在 `configs/base.yaml`。当前使用 BM25/Dense 各 30、RRF k=60、融合 40、
rerank 12、最终最多 8 个证据窗口、总预算 12,000 字符。它们是开发集校准前的工程默认值，
不是实验结论。

父节点补全优先使用父节点和子节点的原文偏移直接切片，确保引用仍可回放到原始 TXT；只有
旧索引缺少偏移时才使用去重叠文本拼接。上下文扩展不会改变子命中的 `chunk_id`，窗口同时
记录全部组成子节点 ID、父节点 ID、文档 ID 和来源偏移。

## 3. 运行与降级

完整链路：

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python scripts/corpus_pipeline.py retrieve \
  "颅脑创伤后脑积水如何诊断？" --device auto
```

命令默认优先使用 `models/huggingface/` 中已有的本地快照（包括中断后已完整取得核心
PyTorch 文件的快照），避免离线运行时再次访问模型仓库；其他位置用 `--model-cache` 指定。

离线或尚未准备模型权重时可验证 RRF 和父节点链路：

```bash
.venv/bin/python scripts/corpus_pipeline.py retrieve \
  "颅脑创伤后脑积水如何诊断？" --no-dense --no-reranker
```

任一路召回或 reranker 失败时，结果的 `trace.degraded` 为 `true`，原因写入
`trace.errors`。不得在正式评测时把降级结果当作 E4/E5 完整结果。

## 4. 已完成验收

- RRF 排序、去重、原始排名/分数保留与确定性并列排序单测；
- reranker 排序封装单测（注入轻量假模型，不依赖权重下载）；
- 父节点相邻补全、精确偏移回放和完整流水线单测；
- 正式 46,516 点 Qdrant 集合查询接口、A/B 过滤和 SQLite 原文补全冒烟；
- 全部测试 10 项通过。

真实模型 CPU 与 MPS 端到端冒烟均已通过：BM25/Dense 各返回 30 条、RRF 输出 40 条、reranker
输出 12 条、父节点预算后输出 4 个窗口，`trace.degraded=false`。CPU 冷启动模型加载约 8.29 秒，
单次检索、重排与补全约 12.01 秒；MPS 冷启动约 13.21 秒、检索链路约 6.58 秒。
这些只是当前机器的一次冒烟值，不作为正式性能结论。首个父窗口为专家共识的“诊断标准”，
其后为“PTH 的分类”和“诊断标准 > 鉴别诊断”。

受限沙箱进程内 `doctor` 会报告 `mps_available=false`，但同一虚拟环境在沙箱外/本机终端中
报告 `mps_available=true` 且张量测试通过，根因是 Metal 设备权限隔离，不是 PyTorch 或模型
配置错误。日常命令使用 `--device auto` 可安全回退；必须验证 MPS 时在本机终端运行
`scripts/run_hybrid_retrieval.command`，该脚本会先执行 `doctor`，再以 `--device mps` 强制运行，
设备不可用时立即失败而不会悄悄改用 CPU。

## 5. 下一步计划

1. 标注首批检索开发题：直接命中、跨两段、特殊人群、剂量/禁忌和不可回答问题，并记录
   必需及可接受替代 `chunk_id`。
2. 在开发集上校准候选数、RRF k、rerank Top-K、相邻范围、文档配额和上下文预算；最终
   测试集不参与调参。
3. 在 CPU/MPS 上重复运行固定查询集，记录 P50/P95 延迟、峰值内存与失败率。
4. 输出 E1–E5 的 Recall@5/10、MRR、nDCG@10、父节点覆盖、限定条件覆盖和延迟，固定配置
   后再对接 Qwen 生成、引用核验和拒答。
