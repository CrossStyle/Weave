# 为Weave准备自定义物体数据

本指南说明如何为自己的motion data准备对应的object data，特别是 `surface.npy` 和 `sdf_128.npz` 文件。

## 📋 概述

Weave中每个物体需要以下文件：

```
your_object/
├── your_object.obj (或 .usd)   # 3D mesh文件
├── surface.npy                  # 表面采样点
├── sdf_128.npz                  # 有向距离场 (SDF)
└── config.yaml (可选)           # 物体配置
```

## 🔍 数据格式详解

### 1. `surface.npy` - 表面采样点

**作用：**
- 用于计算接触点到物体表面的最近距离
- 在奖励函数中评估机器人与物体的接触质量
- 通过 `SampledSurfaceQuery` 类进行快速最近邻查询

**格式：**
```python
# Shape: (N, 3) - 通常 N=512
# Dtype: float32
# 内容: 物体表面均匀采样的3D点坐标 (x, y, z)

例如：
[[0.358, -0.421, 0.374],
 [0.493, -0.025, 0.114],
 [0.636, -0.123, 0.367],
 ...]  # 共512个点
```

**生成方法：**
- 从mesh表面基于面积进行均匀采样
- 确保点分布均匀，覆盖整个表面
- 采样数量建议512个（与现有数据一致）

### 2. `sdf_128.npz` - 有向距离场

**作用：**
- 计算空间中任意点到物体表面的有向距离
- 用于穿透惩罚（当机器人进入物体内部时）
- 通过三线性插值实现高效查询

**格式：**
```python
{
    # === 必需字段 ===
    'sdf': (128, 128, 128) float32,    # 主SDF网格
          # 值含义：负值=物体内部，正值=物体外部，0=表面
    
    'center': (3,) float32,             # 物体中心坐标
    
    'radius': () float32,               # 物体包围半径
    
    'grid_bound': () float32,           # 网格边界，默认1.25
          # SDF网格覆盖范围: [-grid_bound, grid_bound]³
    
    'resolution': () int32,             # 网格分辨率，默认128
    
    'object_name': () str,              # 物体名称
    
    # === 可选元数据 ===
    'mesh_sha256': () str,              # mesh文件的SHA256哈希
    'surface_sha256': () str,           # surface.npy的SHA256哈希
    'generator_version': () str,        # 生成工具版本
    'sign_convention': () str,          # 符号约定说明
    'surface_abs_sdf_mean': () float32, # 表面点的平均SDF绝对值
    'surface_abs_sdf_p95': () float32,  # 95百分位
    'surface_abs_sdf_max': () float32,  # 最大值
}
```

**SDF网格说明：**
- 分辨率128³表示空间被离散化为128×128×128个体素
- 每个体素存储该点到物体表面的有向距离
- 负值表示在物体内部，正值表示在物体外部
- 在运行时通过三线性插值查询任意位置的SDF值

## 🛠️ 快速开始

### 步骤1: 安装依赖

```bash
pip install trimesh mesh-to-sdf numpy
```

### 步骤2: 准备mesh文件

确保你的mesh文件：
- ✅ 是闭合的（watertight）
- ✅ 法向量方向正确
- ✅ 没有自相交
- ✅ 单位和尺度合理

**推荐工具：**
- MeshLab: 修复mesh、重新网格化
- Blender: 建模、清理、导出

### 步骤3: 生成数据

```bash
python scripts/generate_object_data.py \
    --mesh path/to/your_object.obj \
    --output path/to/output_dir \
    --name your_object \
    --num-surface-samples 512 \
    --sdf-resolution 128 \
    --grid-bound 1.25
```

**参数说明：**
- `--mesh`: 输入mesh文件路径（支持.obj, .stl, .ply等）
- `--output`: 输出目录
- `--name`: 物体名称（可选，默认使用文件名）
- `--num-surface-samples`: 表面采样点数量（默认512）
- `--sdf-resolution`: SDF网格分辨率（默认128）
- `--grid-bound`: SDF网格边界（默认1.25）

### 步骤4: 验证输出

检查生成的文件：

```python
import numpy as np

# 检查surface.npy
surface = np.load('output_dir/surface.npy')
print(f"Surface shape: {surface.shape}")  # 应该是 (512, 3)
print(f"Surface dtype: {surface.dtype}")  # 应该是 float32
print(f"Surface range: [{surface.min():.3f}, {surface.max():.3f}]")

# 检查sdf_128.npz
sdf_data = np.load('output_dir/sdf_128.npz')
print(f"SDF keys: {list(sdf_data.keys())}")
print(f"SDF shape: {sdf_data['sdf'].shape}")  # 应该是 (128, 128, 128)
print(f"Grid bound: {sdf_data['grid_bound']}")
print(f"Object center: {sdf_data['center']}")
```

### 步骤5: 集成到Weave

1. **创建物体目录：**
```bash
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/your_object
```

2. **复制文件：**
```bash
cp output_dir/surface.npy source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp output_dir/sdf_128.npz source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp your_object.obj source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
```

3. **注册物体路径** - 编辑 `objects/__init__.py`：
```python
# objects/__init__.py
from pathlib import Path

ASSET_DIR = str(Path(__file__).parent.resolve())

# ... 现有物体 ...

YOUR_OBJECT_USD_PATH = f"{ASSET_DIR}/your_object/your_object.usd"
```

4. **添加物体配置** - 编辑 `objects/object_cfg.py`：
```python
from g1_hoi_learning.objects import YOUR_OBJECT_USD_PATH

YOUR_OBJECT_CFG = _object_cfg(YOUR_OBJECT_USD_PATH)

OBJECT_CFG_BY_NAME = {
    # ... 现有物体 ...
    "your_object": YOUR_OBJECT_CFG,
}
```

5. **准备motion data：**

确保你的motion data文件（.npz）包含：
- `object_names`: 数组，包含 "your_object"
- 其他必需字段（joint_pos, body_pos_w, 等）

## 🔧 高级选项

### 手动生成surface.npy

如果你想更精细地控制采样：

```python
import trimesh
import numpy as np

# 加载mesh
mesh = trimesh.load('your_object.obj')

# 方法1: 基于面积的均匀采样
points, face_indices = trimesh.sample.sample_surface(mesh, 512)

# 方法2: 泊松圆盘采样（更均匀）
points = trimesh.sample.sample_surface_even(mesh, 512)

# 保存
np.save('surface.npy', points.astype(np.float32))
```

### 手动生成SDF

如果脚本不适用，可以使用其他工具：

**选项1: mesh_to_sdf库**
```python
from mesh_to_sdf import mesh_to_sdf
import trimesh
import numpy as np

mesh = trimesh.load('your_object.obj')

# 归一化mesh
center = mesh.bounds.mean(axis=0)
mesh.apply_translation(-center)
radius = np.linalg.norm(mesh.vertices, axis=1).max()
mesh.apply_scale(1.0 / radius)  # 归一化到单位球

# 生成查询点
resolution = 128
grid_bound = 1.25
x = np.linspace(-grid_bound, grid_bound, resolution)
y = np.linspace(-grid_bound, grid_bound, resolution)
z = np.linspace(-grid_bound, grid_bound, resolution)
xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
query_points = np.stack([xx.ravel(), yy.ravel(), zz.ravel()], axis=-1)

# 计算SDF
sdf_values = mesh_to_sdf(mesh, query_points)
sdf_grid = sdf_values.reshape(resolution, resolution, resolution)

# 保存
np.savez('sdf_128.npz',
    sdf=sdf_grid.astype(np.float32),
    center=center.astype(np.float32),
    radius=np.float32(radius),
    grid_bound=np.float32(grid_bound),
    resolution=np.int32(resolution),
    object_name='your_object'
)
```

**选项2: PyMesh**
```bash
pip install pymesh
```

**选项3: SDFGen**
- 开源C++工具，速度快
- https://github.com/christopherbatty/SDFGen

### 调整网格分辨率

如果物体形状复杂：
- 使用更高分辨率: `--sdf-resolution 256`
- 注意：分辨率翻倍，内存和时间增加8倍

如果物体简单或需要更快速度：
- 使用更低分辨率: `--sdf-resolution 64`

### 调整网格边界

`grid_bound` 决定SDF覆盖的空间范围：
- 默认1.25适用于大多数情况
- 如果物体很大或需要查询远处的点，增加此值
- 如果物体很小，可以减小以提高精度

## ⚠️ 常见问题

### Q1: Mesh不是水密的怎么办？

**解决方法：**
1. 使用MeshLab修复：
   - Filters → Cleaning and Repairing → Close Holes
   - Filters → Normals → Invert Faces Orientation（如果需要）

2. 使用PyMesh：
```python
import pymesh
mesh = pymesh.load_mesh('your_object.obj')
mesh, _ = pymesh.remove_isolated_vertices(mesh)
mesh, _ = pymesh.remove_duplicated_vertices(mesh)
mesh = pymesh.form_mesh(mesh.vertices, mesh.faces)
pymesh.save_mesh('fixed.obj', mesh)
```

### Q2: SDF生成太慢？

**解决方法：**
- 降低分辨率到64或32先测试
- 简化mesh（减少面数）
- 考虑使用更快的工具如SDFGen

### Q3: Surface采样点不够均匀？

**解决方法：**
- 使用 `trimesh.sample.sample_surface_even()` 
- 增加采样点数量
- 检查mesh面积权重是否合理

### Q4: 物体在仿真中尺度不对？

**解决方法：**
1. 检查mesh单位（米、厘米等）
2. 在生成数据前先缩放mesh
3. 在USD文件中调整scale参数

### Q5: 如何验证SDF正确性？

**验证脚本：**
```python
import numpy as np
import matplotlib.pyplot as plt

# 加载数据
surface = np.load('surface.npy')
sdf_data = np.load('sdf_128.npz')

# 可视化中间切片
sdf_grid = sdf_data['sdf']
plt.figure(figsize=(10, 10))
plt.imshow(sdf_grid[64, :, :], cmap='RdBu', vmin=-0.5, vmax=0.5)
plt.colorbar(label='SDF value')
plt.title('SDF中间切片 (负值=内部, 正值=外部)')
plt.show()

# 检查表面点应该接近SDF=0
# (需要实现三线性插值查询，简化版本略)
```

## 📚 参考

### 相关代码文件
- `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/mdp/geometry.py` - SDF和surface的使用
- `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/mdp/commands.py` - Motion和object数据加载
- `source/g1_hoi_learning/g1_hoi_learning/objects/` - 现有物体数据示例

### 有用的库
- **trimesh**: mesh操作和采样 - https://trimsh.org/
- **mesh-to-sdf**: SDF生成 - https://github.com/marian42/mesh_to_sdf
- **PyMesh**: mesh修复和处理 - https://pymesh.readthedocs.io/
- **Open3D**: 3D数据处理 - http://www.open3d.org/

## 💡 提示

1. **先用简单物体测试**：用立方体或球体先验证整个流程
2. **检查mesh质量**：好的mesh是准确SDF的基础
3. **保持一致性**：surface点和SDF应该从同一个mesh生成
4. **备份原始数据**：生成过程可能需要多次迭代
5. **可视化验证**：使用MeshLab或Blender检查生成的数据是否合理

## 🤝 需要帮助？

如果遇到问题：
1. 检查现有物体数据作为参考（例如woodchair）
2. 确保mesh文件格式正确
3. 验证依赖库版本兼容性
4. 查看生成过程的warning信息

祝你成功！🎉
