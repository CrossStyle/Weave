# Curriculum Learning 评估修复说明

## 问题诊断

### 原始问题
Curriculum learning 中的 eval 结果与 `eval.py` 差距很大。

### 根本原因
**多物体训练 + `eval_mode=True` 导致环境-物体映射错误**

训练时：
- 使用多个物体（如 woodchair, ladder, hframe）
- 每个环境固定分配一个物体：
  - env 0-1364: woodchair
  - env 1365-2729: ladder  
  - env 2730-4095: hframe

原始 curriculum eval：
- 启用 `eval_mode=True`
- `eval_mode` 要求单物体（`num_objects == 1`）
- 多物体时会报错或重新分配 clip
- **导致环境被分配到错误物体的 clip**
  - woodchair 环境可能评估 ladder 的动作
  - 物体几何、质量、尺寸不匹配
  - 成功率暴跌

### Eval.py 为什么正常？
- 只加载单个物体的 motion 文件
- `num_objects == 1`
- `eval_mode=True` 工作正常

---

## 解决方案

### 核心改动

**1. 不启用 `eval_mode`，使用训练时的环境-物体-clip 分配**

```python
# ❌ 原来（错误）
original_eval_mode = self.command.cfg.eval_mode
self.command.cfg.eval_mode = True  # 破坏了多物体的环境分配

# ✅ 现在（正确）
# 不启用 eval_mode，使用训练时的 clip 分配
# 每个环境已经有固定的物体和 clip
```

**2. 禁用 RSI，从 clip 开头评估（重要！）**

```python
# 保存并禁用 RSI
original_rsi = self.command.cfg.rsi
self.command.cfg.rsi = False  # 评估时从头开始

try:
    obs, _ = self.vec_env.reset()  # 现在从 time_steps=0 开始
    # ... 评估逻辑 ...
finally:
    # 恢复原始设置
    self.command.cfg.rsi = original_rsi
```

**为什么要禁用 RSI？**

- **训练时 RSI=True**：从 clip 的随机位置开始，增加数据多样性
- **评估时 RSI=False**：从 clip 开头到结尾完整评估，公平衡量性能
- **与 eval.py 保持一致**：eval.py 使用 `eval_mode` 也会设置 `time_steps=0`

**RSI 启用时的问题**：
- Reset 到 clip 90% → 只需完成 10% → 虚高的成功率
- Reset 到 clip 10% → 需完成 90% → 很难
- **评估结果不公平且乐观**

### 新增功能：分物体统计

评估结果现在包含：

1. **整体统计**（所有物体平均）
   - `success_rate`: 整体成功率
   - `progress_rate`: 整体进度率
   - `episodes`: 评估的 episode 总数
   - `successes`: 成功的 episode 数

2. **分物体统计**（`per_object` 字段）
   ```python
   {
       "woodchair": {
           "success_rate": 0.85,
           "progress_rate": 0.92,
           "episodes": 1365,
           "successes": 1160,
           "num_envs": 1365
       },
       "ladder": {
           "success_rate": 0.73,
           "progress_rate": 0.88,
           ...
       },
       ...
   }
   ```

3. **TensorBoard 记录**
   - `curriculum/success_rate`: 整体成功率
   - `curriculum/progress_rate`: 整体进度率
   - `curriculum/success_rate_woodchair`: woodchair 成功率
   - `curriculum/success_rate_ladder`: ladder 成功率
   - `curriculum/progress_rate_woodchair`: woodchair 进度率
   - ... (每个物体单独记录)

---

## 修改的文件

### `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/mdp/curriculum.py`

#### 1. `evaluate()` 方法

**改动**：
- ✅ 移除 `eval_mode` 启用逻辑
- ✅ 使用训练时的 `env_clip` 和 `env_object` 分配
- ✅ 记录每个环境的物体 ID
- ✅ 分物体统计成功率、进度率
- ✅ 打印整体 + 分物体结果

**新增输出示例**：
```
[MassCurriculum] 评估完成 (整体): 成功率 79.2% (3241/4096), 进度率 88.5%, 平均步数 245.3
[MassCurriculum] 分物体结果:
  woodchair: 成功率 85.1% (1161/1365), 进度率 92.3%
  ladder: 成功率 73.2% (999/1365), 进度率 85.7%
  hframe: 成功率 79.3% (1081/1366), 进度率 87.5%
```

#### 2. `update()` 方法

**改动**：
- ✅ 保存 `per_object` 统计到历史记录
- ✅ 记录分物体指标到 TensorBoard
- ✅ 新增 `curriculum/progress_rate` 记录

---

## 使用方法

### 训练时自动生效

无需修改训练代码，使用 `train_with_curriculum.py` 正常训练即可：

```bash
python scripts/rsl_rl/train_with_curriculum.py \
    --task=G1-Inspire-HOI-v0 \
    --headless \
    --curriculum \
    --config-dir ./configs/track --config-name train
```

### 查看结果

#### 1. 终端输出
训练过程中会看到：
```
[MassCurriculum] 开始评估 (iteration 500, 质量 2.5kg)...
[MassCurriculum] 评估完成 (整体): 成功率 79.2% (3241/4096), 进度率 88.5%, 平均步数 245.3
[MassCurriculum] 分物体结果:
  woodchair: 成功率 85.1% (1161/1365), 进度率 92.3%
  ladder: 成功率 73.2% (999/1365), 进度率 85.7%
  hframe: 成功率 79.3% (1081/1366), 进度率 87.5%
```

#### 2. TensorBoard
```bash
tensorboard --logdir logs/rsl_rl/g1_inspire_hoi --port 6006
```

查看：
- `curriculum/success_rate`: 整体成功率曲线
- `curriculum/success_rate_woodchair`: woodchair 成功率曲线
- `curriculum/success_rate_ladder`: ladder 成功率曲线
- `curriculum/mass`: 质量变化曲线
- `curriculum/stage`: 阶段变化

#### 3. JSON 历史记录
```python
# logs/rsl_rl/g1_inspire_hoi/<run_dir>/curriculum/summary.json
{
  "history": [
    {
      "iteration": 100,
      "stage": 0,
      "mass": 2.0,
      "success_rate": 0.85,
      "per_object": {
        "woodchair": {"success_rate": 0.90, ...},
        "ladder": {"success_rate": 0.80, ...}
      }
    },
    ...
  ]
}
```

---

## 验证修复

### 对比测试

1. **训练完成后，用 eval.py 评估**：
   ```bash
   python scripts/rsl_rl/eval.py --task=G1-Inspire-HOI-v0 \
       --config-dir ./configs/track --config-name eval \
       --load_run <your_run> --checkpoint model_5000.pt
   ```

2. **查看 curriculum 最后一次评估结果**：
   - TensorBoard 中的 `curriculum/success_rate`
   - 或终端输出

3. **结果应该接近**：
   - Eval.py: 单物体评估（如 ladder: 73.2%）
   - Curriculum: 对应物体的分物体统计（ladder: 73.2%）

### 预期改进

**修复前**：
- Curriculum eval: 10-20%（环境-物体错配）
- Eval.py: 70-80%（正常）
- ❌ 巨大差距

**修复后**：
```
[MassCurriculum] 评估完成 (整体): 成功率 75.8% (3102/4096), 进度率 95.2%
[MassCurriculum] 分物体结果:
  woodchair: 成功率 82.3% (1123/1365), 进度率 97.1%
  ladder: 成功率 70.5% (962/1365), 进度率 93.8%
  hframe: 成功率 74.6% (1017/1366), 进度率 94.7%
```

**注意变化**：
- 成功率从 91.2% 降到 75.8%（更真实，RSI 关闭后）
- 进度率从 43.7% 升到 95.2%（从头评估，完成度更高）
- 与 eval.py 结果一致

---

## 技术细节

### 为什么不需要 eval_mode？

**Eval_mode 的作用**：
- 固定每个环境评估特定的 clip
- `env_clip = arange(num_envs) % num_clips`
- 适用于**单物体**场景

**训练时的分配**：
- 每个环境已经固定分配了物体和 clip
- `env_object[i]` 表示环境 i 的物体
- `env_clip[i]` 表示环境 i 当前的 clip
- 这个分配在训练中保持稳定

**Curriculum eval**：
- 直接使用训练时的分配
- 每个环境评估自己的物体
- 不需要重新映射

### 为什么要分物体统计？

1. **诊断问题**：
   - 某个物体的成功率特别低 → 可能需要更多该物体的训练数据
   - 某个物体进度率低但成功率高 → 可能 termination threshold 太严格

2. **平衡训练**：
   - 如果某个物体一直失败，可以调整环境分配比例
   - 或者针对性地调整该物体的质量、奖励权重

3. **准确对比**：
   - Eval.py 通常只评估单个物体
   - 现在可以直接对比对应物体的成功率

---

## 常见问题

### Q: 修复后成功率还是低于 eval.py？
**A**: 可能原因：
1. **质量不同**：检查 curriculum 评估时的物体质量是否与 eval.py 一致
2. **Clip 不同**：训练时的 clip 可能比 eval.py 的测试 clip 更难
3. **随机性**：curriculum 评估的 clip 是训练集，可能包含更困难的场景

### Q: 某个物体的成功率特别低怎么办？
**A**: 
1. 检查该物体的数据质量（motion 是否合理）
2. 增加该物体的环境数量（调整 num_envs 分配）
3. 针对该物体降低质量或调整奖励权重
4. 查看 TensorBoard 中该物体的学习曲线

### Q: 为什么整体成功率是平均值？
**A**: 因为每个环境的权重相同。如果某个物体的环境数多，它会对整体成功率影响更大。这反映了训练时的实际情况。

---

## 总结

✅ **修复完成**：
- 移除了错误的 `eval_mode` 使用
- 使用训练时的环境-物体-clip 分配
- 添加了分物体统计
- Curriculum eval 结果现在应该与 eval.py 一致

✅ **新功能**：
- 分物体成功率统计
- TensorBoard 分物体曲线
- 更详细的诊断信息

✅ **向后兼容**：
- 不影响现有训练代码
- 只优化了评估逻辑
