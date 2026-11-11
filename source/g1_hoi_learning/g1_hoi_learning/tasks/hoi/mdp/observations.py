from __future__ import annotations

import torch

from isaaclab.assets import RigidObject
from isaaclab.envs import ManagerBasedEnv
from isaaclab.managers import ManagerTermBase
from isaaclab.utils.math import (
    matrix_from_quat,
    quat_apply,
    quat_apply_inverse,
    quat_conjugate,
    quat_mul,
    subtract_frame_transforms,
)

from g1_hoi_learning.objects import ASSET_DIR

from .commands import MotionCommand
from .geometry import SampledSurfaceQuery, load_bps_sdf_assets, sample_sdf_trilinear


def motion_joint_pos(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Reference joint positions from motion data."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    return command.joint_pos


def motion_joint_vel(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Reference joint velocities from motion data."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    return command.joint_vel


def motion_future_joint_pos(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future reference joint positions for configured offsets."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    return command.future_joint_pos.reshape(env.num_envs, -1)


def motion_anchor_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Goal anchor position in the robot's anchor (body) frame."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    pos, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w,
        command.robot_anchor_quat_w,
        command.anchor_pos_w,
        command.anchor_quat_w,
    )
    return pos.view(env.num_envs, -1)


def motion_anchor_ori_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Goal anchor orientation in the robot's anchor frame (first 2 columns of rotation matrix)."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    _, ori = subtract_frame_transforms(
        command.robot_anchor_pos_w,
        command.robot_anchor_quat_w,
        command.anchor_pos_w,
        command.anchor_quat_w,
    )
    mat = matrix_from_quat(ori)
    return mat[..., :2].reshape(env.num_envs, -1)


def motion_body_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Goal tracked-body positions in the robot's anchor frame."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    body_indices = command.body_indices
    pos_b, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, len(body_indices), -1),
        command.body_pos_w[:, body_indices],
        command.body_quat_w[:, body_indices],
    )
    return pos_b.view(env.num_envs, -1)


def motion_body_ori_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Goal tracked-body orientations in the robot's anchor frame."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    body_indices = command.body_indices
    _, ori_b = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, len(body_indices), -1),
        command.body_pos_w[:, body_indices],
        command.body_quat_w[:, body_indices],
    )
    mat = matrix_from_quat(ori_b)
    return mat[..., :2].reshape(env.num_envs, -1)


def motion_future_anchor_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future anchor positions in current robot anchor frame. (num_envs, num_offsets * 3)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    # future_anchor_pos_w: (num_envs, num_offsets, 3)
    n_offsets = len(command.cfg.future_offsets)
    pos, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, n_offsets, -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, n_offsets, -1),
        command.future_anchor_pos_w,
        command.future_anchor_quat_w,
    )
    return pos.reshape(env.num_envs, -1)


def motion_future_anchor_ori_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future anchor orientations in current robot anchor frame. (num_envs, num_offsets * 6)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    n_offsets = len(command.cfg.future_offsets)
    _, ori = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, n_offsets, -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, n_offsets, -1),
        command.future_anchor_pos_w,
        command.future_anchor_quat_w,
    )
    mat = matrix_from_quat(ori)
    return mat[..., :2].reshape(env.num_envs, -1)


def robot_body_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Robot tracked-body positions in the robot's anchor frame."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    body_indices = command.body_indices
    pos_b, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_body_pos_w[:, body_indices],
        command.robot_body_quat_w[:, body_indices],
    )
    return pos_b.view(env.num_envs, -1)


def robot_body_ori_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Robot tracked-body orientations in the robot's anchor frame."""
    command: MotionCommand = env.command_manager.get_term(command_name)
    body_indices = command.body_indices
    _, ori_b = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, len(body_indices), -1),
        command.robot_body_pos_w[:, body_indices],
        command.robot_body_quat_w[:, body_indices],
    )
    mat = matrix_from_quat(ori_b)
    return mat[..., :2].reshape(env.num_envs, -1)

# -- Object observations --


def object_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Current object position relative to robot anchor in anchor frame. (3 dims)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    pos_b, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w,
        command.robot_anchor_quat_w,
        command.obj_pos_w,
        command.obj_quat_w,
    )
    return pos_b.view(env.num_envs, -1)


def object_rot_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Current object orientation in anchor frame (6D tangent-normal). (6 dims)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    _, ori_b = subtract_frame_transforms(
        command.robot_anchor_pos_w,
        command.robot_anchor_quat_w,
        command.obj_pos_w,
        command.obj_quat_w,
    )
    mat = matrix_from_quat(ori_b)
    return mat[..., :2].reshape(env.num_envs, -1)


def motion_future_obj_pos_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future reference object positions in current robot anchor frame. (num_envs, num_offsets * 3)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    n_offsets = len(command.cfg.future_offsets)
    pos_b, _ = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, n_offsets, -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, n_offsets, -1),
        command.future_obj_pos_w,
        command.future_obj_quat_w,
    )
    return pos_b.reshape(env.num_envs, -1)


class ObjectBpsSdf(ManagerTermBase):
    """Signed distances from a fixed 128-point BPS basis to the normalized object mesh."""

    def __init__(self, cfg, env: ManagerBasedEnv):
        super().__init__(cfg, env)
        self.command: MotionCommand = env.command_manager.get_term(cfg.params["command_name"])
        self.basis, self.sdf_grids, self.grid_bound = load_bps_sdf_assets(
            ASSET_DIR,
            self.command.motion.object_names,
            self.command.motion.device,
        )

    def __call__(self, env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
        del env, command_name
        command = self.command
        num_basis = self.basis.shape[0]
        object_from_anchor = quat_mul(quat_conjugate(command.obj_quat_w), command.robot_anchor_quat_w)
        query_points_o = quat_apply(
            object_from_anchor[:, None, :].expand(-1, num_basis, -1),
            self.basis[None, :, :].expand(command.num_envs, -1, -1),
        )
        return sample_sdf_trilinear(
            self.sdf_grids,
            command.env_object,
            query_points_o,
            self.grid_bound,
        )


class object_nearest_point_b(ManagerTermBase):
    """Per-body vector from a robot body to its nearest point on the object surface, expressed in
    the robot anchor frame. (num_envs, len(body_names) * 3)
    """

    def __init__(self, cfg, env: ManagerBasedEnv):
        super().__init__(cfg, env)
        self.command: MotionCommand = env.command_manager.get_term(cfg.params["command_name"])
        self.body_ids, self.body_names = env.scene["robot"].find_bodies(cfg.params["body_names"])
        self.surface_query = SampledSurfaceQuery(self.command.motion.surface, self.command.env_object)
        self.nearest_o = torch.empty(
            (env.num_envs, len(self.body_ids), 3),
            device=env.device,
            dtype=self.command.motion.surface.dtype,
        )

    def __call__(self, env: ManagerBasedEnv, command_name: str, body_names: list[str]) -> torch.Tensor:
        del command_name, body_names
        command = self.command
        body_pos_w = command.robot_body_pos_w[:, self.body_ids]                # (num_envs, B, 3)
        num_bodies = body_pos_w.shape[1]

        body_pos_o = quat_apply_inverse(
            command.obj_quat_w[:, None, :].expand(-1, num_bodies, -1),
            body_pos_w - command.obj_pos_w[:, None, :],
        )
        nearest_o = self.surface_query(body_pos_o, self.nearest_o)
        diff_o = nearest_o - body_pos_o

        diff_w = quat_apply(command.obj_quat_w[:, None, :].expand(-1, num_bodies, -1), diff_o)
        diff_b = quat_apply_inverse(
            command.robot_anchor_quat_w[:, None, :].expand(-1, num_bodies, -1),
            diff_w,
        )
        return diff_b.reshape(env.num_envs, -1)


def motion_future_obj_ori_b(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future reference object orientations in current robot anchor frame. (num_envs, num_offsets * 6)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    n_offsets = len(command.cfg.future_offsets)
    _, ori_b = subtract_frame_transforms(
        command.robot_anchor_pos_w[:, None, :].expand(-1, n_offsets, -1),
        command.robot_anchor_quat_w[:, None, :].expand(-1, n_offsets, -1),
        command.future_obj_pos_w,
        command.future_obj_quat_w,
    )
    mat = matrix_from_quat(ori_b)
    return mat[..., :2].reshape(env.num_envs, -1)


# -- Contact observations --


def motion_contact_label(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Reference per-body contact labels for current timestep. (num_envs, num_bodies)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    return command.ref_contact_label


def motion_future_contact_label(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Future reference contact labels. (num_envs, num_offsets * num_bodies)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    return command.future_contact_label.reshape(env.num_envs, -1)


def contact(env: ManagerBasedEnv, sensor_name: str, threshold: float = 1.0) -> torch.Tensor:
    """Per-robot-body binary contact flag with object from force_matrix_w. (num_envs, 54)"""
    sensor = env.scene[sensor_name]
    # force_matrix_w shape: (num_envs, num_bodies, num_filters, 3)
    # Check if there are any bodies being monitored
    if sensor.data.force_matrix_w is None or sensor.data.force_matrix_w.shape[1] == 0:
        # Return zeros if no contact data available
        num_filters = len(sensor.cfg.filter_prim_paths_expr)
        return torch.zeros(env.num_envs, num_filters, device=sensor.device)
    forces = sensor.data.force_matrix_w[:, 0, :, :]  # (num_envs, num_filters, 3)
    return (forces.norm(dim=-1) > threshold).float()


# -- Object ID embedding --
from g1_hoi_learning.tasks.hoi.object_registry import get_num_objects
import torch.nn.functional as F


# def object_id_onehot(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
#     """One-hot encoding of the object ID for each environment. (num_envs, NUM_OBJECTS_GLOBAL)
#
#     Uses global object registry to ensure consistent IDs across training and evaluation.
#     """
#     command: MotionCommand = env.command_manager.get_term(command_name)
#     num_objects_global = get_num_objects()
#
#     # Get global object IDs for each environment
#     # env_object contains local indices, need to map to global IDs
#     global_ids = torch.tensor(
#         [command.motion.object_ids[local_id] for local_id in command.env_object.cpu().numpy()],
#         device=env.device,
#         dtype=torch.long
#     )
#
#     # Create one-hot encoding with global object space
#     onehot = torch.zeros(env.num_envs, num_objects_global, device=env.device, dtype=torch.float32)
#     onehot.scatter_(1, global_ids.unsqueeze(1), 1.0)
#     return onehot
def object_id_onehot(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """One-hot encoding of the object ID for each environment. (num_envs, NUM_OBJECTS_GLOBAL)"""
    command: MotionCommand = env.command_manager.get_term(command_name)
    num_objects_global = get_num_objects()

    # 1. 确保映射表在 GPU 上（建议直接在 MotionLoader 初始化时存为 GPU tensor，这里做惰性缓存兜底）
    if not isinstance(command.motion.object_ids, torch.Tensor):
        if not hasattr(command.motion, "_object_ids_tensor"):
            command.motion._object_ids_tensor = torch.as_tensor(
                command.motion.object_ids, device=env.device, dtype=torch.long
            )
        obj_ids_map = command.motion._object_ids_tensor
    else:
        obj_ids_map = command.motion.object_ids.to(device=env.device, dtype=torch.long)

    # 2. 纯 GPU 向量化索引 (num_envs,)
    global_ids = obj_ids_map[command.env_object.long()]

    # 3. 直接生成 float32 的 one-hot (num_envs, num_objects_global)
    return F.one_hot(global_ids, num_classes=num_objects_global).to(dtype=torch.float32)


def object_id_index(env: ManagerBasedEnv, command_name: str) -> torch.Tensor:
    """Object ID as integer index for each environment. (num_envs, 1)
    
    Uses global object registry to ensure consistent IDs across training and evaluation.
    """
    command: MotionCommand = env.command_manager.get_term(command_name)
    
    # Get global object IDs for each environment
    global_ids = torch.tensor(
        [command.motion.object_ids[local_id] for local_id in command.env_object.cpu().numpy()],
        device=env.device,
        dtype=torch.float32
    )
    
    return global_ids.unsqueeze(1)


def object_mass(env: ManagerBasedEnv, object_name: str = "object") -> torch.Tensor:
    """Object mass for each environment. (num_envs, 1)"""
    obj: RigidObject = env.scene[object_name]
    # Get mass from the rigid body (assumes single rigid body per object)
    # obj.root_physx_view.get_masses() returns (num_envs, num_bodies) for articulations
    # For RigidObject, it's (num_envs,)
    masses = obj.root_physx_view.get_masses()  # (num_envs,) or (num_envs, 1)
    if masses.ndim == 1:
        masses = masses.unsqueeze(1)
    return masses.to(device=env.device, dtype=torch.float32)
