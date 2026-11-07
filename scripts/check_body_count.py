"""
分析RobotLab实际输出的body数量
"""

import numpy as np
import sys

# 示例：检查RobotLab的输出
print("="*60)
print("RobotLab实际输出分析")
print("="*60)

# 根据你的说明
robotlab_bodies = 65
weave_bodies = 54

print(f"\nRobotLab (USD模型): {robotlab_bodies} bodies")
print(f"Weave (预期): {weave_bodies} bodies")
print(f"差异: {robotlab_bodies - weave_bodies} bodies")

print("\n可能的原因:")
print("1. USD模型包含更多的可视化链接")
print("2. 手指关节产生了额外的body links")
print("3. USD包含了辅助links（如TCP points）")

print("\n解决方案:")
print("方案1: 映射/选择前54个主要bodies")
print("方案2: 保持65个bodies（Weave可能需要调整）")
print("方案3: 找出哪些是额外的11个bodies")

print("\n需要验证:")
print("- RobotLab输出npz中body_pos_w的实际shape")
print("- 哪些是多出来的11个bodies")
print("- Weave是否可以处理65个bodies")
