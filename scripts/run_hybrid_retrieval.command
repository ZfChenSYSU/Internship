#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
QUERY=${*:-颅脑创伤后脑积水如何诊断？}

cd "$PROJECT_DIR"
export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1

"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/corpus_pipeline.py" doctor
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/corpus_pipeline.py" retrieve \
  "$QUERY" \
  --device mps \
  --model-cache "$PROJECT_DIR/models/huggingface"
