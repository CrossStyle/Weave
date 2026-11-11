"""
Unified observation interface for Sim2Sim and Sim2Real deployment.
This module provides an abstraction layer between the policy and the observation sources.
"""

from abc import ABC, abstractmethod
from typing import Dict

import torch


class ObservationInterface(ABC):
    """Abstract interface for observation collection."""

    @abstractmethod
    def get_observation(self) -> Dict[str, torch.Tensor]:
        """
        Get raw observations organized by group.
        
        Returns:
            Dictionary with keys: 
                - "ref_motion_body": future reference for robot bodies
                - "ref_motion_object": future reference for object
                - "object_state_actor": object pose + object_id (deployable)
                - "robot_proprio": robot proprioception
        """
        pass

    def get_actor_obs(self) -> torch.Tensor:
        """
        Concatenate observations into a single tensor for policy input.
        Order must match training: [ref_motion_body, ref_motion_object, object_state_actor, robot_proprio]
        
        Returns:
            Flattened observation tensor (1, obs_dim)
        """
        obs = self.get_observation()
        return torch.cat([
            obs["ref_motion_body"],
            obs["ref_motion_object"],
            obs["object_state_actor"],
            obs["robot_proprio"],
        ], dim=-1)

    @abstractmethod
    def reset(self) -> Dict[str, torch.Tensor]:
        """Reset the observation interface and return initial observation."""
        pass

    @abstractmethod
    def get_device(self) -> torch.device:
        """Get the torch device for tensors."""
        pass
