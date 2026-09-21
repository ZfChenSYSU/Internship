#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1
export HF_HOME="$PROJECT_DIR/models/huggingface"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] resume corpus_v1 dense index"
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/corpus_pipeline.py" dense \
  --chunks "$PROJECT_DIR/data/processed/corpus_v1/chunks.jsonl" \
  --output "$PROJECT_DIR/data/indexes/corpus_v1/qdrant" \
  --collection corpus_v1_children \
  --device mps \
  --batch-size 8 \
  --precision fp32 \
  2>&1 | tee -a "$LOG_DIR/dense_index.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] corpus_v1 dense index completed" | tee -a "$LOG_DIR/dense_index.log"
/usr/bin/osascript -e 'display notification "corpus_v1 稠密索引已完成" with title "Medical RAG"'
