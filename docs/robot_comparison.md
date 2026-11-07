# RobotLab vs Weave 机器人关节对比分析

## 📊 结论：两者使用完全相同的机器人！

### RobotLab G1 Inspire
- **URDF**: `g1_inspire.urdf`
- **总关节数**: 53
  - Body关节: 29
  - 手指关节: 24 (左手12 + 右手12)

### Weave G1 Inspire  
- **配置**: `g1_inspire.py` → `G1_INSPIRE_CFG`
- **总关节数**: 53 (与RobotLab完全相同)
  - Body关节: 29
  - 手指关节: 24

## ✅ 关键发现

**两个项目使用相同的URDF和关节配置！**

从Weave的配置文件可以看到，它定义了完全相同的关节组：

1. **legs** (8个): hip_yaw, hip_roll, hip_pitch, knee (左右各4)
2. **feet** (4个): ankle_pitch, ankle_roll (左右各2)
3. **waist** (3个): waist_roll, waist_pitch, waist_yaw
4. **arms** (14个): shoulder_pitch/roll/yaw, elbow, wrist_roll/pitch/yaw (左右各7)
5. **fingers** (24个): thumb(4) + index(2) + middle(2) + ring(2) + pinky(2) (左右各12)

**总计**: 8 + 4 + 3 + 14 + 24 = **53个关节**

## 📋 关节顺序对比

### Body关节 (29个) - 按URDF顺序

```
RobotLab顺序 = Weave顺序:
0.  left_ankle_pitch
1.  left_ankle_roll
2.  left_elbow
3.  left_hip_pitch
4.  left_hip_roll
5.  left_hip_yaw
6.  left_knee
7.  left_shoulder_pitch
8.  left_shoulder_roll
9.  left_shoulder_yaw
10. left_wrist_pitch
11. left_wrist_roll
12. left_wrist_yaw
13. right_ankle_pitch
14. right_ankle_roll
15. right_elbow
16. right_hip_pitch
17. right_hip_roll
18. right_hip_yaw
19. right_knee
20. right_shoulder_pitch
21. right_shoulder_roll
22. right_shoulder_yaw
23. right_wrist_pitch
24. right_wrist_roll
25. right_wrist_yaw
26. waist_pitch
27. waist_roll
28. waist_yaw
```

### 手指关节 (24个)

```
左手 (12个):
29. L_index_intermediate
30. L_index_proximal
31. L_middle_intermediate
32. L_middle_proximal
33. L_pinky_intermediate
34. L_pinky_proximal
35. L_ring_intermediate
36. L_ring_proximal
37. L_thumb_distal
38. L_thumb_intermediate
39. L_thumb_proximal_pitch
40. L_thumb_proximal_yaw

右手 (12个):
41. R_index_intermediate
42. R_index_proximal
43. R_middle_intermediate
44. R_middle_proximal
45. R_pinky_intermediate
46. R_pinky_proximal
47. R_ring_intermediate
48. R_ring_proximal
49. R_thumb_distal
50. R_thumb_intermediate
51. R_thumb_proximal_pitch
52. R_thumb_proximal_yaw
```

## 🎯 转换策略

### ✅ 直接转换（推荐）

由于两者使用完全相同的机器人配置，**可以直接使用所有53个关节**：

```python
# 不需要任何关节映射或选择
joint_pos_weave = robotlab_data['joint_pos']  # 直接使用
joint_vel_weave = robotlab_data['joint_vel']  # 直接使用
```

### 注意事项

1. **关节顺序**: 确认RobotLab输出的关节顺序与URDF定义一致
2. **Body数量**: 
   - RobotLab: 需要确认有多少个body links
   - Weave: 期望54个bodies (30个links，可能包括base)
3. **数据字段映射**:
   ```python
   # RobotLab → Weave
   'object_base_pos' → 'object_pos_w'
   'object_base_rot' → 'object_quat_w'
   'object_base_lin_vel' → 'object_lin_vel_w'
   'object_base_ang_vel' → 'object_ang_vel_w'
   'contact' → 'contact_label'
   ```

## 🔍 需要验证的点

1. **Body链接数量**:
   ```python
   # 检查RobotLab的body数量
   robotlab_data = np.load('robotlab_output.npz')
   print(f"RobotLab bodies: {robotlab_data['body_pos_w'].shape[1]}")
   
   # 与Weave对比
   weave_data = np.load('data/train/woodchair_987clip.npz')
   print(f"Weave bodies: {weave_data['body_pos_w'].shape[1]}")  # 应该是54
   ```

2. **关节数据顺序**:
   - 打印RobotLab在生成npz时使用的关节名称列表
   - 与URDF中的顺序对比

3. **坐标系**:
   - 两者都使用Isaac Sim/Gym，应该是相同的坐标系（Z-up）
   - 但需要验证生成的motion看起来是否正常

## 💡 结论

**好消息**: RobotLab和Weave使用完全相同的G1 Inspire机器人配置！

转换应该非常直接：
- ✅ 关节数量匹配 (53)
- ✅ 关节定义相同
- ✅ 只需要字段名称映射
- ⚠️ 需要确认body数量是否匹配 (54)
