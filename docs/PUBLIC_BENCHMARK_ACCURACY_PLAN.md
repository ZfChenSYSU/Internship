# 公开医学问答数据集正确率测试方案

版本：v1.0（2026-09-30）  
范围：先测标准答案正确率；本轮不进行幻觉率、陈述级引用支持率或临床安全性评测。

## 1. 目标与现状

本方案沿用[原技术路线的 E0–E7 实验矩阵](../题目2_A+B技术路线与实施计划.md#9-实验矩阵)，用相同试题和评分器比较无检索、不同检索组件、以及同一大模型执行自检和拒答后的答题表现。当前实际生成服务是 DeepSeek Flash，而原计划写的是 Qwen；正式实验应固定**实际运行的同一个模型 ID**，并在报告中注明偏离原计划。不要把 DeepSeek 与 Qwen 的结果放入同一条 E0–E7 消融链。

根据[开发状态](DEVELOPMENT_STATUS.md)，`corpus_v1` 已有 46,516 条可检索证据，BM25、BGE-M3、RRF、重排和父节点补全已经端到端通过；目前还没有公开数据集适配器、统一批量运行器、严格选项解析器和结果表。现有 `src/medical_rag/cli.py` 是单题检索入口，`src/medical_rag/webapp/server.py` 是单轮流式问答入口。测试前先补充批量评测代码；不需要等待 FastAPI 或正式部署。

**主要问题**：在固定模型、题目、提示词主体和 `corpus_v1` 时，各检索阶段使考试题正确率改变多少？E6/E7 只额外观察“同一模型自检或自主拒答”对正确率和作答覆盖率的影响，不能据此声称完成了独立引用核验或阈值校准。

## 2. 数据集与代码调研

| 数据集 | 官方数据与代码 | 本实验取用 | 标签与评分 | 适用性 |
| --- | --- | --- | --- | --- |
| CMB | [官方仓库](https://github.com/FreedomIntelligence/CMB)，[官方 `score.py`](https://github.com/FreedomIntelligence/CMB/blob/main/score.py) | **CMB-Exam 的 CMB-test**；CMB-val 仅用于开发。官方公布 CMB-test 11,200 题、CMB-val 280 题；题型有单选和多选。 | 输出 `id` 与 `model_answer`；单选与多选分开统计，多选按**选项集合完全一致**才算正确。 | 中文主测集。CMB-Clin 是开放式病例问答，不纳入本轮自动正确率。 |
| CMExam | [官方仓库](https://github.com/williamliujl/CMExam)，[官方数据目录](https://github.com/williamliujl/CMExam/tree/main/data)，[评测代码目录](https://github.com/williamliujl/CMExam/tree/main/src/evaluation) | 官方 `val.csv` 调试，`test_with_annotations.csv` 测试。仓库报告 54,497/6,811/6,811 的 train/val/test 划分。 | 按原始答案列核对选择题；导入时确认答案格式、题目与选项列。可参照官方评分代码，但本项目统一实现严格 exact match。 | 中文主测集；可按官方科室、学科和难度标签分层分析。 |
| MedQA | [原作者仓库](https://github.com/jind11/MedQA)，[论文](https://arxiv.org/abs/2009.13081) | **中国大陆简体中文、`4_options` 的官方 dev/test**；原作者同时提供美国英文与台湾繁体题集。本轮先不把它们混入中文主结果。 | 官方题目文件是 JSONL，包含 train/dev/test；每题单个正确选项，按选项 exact match。 | 中文主测集；其教材数据不要直接并入当前索引，否则 E0–E7 将不再只比较现有 `corpus_v1`。原仓库 IR 基线依赖旧版 Elasticsearch，可参考思路，不直接移植。 |
| PubMedQA | [官方仓库](https://github.com/pubmedqa/pubmedqa)，[划分代码](https://github.com/pubmedqa/pubmedqa/blob/master/preprocess/split_dataset.py)，[官方 `evaluation.py`](https://github.com/pubmedqa/pubmedqa/blob/master/evaluation.py) | 仅用专家标注的 **PQA-L**；官方划分是 500 题交叉验证、500 题测试。PQA-U 无标准标签，不测准确率。 | `PMID → yes/no/maybe`；官方代码输出 Accuracy 与 Macro-F1。**maybe 是有效答案类别，不是拒答。** | 英文论文研究问题，原任务给定摘要；与中文指南/教材 RAG 的语种、来源和任务均不同，单列补充结果。 |

以上“官方数据与代码”是获取和核对格式的入口。下载时保存仓库提交号或数据修订号、压缩包 SHA-256、使用条款；数据文件放在被 `.gitignore` 排除的 `data/eval/raw/`。公开题目、答案、解析及 PubMedQA 摘要均不得写入 `corpus_v1` 检索索引。CMB 官方已公开测试答案，公开基准可能被生成模型预训练见过，因此结果只表示这套公开题的表现，不视作独立临床能力证明。

### PubMedQA 的两种输入协议

PubMedQA 原任务是**根据给定摘要**回答 yes/no/maybe。[官方任务说明](https://pubmedqa.github.io/)明确把摘要作为输入。为保持 E0–E7 的同题消融，本项目若纳入它，采用以下**摘要固定协议**：E0–E7 都收到同一题的官方问题和摘要正文；不得输入答案 `final_decision`、结论性 `long_answer` 或其他泄露答案的字段。E1–E7 再附加各实验组从 `corpus_v1` 检索的证据，不能将官方摘要偷偷只给某一组。这个协议测的是“给定摘要时，额外中文检索是否改变分类结果”，属于本项目的扩展评测，**不与 PubMedQA 官方榜单直接比较**。原版摘要输入的 E0 可另用官方评分器作为参考基线。不要把 PubMedQA 的 Accuracy 与中文考试题求一个总平均值。

## 3. 样本选择与冻结

1. **冒烟集**：每个数据集从开发划分取 20 题，覆盖各自题型；只用于验证读取、推理、解析、记录与评分流程，不报告为正式结果。
2. **开发集**：CMB-val、CMExam val、MedQA 简体中文 dev、PubMedQA 的官方 CV 部分。只在开发集上定提示词、检索 Top-K、输入截断、解析规则及 E6/E7 提示词。记录每次修改。
3. **固定测试集**：优先运行 CMB-test、CMExam test、MedQA 简体中文 test 和 PubMedQA 官方 500 题 test。若 API 成本不允许全量中文测试，**测试前**按固定随机种子和预先声明的题型/科室分层抽样，并保存题目 ID 列表及哈希；报告必须写成“固定子集结果”，不可标为全量官方成绩。一个可启动的规模是 CMB 560 题、CMExam 500 题、MedQA 简体中文 500 题、PubMedQA 500 题；抽样数不足的类别按实际可用数记录。正式测试集在配置冻结后运行一次。
4. **中文主结果**：CMB 单选、CMB 多选、CMExam、MedQA 简体中文分别出表。只有当数据集、题型和答案格式完全一致时才直接比较百分比；如展示汇总，只提供事先定义的等权宏平均作为导航信息，同时保留四个分表。
5. **重复和覆盖**：用规范化的“题干＋选项文本”哈希检查跨数据集及各数据集内部重复，保留原始 ID；交叉重复题在每个原数据集的结果中仍可列出，但汇总去重视图单独报告。测试集筛选只使用题型、官方主题标签等**与模型结果无关**的字段；不能按是否答对、是否召回或答案内容筛题。可另按语料主题划定“范围内/范围外”分析层，规则在推理前冻结。

## 4. E0–E7 实验矩阵

所有组使用相同测试题、相同模型 ID、temperature=0、相同选项顺序、相同答案解析规则、相同 `corpus_v1` 和相同上下文预算。推理期间关闭网页搜索、外部知识工具与模型动态路由；Reasoning 开关固定。题干和全部选项作为检索 query；答案及解析不能进入 query。检索返回的是**现有中文文档库**，因此英文 PubMedQA 的检索失败需要单独分析。

| 组别 | 本轮可执行定义 | 变量与当前实现状态 |
| --- | --- | --- |
| E0 | 只给题目、选项；PubMedQA 还给所有组共有的摘要。不查询 `corpus_v1`。 | 无 RAG 基线；需要批量模型调用器。 |
| E1 | BGE-M3 Dense Top-K 子片段 → 模型。 | 需要显式单路选择与证据组装。 |
| E2 | SQLite FTS5 BM25 Top-K 子片段 → 模型。 | 需要显式单路选择与证据组装。 |
| E3 | E1/E2 候选经 RRF 融合 → 模型。 | RRF 已实现；关闭重排及父节点补全。 |
| E4 | E3 + BGE reranker → 模型。 | 重排已实现；关闭父节点补全。 |
| E5 | E4 + 父节点上下文补全 → 模型。 | 当前主流水线已实现。 |
| E6 | 在 E5 的初答后，**同一大模型**再读题目、证据和初答，检查所选选项是否与证据及题意一致，允许改选；保存初答与终答。 | 这是“模型自检”消融，不称独立陈述级引用核验。本轮只测选项正确率，不测引用支持率；需要新增第二次模型调用。 |
| E7 | 在 E6 后允许**同一大模型**根据题目和证据输出“无法确定”；保存改选/拒答原因。 | 这是“模型自主拒答”，**不称已校准拒答**；没有验证集阈值，也不进行拒答质量或幻觉测试。选择题拒答计错，同时报告作答覆盖率及已作答正确率；需要新增拒答输出解析。 |

E0–E5 使用“必须选一个合法答案”的相同核心提示词，以隔离检索模块贡献；E6/E7 的额外调用就是其被研究的变量。E6/E7 会增加模型调用次数和成本，在结果表标明。若本轮只完成 E0–E5，报告标为“正确率阶段结果”，E6/E7 状态列为未运行，不能用 E5 的系统提示词自检能力假装补齐两组。

### 输入和输出约定

- 选项在所有组保持官方顺序。中文题由“题干＋A/B/C/...选项”组成；PubMedQA 使用原英文问题和摘要，不机器翻译。
- E0–E6 最终一行输出固定格式，如 `FINAL_ANSWER: B`、`FINAL_ANSWER: AC`、`FINAL_ANSWER: yes`。E7 额外允许 `FINAL_ANSWER: ABSTAIN`。解释与内部推理不交给评分器；模型若输出自然语言，先保存原文，再用事先固定的解析器抽取，不根据标准答案人工修正。
- 单选只接受一个合法选项；多选去重、按字母排序后比较**完整集合**；多输出、不合法选项、未解析到答案均计错并单列错误类型。PubMedQA 只接受 yes/no/maybe；`maybe` 不当作未答。
- 同一组同一题只取一次最终答案；API 网络失败可用同参数重试，重复请求和原始响应均入日志。模型返回空文本或被截断时计入推理失败率，不在准确率分母中静默剔除。

## 5. 指标与报告

**主指标**为每个数据集、每组的总体正确率 `正确题数 / 固定测试题总数`，所有拒答、格式错误和未解析输出计错。CMB 单选与多选分别报正确率；PubMedQA 除 Accuracy 外报官方使用的 Macro-F1。对 E7 另报 `作答覆盖率 = 有效非拒答数 / 全部题数`、`已作答正确率 = 正确且作答数 / 有效非拒答数`；主表仍使用总体正确率，防止通过大量拒答提高表面准确率。

每个中文数据集至少输出：E0–E7 正确题数/总题数、正确率、相对前一组的百分点变化、格式错误数、模型拒答数、API 失败数、P50/P95 耗时和 token 用量。采用**同题配对**比较：列出每次升级后“由错变对/由对变错”的题数，并对正确率差给出按题目重采样的 95% bootstrap 区间（固定随机种子和重采样次数）。按官方题型、科室或学科做分层结果；小样本层只报告题数和描述性结果。PubMedQA 单独报告类别混淆矩阵，尤其是 maybe 类别。

本轮不输出 Citation Precision、Claim Coverage、幻觉率、拒答 Precision/Recall/F1，也不把公开考试题正确率解释成检索证据确实支持答案。对于准确率下降的组，可以抽看错误题与检索片段做原因分析，但这属于定性排错，不构成本轮引用核验指标。

## 6. 落地代码与运行步骤

以下是原方案的通用目录建议。CMB 专项的加载、E0–E7 批量运行和正确率汇总现已实现，实际命令与产物见 [CMB-Exam 运行说明](CMB_EVAL_RUNBOOK.md)；其他数据集的适配器仍未实现。

```text
data/eval/raw/                         # 官方原始数据，不提交仓库
data/eval/manifest.json                # 来源修订、哈希、抽样种子、ID 清单
src/medical_rag/evaluation/loaders.py  # CMB/CMExam/MedQA/PubMedQA → 统一题目结构
src/medical_rag/evaluation/runner.py   # 批量 E0–E7、缓存、断点续跑
src/medical_rag/evaluation/scoring.py  # 固定答案解析、exact match、指标
configs/experiments/accuracy.yaml      # 模型、索引、各组、预算与随机种子
data/eval/results/<run_id>/             # 每题 JSONL、汇总 CSV、运行配置，不提交仓库
```

统一题目至少保存 `dataset`、`split`、`source_id`、`question_type`、`question`、`options`、`gold`、`provided_context`、`subject`。运行日志每题至少保存 `experiment`、`index_version`、`model_id`、`prompt_version`、检索到的 `chunk_id`、原始模型输出、解析选项、正误、拒答/失败状态、耗时与 token。PubMedQA 用 PMID 作 `source_id`；其他数据集优先用官方 ID，确无稳定 ID 时用“来源文件＋原始行号＋题目哈希”。结果必须可以从原题 ID 回溯，但不要把大段原题复制进 Git 跟踪文件。

按以下次序执行：

1. 固定官方数据修订、`corpus_v1` manifest/索引哈希、DeepSeek 模型 ID 和抽样 ID 清单；核查许可及题库没有进入索引。
2. 写四个加载器和统一题目校验；拒收缺选项、缺标准答案、题型不明的样本，并报告拒收数量。
3. 跑各 20 题冒烟集，逐题核对格式与官方答案；用人工构造的单选、多选、maybe、拒答、无效输出样本验证评分器。
4. 在开发集上只调检索和提示词；确保 E1/E2 单路、E3/E4/E5 组件开关生效且 `trace.degraded=false`。现有 Qdrant local mode 不应被多个评测进程同时打开，先用单进程顺序运行。
5. 冻结配置与代码提交，正式运行 E0–E5；若已实现第二次模型调用，再运行 E6–E7。每组每题增量写 JSONL，失败可恢复，已完成的响应不重复计费。
6. 用统一评分器生成分数据集表格；PubMedQA 完整 500 题可导出官方代码所需格式交叉核对。CMB 官方 `score.py` 使用固定输入路径并面向整份测试集，先核对其代码定义；运行固定子集时需改为传入子集答案与子集预测，避免把缺失题目计入分母。检查总行数、ID 集合、答案解析失败数和所有组的样本一致性，再发布结果。

## 7. 结果解释边界

- 中文考试题与当前语料覆盖面未必一致；E0 胜过 RAG 时，首先检查检索内容、上下文截断和题库/语料领域错配，不据此断言 RAG 普遍无效。
- CMB、CMExam、MedQA 可能含相似考试题；跨库重复与公开题的预训练暴露会影响绝对分数，重点看**同题、同模型**的组间差异。
- PubMedQA 摘要是原任务给定信息；摘要固定协议下增加中文 RAG 的效果只能说明本项目配置对该英文任务的影响。
- E6/E7 的模型自检和自主拒答只按选择题答案评分。后续若恢复原计划的引用与拒答评测，应另建证据标注和可答/不可答测试集，不从本轮正确率反推这些能力。

## 8. 主要来源

- [CMB 官方仓库与评测说明](https://github.com/FreedomIntelligence/CMB)、[CMB 官方评分脚本](https://github.com/FreedomIntelligence/CMB/blob/main/score.py)
- [CMExam 官方仓库](https://github.com/williamliujl/CMExam)、[官方数据目录](https://github.com/williamliujl/CMExam/tree/main/data)
- [MedQA 原作者数据与 IR 代码](https://github.com/jind11/MedQA)、[原论文](https://arxiv.org/abs/2009.13081)
- [PubMedQA 官方仓库](https://github.com/pubmedqa/pubmedqa)、[任务说明](https://pubmedqa.github.io/)、[官方划分脚本](https://github.com/pubmedqa/pubmedqa/blob/master/preprocess/split_dataset.py)、[官方评分脚本](https://github.com/pubmedqa/pubmedqa/blob/master/evaluation.py)
