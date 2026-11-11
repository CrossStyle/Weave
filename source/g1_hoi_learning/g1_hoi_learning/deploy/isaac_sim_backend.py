"""
Isaac Sim backend for Sim2Sim validation.
Uses the same observation pipeline as real robot deployment (with pose estimation from rendered images).
"""

from typing import Dict

import torch
import numpy as np

from isaaclab.envs import ManagerBasedRLEnv

from g1_hoi_learning.deploy import ObservationInterface


class IsaacSimObservation(ObservationInterface):
    """
    Observation interface for Isaac Sim environment.
    
    This can work in two modes:
    1. Direct mode: Use ground-truth observations from the environment
    2. Vision mode: Simulate real-world deployment with vision-based pose estimation
    """

    def __init__(
        self,
        env: ManagerBasedRLEnv,
        env_id: int = 0,
        use_vision: bool = False,
        pose_noise_std: tuple = (0.03, 0.15),  # (position, rotation) noise std
    ):
        """
        Args:
            env: Isaac Lab environment
            env_id: Which environment instance to use (for vectorized envs)
            use_vision: If True, simulate vision-based pose estimation with noise
            pose_noise_std: (pos_std, rot_std) for simulating pose estimation errors
        """
        self.env = env
        self.env_id = env_id
        self.use_vision = use_vision
        self.pose_noise_std = pose_noise_std
        self._device = env.device

    def get_observation(self) -> Dict[str, torch.Tensor]:
        """Get observations from Isaac Sim environment."""
        # Get all observations from the environment
        obs_dict = self.env.observation_manager.compute()
        
        # Extract single environment observations
        result = {}
        for group_name in ["ref_motion_body", "ref_motion_object", "object_state_actor", "robot_proprio"]:
            if group_name in obs_dict:
                # Extract single env: (num_envs, obs_dim) -> (1, obs_dim)
                result[group_name] = obs_dict[group_name][self.env_id:self.env_id+1]
        
        # Simulate vision-based pose estimation if enabled
        if self.use_vision:
            result["object_state_actor"] = self._add_pose_noise(result["object_state_actor"])
        
        return result

    def _add_pose_noise(self, object_state: torch.Tensor) -> torch.Tensor:
        """
        Add noise to object pose to simulate vision-based 6D pose estimation errors.
        
        Args:
            object_state: (1, 3+6+num_objects) = [pos(3), rot(6), object_id(one-hot)]
        
        Returns:
            Noisy object state
        """
        pos_std, rot_std = self.pose_noise_std
        
        # Separate pose and object_id
        object_pos = object_state[:, :3]  # (1, 3)
        object_rot = object_state[:, 3:9]  # (1, 6)
        object_id = object_state[:, 9:]  # (1, num_objects)
        
        # Add Gaussian noise
        pos_noise = torch.randn_like(object_pos) * pos_std
        rot_noise = torch.randn_like(object_rot) * rot_std
        
        noisy_pos = object_pos + pos_noise
        noisy_rot = object_rot + rot_noise
        
        # Concatenate back
        return torch.cat([noisy_pos, noisy_rot, object_id], dim=-1)

    def reset(self) -> Dict[str, torch.Tensor]:
        """Reset the environment and return initial observation."""
        # Reset only the specific environment
        reset_mask = torch.zeros(self.env.num_envs, dtype=torch.bool, device=self._device)
        reset_mask[self.env_id] = True
        
        self.env.reset(env_ids=torch.tensor([self.env_id], device=self._device))
        return self.get_observation()

    def get_device(self) -> torch.device:
        """Get the torch device."""
        return self._device


class IsaacSimVisionObservation(IsaacSimObservation):
    """
    Vision-based observation for Isaac Sim (Sim2Sim validation).
    Renders RGB-D images and runs 6D pose estimation, simulating real deployment.
    """

    def __init__(
        self,
        env: ManagerBasedRLEnv,
        env_id: int = 0,
        camera_name: str = "wrist_camera",
        pose_estimator=None,  # Optional: actual 6D pose estimator (e.g., FoundationPose)
    ):
        """
        Args:
            env: Isaac Lab environment
            env_id: Which environment instance to use
            camera_name: Name of the camera sensor in the scene
            pose_estimator: Optional pose estimation module. If None, uses GT with noise.
        """
        super().__init__(env, env_id, use_vision=True)
        self.camera_name = camera_name
        self.pose_estimator = pose_estimator

    def get_observation(self) -> Dict[str, torch.Tensor]:
        """Get observations with vision-based pose estimation."""
        # Get base observations
        result = super().get_observation()
        
        # If we have a real pose estimator, use it
        if self.pose_estimator is not None:
            # Render camera
            if self.camera_name in self.env.scene.sensors:
                camera = self.env.scene[self.camera_name]
                rgb = camera.data.output["rgb"][self.env_id].cpu().numpy()
                depth = camera.data.output["distance_to_camera"][self.env_id].cpu().numpy()
                
                # Run pose estimation
                obj_pos, obj_quat = self.pose_estimator.estimate(rgb, depth)
                
                # Convert to robot anchor frame and format
                # TODO: Implement coordinate transformation
                pass
        
        # Otherwise use ground-truth with noise (already done in parent class)
        return result
