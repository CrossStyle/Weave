#!/usr/bin/env python
"""
测试条件场景物体加载功能

测试不同物体配置下，场景中是否正确加载了额外的物体（如墙）。

使用方法:
    # 测试 h_frame（应该有墙）
    python scripts/test_conditional_scene.py --object h_frame
    
    # 测试 woodchair（不应该有墙）
    python scripts/test_conditional_scene.py --object woodchair
    
    # 测试多个物体（包含h_frame，应该有墙）
    python scripts/test_conditional_scene.py --object h_frame --object woodchair

退出：按 Q 或 ESC
"""

import argparse
import sys

import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Test conditional scene object loading")
parser.add_argument(
    "--object",
    type=str,
    action="append",
    default=None,
    help="Object name(s) to test (e.g., h_frame, woodchair). Can be specified multiple times.",
)
parser.add_argument("--num_envs", type=int, default=4, help="Number of environments to visualize")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# 如果没有指定物体，使用默认列表
if args_cli.object is None:
    test_objects = ["h_frame"]
else:
    test_objects = args_cli.object

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import carb
import omni.appwindow

import isaaclab.sim as sim_utils
from isaaclab.envs import ManagerBasedRLEnv


def create_test_config(object_names: list[str]):
    """创建测试用的环境配置"""
    # 创建一个临时motion文件路径列表（实际不需要真实文件，只需要object名称）
    # 我们通过修改配置来模拟不同的物体组合
    
    from g1_hoi_learning.tasks.hoi.env_cfg import G1HoiLearningEnvCfg
    
    cfg = G1HoiLearningEnvCfg()
    cfg.scene.num_envs = args_cli.num_envs
    cfg.scene.env_spacing = 5.0
    
    # 修改motion配置来使用指定的物体
    # 注意：这里我们需要实际的motion文件，所以我们尝试找到对应的文件
    import os
    motion_files = []
    
    data_dirs = [
        "./data/datasets/Weave/rollout/train",
        "./data/test",
        "./data/eval",
    ]
    
    for obj_name in object_names:
        found = False
        for data_dir in data_dirs:
            if os.path.isdir(data_dir):
                for file in os.listdir(data_dir):
                    if obj_name in file.lower() and file.endswith('.npz'):
                        motion_files.append(os.path.join(data_dir, file))
                        found = True
                        break
            if found:
                break
        
        if not found:
            print(f"[WARNING] 未找到 {obj_name} 的motion文件，尝试使用默认路径")
            # 如果找不到，使用一个可能的默认路径
            motion_files.append(f"./data/test/{obj_name}.npz")
    
    if motion_files:
        cfg.commands.motion.motion_files = motion_files
    else:
        print("[ERROR] 没有找到任何motion文件")
        sys.exit(1)
    
    return cfg


class SceneInspector:
    """场景检查器：验证场景中是否存在预期的物体"""
    
    def __init__(self):
        self.quit = False
        self._setup_keyboard()
    
    def _setup_keyboard(self):
        """设置键盘监听"""
        self._input = carb.input.acquire_input_interface()
        self._keyboard = omni.appwindow.get_default_app_window().get_keyboard()
        self._keyboard_sub = self._input.subscribe_to_keyboard_events(self._keyboard, self._on_keyboard_event)
    
    def _on_keyboard_event(self, event, *args, **kwargs):
        """键盘事件处理"""
        if event.type != carb.input.KeyboardEventType.KEY_PRESS:
            return True
        key = event.input
        K = carb.input.KeyboardInput
        if key in (K.Q, K.ESCAPE):
            self.quit = True
        return True
    
    def close(self):
        """清理资源"""
        if self._keyboard_sub is not None:
            self._input.unsubscribe_to_keyboard_events(self._keyboard, self._keyboard_sub)
            self._keyboard_sub = None
    
    def inspect_scene(self, env):
        """检查场景中的物体"""
        print("\n" + "=" * 60)
        print("场景检查报告")
        print("=" * 60)
        
        # 获取场景中的所有实体
        scene = env.scene
        print(f"\n场景中的实体数量: {len(scene._scene_entities)}")
        print(f"场景实体名称: {list(scene._scene_entities.keys())}")
        
        # 检查是否有墙
        has_wall_1 = "wall_1" in scene._scene_entities
        has_wall_2 = "wall_2" in scene._scene_entities
        
        print(f"\n✓ 墙体检测:")
        print(f"  - wall_1 存在: {'✅ 是' if has_wall_1 else '❌ 否'}")
        print(f"  - wall_2 存在: {'✅ 是' if has_wall_2 else '❌ 否'}")
        
        # 检查物体
        if "object" in scene._scene_entities:
            print(f"\n✓ 主物体 (object): ✅ 存在")
        
        # 尝试使用USD Stage检查场景图（可选）
        print(f"\n✓ USD Stage 场景图检查:")
        try:
            import omni.usd
            from pxr import UsdGeom
            
            stage = omni.usd.get_context().get_stage()
            
            # 检查每个环境
            for env_idx in range(min(args_cli.num_envs, 2)):  # 只检查前2个环境
                env_prim_path = f"/World/envs/env_{env_idx}"
                env_prim = stage.GetPrimAtPath(env_prim_path)
                
                if env_prim.IsValid():
                    print(f"\n  环境 {env_idx} ({env_prim_path}):")
                    children = env_prim.GetChildren()
                    child_names = [child.GetName() for child in children]
                    print(f"    子物体: {child_names}")
                    
                    # 检查特定物体
                    for obj_name in ["Wall1", "Wall2", "Object", "Robot"]:
                        obj_path = f"{env_prim_path}/{obj_name}"
                        obj_prim = stage.GetPrimAtPath(obj_path)
                        if obj_prim.IsValid():
                            # 获取位置信息
                            xformable = UsdGeom.Xformable(obj_prim)
                            if xformable:
                                local_transform = xformable.ComputeLocalToWorldTransform(0)
                                translation = local_transform.ExtractTranslation()
                                print(f"    ✅ {obj_name}: 位置 = ({translation[0]:.2f}, {translation[1]:.2f}, {translation[2]:.2f})")
                        else:
                            print(f"    ❌ {obj_name}: 不存在")
        except Exception as e:
            print(f"  ⚠️  USD Stage 检查跳过: {e}")
        
        print("\n" + "=" * 60)
        print("按 Q 或 ESC 退出")
        print("=" * 60 + "\n")


def main():
    print(f"\n{'=' * 60}")
    print(f"测试配置:")
    print(f"  物体: {test_objects}")
    print(f"  环境数量: {args_cli.num_envs}")
    print(f"{'=' * 60}\n")
    
    # 根据物体名称判断是否应该有墙
    should_have_walls = "h_frame" in test_objects
    print(f"预期结果: {'应该有墙' if should_have_walls else '不应该有墙'} (因为{'包含' if should_have_walls else '不包含'} h_frame)\n")
    
    try:
        # 导入环境
        import gymnasium as gym
        import g1_hoi_learning.tasks.hoi  # 注册环境
        
        # 创建配置
        env_cfg = create_test_config(test_objects)
        
        # 创建环境
        print("[INFO] 正在创建环境...")
        env = gym.make("G1-Inspire-HOI-v0", cfg=env_cfg)
        
        print("[INFO] 环境创建成功！")
        
        # 创建检查器
        inspector = SceneInspector()
        
        # 检查场景
        inspector.inspect_scene(env)
        
        # 运行仿真循环（可视化）
        print("[INFO] 开始仿真...")
        
        while simulation_app.is_running() and not inspector.quit:
            # 执行一个随机动作
            action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
            env.step(action)
        
        inspector.close()
        env.close()
        
        print("\n[INFO] 测试完成")
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
