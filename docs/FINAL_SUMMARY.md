# 🎉 RobotLab → Weave 转换工具包 - 完整版

## ✅ 已更新关键信息

### 实际情况确认

**RobotLab使用**:
- ✅ G1 Inspire机器人
- ✅ USD模型（非URDF）
- ✅ 53个关节（与Weave一致）
- ⚠️ **65个bodies**（比Weave多11个）

**Weave期望**:
- ✅ G1 Inspire机器人
- ✅ 53个关节
- ⚠️ **54个bodies**

**结论**: 关节完全匹配，只需处理body数量差异！

---

## 📦 完整资源列表

### 🛠️ 转换工具 (3个)

1. **`scripts/convert_robotlab_to_weave.py`** ⭐ 核心转换工具
   - 已更新：支持65→54 bodies映射
   - 三种映射策略：`keep_all`, `first_54`, `auto`

2. **`scripts/validate_weave_motion.py`** 验证工具
   - 检查格式完整性
   - 检测NaN/Inf
   - 对比参考数据

3. **`scripts/analyze_robot_joints.py`** 分析工具
   - 关节配置分析

### 📚 完整文档 (7个)

1. **[`docs/QUICK_CHEATSHEET.md`](docs/QUICK_CHEATSHEET.md)** ⭐ **最快入门**
   - 一分钟快速开始
   - 常用命令
   - 快速故障排查

2. **[`docs/CONVERSION_GUIDE_FINAL_zh.md`](docs/CONVERSION_GUIDE_FINAL_zh.md)** 完整指南
   - 详细转换步骤
   - 批量处理脚本
   - 故障排查

3. **[`docs/body_count_65_vs_54.md`](docs/body_count_65_vs_54.md)** ⭐ **新增：Body问题专题**
   - 65 vs 54的详细分析
   - 三种解决方案
   - 诊断步骤

4. **[`docs/CONVERSION_INDEX_zh.md`](docs/CONVERSION_INDEX_zh.md)** 总索引
   - 所有资源导航
   - 快速命令参考

5. **[`docs/convert_robotlab_to_weave_zh.md`](docs/convert_robotlab_to_weave_zh.md)** 详细技术文档
   - 格式详解
   - 高级选项

6. **[`docs/robot_comparison.md`](docs/robot_comparison.md)** 机器人对比
   - 关节列表
   - 配置对比

7. **物体准备文档** (之前创建的)
   - STL转USD
   - surface和SDF生成

---

## ⚡ 三步转换（考虑65 bodies）

```bash
# 1. 转换（保持所有65个bodies）
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output data/custom/motion.npz \
    --object-name h_frame \
    --body-mapping keep_all

# 2. 验证
python scripts/validate_weave_motion.py \
    --input data/custom/motion.npz

# 3. 测试
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/motion.npz
```

**如果步骤3失败**（Weave不支持65个bodies）:
```bash
# 重新转换，只用前54个
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output data/custom/motion.npz \
    --object-name h_frame \
    --body-mapping first_54
```

---

## 🎯 Body映射策略选择

| 策略 | 何时使用 | 优点 | 缺点 |
|------|---------|------|------|
| **`keep_all`** | Weave可处理65个bodies | 保留完整信息 | 可能不兼容 |
| **`first_54`** | Weave严格要求54个 | 兼容性好 | 可能丢失手指信息 |
| **`auto`** | 不确定时 | 自动决策 | 可能需要手动调整 |

**推荐流程**:
1. 先试 `keep_all`
2. 如果报错，用 `first_54`
3. 如果手指动作重要且不对，需要精确映射（见文档）

---

## 📊 数据格式对照表

### 完全相同的字段
```python
✓ joint_pos: (N, 53)
✓ joint_vel: (N, 53)
✓ fps: (1,)
```

### 需要改名的字段
```python
RobotLab              →  Weave
------------------------------------
body_pos_w            →  body_pos_w (保持)
body_quat_w           →  body_quat_w (保持)
object_base_pos       →  object_pos_w
object_base_rot       →  object_quat_w
object_base_lin_vel   →  object_lin_vel_w
object_base_ang_vel   →  object_ang_vel_w
contact               →  contact_label
```

### 需要添加的字段
```python
motion_lengths: (num_clips,)  # 每个clip的长度
object_names: (num_clips,)    # 物体名称
motion_names: (num_clips,)    # 可选
```

### Body数量差异
```python
RobotLab: body_pos_w: (N, 65, 3)  ⚠
Weave:    body_pos_w: (N, 54, 3)  ← 期望
```

---

## 🔄 完整工作流程图

```
┌─────────────────────────────────────┐
│ RobotLab: 生成motion data            │
│ - 53 joints ✓                       │
│ - 65 bodies ⚠                       │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 转换工具                             │
│ - 关节数据：直接复制 (53→53)         │
│ - Body数据：映射 (65→54 或保持65)    │
│ - 物体数据：改字段名                  │
│ - 元数据：添加lengths和names         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 验证                                 │
│ - 格式检查                           │
│ - 数值检查                           │
│ - 对比参考                           │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ Weave使用                            │
│ - 可视化                             │
│ - 训练                               │
└─────────────────────────────────────┘
```

---

## 📝 使用建议

### 推荐阅读顺序

**新手**:
1. [`QUICK_CHEATSHEET.md`](docs/QUICK_CHEATSHEET.md) - 快速上手
2. [`body_count_65_vs_54.md`](docs/body_count_65_vs_54.md) - 理解body问题
3. 开始转换！

**需要详细了解**:
1. [`CONVERSION_GUIDE_FINAL_zh.md`](docs/CONVERSION_GUIDE_FINAL_zh.md) - 完整流程
2. [`convert_robotlab_to_weave_zh.md`](docs/convert_robotlab_to_weave_zh.md) - 技术细节

**遇到问题**:
1. 查看对应文档的"故障排查"部分
2. 运行验证脚本获取诊断信息
3. 检查body映射策略是否正确

---

## ⚠️ 重要提醒

### 关键点

1. **Body数量**: 这是唯一需要处理的差异
2. **关节顺序**: 已确认完全一致
3. **坐标系**: 都是Z-up，应该一致
4. **单位**: 都是米

### 转换前确认

- [ ] RobotLab输出有65个bodies
- [ ] 关节数量是53
- [ ] 有对应的物体数据（USD + surface + SDF）

### 转换后验证

- [ ] 验证脚本通过
- [ ] Body数量是65或54（取决于映射策略）
- [ ] 可视化正常
- [ ] 手指动作正常（如果重要）

---

## 🚀 立即开始

**最简单的方式**:

```bash
# 复制这个命令，替换路径即可
python scripts/convert_robotlab_to_weave.py \
    --input YOUR_ROBOTLAB_OUTPUT.npz \
    --output data/custom/YOUR_MOTION.npz \
    --object-name YOUR_OBJECT_NAME \
    --body-mapping keep_all
```

**然后验证**:
```bash
python scripts/validate_weave_motion.py \
    --input data/custom/YOUR_MOTION.npz
```

**如果看到** `✓ 验证通过！` **就成功了！**

---

## 📞 需要帮助？

1. **Body数量问题** → [`body_count_65_vs_54.md`](docs/body_count_65_vs_54.md)
2. **转换失败** → [`CONVERSION_GUIDE_FINAL_zh.md`](docs/CONVERSION_GUIDE_FINAL_zh.md) 的故障排查
3. **格式问题** → 运行 `validate_weave_motion.py` 获取详细诊断
4. **快速参考** → [`QUICK_CHEATSHEET.md`](docs/QUICK_CHEATSHEET.md)

---

## 🎊 总结

**好消息**: 
- ✅ 关节完全匹配（53）
- ✅ 机器人配置一致
- ✅ 转换脚本已支持body映射

**注意事项**:
- ⚠️ Body数量需要映射（65→54）
- ⚠️ 先试 `keep_all`，不行再用 `first_54`

**预期时间**:
- 转换: < 1分钟/motion
- 验证: < 10秒
- 可视化测试: 取决于motion长度

**成功率**: 很高！主要是字段映射和body数量调整。

---

**现在你拥有完整的工具和文档，开始转换吧！** 🎉

所有资源已准备就绪：
- ✅ 3个转换脚本
- ✅ 7份详细文档
- ✅ Body映射支持
- ✅ 验证和诊断工具

祝转换顺利！🚀
