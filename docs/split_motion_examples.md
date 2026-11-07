# Motion 切分功能使用指南

## 功能说明

`convert_robotlab_to_weave.py` 现在支持按照指定时长切分 motion 数据，解决长 motion 中某些阶段采样不足的问题。

## 使用场景

### 场景 1: Pick 阶段时间短，采样不足
- 原始 motion: 45 秒，pick 阶段只有 3-4 秒（占比 ~7-9%）
- 问题：RSI 随机采样时，pick 阶段被采样概率很低
- 解决：将 motion 切分成 5-10 秒的片段，每个片段采样概率相等

### 场景 2: 多阶段任务的显式 Curriculum
- 切分成多个阶段（pick, carry, place, return）
- 可以按阶段顺序训练，或调整各阶段的采样权重

## 使用方法

### 方法 1: 转换时直接切分（推荐）

从 RobotLab 格式转换为 Weave 格式时，同时进行切分：

```bash
python scripts/convert_robotlab_to_weave.py \
    --input data/robotlab/ladder_motion.npz \
    --output source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave_split.npz \
    --object-name ladder \
    --split-duration 5.0 \
    --split-overlap 0.5
```

**参数说明**：
- `--split-duration 5.0`: 每段 5 秒
- `--split-overlap 0.5`: 相邻段重叠 0.5 秒（可选，用于平滑过渡）

### 方法 2: 只切分已有的 Weave 文件

如果已经有 Weave 格式的 motion 文件，可以单独切分：

```bash
python scripts/convert_robotlab_to_weave.py \
    --split-only \
    --input source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave.npz \
    --output source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave_5s.npz \
    --split-duration 5.0 \
    --split-overlap 0.0
```

## 切分策略建议

### 1. 基于 motion 长度选择段长度

| Motion 总时长 | 建议段长度 | 理由 |
|--------------|-----------|------|
| < 10s | 不切分 | 已经够短 |
| 10-20s | 5s | 切成 2-4 段 |
| 20-40s | 5-8s | 切成 3-6 段 |
| 40-60s | 8-10s | 切成 5-7 段 |
| > 60s | 10-15s | 避免段数过多 |

### 2. 是否使用重叠？

**不使用重叠 (overlap=0)**：
- ✅ 适合：阶段明确、边界清晰的任务
- ✅ 优点：各段独立，便于分析
- ❌ 缺点：段边界可能不连贯

**使用重叠 (overlap=0.5-1.0s)**：
- ✅ 适合：连续性要求高的任务
- ✅ 优点：段之间有过渡，更平滑
- ❌ 缺点：增加数据冗余

### 3. 针对你的 ladder 任务

**推荐设置**：
```bash
--split-duration 8.0 --split-overlap 1.0
```

**理由**：
- 45s motion 切成 6 段（约 7-8s/段）
- 1s 重叠保证动作连贯性
- Pick 阶段（3-4s）单独成段或占据前半段
- 每段采样概率从 ~7% 提升到 ~17%

## 输出格式

切分后的 npz 文件包含：

```python
{
    'motion_lengths': [frames_1, frames_2, ..., frames_n],  # 每段的帧数
    'motion_names': ['ladder_000', 'ladder_001', ...],      # 自动生成的片段名
    'object_names': ['ladder', 'ladder', ...],              # 物体名（相同）
    # ... 其他数据字段
}
```

## 验证切分结果

切分后，可以用可视化工具检查：

```bash
python scripts/visualize_reference_motion.py \
    --motion source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave_5s.npz
```

检查要点：
- ✅ 每段长度是否符合预期
- ✅ 段之间是否连贯（如果使用了重叠）
- ✅ Pick 阶段是否被正确切分
- ✅ 没有切分点在关键动作中间

## 训练配置

使用切分后的 motion：

```yaml
# configs/track/train.yaml
env:
  commands:
    motion:
      motion_files:
        - ./source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_weave_5s.npz
      rsi: true  # 保持开启，现在每段采样概率相等
```

## 预期效果

切分前（45s，6段假设）：
- Pick 阶段采样概率: ~7%
- Episode 中学到 pick: 低

切分后（8s × 6段）：
- 每段采样概率: ~17%
- Pick 阶段采样概率: ~17% (提升 2.4倍)
- Episode 中学到 pick: 显著提升

## 注意事项

1. **最后一段处理**：
   - 如果最后一段 < 段长度的 50%，会被自动跳过
   - 避免过短的片段影响训练

2. **帧率保持不变**：
   - 切分不改变 FPS
   - 只是重新组织数据结构

3. **内存占用**：
   - 切分不增加数据总量
   - 只是元数据（motion_lengths, motion_names）变多

4. **与 eval_mode 的关系**：
   - eval_mode=True: 每个环境固定一个片段评估
   - eval_mode=False + rsi=True: 随机采样片段和起点

## 故障排除

### 问题 1: 切分后 reward 反而下降

**可能原因**：
- 段太短，policy 看不到完整动作
- 边界切在关键动作中间

**解决**：
- 增加 `--split-duration`
- 增加 `--split-overlap` 保证连贯性

### 问题 2: 某些片段学不会

**可能原因**：
- 该片段本身难度高
- 依赖前面阶段的状态

**解决**：
- 使用手动采样权重（见 training_code_review.md 方案2）
- 或使用自适应采样（见 training_code_review.md 方案3）

### 问题 3: Pick 阶段仍然学不会

**可能原因**：
- Pick 阶段太难（接触复杂、力控要求高）
- Reward 设置不合理

**解决**：
- 检查 pick 阶段的 reward 分量
- 放宽相关的 termination 阈值
- 考虑分阶段训练（先只用 pick 片段）
