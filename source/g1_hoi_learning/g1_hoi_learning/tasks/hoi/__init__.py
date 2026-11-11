# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

import gymnasium as gym

import isaaclab.sim as sim_utils
from isaaclab.assets import RigidObjectCfg, AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnv

from g1_hoi_learning.objects.object_cfg import OBJECT_CFG_BY_NAME
from g1_hoi_learning.objects import ASSET_DIR

from . import agents


def _make_env(cfg, **kwargs):
    """Resolve scene.object from motion_files' object_names.

    Builds a MultiAssetSpawnerCfg(random_choice=False) so envs are assigned objects in round-robin
    order: env i -> object (i % O), matching MotionCommand.env_object. Forces replicate_physics=False
    (required by IsaacLab when spawning heterogeneous assets across envs).
    """
    from .mdp.commands import MotionLoader

    motion_files = cfg.commands.motion.motion_files

    # Unique objects across all clips, in the SAME order MotionLoader uses, so the object spawned for
    # env i (assets_cfg[i % O]) matches that env's fixed object (env_object = arange % O).
    object_names = MotionLoader.object_names_of(motion_files)
    assets_spawn_cfg: list[sim_utils.SpawnerCfg] = []
    for name in object_names:
        if name not in OBJECT_CFG_BY_NAME:
            raise KeyError(f"Unknown object_name '{name}'; not in OBJECT_CFG_BY_NAME")
        assets_spawn_cfg.append(OBJECT_CFG_BY_NAME[name].spawn)

    cfg.scene.object = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Object",
        spawn=sim_utils.MultiAssetSpawnerCfg(
            assets_cfg=assets_spawn_cfg,
            random_choice=False,
            activate_contact_sensors=True,
        ),
    )
    cfg.scene.replicate_physics = False

    # 根据物体类型添加额外场景物体
    _add_conditional_scene_objects(cfg, object_names)
    
    # 直接设置事件函数的 object_names 参数
    if hasattr(cfg, 'events') and hasattr(cfg.events, 'reset_conditional_objects'):
        cfg.events.reset_conditional_objects.params["object_names"] = object_names
        # 传递初始 z 坐标配置
        if has_h_frame := ("h_frame" in object_names):
            cfg.events.reset_conditional_objects.params["h_frame_wall1_init_z"] = cfg.scene.h_frame_wall1.init_state.pos[2]
            cfg.events.reset_conditional_objects.params["h_frame_wall2_init_z"] = cfg.scene.h_frame_wall2.init_state.pos[2]
        if has_ladder := ("ladder" in object_names):
            cfg.events.reset_conditional_objects.params["ladder_support1_init_z"] = cfg.scene.ladder_support1.init_state.pos[2]
            cfg.events.reset_conditional_objects.params["ladder_support2_init_z"] = cfg.scene.ladder_support2.init_state.pos[2]
            cfg.events.reset_conditional_objects.params["ladder_support3_init_z"] = cfg.scene.ladder_support3.init_state.pos[2]
            cfg.events.reset_conditional_objects.params["ladder_support4_init_z"] = cfg.scene.ladder_support4.init_state.pos[2]
        # print(f"[DEBUG] Set object_names in event config: {object_names}")

    # print(f"[INFO]: Resolved scene.object across {len(object_names)} object(s): {object_names}")
    return ManagerBasedRLEnv(cfg=cfg, **kwargs)


def _add_conditional_scene_objects(cfg, object_names: list[str]):
    """根据物体类型添加额外的场景物体（如墙）。
    
    为所有环境添加额外物体，但通过事件管理器在reset时根据每个环境分配的
    主物体类型来动态设置额外物体的位置（需要的环境放在正确位置，不需要的放在地下）。
    
    Args:
        cfg: 环境配置
        object_names: 当前场景中的物体名称列表（按环境分配顺序）
    """
    has_h_frame = "h_frame" in object_names
    has_ladder = "ladder" in object_names
    
    if not has_h_frame and not has_ladder:
        return
    
    # 如果包含 h_frame，添加两堵墙
    if has_h_frame:
        # print(f"[INFO]: Detected h_frame object, adding walls to all environments")
        
        # 添加墙1
        cfg.scene.h_frame_wall1 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/h_frame_wall1",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/h_frame/hframe_wall_mode3.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[-1.0, -3.0, 1.0],
                rot=[0.707, 0.0, 0.0, 0.707],
            ),
        )
        
        # 添加墙2
        cfg.scene.h_frame_wall2 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/h_frame_wall2",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/h_frame/hframe_wall_mode3.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[0.65, -6.0, 1.0],
                rot=[1.0, 0.0, 0.0, 0.0],
            ),
        )

    if has_ladder:
        # print(f"[INFO]: Detected ladder object, adding ladder support to all environments")

        # 添加支撑1
        cfg.scene.ladder_support1 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/ladder_support1",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/ladder/ladder_support1.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[0.0, 0.0, 0.5],
                rot=[1., 0.0, 0.0, 0.],
            ),
        )

        # 添加支撑2
        cfg.scene.ladder_support2 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/ladder_support2",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/ladder/ladder_support2.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[0.0, 0.0, 0.5],
                rot=[1., 0.0, 0.0, 0.],
            ),
        )

        cfg.scene.ladder_support3 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/ladder_support3",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/ladder/ladder_support3.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[0.0, 0.0, 0.7],
                rot=[1., 0.0, 0.0, 0.],
            ),
        )

        cfg.scene.ladder_support4 = RigidObjectCfg(
            prim_path="{ENV_REGEX_NS}/ladder_support4",
            spawn=sim_utils.UsdFileCfg(
                usd_path=f"{ASSET_DIR}/ladder/ladder_support4.usd",
                scale=(1.0, 1.0, 1.0),
                activate_contact_sensors=True,
                rigid_props=sim_utils.RigidBodyPropertiesCfg(
                    kinematic_enabled=True,
                    disable_gravity=True,
                ),
                collision_props=sim_utils.CollisionPropertiesCfg(
                    contact_offset=0.005,
                ),
            ),
            init_state=RigidObjectCfg.InitialStateCfg(
                pos=[0.0, 0.0, 0.7],
                rot=[1., 0.0, 0.0, 0.],
            ),
        )


gym.register(
    id="G1-Inspire-HOI-v0",
    entry_point=_make_env,
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.env_cfg:G1HoiLearningEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:PPORunnerCfg",
    },
)
