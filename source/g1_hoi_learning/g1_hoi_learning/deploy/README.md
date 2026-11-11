# Sim2Sim & Sim2Real Deployment

这个目录包含用于验证和部署训练好的 policy 的代码框架。

## 📁 目录结构

```
deploy/
├── __init__.py                  # ObservationInterface 抽象基类
├── isaac_sim_backend.py         # Isaac Sim backend (Sim2Sim)
├── mujoco_backend.py            # MuJoCo backend (Sim2Sim)
├── real_robot_backend.py        # Real Robot backend (Sim2Real)
├── policy_runner.py             # 统一的 policy 推理引擎
└── README.md                    # 本文件
```

## 🎯 设计思路

### 三层抽象

```
Policy (TorchScript)
    ↓
ObservationInterface (统一接口)
    ↓
Backend (IsaacSim/MuJoCo/Real)
```

### 关键特性

1. **统一接口**：所有 backend 使用相同的 `ObservationInterface`
2. **代码复用**：90% 的代码在不同 backend 之间共享
3. **真实模拟**：可以添加视觉噪声，验证鲁棒性
4. **多环境验证**：Isaac Sim → MuJoCo → Real Robot

## 🚀 使用方法

### 1. Isaac Sim 验证（直接模式）

使用环境的真实观测（无噪声）：

```bash
python scripts/deploy/sim2sim_validate.py \
    --checkpoint model_5000.pt \
    --num_episodes 5 \
    --max_steps 1000
```

### 2. Isaac Sim 验证（视觉模式）

模拟真实部署场景，添加位姿估计噪声：

```bash
python scripts/deploy/sim2sim_validate.py \
    --checkpoint model_5000.pt \
    --use_vision \
    --pose_noise_pos 0.03 \
    --pose_noise_rot 0.15 \
    --num_episodes 10
```

### 3. MuJoCo 验证（独立物理引擎）

在 MuJoCo 中测试，验证 sim2sim 迁移能力：

```bash
python scripts/deploy/mujoco_validate.py \
    --model_path path/to/g1_robot.xml \
    --motion_file data/train/woodchair_46clip.npz \
    --clip_id 0 \
    --checkpoint model_5000.pt \
    --render
```

**使用视觉模式**：

```bash
python scripts/deploy/mujoco_validate.py \
    --model_path path/to/g1_robot.xml \
    --motion_file data/train/woodchair_46clip.npz \
    --checkpoint model_5000.pt \
    --use_vision \
    --pose_noise_pos 0.03 \
    --pose_noise_rot 0.15 \
    --render
```

参数说明：
- `--model_path`: MuJoCo XML 模型文件路径
- `--motion_file`: 参考运动数据（.npz 文件）
- `--clip_id`: 使用哪个 motion clip（默认 0）
- `--use_vision`: 启用视觉模式，添加噪声
- `--render`: 在 MuJoCo viewer 中渲染

### 4. 使用特定 checkpoint

```bash
# Isaac Sim
python scripts/deploy/sim2sim_validate.py \
    --load_run 2026-11-10_12-34-56 \
    --checkpoint model_10000.pt \
    --use_vision

# MuJoCo
python scripts/deploy/mujoco_validate.py \
    --model_path path/to/robot.xml \
    --motion_file data/train/ladder_8s.npz \
    --load_run 2026-11-10_12-34-56 \
    --checkpoint model_10000.pt
```

### 5. Sim2Real 部署（需要实现硬件接口）

```python
from g1_hoi_learning.deploy.real_robot_backend import RealRobotObservation
from g1_hoi_learning.deploy.policy_runner import PolicyRunner

# 1. 实现你的硬件接口
robot = YourRobotInterface()
pose_estimator = FoundationPose(...)  # 或其他 6D pose estimation
motion_planner = YourMotionPlanner()

# 2. 创建观测接口
obs_interface = RealRobotObservation(
    robot_interface=robot,
    pose_estimator=pose_estimator,
    motion_planner=motion_planner,
    object_id=0,
)

# 3. 加载 policy 并运行
runner = PolicyRunner(
    policy_path="logs/.../exported/policy.pt",
    obs_interface=obs_interface,
    device="cpu",  # 真机通常用 CPU
)

# 4. 运行
runner.run_episode(max_steps=1000)
```

## 📊 观测格式

所有 backend 必须返回以下观测：

```python
{
    "ref_motion_body": torch.Tensor,      # (1, N) - 未来参考运动（身体）
    "ref_motion_object": torch.Tensor,    # (1, M) - 未来参考运动（物体）
    "object_state_actor": torch.Tensor,   # (1, 3+6+num_objects) - 位姿 + object_id
    "robot_proprio": torch.Tensor,        # (1, P) - 本体感受
}
```

### object_state_actor 详细格式

- `[0:3]`: object_pos_b - 物体位置（相对 robot anchor）
- `[3:9]`: object_rot_b - 物体旋转（6D 表示，旋转矩阵前 2 列）
- `[9:]`: object_id - one-hot 编码（区分不同物体）

## 🔧 MuJoCo Backend 说明

### 准备 MuJoCo 模型

1. **导出 G1 机器人模型**：
   - 从 URDF/USD 转换到 MuJoCo XML
   - 工具：`mujoco_menagerie` 或自定义转换脚本

2. **添加物体模型**：
   - 在 XML 中添加操作物体（椅子、梯子等）
   - 确保物体有正确的质量、惯性

3. **配置传感器**：
   - 在 base link 添加 gyro 传感器（角速度）
   - 可选：添加力传感器、相机

### MuJoCo 模型示例结构

```xml
<mujoco model="g1_hoi">
  <worldbody>
    <!-- Robot -->
    <body name="pelvis" pos="0 0 1">
      <joint type="free"/>
      <geom type="box" size="0.1 0.15 0.05"/>
      <!-- ... other robot bodies ... -->
    </body>
    
    <!-- Object -->
    <body name="object" pos="0.5 0 0.5">
      <joint type="free"/>
      <geom type="mesh" mesh="chair"/>
    </body>
  </worldbody>
  
  <sensor>
    <gyro site="imu_site"/>
  </sensor>
  
  <actuator>
    <position joint="left_hip_pitch" kp="100"/>
    <!-- ... other actuators ... -->
  </actuator>
</mujoco>
```

### 从 Isaac Sim 导出 Motion 数据

MuJoCo backend 需要与训练时相同格式的 motion 数据：

```python
# motion .npz 文件需要包含：
{
    "joint_pos": (T, 53),           # 关节位置
    "joint_vel": (T, 53),           # 关节速度
    "object_pos_w": (T, 3),         # 物体位置（世界坐标）
    "object_quat_w": (T, 4),        # 物体四元数（世界坐标）
    "body_pos_w": (T, 54, 3),       # 身体位置（世界坐标）
    "body_quat_w": (T, 54, 4),      # 身体四元数（世界坐标）
    "motion_lengths": [T],          # 每个 clip 的长度
    "object_names": ["chair"],      # 物体名称
}
```

## ✅ 验证清单

在真机部署前，确认测试通过：

### Isaac Sim 验证
- [ ] 直接模式（无噪声）：Policy 能成功完成任务
- [ ] 视觉模式（±3cm, ±8.6°）：Policy 对噪声鲁棒
- [ ] 多物体测试：不同 object_id 下都能工作

### MuJoCo 验证（Sim2Sim Transfer）
- [ ] 直接模式：在 MuJoCo 中能运行
- [ ] 视觉模式：对噪声鲁棒
- [ ] 物理差异容忍：能适应不同物理引擎

### 性能验证
- [ ] 推理速度：达到控制频率要求（通常 20-50 Hz）
- [ ] 导出的 TorchScript policy 可以加载并运行
- [ ] CPU 推理速度满足要求（真机通常不用 GPU）

## 🎓 最佳实践

### 1. 渐进式验证策略

```
训练 (Isaac Sim)
    ↓
直接模式验证 (Isaac Sim, no noise)
    ↓
视觉模式验证 (Isaac Sim, with noise)
    ↓
MuJoCo 验证 (different physics)
    ↓
真机部署
```

### 2. MuJoCo 的优势

- **独立验证**：不同于训练环境，测试 sim2sim 迁移
- **快速迭代**：比 Isaac Sim 启动更快
- **轻量级**：不需要 GPU，适合 CPU 测试
- **真实物理**：MuJoCo 的接触模型更接近真实

### 3. 调试技巧

**观测对齐检查**：

```python
# 比较 Isaac Sim 和 MuJoCo 的观测
isaac_obs = isaac_interface.get_observation()
mujoco_obs = mujoco_interface.get_observation()

for key in isaac_obs:
    diff = torch.abs(isaac_obs[key] - mujoco_obs[key]).mean()
    print(f"{key}: mean diff = {diff:.4f}")
```

**动作对齐检查**：

```python
# 在两个环境中应用相同动作，对比结果
action = policy(obs)
isaac_next = isaac_env.step(action)
mujoco_next = mujoco_env.step(action)
```

### 4. 安全第一

- 真机测试前设置紧急停止
- 从低速、小幅度动作开始
- 逐步增加任务难度
- 持续监控观测质量

## 📚 相关文档

- [REAL_WORLD_DEPLOYMENT.md](../../../REAL_WORLD_DEPLOYMENT.md) - 完整的真机部署指南
- 训练配置: `configs/track/train_real_world.yaml`
- 观测定义: `tasks/hoi/mdp/observations.py`

## 🛠️ 常见问题

### Q: 为什么需要 MuJoCo 验证？
**A**: MuJoCo 提供独立的物理引擎，验证 policy 在不同仿真环境下的鲁棒性。如果在 MuJoCo 中失败，说明 policy 过拟合了 Isaac Sim 的物理特性。

### Q: MuJoCo 模型难以准备怎么办？
**A**: 可以跳过 MuJoCo，直接从 Isaac Sim (vision mode) → Real Robot。但 MuJoCo 是一个很好的中间验证步骤。

### Q: 推理速度不够怎么办？
**A**: 
- 使用 `torch.jit.optimize_for_inference(policy)`
- 减小网络大小（训练时调整 hidden_dim）
- 使用量化 (torch quantization)
- 考虑 ONNX Runtime 或 TensorRT

