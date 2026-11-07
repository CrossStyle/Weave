# 物体质量课程学习（Mass Curriculum Learning）

## 概述

物体质量课程学习是一种渐进式训练方法，通过逐步增加物体质量来提升策略的鲁棒性。训练从较轻的物体开始，当成功率达到阈值后自动增加质量，直到达到目标质量。

## 核心特性

- ✅ **阶跃式质量增加**：每次成功后增加固定质量（如 0.5kg）
- ✅ **自动评估**：每隔固定 iteration 自动评估成功率
- ✅ **回退机制**：连续失败多次后自动回退到上一阶段
- ✅ **保护机制**：每个阶段必须训练最少步数才能晋升
- ✅ **Tensorboard 可视化**：记录质量、阶段、成功率曲线
- ✅ **Checkpoint 保存**：每次晋升自动保存模型

## 快速开始

### 基础训练（带课程学习）

```bash
python scripts/rsl_rl/train_with_curriculum.py \
    --task Isaac-G1-Inspire-HOI-v0 \
    --num_envs 4096 \
    --max_iterations 10000 \
    --curriculum \
    --initial_mass 1.0 \
    --final_mass 5.0 \
    --mass_increment 0.5
```

### 完整参数示例

```bash
python scripts/rsl_rl/train_with_curriculum.py \
    --task Isaac-G1-Inspire-HOI-v0 \
    --num_envs 4096 \
    --max_iterations 20000 \
    --headless \
    --curriculum \
    --initial_mass 1.0 \
    --final_mass 5.0 \
    --mass_increment 0.5 \
    --eval_interval 1000 \
    --eval_episodes 50 \
    --success_threshold 0.8
```

## 参数说明

### 课程学习参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--curriculum` | flag | False | 启用课程学习 |
| `--initial_mass` | float | 1.0 | 初始物体质量（kg） |
| `--final_mass` | float | 5.0 | 目标物体质量（kg） |
| `--mass_increment` | float | 0.5 | 每次增加的质量（kg） |
| `--eval_interval` | int | 1000 | 评估间隔（iterations） |
| `--eval_episodes` | int | 50 | 每次评估的 episode 数 |
| `--success_threshold` | float | 0.8 | 晋升成功率阈值（0-1） |

### 标准训练参数

| 参数 | 说明 |
|------|------|
| `--task` | 任务名称 |
| `--num_envs` | 并行环境数 |
| `--max_iterations` | 最大训练迭代数 |
| `--headless` | 无界面模式 |
| `--seed` | 随机种子 |

## 工作原理

### 训练流程

```
初始化 (质量 = 1.0kg)
    ↓
训练 1000 iterations
    ↓
评估 50 episodes
    ↓
成功率 ≥ 80%？
    ├─ 是 → 增加质量 (+0.5kg) → 继续训练
    └─ 否 → 继续训练当前质量
         ↓
    连续失败 3 次？
         ├─ 是 → 回退质量 (-0.5kg)
         └─ 否 → 继续训练
```

### 成功率定义

- **成功**：机器人完成整个 motion clip 且正常结束（`clip_end=True` 且非 `terminated`）
- **失败**：提前终止（如摔倒、物体掉落等）或超时

### 保护机制

1. **最少训练步数**：每个阶段至少训练 5000 iterations 才能评估晋升
2. **回退机制**：连续 3 次评估不达标后，质量回退到上一阶段
3. **自动保存**：每次晋升时保存当前模型 checkpoint

## 输出和日志

### 目录结构

```
logs/rsl_rl/<experiment_name>/<timestamp>/
├── params/
│   ├── env.yaml              # 环境配置
│   ├── agent.yaml            # 训练配置
│   └── curriculum.yaml       # 课程学习配置
├── curriculum/
│   ├── stage_0_mass_1.0kg.json
│   ├── stage_1_mass_1.5kg.json
│   ├── ...
│   └── summary.json          # 训练总结
├── model_1000.pt             # 评估点 checkpoint
├── model_6000.pt
└── ...
```

### Tensorboard 可视化

启动 tensorboard：

```bash
tensorboard --logdir logs/rsl_rl/<experiment_name>
```

查看以下曲线：

- `curriculum/current_mass`：当前物体质量
- `curriculum/stage`：当前训练阶段
- `curriculum/success_rate`：评估成功率
- `curriculum/stage_iterations`：当前阶段已训练步数

### 训练日志示例

```
============================================================
[MassCurriculum] 课程学习已启动
  初始质量: 1.0 kg
  目标质量: 5.0 kg
  增量步长: 0.5 kg
  评估间隔: 1000 iterations
  成功阈值: 80%
============================================================

[INFO] 训练 1000 iterations (总进度: 0/20000)...

[MassCurriculum] 开始评估 (iteration 1000, 质量 1.0kg)...
[MassCurriculum] 评估完成: 成功率 85.0% (42/50), 平均步数 245.3

============================================================
[MassCurriculum] 🎉 晋升到下一阶段！
  阶段: 0 -> 1
  质量: 1.0 kg -> 1.5 kg
  成功率: 85.0%
============================================================
```

## 代码集成

如果要在自己的代码中使用课程学习：

```python
from g1_hoi_learning.tasks.hoi.mdp.curriculum import MassCurriculumCfg, MassCurriculumManager

# 创建配置
curriculum_cfg = MassCurriculumCfg(
    enabled=True,
    initial_mass=1.0,
    final_mass=5.0,
    mass_increment=0.5,
    eval_interval=1000,
    eval_episodes=50,
    success_threshold=0.8,
    min_iterations_per_stage=5000,
    max_failures=3,
    allow_regression=True,
)

# 初始化管理器
curriculum = MassCurriculumManager(
    cfg=curriculum_cfg,
    env=env.unwrapped,
    log_dir=log_dir,
    tb_writer=tensorboard_writer,
)

# 训练循环中
if curriculum.should_evaluate():
    result = curriculum.evaluate(policy_fn)
    curriculum.update(result)

# 训练结束
curriculum.save_summary()
```

## 最佳实践

1. **初始质量**：建议从真实物体质量的 50-70% 开始
2. **增量步长**：建议为 (final_mass - initial_mass) / 8 左右
3. **评估间隔**：建议 1000-2000 iterations，太频繁会影响训练效率
4. **成功阈值**：0.8 是推荐值，可根据任务难度调整到 0.7-0.9
5. **环境数量**：建议至少 2048 个并行环境以保证评估统计稳定

## 注意事项

- 课程学习**只修改训练时的物体质量**，不影响 reference motion
- 评估时使用**当前阶段的质量**，而不是初始质量
- 多物体情况下，**所有物体质量统一调整**
- 课程学习会增加总训练时间（评估开销约 5-10%）

## 故障排除

**问题：评估成功率始终很低**
- 检查初始质量是否过大，尝试降低到 0.5kg
- 增加 `min_iterations_per_stage` 让策略充分学习

**问题：训练卡在某个质量无法晋升**
- 启用回退机制（`allow_regression=True`）
- 降低 `mass_increment`，使用更小的增量步长

**问题：评估时间过长**
- 减少 `eval_episodes` 到 30-40
- 增加 `eval_interval` 到 2000-3000

**问题：质量设置不生效**
- 确保环境配置中添加了 `clip_end` termination
- 检查物体是否正确初始化（查看日志中的 object 信息）
