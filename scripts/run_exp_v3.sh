#!/bin/bash
# Run v3 experiments for Compositional Skill Routing paper
set -e

export HF_ENDPOINT="https://hf-mirror.com"
export TOKENIZERS_PARALLELISM="false"

cd /mnt/workspace/skill-routing

echo "=== Experiment Suite v3: Starting ==="
echo "$(date)"

# Run all experiments (benchmark auto-built if missing)
python3 src/run_experiments.py 2>&1 | tee logs/run_exp_v3.log

echo "=== All experiments completed ==="
echo "$(date)"
