"""
分析RobotLab和Weave的机器人关节差异
"""

# RobotLab G1 Inspire URDF的关节（从urdf文件提取）
robotlab_joints = [
    # 左手关节 (12个)
    'L_index_intermediate', 'L_index_proximal',
    'L_middle_intermediate', 'L_middle_proximal',
    'L_pinky_intermediate', 'L_pinky_proximal',
    'L_ring_intermediate', 'L_ring_proximal',
    'L_thumb_distal', 'L_thumb_intermediate', 
    'L_thumb_proximal_pitch', 'L_thumb_proximal_yaw',
    
    # 右手关节 (12个)
    'R_index_intermediate', 'R_index_proximal',
    'R_middle_intermediate', 'R_middle_proximal',
    'R_pinky_intermediate', 'R_pinky_proximal',
    'R_ring_intermediate', 'R_ring_proximal',
    'R_thumb_distal', 'R_thumb_intermediate',
    'R_thumb_proximal_pitch', 'R_thumb_proximal_yaw',
    
    # Body关节 (29个)
    'left_ankle_pitch', 'left_ankle_roll', 'left_elbow',
    'left_hip_pitch', 'left_hip_roll', 'left_hip_yaw', 'left_knee',
    'left_shoulder_pitch', 'left_shoulder_roll', 'left_shoulder_yaw',
    'left_wrist_pitch', 'left_wrist_roll', 'left_wrist_yaw',
    
    'right_ankle_pitch', 'right_ankle_roll', 'right_elbow',
    'right_hip_pitch', 'right_hip_roll', 'right_hip_yaw', 'right_knee',
    'right_shoulder_pitch', 'right_shoulder_roll', 'right_shoulder_yaw',
    'right_wrist_pitch', 'right_wrist_roll', 'right_wrist_yaw',
    
    'waist_pitch', 'waist_roll', 'waist_yaw',
]

hand_joints = [j for j in robotlab_joints if any(x in j for x in ['index', 'middle', 'pinky', 'ring', 'thumb'])]
body_joints = [j for j in robotlab_joints if j not in hand_joints]

print("="*60)
print("RobotLab G1 Inspire URDF 关节分析")
print("="*60)
print(f"总关节数: {len(robotlab_joints)}")
print(f"手指关节: {len(hand_joints)} (左手12 + 右手12)")
print(f"身体关节: {len(body_joints)}")
print()

print("手指关节列表:")
for i, j in enumerate(hand_joints):
    print(f"  {i}: {j}")
print()

print("身体关节列表:")
for i, j in enumerate(body_joints):
    print(f"  {i}: {j}")
print()

print("="*60)
print("与Weave的对比")
print("="*60)
print("Weave期望:")
print("  - joint_pos: (N, 53)")
print("  - body_pos_w: (N, 54, 3)")
print()
print("RobotLab实际:")
print(f"  - 总关节: {len(robotlab_joints)}")
print(f"  - 如果去除手指: {len(body_joints)}")
print()

if len(robotlab_joints) == 53:
    print("✓ 总关节数匹配 (53)")
    print("  方案: 直接使用所有关节")
else:
    print(f"✗ 总关节数不匹配 ({len(robotlab_joints)} vs 53)")
    print(f"  差异: {53 - len(robotlab_joints)}")
