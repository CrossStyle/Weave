# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Event functions for the HOI learning environment."""

from __future__ import annotations

import torch
from typing import TYPE_CHECKING

from isaaclab.assets import RigidObject
from isaaclab.managers import SceneEntityCfg

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def reset_conditional_scene_objects(
    env: ManagerBasedRLEnv,
    env_ids: torch.Tensor,
    object_names: list[str],
    h_frame_wall1_cfg: SceneEntityCfg | None = None,
    h_frame_wall2_cfg: SceneEntityCfg | None = None,
    ladder_support1_cfg: SceneEntityCfg | None = None,
    ladder_support2_cfg: SceneEntityCfg | None = None,
    ladder_support3_cfg: SceneEntityCfg | None = None,
    ladder_support4_cfg: SceneEntityCfg | None = None,
    h_frame_wall1_init_z: float = 0.0,
    h_frame_wall2_init_z: float = 0.0,
    ladder_support1_init_z: float = 0.0,
    ladder_support2_init_z: float = 0.0,
    ladder_support3_init_z: float = 0.0,
    ladder_support4_init_z: float = 0.0,
):
    """根据每个环境分配的主物体类型，动态设置额外物体的位置。
    
    Args:
        env: 环境实例
        env_ids: 需要重置的环境ID
        object_names: 物体名称列表（按环境分配顺序）
        h_frame_wall1_cfg: h_frame墙1的配置
        h_frame_wall2_cfg: h_frame墙2的配置
        ladder_support1_cfg: 梯子支撑1的配置
        ladder_support2_cfg: 梯子支撑2的配置
        ladder_support3_cfg: 梯子支撑3的配置
        ladder_support4_cfg: 梯子支撑4的配置
        h_frame_wall1_init_z: h_frame墙1的初始z坐标
        h_frame_wall2_init_z: h_frame墙2的初始z坐标
        ladder_support1_init_z: 梯子支撑1的初始z坐标
        ladder_support2_init_z: 梯子支撑2的初始z坐标
        ladder_support3_init_z: 梯子支撑3的初始z坐标
        ladder_support4_init_z: 梯子支撑4的初始z坐标
    """
    # print(f"[DEBUG] reset_conditional_scene_objects called with env_ids={env_ids}, object_names={object_names}")
    
    if not object_names:
        print(f"[DEBUG] object_names is empty, skipping")
        return
    
    num_objects = len(object_names)
    
    # 获取命令管理器中的 env_object（每个环境对应的物体索引）
    if hasattr(env.command_manager, 'get_term'):
        motion_command = env.command_manager.get_term("motion")
        env_object_indices = motion_command.env_object  # (num_envs,) 每个环境对应的物体索引
        # print(f"[DEBUG] env_object_indices from motion_command: {env_object_indices}")
    else:
        # 如果无法获取，使用轮询方式计算
        env_object_indices = torch.arange(env.num_envs, device=env.device) % num_objects
        # print(f"[DEBUG] env_object_indices computed: {env_object_indices}")
    
    # 处理 h_frame 墙
    if h_frame_wall1_cfg is not None and h_frame_wall2_cfg is not None:
        # print(f"[DEBUG] Checking h_frame walls: {h_frame_wall1_cfg.name}, {h_frame_wall2_cfg.name}")
        # 检查场景中是否存在这些物体
        if h_frame_wall1_cfg.name in env.scene.keys() and h_frame_wall2_cfg.name in env.scene.keys():
            # print(f"[DEBUG] h_frame walls found in scene")
            h_frame_wall1: RigidObject = env.scene[h_frame_wall1_cfg.name]
            h_frame_wall2: RigidObject = env.scene[h_frame_wall2_cfg.name]
            
            # 获取 h_frame 在 object_names 中的索引
            try:
                h_frame_idx = object_names.index("h_frame")
                # print(f"[DEBUG] h_frame_idx={h_frame_idx}")
            except ValueError:
                h_frame_idx = -1  # h_frame 不存在
                # print(f"[DEBUG] h_frame not found in object_names")
            
            if h_frame_idx >= 0:
                for env_id in env_ids:
                    env_id_int = env_id.item()
                    obj_idx = env_object_indices[env_id_int].item()
                    
                    # print(f"[DEBUG] env {env_id_int}: obj_idx={obj_idx}, object={object_names[obj_idx]}")
                    
                    if obj_idx == h_frame_idx:
                        # 这是 h_frame 环境，设置墙的正常位置（使用初始配置的z坐标）
                        # print(f"[DEBUG] Setting h_frame walls to normal position for env {env_id_int}")
                        # 获取当前墙的位置（包含环境偏移）
                        current_wall1_pose = h_frame_wall1.data.root_link_pose_w[env_id_int].clone()
                        current_wall2_pose = h_frame_wall2.data.root_link_pose_w[env_id_int].clone()
                        # 设置为配置的初始 z 坐标
                        current_wall1_pose[2] = h_frame_wall1_init_z
                        current_wall2_pose[2] = h_frame_wall2_init_z
                        h_frame_wall1.write_root_pose_to_sim(current_wall1_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
                        h_frame_wall2.write_root_pose_to_sim(current_wall2_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
                    else:
                        # 不是 h_frame 环境，将墙放在地下
                        # print(f"[DEBUG] Moving h_frame walls underground for env {env_id_int}")
                        current_wall1_pose = h_frame_wall1.data.root_link_pose_w[env_id_int].clone()
                        current_wall2_pose = h_frame_wall2.data.root_link_pose_w[env_id_int].clone()
                        # 只修改 z 坐标到地下
                        current_wall1_pose[2] = -1000.0  # z = -1000
                        current_wall2_pose[2] = -1000.0  # z = -1000
                        h_frame_wall1.write_root_pose_to_sim(current_wall1_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
                        h_frame_wall2.write_root_pose_to_sim(current_wall2_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
        # else:
        #     print(f"[DEBUG] h_frame walls NOT found in scene")
    
    # 处理 ladder 支撑
    if all(cfg is not None for cfg in [ladder_support1_cfg, ladder_support2_cfg, ladder_support3_cfg, ladder_support4_cfg]):
        # print(f"[DEBUG] Checking ladder supports")
        # 检查场景中是否存在这些物体
        if all(cfg.name in env.scene.keys() for cfg in [ladder_support1_cfg, ladder_support2_cfg, ladder_support3_cfg, ladder_support4_cfg]):
            # print(f"[DEBUG] ladder supports found in scene")
            ladder_supports = [
                env.scene[ladder_support1_cfg.name],
                env.scene[ladder_support2_cfg.name],
                env.scene[ladder_support3_cfg.name],
                env.scene[ladder_support4_cfg.name],
            ]
            
            # 获取 ladder 在 object_names 中的索引
            try:
                ladder_idx = object_names.index("ladder")
                # print(f"[DEBUG] ladder_idx={ladder_idx}")
            except ValueError:
                ladder_idx = -1  # ladder 不存在
                # print(f"[DEBUG] ladder not found in object_names")
            
            if ladder_idx >= 0:
                # 每个支撑的初始 z 坐标
                support_init_z_list = [
                    ladder_support1_init_z,
                    ladder_support2_init_z,
                    ladder_support3_init_z,
                    ladder_support4_init_z,
                ]
                
                for env_id in env_ids:
                    env_id_int = env_id.item()
                    obj_idx = env_object_indices[env_id_int].item()
                    
                    if obj_idx == ladder_idx:
                        # 这是 ladder 环境，设置支撑的正常位置（使用各自初始配置的z坐标）
                        # print(f"[DEBUG] Setting ladder supports to normal position for env {env_id_int}")
                        for i, support in enumerate(ladder_supports):
                            current_pose = support.data.root_link_pose_w[env_id_int].clone()
                            current_pose[2] = support_init_z_list[i]
                            support.write_root_pose_to_sim(current_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
                    else:
                        # 不是 ladder 环境，将支撑放在地下
                        # print(f"[DEBUG] Moving ladder supports underground for env {env_id_int}")
                        for support in ladder_supports:
                            current_pose = support.data.root_link_pose_w[env_id_int].clone()
                            current_pose[2] = -1000.0  # z = -1000
                            support.write_root_pose_to_sim(current_pose.unsqueeze(0), env_ids=torch.tensor([env_id_int], device=env.device))
        # else:
        #     print(f"[DEBUG] ladder supports NOT found in scene")
    
    # print(f"[DEBUG] reset_conditional_scene_objects completed")
