# STL转USD完整指南

本指南说明如何将STL mesh文件转换为Isaac Sim所需的USD格式。

## 🎯 快速方法对比

| 方法 | 难度 | 质量 | 推荐度 | 说明 |
|------|------|------|--------|------|
| **Blender** | ⭐ | ⭐⭐⭐⭐⭐ | 🔥🔥🔥 | 最简单，质量最好 |
| **Isaac Sim** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 🔥🔥 | 最准确，但需要GUI |
| **脚本自动化** | ⭐⭐⭐ | ⭐⭐⭐⭐ | 🔥 | 适合批量处理 |

## 方法1: 使用Blender (推荐)

### 为什么选择Blender？
- ✅ 免费开源
- ✅ 支持USD导出（3.0+版本）
- ✅ 可视化编辑
- ✅ 质量可控
- ✅ 支持材质、碰撞体等高级设置

### 步骤

#### 1. 安装Blender
```bash
# 下载Blender 3.0或更高版本
# https://www.blender.org/download/
```

#### 2. 导入STL
```
1. 打开Blender
2. File → Import → STL (.stl)
3. 选择你的STL文件
4. Import STL
```

#### 3. 检查和清理mesh
```
1. 选中导入的对象
2. Object Mode → Edit Mode (Tab键)
3. 清理操作 (可选):
   - Mesh → Clean Up → Delete Loose (删除孤立点)
   - Mesh → Normals → Recalculate Outside (重算法向)
   - 检查: Overlays → Face Orientation (红色=内部，蓝色=外部)
```

#### 4. 设置单位和缩放
```
1. Scene Properties → Units
   - Unit System: Metric
   - Length: Meters
   
2. 如果STL是mm或cm单位，需要缩放:
   - 选中对象
   - Object Properties → Transform → Scale
   - mm → m: 输入 0.001
   - cm → m: 输入 0.01
   
3. 应用缩放:
   - Object → Apply → Scale (Ctrl+A → Scale)
```

#### 5. 设置原点和旋转
```
1. 设置原点到底部中心:
   - Object → Set Origin → Origin to Geometry
   - 或手动调整: Object → Set Origin → 3D Cursor
   
2. 如果需要旋转 (例如Y-up转Z-up):
   - Rotate X: 90度
   - Object → Apply → Rotation
```

#### 6. 添加材质 (可选)
```
1. 切换到Shading工作区
2. 添加材质:
   - Material Properties → New
   - 调整Base Color、Roughness等
```

#### 7. 导出为USD
```
1. File → Export → Universal Scene Description (.usd/.usdc)

2. 导出设置:
   ✅ Selection Only (如果只导出选中对象)
   ✅ Visible Only
   
   Materials:
   ✅ Export Materials
   
   Format:
   - ASCII (.usda): 可读，文件大
   - Binary (.usdc): 压缩，文件小 (推荐)
   - Package (.usdz): 打包，包含纹理
   
3. 保存到: your_object.usd
```

### 批量处理脚本 (Blender Python)

如果有多个STL需要转换，可以使用Blender脚本：

```python
# blender_batch_convert.py
import bpy
import sys
from pathlib import Path

def convert_stl_to_usd(stl_path, usd_path, scale=1.0):
    """转换单个STL到USD"""
    
    # 清空场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # 导入STL
    bpy.ops.import_mesh.stl(filepath=str(stl_path))
    
    # 获取导入的对象
    obj = bpy.context.selected_objects[0]
    
    # 应用缩放
    if scale != 1.0:
        obj.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(scale=True)
    
    # 设置原点
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    
    # 重算法向
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.normals_recalculate(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 添加简单材质
    mat = bpy.data.materials.new(name="Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = (0.85, 0.45, 0.20, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.6
    
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    
    # 导出USD
    bpy.ops.wm.usd_export(
        filepath=str(usd_path),
        selected_objects_only=True,
        export_materials=True
    )
    
    print(f"✅ 转换完成: {usd_path}")

# 使用示例
if __name__ == "__main__":
    stl_files = Path("./stl_files").glob("*.stl")
    
    for stl_path in stl_files:
        usd_path = Path("./usd_files") / stl_path.with_suffix('.usd').name
        usd_path.parent.mkdir(exist_ok=True)
        
        convert_stl_to_usd(stl_path, usd_path, scale=0.001)  # mm to m

# 运行方式:
# blender --background --python blender_batch_convert.py
```

## 方法2: 使用Isaac Sim

### 步骤

#### 1. 启动Isaac Sim
```bash
cd <isaac-sim-path>
./isaac-sim.sh
```

#### 2. 导入STL
```
1. File → Import
2. 选择文件类型: STL或OBJ
3. 选择你的mesh文件
4. Import
```

#### 3. 添加物理属性
```
1. 选中导入的对象
2. 右侧Property面板:
   
   Add → Physics → Rigid Body
   - Mass: 10.0 (kg)
   - 其他默认
   
   Add → Physics → Collision Shape
   - Shape Type: Mesh 或 Convex Hull
   - Approximation: Mesh Simplification
```

#### 4. 设置材质
```
1. Material Properties
2. Create → OmniPBR
3. 调整颜色、粗糙度等
```

#### 5. 导出USD
```
1. File → Export
2. 选择导出格式: USD (.usd)
3. 保存路径: your_object.usd
```

## 方法3: 使用Python脚本（自动化）

我已经为你创建了转换脚本，有两种使用方式：

### 选项A: 使用Isaac Sim的Python (完整功能)

```bash
# 使用Isaac Sim内置的Python解释器
<isaac-sim-path>/python.sh scripts/convert_mesh_to_usd.py \
    --input your_model.stl \
    --output your_model.usd \
    --scale 0.001 \
    --mass 10.0
```

### 选项B: 使用系统Python (需要安装pxr)

```bash
# 安装USD Python库
pip install usd-core

# 运行转换
python scripts/convert_mesh_to_usd.py \
    --input your_model.stl \
    --output your_model.usd \
    --scale 0.001 \
    --mass 10.0
```

### 选项C: 先转OBJ，再手动转USD

```bash
# 如果没有pxr，脚本会自动生成OBJ
python scripts/convert_mesh_to_usd.py \
    --input your_model.stl \
    --output your_model.usd \
    --use-obj-fallback

# 然后使用Blender或Isaac Sim导入OBJ，导出USD
```

### 脚本参数说明

```bash
python scripts/convert_mesh_to_usd.py \
    --input model.stl \          # 输入文件
    --output model.usd \         # 输出文件
    --scale 0.001 \              # 缩放 (mm→m用0.001)
    --up-axis Z \                # 向上轴 (Y或Z)
    --mass 10.0 \                # 质量 (kg)
    --color 0.85 0.45 0.20 \     # RGB颜色
    --no-collision               # 不添加碰撞体 (可选)
```

## 🔧 常见问题

### Q1: STL单位是mm/cm，如何转换？

**缩放因子:**
- mm → m: `--scale 0.001`
- cm → m: `--scale 0.01`
- inch → m: `--scale 0.0254`

**在Blender中:**
1. 导入STL后
2. 选中对象 → Object Properties → Scale
3. 输入缩放因子
4. Object → Apply → Scale

### Q2: USD文件太大怎么办？

**解决方法:**
1. 使用压缩格式:
   - `.usdc` (binary) 而不是 `.usda` (ASCII)
   
2. 简化mesh:
   - Blender: Modifiers → Decimate → Ratio 0.5
   - 减少面数但保持形状
   
3. 使用凸包碰撞:
   - 物理精度稍差，但文件小很多

### Q3: Mesh的向上轴不对？

**诊断:**
- STL的Z轴向上 → Isaac Sim的Z轴向上 ✅
- STL的Y轴向上 → Isaac Sim的Z轴向上 ❌ 需要旋转

**修复方法 (Blender):**
```
1. 旋转90度: R (rotate) → X → 90
2. 应用旋转: Object → Apply → Rotation
```

**修复方法 (代码):**
```python
import trimesh
mesh = trimesh.load('model.stl')
# Y-up to Z-up
mesh.apply_transform(trimesh.transformations.rotation_matrix(
    np.radians(90), [1, 0, 0]
))
mesh.export('model_fixed.stl')
```

### Q4: 碰撞体不准确？

**选择合适的碰撞近似:**

| 方法 | 精度 | 性能 | 适用场景 |
|------|------|------|----------|
| **Mesh** | ⭐⭐⭐⭐⭐ | ⭐⭐ | 复杂形状、静态物体 |
| **Convex Hull** | ⭐⭐⭐ | ⭐⭐⭐⭐ | 凸形物体 |
| **Bounding Box** | ⭐ | ⭐⭐⭐⭐⭐ | 简单立方体 |

**在Isaac Sim中设置:**
```
Physics → Collision Shape
- Shape Type: Mesh / Convex Hull / Box
- Approximation: 选择合适的方法
```

### Q5: 如何验证USD是否正确？

**验证步骤:**
```bash
# 1. 在Isaac Sim中打开
# 检查: 可视化、碰撞体、质量

# 2. 使用usdview (如果安装了USD)
usdview your_model.usd

# 3. 检查USD内容
usdcat your_model.usd | head -50
```

**关键检查项:**
- ✅ Mesh显示正常
- ✅ 尺寸合理（单位是米）
- ✅ 原点位置正确
- ✅ 碰撞体存在
- ✅ 质量和刚体属性设置

## 📋 完整工作流程

### 准备单个物体

```bash
# 1. 转换STL到USD
python scripts/convert_mesh_to_usd.py \
    --input my_object.stl \
    --output my_object.usd \
    --scale 0.001 \
    --mass 10.0

# 2. 生成surface和SDF数据
python scripts/generate_object_data.py \
    --mesh my_object.stl \
    --output ./object_data \
    --name my_object

# 如果需要调整scale，也应用到STL:
# python -c "import trimesh; m=trimesh.load('my_object.stl'); m.apply_scale(0.001); m.export('my_object_scaled.stl')"
# python scripts/generate_object_data.py --mesh my_object_scaled.stl ...

# 3. 验证数据
python scripts/validate_object_data.py \
    --object my_object \
    --objects-dir ./object_data \
    --visualize

# 4. 组织文件
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/my_object
cp my_object.usd source/g1_hoi_learning/g1_hoi_learning/objects/my_object/
cp object_data/surface.npy source/g1_hoi_learning/g1_hoi_learning/objects/my_object/
cp object_data/sdf_128.npz source/g1_hoi_learning/g1_hoi_learning/objects/my_object/

# 5. 注册物体 (手动编辑)
# - objects/__init__.py: 添加USD路径
# - objects/object_cfg.py: 添加物体配置
```

### 批量处理

```bash
#!/bin/bash

# 批量转换脚本
OBJECTS=("chair1" "table1" "box1")
SCALE=0.001  # mm to m

for obj in "${OBJECTS[@]}"; do
    echo "处理: $obj"
    
    # 转换USD
    python scripts/convert_mesh_to_usd.py \
        --input stl_files/${obj}.stl \
        --output objects/${obj}/${obj}.usd \
        --scale $SCALE
    
    # 生成数据
    python scripts/generate_object_data.py \
        --mesh stl_files/${obj}.stl \
        --output objects/${obj} \
        --name ${obj}
    
    # 验证
    python scripts/validate_object_data.py \
        --object ${obj} \
        --objects-dir objects \
        --save-plots validation_plots
done
```

## 💡 最佳实践

1. **使用Blender进行首次转换** - 可视化检查最可靠
2. **保持一致的缩放** - USD、surface.npy、sdf_128.npz都用相同的scale
3. **验证物理属性** - 在Isaac Sim中测试物体掉落、碰撞
4. **保存原始文件** - 保留原始STL，便于后续调整
5. **文档化单位** - 记录每个物体的原始单位和缩放因子

## 🔗 相关资源

- **Blender**: https://www.blender.org/
- **Isaac Sim文档**: https://docs.omniverse.nvidia.com/isaacsim/
- **USD文档**: https://graphics.pixar.com/usd/docs/index.html
- **trimesh**: https://trimsh.org/

## 📝 检查清单

转换完成后，确认：
- [ ] USD文件可以在Isaac Sim中打开
- [ ] 尺寸正确（单位为米）
- [ ] 原点位置合理
- [ ] 碰撞体正常工作
- [ ] 质量和物理属性合理
- [ ] surface.npy和sdf_128.npz已生成
- [ ] 所有文件scale一致
- [ ] 在objects/__init__.py中注册
- [ ] 在objects/object_cfg.py中配置

完成这些步骤后，你的物体就可以在Weave中使用了！🎉
