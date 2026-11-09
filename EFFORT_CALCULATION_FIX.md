# 力矩计算修正说明

## 问题

原始实现中，力矩计算只使用了 PD 控制律：
```python
effort = K_p * (target - pos) + K_d * (0 - vel)
```

这样计算的是"期望力矩"，可能会超过 `effort_limit_sim`。但实际上 `effort_limit_sim` 是硬约束，物理引擎会自动限制实际施加的力矩。

## 修正

现在的实现正确地应用了力矩限制：
```python
# 1. 计算未限制的 PD 控制输出
effort_raw = K_p * (target - pos) + K_d * (0 - vel)

# 2. 应用 effort_limit_sim 硬约束
effort = clamp(effort_raw, -effort_limit, +effort_limit)
```

## 影响

✅ **峰值力矩不会超过 limit**：Peak% 最大为 100%，不会出现 > 100% 的情况

✅ **更准确反映实际情况**：估算值更接近物理引擎实际施加的力矩

✅ **统计更有意义**：力矩裕度和峰值比例的分析更加可靠

## 修改位置

- `scripts/rsl_rl/eval.py` 第 268-284 行：`JointEffortAnalyzer.record()` 方法
- 文档已同步更新

## 验证

代码已通过 Python 语法检查，可以直接使用。
