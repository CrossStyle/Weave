"""
MuJoCo backend for Sim2Sim validation.
Uses MuJoCo physics engine as an alternative simulation environment.
"""

from typing import Dict, Optional

import torch
import numpy as np
import mujoco
import mujoco.viewer

from g1_hoi_learning.deploy import ObservationInterface


class MuJoCoObservation(ObservationInterface):
    """
    Observation interface for MuJoCo environment.
    
    This provides an independent validation environment using MuJoCo physics,
    different from Isaac Sim, to test sim2sim transfer.
    """

    def __init__(
        self,
        model_path: str,
        object_id: int = 0,
        use_vision: bool = False,
        pose_noise_std: tuple = (0.03, 0.15),
        device: str = "cpu",
    ):
        """
        Args:
            model_path: Path to MuJoCo XML model file
            object_id: Which object is being manipulated
            use_vision: If True, add noise to simulate vision-based pose estimation
            pose_noise_std: (pos_std, rot_std) for simulating pose estimation errors
            device: Torch device
        """
        self._device = torch.device(device)
        self.object_id = object_id
        self.use_vision = use_vision
        self.pose_noise_std = pose_noise_std
        
        # Load MuJoCo model
        self.model = mujoco.MjModel.from_xml_path(model_path)
        self.data = mujoco.MjData(self.model)
        
        # Find body/joint indices
        self._setup_indices()
        
        # Motion data for reference trajectories
        self.motion_data = None  # To be loaded separately
        self.motion_timestep = 0
        
        # Last action for observation
        self._last_action = torch.zeros(self.num_joints, device=self._device)
        
        # Viewer (optional)
        self.viewer = None

    def _setup_indices(self):
        """Find relevant body and joint indices in MuJoCo model."""
        # TODO: Customize based on your MuJoCo model structure
        
        # Example for G1 robot
        self.robot_base_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
        self.object_body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "object")
        
        # Get all actuated joints (exclude free joints)
        self.joint_ids = []
        self.joint_names = []
        for i in range(self.model.njnt):
            joint_type = self.model.jnt_type[i]
            if joint_type in [mujoco.mjtJoint.mjJNT_HINGE, mujoco.mjtJoint.mjJNT_SLIDE]:
                self.joint_ids.append(i)
                joint_name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, i)
                self.joint_names.append(joint_name)
        
        self.num_joints = len(self.joint_ids)
        print(f"Found {self.num_joints} actuated joints")

    def load_motion_data(self, motion_file: str, clip_id: int = 0):
        """
        Load reference motion data from numpy file.
        
        Args:
            motion_file: Path to .npz motion file
            clip_id: Which clip to use
        """
        data = np.load(motion_file, allow_pickle=True)
        
        # Extract motion data
        motion_lengths = data["motion_lengths"]
        start_idx = sum(motion_lengths[:clip_id]) if clip_id > 0 else 0
        end_idx = start_idx + motion_lengths[clip_id]
        
        self.motion_data = {
            "joint_pos": torch.tensor(data["joint_pos"][start_idx:end_idx], device=self._device, dtype=torch.float32),
            "joint_vel": torch.tensor(data["joint_vel"][start_idx:end_idx], device=self._device, dtype=torch.float32),
            "object_pos_w": torch.tensor(data["object_pos_w"][start_idx:end_idx], device=self._device, dtype=torch.float32),
            "object_quat_w": torch.tensor(data["object_quat_w"][start_idx:end_idx], device=self._device, dtype=torch.float32),
            "body_pos_w": torch.tensor(data["body_pos_w"][start_idx:end_idx], device=self._device, dtype=torch.float32),
            "body_quat_w": torch.tensor(data["body_quat_w"][start_idx:end_idx], device=self._device, dtype=torch.float32),
        }
        
        self.motion_length = motion_lengths[clip_id]
        self.motion_timestep = 0
        print(f"Loaded motion clip {clip_id}: {self.motion_length} frames")

    def get_observation(self) -> Dict[str, torch.Tensor]:
        """Get observations from MuJoCo simulation."""
        
        # 1. Robot proprioception
        robot_proprio = self._get_robot_proprio()
        
        # 2. Object state
        object_state = self._get_object_state()
        
        # 3. Reference motion
        ref_motion_body, ref_motion_object = self._get_reference_motion()
        
        return {
            "robot_proprio": robot_proprio,
            "object_state_actor": object_state,
            "ref_motion_body": ref_motion_body,
            "ref_motion_object": ref_motion_object,
        }

    def _get_robot_proprio(self) -> torch.Tensor:
        """
        Extract robot proprioceptive observations from MuJoCo.
        
        Returns:
            (1, P) tensor with [base_ang_vel, joint_pos, joint_vel, projected_gravity, last_action]
        """
        # Base angular velocity (from base body's gyro)
        base_ang_vel = torch.tensor(
            self.data.sensordata[0:3],  # Assuming first 3 sensors are gyro
            device=self._device,
            dtype=torch.float32
        )
        
        # Joint positions (relative to default)
        joint_pos = torch.tensor(
            self.data.qpos[7:7+self.num_joints],  # Skip free joint (7 DOF)
            device=self._device,
            dtype=torch.float32
        )
        
        # Joint velocities
        joint_vel = torch.tensor(
            self.data.qvel[6:6+self.num_joints],  # Skip free joint (6 DOF)
            device=self._device,
            dtype=torch.float32
        )
        
        # Projected gravity (from base orientation)
        base_quat = self.data.xquat[self.robot_base_id]  # (w, x, y, z) in MuJoCo
        gravity_world = np.array([0, 0, -1])
        # Rotate to base frame
        projected_gravity = self._rotate_vector_by_quat(gravity_world, base_quat)
        projected_gravity = torch.tensor(projected_gravity, device=self._device, dtype=torch.float32)
        
        # Concatenate all
        proprio = torch.cat([
            base_ang_vel,        # (3,)
            joint_pos,           # (num_joints,)
            joint_vel,           # (num_joints,)
            projected_gravity,   # (3,)
            self._last_action,   # (num_joints,)
        ]).unsqueeze(0)  # (1, P)
        
        return proprio

    def _get_object_state(self) -> torch.Tensor:
        """
        Get object state (pose + object_id).
        
        Returns:
            (1, 3+6+num_objects) tensor
        """
        # Object position in world frame
        obj_pos_w = self.data.xpos[self.object_body_id]
        obj_quat_w = self.data.xquat[self.object_body_id]  # (w, x, y, z)
        
        # Robot base (anchor) pose
        base_pos_w = self.data.xpos[self.robot_base_id]
        base_quat_w = self.data.xquat[self.robot_base_id]
        
        # Transform object pose to robot base frame
        obj_pos_b, obj_quat_b = self._transform_pose(
            obj_pos_w, obj_quat_w,
            base_pos_w, base_quat_w
        )
        
        # Convert quaternion to 6D rotation (first 2 columns of rotation matrix)
        rot_mat = self._quat_to_matrix(obj_quat_b)
        obj_rot_b = rot_mat[:, :2].flatten()  # (6,)
        
        # Object ID one-hot
        num_objects = 9  # Adjust based on training
        object_id_onehot = np.zeros(num_objects)
        object_id_onehot[self.object_id] = 1.0
        
        # Concatenate
        object_state = torch.cat([
            torch.tensor(obj_pos_b, device=self._device, dtype=torch.float32),
            torch.tensor(obj_rot_b, device=self._device, dtype=torch.float32),
            torch.tensor(object_id_onehot, device=self._device, dtype=torch.float32),
        ]).unsqueeze(0)  # (1, 3+6+num_objects)
        
        # Add noise if vision mode
        if self.use_vision:
            object_state = self._add_pose_noise(object_state)
        
        return object_state

    def _get_reference_motion(self) -> tuple:
        """
        Get reference motion trajectories.
        
        Returns:
            (ref_motion_body, ref_motion_object) tensors
        """
        if self.motion_data is None:
            raise RuntimeError("Motion data not loaded. Call load_motion_data() first.")
        
        # Get current and future timesteps
        future_offsets = [1, 2, 4, 8]  # Should match training config
        current_t = self.motion_timestep
        
        # Future joint positions
        future_joint_pos = []
        for offset in future_offsets:
            t = min(current_t + offset, self.motion_length - 1)
            future_joint_pos.append(self.motion_data["joint_pos"][t])
        future_joint_pos = torch.stack(future_joint_pos).flatten().unsqueeze(0)
        
        # Future object poses
        future_obj_pos = []
        future_obj_quat = []
        for offset in future_offsets:
            t = min(current_t + offset, self.motion_length - 1)
            future_obj_pos.append(self.motion_data["object_pos_w"][t])
            future_obj_quat.append(self.motion_data["object_quat_w"][t])
        
        # Transform to current robot base frame
        base_pos_w = self.data.xpos[self.robot_base_id]
        base_quat_w = self.data.xquat[self.robot_base_id]
        
        future_obj_pos_b = []
        future_obj_rot_b = []
        for pos, quat in zip(future_obj_pos, future_obj_quat):
            pos_b, quat_b = self._transform_pose(
                pos.cpu().numpy(), quat.cpu().numpy(),
                base_pos_w, base_quat_w
            )
            future_obj_pos_b.append(torch.tensor(pos_b, device=self._device))
            
            rot_mat = self._quat_to_matrix(quat_b)
            future_obj_rot_b.append(torch.tensor(rot_mat[:, :2].flatten(), device=self._device))
        
        future_obj_pos_b = torch.stack(future_obj_pos_b).flatten().unsqueeze(0)
        future_obj_rot_b = torch.stack(future_obj_rot_b).flatten().unsqueeze(0)
        
        # Combine ref_motion_body and ref_motion_object
        ref_motion_body = future_joint_pos  # TODO: Add future anchor poses if needed
        ref_motion_object = torch.cat([future_obj_pos_b, future_obj_rot_b], dim=-1)
        
        return ref_motion_body, ref_motion_object

    def _add_pose_noise(self, object_state: torch.Tensor) -> torch.Tensor:
        """Add noise to simulate vision-based pose estimation."""
        pos_std, rot_std = self.pose_noise_std
        
        object_pos = object_state[:, :3]
        object_rot = object_state[:, 3:9]
        object_id = object_state[:, 9:]
        
        pos_noise = torch.randn_like(object_pos) * pos_std
        rot_noise = torch.randn_like(object_rot) * rot_std
        
        return torch.cat([object_pos + pos_noise, object_rot + rot_noise, object_id], dim=-1)

    def step(self, action: torch.Tensor) -> None:
        """
        Apply action and step the MuJoCo simulation.
        
        Args:
            action: Joint position targets (1, num_joints)
        """
        # Store last action
        self._last_action = action.squeeze(0)
        
        # Set control (position targets)
        self.data.ctrl[:] = action.squeeze(0).cpu().numpy()
        
        # Step simulation
        mujoco.mj_step(self.model, self.data)
        
        # Advance motion timestep
        self.motion_timestep = min(self.motion_timestep + 1, self.motion_length - 1)
        
        # Render if viewer is active
        if self.viewer is not None:
            self.viewer.sync()

    def reset(self) -> Dict[str, torch.Tensor]:
        """Reset the MuJoCo simulation."""
        # Reset simulation state
        mujoco.mj_resetData(self.model, self.data)
        
        # Set initial pose from motion data
        if self.motion_data is not None:
            self.motion_timestep = 0
            initial_qpos = self.motion_data["joint_pos"][0].cpu().numpy()
            self.data.qpos[7:7+self.num_joints] = initial_qpos
            
            # Set object initial pose
            obj_pos = self.motion_data["object_pos_w"][0].cpu().numpy()
            obj_quat = self.motion_data["object_quat_w"][0].cpu().numpy()
            # TODO: Set object pose in MuJoCo (depends on model structure)
        
        # Forward kinematics
        mujoco.mj_forward(self.model, self.data)
        
        return self.get_observation()

    def render(self, mode: str = "human"):
        """Render the MuJoCo simulation."""
        if mode == "human":
            if self.viewer is None:
                self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
            self.viewer.sync()

    def close(self):
        """Close the viewer."""
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None

    def get_device(self) -> torch.device:
        """Get the torch device."""
        return self._device

    # ==================== Utility functions ====================

    @staticmethod
    def _rotate_vector_by_quat(vec, quat):
        """Rotate a vector by a quaternion (MuJoCo convention: w, x, y, z)."""
        w, x, y, z = quat
        vec_quat = np.array([0, vec[0], vec[1], vec[2]])
        
        # q * v * q^-1
        result = MuJoCoObservation._quat_multiply(
            MuJoCoObservation._quat_multiply(quat, vec_quat),
            MuJoCoObservation._quat_conjugate(quat)
        )
        return result[1:]

    @staticmethod
    def _quat_multiply(q1, q2):
        """Multiply two quaternions (w, x, y, z)."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2,
        ])

    @staticmethod
    def _quat_conjugate(q):
        """Conjugate of quaternion (w, x, y, z)."""
        return np.array([q[0], -q[1], -q[2], -q[3]])

    @staticmethod
    def _transform_pose(pos, quat, ref_pos, ref_quat):
        """Transform pose to reference frame."""
        # Position
        pos_local = pos - ref_pos
        pos_b = MuJoCoObservation._rotate_vector_by_quat(
            pos_local,
            MuJoCoObservation._quat_conjugate(ref_quat)
        )
        
        # Orientation
        quat_b = MuJoCoObservation._quat_multiply(
            MuJoCoObservation._quat_conjugate(ref_quat),
            quat
        )
        
        return pos_b, quat_b

    @staticmethod
    def _quat_to_matrix(quat):
        """Convert quaternion (w, x, y, z) to 3x3 rotation matrix."""
        w, x, y, z = quat
        return np.array([
            [1-2*y*y-2*z*z, 2*x*y-2*w*z, 2*x*z+2*w*y],
            [2*x*y+2*w*z, 1-2*x*x-2*z*z, 2*y*z-2*w*x],
            [2*x*z-2*w*y, 2*y*z+2*w*x, 1-2*x*x-2*y*y],
        ])
