# 解剖学部位力矩分析工具

## 使用方法

```bash
# 基本用法
python scripts/rsl_rl/analyze_effort_by_body_part.py <path_to_json_file>

# 示例
python scripts/rsl_rl/analyze_effort_by_body_part.py logs/rsl_rl/experiment/run/eval/joint_effort_analysis.json
```

## 功能说明

该脚本将关节按解剖学部位分组统计，包括：
- **腿部**：Hip（髋）、Knee（膝）、Ankle（踝）
- **躯干**：Waist（腰）
- **手臂**：Shoulder（肩）、Elbow（肘）、Wrist（腕）
- **手指**：Thumb（拇指）、Index/Middle/Ring/Pinky Finger（其他手指）

相同 limit 的关节会自动合并统计，不区分左右。

## 输出示例

```
====================================================================================================
JOINT EFFORT ANALYSIS BY ANATOMICAL BODY PART
====================================================================================================

Body Part            Limit     Mean      Max   Margin    Peak%  Margin%   Joints
----------------------------------------------------------------------------------------------------
Ankle                 50.0     8.45    42.30    41.55    84.6%    83.1%        4
Elbow                 25.0    12.34    20.15    12.66    80.6%    50.6%        2
Hip (88.0N·m)         88.0    15.23    72.45    72.77    82.3%    82.7%        2
Hip (139.0N·m)       139.0    25.67   110.32   113.33    79.4%    81.5%        2
...

⚠️  HIGH UTILIZATION BODY PARTS (Peak > 80%):
  - Ankle: 84.6% (42.30/50.0 N·m, 4 joints)
  - Hip (88.0N·m): 82.3% (72.45/88.0 N·m, 2 joints)
```

## 统计指标

- **Limit**: 该组关节的力矩限制
- **Mean**: 平均力矩（所有关节的平均）
- **Max**: 峰值力矩（所有关节中的最大值）
- **Margin**: 平均裕度 (Limit - Mean)
- **Peak%**: 峰值比例 (Max / Limit × 100%)
- **Margin%**: 裕度百分比
- **Joints**: 该组包含的关节数量
