# 创建65→54 Body精确映射指南

## 🎯 目标

从RobotLab的USD文件中提取65个body names，然后创建到Weave的54个bodies的精确映射。

## 📋 Weave期望的54个Bodies（已知）

```python
1.  pelvis
2.  left_hip_pitch_link
3.  right_hip_pitch_link
4.  waist_yaw_link
5.  left_hip_roll_link
6.  right_hip_roll_link
7.  waist_roll_link
8.  left_hip_yaw_link
9.  right_hip_yaw_link
10. torso_link
11. left_knee_link
12. right_knee_link
13. left_shoulder_pitch_link
14. right_shoulder_pitch_link
15. left_ankle_pitch_link
16. right_ankle_pitch_link
17. left_shoulder_roll_link
18. right_shoulder_roll_link
19. left_ankle_roll_link
20. right_ankle_roll_link
21. left_shoulder_yaw_link
22. right_shoulder_yaw_link
23. left_elbow_link
24. right_elbow_link
25. left_wrist_roll_link
26. right_wrist_roll_link
27. left_wrist_pitch_link
28. right_wrist_pitch_link
29. left_wrist_yaw_link
30. right_wrist_yaw_link
31. L_index_proximal
32. L_middle_proximal
33. L_pinky_proximal
34. L_ring_proximal
35. L_thumb_proximal_base
36. R_index_proximal
37. R_middle_proximal
38. R_pinky_proximal
39. R_ring_proximal
40. R_thumb_proximal_base
41. L_index_intermediate
42. L_middle_intermediate
43. L_pinky_intermediate
44. L_ring_intermediate
45. L_thumb_proximal
46. R_index_intermediate
47. R_middle_intermediate
48. R_pinky_intermediate
49. R_ring_intermediate
50. R_thumb_proximal
51. L_thumb_intermediate
52. R_thumb_intermediate
53. L_thumb_distal
54. R_thumb_distal
```

## 🔧 方法1：从USD文件提取（推荐）

### 步骤1：提取RobotLab的body names

在Isaac Sim环境中运行：

```bash
# 使用Isaac Sim的Python
<isaac-sim-path>/python.sh scripts/create_body_mapping.py \
    --usd-path D:/code/robot/RoMotion/romotion/assets/g1_inspire/g1_29dof_with_inspire_rev_1_0.usd \
    --output-mapping body_mapping_65_to_54.py
```

这会：
1. 从USD中提取65个body names
2. 创建到Weave 54个bodies的映射
3. 保存映射到 `body_mapping_65_to_54.py`

### 步骤2：检查生成的映射

```python
# 查看生成的映射文件
cat body_mapping_65_to_54.py

# 应该看到类似:
BODY_MAPPING_65_TO_54 = [0, 1, 2, ..., 53]
```

### 步骤3：在转换脚本中使用

```bash
# 将生成的映射文件复制到scripts目录
cp body_mapping_65_to_54.py scripts/

# 转换时使用精确映射
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping custom
```

---

## 🔧 方法2：从RobotLab的npz提取

如果RobotLab在生成npz时保存了body names：

### 修改 pkl_to_nqz_inspire.py

在RobotLab的脚本中添加body names输出：

```python
# 在 pkl_to_nqz_inspire.py 的 log 字典中添加
log = {
    "fps": [args_cli.output_fps],
    "base_pos": [],
    # ... 其他字段 ...
    "body_names": robot.body_names,  # 添加这行
}
```

重新生成npz，然后：

```bash
python scripts/create_body_mapping.py \
    --robotlab-npz robotlab_output_with_names.npz \
    --output-mapping body_mapping_65_to_54.py
```

---

## 🔧 方法3：手动指定（如果知道body names）

如果你已经知道RobotLab的65个body names（按顺序）：

```bash
python scripts/create_body_mapping.py \
    --robotlab-bodies \
        pelvis base_link left_hip_pitch_link ... \
    --output-mapping body_mapping_65_to_54.py
```

---

## 🚀 一步到位：提取并应用映射

如果RobotLab的npz包含body names，可以一步完成：

```bash
python scripts/create_body_mapping.py \
    --robotlab-npz robotlab_output.npz \
    --apply-to-npz robotlab_output.npz \
    --output-npz weave_54bodies.npz \
    --output-mapping body_mapping_65_to_54.py
```

这会：
1. 从npz提取body names
2. 创建映射
3. 应用映射到body数据
4. 输出只有54个bodies的npz
5. 保存映射文件供后续使用

---

## 📊 映射验证

生成映射后，脚本会输出：

```
创建Body映射
============================================================
RobotLab bodies: 65
Weave bodies: 54

映射结果:
  成功映射: 54/54

RobotLab中未使用的bodies (11个):
  54: left_tcp_link
  55: right_tcp_link
  56: L_index_distal
  57: L_middle_distal
  ... (其他未使用的bodies)
```

**重要检查**：
- ✅ 成功映射应该是 54/54
- ⚠️ 如果有missing，需要检查名称变体
- ℹ️ 未使用的11个bodies通常是可视化links或distal links

---

## 🔍 故障排查

### 问题1：pxr模块不存在

```
ModuleNotFoundError: No module named 'pxr'
```

**解决**：
- 使用Isaac Sim的Python运行脚本
- 或使用方法2/3（从npz或手动指定）

### 问题2：某些bodies未找到

```
⚠ 警告: 以下Weave bodies在RobotLab中未找到:
  - torso_link
```

**可能原因**：
- RobotLab使用了不同的名称（如 `torso` vs `torso_link`）
- 脚本会自动尝试常见变体

**解决**：
- 检查输出的"注意"信息，看是否已自动匹配
- 手动编辑生成的映射文件

### 问题3：body数量不是65

```
警告: RobotLab body数量为63，期望65
```

**可能原因**：
- USD提取方式不对
- 某些bodies没有RigidBodyAPI

**解决**：
- 检查USD文件结构
- 尝试从npz提取（如果可用）

---

## 💡 使用生成的映射

### 在convert_robotlab_to_weave.py中

```python
# 在文件开头导入
from body_mapping_65_to_54 import BODY_MAPPING_65_TO_54

# 在convert_single_motion函数中使用
if body_mapping == "custom":
    body_pos_w = robotlab_data['body_pos_w'][:, BODY_MAPPING_65_TO_54, :]
    body_quat_w = robotlab_data['body_quat_w'][:, BODY_MAPPING_65_TO_54, :]
    body_lin_vel_w = robotlab_data['body_lin_vel_w'][:, BODY_MAPPING_65_TO_54, :]
    body_ang_vel_w = robotlab_data['body_ang_vel_w'][:, BODY_MAPPING_65_TO_54, :]
    contact_label = robotlab_data['contact'][:, BODY_MAPPING_65_TO_54]
```

### 或使用映射后的npz

如果使用 `--apply-to-npz` 生成了54 bodies的npz：

```bash
# 直接转换映射后的npz
python scripts/convert_robotlab_to_weave.py \
    --input weave_54bodies.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping auto  # 现在是54，不需要特殊处理
```

---

## 📝 最佳实践

1. **优先使用方法1**（从USD提取）- 最准确
2. **保存映射文件** - 供后续使用
3. **验证映射** - 检查未使用的bodies是否合理
4. **测试可视化** - 确认映射后的motion正常

---

## 🎯 预期结果

成功后，你应该有：

1. **映射文件**: `body_mapping_65_to_54.py`
   ```python
   BODY_MAPPING_65_TO_54 = [0, 3, 4, 5, ...]  # 54个索引
   ```

2. **未使用的bodies清单**（11个）
   - 通常是TCP links、distal links等辅助links

3. **转换脚本可用的精确映射**
   - 不会丢失重要的body信息
   - 手指动作完全保留

---

## 🚀 快速开始

```bash
# 如果有Isaac Sim
<isaac-sim>/python.sh scripts/create_body_mapping.py \
    --usd-path path/to/g1_inspire.usd \
    --output-mapping body_mapping_65_to_54.py

# 如果RobotLab npz有body names
python scripts/create_body_mapping.py \
    --robotlab-npz robotlab_output.npz \
    --apply-to-npz robotlab_output.npz \
    --output-npz mapped_54bodies.npz

# 然后正常转换
python scripts/convert_robotlab_to_weave.py \
    --input mapped_54bodies.npz \
    --output weave_motion.npz \
    --object-name h_frame
```

完成！🎉
