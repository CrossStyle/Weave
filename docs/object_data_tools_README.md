# 物体数据准备工具

为Weave准备自定义物体数据的完整工具集。

## 🎯 快速开始

### 0. 准备mesh文件

如果你只有STL文件，需要先转换为USD：

```bash
# 方法1: 使用Blender (推荐) - 见详细指南
# 方法2: 使用脚本
python scripts/convert_mesh_to_usd.py \
    --input your_object.stl \
    --output your_object.usd \
    --scale 0.001  # mm to m
```

详见: [`docs/stl_to_usd_guide_zh.md`](stl_to_usd_guide_zh.md)

### 1. 生成物体数据

```bash
# 从mesh文件生成surface.npy和sdf_128.npz
python scripts/generate_object_data.py \
    --mesh path/to/your_object.obj \
    --output path/to/output_dir \
    --name your_object
```

### 2. 验证生成的数据

```bash
# 验证数据格式
python scripts/validate_object_data.py --object your_object

# 验证并可视化
python scripts/validate_object_data.py --object your_object --visualize

# 保存可视化图表
python scripts/validate_object_data.py --object your_object --save-plots ./outputs
```

### 3. 验证现有物体数据

```bash
# 检查项目中现有的物体数据
python scripts/validate_object_data.py --object woodchair --visualize
python scripts/validate_object_data.py --object whitechair --visualize
```

## 📁 文件说明

### 工具脚本

- **`scripts/convert_mesh_to_usd.py`** - 将STL/OBJ等格式转换为USD
  - 支持多种mesh格式输入
  - 自动设置物理属性和碰撞体
  - 可配置缩放、质量、材质

- **`scripts/generate_object_data.py`** - 从3D mesh生成surface.npy和sdf_128.npz
  - 支持多种mesh格式 (.obj, .stl, .ply等)
  - 可配置采样点数、SDF分辨率、网格边界
  - 自动计算元数据和哈希值

- **`scripts/validate_object_data.py`** - 验证和可视化物体数据
  - 检查数据格式和完整性
  - 生成统计信息
  - 可视化表面点和SDF切片

### 文档

- **`docs/stl_to_usd_guide_zh.md`** - STL转USD完整指南
  - 三种方法对比（Blender、Isaac Sim、脚本）
  - 详细步骤说明
  - 批量处理示例
  - 常见问题解答

- **`docs/prepare_object_data_zh.md`** - 完整的中文指南
  - 数据格式详解
  - 生成步骤说明
  - 常见问题解答
  - 高级选项和技巧

## 🔧 安装依赖

生成工具需要额外的依赖：

```bash
pip install trimesh mesh-to-sdf
```

可视化工具需要：

```bash
pip install matplotlib
```

## 📊 数据格式

### surface.npy
- **Shape**: `(N, 3)` - 通常N=512
- **Dtype**: `float32`
- **内容**: 物体表面的均匀采样点

### sdf_128.npz
- **主要字段**:
  - `sdf`: `(128, 128, 128)` - SDF网格
  - `center`: `(3,)` - 物体中心
  - `radius`: `()` - 包围半径
  - `grid_bound`: `()` - 网格边界
  - `resolution`: `()` - 分辨率
  - `object_name`: `()` - 物体名称
- **可选元数据**: mesh_sha256, surface_sha256等

## 🎨 使用示例

### 示例1: 为新物体生成数据

```bash
# 准备mesh文件
# my_chair.obj

# 生成数据
python scripts/generate_object_data.py \
    --mesh my_chair.obj \
    --output ./my_chair_data \
    --name my_chair \
    --num-surface-samples 512 \
    --sdf-resolution 128

# 验证输出
python scripts/validate_object_data.py \
    --object my_chair \
    --objects-dir ./my_chair_data \
    --visualize
```

### 示例2: 批量处理多个物体

```bash
#!/bin/bash

objects=("chair1" "table1" "box1")

for obj in "${objects[@]}"; do
    echo "处理 $obj..."
    python scripts/generate_object_data.py \
        --mesh meshes/${obj}.obj \
        --output objects_data/${obj} \
        --name ${obj}
    
    python scripts/validate_object_data.py \
        --object ${obj} \
        --objects-dir objects_data \
        --save-plots validation_plots
done
```

### 示例3: 自定义参数

```bash
# 高分辨率SDF (用于复杂形状)
python scripts/generate_object_data.py \
    --mesh complex_object.obj \
    --output ./output \
    --sdf-resolution 256 \
    --grid-bound 2.0

# 更多表面采样点
python scripts/generate_object_data.py \
    --mesh detailed_object.obj \
    --output ./output \
    --num-surface-samples 1024
```

## 🔍 验证检查项

验证脚本会检查：

✅ 文件是否存在  
✅ 数据格式是否正确 (shape, dtype)  
✅ 必需字段是否完整  
✅ 数值范围是否合理  
✅ SDF内外部体素分布  
✅ 分辨率与shape的一致性  

## ⚠️ 常见问题

### mesh不是水密的
- 使用MeshLab修复: Filters → Cleaning and Repairing → Close Holes
- 或使用PyMesh: `pymesh.remove_isolated_vertices()`, `pymesh.remove_duplicated_vertices()`

### SDF生成太慢
- 降低分辨率: `--sdf-resolution 64`
- 简化mesh (减少面数)
- 考虑使用C++版本的SDFGen

### 表面采样不均匀
- 使用更高质量的mesh
- 增加采样点数
- 检查mesh面积权重

### 内存不足
- 降低SDF分辨率
- 分批处理多个物体
- 使用64位Python

## 📚 进一步阅读

详细信息请参考：
- **完整指南**: `docs/prepare_object_data_zh.md`
- **代码示例**: `source/g1_hoi_learning/g1_hoi_learning/objects/`
- **使用代码**: `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/mdp/geometry.py`

## 🤝 贡献

欢迎改进这些工具！如果你有更好的SDF生成方法或其他建议，请提交PR。

## 📝 许可

与主项目相同的许可证。
