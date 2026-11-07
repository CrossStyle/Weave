# RobotLab → Weave 转换完整资源索引

本文档汇总了从RobotLab转换motion data到Weave所需的所有工具和文档。

---

## 🎯 核心发现

**✅ RobotLab和Weave使用完全相同的G1 Inspire机器人！**

- 总关节: 53 (29 body + 24 hand)
- 关节定义: 完全一致
- 转换难度: **简单** - 主要是字段名称映射

---

## 📚 文档指南

### 🚀 快速开始
**[`docs/CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md)** ⭐ **从这里开始**
- 完整的转换流程
- 批量转换脚本
- 故障排查指南
- 转换成功清单

### 🔍 深入了解
**[`docs/convert_robotlab_to_weave_zh.md`](convert_robotlab_to_weave_zh.md)**
- 详细的格式对比
- 转换原理说明
- 高级选项
- 常见问题详解

**[`docs/robot_comparison.md`](robot_comparison.md)**
- 机器人配置对比分析
- 关节列表和顺序
- 为什么可以直接转换

---

## 🛠️ 转换工具

### 核心脚本

| 脚本 | 功能 | 优先级 |
|------|------|--------|
| **`scripts/convert_robotlab_to_weave.py`** | 转换RobotLab npz到Weave格式 | 🔥🔥🔥 |
| **`scripts/validate_weave_motion.py`** | 验证转换后的数据 | 🔥🔥 |
| **`scripts/analyze_robot_joints.py`** | 分析机器人关节配置 | 🔥 |

### 辅助脚本

| 脚本 | 功能 |
|------|------|
| `scripts/convert_mesh_to_usd.py` | STL转USD |
| `scripts/generate_object_data.py` | 生成surface和SDF |
| `scripts/validate_object_data.py` | 验证物体数据 |

---

## ⚡ 快速命令参考

### 转换单个motion
```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_data/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame
```

### 验证转换结果
```bash
python scripts/validate_weave_motion.py \
    --input data/custom/h_frame_1clip.npz \
    --reference data/train/woodchair_987clip.npz
```

### 合并多个motions
```bash
python scripts/convert_robotlab_to_weave.py \
    --input \
        robotlab_data/motion1.npz \
        robotlab_data/motion2.npz \
    --output data/custom/combined.npz \
    --object-name h_frame \
    --motion-names "motion1" "motion2"
```

---

## 📊 数据格式速查

### RobotLab格式
```python
{
    'joint_pos': (N, 53),           # 53个关节
    'joint_vel': (N, 53),
    'body_pos_w': (N, num_bodies, 3),
    'body_quat_w': (N, num_bodies, 4),
    'body_lin_vel_w': (N, num_bodies, 3),
    'body_ang_vel_w': (N, num_bodies, 3),
    'object_base_pos': (N, 3),      # 注意字段名
    'object_base_rot': (N, 4),
    'object_base_lin_vel': (N, 3),
    'object_base_ang_vel': (N, 3),
    'contact': (N, num_bodies),
    'fps': (1,)
}
```

### Weave格式
```python
{
    'joint_pos': (N, 53),           # 相同
    'joint_vel': (N, 53),
    'body_pos_w': (N, 54, 3),       # 期望54个bodies
    'body_quat_w': (N, 54, 4),
    'body_lin_vel_w': (N, 54, 3),
    'body_ang_vel_w': (N, 54, 3),
    'object_pos_w': (N, 3),         # 字段名不同
    'object_quat_w': (N, 4),
    'object_lin_vel_w': (N, 3),
    'object_ang_vel_w': (N, 3),
    'contact_label': (N, 54),       # 字段名不同
    'motion_lengths': (num_clips,), # 新增
    'object_names': (num_clips,),   # 新增
    'fps': (1,)
}
```

---

## 🔄 完整工作流程

```
┌─────────────────────────────────────────────────────────┐
│ RobotLab: 生成motion data                                │
├─────────────────────────────────────────────────────────┤
│ pkl_to_nqz_inspire.py → output.npz                      │
│ (包含joint_pos, body_pos_w, object_base_pos等)          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ 转换: RobotLab → Weave                                   │
├─────────────────────────────────────────────────────────┤
│ convert_robotlab_to_weave.py                            │
│ - 复制关节数据 (53关节完全匹配)                          │
│ - 复制body数据                                           │
│ - 重命名物体字段 (base_pos → pos_w)                      │
│ - 添加motion_lengths和object_names                       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ 验证转换结果                                              │
├─────────────────────────────────────────────────────────┤
│ validate_weave_motion.py                                │
│ - 检查格式 (53关节, 54 bodies)                           │
│ - 验证数值 (无NaN/Inf)                                   │
│ - 对比参考数据                                            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ 准备物体数据 (如果还没有)                                 │
├─────────────────────────────────────────────────────────┤
│ 1. convert_mesh_to_usd.py (STL→USD)                    │
│ 2. generate_object_data.py (surface+SDF)               │
│ 3. 部署到objects/目录                                    │
│ 4. 注册到__init__.py和object_cfg.py                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│ 在Weave中使用                                            │
├─────────────────────────────────────────────────────────┤
│ 1. visualize_reference_motion.py (可视化检查)           │
│ 2. train.py (训练)                                      │
└─────────────────────────────────────────────────────────┘
```

---

## ⚠️ 重要检查项

在转换前确认：
- [ ] RobotLab使用的是 `g1_inspire.urdf`
- [ ] 输出包含53个关节
- [ ] Body数量是多少（30或54）

转换后验证：
- [ ] 验证脚本通过所有检查
- [ ] 关节数量: 53 ✓
- [ ] Body数量: 54（或合理的其他值）
- [ ] 无NaN或Inf值 ✓
- [ ] motion_lengths总和 = 总帧数 ✓

可视化检查：
- [ ] 机器人动作正常
- [ ] 物体位置合理
- [ ] 无穿模或异常姿势
- [ ] 接触看起来真实

---

## 🐛 常见问题快速索引

| 问题 | 查看 |
|------|------|
| Body数量不匹配 | [`CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md#问题1-body数量不匹配) |
| 关节数量不对 | [`CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md#问题2-关节数量不对) |
| 可视化姿势异常 | [`CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md#问题3-可视化时机器人姿势异常) |
| 物体位置不对 | [`CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md#问题4-物体位置不对) |
| 物体数据准备 | [`prepare_object_data_zh.md`](prepare_object_data_zh.md) |
| STL转USD | [`stl_to_usd_guide_zh.md`](stl_to_usd_guide_zh.md) |

---

## 📞 获取帮助

1. **查看文档**: 按优先级阅读上述文档
2. **运行验证**: 使用验证脚本诊断问题
3. **检查日志**: 转换脚本会输出详细信息
4. **对比参考**: 与Weave现有数据对比格式

---

## 🎉 转换成功标志

当你看到这些，说明转换成功了：

```
✓ 验证通过！数据格式正确
✓ 关节数量正确 (53)
✓ Body数量正确 (54)
✓ 无NaN或Inf值
✓ Motion lengths总和匹配总帧数
✓ 所有帧数一致
```

然后在可视化中：
- ✅ 机器人动作流畅自然
- ✅ 物体跟随机器人移动
- ✅ 接触看起来真实
- ✅ 无穿模或抖动

最后在训练中：
- ✅ 训练正常启动
- ✅ 无数据相关错误
- ✅ 奖励曲线合理

---

## 📦 文件清单

### 转换工具 (scripts/)
- ✅ `convert_robotlab_to_weave.py` - 核心转换脚本
- ✅ `validate_weave_motion.py` - 验证脚本
- ✅ `analyze_robot_joints.py` - 关节分析

### 物体准备工具 (scripts/)
- ✅ `convert_mesh_to_usd.py`
- ✅ `generate_object_data.py`
- ✅ `validate_object_data.py`

### 文档 (docs/)
- ✅ `CONVERSION_GUIDE_FINAL_zh.md` - 快速开始
- ✅ `convert_robotlab_to_weave_zh.md` - 详细指南
- ✅ `robot_comparison.md` - 机器人对比
- ✅ `prepare_object_data_zh.md` - 物体数据
- ✅ `stl_to_usd_guide_zh.md` - USD转换

**总计**: 3个转换脚本 + 3个物体工具 + 5份文档

---

## 🚀 现在开始

```bash
# 1. 转换第一个motion
python scripts/convert_robotlab_to_weave.py \
    --input your_robotlab_output.npz \
    --output data/custom/test.npz \
    --object-name your_object

# 2. 验证
python scripts/validate_weave_motion.py --input data/custom/test.npz

# 3. 可视化
python scripts/visualize_reference_motion.py --motion_file data/custom/test.npz

# 4. 训练
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[./data/custom/test.npz]
```

祝转换成功！🎊
