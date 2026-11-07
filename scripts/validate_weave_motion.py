"""
验证RobotLab到Weave的转换结果
"""

import argparse
import numpy as np
from pathlib import Path


def validate_weave_format(npz_path: str) -> bool:
    """验证npz文件是否符合Weave格式"""
    
    print(f"\n{'='*60}")
    print(f"验证Weave格式: {npz_path}")
    print(f"{'='*60}\n")
    
    try:
        data = np.load(npz_path, allow_pickle=True)
    except Exception as e:
        print(f"❌ 无法加载文件: {e}")
        return False
    
    # 必需字段
    required_keys = [
        'joint_pos', 'joint_vel',
        'body_pos_w', 'body_quat_w', 'body_lin_vel_w', 'body_ang_vel_w',
        'object_pos_w', 'object_quat_w', 'object_lin_vel_w', 'object_ang_vel_w',
        'contact_label', 'motion_lengths', 'object_names', 'fps'
    ]
    
    all_valid = True
    
    # 1. 检查必需字段
    print("1. 检查必需字段:")
    missing_keys = [k for k in required_keys if k not in data.keys()]
    if missing_keys:
        print(f"   ❌ 缺少字段: {missing_keys}")
        all_valid = False
    else:
        print(f"   ✓ 所有必需字段存在")
    
    # 2. 检查数据形状
    print("\n2. 检查数据形状:")
    
    total_frames = data['joint_pos'].shape[0]
    print(f"   总帧数: {total_frames}")
    
    # 关节
    joint_shape = data['joint_pos'].shape
    print(f"   joint_pos: {joint_shape}")
    if joint_shape[1] == 53:
        print(f"      ✓ 关节数量正确 (53)")
    else:
        print(f"      ⚠ 关节数量: {joint_shape[1]}，期望53")
        all_valid = False
    
    # Bodies
    body_shape = data['body_pos_w'].shape
    print(f"   body_pos_w: {body_shape}")
    if body_shape[1] == 54:
        print(f"      ✓ Body数量正确 (54)")
    elif body_shape[1] == 30:
        print(f"      ⚠ Body数量: {body_shape[1]}，期望54（但30也可能是正常的）")
    else:
        print(f"      ⚠ Body数量: {body_shape[1]}，期望54")
    
    # Object
    object_shape = data['object_pos_w'].shape
    print(f"   object_pos_w: {object_shape}")
    if object_shape == (total_frames, 3):
        print(f"      ✓ Object形状正确")
    else:
        print(f"      ❌ Object形状错误，期望 ({total_frames}, 3)")
        all_valid = False
    
    # 3. 检查一致性
    print("\n3. 检查帧数一致性:")
    frame_keys = ['joint_pos', 'joint_vel', 'body_pos_w', 'body_quat_w',
                  'object_pos_w', 'object_quat_w', 'contact_label']
    
    inconsistent = []
    for key in frame_keys:
        if data[key].shape[0] != total_frames:
            inconsistent.append(f"{key}: {data[key].shape[0]}")
    
    if inconsistent:
        print(f"   ❌ 帧数不一致: {inconsistent}")
        all_valid = False
    else:
        print(f"   ✓ 所有帧数一致")
    
    # 4. 检查motion_lengths
    print("\n4. 检查motion信息:")
    num_clips = len(data['motion_lengths'])
    print(f"   Clips数量: {num_clips}")
    print(f"   Motion lengths: {data['motion_lengths']}")
    print(f"   Object names: {data['object_names']}")
    
    if data['motion_lengths'].sum() == total_frames:
        print(f"   ✓ Motion lengths总和匹配总帧数")
    else:
        print(f"   ❌ Motion lengths总和({data['motion_lengths'].sum()}) != 总帧数({total_frames})")
        all_valid = False
    
    # 5. 检查数值范围
    print("\n5. 检查数值范围:")
    
    # 检查NaN和Inf
    has_issues = False
    for key in ['joint_pos', 'joint_vel', 'body_pos_w', 'object_pos_w']:
        if np.any(np.isnan(data[key])):
            print(f"   ❌ {key} 包含NaN")
            has_issues = True
        if np.any(np.isinf(data[key])):
            print(f"   ❌ {key} 包含Inf")
            has_issues = True
    
    if not has_issues:
        print(f"   ✓ 无NaN或Inf值")
    else:
        all_valid = False
    
    # 打印数值范围
    print(f"\n   数值范围:")
    print(f"   joint_pos: [{data['joint_pos'].min():.3f}, {data['joint_pos'].max():.3f}]")
    print(f"   body_pos_w: [{data['body_pos_w'].min():.3f}, {data['body_pos_w'].max():.3f}]")
    print(f"   object_pos_w: [{data['object_pos_w'].min():.3f}, {data['object_pos_w'].max():.3f}]")
    
    # 6. 检查FPS
    print(f"\n6. FPS信息:")
    print(f"   FPS: {data['fps'][0]}")
    if data['fps'][0] in [50, 60]:
        print(f"   ✓ FPS合理")
    else:
        print(f"   ⚠ FPS不常见: {data['fps'][0]}")
    
    # 7. 对比参考数据（如果提供）
    print(f"\n{'='*60}")
    if all_valid:
        print("✓ 验证通过！数据格式正确")
    else:
        print("⚠ 验证发现问题，请检查上述错误")
    print(f"{'='*60}\n")
    
    return all_valid


def compare_with_reference(converted_path: str, reference_path: str):
    """与参考数据对比"""
    
    print(f"\n{'='*60}")
    print(f"与参考数据对比")
    print(f"{'='*60}\n")
    
    converted = np.load(converted_path, allow_pickle=True)
    reference = np.load(reference_path, allow_pickle=True)
    
    print(f"转换数据: {converted_path}")
    print(f"参考数据: {reference_path}\n")
    
    # 对比形状
    print("形状对比:")
    for key in ['joint_pos', 'body_pos_w', 'object_pos_w']:
        if key in converted and key in reference:
            conv_shape = converted[key].shape[1:]  # 跳过帧数维度
            ref_shape = reference[key].shape[1:]
            
            match = "✓" if conv_shape == ref_shape else "❌"
            print(f"  {key}:")
            print(f"    转换: {conv_shape}")
            print(f"    参考: {ref_shape} {match}")
    
    # 对比dtype
    print("\nDtype对比:")
    for key in ['joint_pos', 'body_pos_w', 'object_pos_w']:
        if key in converted and key in reference:
            conv_dtype = converted[key].dtype
            ref_dtype = reference[key].dtype
            
            match = "✓" if conv_dtype == ref_dtype else "⚠"
            print(f"  {key}: {conv_dtype} vs {ref_dtype} {match}")


def main():
    parser = argparse.ArgumentParser(description="验证Weave格式的motion数据")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="要验证的npz文件"
    )
    parser.add_argument(
        "--reference",
        type=str,
        default=None,
        help="参考npz文件（可选，用于对比）"
    )
    
    args = parser.parse_args()
    
    # 验证格式
    is_valid = validate_weave_format(args.input)
    
    # 与参考数据对比（如果提供）
    if args.reference:
        compare_with_reference(args.input, args.reference)
    
    # 返回状态
    exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
