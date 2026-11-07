# 🎉 RobotLab → Weave 完整转换方案 - 最终版

## ✅ 完整解决方案已就绪！

基于实际情况（RobotLab使用USD模型，输出65个bodies），我们提供了完整的转换工具链。

---

## 📊 实际情况总结

**RobotLab**:
- ✅ G1 Inspire (USD模型)
- ✅ 53个关节
- ⚠️ 65个bodies

**Weave**:
- ✅ G1 Inspire
- ✅ 53个关节
- ✅ 54个bodies (已知顺序)

**转换需求**:
- 关节: 53→53 (直接复制) ✓
- Bodies: 65→54 (需要精确映射) ⭐

---

## 🎯 三种转换方案

### 方案1: 快速转换（保持65个bodies）⚡

**适用**: 快速测试，看Weave是否能处理65个bodies

```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping keep_all
```

**优点**: 最快，保留完整信息  
**缺点**: 可能不兼容Weave

---

### 方案2: 简单映射（前54个bodies）⚡⚡

**适用**: Weave严格要求54个，快速解决

```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping first_54
```

**优点**: 简单直接  
**缺点**: 可能丢失部分hand finger信息

---

### 方案3: 精确映射（推荐）⭐⭐⭐

**适用**: 需要完整保留所有重要bodies

#### 步骤1: 创建精确映射

```bash
# 使用Isaac Sim的Python
<isaac-sim>/python.sh scripts/create_body_mapping.py \
    --usd-path D:/code/robot/RoMotion/romotion/assets/g1_inspire/g1_29dof_with_inspire_rev_1_0.usd \
    --output-mapping body_mapping_65_to_54.py
```

这会：
- 从USD提取65个body names
- 根据Weave的54个body顺序创建精确映射
- 保存映射到 `body_mapping_65_to_54.py`

#### 步骤2: 使用映射转换

```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping custom \
    --body-mapping-file body_mapping_65_to_54.py
```

**优点**: 
- ✅ 精确映射，不丢失信息
- ✅ 保留完整手指动作
- ✅ 符合Weave的body顺序

---

## 🚀 推荐工作流程

### 第一次转换（探索）

```bash
# 1. 先试方案1（最快）
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output test_65.npz \
    --object-name h_frame \
    --body-mapping keep_all

# 2. 测试
python scripts/visualize_reference_motion.py --motion_file test_65.npz

# 如果成功 → 继续使用方案1
# 如果失败（body数量错误）→ 进入下一步
```

### 如果方案1失败

```bash
# 创建精确映射（一次性工作）
<isaac-sim>/python.sh scripts/create_body_mapping.py \
    --usd-path path/to/g1_inspire.usd \
    --output-mapping body_mapping_65_to_54.py

# 使用精确映射转换
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping custom \
    --body-mapping-file body_mapping_65_to_54.py

# 测试
python scripts/visualize_reference_motion.py --motion_file weave_motion.npz
```

---

## 📋 完整命令示例

### 单个motion（精确映射）

```bash
# 转换
python scripts/convert_robotlab_to_weave.py \
    --input ../RobotLab/output/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame \
    --motion-names "h_frame_frontcarry" \
    --body-mapping custom \
    --body-mapping-file body_mapping_65_to_54.py

# 验证
python scripts/validate_weave_motion.py \
    --input data/custom/h_frame_1clip.npz \
    --reference data/train/woodchair_987clip.npz

# 可视化
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/h_frame_1clip.npz
```

### 多个motions合并

```bash
python scripts/convert_robotlab_to_weave.py \
    --input \
        ../RobotLab/output/h_frame_mode3.npz \
        ../RobotLab/output/h_frame_mode4.npz \
    --output data/custom/h_frame_2clips.npz \
    --object-name h_frame \
    --motion-names "frontcarry" "lowcarry" \
    --body-mapping custom \
    --body-mapping-file body_mapping_65_to_54.py
```

---

## 🛠️ 工具链总览

### 已创建的工具

1. **`scripts/create_body_mapping.py`** ⭐ 新增
   - 从USD提取body names
   - 创建65→54精确映射
   - 可直接应用映射到npz

2. **`scripts/convert_robotlab_to_weave.py`** ✨ 已更新
   - 支持custom映射策略
   - 可加载外部映射文件
   - 自动处理65→54转换

3. **`scripts/validate_weave_motion.py`**
   - 验证转换结果
   - 对比参考数据

### 文档清单

1. **[`docs/QUICK_CHEATSHEET.md`](docs/QUICK_CHEATSHEET.md)** - 快速参考
2. **[`docs/create_body_mapping_guide.md`](docs/create_body_mapping_guide.md)** ⭐ 新增 - 映射创建指南
3. **[`docs/body_count_65_vs_54.md`](docs/body_count_65_vs_54.md)** - Body问题详解
4. **[`docs/CONVERSION_GUIDE_FINAL_zh.md`](docs/CONVERSION_GUIDE_FINAL_zh.md)** - 完整转换指南
5. **[`docs/FINAL_SUMMARY.md`](docs/FINAL_SUMMARY.md)** - 总结文档

---

## 📊 方案对比

| 方案 | 速度 | 精确度 | 兼容性 | 推荐度 |
|------|------|--------|--------|--------|
| 方案1 (keep_all) | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⚠️ 取决于Weave | 🔥 先试试 |
| 方案2 (first_54) | ⚡⚡⚡ | ⭐⭐ | ✅ 好 | 🔥 快速方案 |
| 方案3 (custom) | ⚡⚡ | ⭐⭐⭐⭐⭐ | ✅ 最佳 | 🔥🔥🔥 推荐 |

---

## ✅ 成功标志

### 转换成功
```
✓ 关节数量正确 (53)
✓ 输出body数量: 54
✓ 精确映射完成
```

### 验证通过
```
✓ 验证通过！数据格式正确
✓ 所有必需字段存在
✓ 帧数一致
✓ 无NaN或Inf值
```

### 可视化正常
- ✅ 机器人动作流畅
- ✅ 手指动作正确
- ✅ 物体跟随机器人
- ✅ 无穿模或异常

---

## 🎯 常见使用场景

### 场景1: 单个motion测试
```bash
# 使用方案1快速测试
python scripts/convert_robotlab_to_weave.py \
    --input test.npz --output test_weave.npz \
    --object-name h_frame --body-mapping keep_all
```

### 场景2: 批量生产转换
```bash
# 创建映射（一次）
<isaac-sim>/python.sh scripts/create_body_mapping.py \
    --usd-path g1_inspire.usd \
    --output-mapping body_mapping.py

# 批量转换（使用精确映射）
for file in *.npz; do
    python scripts/convert_robotlab_to_weave.py \
        --input $file \
        --output weave_$file \
        --object-name h_frame \
        --body-mapping custom \
        --body-mapping-file body_mapping.py
done
```

### 场景3: 不同物体的motions
```bash
# h_frame
python scripts/convert_robotlab_to_weave.py \
    --input h_frame*.npz \
    --output h_frame_multi.npz \
    --object-name h_frame \
    --body-mapping custom \
    --body-mapping-file body_mapping.py

# pallet
python scripts/convert_robotlab_to_weave.py \
    --input pallet*.npz \
    --output pallet_multi.npz \
    --object-name pallet \
    --body-mapping custom \
    --body-mapping-file body_mapping.py
```

---

## 💡 最佳实践

1. **创建一次映射，重复使用**
   - `body_mapping_65_to_54.py` 对所有motion都适用
   - 保存到项目根目录

2. **先小规模测试**
   - 转换1个motion
   - 验证和可视化
   - 确认无误后批量处理

3. **保留原始数据**
   - RobotLab的npz文件
   - 方便后续调整

4. **文档化映射**
   - 记录哪些bodies被映射
   - 记录哪些bodies被排除

---

## 📞 需要帮助？

| 问题 | 查看文档 |
|------|----------|
| 如何创建映射 | [`create_body_mapping_guide.md`](docs/create_body_mapping_guide.md) |
| Body数量问题 | [`body_count_65_vs_54.md`](docs/body_count_65_vs_54.md) |
| 完整转换流程 | [`CONVERSION_GUIDE_FINAL_zh.md`](docs/CONVERSION_GUIDE_FINAL_zh.md) |
| 快速命令 | [`QUICK_CHEATSHEET.md`](docs/QUICK_CHEATSHEET.md) |

---

## 🎊 总结

你现在拥有：

✅ **完整的工具链**
- body映射创建工具
- 灵活的转换脚本
- 验证和诊断工具

✅ **三种转换方案**
- 快速测试（keep_all）
- 简单映射（first_54）
- 精确映射（custom）⭐

✅ **详细文档**
- 9份指南文档
- 使用示例
- 故障排查

**开始转换吧！** 🚀

推荐流程：**先试方案1 → 如果需要，创建精确映射（方案3）**
