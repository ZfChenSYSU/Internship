# CMB-Exam 消融评测运行说明

本说明对应[公开基准正确率方案](PUBLIC_BENCHMARK_ACCURACY_PLAN.md)中的 CMB 部分。已完成的固定 [1000 题测试](CMB_EVAL_RESULTS_1000.md)与此前的 [100 题测试](CMB_EVAL_RESULTS_100.md)分别有结果报告。本轮只评分选择题正确率；E6 是同一 DeepSeek 模型复核，E7 是模型自主拒答，不代表独立引用核验或阈值校准。

## 数据与代码

- CMB 官方仓库位于 `data/eval/raw/CMB/`，修订号 `6c8ece46097dae736c6805dd3b831e1a38c08971`。只解压了 CMB-Exam 验证题和测试题；题目、答案、解析未加入 `corpus_v1`。
- 验证集为 `data/eval/raw/CMB/data/CMB/CMB-Exam/CMB-val/CMB-val-merge.json`，280 题。测试集为 `data/eval/raw/CMB/data/CMB/CMB-Exam/CMB-test/CMB-test-choice-question-merge.json`，11,200 题；答案独立存于 `data/eval/raw/CMB/data/CMB-test-choice-answer.json`，测试时必须传 `--answers`。
- 入口为 `python -m medical_rag.evaluation.run_cmb`；读取与评分在 `src/medical_rag/evaluation/cmb.py`。输出放在被 `.gitignore` 排除的 `data/eval/results/<run_id>/`。
- 官方文件有空白选项文本：验证集 31/280、测试集 1,202/11,200；这些题的标准答案均未指向空白选项。加载器保留原题与分母。

## 已完成的固定 100 题运行

配置：CMB-test，随机种子 `20260930`，`--limit 100`，模型 `deepseek-flash`，提示词版本 `cmb_accuracy_v2`，E0–E7。正式测试前在验证题上排查了输出截断，改为仅要求单行答案。五次增量运行，每次最多新增 160 次逻辑模型调用，合计 800 次。输出目录固定为 `data/eval/results/cmb_test_100_v2`。

```bash
PYTHONPYCACHEPREFIX=/private/tmp/medical_rag_pycache .venv/bin/python \
  -m medical_rag.evaluation.run_cmb \
  --questions data/eval/raw/CMB/data/CMB/CMB-Exam/CMB-test/CMB-test-choice-question-merge.json \
  --answers data/eval/raw/CMB/data/CMB-test-choice-answer.json \
  --limit 100 --seed 20260930 \
  --experiments E0,E1,E2,E3,E4,E5,E6,E7 \
  --max-api-calls 160 \
  --output data/eval/results/cmb_test_100_v2
```

相同命令会读取已完成记录并续跑；此目录已完成，再执行不会新增模型调用。`--max-api-calls` 限制**单次进程新增的逻辑模型调用数**，不含 API 层对临时错误的重试。不要让两个进程同时打开同一个 Qdrant local mode 索引或写同一个输出目录。更改题目数、提示词、模型、数据或代码配置时使用新输出目录，不得覆盖这个固定样本结果。完整 CMB-test 的 E0–E7 需要 11,200 × 8 = 89,600 次逻辑调用；扩大样本前按预算决定规模。

## 输出文件与核查

- `manifest.json`：数据及代码 SHA-256、抽样 ID、模型、提示词版本和索引路径。
- `predictions.jsonl`：每题每组的原始输出、解析答案、正误、证据 `chunk_id`、耗时和 token 用量；不记录 API Key。
- `summary.json` / `summary.csv`：单选、多选和总体正确率、作答覆盖率、无效输出与失败数。拒答和无效输出保留在总分母。
- `comparisons.json` / `comparisons.csv`：同题配对的错转对、对转错及 2,000 次 bootstrap 差值区间。

本次核查为 100 个不同 ID × 8 组 = 800 条不同记录，`failed=invalid=abstained=0`，`finish_reason=stop` 共 800 条。100 题是未分层的固定随机子集，**不是** 11,200 题全量官方成绩。

## 已完成的固定 1000 题运行与错题抽样

同一配置、同一随机种子扩大到 `--limit 1000`，输出为 `data/eval/results/cmb_test_1000_v2`。因为抽样 ID 包含上述 100 题，已复用 792 条旧响应；复用记录和配置比对见输出目录的 `reuse_log.json`。全量结果为 1000 个不同 ID × 8 组 = 8000 条不同记录，18 条无效输出、0 条 API 失败、0 次拒答。详情见[1000 题结果报告](CMB_EVAL_RESULTS_1000.md)和[42 道 E0→E5 退化题复核](CMB_EVAL_REGRESSION_AUDIT_42.md)。

```bash
PYTHONPYCACHEPREFIX=/private/tmp/medical_rag_pycache .venv/bin/python \
  -m medical_rag.evaluation.run_cmb \
  --questions data/eval/raw/CMB/data/CMB/CMB-Exam/CMB-test/CMB-test-choice-question-merge.json \
  --answers data/eval/raw/CMB/data/CMB-test-choice-answer.json \
  --limit 1000 --seed 20260930 \
  --experiments E0,E1,E2,E3,E4,E5,E6,E7 \
  --output data/eval/results/cmb_test_1000_v2
```

重现 E5 错题 10% 抽样（不调用模型）：

```bash
PYTHONPATH=src PYTHONPYCACHEPREFIX=/private/tmp/medical_rag_pycache .venv/bin/python \
  scripts/analyze_cmb_errors.py \
  --results data/eval/results/cmb_test_1000_v2 \
  --questions data/eval/raw/CMB/data/CMB/CMB-Exam/CMB-test/CMB-test-choice-question-merge.json \
  --answers data/eval/raw/CMB/data/CMB-test-choice-answer.json \
  --bm25-index data/indexes/corpus_v1/bm25.sqlite3 \
  --experiment E5 --fraction 0.1 --seed 20261001
```

脚本生成 `error_sample.json` 和 `error_sample_dossier.md`；前者记录抽样参数、题目、各组答案和证据，后者供人工阅读。抽样是固定随机的；报告中的原因判断仍须人工复核。
