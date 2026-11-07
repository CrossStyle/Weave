#!/usr/bin/env python
"""
IsaacLab可视化脚本：回放reference motion（机器人 + 交互物体），不跑物理，只做运动学回放。

使用方法:
    python scripts/visualize_reference_motion.py --motion_file data/train/clothesstand_861clip.npz

键盘控制（需要先点一下Isaac Sim窗口让它获得焦点）:
    - 左箭头: 上一个motion clip
    - 右箭头: 下一个motion clip
    - 空格: 暂停/播放
    - R: 当前clip回到第一帧
    - Q/ESC: 退出
"""

import argparse

# Windows: torch 必须在启动 Isaac Sim 之前导入，否则 Kit 先加载的 DLL 会和 torch 的冲突，导致 access violation
import torch  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Visualize reference motion in IsaacLab")
parser.add_argument(
    "--motion_file",
    type=str,
    # default=r"D:\code\robot\Weave\source\g1_hoi_learning\g1_hoi_learning\objects\h_frame\h_frame_weave.npz",
    default=r"D:\code\robot\Weave\source\g1_hoi_learning\g1_hoi_learning\objects\ladder\ladder_weave_8s.npz",
    # default="D:/code/robot/Weave/data/datasets/Weave/rollout/train/sub17_woodchair_005.npz",
    # default=r"D:\code\robot\Weave\data\datasets\Weave\rollout\test\clothesstand_rollout.npz",
    help="Path to motion npz file",
)
parser.add_argument("--fps", type=float, default=None, help="Playback framerate (default: motion fps)")
parser.add_argument("--start_clip", type=int, default=0, help="Start from which clip index")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import os
import time

import carb
import omni.appwindow

import isaaclab.sim as sim_utils
from isaaclab.assets import Articulation, AssetBaseCfg, RigidObject, RigidObjectCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.utils import configclass
from isaaclab.sensors import ContactSensorCfg

from g1_hoi_learning.assets import GROUND_PLANE_USD_PATH
from g1_hoi_learning.objects.object_cfg import OBJECT_CFG_BY_NAME
from g1_hoi_learning.robots.g1_inspire import G1_INSPIRE_CFG
from g1_hoi_learning.tasks.hoi.mdp.commands import MotionLoader
from g1_hoi_learning.objects import ASSET_DIR


# 不属于当前clip的物体放到这里藏起来
HIDDEN_POS = (0.0, 0.0, -100.0)


@configclass
class VisualizationSceneCfg(InteractiveSceneCfg):
    """可视化场景：地面 + 灯光 + 机器人。物体在运行时按motion文件里的object_names添加。"""

    ground = AssetBaseCfg(
        prim_path="/World/ground",
        # 用程序化网格地面，不依赖贴图文件
        spawn=sim_utils.GroundPlaneCfg(size=(100.0, 100.0)),
    )

    dome_light = AssetBaseCfg(
        prim_path="/World/DomeLight",
        spawn=sim_utils.DomeLightCfg(color=(0.9, 0.9, 0.9), intensity=500.0),
    )

    robot = G1_INSPIRE_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    feet_contact_sensor = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/.*_ankle_roll_link",
        history_length=3,
        track_air_time=True,
    )

    # h-frame
    # wall_1 = RigidObjectCfg(
    #     prim_path="{ENV_REGEX_NS}/Wall1",
    #     spawn=sim_utils.UsdFileCfg(
    #         usd_path=f"{ASSET_DIR}/../objects/h_frame/hframe_wall_mode3.usd",
    #         scale=(1.0, 1.0, 1.0),
    #         rigid_props=sim_utils.RigidBodyPropertiesCfg(
    #             kinematic_enabled=True,  # 静态物体
    #             disable_gravity=True,
    #         ),
    #     ),
    #     init_state=RigidObjectCfg.InitialStateCfg(
    #         pos=[-1.0, -3.0, 0.0],
    #         rot=[0.707, 0.0, 0.0, 0.707],  # 四元数 [x, y, z, w]
    #     ),
    # )
    #
    # wall_2 = RigidObjectCfg(
    #     prim_path="{ENV_REGEX_NS}/Wall2",
    #     spawn=sim_utils.UsdFileCfg(
    #         usd_path=f"{ASSET_DIR}/../objects/h_frame/hframe_wall_mode3.usd",
    #         scale=(1.0, 1.0, 1.0),
    #         rigid_props=sim_utils.RigidBodyPropertiesCfg(
    #             kinematic_enabled=True,  # 静态物体
    #             disable_gravity=True,
    #         ),
    #     ),
    #     init_state=RigidObjectCfg.InitialStateCfg(
    #         pos=[0.65, -6.0, 0.0],
    #         rot=[1.0, 0.0, 0.0, 0.0],  # 无旋转
    #     ),
    # )

    # h-frame
    ladder_support1 = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Wall1",
        spawn=sim_utils.UsdFileCfg(
            usd_path=f"{ASSET_DIR}/../objects/ladder/ladder_support1.usd",
            scale=(1.0, 1.0, 1.0),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,  # 静态物体
                disable_gravity=True,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=[0.0, 0.0, 0.0],
            rot=[1., 0.0, 0.0, 0.],  # 四元数 [w, x, y, z]
        ),
    )

    ladder_support2 = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Wall2",
        spawn=sim_utils.UsdFileCfg(
            usd_path=f"{ASSET_DIR}/../objects/ladder/ladder_support2.usd",
            scale=(1.0, 1.0, 1.0),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,  # 静态物体
                disable_gravity=True,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=[0.0, 0.0, 0.0],
            rot=[1., 0.0, 0.0, 0.],  # 四元数 [w, x, y, z]
        ),
    )

    ladder_support3 = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Wall3",
        spawn=sim_utils.UsdFileCfg(
            usd_path=f"{ASSET_DIR}/../objects/ladder/ladder_support3.usd",
            scale=(1.0, 1.0, 1.0),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,  # 静态物体
                disable_gravity=True,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=[0.0, 0.0, 0.0],
            rot=[1., 0.0, 0.0, 0.],  # 四元数 [w, x, y, z]
        ),
    )

    ladder_support4 = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Wall4",
        spawn=sim_utils.UsdFileCfg(
            usd_path=f"{ASSET_DIR}/../objects/ladder/ladder_support4.usd",
            scale=(1.0, 1.0, 1.0),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=True,  # 静态物体
                disable_gravity=True,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=[0.0, 0.0, 0.0],
            rot=[1., 0.0, 0.0, 0.],  # 四元数 [w, x, y, z]
        ),
    )


class MotionVisualizer:
    """Reference motion回放器"""

    def __init__(self, sim: sim_utils.SimulationContext, motion_file: str, start_clip: int, fps: float | None):
        self.sim = sim
        self.device = sim.device

        print(f"[INFO] 加载motion文件: {motion_file}")
        self.motion = MotionLoader([motion_file], device=self.device)
        # breakpoint()
        print(f"[INFO] clips: {self.motion.num_clips}, objects: {self.motion.object_names}, fps: {self.motion.fps}")

        for name in self.motion.object_names:
            if name not in OBJECT_CFG_BY_NAME:
                raise KeyError(f"Unknown object_name '{name}'; not in OBJECT_CFG_BY_NAME")

        # 每种物体各生成一个，只显示当前clip用到的那个
        scene_cfg = VisualizationSceneCfg(num_envs=1, env_spacing=5.0)
        self.object_keys = []
        for i, name in enumerate(self.motion.object_names):
            key = f"object_{i}"
            setattr(scene_cfg, key, OBJECT_CFG_BY_NAME[name].replace(prim_path=f"{{ENV_REGEX_NS}}/Object_{name}"))

            # 为每个物体都建一个sensor
            setattr(scene_cfg, f"contact_sensor_{name}",
                    ContactSensorCfg(
                        prim_path=f"{{ENV_REGEX_NS}}/Object_{name}",
                        history_length=0,
                        track_air_time=False,
                        filter_prim_paths_expr=[
                            # robot.body_names order
                            "{ENV_REGEX_NS}/Robot/pelvis",
                            "{ENV_REGEX_NS}/Robot/left_hip_pitch_link", "{ENV_REGEX_NS}/Robot/right_hip_pitch_link",
                            "{ENV_REGEX_NS}/Robot/waist_yaw_link",
                            "{ENV_REGEX_NS}/Robot/left_hip_roll_link", "{ENV_REGEX_NS}/Robot/right_hip_roll_link",
                            "{ENV_REGEX_NS}/Robot/waist_roll_link",
                            "{ENV_REGEX_NS}/Robot/left_hip_yaw_link", "{ENV_REGEX_NS}/Robot/right_hip_yaw_link",
                            "{ENV_REGEX_NS}/Robot/torso_link",
                            "{ENV_REGEX_NS}/Robot/left_knee_link", "{ENV_REGEX_NS}/Robot/right_knee_link",
                            "{ENV_REGEX_NS}/Robot/left_shoulder_pitch_link",
                            "{ENV_REGEX_NS}/Robot/right_shoulder_pitch_link",
                            "{ENV_REGEX_NS}/Robot/left_ankle_pitch_link", "{ENV_REGEX_NS}/Robot/right_ankle_pitch_link",
                            "{ENV_REGEX_NS}/Robot/left_shoulder_roll_link",
                            "{ENV_REGEX_NS}/Robot/right_shoulder_roll_link",
                            "{ENV_REGEX_NS}/Robot/left_ankle_roll_link", "{ENV_REGEX_NS}/Robot/right_ankle_roll_link",
                            "{ENV_REGEX_NS}/Robot/left_shoulder_yaw_link",
                            "{ENV_REGEX_NS}/Robot/right_shoulder_yaw_link",
                            "{ENV_REGEX_NS}/Robot/left_elbow_link", "{ENV_REGEX_NS}/Robot/right_elbow_link",
                            "{ENV_REGEX_NS}/Robot/left_wrist_roll_link", "{ENV_REGEX_NS}/Robot/right_wrist_roll_link",
                            "{ENV_REGEX_NS}/Robot/left_wrist_pitch_link", "{ENV_REGEX_NS}/Robot/right_wrist_pitch_link",
                            "{ENV_REGEX_NS}/Robot/left_wrist_yaw_link", "{ENV_REGEX_NS}/Robot/right_wrist_yaw_link",
                            "{ENV_REGEX_NS}/Robot/L_index_proximal", "{ENV_REGEX_NS}/Robot/L_middle_proximal",
                            "{ENV_REGEX_NS}/Robot/L_pinky_proximal", "{ENV_REGEX_NS}/Robot/L_ring_proximal",
                            "{ENV_REGEX_NS}/Robot/L_thumb_proximal_base",
                            "{ENV_REGEX_NS}/Robot/R_index_proximal", "{ENV_REGEX_NS}/Robot/R_middle_proximal",
                            "{ENV_REGEX_NS}/Robot/R_pinky_proximal", "{ENV_REGEX_NS}/Robot/R_ring_proximal",
                            "{ENV_REGEX_NS}/Robot/R_thumb_proximal_base",
                            "{ENV_REGEX_NS}/Robot/L_index_intermediate", "{ENV_REGEX_NS}/Robot/L_middle_intermediate",
                            "{ENV_REGEX_NS}/Robot/L_pinky_intermediate", "{ENV_REGEX_NS}/Robot/L_ring_intermediate",
                            "{ENV_REGEX_NS}/Robot/L_thumb_proximal",
                            "{ENV_REGEX_NS}/Robot/R_index_intermediate", "{ENV_REGEX_NS}/Robot/R_middle_intermediate",
                            "{ENV_REGEX_NS}/Robot/R_pinky_intermediate", "{ENV_REGEX_NS}/Robot/R_ring_intermediate",
                            "{ENV_REGEX_NS}/Robot/R_thumb_proximal",
                            "{ENV_REGEX_NS}/Robot/L_thumb_intermediate", "{ENV_REGEX_NS}/Robot/R_thumb_intermediate",
                            "{ENV_REGEX_NS}/Robot/L_thumb_distal", "{ENV_REGEX_NS}/Robot/R_thumb_distal",
                        ]
                    ))

            self.object_keys.append(key)
        self.scene = InteractiveScene(scene_cfg)

        # 初始化物理句柄（之后不再step物理，只写状态+渲染）
        self.sim.reset()

        self.robot: Articulation = self.scene["robot"]
        self.objects: list[RigidObject] = [self.scene[k] for k in self.object_keys]
        self.env_origin = self.scene.env_origins[0:1]
        self.hidden_state = torch.zeros((1, 13), device=self.device)
        self.hidden_state[:, :3] = torch.tensor(HIDDEN_POS, device=self.device)
        self.hidden_state[:, 3] = 1.0

        self.clip_idx = min(max(start_clip, 0), self.motion.num_clips - 1)
        self.frame = 0
        self.playing = True
        self.frame_dt = 1.0 / (fps if fps else self.motion.fps)

        # 键盘回调里只改标志位，真正的切换放在主循环里做
        self._pending: list[str] = []
        self.quit = False
        self._setup_keyboard()

        self._start_clip()

    # ------------------------------------------------------------------ keyboard

    def _setup_keyboard(self):
        self._input = carb.input.acquire_input_interface()
        self._keyboard = omni.appwindow.get_default_app_window().get_keyboard()
        self._keyboard_sub = self._input.subscribe_to_keyboard_events(self._keyboard, self._on_keyboard_event)

    def close(self):
        if self._keyboard_sub is not None:
            self._input.unsubscribe_to_keyboard_events(self._keyboard, self._keyboard_sub)
            self._keyboard_sub = None

    def _on_keyboard_event(self, event, *args, **kwargs):
        if event.type != carb.input.KeyboardEventType.KEY_PRESS:
            return True
        key = event.input
        K = carb.input.KeyboardInput
        if key == K.LEFT:
            self._pending.append("prev")
        elif key == K.RIGHT:
            self._pending.append("next")
        elif key == K.SPACE:
            self._pending.append("toggle")
        elif key == K.R:
            self._pending.append("restart")
        elif key in (K.Q, K.ESCAPE):
            self.quit = True
        return True

    def _handle_pending(self):
        while self._pending:
            cmd = self._pending.pop(0)
            if cmd == "prev":
                self.clip_idx = (self.clip_idx - 1) % self.motion.num_clips
                self._start_clip()
            elif cmd == "next":
                self.clip_idx = (self.clip_idx + 1) % self.motion.num_clips
                self._start_clip()
            elif cmd == "toggle":
                self.playing = not self.playing
                print(f"[INFO] {'播放' if self.playing else '暂停'}")
            elif cmd == "restart":
                self.frame = 0
                print("[INFO] 回到第一帧")

    # ------------------------------------------------------------------ playback

    def _start_clip(self):
        self.frame = 0
        frame = self._current_frame()
        # 每次切clip把相机对准机器人
        target = (frame.body_pos_w[0, 0] + self.env_origin[0]).tolist()
        eye = [target[0] - 3.0, target[1] - 3.0, target[2] + 1.5]
        self.sim.set_camera_view(eye=eye, target=target)
        self._print_clip_info()

    def _current_frame(self):
        clip = torch.tensor([self.clip_idx], dtype=torch.long, device=self.device)
        t = torch.tensor([self.frame], dtype=torch.long, device=self.device)
        return self.motion.frames(clip, t)

    def _print_clip_info(self):
        length = int(self.motion.clip_lengths[self.clip_idx])
        obj_name = self.motion.object_names[int(self.motion.clip_object[self.clip_idx])]
        print(
            f"[CLIP] {self.clip_idx}/{self.motion.num_clips - 1}  object={obj_name}  "
            f"length={length} frames ({length / self.motion.fps:.2f}s)"
        )

    def _write_frame(self):
        f = self._current_frame()

        root_state = torch.cat(
            [f.body_pos_w[:, 0] + self.env_origin, f.body_quat_w[:, 0], f.body_lin_vel_w[:, 0], f.body_ang_vel_w[:, 0]],
            dim=-1,
        )
        self.robot.write_root_state_to_sim(root_state)
        self.robot.write_joint_state_to_sim(f.joint_pos, f.joint_vel)

        active = int(self.motion.clip_object[self.clip_idx])
        for i, obj in enumerate(self.objects):
            if i == active:
                obj_state = torch.cat(
                    [f.object_pos_w + self.env_origin, f.object_quat_w, f.object_lin_vel_w, f.object_ang_vel_w], dim=-1
                )
                obj.write_root_state_to_sim(obj_state)
            else:
                obj.write_root_state_to_sim(self.hidden_state)

    def run(self):
        print(
            "\n[INFO] 键盘: ←/→ 切换clip, 空格 暂停/播放, R 回到第一帧, Q/ESC 退出"
            "（先点一下Isaac Sim窗口让它获得键盘焦点）\n"
        )
        while simulation_app.is_running() and not self.quit:
            t0 = time.perf_counter()
            self._handle_pending()

            self._write_frame()
            # 不调用sim.step()：物理不推进，只刷新运动学和画面
            self.sim.render()
            self.scene.update(self.frame_dt)

            if self.playing:
                self.frame += 1
                if self.frame >= int(self.motion.clip_lengths[self.clip_idx]):
                    self.frame = 0

            sleep = self.frame_dt - (time.perf_counter() - t0)
            if sleep > 0:
                time.sleep(sleep)


def main():
    print(f"[DEBUG] motion_file={args_cli.motion_file}")
    print(f"[DEBUG] file exists: {os.path.isfile(args_cli.motion_file)}")
    if not os.path.isfile(args_cli.motion_file):
        raise FileNotFoundError(f"Motion文件不存在: {args_cli.motion_file}")

    print("[DEBUG] Creating SimulationContext...")
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=1.0 / 50.0, device=args_cli.device))
    print("[DEBUG] Creating MotionVisualizer...")
    visualizer = MotionVisualizer(sim, args_cli.motion_file, args_cli.start_clip, args_cli.fps)
    print("[DEBUG] Starting run loop...")

    visualizer.run()
    visualizer.close()
    # try:
    #     visualizer.run()
    # finally:
    #     visualizer.close()


if __name__ == "__main__":
    # try:
    #     main()
    # finally:
    #     simulation_app.close()

    main()
    simulation_app.close()
