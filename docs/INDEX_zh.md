# Weave物体数据准备 - 完整资源索引

本文档汇总了所有用于准备Weave物体数据的工具、脚本和文档。

## 📖 文档指南

### 🚀 新手入门
- **[QUICKSTART_zh.md](QUICKSTART_zh.md)** - **从这里开始！**
  - 从STL到Weave的完整5步流程
  - 包含一键脚本
  - 检查清单和常见问题

### 🔧 专项指南
- **[stl_to_usd_guide_zh.md](stl_to_usd_guide_zh.md)** - STL转USD详细指南
  - Blender、Isaac Sim、脚本三种方法
  - 批量处理示例
  - 单位转换和验证
  
- **[prepare_object_data_zh.md](prepare_object_data_zh.md)** - 数据生成详细指南
  - surface.npy和sdf_128.npz格式详解
  - 高级生成选项
  - 手动生成方法

- **[object_data_tools_README.md](object_data_tools_README.md)** - 工具使用手册
  - 所有脚本的快速参考
  - 使用示例
  - 安装依赖

## 🛠️ 工具脚本

### 核心工具

| 脚本 | 功能 | 输入 | 输出 |
|------|------|------|------|
| **convert_mesh_to_usd.py** | STL/OBJ → USD | .stl/.obj等 | .usd |
| **generate_object_data.py** | 生成surface和SDF | .stl/.obj等 | surface.npy, sdf_128.npz |
| **validate_object_data.py** | 验证和可视化 | 物体数据目录 | 报告和图表 |

### 快速使用

```bash
# 1. STL转USD
python scripts/convert_mesh_to_usd.py --input model.stl --output model.usd --scale 0.001

# 2. 生成数据
python scripts/generate_object_data.py --mesh model.stl --output ./data --name my_object

# 3. 验证
python scripts/validate_object_data.py --object my_object --objects-dir ./data --visualize
```

## 📋 数据格式速查

### surface.npy
```python
Shape:  (512, 3)      # 512个表面点，xyz坐标
Dtype:  float32       # 浮点数
单位:   米 (m)        # 与USD一致
```

### sdf_128.npz
```python
主要字段:
  'sdf':        (128, 128, 128) float32  # SDF网格，负=内部，正=外部
  'center':     (3,) float32             # 物体中心
  'radius':     () float32               # 包围半径
  'grid_bound': () float32               # 网格边界 (1.25)
  'resolution': () int32                 # 分辨率 (128)
  'object_name': () str                  # 物体名称
```

### your_object.usd
- Isaac Sim可打开的3D场景文件
- 包含geometry、材质、物理属性
- 单位必须是米（m）

## 🎯 工作流程图

```
原始模型 (STL)
    ↓
[convert_mesh_to_usd.py]  ← 缩放、设置物理属性
    ↓
USD文件 ← Isaac Sim可用
    ↓
[generate_object_data.py]  ← 表面采样、SDF计算
    ↓
surface.npy + sdf_128.npz
    ↓
[validate_object_data.py]  ← 验证格式、可视化
    ↓
✅ 数据准备完成
    ↓
复制到 objects/your_object/
    ↓
注册到代码 (__init__.py, object_cfg.py)
    ↓
🎉 可在Weave中使用
```

## 📦 文件组织

### 推荐目录结构

```
Weave/
├── scripts/
│   ├── convert_mesh_to_usd.py      # STL转USD
│   ├── generate_object_data.py     # 生成数据
│   └── validate_object_data.py     # 验证数据
│
├── docs/
│   ├── QUICKSTART_zh.md            # 快速开始
│   ├── stl_to_usd_guide_zh.md     # USD转换指南
│   ├── prepare_object_data_zh.md  # 数据生成指南
│   └── object_data_tools_README.md # 工具说明
│
└── source/g1_hoi_learning/g1_hoi_learning/objects/
    ├── your_object/
    │   ├── your_object.usd         # 必需
    │   ├── surface.npy             # 必需
    │   └── sdf_128.npz            # 必需
    │
    ├── __init__.py                 # 注册USD路径
    └── object_cfg.py               # 注册物体配置
```

## ⚡ 快速命令参考

### 最小化流程
```bash
# 假设：你有 chair.stl (mm单位)

# 1. 一步转换
python scripts/convert_mesh_to_usd.py --input chair.stl --output chair.usd --scale 0.001

# 2. 一步生成数据（记得缩放STL）
python -c "import trimesh; m=trimesh.load('chair.stl'); m.apply_scale(0.001); m.export('chair_m.stl')"
python scripts/generate_object_data.py --mesh chair_m.stl --output ./chair_data --name chair

# 3. 快速验证
python scripts/validate_object_data.py --object chair --objects-dir ./chair_data

# 4. 部署
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/chair
cp chair.usd chair_data/* source/g1_hoi_learning/g1_hoi_learning/objects/chair/

# 5. 手动注册代码（编辑 __init__.py 和 object_cfg.py）
```

### 批量处理
```bash
# 处理多个STL文件
for stl in stl_files/*.stl; do
    name=$(basename "$stl" .stl)
    python scripts/convert_mesh_to_usd.py --input "$stl" --output "${name}.usd" --scale 0.001
    python scripts/generate_object_data.py --mesh "$stl" --output "./${name}_data" --name "$name"
done
```

## 🔍 验证检查清单

使用前确认：

### USD文件
- [ ] 在Isaac Sim中可以打开
- [ ] 尺寸合理（通常0.5m-2m范围）
- [ ] 单位是米
- [ ] 有碰撞体（Collision Shape）
- [ ] 有刚体属性（Rigid Body）
- [ ] 质量设置合理（5-20kg）

### surface.npy
- [ ] Shape: (N, 3) 其中N≈512
- [ ] Dtype: float32
- [ ] 数值范围合理（通常-2到2之间）
- [ ] 点分布均匀

### sdf_128.npz
- [ ] 包含所有必需字段
- [ ] SDF shape: (128, 128, 128)
- [ ] 内部体素（负值）和外部体素（正值）都存在
- [ ] grid_bound通常是1.25
- [ ] resolution是128

### 代码集成
- [ ] objects/__init__.py中定义了USD_PATH
- [ ] objects/object_cfg.py中定义了CFG
- [ ] OBJECT_CFG_BY_NAME字典中注册了物体
- [ ] 物体名称与文件夹名称一致

## 🆘 问题排查

### 问题：USD文件打不开
- 检查：是否使用正确的pxr版本
- 解决：用Blender重新导出

### 问题：物体在仿真中太大/太小
- 检查：USD和数据文件的缩放是否一致
- 解决：重新生成所有文件，使用相同scale

### 问题：SDF生成失败
- 检查：mesh是否闭合（watertight）
- 解决：在MeshLab中修复mesh

### 问题：碰撞不准确
- 检查：USD中的碰撞体设置
- 解决：使用mesh collision而非convex hull

### 问题：表面采样不均匀
- 检查：mesh面积权重是否合理
- 解决：重新网格化mesh，使三角形更均匀

## 📚 额外资源

### 推荐工具
- **Blender** (3.0+): mesh编辑和USD导出
- **MeshLab**: mesh修复和清理
- **Isaac Sim**: USD验证和物理测试
- **MeshMixer**: mesh简化和修复

### Python库
```bash
pip install trimesh          # mesh操作
pip install mesh-to-sdf      # SDF生成
pip install usd-core         # USD支持（可选）
pip install matplotlib       # 可视化
pip install pymesh           # mesh修复（可选）
```

### 在线资源
- Blender: https://www.blender.org/
- Isaac Sim文档: https://docs.omniverse.nvidia.com/isaacsim/
- USD文档: https://graphics.pixar.com/usd/docs/
- trimesh文档: https://trimsh.org/

## 📞 获取帮助

1. **查看示例**：参考 `objects/woodchair/` 等现有物体
2. **运行验证**：使用 `validate_object_data.py` 诊断问题
3. **检查日志**：脚本会输出详细的错误信息
4. **参考文档**：查看对应的详细指南

## 🎓 学习路径

### 初学者
1. 阅读 [QUICKSTART_zh.md](QUICKSTART_zh.md)
2. 使用简单立方体测试完整流程
3. 用验证脚本检查每一步

### 进阶用户
1. 阅读 [prepare_object_data_zh.md](prepare_object_data_zh.md)
2. 了解SDF原理和参数调优
3. 自定义生成脚本满足特殊需求

### 批量处理
1. 阅读 [stl_to_usd_guide_zh.md](stl_to_usd_guide_zh.md) 的批量处理部分
2. 使用Blender Python脚本自动化
3. 编写自己的pipeline脚本

## 🎉 总结

按照以下顺序使用资源：

1. **新手？** → 从 [QUICKSTART_zh.md](QUICKSTART_zh.md) 开始
2. **需要转USD？** → 看 [stl_to_usd_guide_zh.md](stl_to_usd_guide_zh.md)
3. **需要详细说明？** → 看 [prepare_object_data_zh.md](prepare_object_data_zh.md)
4. **需要快速参考？** → 看 [object_data_tools_README.md](object_data_tools_README.md)
5. **遇到问题？** → 看对应文档的"常见问题"部分

所有工具都已准备好，祝你成功！🚀
