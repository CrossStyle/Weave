# 从STL到Weave完整流程

本指南将帮助你从STL mesh文件开始，完整准备好在Weave中使用的物体数据。

## 📋 你需要的文件

对于每个物体，最终需要准备：

```
your_object/
├── your_object.usd          # 3D模型（Isaac Sim格式）
├── your_object.obj          # 3D模型（可选，用于生成数据）
├── surface.npy              # 表面采样点
└── sdf_128.npz             # 有向距离场
```

## 🚀 完整流程（5步）

### 第1步：STL转USD

如果你只有STL文件，首先需要转换为USD格式。

**方法A：使用Blender（最推荐）**
```bash
# 1. 打开Blender
# 2. File → Import → STL → 选择你的STL文件
# 3. 如果需要缩放：Object → Scale → 输入缩放因子 → Apply Scale
# 4. File → Export → USD → 保存为 your_object.usd
```

**方法B：使用脚本**
```bash
python scripts/convert_mesh_to_usd.py \
    --input your_object.stl \
    --output your_object.usd \
    --scale 0.001 \      # mm转m用0.001，cm转m用0.01
    --mass 10.0          # 物体质量（kg）
```

📖 详细说明：[`docs/stl_to_usd_guide_zh.md`](stl_to_usd_guide_zh.md)

---

### 第2步：生成surface.npy和sdf_128.npz

```bash
# 方法1：从STL生成（推荐，保证单位一致）
python scripts/generate_object_data.py \
    --mesh your_object.stl \
    --output ./your_object_data \
    --name your_object

# 方法2：从OBJ生成
python scripts/generate_object_data.py \
    --mesh your_object.obj \
    --output ./your_object_data \
    --name your_object
```

⚠️ **重要：** 如果STL转USD时使用了缩放，生成数据时也要使用相同的缩放：
```bash
# 先缩放STL
python -c "import trimesh; m=trimesh.load('your_object.stl'); m.apply_scale(0.001); m.export('your_object_scaled.stl')"

# 然后从缩放后的STL生成数据
python scripts/generate_object_data.py \
    --mesh your_object_scaled.stl \
    --output ./your_object_data \
    --name your_object
```

---

### 第3步：验证数据

```bash
# 验证并可视化
python scripts/validate_object_data.py \
    --object your_object \
    --objects-dir ./your_object_data \
    --visualize

# 检查输出：
# ✅ surface.npy shape应该是 (512, 3)
# ✅ sdf_128.npz shape应该是 (128, 128, 128)
# ✅ 所有格式验证通过
```

---

### 第4步：组织文件

```bash
# 创建物体目录
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/your_object

# 复制所有文件
cp your_object.usd source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp your_object_data/surface.npy source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
cp your_object_data/sdf_128.npz source/g1_hoi_learning/g1_hoi_learning/objects/your_object/

# 可选：也复制OBJ文件作为参考
cp your_object.obj source/g1_hoi_learning/g1_hoi_learning/objects/your_object/
```

---

### 第5步：注册物体

#### 5.1 编辑 `source/g1_hoi_learning/g1_hoi_learning/objects/__init__.py`

添加：
```python
from pathlib import Path

ASSET_DIR = str(Path(__file__).parent.resolve())

# ... 现有物体 ...

# 添加你的物体
YOUR_OBJECT_USD_PATH = f"{ASSET_DIR}/your_object/your_object.usd"
```

#### 5.2 编辑 `source/g1_hoi_learning/g1_hoi_learning/objects/object_cfg.py`

添加：
```python
from g1_hoi_learning.objects import YOUR_OBJECT_USD_PATH

# 在文件末尾添加配置
YOUR_OBJECT_CFG = _object_cfg(YOUR_OBJECT_USD_PATH)

# 在字典中注册
OBJECT_CFG_BY_NAME = {
    # ... 现有物体 ...
    "your_object": YOUR_OBJECT_CFG,
}
```

---

## ✅ 验证完整性

运行检查脚本确认一切正常：

```bash
# 1. 验证数据文件
python scripts/validate_object_data.py \
    --object your_object \
    --objects-dir source/g1_hoi_learning/g1_hoi_learning/objects

# 2. 在Isaac Sim中打开USD检查
# 启动Isaac Sim → File → Open → 选择your_object.usd
# 检查：模型显示正常，尺寸合理，有碰撞体

# 3. 尝试可视化参考motion（如果有对应的motion data）
python scripts/visualize_reference_motion.py --motion_file your_motion.npz
```

---

## 📝 检查清单

在使用前，确认：

- [ ] **USD文件**
  - [ ] 可以在Isaac Sim中打开
  - [ ] 尺寸正确（单位为米）
  - [ ] 原点位置合理（通常在底部中心）
  - [ ] 有碰撞体（Collision Shape）
  - [ ] 有刚体属性（Rigid Body）

- [ ] **surface.npy**
  - [ ] Shape是 (512, 3) 或类似
  - [ ] Dtype是 float32
  - [ ] 点分布均匀覆盖物体表面

- [ ] **sdf_128.npz**
  - [ ] 包含所有必需字段
  - [ ] SDF grid是 (128, 128, 128)
  - [ ] 内外部体素分布合理

- [ ] **代码注册**
  - [ ] 在 `objects/__init__.py` 中添加USD路径
  - [ ] 在 `objects/object_cfg.py` 中添加配置
  - [ ] 物体名称在 `OBJECT_CFG_BY_NAME` 中

- [ ] **缩放一致性**
  - [ ] USD、surface.npy、sdf_128.npz使用相同的缩放
  - [ ] 单位都是米（m）

---

## 🎯 快速命令（一键执行）

将下面的脚本保存为 `prepare_object.sh`，然后运行 `bash prepare_object.sh your_object.stl`

```bash
#!/bin/bash

# 使用方法: bash prepare_object.sh your_object.stl [scale]
# 例如: bash prepare_object.sh chair.stl 0.001

STL_FILE=$1
SCALE=${2:-0.001}  # 默认0.001 (mm to m)

if [ -z "$STL_FILE" ]; then
    echo "使用方法: bash prepare_object.sh <stl_file> [scale]"
    exit 1
fi

# 获取文件名（不含扩展名）
OBJ_NAME=$(basename "$STL_FILE" .stl)
echo "准备物体: $OBJ_NAME (缩放: $SCALE)"

# 第1步：转换USD
echo "第1步：转换USD..."
python scripts/convert_mesh_to_usd.py \
    --input "$STL_FILE" \
    --output "${OBJ_NAME}.usd" \
    --scale $SCALE

# 第2步：缩放STL用于数据生成
echo "第2步：缩放STL..."
python -c "import trimesh; m=trimesh.load('$STL_FILE'); m.apply_scale($SCALE); m.export('${OBJ_NAME}_scaled.stl')"

# 第3步：生成数据
echo "第3步：生成surface和SDF..."
python scripts/generate_object_data.py \
    --mesh "${OBJ_NAME}_scaled.stl" \
    --output "./${OBJ_NAME}_data" \
    --name "$OBJ_NAME"

# 第4步：验证
echo "第4步：验证数据..."
python scripts/validate_object_data.py \
    --object "$OBJ_NAME" \
    --objects-dir "./${OBJ_NAME}_data" \
    --save-plots "./validation_plots"

# 第5步：组织文件
echo "第5步：组织文件..."
OBJ_DIR="source/g1_hoi_learning/g1_hoi_learning/objects/${OBJ_NAME}"
mkdir -p "$OBJ_DIR"

cp "${OBJ_NAME}.usd" "$OBJ_DIR/"
cp "${OBJ_NAME}_data/surface.npy" "$OBJ_DIR/"
cp "${OBJ_NAME}_data/sdf_128.npz" "$OBJ_DIR/"

echo ""
echo "✅ 完成！文件已复制到: $OBJ_DIR"
echo ""
echo "下一步："
echo "1. 编辑 objects/__init__.py 添加:"
echo "   ${OBJ_NAME^^}_USD_PATH = f\"\{ASSET_DIR}/${OBJ_NAME}/${OBJ_NAME}.usd\""
echo ""
echo "2. 编辑 objects/object_cfg.py 添加:"
echo "   ${OBJ_NAME^^}_CFG = _object_cfg(${OBJ_NAME^^}_USD_PATH)"
echo "   OBJECT_CFG_BY_NAME[\"${OBJ_NAME}\"] = ${OBJ_NAME^^}_CFG"
```

---

## 🆘 常见问题

### Q: mesh单位不确定怎么办？

**测试方法：**
```python
import trimesh
mesh = trimesh.load('your_object.stl')
print(f"边界: {mesh.bounds}")
print(f"尺寸: {mesh.extents}")

# 如果尺寸是几十到几百，可能是mm
# 如果尺寸是几到几十，可能是cm
# 如果尺寸是0.几到几，可能已经是m
```

### Q: 生成的数据看起来不对？

**诊断步骤：**
1. 用验证脚本可视化：`--visualize`
2. 检查mesh质量：是否水密、法向量方向
3. 确认缩放一致性：USD和数据文件用相同scale
4. 参考现有物体：对比woodchair等示例

### Q: Isaac Sim中物体太大或太小？

**解决方法：**
- 重新生成USD，调整 `--scale` 参数
- 同时重新生成surface和SDF数据
- 确保两者使用相同的缩放因子

### Q: 碰撞检测不准确？

**检查：**
- USD中是否有Collision Shape
- Collision approximation设置（mesh/convex hull）
- mesh是否闭合（watertight）

---

## 📚 详细文档

- **STL转USD指南**: [`docs/stl_to_usd_guide_zh.md`](stl_to_usd_guide_zh.md)
- **数据生成详解**: [`docs/prepare_object_data_zh.md`](prepare_object_data_zh.md)  
- **工具使用说明**: [`docs/object_data_tools_README.md`](object_data_tools_README.md)

---

## 💡 提示

1. **第一次操作先用简单物体测试**（如立方体）
2. **保持所有文件使用相同的缩放因子**
3. **用Blender可视化检查每一步的结果**
4. **参考现有物体（woodchair等）作为模板**
5. **保存原始STL文件，便于后续调整**

完成这些步骤后，你就可以在Weave中使用自己的物体进行训练了！🎉
