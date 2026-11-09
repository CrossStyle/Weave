# 关节力矩分析功能 - 更新说明

## 📋 更新内容

根据您的要求，已添加 `--effort` 参数来控制关节力矩分析功能的启用。

## ✅ 主要变化

1. **添加了 `--effort` 命令行参数**
   - 默认：**关闭**（不进行力矩分析）
   - 启用：添加 `--effort` 参数

2. **条件执行**
   - 只有使用 `--effort` 参数时才会：
     - 创建 `JointEffortAnalyzer` 实例
     - 记录关节力矩数据
     - 保存分析结果
     - 打印分析报告

3. **零性能影响**
   - 不使用 `--effort` 时，完全没有额外的内存和计算开销

## 🚀 使用方法

### 启用力矩分析
```bash
python scripts/rsl_rl/eval.py \
    --task=Isaac-HOI-G1-Inspire-v0 \
    --num_envs=50 \
    --effort
```

### 不启用力矩分析（默认）
```bash
python scripts/rsl_rl/eval.py \
    --task=Isaac-HOI-G1-Inspire-v0 \
    --num_envs=50
```

### 同时启用视频录制和力矩分析
```bash
python scripts/rsl_rl/eval.py \
    --task=Isaac-HOI-G1-Inspire-v0 \
    --num_envs=50 \
    --effort \
    --video
```

## 📊 输出文件

当使用 `--effort` 参数时，会生成：
- `<log_dir>/eval/joint_effort_analysis.json` - 完整的力矩分析数据
- 终端输出 - 格式化的力矩分析报告

不使用 `--effort` 时：
- 不会生成 `joint_effort_analysis.json`
- 不会显示力矩分析报告
- 正常的评估功能不受影响

## 📚 相关文档

- **详细功能文档**: `scripts/rsl_rl/JOINT_EFFORT_ANALYSIS.md`
- **快速参考**: `scripts/rsl_rl/QUICK_REFERENCE.md`
- **实现总结**: `EFFORT_ANALYSIS_SUMMARY.md`

## ✨ 优势

1. **按需启用**：只在需要时才启用，避免不必要的开销
2. **向后兼容**：现有的评估脚本无需修改，默认行为不变
3. **灵活性高**：可以根据具体需求选择是否分析力矩
4. **清晰明确**：`--effort` 参数名称直观易懂

## 🔧 技术细节

代码修改位置：
- 第 37-41 行：添加 `--effort` 参数定义
- 第 524 行：条件创建 `JointEffortAnalyzer` 实例
- 第 527 行：条件创建 fallback 张量
- 第 541-557 行：条件记录力矩数据
- 第 577-585 行：条件保存和打印分析结果

所有修改都通过了 Python 语法检查，可以直接使用！
