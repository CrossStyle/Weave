# Weave真机部署指南

## 问题：为什么不能直接部署当前的policy？

当前的policy使用了以下**仿真特权信息**，真机无法获取：

1. **精确的物体几何信息**：
   - `object_bps_sdf_b`：需要物体的完整SDF网格
   - `object_nearest_point_b`：需要物体表面采样点云

2. **接触力传感器**：
   - `contact`：需要54个body的接触力测量（大部分真机没有）

3. **参考运动轨迹**（motion命令）：
   - 训练时的teacher信号，部署时不可用

## 方案对比

### 方案1：保留位姿 + 视觉估计（推荐优先尝试）✅

**原理**：保留物体位姿作为观测，但通过视觉6D pose estimation获取

**优点**：
- 最容易迁移现有policy
- 不需要重新训练视觉encoder
- 对于需要精确操作的HOI任务效果好

**缺点**：
- 依赖6D pose estimation的准确性
- 需要已知物体CAD模型（或在线重建）

**实施步骤**：

#### 1.1 在仿真中训练鲁棒policy

使用真机可获取的观测 + 添加噪声模拟视觉估计误差：

```bash
# 使用新的配置训练
python scripts/rsl_rl/train.py --task=G1-Inspire-HOI-v0 --headless \
    --config-dir ./configs/track --config-name train_real_world
```

**关键修改**（已在`train_real_world.yaml`中）：
- Actor观测组：`["ref_motion_body", "ref_motion_object", "object_state_actor", "robot_proprio"]`
- 去掉`object_bps_sdf_b`和`object_nearest_point_b`
- 去掉`contact`观测（如果真机没有力传感器）
- 物体位姿添加噪声（±3cm位置，±8.6°旋转）

#### 1.2 修改PPO配置使用简化观测

编辑 `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/agents/rsl_rl_ppo_cfg.py`：

```python
obs_groups: dict = {
    # 真机部署：使用object_state_actor而不是object_state
    "policy": ["ref_motion_body", "ref_motion_object", "object_state_actor", "robot_proprio"],
    "critic": ["ref_motion_body", "ref_motion_object", "object_state", "robot_privileged"],
}
```

#### 1.3 真机部署时的观测接口

在真机上需要实现以下接口：

```python
class RealWorldObservation:
    def __init__(self):
        # 初始化6D pose estimation (如FoundationPose)
        self.pose_estimator = FoundationPose(...)
        
    def get_object_pose(self, rgb, depth):
        """从RGB-D图像估计物体6D位姿"""
        pos, quat = self.pose_estimator.estimate(rgb, depth)
        
        # 转换到robot anchor frame
        pos_b, quat_b = transform_to_anchor_frame(pos, quat, 
                                                   self.robot_anchor_pos,
                                                   self.robot_anchor_quat)
        return pos_b, quat_b
    
    def get_observation(self):
        """构造policy输入"""
        return {
            # 从motion planner获取（或者使用MPC在线规划）
            "ref_motion_body": self.get_reference_motion(),
            "ref_motion_object": self.get_reference_object_motion(),
            
            # 从视觉估计
            "object_state_actor": {
                "object_pos_b": self.object_pos_b,  # (3,)
                "object_rot_b": self.object_rot_b,  # (6,) - rotation matrix前2列
            },
            
            # 从机器人传感器
            "robot_proprio": {
                "base_ang_vel": self.imu.angular_velocity,
                "joint_pos": self.joint_positions,
                "joint_vel": self.joint_velocities,
                "projected_gravity": self.imu.gravity_projection,
                "actions": self.last_action,
            }
        }
```

**推荐的6D pose estimation方法**：
- **FoundationPose**：无需CAD模型，少量示例即可
- **MegaPose**：通用，支持多种物体
- **SAM6D**：结合Segment Anything
- **BundleSDF**：在线重建+跟踪

---

### 方案2：纯视觉policy（长期方案）

**原理**：完全用RGB-D相机观测替代物体位姿

**优点**：
- 最通用，不需要物体模型
- 更好的泛化能力

**缺点**：
- 需要大量视觉数据训练
- sim2real gap更大
- 需要重新设计网络架构

**实施步骤**：

#### 2.1 Teacher-Student蒸馏

```python
# 伪代码框架
class VisionBasedStudent:
    def __init__(self):
        self.vision_encoder = ResNet50(...)  # 或ViT
        self.policy_head = MLPPolicy(...)
        
    def forward(self, rgb, depth, proprio):
        # 提取视觉特征
        visual_feat = self.vision_encoder(rgb, depth)
        
        # 结合本体感受
        obs = torch.cat([visual_feat, proprio], dim=-1)
        
        return self.policy_head(obs)

# 训练循环
for batch in dataloader:
    # Teacher前向（使用精确位姿）
    teacher_action = teacher_policy(privileged_obs)
    
    # Student前向（只用视觉）
    student_action = student_policy(rgb, depth, proprio)
    
    # 行为克隆损失
    loss = MSE(student_action, teacher_action)
```

#### 2.2 需要添加的组件

1. **相机模拟**（在Isaac Sim中）：
```python
# 添加到env_cfg.py
wrist_camera = CameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/wrist_camera",
    update_period=0.1,  # 10Hz
    height=480,
    width=640,
    data_types=["rgb", "distance_to_camera"],
)
```

2. **Domain Randomization**：
- 光照变化
- 纹理随机化
- 相机位姿扰动
- 背景多样化

---

### 方案3：混合方案（最佳平衡）⭐

结合前两种方法的优点：

**架构**：
```
输入: RGB-D + 物体位姿估计（来自视觉） + 本体感受
      ↓
   视觉编码器 → 视觉特征 (128-d)
      ↓
   位姿编码器 → 位姿特征 (64-d)  ← 对噪声鲁棒
      ↓
   [concat]
      ↓
   Policy Head → 动作
```

**优势**：
- 位姿提供粗略的空间定位
- 视觉提供细节和遮挡处理
- 互相补充，更鲁棒

---

## 实际建议

### 短期（1-2周）：
1. ✅ 使用`train_real_world.yaml`训练policy
2. ✅ 集成6D pose estimation到真机系统
3. ✅ 测试position/orientation tracking误差对性能的影响

### 中期（1-2月）：
4. 添加相机到仿真环境
5. 收集真机RGB-D数据
6. 训练vision encoder或做teacher-student蒸馏

### 长期：
7. 完全的vision-based policy
8. 在线适应和微调

---

## 常见问题

### Q: 必须去掉物体位姿吗？
**A**: 不必须。对于HOI这种需要精确操作的任务，保留位姿（通过视觉估计）是更实用的选择。完全的end-to-end视觉学习需要大量数据和时间。

### Q: 如果没有物体CAD模型怎么办？
**A**: 使用FoundationPose或BundleSDF，它们可以从少量RGB-D图像在线重建和跟踪。

### Q: 参考运动轨迹（motion命令）怎么处理？
**A**: 真机部署时有两种方案：
1. **离线规划**：提前规划好参考轨迹，存储为motion file
2. **在线MPC**：使用model predictive control实时生成参考轨迹

### Q: 接触力传感器是必须的吗？
**A**: 不必须，但会降低性能。可以：
1. 去掉contact reward，依赖位置tracking
2. 用视觉估计接触（触觉GelSight等）
3. 用joint torque间接估计

### Q: 训练收敛需要多久？
**A**: 使用`train_real_world.yaml`配置，在4096个环境下约需要：
- 5000-10000 iterations达到基本性能
- 30000+ iterations达到最优

---

## 验证清单

部署前确认：

- [ ] Policy只使用真机可获取的观测
- [ ] 添加了足够的观测噪声（位姿±3cm，旋转±10°）
- [ ] 测试了6D pose estimation在目标物体上的准确性
- [ ] 准备了降级方案（如果视觉失效）
- [ ] 实现了安全终止条件

---

## 参考资料

**6D Pose Estimation**:
- FoundationPose: https://github.com/NVlabs/FoundationPose
- MegaPose: https://github.com/megapose6d/megapose6d
- BundleSDF: https://github.com/NVlabs/BundleSDF

**Sim2Real Transfer**:
- Learning Dexterous In-Hand Manipulation (OpenAI)
- Visual Imitation Made Easy (PIGINet)
- DexMV: Imitation Learning for Dexterous Manipulation from Human Videos
