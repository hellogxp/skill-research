#!/bin/bash
# Run all experiments for Compositional Skill Routing paper (v2)
set -e

export HF_ENDPOINT="https://hf-mirror.com"
export TOKENIZERS_PARALLELISM="false"

cd /mnt/workspace/skill-routing

echo "=== Experiment Suite v2: Starting ==="
echo "$(date)"

# Run all experiments
python3 src/run_experiments.py 2>&1 | tee logs/run_exp_v2.log

echo "=== All experiments completed ==="
echo "$(date)"
