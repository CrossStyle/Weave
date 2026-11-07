@echo off
REM Set CUDA debugging flags for better error reporting
set CUDA_LAUNCH_BLOCKING=1
set TORCH_USE_CUDA_DSA=1

REM Run the training script
python scripts/rsl_rl/train_with_curriculum.py --task=G1-Inspire-HOI-v0 --config-dir ./configs/track --config-name train --curriculum agent.policy.compile=false
