"""
Policy runner for Sim2Sim and Sim2Real deployment.
Loads TorchScript policy and runs inference with the unified observation interface.
"""

import time
from pathlib import Path
from typing import Optional

import torch

from g1_hoi_learning.deploy import ObservationInterface


class PolicyRunner:
    """
    Unified policy runner for both Sim2Sim and Sim2Real deployment.
    """

    def __init__(
        self,
        policy_path: str,
        obs_interface: ObservationInterface,
        device: str = "cuda",
    ):
        """
        Args:
            policy_path: Path to exported TorchScript policy (.pt file)
            obs_interface: Observation interface (IsaacSim or RealRobot)
            device: Device to run policy on
        """
        self.device = torch.device(device)
        self.obs_interface = obs_interface
        
        # Load TorchScript policy
        policy_path = Path(policy_path)
        if not policy_path.exists():
            raise FileNotFoundError(f"Policy not found: {policy_path}")
        
        print(f"Loading policy from: {policy_path}")
        self.policy = torch.jit.load(str(policy_path), map_location=self.device)
        self.policy.eval()
        
        print(f"Policy loaded successfully on {self.device}")

    def reset(self) -> torch.Tensor:
        """Reset and get initial observation."""
        obs_dict = self.obs_interface.reset()
        return self.obs_interface.get_actor_obs()

    def step(self, obs: torch.Tensor) -> torch.Tensor:
        """
        Run policy inference for one step.
        
        Args:
            obs: Observation tensor (1, obs_dim)
        
        Returns:
            Action tensor (1, action_dim)
        """
        with torch.no_grad():
            action = self.policy(obs)
        return action

    def run_episode(
        self,
        max_steps: int = 1000,
        render: bool = True,
        verbose: bool = True,
    ) -> dict:
        """
        Run one episode with the policy.
        
        Args:
            max_steps: Maximum number of steps
            render: Whether to render (for Isaac Sim)
            verbose: Print step info
        
        Returns:
            Episode statistics
        """
        obs = self.reset()
        
        step_count = 0
        episode_time = 0.0
        
        if verbose:
            print("\n" + "="*60)
            print("Starting episode...")
            print("="*60)
        
        for step in range(max_steps):
            step_start = time.time()
            
            # Get action from policy
            action = self.step(obs)
            
            # Apply action and get next observation
            # Note: This needs to be implemented differently for Sim vs Real
            obs = self.obs_interface.get_actor_obs()
            
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
