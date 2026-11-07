"""
在 IsaacSim 中检查 ladder USD 文件的刚体结构
运行方式：使用 IsaacSim 的 Python 环境运行
"""

from omni.isaac.lab.app import AppLauncher

# 启动 IsaacSim
app_launcher = AppLauncher({"headless": False})  # headless=False 显示 GUI
simulation_app = app_launcher.app

from pxr import Usd, UsdGeom, UsdPhysics
import omni.usd
import carb

def inspect_usd_file(usd_path: str):
    """检查 USD 文件的刚体结构"""
    
    print("=" * 80)
    print(f"检查文件: {usd_path}")
    print("=" * 80)
    
    # 打开 USD stage
    stage = Usd.Stage.Open(usd_path)
    if not stage:
        print(f"❌ 无法打开文件: {usd_path}")
        return
    
    print(f"✓ 成功打开 USD 文件\n")
    
    # 统计信息
    total_prims = 0
    rigid_bodies = []
    collision_prims = []
    meshes = []
    
    print("Prim 层级结构:")
    print("-" * 80)
    
    for prim in stage.Traverse():
        total_prims += 1
        indent = "  " * (len(prim.GetPath().pathString.split('/')) - 2)
        prim_type = prim.GetTypeName()
        
        # 基本信息
        info_parts = [f"{prim.GetPath()}"]
        if prim_type:
            info_parts.append(f"[{prim_type}]")
        
        # 检查是否是刚体
        if UsdPhysics.RigidBodyAPI(prim):
            info_parts.append("🔵 RigidBody")
            rigid_bodies.append(prim)
            
            # 检查刚体属性
            rigid_api = UsdPhysics.RigidBodyAPI(prim)
            if rigid_api.GetKinematicEnabledAttr().Get():
                info_parts.append("(Kinematic)")
        
        # 检查是否有碰撞
        if UsdPhysics.CollisionAPI(prim):
            info_parts.append("🟢 Collision")
            collision_prims.append(prim)
        
        # 检查是否是 Mesh
        if UsdGeom.Mesh(prim):
            info_parts.append("📐 Mesh")
            meshes.append(prim)
        
        print(f"{indent}{' '.join(info_parts)}")
    
    # 汇总报告
    print("\n" + "=" * 80)
    print("汇总报告:")
    print("=" * 80)
    print(f"总 Prim 数量: {total_prims}")
    print(f"Mesh 数量: {len(meshes)}")
    print(f"碰撞体数量: {len(collision_prims)}")
    print(f"刚体数量: {len(rigid_bodies)} {'❌ 问题：没有刚体！' if len(rigid_bodies) == 0 else '✓'}")
    
    if len(rigid_bodies) > 0:
        print("\n刚体详细信息:")
        for i, rb in enumerate(rigid_bodies, 1):
            print(f"\n  {i}. {rb.GetPath()}")
            rigid_api = UsdPhysics.RigidBodyAPI(rb)
            
            # 获取质量
            mass_api = UsdPhysics.MassAPI(rb)
            if mass_api:
                mass = mass_api.GetMassAttr().Get()
                print(f"     质量: {mass}")
            
            # 检查是否是运动学
            kinematic = rigid_api.GetKinematicEnabledAttr().Get()
            print(f"     运动学模式: {kinematic}")
    
    if len(collision_prims) > 0:
        print(f"\n碰撞体路径:")
        for col in collision_prims[:10]:  # 只显示前10个
            print(f"  - {col.GetPath()}")
        if len(collision_prims) > 10:
            print(f"  ... 还有 {len(collision_prims) - 10} 个")
    
    print("\n" + "=" * 80)
    if len(rigid_bodies) == 0:
        print("⚠️  警告：此 USD 文件没有刚体！")
        print("   ContactSensor 需要至少一个刚体才能工作。")
        print("\n建议：")
        print("   1. 在 USD 文件中添加 RigidBodyAPI")
        print("   2. 或者使用包含刚体的其他 USD 文件")
    else:
        print("✓ 此 USD 文件包含刚体，应该可以与 ContactSensor 一起使用")
    print("=" * 80)


if __name__ == "__main__":
    # 检查两个文件
    files_to_check = [
        "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_collision.usd",
        "source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder.usd",
        "source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/hframe_collision.usd",
    ]
    
    for usd_file in files_to_check:
        try:
            inspect_usd_file(usd_file)
            print("\n\n")
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n按 Enter 关闭...")
    input()
    simulation_app.close()
