#!/usr/bin/env python3
"""
MuJoCo Sim2Sim validation script.

This script runs the trained policy in MuJoCo as an independent validation environment,
testing sim2sim transfer from Isaac Sim to MuJoCo.

Usage:
    # Basic validation
    python scripts/deploy/mujoco_validate.py \
        --model_path path/to/robot.xml \
        --motion_file data/train/woodchair_46clip.npz \
        --checkpoint model_5000.pt
    
    # With vision mode (add pose noise)
    python scripts/deploy/mujoco_validate.py \
        --model_path path/to/robot.xml \
        --motion_file data/train/woodchair_46clip.npz \
        --checkpoint model_5000.pt \
        --use_vision \
        --render
    
    # Multiple episodes
    python scripts/deploy/mujoco_validate.py \
        --model_path path/to/robot.xml \
        --motion_file data/train/woodchair_46clip.npz \
        --checkpoint model_5000.pt \
        --num_episodes 10 \
        --clip_id 0
"""

import argparse
import time
from pathlib import Path

import torch
import numpy as np

from g1_hoi_learning.deploy.mujoco_backend import MuJoCoObservation
from g1_hoi_learning.deploy.policy_runner import PolicyRunner


def find_checkpoint_path(run_name: str = None, checkpoint: str = "model_latest.pt") -> Path:
    """Find checkpoint path from logs directory."""
    logs_dir = Path("logs/rsl_rl/g1_inspire_hoi")
    
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")
    
    if run_name is None:
        # Use latest run
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
        # Try exported policy
        exported_path = run_dir / "exported" / "policy.pt"
        if exported_path.exists():
            checkpoint_path = exported_path
            print(f"Using exported policy: {checkpoint_path}")
        else:
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    return checkpoint_path


class MuJoCoPolicyRunner(PolicyRunner):
    """Extended PolicyRunner for MuJoCo with action application."""
    
    def __init__(self, policy_path: str, obs_interface: MuJoCoObservation, device: str = "cpu"):
        super().__init__(policy_path, obs_interface, device)
        self.mujoco_interface = obs_interface
    
    def run_episode(self, max_steps: int = 1000, render: bool = True, verbose: bool = True) -> dict:
        """Run one episode in MuJoCo."""
        obs = self.reset()
        
        step_count = 0
        episode_time = 0.0
        
        if render:
            self.mujoco_interface.render()
        
        if verbose:
            print("\n" + "="*60)
            print("Starting MuJoCo episode...")
            print("="*60)
        
        for step in range(max_steps):
            step_start = time.time()
            
            # Get action from policy
            action = self.step(obs)
            
            # Apply action to MuJoCo
            self.mujoco_interface.step(action)
            
            # Get next observation
            obs = self.obs_interface.get_actor_obs()
            
            # Render
            if render:
                self.mujoco_interface.render()
            
            step_time = time.time() - step_start
            episode_time += step_time
            step_count += 1
            
            if verbose and step % 50 == 0:
                print(f"Step {step:4d} | Time: {step_time*1000:.1f}ms | FPS: {1.0/step_time:.1f}")
        
        stats = {
            "total_steps": step_count,
            "total_time": episode_time,
            "avg_step_time": episode_time / step_count if step_count > 0 else 0,
            "avg_fps": step_count / episode_time if episode_time > 0 else 0,
        }
        
        if verbose:
            print("\n" + "="*60)
            print("Episode finished!")
            print(f"Total steps: {stats['total_steps']}")
            print(f"Total time: {stats['total_time']:.2f}s")
            print(f"Avg step time: {stats['avg_step_time']*1000:.2f}ms")
            print(f"Avg FPS: {stats['avg_fps']:.1f}")
            print("="*60 + "\n")
        
        return stats


def main():
    parser = argparse.ArgumentParser(description="MuJoCo Sim2Sim validation")
    parser.add_argument("--model_path", type=str, required=True, help="Path to MuJoCo XML model")
    parser.add_argument("--motion_file", type=str, required=True, help="Path to motion data (.npz)")
    parser.add_argument("--clip_id", type=int, default=0, help="Which motion clip to use")
    parser.add_argument("--load_run", type=str, default=None, help="Run directory name")
    parser.add_argument("--checkpoint", type=str, default="model_latest.pt", help="Checkpoint filename")
    parser.add_argument("--num_episodes", type=int, default=1, help="Number of episodes")
    parser.add_argument("--max_steps", type=int, default=1000, help="Max steps per episode")
    parser.add_argument("--object_id", type=int, default=0, help="Object ID (for multi-object)")
    parser.add_argument("--use_vision", action="store_true", help="Add pose noise")
    parser.add_argument("--pose_noise_pos", type=float, default=0.03, help="Position noise std (m)")
    parser.add_argument("--pose_noise_rot", type=float, default=0.15, help="Rotation noise std (rad)")
    parser.add_argument("--render", action="store_true", help="Render in MuJoCo viewer")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu/cuda)")
    
    args = parser.parse_args()
    
    # Find checkpoint
    checkpoint_path = find_checkpoint_path(args.load_run, args.checkpoint)
    
    print("\n" + "="*80)
    print("MUJOCO SIM2SIM VALIDATION")
    print("="*80)
    print(f"MuJoCo model: {args.model_path}")
    print(f"Motion file: {args.motion_file}")
    print(f"Clip ID: {args.clip_id}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Use vision: {args.use_vision}")
    if args.use_vision:
        print(f"Pose noise: pos={args.pose_noise_pos}m, rot={args.pose_noise_rot}rad")
    print(f"Episodes: {args.num_episodes}")
    print(f"Max steps: {args.max_steps}")
    print(f"Device: {args.device}")
    print("="*80 + "\n")
    
    # Check files exist
    if not Path(args.model_path).exists():
        raise FileNotFoundError(f"MuJoCo model not found: {args.model_path}")
    if not Path(args.motion_file).exists():
        raise FileNotFoundError(f"Motion file not found: {args.motion_file}")
    
    # Create MuJoCo observation interface
    print("Setting up MuJoCo environment...")
    obs_interface = MuJoCoObservation(
        model_path=args.model_path,
        object_id=args.object_id,
        use_vision=args.use_vision,
        pose_noise_std=(args.pose_noise_pos, args.pose_noise_rot),
        device=args.device,
    )
    
    # Load motion data
    print(f"Loading motion data (clip {args.clip_id})...")
    obs_interface.load_motion_data(args.motion_file, clip_id=args.clip_id)
    
    # Create policy runner
    print("Loading policy...")
    runner = MuJoCoPolicyRunner(
        policy_path=str(checkpoint_path),
        obs_interface=obs_interface,
        device=args.device,
    )
    
    # Run episodes
    all_stats = []
    for episode in range(args.num_episodes):
        print(f"\n{'='*80}")
        print(f"EPISODE {episode + 1}/{args.num_episodes}")
        print(f"{'='*80}")
        
        stats = runner.run_episode(
            max_steps=args.max_steps,
            render=args.render,
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
    
    # Close
    obs_interface.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        raise
