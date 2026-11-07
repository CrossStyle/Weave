#!/usr/bin/env python3
"""
快速检查 USD 文件的刚体结构（无需 GUI）
使用 IsaacLab 的 conda 环境运行：
    python quick_check_usd.py
"""

import sys
import os

# 确保导入 IsaacLab
sys.path.insert(0, "d:/code/robot/isaaclab/isaaclab-2.3.0/source")

from omni.isaac.lab.app import AppLauncher

# 无界面模式启动
app_launcher = AppLauncher({"headless": True})
simulation_app = app_launcher.app

from pxr import Usd, UsdPhysics

def quick_check(usd_path: str) -> dict:
    """快速检查 USD 文件"""
    result = {
        "path": usd_path,
        "exists": os.path.exists(usd_path),
        "can_open": False,
        "num_rigid_bodies": 0,
        "num_collisions": 0,
        "rigid_body_paths": [],
        "has_physics": False
    }
    
    if not result["exists"]:
        return result
    
    try:
        stage = Usd.Stage.Open(usd_path)
        if stage:
            result["can_open"] = True
            
            for prim in stage.Traverse():
                if UsdPhysics.RigidBodyAPI(prim):
                    result["num_rigid_bodies"] += 1
                    result["rigid_body_paths"].append(str(prim.GetPath()))
                    result["has_physics"] = True
                
                if UsdPhysics.CollisionAPI(prim):
                    result["num_collisions"] += 1
    except Exception as e:
        result["error"] = str(e)
    
    return result

if __name__ == "__main__":
    print("检查 USD 文件的刚体结构...")
    print("=" * 80)
    
    files = [
        "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_collision.usd",
        "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder.usd",
        "source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/hframe_collision.usd",
    ]
    
    results = []
    for f in files:
        print(f"\n检查: {f}")
        result = quick_check(f)
        results.append(result)
        
        if not result["exists"]:
            print("  ❌ 文件不存在")
        elif not result["can_open"]:
            print("  ❌ 无法打开文件")
        elif "error" in result:
            print(f"  ❌ 错误: {result['error']}")
        else:
            print(f"  ✓ 文件正常打开")
            print(f"  刚体数量: {result['num_rigid_bodies']}")
            print(f"  碰撞体数量: {result['num_collisions']}")
            
            if result["num_rigid_bodies"] == 0:
                print("  ⚠️  警告: 没有刚体！这会导致 ContactSensor 错误")
            else:
                print(f"  刚体路径:")
                for path in result["rigid_body_paths"]:
                    print(f"    - {path}")
    
    print("\n" + "=" * 80)
    print("总结:")
    print("=" * 80)
    
    for r in results:
        name = os.path.basename(r["path"])
        status = "✓" if r["num_rigid_bodies"] > 0 else "❌"
        print(f"{status} {name}: {r['num_rigid_bodies']} 个刚体")
    
    # 找出问题文件
    problem_files = [r for r in results if r["can_open"] and r["num_rigid_bodies"] == 0]
    if problem_files:
        print("\n⚠️  以下文件没有刚体，会导致 ContactSensor 错误:")
        for r in problem_files:
            print(f"  - {os.path.basename(r['path'])}")
    
    simulation_app.close()
