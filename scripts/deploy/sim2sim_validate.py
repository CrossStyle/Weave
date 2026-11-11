#!/usr/bin/env python3
"""
Sim2Sim validation script.

This script runs the trained policy in Isaac Sim using the same observation pipeline
as real-world deployment (optionally with vision-based pose estimation).

Usage:
    # Direct mode (ground-truth observations)
    python scripts/deploy/sim2sim_validate.py --checkpoint model_5000.pt
    
    # Vision mode (simulated pose estimation with noise)
    python scripts/deploy/sim2sim_validate.py --checkpoint model_5000.pt --use_vision
    
    # Specific run and checkpoint
    python scripts/deploy/sim2sim_validate.py \
        --load_run 2026-11-10_12-34-56 \
        --checkpoint model_10000.pt \
        --num_episodes 10
"""

import argparse
import os
from pathlib import Path

import torch

# IsaacLab imports
from isaaclab.app import AppLauncher

# Parse arguments
parser = argparse.ArgumentParser(description="Sim2Sim validation for trained policy")
parser.add_argument("--task", type=str, default="G1-Inspire-HOI-v0", help="Task name")
parser.add_argument("--load_run", type=str, default=None, help="Run directory name (e.g., 2026-11-10_12-34-56)")
parser.add_argument("--checkpoint", type=str, default="model_latest.pt", help="Checkpoint filename")
parser.add_argument("--num_episodes", type=int, default=1, help="Number of episodes to run")
parser.add_argument("--max_steps", type=int, default=1000, help="Max steps per episode")
parser.add_argument("--use_vision", action="store_true", help="Use vision-based pose estimation (add noise)")
parser.add_argument("--pose_noise_pos", type=float, default=0.03, help="Position noise std (meters)")
parser.add_argument("--pose_noise_rot", type=float, default=0.15, help="Rotation noise std (radians)")
parser.add_argument("--env_id", type=int, default=0, help="Environment ID to use (for multi-env)")
parser.add_argument("--headless", action="store_true", help="Run headless (no GUI)")
parser.add_argument("--video", action="store_true", help="Record video")
parser.add_argument("--video_length", type=int, default=500, help="Video length in frames")

# Parse args for AppLauncher
args_cli, hydra_args = parser.parse_known_args()

# Launch Isaac Sim
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# Now we can import other modules
import gymnasium as gym

from g1_hoi_learning.deploy.isaac_sim_backend import IsaacSimObservation
from g1_hoi_learning.deploy.policy_runner import PolicyRunner


def find_checkpoint_path(task_name: str, run_name: str = None, checkpoint: str = "model_latest.pt") -> Path:
    """
    Find the checkpoint path from the logs directory.
    
    Args:
        task_name: Task name (e.g., G1-Inspire-HOI-v0)
        run_name: Run directory name (e.g., 2026-11-10_12-34-56). If None, uses latest.
        checkpoint: Checkpoint filename
    
    Returns:
        Path to checkpoint file
    """
    logs_dir = Path("logs/rsl_rl/g1_inspire_hoi")
    
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")
    
    # Find run directory
    if run_name is None:
        # Use the latest run
        run_dirs = sorted([d for d in logs_dir.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime)
        if not run_dirs:
            raise FileNotFoundError(f"No runs found in {logs_dir}")
        run_dir = run_dirs[-1]
        print(f"Using latest run: {run_dir.name}")
    else:
        run_dir = logs_dir / run_name
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
    
    # Find checkpoint
    checkpoint_path = run_dir / checkpoint
    if not checkpoint_path.exists():
        # Try looking for exported policy
        exported_path = run_dir / "exported" / "policy.pt"
        if exported_path.exists():
            checkpoint_path = exported_path
            print(f"Using exported policy: {checkpoint_path}")
        else:
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    return checkpoint_path


def main():
    """Run Sim2Sim validation."""
    
    # Find checkpoint
    checkpoint_path = find_checkpoint_path(
        args_cli.task,
        args_cli.load_run,
        args_cli.checkpoint,
    )
    
    print("\n" + "="*80)
    print("SIM2SIM VALIDATION")
    print("="*80)
    print(f"Task: {args_cli.task}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Use vision: {args_cli.use_vision}")
    if args_cli.use_vision:
        print(f"Pose noise: pos={args_cli.pose_noise_pos}m, rot={args_cli.pose_noise_rot}rad")
    print(f"Episodes: {args_cli.num_episodes}")
    print(f"Max steps: {args_cli.max_steps}")
    print("="*80 + "\n")
    
    # Create environment
    print("Creating environment...")
    env = gym.make(args_cli.task, num_envs=1, headless=args_cli.headless)
    
    # Create observation interface
    print("Setting up observation interface...")
    obs_interface = IsaacSimObservation(
        env=env.unwrapped,
        env_id=args_cli.env_id,
        use_vision=args_cli.use_vision,
        pose_noise_std=(args_cli.pose_noise_pos, args_cli.pose_noise_rot),
    )
    
    # Create policy runner
    print("Loading policy...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    runner = PolicyRunner(
        policy_path=str(checkpoint_path),
        obs_interface=obs_interface,
        device=device,
    )
    
    # Run episodes
    all_stats = []
    for episode in range(args_cli.num_episodes):
        print(f"\n{'='*80}")
        print(f"EPISODE {episode + 1}/{args_cli.num_episodes}")
        print(f"{'='*80}")
        
        stats = runner.run_episode(
            max_steps=args_cli.max_steps,
            render=not args_cli.headless,
            verbose=True,
        )
        all_stats.append(stats)
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    avg_fps = sum(s["avg_fps"] for s in all_stats) / len(all_stats)
    avg_step_time = sum(s["avg_step_time"] for s in all_stats) / len(all_stats)
    print(f"Episodes completed: {len(all_stats)}")
    print(f"Average FPS: {avg_fps:.1f}")
    print(f"Average step time: {avg_step_time*1000:.2f}ms")
    print("="*80 + "\n")
    
    # Close environment
    env.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        simulation_app.close()
