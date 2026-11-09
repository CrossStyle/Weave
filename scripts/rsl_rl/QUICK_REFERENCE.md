# 关节力矩分析 - 快速参考

## 功能概述
在评估 RSL-RL agent 时自动记录和分析机器人关节的力矩数据，包括平均力矩、峰值、裕度等统计指标。

## 使用方法

### 运行评估（启用力矩分析）
```bash
# 添加 --effort 参数启用力矩分析
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50 --effort

# 不添加 --effort 则不进行力矩分析（默认）
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50
```

### 查看结果
评估完成后会自动：
1. **终端输出**：显示格式化的力矩分析报告
2. **JSON 文件**：保存到 `<log_dir>/eval/joint_effort_analysis.json`

## 输出示例

### 终端报告
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

## 关键指标说明

| 指标 | 说明 | 计算方法 |
|------|------|---------|
| **Limit** | 关节力矩限制 | 从执行器配置提取 |
| **Mean** | 平均力矩 | 所有时刻的平均绝对值 |
| **Max** | 峰值力矩 | 所有时刻的最大绝对值 |
| **Margin** | 平均裕度 | `Limit - Mean` |
| **Peak%** | 峰值比例 | `(Max / Limit) * 100%` |
| **Margin%** | 裕度百分比 | `(Margin / Limit) * 100%` |

## JSON 输出结构

```json
{
  "joint_names": ["left_hip_yaw_joint", ...],
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
    }
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

## 常见问题

**Q: 如何启用力矩分析？**  
A: 在运行 eval.py 时添加 `--effort` 参数。

**Q: 为什么只分析成功的环境？**  
A: 失败的环境通常因为碰撞、跌倒等异常情况终止，其力矩数据不具有代表性。

**Q: 力矩数据是实际测量的吗？**  
A: 不是，是基于 PD 控制律估算并应用 effort_limit 约束的：
```python
effort_raw = K_p * (target - pos) + K_d * (0 - vel)
effort = clamp(effort_raw, -limit, +limit)
```
这确保了估算值不会超过 `effort_limit_sim` 的硬约束。

**Q: 如何关闭此功能？**  
A: 默认是关闭的，不添加 `--effort` 参数即可。

**Q: 如果没有成功的环境会怎样？**  
A: 会显示警告 "No successful rollouts to analyze"

## 文件位置

- **实现代码**: `scripts/rsl_rl/eval.py`
- **详细文档**: `scripts/rsl_rl/JOINT_EFFORT_ANALYSIS.md`
- **输出文件**: `<log_dir>/eval/joint_effort_analysis.json`

## 相关配置

机器人的力矩限制在以下文件定义：
```
source/g1_hoi_learning/g1_hoi_learning/robots/g1_inspire.py
```

修改 `effort_limit_sim` 值会影响分析结果。
