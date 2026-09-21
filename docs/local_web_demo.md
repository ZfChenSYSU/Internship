# 本地 Medical RAG + DeepSeek Web 演示

更新日期：2026-09-21

## 功能

当前页面是一个只在 `127.0.0.1` 监听的单页演示，视觉和交互参考 DeepSeek 首页，但仅保留：

- 医疗问题输入和发送；
- DeepSeek Reasoning 开关；
- BM25 + Dense + RRF + BGE reranker + 父节点补全；
- `deepseek-flash` 自然语言流式回答；
- 思考过程折叠面板与引用证据折叠列表。

页面不会展示或要求模型返回 JSON。浏览器与后端之间使用 NDJSON 增量事件承载流式文本，
但这只是内部传输格式，用户看到的是格式化自然语言。

## 启动

确认以下本地资产存在：

- `.venv/` 及项目依赖；
- `data/indexes/corpus_v1/` 的 BM25 和 Qdrant 索引；
- `models/huggingface/` 的 BGE-M3 与 reranker；
- 项目根目录中的 `deepseek_apikey.txt`。

然后双击或在终端运行：

```bash
scripts/run_local_web.command
```

脚本会先检查 MPS，再启动 `http://127.0.0.1:8000` 并打开默认浏览器。停止服务时在终端按
`Ctrl+C`。如果只想使用 CPU：

```bash
.venv/bin/python -m medical_rag.webapp.server --device cpu --port 8000 --open-browser
```

## DeepSeek 配置

| 参数 | 当前值 |
|---|---|
| Model | `deepseek-flash` |
| User ID | `50817cc0-9a41-4bdf-b34c-6d0e963afcff` |
| Temperature | `0` |
| Max tokens | `10000` |
| Thinking | 页面开关映射到 `thinking.type=enabled/disabled` |
| Streaming | 开启 |

Reasoning 关闭时，后端不会向浏览器发送思考内容；开启时，`reasoning_content` 与最终回答
分别流入思考折叠面板和正文。API key 只从本地文件读取，既不写入 HTML/JavaScript，也不
包含在浏览器请求中。`deepseek_apikey.txt` 已加入 `.gitignore`。

## 已完成验收

- 健康接口返回 `model=deepseek-flash`、`max_tokens=10000`；
- 页面 HTML、CSS 和 JavaScript 均可从本地服务读取；
- Reasoning 关闭：4 条证据、0 字思考内容、1,334 字回答，端到端约 10.1 秒；
- Reasoning 开启：4 条证据、4,023 字思考内容、1,295 字回答，端到端约 20.6 秒；
- 两种模式均使用 MPS 完成检索，DeepSeek 回答为自然语言并带 `[S1]` 形式引用；
- Python 单测 10 项通过，JavaScript 语法检查通过。

上述时间只是一轮本机冒烟值，不代表正式性能结论。Qdrant 仍是 local mode，当前服务通过
进程内锁串行执行检索；迁移到多进程 API 服务前应改用 Qdrant Server。
