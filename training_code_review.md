# 训练代码全面检查报告

## 1. train_with_curriculum.py 中已修复的问题 ✅

### 问题：iteration 更新逻辑冗余
**位置**: 第 310 行和第 325 行

**原代码**:
```python
curriculum.iteration = max_iterations - remaining_iterations  # 第 310 行
# ... 训练 ...
curriculum.iteration += iterations_until_eval  # 第 325 行（冗余）
```

**已修复**: 使用 `current_progress` 临时变量，只在训练后更新一次 iteration

### 问题：评估后没有重置环境
**位置**: 第 347 行之后

**问题**: evaluate() 会 reset 所有环境，但之后直接继续训练，破坏了训练数据连续性

**已修复**: 添加了 `runner.env.reset()` 在评估完成后

---

## 2. curriculum.py - 课程学习管理器 ✅

### 检查项目
- ✅ `should_evaluate()` 逻辑正确
- ✅ `evaluate()` 方法与 eval.py 保持一致
- ✅ `update()` 正确更新 last_eval_iteration
- ✅ 质量设置函数 `_set_object_mass()` 正确
- ✅ 晋升和回退逻辑合理

**无明显问题**

---

## 3. train.py - 标准训练脚本 ✅

### 检查项目
- ✅ 环境创建流程正确
- ✅ Runner 初始化正确
- ✅ checkpoint 加载逻辑正确
- ✅ 使用 `init_at_random_ep_len=True` 启用 RSI

**无明显问题**

---

## 4. env_cfg.py - 环境配置 ⚠️

### 潜在问题点

#### 4.1 Reward 权重设置
**位置**: RewardsCfg

当前权重：
```python
motion_anchor_pos: 1.0
motion_anchor_ori: 1.0
motion_body_pos: 1.0
motion_body_ori: 1.0
object_pos: 2.0        # 物体位置权重较高
object_ori: 2.0        # 物体朝向权重较高
hand_obj_rel_pos: 2.0  # 手-物体相对位置权重较高
contact: 2.0           # 接触奖励权重较高
```

**分析**: 
- 如果物体交互困难（如 ladder），物体相关的 reward 可能长期很低
- 这会导致总 reward 难以上升
- 建议：可以尝试降低物体相关 reward 的权重，或增加机器人 tracking 的权重

#### 4.2 Termination 阈值
**位置**: TerminationsCfg

```python
anchor_pos: threshold=0.25     # pelvis 位置偏差 > 25cm 终止
anchor_ori: threshold=0.8      # pelvis 朝向偏差 > 0.8 rad 终止
object_pos: threshold=0.25     # 物体位置偏差 > 25cm 终止
object_ori: threshold=0.3      # 物体朝向偏差 > 0.3 rad 终止
```

**分析**:
- 阈值可能过于严格，导致 episode 过早终止
- 如果 episode 频繁被 terminate，policy 没有足够时间学习
- 建议：可以适当放宽阈值，特别是在训练早期

#### 4.3 Episode 长度
**位置**: `__post_init__`

```python
self.episode_length_s = 20.0  # 20秒，在 decimation=4, dt=1/200 下是 1000 步
```

**分析**:
- 对于复杂任务可能偏短
- train.yaml 中设置为 45.0s，这个会被覆盖吗？
- 需要确认实际使用的 episode 长度

---

## 5. commands.py - Motion Command ⚠️

### 5.1 RSI 逻辑
**位置**: `_resample_command()` 第 447-457 行

```python
if self.cfg.eval_mode:          # 优先级最高
    self.time_steps[env_ids] = 0
elif self.cfg.rsi:              # 只有 eval_mode=False 时才生效
    self.time_steps[env_ids] = random
else:
    self.time_steps[env_ids] = 0
```

**问题**: eval_mode 优先级高于 rsi，这在训练时是对的，但需要确保训练配置中 `eval_mode=False`

### 5.2 Motion 更新逻辑
**位置**: `_update_command()` 第 500-510 行

需要检查：
- time_steps 是否正确递增
- 是否在 clip 结束时正确处理
- 是否会导致 motion reference 不连续

---

## 6. rewards.py - 奖励函数 ⚠️

### 6.1 指数奖励形式
所有 tracking reward 都使用指数形式：
```python
reward = exp(-error / std^2)
```

**分析**:
- 当 error 很大时，reward 接近 0
- 梯度可能很小，学习困难
- 建议：可以尝试 `1 - tanh(error/std)` 或其他形式，提供更强的梯度信号

### 6.2 Contact Reward
**位置**: contact reward

**问题**: 
- 如果 motion reference 中接触很少，contact reward 可能长期为 0
- 这会让 policy 忽视接触学习
- 建议：检查 ladder motion 中是否有足够的接触标注

---

## 7. 配置文件层级 ⚠️

### train.yaml 配置继承
```yaml
defaults:
  - G1-Inspire-HOI-v0  # 基础配置
  - _self_
```

**问题**: 找不到 `G1-Inspire-HOI-v0.yaml` 文件

**分析**:
- 这个配置可能是通过 Python 代码定义的（env_cfg.py）
- 需要确认 Hydra 如何解析这个引用
- 可能存在配置覆盖顺序问题

---

## 8. 训练流程总结

### 标准训练 (train.py)
```
1. 创建环境（rsi=True 生效）
2. 创建 Runner
3. runner.learn(init_at_random_ep_len=True) 
   └─> RSL-RL 自动处理 RSI
```

### 课程学习训练 (train_with_curriculum.py)  
```
1. 创建环境（rsi=True 生效）
2. 创建 Runner
3. 创建 CurriculumManager
4. 自定义训练循环：
   while remaining_iterations > 0:
       - 训练 N iterations
       - 评估成功率
       - 更新课程（调整物体质量）
       - 重置环境 ✅（已修复）
```

---

## 9. 可能导致 Reward 不上升的原因

### 高优先级问题
1. ✅ **已修复**: curriculum 训练循环的 iteration 更新逻辑错误
2. ✅ **已修复**: 评估后没有重置环境，破坏训练连续性

### 中优先级问题
3. ⚠️ **Reward 权重不平衡**: 物体相关 reward 权重过高，但物体任务困难
4. ⚠️ **Termination 过于严格**: episode 过早终止，学习不充分
5. ⚠️ **Episode 长度**: 可能对复杂任务偏短
6. ⚠️ **指数 reward 形式**: 大误差时梯度过小

### 低优先级问题
7. ⚠️ **Contact reward**: 如果 motion 中接触标注少，这部分 reward 无效
8. ⚠️ **配置继承**: 需要确认 Hydra 配置是否正确解析

---

## 10. 建议的调试步骤

### Step 1: 验证修复是否生效
运行 train_with_curriculum.py，检查：
- [ ] iteration 是否正确递增
- [ ] 评估是否正常触发
- [ ] 评估后环境是否重置

### Step 2: 检查训练指标
在 TensorBoard 中查看：
- [ ] 各个 reward 分量的趋势
- [ ] termination 原因的分布
- [ ] episode 长度的分布
- [ ] curriculum 的质量变化

### Step 3: 如果 reward 仍不上升
尝试以下调整：
1. 降低物体相关 reward 权重（object_pos, object_ori 从 2.0 降到 1.0）
2. 放宽 termination 阈值（如 anchor_pos 从 0.25 改到 0.4）
3. 增加 episode 长度（如从 20s 改到 30s）
4. 尝试不同的 reward 函数形式

### Step 4: 验证 motion data
检查 ladder_weave.npz：
- [ ] clip 数量和长度
- [ ] 物体轨迹是否合理
- [ ] 接触标注是否充分
- [ ] 起始姿态是否可行

---

## 11. 需要进一步确认的点

1. **实际使用的配置**: 运行时打印完整的 env_cfg，确认哪些参数生效
2. **Motion data 质量**: 检查 ladder motion 是否适合训练
3. **RSL-RL 版本**: 确认是否有兼容性问题
4. **硬件资源**: GPU 内存、训练速度是否正常

