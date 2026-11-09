# 关节力矩分析功能 - 实现总结

## 已完成的修改

### 1. 新增命令行参数（eval.py 37-41行）

添加了 `--effort` 参数来控制是否启用力矩分析：

```python
parser.add_argument(
    "--effort", action="store_true", default=False,
    help="Analyze and save joint effort (torque) statistics for successful rollouts.",
)
```

**默认关闭**，需要显式添加 `--effort` 参数才会启用。

### 2. 新增 `JointEffortAnalyzer` 类（eval.py 186-342行）

该类负责：
- 记录每个时刻的关节位置、速度和目标位置
- 从执行器配置中提取每个关节的 effort_limit、stiffness 和 damping
- 基于 PD 控制律计算估算力矩：`effort = K_p * (target - pos) + K_d * (0 - vel)`
- 统计成功环境的力矩数据，计算平均值、峰值、裕度等指标
- 保存结果到 JSON 文件

### 3. 新增 `print_effort_report()` 函数（eval.py 419-466行）

在终端打印格式化的力矩分析报告，包括：
- 整体统计信息
- 每个关节的详细数据表格
- 高利用率关节警告（峰值 > 80%）

### 4. 主评估流程集成（eval.py 519-571行）

在主函数 `main()` 中：
- 根据 `--effort` 参数决定是否初始化 `JointEffortAnalyzer` 实例
- 在每个时间步记录关节状态和目标（仅当启用时）
- 评估完成后标记成功的环境（仅当启用时）
- 保存分析结果到 `<output_dir>/joint_effort_analysis.json`（仅当启用时）
- 打印终端报告（仅当启用时）

### 5. 文档

创建了详细的功能说明文档：
- `scripts/rsl_rl/JOINT_EFFORT_ANALYSIS.md` - 完整的功能文档

## 关键特性

✅ **可选启用**：使用 `--effort` 参数控制，默认关闭  
✅ **仅分析成功环境**：只统计成功完成全程的环境数据  
✅ **完整统计指标**：平均力矩、峰值力矩、力矩裕度、峰值比例  
✅ **支持所有关节类型**：自动从 G1 机器人配置中提取所有执行器参数  
✅ **格式化输出**：终端表格 + JSON 文件双重输出  
✅ **错误处理**：如果无法获取关节目标，会使用零值并给出警告  
✅ **零性能影响**：不启用时完全没有额外开销  

## 输出文件

运行评估后会生成以下文件：
1. `<log_dir>/eval/metrics.json` - 原有的评估指标（成功率、进度等）
2. `<log_dir>/eval/joint_effort_analysis.json` - **新增**：关节力矩分析结果
3. `<log_dir>/eval/videos/...` - 视频录制（如果使用 --video 参数）

## 使用示例

```bash
# 启用力矩分析
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50 --effort

# 不启用力矩分析（默认）
python scripts/rsl_rl/eval.py --task=Isaac-HOI-G1-Inspire-v0 --num_envs=50

# 评估完成后查看结果（仅当使用 --effort 时才会生成）
cat logs/rsl_rl/<experiment_name>/<run_name>/eval/joint_effort_analysis.json
```

## 技术实现要点

### 力矩估算方法
由于 IsaacLab 不直接暴露实际施加的关节力矩，我们使用 PD 控制器的控制律估算：

```python
effort = stiffness * (target_pos - current_pos) + damping * (0 - current_vel)
```

这个估算值接近实际的执行器输出力矩，因为 IsaacLab 使用隐式执行器（Implicit Actuator）模型。

### 执行器参数提取
从机器人配置（`g1_inspire.py`）中提取每个关节的参数：
- 支持字典形式的参数映射（不同关节不同值）
- 支持正则表达式匹配关节名称
- 处理 `effort_limit_sim` 和 `effort_limit` 两种命名方式

### 内存优化考虑
存储完整轨迹数据的内存使用量：
```
memory = num_envs * num_joints * max_steps * 4_tensors * 4_bytes
示例：50 envs * 29 joints * 1200 steps * 4 * 4 bytes ≈ 27.8 MB
```

## 测试建议

建议使用以下场景测试功能：
1. 小规模测试（--num_envs=5）验证功能正常
2. 检查 JSON 输出格式是否正确
3. 验证终端报告显示是否清晰
4. 测试没有成功环境的情况（应显示警告）
5. 测试不同的机器人配置

## 未来改进方向

1. **可选功能开关**：添加 `--analyze-effort` 参数控制是否启用
2. **历史轨迹导出**：支持导出完整的力矩时间序列到 CSV
3. **可视化**：生成力矩曲线图
4. **实时力矩访问**：如果 IsaacLab 未来支持，切换到直接读取实际力矩
5. **多机器人支持**：当前硬编码 `robot_name="robot"`，可以改为自动检测

## 相关文件清单

修改的文件：
- `scripts/rsl_rl/eval.py` - 主要实现

新增的文件：
- `scripts/rsl_rl/JOINT_EFFORT_ANALYSIS.md` - 功能文档
- `EFFORT_ANALYSIS_SUMMARY.md` - 本总结文档
