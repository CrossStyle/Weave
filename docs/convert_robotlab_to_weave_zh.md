# RobotLab Motion Data 转换为 Weave 格式指南

本指南说明如何将RobotLab的pkl motion data转换为Weave所需的格式。

## 📊 格式对比

### RobotLab格式（pkl_to_nqz_inspire.py生成）

```python
{
    'fps': [50],                           # (1,) 帧率
    'base_pos': (N, 3),                   # 机器人根部位置
    'base_rot': (N, 4),                   # 机器人根部四元数
    'joint_pos': (N, num_joints),         # 关节位置（包含手指）
    'joint_vel': (N, num_joints),         # 关节速度
    'body_pos_w': (N, num_bodies, 3),    # Body位置
    'body_quat_w': (N, num_bodies, 4),   # Body四元数
    'body_lin_vel_w': (N, num_bodies, 3), # Body线速度
    'body_ang_vel_w': (N, num_bodies, 3), # Body角速度
    'object_base_pos': (N, 3),            # 物体位置
    'object_base_rot': (N, 4),            # 物体四元数
    'object_base_lin_vel': (N, 3),        # 物体线速度
    'object_base_ang_vel': (N, 3),        # 物体角速度
    'left_gripper': (N,),                 # 左手抓取状态 (-1 or 1)
    'right_gripper': (N,),                # 右手抓取状态
    'contact': (N, num_bodies),           # 接触力
}
```

### Weave格式

```python
{
    'fps': (1,),                           # 帧率
    'joint_pos': (total_frames, 53),      # 关节位置（53个，不含手指）
    'joint_vel': (total_frames, 53),      # 关节速度
    'body_pos_w': (total_frames, 54, 3),  # 54个body的位置
    'body_quat_w': (total_frames, 54, 4), # Body四元数
    'body_lin_vel_w': (total_frames, 54, 3),
    'body_ang_vel_w': (total_frames, 54, 3),
    'object_pos_w': (total_frames, 3),    # 物体位置（单个物体）
    'object_quat_w': (total_frames, 4),   # 物体四元数
    'object_lin_vel_w': (total_frames, 3),
    'object_ang_vel_w': (total_frames, 3),
    'contact_label': (total_frames, 54),   # 接触标签
    'motion_lengths': (num_clips,),        # 每个clip的长度
    'motion_names': (num_clips,),          # 每个clip的名称（可选）
    'object_names': (num_clips,),          # 每个clip对应的物体名称
}
```

## 🔍 关键差异

### 1. **根部状态的表示**
- **RobotLab**: 使用独立的 `base_pos` 和 `base_rot`
- **Weave**: 根部状态包含在 `body_pos_w` 和 `body_quat_w` 中（通常是第0个body）

### 2. **关节数量**
- **RobotLab**: 可能包含手指关节（例如：29 body + 24 finger = 53 joints）
- **Weave**: 53个关节，具体配置取决于机器人定义

⚠️ **重要**: 需要确认两边使用的机器人配置是否一致！

### 3. **物体命名**
- **RobotLab**: 使用如 `h_frame`, `pallet` 等
- **Weave**: 需要对应到 `objects/` 目录下的物体名称

### 4. **多Clip支持**
- **RobotLab**: 每个npz通常是单个motion
- **Weave**: 一个npz可以包含多个clips，通过 `motion_lengths` 索引

## 🛠️ 转换步骤

### 步骤1: 检查机器人配置

首先需要确认两个项目使用的机器人关节定义是否一致。

**检查RobotLab的机器人配置:**
```python
# 在RobotLab项目中查看
# mycode/scene_cfg.py 中的 UNITREE_G1_INSPPIRE_CFG
# 或运行生成脚本时打印joint_names
```

**检查Weave的机器人配置:**
```python
# 在Weave项目中
import numpy as np
data = np.load('data/train/woodchair_987clip.npz', allow_pickle=True)
print("Weave joint count:", data['joint_pos'].shape[1])  # 应该是53
print("Weave body count:", data['body_pos_w'].shape[1])  # 应该是54
```

### 步骤2: 准备物体数据

确保RobotLab中使用的物体在Weave中也存在：

```bash
# 如果RobotLab使用的是 h_frame，需要在Weave中创建对应物体
# 假设RobotLab的物体名称是 "HFrame"，Weave使用 "h_frame"

# 1. 准备物体的USD、surface.npy、sdf_128.npz
# 参考之前创建的物体数据准备工具

# 2. 确保物体名称映射正确
# RobotLab: "HFrame" -> Weave: "h_frame"
```

### 步骤3: 转换Motion数据

使用转换脚本：

```bash
# 单个motion
python scripts/convert_robotlab_to_weave.py \
    --input path/to/robotlab/h_frame_mode3.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame \
    --motion-names "h_frame_frontcarry"

# 多个motions合并
python scripts/convert_robotlab_to_weave.py \
    --input \
        robotlab_data/h_frame_mode3.npz \
        robotlab_data/h_frame_mode4.npz \
    --output data/custom/h_frame_2clip.npz \
    --object-name h_frame \
    --motion-names \
        "h_frame_frontcarry" \
        "h_frame_lowcarry"
```

### 步骤4: 验证转换结果

```python
import numpy as np

# 加载转换后的数据
data = np.load('data/custom/h_frame_1clip.npz', allow_pickle=True)

# 检查基本信息
print("Keys:", list(data.keys()))
print("Total frames:", data['joint_pos'].shape[0])
print("Joint dimensions:", data['joint_pos'].shape[1])  # 应该是53
print("Body count:", data['body_pos_w'].shape[1])       # 应该是54
print("Number of clips:", len(data['motion_lengths']))
print("Motion lengths:", data['motion_lengths'])
print("Object names:", data['object_names'])
print("FPS:", data['fps'][0])

# 检查数值范围
print("\nValue ranges:")
print(f"  joint_pos: [{data['joint_pos'].min():.3f}, {data['joint_pos'].max():.3f}]")
print(f"  body_pos_w: [{data['body_pos_w'].min():.3f}, {data['body_pos_w'].max():.3f}]")
print(f"  object_pos_w: [{data['object_pos_w'].min():.3f}, {data['object_pos_w'].max():.3f}]")

# 检查是否有NaN或Inf
for key in data.keys():
    if hasattr(data[key], 'dtype') and np.issubdtype(data[key].dtype, np.floating):
        if np.any(np.isnan(data[key])):
            print(f"WARNING: {key} contains NaN!")
        if np.any(np.isinf(data[key])):
            print(f"WARNING: {key} contains Inf!")
```

### 步骤5: 在Weave中测试

```bash
# 可视化motion
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/h_frame_1clip.npz

# 或在训练配置中使用
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[./data/custom/h_frame_1clip.npz]
```

## ⚠️ 常见问题

### Q1: 关节数量不匹配

**问题**: RobotLab的关节数量与Weave不同

**原因**: 两个项目使用的机器人配置可能不同（是否包含手指关节）

**解决方案**:
1. 检查两边的机器人URDF/USD配置
2. 修改转换脚本中的 `get_joint_mapping()` 函数
3. 确保关节顺序一致

```python
def get_joint_mapping(robotlab_robot: str, weave_robot: str) -> tuple:
    if robotlab_robot == "g1_inspire" and weave_robot == "g1":
        # 方案1: 如果RobotLab有29个body关节，需要填充到53
        robotlab_body_joints = 29
        weave_total_joints = 53
        
        # 使用前29个关节，其余填充为0
        joint_indices = list(range(robotlab_body_joints))
        return joint_indices, weave_total_joints
        
        # 方案2: 如果关节数量完全匹配
        # return list(range(53)), 53
```

### Q2: Body数量不匹配

**问题**: RobotLab和Weave的body数量不同

**检查**:
```python
# RobotLab
robotlab_data = np.load('robotlab_output.npz')
print("RobotLab bodies:", robotlab_data['body_pos_w'].shape[1])

# Weave
weave_data = np.load('data/train/woodchair_987clip.npz')
print("Weave bodies:", weave_data['body_pos_w'].shape[1])
```

**解决方案**: 
- 确认是否使用了相同的机器人模型
- 可能需要重新生成RobotLab数据，使用与Weave一致的机器人配置

### Q3: 物体名称映射

**问题**: RobotLab和Weave使用不同的物体名称

**映射表**（示例）:
```python
OBJECT_NAME_MAPPING = {
    'HFrame': 'h_frame',
    'Pallet': 'pallet',
    'SmallBox': 'smallbox',
    'Stool': 'stool',
    'Chair': 'chair',
    # 添加其他映射
}
```

在转换脚本中使用：
```python
robotlab_obj_name = "HFrame"
weave_obj_name = OBJECT_NAME_MAPPING.get(robotlab_obj_name, robotlab_obj_name.lower())
```

### Q4: 坐标系不一致

**问题**: 两个项目可能使用不同的坐标系（Y-up vs Z-up）

**检查**:
- 查看生成的motion，物体或机器人是否"躺着"或旋转了90度
- 比较两个项目的ground plane设置

**解决方案**:
如果需要坐标系转换：
```python
def transform_coordinates(pos, quat, from_up='Z', to_up='Y'):
    """坐标系转换"""
    if from_up == to_up:
        return pos, quat
    
    # Z-up to Y-up: 绕X轴旋转-90度
    if from_up == 'Z' and to_up == 'Y':
        R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        pos_new = pos @ R.T
        # 四元数也需要相应转换
        # ... (需要实现四元数旋转)
        return pos_new, quat_new
```

### Q5: FPS不匹配

**问题**: RobotLab和Weave使用不同的FPS

**解决方案**:
- 在RobotLab的 `pkl_to_nqz_inspire.py` 中已经有重采样功能
- 确保 `--output_fps` 设置为Weave期望的FPS（通常是50或60）

## 📋 完整工作流程

```bash
# 1. 从RobotLab生成初始npz
cd RobotLab
python scripts/tools/beyondmimic/pkl_to_nqz_inspire.py \
    --input_file path/to/pkl_data \
    --output_name output/h_frame_motion.npz \
    --input_fps 50 \
    --output_fps 50 \
    --frame_range 7900 9570

# 2. 转换为Weave格式
cd Weave
python scripts/convert_robotlab_to_weave.py \
    --input ../RobotLab/output/h_frame_motion.npz \
    --output data/custom/h_frame_1clip.npz \
    --object-name h_frame

# 3. 准备物体数据（如果还没有）
python scripts/generate_object_data.py \
    --mesh path/to/h_frame.stl \
    --output objects_data/h_frame \
    --name h_frame

python scripts/convert_mesh_to_usd.py \
    --input path/to/h_frame.stl \
    --output objects_data/h_frame/h_frame.usd \
    --scale 0.001

# 4. 部署到Weave
cp -r objects_data/h_frame source/g1_hoi_learning/g1_hoi_learning/objects/

# 5. 注册物体（手动编辑）
# 编辑 objects/__init__.py
# 编辑 objects/object_cfg.py

# 6. 测试
python scripts/visualize_reference_motion.py \
    --motion_file data/custom/h_frame_1clip.npz

# 7. 训练
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[./data/custom/h_frame_1clip.npz]
```

## 🔧 高级选项

### 批量转换多个motions

```python
# create_batch_conversion.py
import subprocess
from pathlib import Path

robotlab_motions = [
    ('h_frame_mode3.npz', 'h_frame', 'frontcarry'),
    ('h_frame_mode4.npz', 'h_frame', 'lowcarry'),
    ('pallet_mode1.npz', 'pallet', 'walk'),
    ('pallet_mode2.npz', 'pallet', 'carry'),
]

for input_file, obj_name, motion_name in robotlab_motions:
    output_file = f'data/custom/{obj_name}_{motion_name}.npz'
    cmd = [
        'python', 'scripts/convert_robotlab_to_weave.py',
        '--input', f'../RobotLab/output/{input_file}',
        '--output', output_file,
        '--object-name', obj_name,
        '--motion-names', motion_name
    ]
    subprocess.run(cmd)
    print(f'✓ Converted {input_file} -> {output_file}')
```

### 合并多个物体的motions

```bash
# 为不同物体创建多个训练文件
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_data/h_frame_*.npz \
    --output data/custom/h_frame_multiclip.npz \
    --object-name h_frame

python scripts/convert_robotlab_to_weave.py \
    --input robotlab_data/pallet_*.npz \
    --output data/custom/pallet_multiclip.npz \
    --object-name pallet

# 在训练时使用多个文件
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name train \
    env.commands.motion.motion_files=[\
        ./data/custom/h_frame_multiclip.npz,\
        ./data/custom/pallet_multiclip.npz\
    ]
```

## 💡 最佳实践

1. **先用单个短motion测试**: 验证整个pipeline是否正确
2. **检查可视化**: 使用 `visualize_reference_motion.py` 确认motion看起来正常
3. **验证关节范围**: 确保关节角度在合理范围内
4. **保持命名一致**: 物体名称在RobotLab和Weave中保持一致
5. **备份原始数据**: 转换前备份RobotLab的输出

## 📞 需要帮助？

如果遇到转换问题：
1. 检查本文档的"常见问题"部分
2. 验证机器人配置是否一致
3. 使用验证脚本检查数据格式
4. 查看RobotLab和Weave的机器人定义文件

转换成功的标志：
- ✅ 数据形状匹配Weave格式
- ✅ 可视化motion正常显示
- ✅ 训练可以正常启动
- ✅ 没有NaN或Inf值

祝转换顺利！🚀
