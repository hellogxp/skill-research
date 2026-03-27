#!/bin/bash
# Download BGE model and run first experiment
set -e

echo "=== Step 1: Download BGE embedding model ==="
python3 -c "
from modelscope import snapshot_download
path = snapshot_download('BAAI/bge-large-en-v1.5', cache_dir='/mnt/workspace/models/embeddings')
print(f'BGE downloaded to: {path}')
"

echo "=== Step 2: Update pipeline to use local model path ==="
# The pipeline will use the local path
export BGE_MODEL_PATH="/mnt/workspace/models/embeddings/BAAI/bge-large-en-v1___5"
export HF_ENDPOINT="https://hf-mirror.com"

echo "=== Step 3: Run experiment ==="
cd /mnt/workspace/skill-routing
python3 src/pipeline/pipeline.py

echo "=== DONE ==="
