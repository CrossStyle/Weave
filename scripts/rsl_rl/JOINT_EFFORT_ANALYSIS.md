# 关节力矩分析功能

## 功能概述

在 `eval.py` 中增加了关节力矩（effort/torque）分析功能，用于记录和分析成功完成任务的环境中机器人各个关节的力矩数据。

**注意：此功能需要使用 `--effort` 参数显式启用。**

## 功能特性

### 1. 数据记录
- 记录每个时刻的关节位置、速度和目标位置
- 基于 PD 控制律计算估算力矩：`torque = K_p * (target_pos - current_pos) + K_d * (0 - current_vel)`
- 仅分析成功完成任务的环境数据

### 2. 统计分析
对每个关节计算以下指标：
- **effort_limit**: 关节力矩限制（从执行器配置中提取）
- **mean_effort**: 平均力矩（绝对值）
- **max_effort**: 峰值力矩（绝对值）
- **mean_margin**: 平均力矩裕度 = `limit - mean_effort`
- **peak_ratio**: 峰值比例 = `max_effort / limit`
- **margin_percentage**: 裕度百分比 = `mean_margin / limit * 100%`

### 3. 输出内容

#### 终端输出
运行评估后会在终端打印详细的力矩分析报告，包括：
- 成功环境数量和时间步数
- 整体统计信息（所有关节的平均/最大力矩）
- 每个关节的详细数据表格
- 高利用率关节警告（峰值比例 > 80%）

示例输出：
```
===== JOINT EFFORT ANALYSIS (Successful Rollouts Only) =====
Number of successful envs: 45
Number of timesteps: 1200

Overall Statistics:
  Mean effort (all joints): 12.34 Nm
  Max effort (all joints):  89.56 Nm
  Mean limit:               50.00 Nm

Per-Joint Analysis:
Joint Name                          Limit     Mean      Max   Margin    Peak%  Margin%
-----------------------------------------------------------------------------------------------
left_hip_yaw_joint                   88.0    15.23    72.45    72.77    82.3%    82.7%
left_hip_roll_joint                 139.0    25.67   110.32   113.33    79.4%    81.5%
...

⚠️  High utilization joints (>80% peak):
  - left_hip_yaw_joint: 82.3% (72.45/88.0 Nm)
```

#### JSON 文件
分析结果保存到 `<output_dir>/joint_effort_analysis.json`，包含完整的数据：

```json
{
  "joint_names": ["left_hip_yaw_joint", "left_hip_roll_joint", ...],
  "effort_limits": [88.0, 139.0, ...],
  "joint_analysis": [
    {
      "joint_name": "left_hip_yaw_joint",
      "effort_limit": 88.0,
      "mean_effort": 15.23,
      "max_effort": 72.45,
      "mean_margin": 72.77,
      "peak_ratio": 0.823,
      "margin_percentage": 82.7
    },
    ...
  ],
  "overall": {
    "num_success_envs": 45,
    "num_timesteps": 1200,
    "mean_effort_all_joints": 12.34,
    "max_effort_all_joints": 89.56,
    "mean_limit": 50.0
  }
}
```

## 使用方法

使用 `--effort` 参数启用关节力矩分析功能：

```bash
# 启用力矩分析
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50 --effort

# 不启用力矩分析（默认）
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50
```

评估完成后：
1. 终端会显示力矩分析报告
2. `<log_dir>/eval/joint_effort_analysis.json` 会保存完整的分析数据
3. `<log_dir>/eval/metrics.json` 会保存原有的评估指标

## 实现细节

### 力矩估算方法
由于 IsaacLab 的 `articulation.data` 不直接暴露实际施加的力矩，我们使用 PD 控制律估算并应用力矩限制：

```python
# 1. 计算未限制的 PD 控制输出
effort_raw = stiffness * (target_pos - current_pos) + damping * (0 - current_vel)

# 2. 应用 effort_limit_sim 硬约束（裁剪到 [-limit, +limit]）
effort = clamp(effort_raw, -effort_limit, +effort_limit)
```

这样计算的力矩值会遵守 `effort_limit_sim` 的硬约束，不会超过设定的限制。

其中：
- `stiffness` 和 `damping` 从执行器配置中提取
- `target_pos` 从 action manager 获取
- `current_pos` 和 `current_vel` 从 `robot.data` 获取
- `effort_limit` 从 `effort_limit_sim` 配置中提取

### 关键类：JointEffortAnalyzer
位于 `eval.py` 中，主要方法：
- `__init__()`: 初始化存储空间，提取执行器参数
- `_extract_actuator_params()`: 从配置中提取每个关节的 stiffness, damping, effort_limit
- `record()`: 每个时间步记录关节状态和计算力矩
- `mark_success()`: 标记成功完成的环境
- `analyze()`: 计算统计指标
- `save_results()`: 保存结果到 JSON 文件

## 注意事项

1. **仅分析成功环境**：只有成功完成全程的环境数据会被用于统计分析
2. **力矩估算**：使用 PD 控制律估算，可能与实际物理引擎计算的力矩略有差异
3. **执行器配置依赖**：需要机器人配置正确定义 `effort_limit_sim`、`stiffness` 和 `damping`
4. **内存使用**：会存储完整的关节轨迹数据，内存使用量 = `num_envs * num_joints * max_steps * 4 * sizeof(float32)`

## 适用场景

- 分析机器人执行特定动作时的关节负载
- 识别接近力矩极限的关节（可能需要优化控制策略）
- 评估力矩裕度，指导硬件选型或参数调整
- 比较不同策略的力矩使用效率
