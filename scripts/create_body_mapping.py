"""
从RobotLab的USD文件中提取body names，并创建到Weave的精确映射

Weave期望的54个bodies（按顺序）:
pelvis, left_hip_pitch_link, right_hip_pitch_link, waist_yaw_link,
left_hip_roll_link, right_hip_roll_link, waist_roll_link, left_hip_yaw_link,
right_hip_yaw_link, torso_link, left_knee_link, right_knee_link,
left_shoulder_pitch_link, right_shoulder_pitch_link, left_ankle_pitch_link,
right_ankle_pitch_link, left_shoulder_roll_link, right_shoulder_roll_link,
left_ankle_roll_link, right_ankle_roll_link, left_shoulder_yaw_link,
right_shoulder_yaw_link, left_elbow_link, right_elbow_link,
left_wrist_roll_link, right_wrist_roll_link, left_wrist_pitch_link,
right_wrist_pitch_link, left_wrist_yaw_link, right_wrist_yaw_link,
L_index_proximal, L_middle_proximal, L_pinky_proximal, L_ring_proximal,
L_thumb_proximal_base, R_index_proximal, R_middle_proximal, R_pinky_proximal,
R_ring_proximal, R_thumb_proximal_base, L_index_intermediate,
L_middle_intermediate, L_pinky_intermediate, L_ring_intermediate,
L_thumb_proximal, R_index_intermediate, R_middle_intermediate,
R_pinky_intermediate, R_ring_intermediate, R_thumb_proximal,
L_thumb_intermediate, R_thumb_intermediate, L_thumb_distal, R_thumb_distal
"""

import argparse
import numpy as np
from pathlib import Path

# Weave期望的54个bodies（按顺序）
WEAVE_BODY_NAMES = [
    'pelvis', 'left_hip_pitch_link', 'right_hip_pitch_link', 'waist_yaw_link',
    'left_hip_roll_link', 'right_hip_roll_link', 'waist_roll_link', 'left_hip_yaw_link',
    'right_hip_yaw_link', 'torso_link', 'left_knee_link', 'right_knee_link',
    'left_shoulder_pitch_link', 'right_shoulder_pitch_link', 'left_ankle_pitch_link',
    'right_ankle_pitch_link', 'left_shoulder_roll_link', 'right_shoulder_roll_link',
    'left_ankle_roll_link', 'right_ankle_roll_link', 'left_shoulder_yaw_link',
    'right_shoulder_yaw_link', 'left_elbow_link', 'right_elbow_link',
    'left_wrist_roll_link', 'right_wrist_roll_link', 'left_wrist_pitch_link',
    'right_wrist_pitch_link', 'left_wrist_yaw_link', 'right_wrist_yaw_link',
    'L_index_proximal', 'L_middle_proximal', 'L_pinky_proximal', 'L_ring_proximal',
    'L_thumb_proximal_base', 'R_index_proximal', 'R_middle_proximal', 'R_pinky_proximal',
    'R_ring_proximal', 'R_thumb_proximal_base', 'L_index_intermediate',
    'L_middle_intermediate', 'L_pinky_intermediate', 'L_ring_intermediate',
    'L_thumb_proximal', 'R_index_intermediate', 'R_middle_intermediate',
    'R_pinky_intermediate', 'R_ring_intermediate', 'R_thumb_proximal',
    'L_thumb_intermediate', 'R_thumb_intermediate', 'L_thumb_distal', 'R_thumb_distal'
]


def extract_body_names_from_usd(usd_path: str):
    """从USD文件中提取body names"""
    try:
        from pxr import Usd, UsdPhysics
        
        stage = Usd.Stage.Open(usd_path)
        body_names = []
        
        # 遍历所有prims，查找RigidBodyAPI
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                # 获取prim名称，通常是link名称
                name = prim.GetName()
                # 或者使用完整路径的最后部分
                # name = str(prim.GetPath()).split('/')[-1]
                body_names.append(name)
        
        return body_names
    except ImportError:
        print("错误: 需要pxr库来读取USD文件")
        print("解决方案:")
        print("1. 使用Isaac Sim的Python运行此脚本")
        print("2. 或手动提供body names（使用--robotlab-bodies参数）")
        return None


def extract_body_names_from_npz(npz_path: str):
    """从RobotLab的npz输出中提取body names（如果有的话）"""
    try:
        data = np.load(npz_path, allow_pickle=True)
        if 'body_names' in data:
            return list(data['body_names'])
        else:
            print("警告: npz文件中没有'body_names'字段")
            return None
    except Exception as e:
        print(f"错误: 无法从npz读取body names: {e}")
        return None


def create_body_mapping(robotlab_bodies, weave_bodies):
    """创建从RobotLab的65个bodies到Weave的54个bodies的映射"""
    
    print(f"\n{'='*60}")
    print("创建Body映射")
    print(f"{'='*60}")
    print(f"RobotLab bodies: {len(robotlab_bodies)}")
    print(f"Weave bodies: {len(weave_bodies)}")
    
    # 创建映射：对于每个Weave body，找到对应的RobotLab索引
    mapping = []
    missing = []
    
    for weave_name in weave_bodies:
        try:
            idx = robotlab_bodies.index(weave_name)
            mapping.append(idx)
        except ValueError:
            # 尝试一些常见的名称变体
            variants = [
                weave_name,
                weave_name.replace('_link', ''),
                weave_name + '_link',
                weave_name.replace('_', ''),
            ]
            
            found = False
            for variant in variants:
                try:
                    idx = robotlab_bodies.index(variant)
                    mapping.append(idx)
                    found = True
                    print(f"  注意: '{weave_name}' 映射到 '{variant}' (索引 {idx})")
                    break
                except ValueError:
                    continue
            
            if not found:
                missing.append(weave_name)
                mapping.append(-1)  # 占位符
    
    print(f"\n映射结果:")
    print(f"  成功映射: {len([m for m in mapping if m != -1])}/{len(weave_bodies)}")
    
    if missing:
        print(f"\n⚠ 警告: 以下Weave bodies在RobotLab中未找到:")
        for name in missing:
            print(f"  - {name}")
    
    # 找出RobotLab中多余的bodies
    used_indices = set(m for m in mapping if m != -1)
    unused_indices = set(range(len(robotlab_bodies))) - used_indices
    
    if unused_indices:
        print(f"\nRobotLab中未使用的bodies ({len(unused_indices)}个):")
        for idx in sorted(unused_indices):
            print(f"  {idx}: {robotlab_bodies[idx]}")
    
    return mapping


def save_mapping_to_file(mapping, output_path):
    """保存映射到Python文件"""
    
    mapping_code = f"""# RobotLab (65 bodies) → Weave (54 bodies) 映射
# 自动生成的映射文件

# 映射数组：Weave的第i个body对应RobotLab的BODY_MAPPING_65_TO_54[i]
BODY_MAPPING_65_TO_54 = {mapping}

# 使用方法:
# weave_body_data = robotlab_body_data[:, BODY_MAPPING_65_TO_54, :]
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(mapping_code)
    
    print(f"\n映射已保存到: {output_path}")


def apply_mapping_to_npz(input_npz, output_npz, mapping):
    """应用映射到npz文件"""
    
    print(f"\n{'='*60}")
    print("应用映射到npz文件")
    print(f"{'='*60}")
    
    # 加载数据
    data = np.load(input_npz, allow_pickle=True)
    
    # 创建映射后的数据
    mapped_data = {}
    
    for key in data.keys():
        if key in ['body_pos_w', 'body_quat_w', 'body_lin_vel_w', 'body_ang_vel_w', 'contact']:
            # 应用body映射
            original = data[key]
            if len(original.shape) >= 2:
                # (N, 65, ...) → (N, 54, ...)
                mapped = original[:, mapping, ...]
                mapped_data[key] = mapped
                print(f"  {key}: {original.shape} → {mapped.shape}")
            else:
                mapped_data[key] = original
        else:
            # 其他字段直接复制
            mapped_data[key] = data[key]
    
    # 保存
    np.savez(output_npz, **mapped_data)
    print(f"\n映射后的数据已保存到: {output_npz}")


def main():
    parser = argparse.ArgumentParser(
        description="创建RobotLab (65 bodies) 到 Weave (54 bodies) 的精确映射"
    )
    parser.add_argument(
        "--usd-path",
        type=str,
        help="RobotLab的USD文件路径（用于提取body names）"
    )
    parser.add_argument(
        "--robotlab-npz",
        type=str,
        help="RobotLab的npz输出（用于提取body names或应用映射）"
    )
    parser.add_argument(
        "--robotlab-bodies",
        type=str,
        nargs='+',
        help="手动指定RobotLab的65个body names（按顺序）"
    )
    parser.add_argument(
        "--output-mapping",
        type=str,
        default="body_mapping_65_to_54.py",
        help="输出映射文件路径"
    )
    parser.add_argument(
        "--apply-to-npz",
        type=str,
        help="应用映射到指定的npz文件（输出到--output-npz）"
    )
    parser.add_argument(
        "--output-npz",
        type=str,
        help="映射后的npz文件输出路径"
    )
    
    args = parser.parse_args()
    
    # 获取RobotLab的body names
    robotlab_bodies = None
    
    if args.robotlab_bodies:
        # 手动指定
        robotlab_bodies = args.robotlab_bodies
        print(f"使用手动指定的body names ({len(robotlab_bodies)}个)")
    elif args.usd_path:
        # 从USD提取
        print(f"从USD文件提取body names: {args.usd_path}")
        robotlab_bodies = extract_body_names_from_usd(args.usd_path)
    elif args.robotlab_npz:
        # 从npz提取
        print(f"从npz文件提取body names: {args.robotlab_npz}")
        robotlab_bodies = extract_body_names_from_npz(args.robotlab_npz)
    else:
        print("错误: 必须提供以下之一:")
        print("  --usd-path: USD文件路径")
        print("  --robotlab-npz: 包含body_names的npz文件")
        print("  --robotlab-bodies: 手动指定body names列表")
        return
    
    if robotlab_bodies is None:
        print("错误: 无法获取RobotLab的body names")
        return
    
    if len(robotlab_bodies) != 65:
        print(f"警告: RobotLab body数量为{len(robotlab_bodies)}，期望65")
    
    # 创建映射
    mapping = create_body_mapping(robotlab_bodies, WEAVE_BODY_NAMES)
    
    # 保存映射
    if args.output_mapping:
        save_mapping_to_file(mapping, args.output_mapping)
    
    # 如果指定，应用映射到npz
    if args.apply_to_npz and args.output_npz:
        apply_mapping_to_npz(args.apply_to_npz, args.output_npz, mapping)
    
    # 打印使用说明
    print(f"\n{'='*60}")
    print("后续使用")
    print(f"{'='*60}")
    print("\n1. 在convert_robotlab_to_weave.py中使用此映射:")
    print(f"   from {Path(args.output_mapping).stem} import BODY_MAPPING_65_TO_54")
    print(f"   weave_bodies = robotlab_bodies[:, BODY_MAPPING_65_TO_54, :]")
    
    print("\n2. 或直接使用此脚本映射npz文件:")
    print(f"   python scripts/create_body_mapping.py \\")
    print(f"       --robotlab-npz input.npz \\")
    print(f"       --apply-to-npz input.npz \\")
    print(f"       --output-npz output_54bodies.npz")


if __name__ == "__main__":
    main()
