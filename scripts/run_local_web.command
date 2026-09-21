#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}

cd "$PROJECT_DIR"
export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1

"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/corpus_pipeline.py" doctor
"$PROJECT_DIR/.venv/bin/python" -m medical_rag.webapp.server \
  --host 127.0.0.1 \
  --port 8000 \
  --device mps \
  --model deepseek-flash \
  --max-tokens 10000 \
  --api-key-file "$PROJECT_DIR/deepseek_apikey.txt" \
  --open-browser
