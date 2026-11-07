"""
将RobotLab的pkl motion data转换为Weave所需的npz格式

RobotLab格式（pkl_to_nqz_inspire.py生成的npz）:
- base_pos: (N, 3)
- base_rot: (N, 4)  # quaternion
- joint_pos: (N, num_joints)  # 包含手指关节
- joint_vel: (N, num_joints)
- body_pos_w: (N, num_bodies, 3)
- body_quat_w: (N, num_bodies, 4)
- body_lin_vel_w: (N, num_bodies, 3)
- body_ang_vel_w: (N, num_bodies, 3)
- object_base_pos: (N, 3)
- object_base_rot: (N, 4)
- object_base_lin_vel: (N, 3)
- object_base_ang_vel: (N, 3)
- left_gripper: (N,)  # -1 or 1
- right_gripper: (N,)
- contact: (N, num_bodies)
- fps: [50]

Weave格式（需要的npz）:
- joint_pos: (total_frames, 53)  # G1机器人的关节，不包括手指
- joint_vel: (total_frames, 53)
- body_pos_w: (total_frames, 54, 3)  # 54个body
- body_quat_w: (total_frames, 54, 4)
- body_lin_vel_w: (total_frames, 54, 3)
- body_ang_vel_w: (total_frames, 54, 3)
- object_pos_w: (total_frames, 3)
- object_quat_w: (total_frames, 4)
- object_lin_vel_w: (total_frames, 3)
- object_ang_vel_w: (total_frames, 3)
- contact_label: (total_frames, 54)
- motion_lengths: (num_clips,)
- motion_names: (num_clips,)  # 可选
- object_names: (num_clips,)
- fps: (1,)

关键差异：
1. RobotLab使用base_pos/base_rot，Weave使用body_pos_w中的root body
2. RobotLab的joint_pos包含手指，Weave只包含body joints (53)
3. Weave需要多个clips打包在一起，需要motion_lengths和object_names
"""

import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict


def load_robotlab_motion(npz_path: str) -> Dict[str, np.ndarray]:
    """加载RobotLab格式的motion数据"""
    data = np.load(npz_path, allow_pickle=True)
    return {k: data[k] for k in data.keys()}


def get_joint_mapping(robotlab_robot: str, weave_robot: str) -> tuple:
    """
    获取关节映射关系
    
    返回:
        (robotlab_joint_indices, num_weave_joints)
    """
    if robotlab_robot == "g1_inspire" and weave_robot == "g1_inspire":
        # ✅ 好消息：两者使用完全相同的G1 Inspire配置！
        # RobotLab: 53 joints (29 body + 24 hand)
        # Weave: 53 joints (29 body + 24 hand)
        # 关节定义完全一致，可以直接使用
        
        print("✓ RobotLab和Weave使用相同的G1 Inspire配置")
        print("  - 总关节: 53")
        print("  - Body关节: 29")
        print("  - 手指关节: 24 (左手12 + 右手12)")
        print("  - 直接使用所有关节，无需映射")
        
        return list(range(53)), 53
    
    elif robotlab_robot == "g1_inspire" and weave_robot == "g1":
        # 如果Weave使用不带手指的G1配置
        print("⚠ 注意：Weave使用不带手指的G1配置")
        print("  - 只使用前29个body关节")
        
        # 只取前29个body关节
        return list(range(29)), 29
    
    raise ValueError(f"Unsupported robot mapping: {robotlab_robot} -> {weave_robot}")


def convert_single_motion(
    robotlab_data: Dict[str, np.ndarray],
    motion_name: str,
    object_name: str,
    joint_indices: List[int],
    num_weave_joints: int,
    body_mapping: str = "auto",
    custom_body_indices: List[int] = None,
) -> Dict[str, np.ndarray]:
    """
    转换单个motion clip
    
    Args:
        robotlab_data: RobotLab格式的数据
        motion_name: motion名称
        object_name: 物体名称
        joint_indices: 要使用的关节索引
        num_weave_joints: Weave期望的关节数量
        body_mapping: body映射策略 ("auto", "keep_all", "first_54", "custom")
        custom_body_indices: 自定义body索引映射（当body_mapping="custom"时使用）
    
    Returns:
        Weave格式的数据字典
    """
    num_frames = robotlab_data['joint_pos'].shape[0]
    num_bodies_robotlab = robotlab_data['body_pos_w'].shape[1]
    
    print(f"  转换详情:")
    print(f"    - 帧数: {num_frames}")
    print(f"    - RobotLab关节数: {robotlab_data['joint_pos'].shape[1]}")
    print(f"    - RobotLab bodies: {num_bodies_robotlab}")
    print(f"    - 目标关节数: {num_weave_joints}")
    
    # 提取关节数据
    if robotlab_data['joint_pos'].shape[1] == num_weave_joints:
        joint_pos = robotlab_data['joint_pos']
        joint_vel = robotlab_data['joint_vel']
        print(f"    ✓ 关节数量匹配，直接使用")
    else:
        joint_pos = robotlab_data['joint_pos'][:, joint_indices]
        joint_vel = robotlab_data['joint_vel'][:, joint_indices]
        print(f"    ⚠ 选择前{len(joint_indices)}个关节")
        
        if joint_pos.shape[1] < num_weave_joints:
            pad_width = num_weave_joints - joint_pos.shape[1]
            joint_pos = np.pad(joint_pos, ((0, 0), (0, pad_width)), mode='constant')
            joint_vel = np.pad(joint_vel, ((0, 0), (0, pad_width)), mode='constant')
            print(f"    ⚠ 填充{pad_width}个关节为0")
    
    # 处理body数量差异
    body_pos_w = robotlab_data['body_pos_w']
    body_quat_w = robotlab_data['body_quat_w']
    body_lin_vel_w = robotlab_data['body_lin_vel_w']
    body_ang_vel_w = robotlab_data['body_ang_vel_w']
    contact_label = robotlab_data['contact']
    
    if num_bodies_robotlab != 54:
        print(f"    ⚠ Body数量: {num_bodies_robotlab} (Weave标准是54)")
        
        if body_mapping == "custom" and custom_body_indices is not None:
            # 使用自定义映射（精确映射）
            print(f"    → 使用自定义映射 (65→54)")
            body_pos_w = body_pos_w[:, custom_body_indices, :]
            body_quat_w = body_quat_w[:, custom_body_indices, :]
            body_lin_vel_w = body_lin_vel_w[:, custom_body_indices, :]
            body_ang_vel_w = body_ang_vel_w[:, custom_body_indices, :]
            contact_label = contact_label[:, custom_body_indices]
            print(f"    ✓ 精确映射完成")
            
        elif body_mapping == "first_54" and num_bodies_robotlab > 54:
            # 只取前54个bodies
            print(f"    → 使用前54个bodies")
            body_pos_w = body_pos_w[:, :54, :]
            body_quat_w = body_quat_w[:, :54, :]
            body_lin_vel_w = body_lin_vel_w[:, :54, :]
            body_ang_vel_w = body_ang_vel_w[:, :54, :]
            contact_label = contact_label[:, :54]
            
        elif body_mapping == "keep_all":
            # 保持所有bodies（可能需要Weave支持）
            print(f"    → 保持所有{num_bodies_robotlab}个bodies")
            print(f"    ⚠ 注意：Weave可能需要调整来支持{num_bodies_robotlab}个bodies")
            
        else:  # auto
            if num_bodies_robotlab == 65 and custom_body_indices is not None:
                # 有自定义映射，优先使用
                print(f"    → 检测到65个bodies，使用自定义映射")
                body_pos_w = body_pos_w[:, custom_body_indices, :]
                body_quat_w = body_quat_w[:, custom_body_indices, :]
                body_lin_vel_w = body_lin_vel_w[:, custom_body_indices, :]
                body_ang_vel_w = body_ang_vel_w[:, custom_body_indices, :]
                contact_label = contact_label[:, custom_body_indices]
            elif num_bodies_robotlab == 65:
                # 没有自定义映射，建议用户创建
                print(f"    → 检测到65个bodies（RobotLab USD模型）")
                print(f"    → 建议：使用create_body_mapping.py创建精确映射")
                print(f"    → 当前：保持所有65个bodies")
            else:
                print(f"    → 保持原始{num_bodies_robotlab}个bodies")
    else:
        print(f"    ✓ Body数量匹配 (54)")
    
    # 构建Weave格式
    weave_data = {
        'joint_pos': joint_pos.astype(np.float32),
        'joint_vel': joint_vel.astype(np.float32),
        'body_pos_w': body_pos_w.astype(np.float32),
        'body_quat_w': body_quat_w.astype(np.float32),
        'body_lin_vel_w': body_lin_vel_w.astype(np.float32),
        'body_ang_vel_w': body_ang_vel_w.astype(np.float32),
        'object_pos_w': robotlab_data['object_base_pos'].astype(np.float32),
        'object_quat_w': robotlab_data['object_base_rot'].astype(np.float32),
        'object_lin_vel_w': robotlab_data['object_base_lin_vel'].astype(np.float32),
        'object_ang_vel_w': robotlab_data['object_base_ang_vel'].astype(np.float32),
        'contact_label': contact_label.astype(np.float32),
        'motion_lengths': np.array([num_frames], dtype=np.int32),
        'motion_names': np.array([motion_name], dtype=object),
        'object_names': np.array([object_name], dtype=object),
        'fps': robotlab_data['fps'],
    }
    
    print(f"    → 输出body数量: {weave_data['body_pos_w'].shape[1]}")
    
    return weave_data


def split_motion_by_duration(
    weave_data: Dict[str, np.ndarray],
    segment_duration: float,
    overlap_duration: float = 0.0,
    base_name: str = "segment",
) -> Dict[str, np.ndarray]:
    """
    按照指定时长切分motion
    
    Args:
        weave_data: Weave格式的单个motion数据
        segment_duration: 每段的时长（秒）
        overlap_duration: 段之间的重叠时长（秒）
        base_name: 切分后的motion名称前缀
    
    Returns:
        切分后的Weave格式数据（包含多个clips）
    """
    fps = int(weave_data['fps'][0])
    total_frames = weave_data['joint_pos'].shape[0]
    total_duration = total_frames / fps
    
    # 计算每段的帧数
    segment_frames = int(segment_duration * fps)
    overlap_frames = int(overlap_duration * fps)
    step_frames = segment_frames - overlap_frames
    
    if segment_frames <= 0:
        raise ValueError(f"segment_duration too small: {segment_duration}s = {segment_frames} frames")
    
    if overlap_frames >= segment_frames:
        raise ValueError(f"overlap_duration ({overlap_duration}s) must be less than segment_duration ({segment_duration}s)")
    
    print(f"\n切分motion:")
    print(f"  总帧数: {total_frames} ({total_duration:.2f}s @ {fps}fps)")
    print(f"  段长度: {segment_frames} frames ({segment_duration:.2f}s)")
    print(f"  重叠: {overlap_frames} frames ({overlap_duration:.2f}s)")
    print(f"  步进: {step_frames} frames")
    
    # 计算切分点
    segments = []
    start_frame = 0
    segment_idx = 0
    
    while start_frame < total_frames:
        end_frame = min(start_frame + segment_frames, total_frames)
        actual_frames = end_frame - start_frame
        
        # 如果最后一段太短（小于segment_frames的50%），跳过
        if actual_frames < segment_frames * 0.5 and len(segments) > 0:
            print(f"  ⚠ 跳过最后一段（太短: {actual_frames} frames）")
            break
        
        segments.append((start_frame, end_frame, f"{base_name}_{segment_idx:03d}"))
        segment_idx += 1
        start_frame += step_frames
    
    print(f"  切分为 {len(segments)} 段:")
    for start, end, name in segments:
        duration = (end - start) / fps
        print(f"    {name}: frames [{start}:{end}] ({duration:.2f}s)")
    
    # 切分数据
    concat_keys = [
        'joint_pos', 'joint_vel', 
        'body_pos_w', 'body_quat_w', 'body_lin_vel_w', 'body_ang_vel_w',
        'object_pos_w', 'object_quat_w', 'object_lin_vel_w', 'object_ang_vel_w',
        'contact_label'
    ]
    
    split_data = {}
    for key in concat_keys:
        split_data[key] = np.concatenate(
            [weave_data[key][start:end] for start, end, _ in segments],
            axis=0
        )
    
    # 构建元数据
    split_data['motion_lengths'] = np.array([end - start for start, end, _ in segments], dtype=np.int32)
    split_data['motion_names'] = np.array([name for _, _, name in segments], dtype=object)
    split_data['object_names'] = np.array([weave_data['object_names'][0]] * len(segments), dtype=object)
    split_data['fps'] = weave_data['fps']
    
    return split_data


def merge_multiple_motions(motion_list: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    """
    合并多个motion clips
    
    Args:
        motion_list: Weave格式的motion数据列表
    
    Returns:
        合并后的数据
    """
    if len(motion_list) == 0:
        raise ValueError("motion_list is empty")
    
    if len(motion_list) == 1:
        return motion_list[0]
    
    # 合并所有帧数据
    merged = {}
    
    # 需要concatenate的字段
    concat_keys = [
        'joint_pos', 'joint_vel', 
        'body_pos_w', 'body_quat_w', 'body_lin_vel_w', 'body_ang_vel_w',
        'object_pos_w', 'object_quat_w', 'object_lin_vel_w', 'object_ang_vel_w',
        'contact_label'
    ]
    
    for key in concat_keys:
        merged[key] = np.concatenate([m[key] for m in motion_list], axis=0)
    
    # 合并元数据
    merged['motion_lengths'] = np.concatenate([m['motion_lengths'] for m in motion_list])
    merged['motion_names'] = np.concatenate([m['motion_names'] for m in motion_list])
    merged['object_names'] = np.concatenate([m['object_names'] for m in motion_list])
    merged['fps'] = motion_list[0]['fps']  # 假设所有motion使用相同fps
    
    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Convert RobotLab motion to Weave format, or split existing Weave motion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 转换RobotLab格式到Weave格式
  python convert_robotlab_to_weave.py --input motion.npz --output output.npz --object-name ladder
  
  # 转换并切分成5秒片段
  python convert_robotlab_to_weave.py --input motion.npz --output output.npz --object-name ladder --split-duration 5.0
  
  # 只切分已有的Weave文件
  python convert_robotlab_to_weave.py --split-only --input ladder_weave.npz --output ladder_split.npz --split-duration 5.0
        """
    )
    parser.add_argument(
        "--input",
        type=str,
        nargs='+',
        required=True,
        help="Input RobotLab npz file(s), or Weave npz file (when using --split-only)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output Weave npz file"
    )
    parser.add_argument(
        "--split-only",
        action="store_true",
        help="只切分已有的Weave格式motion文件，不进行RobotLab转换"
    )
    parser.add_argument(
        "--object-name",
        type=str,
        required=True,
        help="Object name (e.g., 'h_frame', 'woodchair')"
    )
    parser.add_argument(
        "--motion-names",
        type=str,
        nargs='+',
        default=None,
        help="Motion names for each input file (optional)"
    )
    parser.add_argument(
        "--robotlab-robot",
        type=str,
        default="g1_inspire",
        help="RobotLab robot type (default: g1_inspire)"
    )
    parser.add_argument(
        "--weave-robot",
        type=str,
        default="g1_inspire",
        help="Weave robot type (default: g1_inspire, 也可以是 g1 如果只用body关节)"
    )
    parser.add_argument(
        "--body-mapping",
        type=str,
        default="auto",
        choices=["auto", "keep_all", "first_54", "custom"],
        help="Body映射策略: auto(自动), keep_all(保持所有65个), first_54(只用前54个), custom(使用精确映射)"
    )
    parser.add_argument(
        "--body-mapping-file",
        type=str,
        default=None,
        help="精确body映射文件路径（当--body-mapping=custom时使用，例如body_mapping_65_to_54.py）"
    )
    parser.add_argument(
        "--split-duration",
        type=float,
        default=None,
        help="切分motion的时长（秒）。如果指定，会将每个motion按此时长切分成多个片段"
    )
    parser.add_argument(
        "--split-overlap",
        type=float,
        default=0.0,
        help="切分时的重叠时长（秒，默认0）。可以让相邻片段有平滑过渡"
    )
    
    args = parser.parse_args()
    
    # 如果是只切分模式
    if args.split_only:
        if args.split_duration is None:
            raise ValueError("--split-only mode requires --split-duration")
        
        if len(args.input) != 1:
            raise ValueError("--split-only mode only supports single input file")
        
        input_file = Path(args.input[0])
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        print(f"\n{'='*60}")
        print(f"Split Weave motion file")
        print(f"{'='*60}")
        print(f"Input: {input_file}")
        print(f"Output: {args.output}")
        print(f"Segment duration: {args.split_duration}s")
        print(f"Overlap duration: {args.split_overlap}s")
        
        # 加载Weave格式数据
        print(f"\nLoading Weave motion data...")
        weave_data = dict(np.load(input_file, allow_pickle=True))
        
        total_frames = weave_data['joint_pos'].shape[0]
        num_clips = len(weave_data['motion_lengths'])
        fps = int(weave_data['fps'][0])
        
        print(f"  Total frames: {total_frames}")
        print(f"  Number of clips: {num_clips}")
        print(f"  FPS: {fps}")
        print(f"  Clip lengths: {weave_data['motion_lengths']}")
        
        # 如果原文件只有一个clip，直接切分
        if num_clips == 1:
            print(f"\nSingle clip detected, splitting directly...")
            split_data = split_motion_by_duration(
                weave_data,
                segment_duration=args.split_duration,
                overlap_duration=args.split_overlap,
                base_name=str(weave_data['motion_names'][0]),
            )
        else:
            # 多个clips，分别切分后合并
            print(f"\nMultiple clips detected, splitting each clip...")
            split_clips = []
            frame_offset = 0
            
            for i, clip_length in enumerate(weave_data['motion_lengths']):
                clip_name = str(weave_data['motion_names'][i])
                print(f"\n  Clip {i}: {clip_name} ({clip_length} frames)")
                
                # 提取单个clip的数据
                clip_data = {}
                for key in ['joint_pos', 'joint_vel', 'body_pos_w', 'body_quat_w', 
                           'body_lin_vel_w', 'body_ang_vel_w', 'object_pos_w', 
                           'object_quat_w', 'object_lin_vel_w', 'object_ang_vel_w', 
                           'contact_label']:
                    clip_data[key] = weave_data[key][frame_offset:frame_offset+clip_length]
                
                clip_data['motion_lengths'] = np.array([clip_length], dtype=np.int32)
                clip_data['motion_names'] = np.array([clip_name], dtype=object)
                clip_data['object_names'] = np.array([weave_data['object_names'][i]], dtype=object)
                clip_data['fps'] = weave_data['fps']
                
                # 切分这个clip
                split_clip = split_motion_by_duration(
                    clip_data,
                    segment_duration=args.split_duration,
                    overlap_duration=args.split_overlap,
                    base_name=clip_name,
                )
                
                split_clips.append(split_clip)
                frame_offset += clip_length
            
            # 合并所有切分后的clips
            print(f"\nMerging all split clips...")
            split_data = merge_multiple_motions(split_clips)
        
        # 保存
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(output_path, **split_data)
        
        print(f"\n{'='*60}")
        print(f"✓ Split complete!")
        print(f"{'='*60}")
        print(f"Output file: {output_path}")
        print(f"Original clips: {num_clips}")
        print(f"Split into: {len(split_data['motion_lengths'])} clips")
        print(f"Clip lengths: {split_data['motion_lengths']}")
        
        return
    
    # 以下是原有的转换逻辑
    # 验证输入
    input_files = [Path(f) for f in args.input]
    for f in input_files:
        if not f.exists():
            raise FileNotFoundError(f"Input file not found: {f}")
    
    # 生成motion names
    if args.motion_names:
        if len(args.motion_names) != len(input_files):
            raise ValueError("Number of motion_names must match number of input files")
        motion_names = args.motion_names
    else:
        motion_names = [f.stem for f in input_files]
    
    print(f"\n{'='*60}")
    print(f"Converting RobotLab motion to Weave format")
    print(f"{'='*60}")
    print(f"Input files: {len(input_files)}")
    print(f"Object name: {args.object_name}")
    print(f"Output: {args.output}")
    
    # 获取关节映射
    joint_indices, num_weave_joints = get_joint_mapping(
        args.robotlab_robot, 
        args.weave_robot
    )
    print(f"\nJoint mapping:")
    print(f"  RobotLab robot: {args.robotlab_robot}")
    print(f"  Weave robot: {args.weave_robot}")
    print(f"  Using joints: {len(joint_indices)}")
    print(f"  Target joints: {num_weave_joints}")
    
    # 加载自定义body映射（如果指定）
    custom_body_indices = None
    if args.body_mapping == "custom":
        if args.body_mapping_file:
            print(f"\n加载自定义body映射: {args.body_mapping_file}")
            try:
                # 动态导入映射文件
                import importlib.util
                spec = importlib.util.spec_from_file_location("body_mapping", args.body_mapping_file)
                body_mapping_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(body_mapping_module)
                custom_body_indices = body_mapping_module.BODY_MAPPING_65_TO_54
                print(f"  ✓ 加载了{len(custom_body_indices)}个body索引的映射")
            except Exception as e:
                print(f"  ❌ 加载映射文件失败: {e}")
                print(f"  将使用auto策略")
                args.body_mapping = "auto"
        else:
            print(f"\n⚠ 警告: 指定了custom映射但未提供--body-mapping-file")
            print(f"  将使用auto策略")
            args.body_mapping = "auto"
    
    # 转换每个motion
    converted_motions = []
    for input_file, motion_name in zip(input_files, motion_names):
        print(f"\nProcessing: {input_file.name}")
        
        # 加载数据
        robotlab_data = load_robotlab_motion(str(input_file))
        print(f"  Loaded {robotlab_data['joint_pos'].shape[0]} frames")
        print(f"  Joints: {robotlab_data['joint_pos'].shape[1]}")
        print(f"  Bodies: {robotlab_data['body_pos_w'].shape[1]}")
        
        # 转换
        weave_data = convert_single_motion(
            robotlab_data,
            motion_name,
            args.object_name,
            joint_indices,
            num_weave_joints,
            body_mapping=args.body_mapping,
            custom_body_indices=custom_body_indices,
        )
        
        # 如果指定了切分时长，进行切分
        if args.split_duration is not None:
            print(f"  应用切分: {args.split_duration}s (overlap: {args.split_overlap}s)")
            weave_data = split_motion_by_duration(
                weave_data,
                segment_duration=args.split_duration,
                overlap_duration=args.split_overlap,
                base_name=motion_name,
            )
            print(f"  ✓ 切分为 {len(weave_data['motion_lengths'])} 个片段")
        
        converted_motions.append(weave_data)
        print(f"  ✓ Converted")
    
    # 合并所有motions
    print(f"\nMerging {len(converted_motions)} motions...")
    merged_data = merge_multiple_motions(converted_motions)
    
    # 保存
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(output_path, **merged_data)
    
    print(f"\n{'='*60}")
    print(f"✓ Conversion complete!")
    print(f"{'='*60}")
    print(f"Output file: {output_path}")
    print(f"Total frames: {merged_data['joint_pos'].shape[0]}")
    print(f"Number of clips: {len(merged_data['motion_lengths'])}")
    print(f"Motion lengths: {merged_data['motion_lengths']}")
    print(f"Object names: {merged_data['object_names']}")
    print(f"FPS: {merged_data['fps'][0]}")
    
    # 验证数据
    print(f"\nData shapes:")
    for key in ['joint_pos', 'joint_vel', 'body_pos_w', 'body_quat_w', 
                'object_pos_w', 'object_quat_w', 'contact_label']:
        print(f"  {key}: {merged_data[key].shape}")
    
    print(f"\nTo use this motion in Weave:")
    print(f"1. Make sure object '{args.object_name}' exists in:")
    print(f"   source/g1_hoi_learning/g1_hoi_learning/objects/{args.object_name}/")
    print(f"2. Update training config to use: {output_path}")


if __name__ == "__main__":
    main()
