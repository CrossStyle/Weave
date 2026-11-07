# RobotLab → Weave 转换快速参考卡

## ⚡ 一分钟快速开始

```bash
# 转换（65 bodies → Weave）
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output data/custom/motion.npz \
    --object-name h_frame \
    --body-mapping keep_all

# 验证
python scripts/validate_weave_motion.py --input data/custom/motion.npz

# 测试
python scripts/visualize_reference_motion.py --motion_file data/custom/motion.npz
```

---

## 🔑 关键信息

### 机器人配置
- **RobotLab**: G1 Inspire (USD模型)
- **Weave**: G1 Inspire
- **关节**: 53 (完全匹配 ✓)
- **Bodies**: 65 vs 54 (需要处理 ⚠)

### 数据差异

| 项目 | RobotLab | Weave | 状态 |
|------|----------|-------|------|
| 关节数 | 53 | 53 | ✅ 匹配 |
| Body数 | 65 | 54 | ⚠ 需映射 |
| 字段名 | `object_base_*` | `object_*_w` | ⚠ 需改名 |

---

## 🛠️ Body映射选项

### 选项1: 保持所有65个 (推荐)
```bash
--body-mapping keep_all
```
**适用**: Weave可以处理65个bodies时

### 选项2: 只用前54个
```bash
--body-mapping first_54
```
**适用**: Weave严格要求54个bodies时

### 选项3: 自动检测
```bash
--body-mapping auto
```
**适用**: 让脚本自动决定（默认）

---

## 📋 完整命令示例

### 单个motion
```bash
python scripts/convert_robotlab_to_weave.py \
    --input ../RobotLab/output/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame \
    --motion-names "h_frame_frontcarry" \
    --body-mapping keep_all
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
    --body-mapping keep_all
```

---

## ✅ 验证清单

转换后检查：
- [ ] 关节数量: 53
- [ ] Body数量: 65 或 54
- [ ] 无NaN/Inf值
- [ ] motion_lengths总和 = 总帧数
- [ ] 可视化正常
- [ ] 物体跟随机器人

---

## 🐛 快速故障排查

### 问题: Weave报错body数量
**解决**: 使用 `--body-mapping first_54`

### 问题: 手指动作不对
**原因**: 可能丢失了手指相关的bodies
**解决**: 使用 `--body-mapping keep_all`

### 问题: 可视化时机器人姿势异常
**检查**:
1. 关节顺序是否正确
2. 单位是否正确（米）
3. 坐标系是否一致

---

## 📚 详细文档

| 文档 | 内容 |
|------|------|
| [`CONVERSION_GUIDE_FINAL_zh.md`](CONVERSION_GUIDE_FINAL_zh.md) | 完整转换指南 |
| [`body_count_65_vs_54.md`](body_count_65_vs_54.md) | Body数量问题详解 |
| [`CONVERSION_INDEX_zh.md`](CONVERSION_INDEX_zh.md) | 所有资源索引 |

---

## 🎯 最佳实践

1. **先用 `keep_all`**: 保留完整信息
2. **验证每一步**: 使用验证脚本
3. **可视化检查**: 确认动作正常
4. **小批量测试**: 先转换一个motion

---

## 💡 记住这个

```bash
# 标准转换命令（复制即用）
python scripts/convert_robotlab_to_weave.py \
    --input INPUT.npz \
    --output OUTPUT.npz \
    --object-name OBJECT_NAME \
    --body-mapping keep_all
```

**替换**:
- `INPUT.npz`: RobotLab的输出文件
- `OUTPUT.npz`: Weave格式的输出
- `OBJECT_NAME`: 物体名称（如 h_frame）

---

## 🚀 成功标志

看到这些就是成功了：
```
✓ 验证通过！数据格式正确
✓ 关节数量正确 (53)
✓ 输出body数量: 65
✓ 无NaN或Inf值
✓ 可视化正常
```

---

**需要帮助？** 查看详细文档或运行验证脚本获取诊断信息。
