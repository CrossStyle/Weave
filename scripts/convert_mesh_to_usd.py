"""
将mesh文件（STL/OBJ等）转换为USD格式

USD是Universal Scene Description格式，Isaac Sim使用它来表示3D场景和资产。

依赖:
    pip install trimesh pxr

用法:
    python scripts/convert_mesh_to_usd.py --input model.stl --output model.usd
    python scripts/convert_mesh_to_usd.py --input model.obj --output model.usd --scale 0.01
"""

import argparse
from pathlib import Path

import numpy as np
import trimesh


def convert_mesh_to_usd(
    input_path: Path,
    output_path: Path,
    scale: float = 1.0,
    up_axis: str = "Z",
    apply_collision: bool = True,
    material_color: tuple = (0.85, 0.45, 0.20),
    mass: float = 10.0,
) -> bool:
    """
    将mesh文件转换为USD格式
    
    Args:
        input_path: 输入mesh文件路径 (.stl, .obj, .ply等)
        output_path: 输出USD文件路径
        scale: 缩放因子（例如0.001将mm转为m）
        up_axis: 向上轴 ("Y" 或 "Z")
        apply_collision: 是否添加碰撞体
        material_color: 材质颜色 (r, g, b)
        mass: 质量（kg）
    
    Returns:
        是否成功
    """
    try:
        from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Gf, Vt
    except ImportError:
        print("错误: 需要安装 pxr (USD Python库)")
        print("\n方法1 - 使用Isaac Sim的Python:")
        print("  使用Isaac Sim自带的Python解释器运行此脚本")
        print("\n方法2 - 安装usd-core:")
        print("  pip install usd-core")
        print("\n方法3 - 使用Blender USD导出:")
        print("  在Blender中导入mesh，然后导出为USD")
        return False
    
    print(f"\n{'='*60}")
    print(f"转换mesh到USD")
    print(f"{'='*60}")
    print(f"输入: {input_path}")
    print(f"输出: {output_path}")
    print(f"缩放: {scale}")
    print(f"向上轴: {up_axis}")
    
    # 加载mesh
    print(f"\n加载mesh...")
    mesh = trimesh.load(input_path, force='mesh')
    
    if isinstance(mesh, trimesh.Scene):
        print("检测到Scene，合并所有mesh...")
        mesh = trimesh.util.concatenate(
            [geom for geom in mesh.geometry.values() 
             if isinstance(geom, trimesh.Trimesh)]
        )
    
    print(f"Mesh信息:")
    print(f"  - 顶点数: {len(mesh.vertices)}")
    print(f"  - 面数: {len(mesh.faces)}")
    print(f"  - 边界: {mesh.bounds}")
    print(f"  - 是否闭合: {mesh.is_watertight}")
    
    if not mesh.is_watertight:
        print("⚠️  警告: Mesh不是水密的，物理模拟可能不稳定")
    
    # 应用缩放
    if scale != 1.0:
        print(f"\n应用缩放: {scale}")
        mesh.apply_scale(scale)
    
    # 创建USD stage
    print(f"\n创建USD stage...")
    stage = Usd.Stage.CreateNew(str(output_path))
    
    # 设置stage元数据
    UsdGeom.SetStageUpAxis(stage, up_axis)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    
    # 创建根Xform
    root_prim_path = f"/{output_path.stem}"
    root_xform = UsdGeom.Xform.Define(stage, root_prim_path)
    
    # 设置为默认prim（重要！）
    stage.SetDefaultPrim(root_xform.GetPrim())
    
    # 创建mesh geometry
    mesh_prim_path = f"{root_prim_path}/mesh"
    usd_mesh = UsdGeom.Mesh.Define(stage, mesh_prim_path)
    
    # 设置顶点
    vertices = mesh.vertices.astype(np.float32)
    usd_mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(vertices))
    
    # 设置面（需要展平索引）
    face_vertex_counts = [3] * len(mesh.faces)  # 都是三角形
    face_vertex_indices = mesh.faces.flatten().tolist()
    usd_mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
    usd_mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)
    
    # 设置法向量
    if mesh.vertex_normals is not None:
        normals = mesh.vertex_normals.astype(np.float32)
        usd_mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals))
        usd_mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    
    # 创建材质
    print(f"创建材质...")
    material_path = f"{root_prim_path}/Looks/Material"
    material = UsdShade.Material.Define(stage, material_path)
    
    # 创建PreviewSurface shader
    shader_path = f"{material_path}/PreviewSurface"
    shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("UsdPreviewSurface")
    
    # 设置材质属性
    shader.CreateInput("diffuseColor", Gf.Vec3f(*material_color))
    shader.CreateInput("roughness", 0.6)
    shader.CreateInput("metallic", 0.0)
    
    # 连接shader输出到material
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    
    # 绑定材质到mesh
    UsdShade.MaterialBindingAPI(usd_mesh).Bind(material)
    
    # 添加碰撞体
    if apply_collision:
        print(f"添加碰撞体...")
        
        # 方法1: 使用原始mesh作为碰撞体（精确但计算量大）
        collision_prim = usd_mesh.GetPrim()
        UsdPhysics.CollisionAPI.Apply(collision_prim)
        UsdPhysics.MeshCollisionAPI.Apply(collision_prim)
        
        # 设置碰撞近似为"none"表示使用精确mesh
        mesh_collision = UsdPhysics.MeshCollisionAPI(collision_prim)
        mesh_collision.CreateApproximationAttr("meshSimplification")
        
        # 可选: 使用凸包近似（更快但不精确）
        # mesh_collision.CreateApproximationAttr("convexHull")
        
        # 添加刚体属性到根节点
        rigid_body_api = UsdPhysics.RigidBodyAPI.Apply(root_xform.GetPrim())
        
        # 设置质量
        mass_api = UsdPhysics.MassAPI.Apply(root_xform.GetPrim())
        mass_api.CreateMassAttr(mass)
    
    # 保存
    print(f"\n保存USD文件...")
    stage.GetRootLayer().Save()
    
    print(f"\n✅ 转换成功!")
    print(f"输出文件: {output_path}")
    print(f"文件大小: {output_path.stat().st_size / 1024:.2f} KB")
    
    return True


def convert_with_intermediate_obj(
    input_path: Path,
    output_path: Path,
    scale: float = 1.0,
    **kwargs
) -> bool:
    """
    使用中间OBJ文件的转换方法（备选方案）
    
    当pxr不可用时，先转为OBJ，然后提示用户使用其他工具转换
    """
    print(f"\n{'='*60}")
    print(f"使用备选方案: 先转换为OBJ")
    print(f"{'='*60}")
    
    # 加载mesh
    print(f"加载mesh: {input_path}")
    mesh = trimesh.load(input_path, force='mesh')
    
    if isinstance(mesh, trimesh.Scene):
        print("合并Scene中的所有mesh...")
        mesh = trimesh.util.concatenate(
            [geom for geom in mesh.geometry.values() 
             if isinstance(geom, trimesh.Trimesh)]
        )
    
    # 应用缩放
    if scale != 1.0:
        print(f"应用缩放: {scale}")
        mesh.apply_scale(scale)
    
    # 导出为OBJ
    obj_path = output_path.with_suffix('.obj')
    print(f"\n导出为OBJ: {obj_path}")
    mesh.export(obj_path)
    
    print(f"\n✅ OBJ文件已生成: {obj_path}")
    print(f"\n现在需要将OBJ转换为USD，请选择以下方法之一:")
    print(f"\n方法1 - 使用Isaac Sim:")
    print(f"  1. 启动Isaac Sim")
    print(f"  2. File → Import → 选择 {obj_path}")
    print(f"  3. File → Export → 另存为 {output_path}")
    
    print(f"\n方法2 - 使用Blender (推荐):")
    print(f"  1. 打开Blender")
    print(f"  2. File → Import → Wavefront (.obj) → 选择 {obj_path}")
    print(f"  3. File → Export → Universal Scene Description (.usd/.usdc)")
    print(f"  4. 选择输出路径 {output_path}")
    
    print(f"\n方法3 - 使用usd_from_gltf:")
    print(f"  pip install usd-core")
    print(f"  # 先转为GLTF，再用usd工具转换")
    
    print(f"\n方法4 - 使用此脚本 (需要安装pxr):")
    print(f"  # 在Isaac Sim的Python环境中运行:")
    print(f"  <isaac-sim>/python.sh scripts/convert_mesh_to_usd.py --input {obj_path} --output {output_path}")
    
    return False


def main():
    parser = argparse.ArgumentParser(description="将mesh转换为USD格式")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="输入mesh文件路径 (.stl, .obj, .ply等)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="输出USD文件路径 (.usd或.usdc)"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="缩放因子 (例如: 0.001将mm转为m, 0.01将cm转为m)"
    )
    parser.add_argument(
        "--up-axis",
        type=str,
        default="Z",
        choices=["Y", "Z"],
        help="向上轴方向"
    )
    parser.add_argument(
        "--no-collision",
        action="store_true",
        help="不添加碰撞体"
    )
    parser.add_argument(
        "--color",
        type=float,
        nargs=3,
        default=[0.85, 0.45, 0.20],
        metavar=("R", "G", "B"),
        help="材质颜色 RGB (0-1范围)"
    )
    parser.add_argument(
        "--mass",
        type=float,
        default=10.0,
        help="刚体质量 (kg)"
    )
    parser.add_argument(
        "--use-obj-fallback",
        action="store_true",
        help="强制使用OBJ中间文件方案"
    )
    
    args = parser.parse_args()
    
    # 路径检查
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 输入文件不存在: {input_path}")
        return
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 尝试导入pxr
    try:
        import pxr
        has_pxr = True
    except ImportError:
        has_pxr = False
    
    # 选择转换方法
    if args.use_obj_fallback or not has_pxr:
        if not has_pxr:
            print("⚠️  未检测到pxr库，使用备选方案")
        convert_with_intermediate_obj(
            input_path,
            output_path,
            scale=args.scale,
        )
    else:
        success = convert_mesh_to_usd(
            input_path,
            output_path,
            scale=args.scale,
            up_axis=args.up_axis,
            apply_collision=not args.no_collision,
            material_color=tuple(args.color),
            mass=args.mass,
        )
        
        if success:
            print(f"\n{'='*60}")
            print("后续步骤:")
            print(f"{'='*60}")
            print("1. 在Isaac Sim中验证USD文件:")
            print(f"   - 打开Isaac Sim")
            print(f"   - File → Open → 选择 {output_path}")
            print(f"   - 检查mesh显示和碰撞体是否正确")
            print("\n2. 如需调整:")
            print(f"   - 缩放: 重新运行脚本并调整 --scale 参数")
            print(f"   - 材质: 使用 --color 参数")
            print(f"   - 质量: 使用 --mass 参数")


if __name__ == "__main__":
    main()
