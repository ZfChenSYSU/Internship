# Trusted Medical RAG · 可信医疗 RAG

一个面向中文医疗资料的本地 RAG（Retrieval-Augmented Generation）演示系统。项目将
SQLite FTS5-BM25、BGE-M3、RRF、BGE reranker 和父子节点上下文补全组合起来，再由
DeepSeek 根据检索证据生成带引用的自然语言回答。

> [!WARNING]
> 本项目仅用于课程研究与工程验证，不提供诊断、治疗或用药建议，不能替代医生。请勿上传、
> 索引或发送任何未经授权的患者隐私数据。

## 当前能做什么

- 对中文指南、专家共识和教材执行来源感知的父子分片；
- BM25 与 BGE-M3 并行召回，使用 RRF 融合结果；
- 使用 `BAAI/bge-reranker-v2-m3` 重排候选段落；
- 合并同一父节点的相邻子片段，在上下文预算内补全限定条件；
- 通过 `deepseek-flash` 流式生成带 `[S1]` 引用的中文回答；
- 在本地 DeepSeek 风格页面中切换 Reasoning 模式并展开原始证据；
- 审计 BM25/Qdrant 的 ID、payload、权威等级和向量维度一致性。

尚未完成的部分包括自动陈述级引用核验、经验证集校准的拒答策略、上传文档、多轮对话、
Qdrant Server 部署和完整 E0–E7 评测。详情见[开发状态与内部记录](docs/DEVELOPMENT_STATUS.md)。

## 系统流程

```text
离线
授权医疗资料
  → 清洗与层级解析
  → 文档 / 父节点 / 子片段
  → SQLite FTS5-BM25 + BGE-M3/Qdrant

在线
用户问题
  → BM25 Top-30 + Dense Top-30
  → RRF(k=60) Top-40
  → BGE reranker Top-12
  → 父节点聚类、相邻补全、上下文预算
  → DeepSeek Flash（Reasoning 可选）
  → 自然语言回答 + [S1] 引用 + 可展开证据
```

## 运行环境

推荐配置：

- macOS 13+、Apple Silicon、16 GB 以上统一内存，24 GB 更适合完整索引；
- Python 3.11 或 3.12；项目当前也在 Python 3.9.6 上通过测试；
- 约 8–12 GB 可用磁盘空间，用于模型、Qdrant、SQLite 和处理结果；
- 可访问 Hugging Face 与 DeepSeek API 的网络；
- 一个可用的 DeepSeek API key。

CPU 可以运行，但嵌入、重排和首次响应会明显更慢。当前命令行只正式验证了 Apple MPS 与
CPU；NVIDIA CUDA 尚未完成项目级验收。

## 快速开始

### 1. 获取代码

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

### 2. 创建 Python 环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[dense,dev]'
```

安装内容包括 PyTorch、Sentence Transformers、Qdrant Client、NumPy 和 pytest。Web 演示后端
使用 Python 标准库，不需要 Node.js、FastAPI 或 Streamlit。

### 3. 下载开源模型

本项目使用以下 Hugging Face 模型：

| 用途         | 模型                        | Hugging Face                                              |
| ------------ | --------------------------- | --------------------------------------------------------- |
| 稠密检索     | `BAAI/bge-m3`             | [模型主页](https://huggingface.co/BAAI/bge-m3)             |
| 交叉编码重排 | `BAAI/bge-reranker-v2-m3` | [模型主页](https://huggingface.co/BAAI/bge-reranker-v2-m3) |

模型默认从项目内的 `models/huggingface/` 读取。下面的命令排除了当前 PyTorch/MPS 流程不需要
的 ONNX 和演示图片文件：

```bash
.venv/bin/hf download BAAI/bge-m3 \
  --cache-dir models/huggingface \
  --exclude 'onnx/*' 'imgs/*' '*.jpg' '*.webp'

.venv/bin/hf download BAAI/bge-reranker-v2-m3 \
  --cache-dir models/huggingface \
  --exclude 'assets/*'
```

如果没有 `.venv/bin/hf`，先运行：

```bash
python -m pip install --upgrade huggingface_hub
```

模型目录约占数 GB，已被 `.gitignore` 排除，不要提交模型权重。

### 4. 准备 DeepSeek API key

在项目根目录创建 `deepseek_apikey.txt`，文件中只放一行 API key：

```text
sk-your-deepseek-api-key
```

然后限制本机读取权限：

```bash
chmod 600 deepseek_apikey.txt
```

该文件已被 `.gitignore` 排除。后端只在本地读取 key，不会把 key 发送到浏览器。当前 Web
配置使用：

| 参数              | 值                                             |
| ----------------- | ---------------------------------------------- |
| Model             | `deepseek-flash`                             |
| Temperature       | `0`                                          |
| Max output tokens | `10000`                                      |
| Thinking          | 页面开关控制`thinking.type=enabled/disabled` |
| Streaming         | 开启                                           |

DeepSeek 接口参数可参考[官方 Chat Completion 文档](https://api-docs.deepseek.com/api/create-chat-completion)。

### 5. 获取语料和预构建索引

原始医疗语料、处理结果和索引体积较大，因此不直接提交到 Git。项目维护者通过百度网盘提供
`corpus_v1` 整理包，压缩包内包含 `data/` 和 `Medical Corpus/` 两个文件夹：

通过网盘分享的文件：Archive.zip
链接: https://pan.baidu.com/s/1dzUgVmlOBVpcw0NMUyT_rA?pwd=d7xk 提取码: d7xk

下载后解压到项目根目录，至少应得到：

```text
Medical Corpus/   # 仅在需要重建时使用

data/
├── manifests/
│   ├── corpus_scope.json
│   └── corpus_v1.jsonl
├── processed/corpus_v1/
│   ├── documents.jsonl
│   ├── parents.jsonl
│   ├── chunks.jsonl
│   └── quality_report.json
└── indexes/corpus_v1/
    ├── bm25.sqlite3
    └── qdrant/
```

如果只想运行 Web 演示，可以不保留 `Medical Corpus/`，但必须保留 `data/indexes/`。如果需要
复核原文偏移或从零重建，则必须准备有合法使用权的原始语料。

> [!IMPORTANT]
> 发布百度网盘前，请确认其中不包含无权再分发的教材、指南、个人信息、API key、模型权重或
> 其他受限内容，并同时公布文件哈希、数据版本和许可说明。

### 6. 验证模型与索引

检查当前进程是否能使用 Apple MPS：

```bash
.venv/bin/python scripts/corpus_pipeline.py doctor
```

检查 BM25 和 Qdrant 是否完全一致：

```bash
.venv/bin/python scripts/audit_indexes.py
```

`corpus_v1` 的参考结果为：

```text
expected_eligible_chunks = 46516
qdrant_points = 46516
missing = extra = bad_payload = bad_point_ids = 0
vector_dimension = 1024
passed = true
```

不同语料版本的数量可以不同，但 `missing`、`extra`、`bad_payload` 和 `bad_point_ids` 应为 0。

### 7. 启动本地 Web 演示

macOS + MPS：

```bash
scripts/run_local_web.command
```

脚本会运行 MPS 诊断、加载检索模型、启动服务并打开：

```text
http://127.0.0.1:8000
```

手动启动或使用 CPU：

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 \
.venv/bin/python -m medical_rag.webapp.server \
  --host 127.0.0.1 \
  --port 8000 \
  --device auto \
  --model deepseek-flash \
  --max-tokens 10000 \
  --api-key-file deepseek_apikey.txt \
  --open-browser
```

按 `Ctrl+C` 停止服务。服务默认只监听 `127.0.0.1`，不要在没有鉴权、TLS 和访问控制的情况下
将它绑定到公网地址。

## 从零构建数据和索引

如果不使用百度网盘中的预构建资产，请先按照以下目录放置有授权的 UTF-8/TXT 语料：

```text
Medical Corpus/
├── Clinical Guidance/
├── Expert Consensus/
└── Textbook/
```

首版策略只纳入上述 A/B 级来源；`Web Article`、`Wiki` 和 `EMR` 默认排除。

### 生成 manifest、父节点和子片段

```bash
.venv/bin/python scripts/corpus_pipeline.py prepare \
  --corpus-root 'Medical Corpus' \
  --data-root data
```

### 构建 SQLite FTS5-BM25

```bash
.venv/bin/python scripts/corpus_pipeline.py bm25
```

### 构建或断点续建 BGE-M3/Qdrant

MPS：

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 \
.venv/bin/python scripts/corpus_pipeline.py dense \
  --device mps \
  --batch-size 8 \
  --precision fp32
```

CPU：

```bash
.venv/bin/python scripts/corpus_pipeline.py dense \
  --device cpu \
  --batch-size 4 \
  --precision fp32
```

稠密索引使用确定性 point ID，重复执行会跳过已经成功写入的子片段。

### 检索冒烟测试

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 \
.venv/bin/python scripts/corpus_pipeline.py retrieve \
  '颅脑创伤后脑积水如何诊断？' \
  --device auto
```

也可以在不加载稠密模型和 reranker 的情况下验证降级链路：

```bash
.venv/bin/python scripts/corpus_pipeline.py retrieve \
  '颅脑创伤后脑积水如何诊断？' \
  --no-dense \
  --no-reranker
```

## 测试

```bash
.venv/bin/python -m pytest -q
```

当前仓库有 10 项单元测试，覆盖分片偏移、BM25 过滤、RRF、模型缓存解析、reranker 封装、
父节点补全和完整混合检索编排。

## 目录结构

```text
.
├── configs/base.yaml                 # 分片、索引、融合、重排和层级参数
├── docs/                             # 数据卡、交接说明和开发记录
├── scripts/
│   ├── corpus_pipeline.py            # prepare/bm25/dense/retrieve/doctor
│   ├── audit_indexes.py              # 双索引一致性审计
│   └── run_local_web.command         # macOS 本地 Web 启动入口
├── src/medical_rag/
│   ├── ingestion/                    # manifest 与范围策略
│   ├── chunking/                     # 来源感知层级分片
│   ├── indexing/                     # BM25 与 Qdrant 索引
│   ├── retrieval/                    # Dense、RRF、父节点补全和编排
│   ├── reranking/                    # BGE reranker
│   └── webapp/                       # 本地 DeepSeek Web 后端
├── tests/
└── web/                              # HTML、CSS、JavaScript
```

## 数据、安全与隐私

- `Medical Corpus/`、`data/`、`models/`、`logs/` 和 `deepseek_apikey.txt` 默认不进入 Git；
- 只索引来源、版本、授权和权威等级可追溯的资料；
- 禁止把公开评测题的答案或解析混入检索语料；
- 电子病历默认排除，任何患者数据都必须先完成授权、脱敏和合规审查；
- Web 提问及检索证据会发送到 DeepSeek API，请先确认资料允许发送给第三方模型服务；
- 本地 Web 服务目前没有用户认证，不应直接暴露到局域网或公网。

## 已知限制

- 当前拒答主要依赖生成提示，还没有完成经验证集校准的多信号拒答策略；
- 尚未自动验证每个生成 claim 是否被其引用证据支持；
- Qdrant 使用 local mode，46,516 点会出现规模提示，且不适合多进程同时打开；
- 当前父节点与 Top-K 参数是工程起始值，尚未完成正式开发集调优；
- 部分语料缺少出版日期、版本、机构和 URL，需要进一步人工核验；
- 当前 Web 演示是单轮、单机、单用户原型，没有上传、会话隔离和持久聊天记录。

## 文档

- [开发状态与内部记录](docs/DEVELOPMENT_STATUS.md)
- [corpus_v1 数据卡](docs/data_card.md)
- [索引交接说明](docs/index_handoff.md)
- [RRF、BGE 重排与父节点补全](docs/retrieval_pipeline.md)
- [本地 DeepSeek Web 演示](docs/local_web_demo.md)
- [完整技术路线与实施计划](Medical_RAG_A+B_Technical_Roadmap_and_Implementation_Plan.md)

## 贡献

欢迎提交 Issue 或 Pull Request。与医学语料、评测答案和患者数据有关的贡献，请先确认版权、
授权和隐私边界；不要把大模型权重、原始受限语料、构建索引或 API key 提交到仓库。

## License

仓库目前尚未添加开源许可证。正式公开前，请由维护者选择并加入 `LICENSE`（例如 MIT、
Apache-2.0 或其他符合课程、数据与依赖约束的许可证）。在许可证确定前，默认版权法仍然适用。
