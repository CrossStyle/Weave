# 关节力矩数据源说明

## 问题：能否直接获取真实的力矩？

经过深入探索，IsaacLab 提供了以下力矩相关字段：

### 可用的力矩数据

1. **`articulation.data.applied_torque`** ✅ 推荐
   - 执行器模型应用的力矩（裁剪后）
   - 这是最接近"实际施加"的力矩
   - 已经考虑了 `effort_limit_sim` 的约束

2. **`articulation.data.computed_torque`**
   - 执行器模型计算的力矩（裁剪前）
   - 可能超过 effort_limit
   - 需要手动裁剪

3. **PD 控制律估算**（备选）
   - 当上述字段不可用时的回退方案
   - 手动计算：`torque = K_p * error + K_d * vel_error`

### 重要说明

⚠️ **这些都不是 PhysX 物理引擎内部的约束力**

IsaacLab 使用执行器模型（Actuator Model）来模拟电机行为：
- 执行器模型根据目标位置和当前状态计算力矩
- 力矩被裁剪到 `effort_limit_sim`
- 裁剪后的力矩作为"广义力"施加到关节上
- PhysX 物理引擎求解动力学方程

所以 `applied_torque` 是执行器模型的输出，非常接近但不完全等同于物理引擎内部的约束力。

### 当前实现

代码现在会自动选择最佳的数据源：

```python
# 优先级顺序：
1. applied_torque (如果可用) - 最准确
2. computed_torque + 手动裁剪 - 次选
3. PD 估算 - 备选
```

运行时会显示使用的数据源：
```
[INFO] Joint effort analysis using: applied_torque (actual from actuator model)
```

### 获取 PhysX 真实约束力的方法

如果你需要 PhysX 物理引擎的真实约束力，需要：

1. **使用低级 PhysX API**：
   ```python
   # 需要在 Isaac Sim 层面启用 DOF force sensors
   articulation_view.enable_dof_force_sensors = True
   forces = articulation_view.get_measured_joint_forces()
   ```

2. **使用关节反作用力**：
   ```python
   # 从 body_incoming_joint_wrench_b 投影到关节轴
   wrench = articulation.data.body_incoming_joint_wrench_b
   # 需要知道关节轴方向并投影
   ```

3. **等待 IsaacLab 官方支持**：
   - GitHub Issue [#1725](https://github.com/isaac-sim/IsaacLab/issues/1725) 请求 FT 传感器支持
   - 未来版本可能会提供更直接的接口

### 结论

对于大多数强化学习应用，**`applied_torque` 已经足够准确**，因为：
- 它是执行器模型的实际输出
- 已经正确应用了力矩限制
- 反映了控制器实际能施加的力矩
- 与真实机器人的电机输出力矩概念一致

只有在需要研究物理引擎的内部约束求解时，才需要真正的 PhysX 约束力。
