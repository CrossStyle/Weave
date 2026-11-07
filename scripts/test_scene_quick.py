#!/usr/bin/env python
"""
最简单的测试脚本：直接创建环境并检查场景

使用方法:
    # 快速测试
    python scripts/test_scene_quick.py --headless
    
    # GUI 模式查看场景
    python scripts/test_scene_quick.py

这个脚本会直接使用代码中注册的环境，检查墙是否正确加载。
"""

import argparse
import sys

import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Quick test for conditional scene object loading")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import carb
import omni.appwindow


class QuickTester:
    """快速测试器"""
    
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
    
    def check_scene(self, env):
        """检查场景"""
        print("\n" + "=" * 70)
        print("场景检查报告".center(70))
        print("=" * 70)
        
        scene = env.unwrapped.scene
        
        # 尝试获取场景实体列表
        if hasattr(scene, '_scene_entities'):
            scene_entities = list(scene._scene_entities.keys())
        elif hasattr(scene, 'keys'):
            scene_entities = list(scene.keys())
        else:
            # 手动检查已知的实体
            scene_entities = []
            known_entities = ['robot', 'object', 'wall_1', 'wall_2', 'ground', 'dome_light', 
                            'contact_sensor', 'feet_contact_sensor']
            for entity in known_entities:
                try:
                    _ = scene[entity]
                    scene_entities.append(entity)
                except (KeyError, AttributeError):
                    pass
        
        print(f"\n📦 场景实体列表 (共 {len(scene_entities)} 个):")
        for i, name in enumerate(scene_entities, 1):
            icon = "🧱" if "wall" in name else "🤖" if name == "robot" else "📦" if name == "object" else "🔧"
            print(f"   {i:2d}. {icon} {name}")
        
        # 检查关键物体
        print(f"\n🔍 关键物体检测:")
        
        def entity_exists(name):
            """检查实体是否存在"""
            if name in scene_entities:
                return True
            try:
                _ = scene[name]
                return True
            except (KeyError, AttributeError):
                return False
        
        checks = {
            "robot": ("机器人", True),
            "object": ("交互物体", True),
            "wall_1": ("墙 1", None),
            "wall_2": ("墙 2", None),
        }
        
        for key, (desc, expected) in checks.items():
            exists = entity_exists(key)
            if expected is True:
                status = "✅" if exists else "❌"
            elif expected is False:
                status = "❌" if exists else "✅"
            else:
                status = "✅" if exists else "⚪"
            print(f"   {status} {desc:15s} ({'存在' if exists else '不存在'})")
        
        # 分析结果
        has_walls = entity_exists("wall_1") and entity_exists("wall_2")
        
        # 尝试从motion文件推断
        try:
            motion_files = env.unwrapped.cfg.commands.motion.motion_files
            print(f"\n📄 Motion 文件:")
            for mf in motion_files[:3]:  # 只显示前3个
                print(f"   - {mf}")
            if len(motion_files) > 3:
                print(f"   ... 以及其他 {len(motion_files) - 3} 个文件")
            
            has_hframe = any("h_frame" in str(mf).lower() for mf in motion_files)
            
            print(f"\n💡 分析:")
            print(f"   - 物体类型: {'包含 h_frame' if has_hframe else '不包含 h_frame'}")
            print(f"   - 墙的状态: {'已加载' if has_walls else '未加载'}")
            
            if has_hframe and has_walls:
                print(f"   - ✅ 正确: h_frame 场景应该有墙")
            elif not has_hframe and not has_walls:
                print(f"   - ✅ 正确: 非 h_frame 场景不应该有墙")
            elif has_hframe and not has_walls:
                print(f"   - ❌ 错误: h_frame 场景应该有墙但没有")
            else:
                print(f"   - ❌ 错误: 非 h_frame 场景不应该有墙但有")
        except Exception as e:
            print(f"\n💡 分析: 场景中{'有' if has_walls else '没有'}墙")
            print(f"   (无法读取motion配置: {e})")
        
        print("\n" + "=" * 70)
        if not args_cli.headless:
            print("按 Q 或 ESC 退出".center(70))
        print("=" * 70 + "\n")
        
        return has_walls


def main():
    print("\n" + "=" * 70)
    print("测试条件场景物体加载".center(70))
    print("=" * 70)
    print(f"模式: {'Headless' if args_cli.headless else 'GUI'}")
    print("=" * 70)
    
    try:
        # 导入环境
        print("\n[INFO] 导入环境...")
        import gymnasium as gym
        import g1_hoi_learning.tasks.hoi
        
        # 读取默认配置
        print("[INFO] 加载配置...")
        from g1_hoi_learning.tasks.hoi.env_cfg import G1HoiLearningEnvCfg
        
        cfg = G1HoiLearningEnvCfg()
        
        # 减少环境数量以加快测试
        cfg.scene.num_envs = 4
        
        # 设置motion文件（使用h_frame测试）
        # cfg.commands.motion.motion_files = ["./source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/h_frame_weave.npz"]
        # cfg.commands.motion.motion_files = ["./data/datasets/Weave/rollout/train/sub17_woodchair.npz"]
        cfg.commands.motion.motion_files = ["./source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave.npz"]
        
        print("[INFO] 创建环境（这可能需要一些时间）...")
        print("[INFO] 请耐心等待...")
        
        # 重要：使用环境ID创建，这样会调用 _make_env 来正确设置物体配置
        env = gym.make("G1-Inspire-HOI-v0", cfg=cfg)
        
        print("[INFO] ✅ 环境创建成功！")
        
        # 检查场景
        tester = QuickTester()
        has_walls = tester.check_scene(env)
        
        # 运行仿真
        if args_cli.headless:
            print("[INFO] Headless模式: 运行10步后退出...")
            env.reset()
            for _ in range(10):
                action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                env.step(action)
            print("[INFO] ✅ 测试完成")
        else:
            print("[INFO] GUI模式: 仿真运行中，按 Q 或 ESC 退出...")
            step_count = 0
            env.reset()
            while simulation_app.is_running() and not tester.quit:
                action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                env.step(action)
                step_count += 1
                
                if step_count % 100 == 0:
                    print(f"[INFO] 已运行 {step_count} 步")
            
            print(f"\n[INFO] ✅ 测试完成 (共 {step_count} 步)")
        
        tester.close()
        env.close()
        
    except Exception as e:
        print(f"\n[ERROR] ❌ 测试失败:")
        print(f"{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
