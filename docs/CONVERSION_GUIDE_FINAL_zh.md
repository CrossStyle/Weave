# RobotLab Motion 转换指南 - 最终版

## ✅ 重要发现

**RobotLab和Weave使用完全相同的G1 Inspire机器人配置！**

- 总关节数: 53 (29 body + 24 hand)
- 关节定义: 完全一致
- **结论**: 转换非常简单，基本上是字段名称映射

## 🚀 快速开始

### 1. 转换单个motion

```bash
python scripts/convert_robotlab_to_weave.py \
    --input path/to/robotlab/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame \
    --motion-names "h_frame_frontcarry"
```

### 2. 验证转换结果

```bash
python scripts/validate_weave_motion.py \
    --input data/custom/h_frame_1clip.npz \
    --reference data/train/woodchair_987clip.npz
```

### 3. 可视化测试

```bash
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/h_frame_1clip.npz
```

### 4. 在训练中使用

```bash
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[./data/custom/h_frame_1clip.npz]
```

## 📊 数据映射

### 字段名称映射

| RobotLab | Weave | 说明 |
|----------|-------|------|
| `joint_pos` | `joint_pos` | ✓ 直接使用 (53个关节) |
| `joint_vel` | `joint_vel` | ✓ 直接使用 |
| `body_pos_w` | `body_pos_w` | ✓ 直接使用 |
| `body_quat_w` | `body_quat_w` | ✓ 直接使用 |
| `body_lin_vel_w` | `body_lin_vel_w` | ✓ 直接使用 |
| `body_ang_vel_w` | `body_ang_vel_w` | ✓ 直接使用 |
| `object_base_pos` | `object_pos_w` | 改名 |
| `object_base_rot` | `object_quat_w` | 改名 |
| `object_base_lin_vel` | `object_lin_vel_w` | 改名 |
| `object_base_ang_vel` | `object_ang_vel_w` | 改名 |
| `contact` | `contact_label` | 改名 |
| `fps` | `fps` | ✓ 直接使用 |
| - | `motion_lengths` | 新增 (每个clip的长度) |
| - | `motion_names` | 新增 (可选) |
| - | `object_names` | 新增 (每个clip对应的物体) |

### 关节顺序 (53个)

**完全相同！** 按URDF顺序：

```
Body关节 (0-28):
  0-12:  左侧 (ankle, elbow, hip×3, knee, shoulder×3, wrist×3)
  13-25: 右侧 (ankle, elbow, hip×3, knee, shoulder×3, wrist×3)
  26-28: waist (pitch, roll, yaw)

手指关节 (29-52):
  29-40: 左手 (index×2, middle×2, pinky×2, ring×2, thumb×4)
  41-52: 右手 (index×2, middle×2, pinky×2, ring×2, thumb×4)
```

## ⚠️ 重要更新：Body数量差异

### 实际情况

**RobotLab**:
- 使用USD模型（不是URDF）
- **输出65个bodies**
- 关节数量: 53 ✓

**Weave**:
- 期望54个bodies
- 关节数量: 53 ✓

**差异**: 11个额外的bodies需要处理

### 解决方案

转换时使用 `--body-mapping` 参数：

```bash
# 方案1: 保持所有65个bodies (推荐先尝试)
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping keep_all

# 方案2: 只使用前54个bodies
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping first_54
```

**详细说明**: 参见 [`docs/body_count_65_vs_54.md`](body_count_65_vs_54.md)

---

### 2. 物体名称

确保物体在Weave中存在：

```bash
# 检查物体目录
ls source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/

# 应该包含:
# - h_frame.usd
# - surface.npy
# - sdf_128.npz
```

### 3. 坐标系

两者都使用Isaac Sim (Z-up)，应该一致。但建议：
- 可视化检查motion是否正常
- 确认物体和机器人的位置/朝向合理

## 🔧 完整工作流程示例

```bash
# ========================================
# 步骤1: 从RobotLab生成npz（如果还没有）
# ========================================
cd RobotLab
python scripts/tools/beyondmimic/pkl_to_nqz_inspire.py \
    --input_file D:/code/robot/RoMotion/save_mujoco_data/h_frame_mode3 \
    --output_name output/h_frame_mode3.npz \
    --input_fps 50 \
    --output_fps 50 \
    --frame_range 7900 9570

# ========================================
# 步骤2: 转换为Weave格式
# ========================================
cd ../Weave
python scripts/convert_robotlab_to_weave.py \
    --input ../RobotLab/output/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame \
    --motion-names "h_frame_frontcarry"

# ========================================
# 步骤3: 验证转换
# ========================================
python scripts/validate_weave_motion.py \
    --input data/custom/h_frame_1clip.npz \
    --reference data/train/woodchair_987clip.npz

# 应该看到:
# ✓ 验证通过！数据格式正确
# ✓ 关节数量正确 (53)
# ✓ Body数量正确 (54) 或警告

# ========================================
# 步骤4: 准备物体数据（如果还没有）
# ========================================

# 4a. 转换mesh到USD
python scripts/convert_mesh_to_usd.py \
    --input path/to/h_frame.stl \
    --output h_frame.usd \
    --scale 0.001 \
    --mass 10.0

# 4b. 生成surface和SDF
python scripts/generate_object_data.py \
    --mesh path/to/h_frame.stl \
    --output ./h_frame_data \
    --name h_frame

# 4c. 部署到Weave
mkdir -p source/g1_hoi_learning/g1_hoi_learning/objects/h_frame
cp h_frame.usd source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/
cp h_frame_data/surface.npy source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/
cp h_frame_data/sdf_128.npz source/g1_hoi_learning/g1_hoi_learning/objects/h_frame/

# 4d. 注册物体（手动编辑）
# 编辑 source/g1_hoi_learning/g1_hoi_learning/objects/__init__.py
# 添加: H_FRAME_USD_PATH = f"{ASSET_DIR}/h_frame/h_frame.usd"

# 编辑 source/g1_hoi_learning/g1_hoi_learning/objects/object_cfg.py
# 添加: H_FRAME_CFG = _object_cfg(H_FRAME_USD_PATH)
# 在OBJECT_CFG_BY_NAME中添加: "h_frame": H_FRAME_CFG,

# ========================================
# 步骤5: 可视化测试
# ========================================
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/h_frame_1clip.npz

# 检查:
# - 机器人动作是否正常
# - 物体位置是否合理
# - 没有穿模或奇怪的姿势

# ========================================
# 步骤6: 训练
# ========================================
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[./data/custom/h_frame_1clip.npz] \
    env.scene.num_envs=1024
```

## 📝 批量转换脚本

如果有多个motions需要转换：

```bash
#!/bin/bash
# batch_convert.sh

# 定义motion列表
declare -a MOTIONS=(
    "h_frame_mode3:h_frame:frontcarry"
    "h_frame_mode4:h_frame:lowcarry"
    "pallet_mode1:pallet:walk"
    "pallet_mode2:pallet:carry"
)

# 批量转换
for motion_info in "${MOTIONS[@]}"; do
    IFS=':' read -r input_name obj_name motion_name <<< "$motion_info"
    
    echo "转换 ${input_name}..."
    
    python scripts/convert_robotlab_to_weave.py \
        --input "../RobotLab/output/${input_name}.npz" \
        --output "data/custom/${obj_name}_${motion_name}.npz" \
        --object-name "${obj_name}" \
        --motion-names "${motion_name}"
    
    # 验证
    python scripts/validate_weave_motion.py \
        --input "data/custom/${obj_name}_${motion_name}.npz"
    
    echo "✓ ${input_name} 转换完成"
    echo ""
done

echo "所有转换完成！"
```

## 🐛 故障排查

### 问题1: Body数量不匹配

```
⚠ Body数量: 30，期望54
```

**原因**: RobotLab可能只输出了30个body links

**解决方案**:
1. 检查RobotLab的`pkl_to_nqz_inspire.py`脚本
2. 确认是否使用了完整的机器人配置
3. 可能需要在RobotLab中重新生成数据

### 问题2: 关节数量不对

```
⚠ 关节数量: 29，期望53
```

**原因**: 可能只导出了body关节，没有手指

**解决方案**:
1. 检查RobotLab输出时是否包含手指关节
2. 如果只需要body关节，使用 `--weave-robot g1` 参数

### 问题3: 可视化时机器人姿势异常

**检查清单**:
- [ ] 关节顺序是否正确
- [ ] 坐标系是否一致
- [ ] 单位是否正确（米）
- [ ] 关节限位是否合理

**调试方法**:
```python
# 打印关节值范围
import numpy as np
data = np.load('data/custom/h_frame_1clip.npz')
for i in range(data['joint_pos'].shape[1]):
    joint_vals = data['joint_pos'][:, i]
    print(f"Joint {i}: [{joint_vals.min():.3f}, {joint_vals.max():.3f}]")
```

### 问题4: 物体位置不对

**检查**:
- 物体的scale是否正确
- 物体的原点位置是否合理
- USD文件中的transform是否正确

## 📚 相关文档

- **机器人对比**: `docs/robot_comparison.md`
- **转换脚本详解**: `docs/convert_robotlab_to_weave_zh.md`
- **物体数据准备**: `docs/prepare_object_data_zh.md`
- **STL转USD**: `docs/stl_to_usd_guide_zh.md`

## ✨ 转换成功的标志

- [x] 验证脚本通过所有检查
- [x] 关节数量: 53
- [x] Body数量: 54 (或30，取决于配置)
- [x] 无NaN或Inf值
- [x] motion_lengths总和等于总帧数
- [x] 可视化时motion看起来正常
- [x] 物体和机器人交互合理
- [x] 训练可以正常启动

## 🎉 总结

由于RobotLab和Weave使用完全相同的机器人配置，转换过程非常直接：

1. **关节数据**: 直接复制 (53个关节完全匹配)
2. **Body数据**: 直接复制 (需要验证数量)
3. **物体数据**: 改字段名 (`base_pos` → `pos_w`)
4. **元数据**: 添加 `motion_lengths` 和 `object_names`

**预期转换时间**: 每个motion < 1分钟

祝转换顺利！如有问题，请参考故障排查部分。🚀
