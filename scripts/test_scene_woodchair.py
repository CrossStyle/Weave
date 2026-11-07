#!/usr/bin/env python
"""
最简单的测试脚本：测试条件场景物体加载（使用 woodchair）

使用方法:
    # 测试 woodchair（不应该有墙）
    python scripts/test_scene_woodchair.py --headless
    
    # GUI 模式
    python scripts/test_scene_woodchair.py

这个脚本使用 woodchair 来验证：当不是 h_frame 时，场景中不应该有墙。
"""

import argparse
import sys

import torch

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Test conditional scene without h_frame")
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
        print("场景检查报告 - woodchair 测试".center(70))
        print("=" * 70)
        
        scene = env.unwrapped.scene
        
        # 尝试获取场景实体列表
        # InteractiveScene 可能使用不同的属性名
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
            "object": ("交互物体 (woodchair)", True),
            "wall_1": ("墙 1", False),  # 不应该存在
            "wall_2": ("墙 2", False),  # 不应该存在
        }
        
        all_correct = True
        for key, (desc, should_exist) in checks.items():
            exists = entity_exists(key)
            if should_exist and exists:
                status = "✅"
            elif not should_exist and not exists:
                status = "✅"
            else:
                status = "❌"
                all_correct = False
            
            print(f"   {status} {desc:30s} ({'存在' if exists else '不存在'}) - {'符合预期' if (should_exist == exists) else '不符合预期!'}")
        
        # 分析结果
        has_walls = entity_exists("wall_1") or entity_exists("wall_2")
        
        print(f"\n💡 测试结果:")
        print(f"   - 测试物体: woodchair")
        print(f"   - 预期: 不应该有墙")
        print(f"   - 实际: {'有墙' if has_walls else '没有墙'}")
        
        if not has_walls:
            print(f"   - ✅ 测试通过: woodchair 场景正确地没有加载墙")
        else:
            print(f"   - ❌ 测试失败: woodchair 场景不应该有墙但却有")
        
        print("\n" + "=" * 70)
        if not args_cli.headless:
            print("按 Q 或 ESC 退出".center(70))
        print("=" * 70 + "\n")
        
        return all_correct


def main():
    print("\n" + "=" * 70)
    print("测试条件场景物体加载 - woodchair 测试".center(70))
    print("=" * 70)
    print(f"模式: {'Headless' if args_cli.headless else 'GUI'}")
    print("预期: woodchair 场景不应该有墙")
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
        
        # 使用 woodchair（应该不会有墙）
        cfg.commands.motion.motion_files = ["./data/datasets/Weave/rollout/train/sub17_woodchair.npz"]
        
        print("[INFO] 创建环境（这可能需要一些时间）...")
        print("[INFO] 请耐心等待...")
        
        # 创建环境
        env = gym.make("G1-Inspire-HOI-v0", cfg=cfg)
        
        print("[INFO] ✅ 环境创建成功！")
        
        # 检查场景
        tester = QuickTester()
        test_passed = tester.check_scene(env)
        
        # 运行仿真
        if args_cli.headless:
            print("[INFO] Headless模式: 运行10步后退出...")
            env.reset()
            for _ in range(10):
                action = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                env.step(action)
            print(f"\n[INFO] {'✅ 测试完成 - 所有检查通过' if test_passed else '❌ 测试完成 - 有检查失败'}")
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
            
            print(f"\n[INFO] {'✅ 测试完成 - 所有检查通过' if test_passed else '❌ 测试完成 - 有检查失败'} (共 {step_count} 步)")
        
        tester.close()
        env.close()
        
        # 返回适当的退出码
        sys.exit(0 if test_passed else 1)
        
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
