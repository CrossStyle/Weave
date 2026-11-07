# 为Weave准备自定义物体数据 - 完整工具包

## ✅ 已创建的资源

我已经为你创建了完整的工具和文档，帮助你从STL mesh准备Weave所需的物体数据。

---

## 📜 脚本工具 (3个)

### 1. `scripts/convert_mesh_to_usd.py`
**功能**: 将STL/OBJ等格式转换为USD格式

**使用示例**:
```bash
python scripts/convert_mesh_to_usd.py \
    --input your_object.stl \
    --output your_object.usd \
    --scale 0.001 \
    --mass 10.0
```

**特性**:
- 支持多种mesh格式 (.stl, .obj, .ply等)
- 自动设置物理属性（刚体、碰撞体）
- 可配置缩放、质量、材质颜色
- 提供备选方案（当pxr不可用时）

---

### 2. `scripts/generate_object_data.py`
**功能**: 从mesh生成surface.npy和sdf_128.npz

**使用示例**:
```bash
python scripts/generate_object_data.py \
    --mesh your_object.stl \
    --output ./output_dir \
    --name your_object \
    --num-surface-samples 512 \
    --sdf-resolution 128
```

**特性**:
- 自动表面采样（基于面积均匀分布）
- 生成有向距离场（SDF）
- 计算并保存元数据（SHA256哈希等）
- 支持自定义分辨率和采样数量

---

### 3. `scripts/validate_object_data.py`
**功能**: 验证和可视化物体数据

**使用示例**:
```bash
python scripts/validate_object_data.py \
    --object your_object \
    --objects-dir ./output_dir \
    --visualize \
    --save-plots ./validation_plots
```

**特性**:
- 检查数据格式和完整性
- 生成详细统计报告
- 3D可视化表面采样点
- 可视化SDF切片
- 保存验证图表

---

## 📚 文档指南 (5个)

### 1. `docs/QUICKSTART_zh.md` ⭐ **从这里开始**
**内容**: 从STL到Weave的完整5步流程

**适合**: 新手用户，想快速上手

**包含**:
- 完整工作流程（5个步骤）
- 一键执行脚本
- 检查清单
- 常见问题解答

---

### 2. `docs/stl_to_usd_guide_zh.md`
**内容**: STL转USD的详细指南

**适合**: 需要深入了解USD转换的用户

**包含**:
- 三种方法对比（Blender、Isaac Sim、脚本）
- 详细步骤说明和截图指引
- Blender批量处理脚本
- 单位转换和验证方法
- 常见问题（20+问题）

---

### 3. `docs/prepare_object_data_zh.md`
**内容**: 数据生成的完整指南（6000+字）

**适合**: 需要了解数据格式和原理的用户

**包含**:
- surface.npy和sdf_128.npz格式详解
- 数据生成原理
- 高级生成选项
- 手动生成方法
- 验证和可视化技巧
- 丰富的代码示例

---

### 4. `docs/object_data_tools_README.md`
**内容**: 工具使用手册

**适合**: 快速查找命令和参数

**包含**:
- 所有脚本的快速参考
- 命令行参数说明
- 批量处理示例
- 安装依赖说明

---

### 5. `docs/INDEX_zh.md`
**内容**: 完整资源索引

**适合**: 了解全貌，快速导航

**包含**:
- 所有文档和工具的总览
- 工作流程图
- 快速命令参考
- 验证检查清单
- 问题排查指南

---

### 6. `docs/QUICK_REFERENCE.md` (英文)
**内容**: 英文快速参考

**适合**: 国际用户，快速查阅

**包含**:
- 核心命令
- 数据格式
- 常见问题

---

## 🎯 使用流程

### 第一次使用
1. 阅读 **`docs/QUICKSTART_zh.md`**
2. 安装依赖: `pip install trimesh mesh-to-sdf matplotlib`
3. 准备一个简单的STL文件测试
4. 按照5步流程操作
5. 使用验证脚本检查结果

### 日常使用
1. 转换USD: `convert_mesh_to_usd.py`
2. 生成数据: `generate_object_data.py`
3. 验证: `validate_object_data.py`
4. 部署到项目

### 批量处理
1. 参考 **`docs/stl_to_usd_guide_zh.md`** 的批量处理部分
2. 修改提供的批量脚本
3. 自动化整个pipeline

### 遇到问题
1. 查看对应文档的"常见问题"部分
2. 运行验证脚本诊断
3. 参考现有物体（woodchair等）

---

## 📋 数据格式总结

### surface.npy
```python
Shape:  (512, 3)      # 512个表面点
Dtype:  float32
单位:   米 (m)
用途:   最近点查询、接触评估
```

### sdf_128.npz
```python
主要字段:
  sdf:        (128, 128, 128)  # SDF网格
  center:     (3,)              # 物体中心
  radius:     scalar            # 包围半径
  grid_bound: 1.25              # 网格边界
  resolution: 128               # 分辨率

用途: 距离场查询、穿透检测
```

### your_object.usd
- Isaac Sim使用的3D场景文件
- 包含geometry、材质、物理属性
- 单位必须是米（m）

---

## ⚡ 快速命令

```bash
# 1. 转换USD
python scripts/convert_mesh_to_usd.py --input model.stl --output model.usd --scale 0.001

# 2. 生成数据
python scripts/generate_object_data.py --mesh model.stl --output ./data --name obj

# 3. 验证
python scripts/validate_object_data.py --object obj --objects-dir ./data --visualize

# 4. 部署
cp model.usd data/* source/g1_hoi_learning/g1_hoi_learning/objects/obj/

# 5. 注册（手动编辑 __init__.py 和 object_cfg.py）
```

---

## ✨ 特色功能

### 自动化程度高
- 一键生成所有需要的文件
- 自动计算元数据
- 自动验证数据格式

### 验证完善
- 格式检查
- 统计分析
- 可视化验证
- 问题诊断

### 文档完整
- 中英文文档
- 适合不同水平用户
- 丰富的示例代码
- 详细的问题解答

### 灵活性高
- 支持多种mesh格式
- 可配置所有参数
- 提供多种转换方案
- 适合批量处理

---

## 🔍 关键要点

1. **保持缩放一致**: USD、surface.npy、sdf_128.npz必须使用相同的缩放因子
2. **单位是米**: 所有文件的单位都是米（m）
3. **mesh质量**: 确保mesh是闭合的（watertight）
4. **验证每步**: 使用验证脚本检查每个步骤的输出
5. **参考示例**: 查看现有物体（woodchair等）作为模板

---

## 📞 获取帮助

### 快速诊断
```bash
# 运行验证脚本查看详细信息
python scripts/validate_object_data.py --object your_object --objects-dir ./data
```

### 查看示例
```bash
# 验证现有物体，作为参考
python scripts/validate_object_data.py --object woodchair --visualize
```

### 查阅文档
- 新手问题 → `docs/QUICKSTART_zh.md`
- USD转换 → `docs/stl_to_usd_guide_zh.md`
- 数据格式 → `docs/prepare_object_data_zh.md`
- 命令参考 → `docs/object_data_tools_README.md`

---

## 🎉 总结

现在你拥有：
- ✅ 3个功能完整的Python脚本
- ✅ 6份详细的中英文文档
- ✅ 从STL到Weave的完整工作流程
- ✅ 验证和可视化工具
- ✅ 批量处理方案
- ✅ 丰富的示例和问题解答

**下一步**:
1. 从 `docs/QUICKSTART_zh.md` 开始
2. 用一个简单的STL文件测试完整流程
3. 在Weave中使用你的自定义物体进行训练

祝你成功！🚀

---

## 📄 文件清单

### 脚本 (scripts/)
- ✅ convert_mesh_to_usd.py
- ✅ generate_object_data.py
- ✅ validate_object_data.py

### 文档 (docs/)
- ✅ QUICKSTART_zh.md (中文快速开始)
- ✅ stl_to_usd_guide_zh.md (USD转换指南)
- ✅ prepare_object_data_zh.md (数据准备详细指南)
- ✅ object_data_tools_README.md (工具说明)
- ✅ INDEX_zh.md (资源索引)
- ✅ QUICK_REFERENCE.md (英文快速参考)

### 额外资源
- ✅ 本总结文档

**总计**: 3个脚本 + 6份文档 = 9个文件

所有工具和文档都已准备就绪！🎊
