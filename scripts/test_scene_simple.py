#!/usr/bin/env python
"""
简单测试脚本：验证条件场景物体加载功能

这个脚本直接使用训练配置，测试场景中是否正确加载了墙。

使用方法:
    # 使用默认配置（train.yaml）
    python scripts/test_scene_simple.py
    
    # 使用headless模式（无GUI，快速测试）
    python scripts/test_scene_simple.py --headless
    
    # 指定环境数量
    python scripts/test_scene_simple.py --num_envs=2

提示：
    - 如果 motion_files 包含 h_frame，场景中应该有 wall_1 和 wall_2
    - 如果不包含 h_frame，场景中不应该有墙
    - 运行后会在控制台输出场景实体列表
    - GUI模式下按 Q 或 ESC 退出
"""

import argparse
import sys

import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Test conditional scene object loading")
parser.add_argument(
    "--config-dir",
    type=str,
    default="./configs/track",
    help="Config directory",
)
parser.add_argument(
    "--config-name",
    type=str,
    default="train",
    help="Config name (without .yaml)",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import carb
import omni.appwindow


class SceneInspector:
    """场景检查器"""
    
    def __init__(self):
        self.quit = False
        if not args_cli.headless:
            self._setup_keyboard()
    
    def _setup_keyboard(self):
        """设置键盘监听"""
        try:
            self._input = carb.input.acquire_input_interface()
            self._keyboard = omni.appwindow.get_default_app_window().get_keyboard()
            self._keyboard_sub = self._input.subscribe_to_keyboard_events(self._keyboard, self._on_keyboard_event)
        except Exception as e:
            print(f"[WARNING] 无法设置键盘监听: {e}")
    
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
        if hasattr(self, '_keyboard_sub') and self._keyboard_sub is not None:
            self._input.unsubscribe_to_keyboard_events(self._keyboard, self._keyboard_sub)
            self._keyboard_sub = None
    
    def inspect_scene(self, env):
        """检查场景中的物体"""
        print("\n" + "=" * 70)
        print("场景检查报告".center(70))
        print("=" * 70)
        
        # 获取场景中的所有实体
        scene = env.unwrapped.scene
        scene_entities = list(scene._scene_entities.keys())
        
        print(f"\n📦 场景实体列表 (共 {len(scene_entities)} 个):")
        for i, entity_name in enumerate(scene_entities, 1):
            print(f"   {i}. {entity_name}")
        
        # 检查关键物体
        print(f"\n🔍 关键物体检测:")
        
        critical_objects = {
            "robot": "机器人",
            "object": "交互物体",
            "wall_1": "墙 1",
            "wall_2": "墙 2",
            "ground": "地面",
        }
        
        for obj_key, obj_desc in critical_objects.items():
            exists = obj_key in scene_entities
            status = "✅" if exists else "❌"
            print(f"   {status} {obj_desc:15s} ({obj_key})")
        
        # 判断是否符合预期
        has_walls = "wall_1" in scene_entities and "wall_2" in scene_entities
        
        # 从motion文件推断物体类型
        motion_files = env.unwrapped.cfg.commands.motion.motion_files
        print(f"\n📄 Motion 文件配置:")
        for i, mf in enumerate(motion_files, 1):
            print(f"   {i}. {mf}")
        
        # 简单检查文件名中是否包含 h_frame
        has_hframe = any("h_frame" in str(mf).lower() for mf in motion_files)
        
        print(f"\n💡 分析结果:")
        print(f"   - Motion文件中{'包含' if has_hframe else '不包含'} h_frame")
        print(f"   - 场景中{'有' if has_walls else '没有'}墙")
        
        if has_hframe and has_walls:
            print(f"   - ✅ 结果符合预期：h_frame 场景应该有墙")
        elif not has_hframe and not has_walls:
            print(f"   - ✅ 结果符合预期：非 h_frame 场景不应该有墙")
        elif has_hframe and not has_walls:
            print(f"   - ❌ 结果异常：h_frame 场景应该有墙，但没有找到")
        else:
            print(f"   - ❌ 结果异常：非 h_frame 场景不应该有墙，但找到了墙")
        
        # 尝试使用USD Stage检查（可选，如果可用的话）
        print(f"\n🌍 环境 0 详细信息:")
        try:
            import omni.usd
            from pxr import UsdGeom
            
            stage = omni.usd.get_context().get_stage()
            env_prim_path = "/World/envs/env_0"
            env_prim = stage.GetPrimAtPath(env_prim_path)
            
            if env_prim.IsValid():
                children = env_prim.GetChildren()
                child_names = [child.GetName() for child in children]
                print(f"   子物体: {', '.join(child_names)}")
                
                # 检查墙的位置（如果存在）
                for wall_name in ["Wall1", "Wall2"]:
                    wall_path = f"{env_prim_path}/{wall_name}"
                    wall_prim = stage.GetPrimAtPath(wall_path)
                    if wall_prim.IsValid():
                        xformable = UsdGeom.Xformable(wall_prim)
                        if xformable:
                            local_transform = xformable.ComputeLocalToWorldTransform(0)
                            translation = local_transform.ExtractTranslation()
                            print(f"   ✅ {wall_name} 位置: ({translation[0]:.2f}, {translation[1]:.2f}, {translation[2]:.2f})")
            else:
                print(f"   ❌ 无法找到环境路径: {env_prim_path}")
        except Exception as e:
            print(f"   ⚠️  USD Stage 检查跳过 (这不影响功能验证): {e}")
        
        print("\n" + "=" * 70)
        if not args_cli.headless:
            print("按 Q 或 ESC 退出".center(70))
            print("=" * 70)
        print()


def main():
    print(f"\n{'=' * 70}")
    print("测试条件场景物体加载".center(70))
    print("=" * 70)
    print(f"配置: {args_cli.config_dir}/{args_cli.config_name}.yaml")
    print(f"模式: {'Headless (无GUI)' if args_cli.headless else 'GUI'}")
    print("=" * 70)
    
    try:
        # 导入环境
        import gymnasium as gym
        import g1_hoi_learning.tasks.hoi  # 注册环境
        
        # 使用 hydra 加载配置
        from hydra import compose, initialize_config_dir
        import os
        
        config_dir = os.path.abspath(args_cli.config_dir)
        print(f"\n[INFO] 从配置目录加载: {config_dir}")
        
        with initialize_config_dir(config_dir=config_dir, version_base=None):
            cfg = compose(config_name=args_cli.config_name)
        
        # 修改一些配置以便快速测试
        if hasattr(cfg, 'env') and hasattr(cfg.env, 'scene'):
            original_num_envs = cfg.env.scene.num_envs
            # 限制环境数量以加快启动
            cfg.env.scene.num_envs = min(4, original_num_envs)
            print(f"[INFO] 环境数量: {original_num_envs} -> {cfg.env.scene.num_envs} (为加快测试)")
        
        # 创建环境
        print("\n[INFO] 正在创建环境...")
        print("[INFO] (这可能需要一些时间，请耐心等待...)")
        
        env = gym.make("G1-Inspire-HOI-v0", cfg=cfg.env)
        
        print("[INFO] ✅ 环境创建成功！")
        
        # 创建检查器
        inspector = SceneInspector()
        
        # 检查场景
        inspector.inspect_scene(env)
        
        # 在headless模式下，快速运行几步就退出
        if args_cli.headless:
            print("\n[INFO] Headless模式：运行10步后退出...")
            for i in range(10):
                action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                env.step(action)
            print("[INFO] ✅ 测试完成")
        else:
            # GUI模式：持续运行直到用户退出
            print("\n[INFO] GUI模式：仿真运行中...")
            step_count = 0
            while simulation_app.is_running() and not inspector.quit:
                action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                env.step(action)
                step_count += 1
                
                # 每100步打印一次
                if step_count % 100 == 0:
                    print(f"[INFO] 已运行 {step_count} 步...")
            
            print(f"\n[INFO] ✅ 测试完成 (共运行 {step_count} 步)")
        
        inspector.close()
        env.close()
        
    except Exception as e:
        print(f"\n[ERROR] ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
