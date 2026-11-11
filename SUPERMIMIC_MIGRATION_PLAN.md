# SuperMimic 迁移方案B：混合实现详细计划

## 📋 目标

将SuperMimic的World Model思想迁移到Weave项目，同时保留Weave的HOI任务定义和环境。实现一个可以与PPO对比的混合训练系统。

---

## 🏗️ 整体架构设计

```
Weave环境（保留）
    ├── Isaac Lab + PhysX
    ├── G1机器人 + 物体交互
    ├── 奖励函数（12+项）
    └── 观察空间（参考动作、物体状态、本体感知）
    
新增组件（SuperMimic风格）
    ├── World Model: 预测 (robot_state, object_state) → (next_robot, next_object)
    ├── Replay Buffer: 存储真实交互数据
    ├── Imagination Rollout: 在想象中BPTT优化策略
    └── 混合训练循环: PPO baseline + World Model variant
```

---

## 📂 代码结构规划

```
source/g1_hoi_learning/g1_hoi_learning/
├── algorithms/
│   ├── ppo/                          # 现有PPO (保留)
│   │   ├── algorithm.py
│   │   ├── networks.py
│   │   └── runner.py
│   └── supermimic/                   # 新增
│       ├── __init__.py
│       ├── world_model.py           # World Model网络
│       ├── replay_buffer.py         # GPU Replay Buffer
│       ├── networks.py              # Policy/Critic (with encoder-decoder)
│       ├── algorithm.py             # SuperMimic训练算法
│       └── runner.py                # SuperMimic训练循环
├── tasks/
│   └── hoi/
│       ├── env_cfg.py               # 保持不变
│       └── mdp/
│           ├── state_utils.py       # 新增：状态表示工具
│           └── world_model_mdp.py   # 新增：适配World Model的MDP
└── utils/                            # 新增
    ├── rotations.py                 # 旋转表示工具（从supermimic移植）
    └── running_norm.py              # Running normalization
```

---

## 🔧 实现步骤

### **阶段1：基础设施搭建（Week 1）**

#### 1.1 状态表示统一

**文件**: `source/g1_hoi_learning/g1_hoi_learning/tasks/hoi/mdp/state_utils.py`

```python
"""统一的状态表示，兼容World Model和现有环境"""
import torch
from dataclasses import dataclass

@dataclass
class UnifiedState:
    """
    完整状态表示，包含机器人和物体
    
    机器人部分（类似SuperMimic）:
        - root_pos: (N, 3)        pelvis世界位置
        - root_R: (N, 3, 3)        pelvis旋转矩阵
        - root_vel: (N, 3)         线速度
        - root_angvel: (N, 3)      角速度
        - joint_pos: (N, 53)       关节位置（包含手指）
        - joint_vel: (N, 53)       关节速度
    
    物体部分（Weave特有）:
        - obj_pos: (N, 3)          物体世界位置
        - obj_quat: (N, 4)         物体四元数 (xyzw)
        - obj_vel: (N, 3)          物体线速度
        - obj_angvel: (N, 3)       物体角速度
    
    接触部分:
        - contact_forces: (N, 54)  每个body的接触力
    """
    # 机器人
    root_pos: torch.Tensor
    root_R: torch.Tensor
    root_vel: torch.Tensor
    root_angvel: torch.Tensor
    joint_pos: torch.Tensor
    joint_vel: torch.Tensor
    
    # 物体
    obj_pos: torch.Tensor
    obj_quat: torch.Tensor
    obj_vel: torch.Tensor
    obj_angvel: torch.Tensor
    
    # 接触
    contact_forces: torch.Tensor | None = None

def flatten_state(state: UnifiedState) -> torch.Tensor:
    """展平为单一向量 (N, D)"""
    from g1_hoi_learning.utils.rotations import mat_to_quat
    
    return torch.cat([
        state.root_pos,                    # 3
        mat_to_quat(state.root_R),         # 4
        state.root_vel,                    # 3
        state.root_angvel,                 # 3
        state.joint_pos,                   # 53
        state.joint_vel,                   # 53
        state.obj_pos,                     # 3
        state.obj_quat,                    # 4
        state.obj_vel,                     # 3
        state.obj_angvel,                  # 3
    ], dim=-1)  # Total: 132D

def unflatten_state(x: torch.Tensor) -> UnifiedState:
    """从向量恢复状态"""
    from g1_hoi_learning.utils.rotations import quat_to_mat
    
    idx = 0
    root_pos = x[..., idx:idx+3]; idx += 3
    root_quat = x[..., idx:idx+4]; idx += 4
    root_R = quat_to_mat(root_quat)
    root_vel = x[..., idx:idx+3]; idx += 3
    root_angvel = x[..., idx:idx+3]; idx += 3
    joint_pos = x[..., idx:idx+53]; idx += 53
    joint_vel = x[..., idx:idx+53]; idx += 53
    obj_pos = x[..., idx:idx+3]; idx += 3
    obj_quat = x[..., idx:idx+4]; idx += 4
    obj_vel = x[..., idx:idx+3]; idx += 3
    obj_angvel = x[..., idx:idx+3]; idx += 3
    
    return UnifiedState(
        root_pos=root_pos,
        root_R=root_R,
        root_vel=root_vel,
        root_angvel=root_angvel,
        joint_pos=joint_pos,
        joint_vel=joint_vel,
        obj_pos=obj_pos,
        obj_quat=obj_quat,
        obj_vel=obj_vel,
        obj_angvel=obj_angvel,
    )

def extract_state_from_env(env) -> UnifiedState:
    """从Weave环境提取状态"""
    from g1_hoi_learning.utils.rotations import quat_to_mat
    
    robot = env.scene["robot"]
    obj = env.scene["object"]
    
    # 机器人状态
    root_pose = robot.data.root_link_pose_w
    root_vel_w = robot.data.root_link_vel_w
    root_pos = root_pose[:, :3] - env.scene.env_origins  # 相对origin
    root_quat_xyzw = root_pose[:, 3:7]  # Isaac Lab 3.0 uses xyzw
    # 转换为wxyz用于quat_to_mat
    root_quat_wxyz = torch.cat([root_quat_xyzw[:, 3:4], root_quat_xyzw[:, :3]], dim=-1)
    root_R = quat_to_mat(root_quat_wxyz)
    
    # 物体状态
    obj_pose = obj.data.root_link_pose_w
    obj_vel_w = obj.data.root_link_vel_w
    obj_pos = obj_pose[:, :3] - env.scene.env_origins
    obj_quat = obj_pose[:, 3:7]  # xyzw
    
    # 接触力（如果有）
    contact_forces = None
    if "contact_sensor" in env.scene.sensors:
        sensor = env.scene.sensors["contact_sensor"]
        # 汇总每个body的接触力
        contact_forces = sensor.data.net_forces_w.norm(dim=-1)
    
    return UnifiedState(
        root_pos=root_pos,
        root_R=root_R,
        root_vel=root_vel_w[:, :3],
        root_angvel=root_vel_w[:, 3:6],
        joint_pos=robot.data.joint_pos.clone(),
        joint_vel=robot.data.joint_vel.clone(),
        obj_pos=obj_pos,
        obj_quat=obj_quat,
        obj_vel=obj_vel_w[:, :3],
        obj_angvel=obj_vel_w[:, 3:6],
        contact_forces=contact_forces,
    )
```

#### 1.2 旋转工具移植

**文件**: `source/g1_hoi_learning/g1_hoi_learning/utils/rotations.py`

从SuperMimic复制核心旋转函数：
- `quat_to_mat`, `mat_to_quat`
- `so3_log`, `so3_exp`
- `yaw_mat`, `mat_to_6d`
- `rot_angle_sq`

#### 1.3 Running Normalization

**文件**: `source/g1_hoi_learning/g1_hoi_learning/utils/running_norm.py`

```python
"""Running mean/std normalization with proper floor (from SuperMimic)"""
import torch
import torch.nn as nn

class RunningNorm(nn.Module):
    """Running normalization with update control"""
    
    def __init__(self, dim: int, max_count: float = 2e8, eps: float = 1e-2):
        super().__init__()
        self.register_buffer("mean", torch.zeros(dim))
        self.register_buffer("var", torch.ones(dim))
        self.register_buffer("count", torch.zeros(()))
        self.max_count = max_count
        self.eps = eps
    
    @torch.no_grad()
    def update(self, x: torch.Tensor):
        """Welford's online algorithm"""
        if self.count >= self.max_count:
            return
        
        x = x.reshape(-1, x.shape[-1]).float()
        n = x.shape[0]
        m = x.mean(0)
        v = x.var(0, unbiased=False)
        
        tot = self.count + n
        delta = m - self.mean
        self.mean += delta * n / tot
        self.var = (self.var * self.count + v * n + 
                    delta**2 * self.count * n / tot) / tot
        self.count = tot
    
    def forward(self, x):
        return (x - self.mean) / torch.sqrt(self.var + self.eps**2)
    
    def std(self):
        return torch.sqrt(self.var + self.eps**2)
```

---

### **阶段2：World Model实现（Week 2）**

#### 2.1 World Model网络

**文件**: `source/g1_hoi_learning/g1_hoi_learning/algorithms/supermimic/world_model.py`

```python
"""
World Model for HOI task: predicts (robot, object) state transitions
"""
import torch
import torch.nn as nn
from g1_hoi_learning.utils.running_norm import RunningNorm
from g1_hoi_learning.utils.rotations import so3_exp, so3_log, yaw_mat
from g1_hoi_learning.tasks.hoi.mdp.state_utils import UnifiedState

def mlp(inp: int, hidden: list[int], out: int, act=nn.SiLU, layer_norm=True):
    """MLP builder with layer norm"""
    layers, d = [], inp
    for h in hidden:
        layers.append(nn.Linear(d, h))
        if layer_norm:
            layers.append(nn.LayerNorm(h))
        layers.append(act())
        d = h
    layers.append(nn.Linear(d, out))
    return nn.Sequential(*layers)


class HOIWorldModel(nn.Module):
    """
    预测状态增量：s_{t+1} = f(s_t, a_t, ξ)
    
    输入特征：
        - 机器人不变量特征（heading-invariant）
        - 动作 (53D)
        - sim context ξ (摩擦、质量等)
    
    输出增量：
        - 机器人: Δp, Δθ, Δv, Δω, Δq, Δq̇ (3+3+3+3+53+53 = 118D)
        - 物体: Δp_obj, Δθ_obj, Δv_obj, Δω_obj (3+3+3+3 = 12D)
        Total: 130D
    """
    
    def __init__(self, 
                 action_dim: int = 53,
                 xi_dim: int = 10,  # friction, object_mass, etc.
                 hidden: tuple = (2048, 2048, 2048),
                 use_amp: bool = True):
        super().__init__()
        
        # 不变量特征维度
        # robot: height(1) + tilt(6) + vel_b(3) + angvel_b(3) + q(53) + qd(53) = 119
        # object: pos_rel(3) + ori_rel(6) + vel_rel(3) + angvel_rel(3) = 15
        self.inv_dim = 119 + 15  # = 134
        self.in_dim = self.inv_dim + action_dim + xi_dim  # 134 + 53 + 10 = 197
        self.out_dim = 130  # robot(118) + object(12)
        
        self.net = mlp(self.in_dim, list(hidden), self.out_dim, 
                      act=nn.SiLU, layer_norm=True)
        
        # 初始化为接近恒等映射
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)
        
        self.in_norm = RunningNorm(self.in_dim)
        self.out_norm = RunningNorm(self.out_dim, eps=1e-4)
        
        self.use_amp = use_amp
        self.amp_dtype = torch.bfloat16 if use_amp else None
    
    def invariant_features(self, state: UnifiedState) -> torch.Tensor:
        """提取heading和position无关的特征"""
        # 机器人部分
        H = yaw_mat(state.root_R)  # heading frame
        Ht = H.transpose(-1, -2)
        Rt = state.root_R.transpose(-1, -2)
        
        robot_inv = torch.cat([
            state.root_pos[..., 2:3],  # height
            self._mat_to_6d(Ht @ state.root_R),  # tilt (6D)
            (Rt @ state.root_vel.unsqueeze(-1)).squeeze(-1),  # vel in body frame
            (Rt @ state.root_angvel.unsqueeze(-1)).squeeze(-1),
            state.joint_pos,
            state.joint_vel,
        ], dim=-1)  # 119D
        
        # 物体相对机器人
        obj_rel_pos = state.obj_pos - state.root_pos
        obj_rel_pos_b = (Ht @ obj_rel_pos.unsqueeze(-1)).squeeze(-1)
        
        # 物体朝向相对机器人朝向
        from g1_hoi_learning.utils.rotations import quat_to_mat
        obj_R = quat_to_mat(torch.cat([state.obj_quat[..., 3:4], 
                                       state.obj_quat[..., :3]], dim=-1))
        obj_rel_R = Ht @ obj_R
        
        obj_inv = torch.cat([
            obj_rel_pos_b,
            self._mat_to_6d(obj_rel_R),
            (Rt @ state.obj_vel.unsqueeze(-1)).squeeze(-1),
            (Rt @ state.obj_angvel.unsqueeze(-1)).squeeze(-1),
        ], dim=-1)  # 15D
        
        return torch.cat([robot_inv, obj_inv], dim=-1)
    
    @staticmethod
    def _mat_to_6d(R):
        """旋转矩阵 → 6D连续表示"""
        return torch.cat([R[..., :, 0], R[..., :, 1]], dim=-1)
    
    def inputs(self, state: UnifiedState, action: torch.Tensor, 
               xi_normalized: torch.Tensor) -> torch.Tensor:
        """构造网络输入"""
        return torch.cat([
            self.invariant_features(state),
            action,
            xi_normalized,
        ], dim=-1)
    
    def targets(self, s0: UnifiedState, s1: UnifiedState) -> torch.Tensor:
        """计算回归目标：frame-local增量"""
        # 机器人增量
        H = yaw_mat(s0.root_R)
        Rt = s0.root_R.transpose(-1, -2)
        
        dp = (H.transpose(-1, -2) @ (s1.root_pos - s0.root_pos).unsqueeze(-1)).squeeze(-1)
        dth = so3_log(Rt @ s1.root_R)
        dv = (Rt @ (s1.root_vel - s0.root_vel).unsqueeze(-1)).squeeze(-1)
        dw = (Rt @ (s1.root_angvel - s0.root_angvel).unsqueeze(-1)).squeeze(-1)
        dq = s1.joint_pos - s0.joint_pos
        dqd = s1.joint_vel - s0.joint_vel
        
        # 物体增量（也在heading frame）
        dp_obj = (H.transpose(-1, -2) @ (s1.obj_pos - s0.obj_pos).unsqueeze(-1)).squeeze(-1)
        
        from g1_hoi_learning.utils.rotations import quat_to_mat
        R0_obj = quat_to_mat(torch.cat([s0.obj_quat[..., 3:4], s0.obj_quat[..., :3]], -1))
        R1_obj = quat_to_mat(torch.cat([s1.obj_quat[..., 3:4], s1.obj_quat[..., :3]], -1))
        dth_obj = so3_log(R0_obj.transpose(-1, -2) @ R1_obj)
        
        dv_obj = (Rt @ (s1.obj_vel - s0.obj_vel).unsqueeze(-1)).squeeze(-1)
        dw_obj = (Rt @ (s1.obj_angvel - s0.obj_angvel).unsqueeze(-1)).squeeze(-1)
        
        return torch.cat([
            dp, dth, dv, dw, dq, dqd,  # robot: 118D
            dp_obj, dth_obj, dv_obj, dw_obj,  # object: 12D
        ], dim=-1)
    
    def forward_mlp(self, x: torch.Tensor) -> torch.Tensor:
        """MLP forward with optional bf16"""
        if self.amp_dtype is None:
            return self.net(x)
        with torch.autocast("cuda", dtype=self.amp_dtype):
            return self.net(x).float()
    
    def step(self, state: UnifiedState, action: torch.Tensor, 
             xi_normalized: torch.Tensor) -> UnifiedState:
        """单步预测 s_{t+1}"""
        inp = self.inputs(state, action, xi_normalized)
        y = self.forward_mlp(self.in_norm(inp))
        delta = y * self.out_norm.std() + self.out_norm.mean
        
        # 解包增量
        idx = 0
        dp = delta[..., idx:idx+3]; idx += 3
        dth = delta[..., idx:idx+3]; idx += 3
        dv = delta[..., idx:idx+3]; idx += 3
        dw = delta[..., idx:idx+3]; idx += 3
        dq = delta[..., idx:idx+53]; idx += 53
        dqd = delta[..., idx:idx+53]; idx += 53
        dp_obj = delta[..., idx:idx+3]; idx += 3
        dth_obj = delta[..., idx:idx+3]; idx += 3
        dv_obj = delta[..., idx:idx+3]; idx += 3
        dw_obj = delta[..., idx:idx+3]; idx += 3
        
        # 应用增量
        H = yaw_mat(state.root_R)
        new_root_pos = state.root_pos + (H @ dp.unsqueeze(-1)).squeeze(-1)
        new_root_R = state.root_R @ so3_exp(dth)
        new_root_vel = state.root_vel + (state.root_R @ dv.unsqueeze(-1)).squeeze(-1)
        new_root_angvel = state.root_angvel + (state.root_R @ dw.unsqueeze(-1)).squeeze(-1)
        
        new_obj_pos = state.obj_pos + (H @ dp_obj.unsqueeze(-1)).squeeze(-1)
        from g1_hoi_learning.utils.rotations import quat_to_mat, mat_to_quat
        R_obj = quat_to_mat(torch.cat([state.obj_quat[..., 3:4], 
                                       state.obj_quat[..., :3]], -1))
        new_R_obj = R_obj @ so3_exp(dth_obj)
        new_obj_quat_wxyz = mat_to_quat(new_R_obj)
        # 转回xyzw
        new_obj_quat = torch.cat([new_obj_quat_wxyz[..., 1:4], 
                                  new_obj_quat_wxyz[..., 0:1]], -1)
        new_obj_vel = state.obj_vel + (state.root_R @ dv_obj.unsqueeze(-1)).squeeze(-1)
        new_obj_angvel = state.obj_angvel + (state.root_R @ dw_obj.unsqueeze(-1)).squeeze(-1)
        
        return UnifiedState(
            root_pos=new_root_pos,
            root_R=new_root_R,
            root_vel=new_root_vel,
            root_angvel=new_root_angvel,
            joint_pos=state.joint_pos + dq,
            joint_vel=state.joint_vel + dqd,
            obj_pos=new_obj_pos,
            obj_quat=new_obj_quat,
            obj_vel=new_obj_vel,
            obj_angvel=new_obj_angvel,
        )
    
    def state_error(self, pred: UnifiedState, target: UnifiedState) -> torch.Tensor:
        """状态误差（用于训练）"""
        return self.targets(target, pred)  # 复用targets的计算
```

#### 2.2 Replay Buffer

**文件**: `source/g1_hoi_learning/g1_hoi_learning/algorithms/supermimic/replay_buffer.py`

```python
"""GPU Replay Buffer for HOI transitions"""
import torch

class HOIReplayBuffer:
    """
    固定大小的GPU buffer，存储 (time, env) 格式的transitions
    """
    
    def __init__(self, capacity: int, num_envs: int, 
                 state_dim: int = 132,  # flatten state
                 action_dim: int = 53,
                 xi_dim: int = 10,
                 device: str = "cuda"):
        self.capacity = capacity
        self.num_envs = num_envs
        self.device = device
        
        # 存储结构: (T, N, D)
        self.states = torch.zeros((capacity, num_envs, state_dim), 
                                 dtype=torch.float32, device=device)
        self.next_states = torch.zeros((capacity, num_envs, state_dim), 
                                      dtype=torch.float32, device=device)
        self.actions = torch.zeros((capacity, num_envs, action_dim), 
                                  dtype=torch.float32, device=device)
        self.rewards = torch.zeros((capacity, num_envs), 
                                  dtype=torch.float32, device=device)
        self.dones = torch.zeros((capacity, num_envs), 
                                dtype=torch.bool, device=device)
        self.xi = torch.zeros((capacity, num_envs, xi_dim), 
                             dtype=torch.float32, device=device)
        self.ep_steps = torch.zeros((capacity, num_envs), 
                                   dtype=torch.int32, device=device)
        
        self.ptr = 0
        self.size = 0
    
    def add(self, state, next_state, action, reward, done, xi, ep_step):
        """添加一个时间步的数据"""
        self.states[self.ptr] = state
        self.next_states[self.ptr] = next_state
        self.actions[self.ptr] = action
        self.rewards[self.ptr] = reward
        self.dones[self.ptr] = done
        self.xi[self.ptr] = xi
        self.ep_steps[self.ptr] = ep_step
        
        self.ptr = (self.ptr + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
    
    def sample_windows(self, batch_size: int, window_length: int):
        """
        采样k步窗口用于训练World Model
        
        Returns:
            dict with keys: states, actions, next_states, xi, mask
            shapes: (B, k, ...)
        """
        if window_length > self.size:
            raise ValueError(f"Window {window_length} > buffer size {self.size}")
        
        # 随机采样起始位置
        t0 = torch.randint(0, self.size - window_length + 1, 
                          (batch_size,), device=self.device)
        env_ids = torch.randint(0, self.num_envs, 
                               (batch_size,), device=self.device)
        
        # 构造时间索引
        ages = t0.unsqueeze(-1) + torch.arange(window_length, device=self.device)
        rows = (self.ptr - self.size + ages) % self.capacity
        
        # 索引
        env_idx = env_ids.unsqueeze(-1).expand_as(rows)
        
        # 提取数据
        states_w = self.states[rows, env_idx]       # (B, k, D)
        actions_w = self.actions[rows, env_idx]
        next_states_w = self.next_states[rows, env_idx]
        xi_w = self.xi[rows, env_idx]
        dones_w = self.dones[rows, env_idx]
        
        # 计算有效性mask（如果中间有done，后续无效）
        mask = torch.cumprod(
            torch.cat([
                torch.ones(batch_size, 1, device=self.device),
                1 - dones_w[:, :-1].float()
            ], dim=-1),
            dim=-1
        )
        
        return {
            "states": states_w,
            "actions": actions_w,
            "next_states": next_states_w,
            "xi": xi_w,
            "mask": mask,
        }
    
    def sample_starts(self, batch_size: int, history_length: int = 10):
        """
        采样imagination起点及其历史观察
        
        Returns:
            start: 起点状态字典
            history: 历史状态字典
        """
        # 随机采样
        ages = torch.randint(0, self.size, (batch_size,), device=self.device)
        env_ids = torch.randint(0, self.num_envs, (batch_size,), device=self.device)
        
        rows = (self.ptr - self.size + ages) % self.capacity
        ep_steps_at_sample = self.ep_steps[rows, env_ids].long()
        
        # 历史索引（不超出episode边界）
        back = torch.arange(history_length - 1, -1, -1, device=self.device)
        back = torch.minimum(back.unsqueeze(0), ep_steps_at_sample.unsqueeze(-1))
        back = torch.minimum(back, ages.unsqueeze(-1))
        
        hist_rows = (self.ptr - self.size + ages.unsqueeze(-1) - back) % self.capacity
        hist_env = env_ids.unsqueeze(-1).expand_as(hist_rows)
        
        # 提取
        start = {
            "state": self.states[rows, env_ids],
            "xi": self.xi[rows, env_ids],
        }
        
        history = {
            "states": self.states[hist_rows, hist_env],
            "actions": self.actions[hist_rows, hist_env],
        }
        
        return start, history
```

---

### **阶段3：策略网络改造（Week 2-3）**

#### 3.1 编码器-解码器策略

**文件**: `source/g1_hoi_learning/g1_hoi_learning/algorithms/supermimic/networks.py`

```python
"""SuperMimic-style Policy with motion encoder"""
import torch
import torch.nn as nn
from g1_hoi_learning.utils.running_norm import RunningNorm

def mlp(inp, hidden, out, act=nn.ELU):
    layers, d = [], inp
    for h in hidden:
        layers.append(nn.Linear(d, h))
        layers.append(act())
        d = h
    layers.append(nn.Linear(d, out))
    return nn.Sequential(*layers)


class MotionEncoderPolicy(nn.Module):
    """
    策略：a = decoder(encoder(goal), obs_history)
    
    类似SuperMimic但适配HOI:
        - goal: 未来K帧参考（机器人+物体）
        - obs_history: 最近H帧观察
        - latent z: 32D (tanh bounded)
    """
    
    def __init__(self, 
                 obs_dim: int,
                 goal_dim: int,  # K帧 × (body+object特征)
                 action_dim: int = 53,
                 history_len: int = 10,
                 z_dim: int = 32,
                 use_amp: bool = True):
        super().__init__()
        
        self.history_len = history_len
        self.obs_dim = obs_dim
        self.goal_dim = goal_dim
        self.z_dim = z_dim
        
        # Encoder: goal → z
        self.encoder = mlp(goal_dim, [2048, 1024, 512, 256], z_dim)
        
        # Decoder: (z, obs_history) → action
        dec_in = z_dim + obs_dim * history_len
        self.decoder = mlp(dec_in, [2048, 1024, 512, 256], action_dim)
        
        # 小初始化
        with torch.no_grad():
            self.decoder[-1].weight.mul_(0.01)
            self.decoder[-1].bias.zero_()
        
        # Normalizers
        self.obs_norm = RunningNorm(obs_dim)
        self.goal_norm = RunningNorm(goal_dim)
        
        self.use_amp = use_amp
        self.amp_dtype = torch.bfloat16 if use_amp else None
    
    def _run_mlp(self, net, x):
        if self.amp_dtype is None:
            return net(x)
        with torch.autocast("cuda", dtype=self.amp_dtype):
            return net(x).float()
    
    def forward(self, obs_history: torch.Tensor, goal: torch.Tensor, 
                deterministic: bool = False):
        """
        Args:
            obs_history: (B, H, obs_dim) 历史观察，newest last
            goal: (B, goal_dim) 未来参考
        
        Returns:
            action: (B, action_dim)
        """
        # Encode goal
        z = torch.tanh(self._run_mlp(self.encoder, self.goal_norm(goal)))
        
        # Normalize and flatten history
        obs_norm = self.obs_norm(obs_history)  # (B, H, D)
        obs_flat = obs_norm.flatten(-2)  # (B, H*D)
        
        # Decode
        action = self._run_mlp(self.decoder, torch.cat([z, obs_flat], dim=-1))
        
        return action


class Critic(nn.Module):
    """Value function: V(state_features, goal)"""
    
    def __init__(self, in_dim: int):
        super().__init__()
        self.net = mlp(in_dim, [256, 128], 1)
        self.norm = RunningNorm(in_dim)
    
    def forward(self, x):
        return self.net(self.norm(x)).squeeze(-1)
```

---

### **阶段4：训练算法（Week 3-4）**

#### 4.1 SuperMimic训练循环

**文件**: `source/g1_hoi_learning/g1_hoi_learning/algorithms/supermimic/algorithm.py`

```python
"""SuperMimic training algorithm for HOI"""
import torch
import torch.nn as nn
from typing import Dict, Tuple
import time

from .world_model import HOIWorldModel
from .networks import MotionEncoderPolicy, Critic
from .replay_buffer import HOIReplayBuffer
from g1_hoi_learning.tasks.hoi.mdp.state_utils import (
    extract_state_from_env, flatten_state, unflatten_state
)


class SuperMimicHOI:
    """
    SuperMimic算法适配HOI任务
    
    训练循环:
        1. 收集真实交互 → replay buffer
        2. 训练World Model（多batch）
        3. 从buffer采样起点 → imagination rollout (BPTT)
        4. 优化policy和critic
    """
    
    def __init__(self,
                 env,
                 world_model: HOIWorldModel,
                 policy: MotionEncoderPolicy,
                 critic: Critic,
                 # Hyperparameters
                 buffer_capacity: int = 1000,
                 utd_ratio: float = 0.4,
                 wm_window: int = 8,
                 wm_batches: int = 10,
                 wm_batch_size: int = 2048,
                 imagination_horizon: int = 32,
                 imagination_batch: int = 4096,
                 gamma: float = 0.99,
                 gae_lambda: float = 0.95,
                 lr: float = 2e-4,
                 action_noise: float = 0.1,
                 warmup_iters: int = 500,
                 device: str = "cuda"):
        
        self.env = env
        self.wm = world_model.to(device)
        self.policy = policy.to(device)
        self.critic = critic.to(device)
        
        self.device = device
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.imagination_horizon = imagination_horizon
        self.action_noise = action_noise
        self.warmup_iters = warmup_iters
        
        # Replay buffer
        self.buffer = HOIReplayBuffer(
            capacity=buffer_capacity,
            num_envs=env.num_envs,
            device=device
        )
        
        # Optimizers
        self.opt_wm = torch.optim.Adam(self.wm.parameters(), lr=lr)
        self.opt_policy = torch.optim.Adam(self.policy.parameters(), 
                                          lr=lr, betas=(0.9, 0.95))
        self.opt_critic = torch.optim.Adam(self.critic.parameters(), lr=lr)
        
        # Training config
        self.utd_ratio = utd_ratio
        self.step_accumulator = 0.0
        self.wm_window = wm_window
        self.wm_batches = wm_batches
        self.wm_batch_size = wm_batch_size
        self.imagination_batch = imagination_batch
        
        # Bookkeeping
        self.iteration = 0
        self.total_steps = 0
        
        # WM error floor (类似SuperMimic)
        self.wm_err_floor = torch.cat([
            torch.full((3,), 3e-3),   # pos
            torch.full((3,), 5e-3),   # rotation
            torch.full((3,), 2e-2),   # vel
            torch.full((3,), 5e-2),   # angvel
            torch.full((53,), 3e-3),  # joint_pos
            torch.full((53,), 5e-2),  # joint_vel
            torch.full((3,), 3e-3),   # obj pos
            torch.full((3,), 5e-3),   # obj rot
            torch.full((3,), 2e-2),   # obj vel
            torch.full((3,), 5e-2),   # obj angvel
        ]).to(device)
    
    def collect_step(self) -> Dict:
        """收集一个环境步（所有envs并行）"""
        # 提取当前状态
        state = extract_state_from_env(self.env)
        
        # 获取observation和goal（从env的command manager）
        obs = self.env.observation_manager.compute_group("robot_proprio")
        # TODO: 构造goal（未来K帧参考）
        goal = self._get_goal_from_env()
        
        # 策略推理（带噪声）
        with torch.no_grad():
            # 需要obs history，初始化为当前obs重复
            if not hasattr(self, '_obs_history'):
                self._obs_history = obs.unsqueeze(1).repeat(1, self.policy.history_len, 1)
            
            action = self.policy(self._obs_history, goal)
            if self.training:
                action = action + self.action_noise * torch.randn_like(action)
                action = torch.clamp(action, -20, 20)
        
        # 环境步进
        obs_next, reward, terminated, truncated, info = self.env.step(action)
        done = terminated | truncated
        
        # 下一个状态
        state_next = extract_state_from_env(self.env)
        
        # 更新obs history
        self._obs_history = torch.cat([
            self._obs_history[:, 1:],
            obs.unsqueeze(1)
        ], dim=1)
        
        # 存入buffer
        xi = self._get_sim_context()  # 摩擦、质量等
        ep_step = getattr(self.env, 'episode_length_buf', 
                         torch.zeros(self.env.num_envs, device=self.device))
        
        self.buffer.add(
            state=flatten_state(state),
            next_state=flatten_state(state_next),
            action=action,
            reward=reward,
            done=done,
            xi=xi,
            ep_step=ep_step.int()
        )
        
        # 更新统计
        self.total_steps += self.env.num_envs
        
        # 更新归一化器
        self.wm.in_norm.update(self.wm.inputs(state, action, xi))
        self.wm.out_norm.update(self.wm.targets(state, state_next))
        self.policy.obs_norm.update(obs)
        self.policy.goal_norm.update(goal)
        
        return {
            "reward": reward.mean().item(),
            "done": done.float().mean().item(),
        }
    
    def _get_goal_from_env(self) -> torch.Tensor:
        """从环境的motion command构造goal"""
        # TODO: 根据Weave的MotionCommand实现
        # 应该返回 (N, goal_dim) 未来K帧的参考
        cmd = self.env.command_manager.get_term("motion")
        # 简化版：拼接未来参考
        K = 10  # future frames
        goal = torch.cat([
            cmd.motion_future_joint_pos,  # 已经是K帧
            cmd.motion_future_anchor_pos_b,
            cmd.motion_future_anchor_ori_b,
            cmd.motion_future_obj_pos_b,
            cmd.motion_future_obj_ori_b,
        ], dim=-1)
        return goal
    
    def _get_sim_context(self) -> torch.Tensor:
        """提取sim context ξ"""
        # TODO: 从env提取friction, object mass等
        # 简化版：返回零向量
        return torch.zeros(self.env.num_envs, 10, device=self.device)
    
    def update_world_model(self) -> Dict[str, float]:
        """训练World Model"""
        losses = []
        errors = []
        
        for _ in range(self.wm_batches):
            # 采样k步窗口
            batch = self.buffer.sample_windows(
                self.wm_batch_size, 
                self.wm_window
            )
            
            states = unflatten_state(batch["states"])  # (B, k, ...)
            actions = batch["actions"]
            next_states_gt = unflatten_state(batch["next_states"])
            xi = batch["xi"]
            mask = batch["mask"]
            
            # 自回归预测k步
            S = unflatten_state(batch["states"][:, 0])  # 起点
            predictions = []
            for t in range(self.wm_window):
                S = self.wm.step(S, actions[:, t], xi[:, t])
                predictions.append(S)
            
            # 计算误差
            total_loss = 0
            for t in range(self.wm_window):
                error = self.wm.state_error(predictions[t], 
                                           next_states_gt[:, t])
                # 归一化误差
                std = torch.maximum(self.wm.out_norm.std(), self.wm_err_floor)
                squared_err = (error / std) ** 2
                step_loss = (squared_err.mean(-1) * mask[:, t]).sum() / self.wm_batch_size
                total_loss += step_loss
            
            loss = total_loss / self.wm_window
            
            # 优化
            self.opt_wm.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.wm.parameters(), 1.0)
            self.opt_wm.step()
            
            losses.append(loss.item())
            errors.append(squared_err[:, -1].mean().item())
        
        return {
            "wm_loss": sum(losses) / len(losses),
            "wm_error_last": sum(errors) / len(errors),
        }
    
    def update_policy(self) -> Dict[str, float]:
        """在imagination中优化policy"""
        # 采样起点
        starts, history = self.buffer.sample_starts(
            self.imagination_batch,
            history_length=self.policy.history_len
        )
        
        S = unflatten_state(starts["state"])
        xi = starts["xi"]
        
        # 构造obs history（从history states）
        with torch.no_grad():
            # TODO: 从history构造真实的obs
            # 简化：直接用当前obs重复
            obs_hist = self._construct_obs_history(history)
            goal = self._construct_goal(S)  # 根据S构造goal
        
        # Imagination rollout
        H = self.imagination_horizon
        rewards = []
        terminations = []
        states_traj = [S]
        actions_traj = []
        
        for t in range(H):
            # Policy forward
            action = self.policy(obs_hist, goal)
            
            # World model step
            S_next = self.wm.step(S, action, xi)
            
            # 计算reward和termination（解析式）
            r, term = self._compute_reward_termination(S_next, goal)
            
            rewards.append(r)
            terminations.append(term)
            states_traj.append(S_next)
            actions_traj.append(action)
            
            # 更新for next step
            S = S_next
            # 更新obs_hist（从predicted state）
            obs_hist = self._update_obs_history(obs_hist, S, action)
            # goal可能也需要更新（时间推进）
        
        # Stack
        rewards = torch.stack(rewards)  # (H, B)
        terms = torch.stack(terminations)  # (H, B)
        
        # 计算return（with soft termination）
        alive = torch.cumprod(1 - terms, dim=0)
        c_t = torch.cat([torch.ones(1, self.imagination_batch, device=self.device),
                        alive[:-1]], dim=0)
        
        discounts = self.gamma ** torch.arange(H, device=self.device).unsqueeze(-1)
        J = (discounts * c_t * rewards).sum(0)
        
        # Critic bootstrap
        with torch.no_grad():
            V_final = self.critic(self._critic_features(S, goal, xi))
        J = J + (self.gamma ** H) * alive[-1] * V_final
        
        # Policy loss
        policy_loss = -J.mean()
        
        # Optimize policy
        self.opt_policy.zero_grad()
        policy_loss.backward()
        grad_norm = nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        nn.utils.clip_grad_value_(self.policy.parameters(), 0.1)
        self.opt_policy.step()
        
        # Critic update (GAE)
        critic_loss = self._update_critic(states_traj, rewards, terms, goal, xi)
        
        return {
            "policy_loss": policy_loss.item(),
            "critic_loss": critic_loss,
            "imagined_return": J.mean().item(),
            "policy_grad_norm": grad_norm.item(),
            "survival_rate": alive[-1].mean().item(),
        }
    
    def _compute_reward_termination(self, state, goal):
        """解析式奖励和termination（从Weave的reward terms改造）"""
        # TODO: 调用Weave的奖励函数
        # 这里需要适配让它接受UnifiedState
        # 简化：返回dummy
        r = torch.zeros(state.root_pos.shape[0], device=self.device)
        term = torch.zeros_like(r)
        return r, term
    
    def _update_critic(self, states_traj, rewards, terms, goal, xi):
        """用GAE更新critic"""
        # TODO: 实现GAE targets
        # 简化：返回0
        return 0.0
    
    def _construct_obs_history(self, history):
        """从history dict构造obs"""
        # TODO
        pass
    
    def _construct_goal(self, state):
        """从state构造goal"""
        # TODO
        pass
    
    def _update_obs_history(self, obs_hist, state, action):
        """更新观察历史"""
        # TODO
        pass
    
    def _critic_features(self, state, goal, xi):
        """Critic输入特征"""
        # TODO
        pass
    
    def train_iteration(self) -> Dict[str, float]:
        """一次训练迭代"""
        # 1. 收集数据
        self.step_accumulator += 1.0 / self.utd_ratio
        n_steps = int(self.step_accumulator)
        self.step_accumulator -= n_steps
        
        collect_stats = []
        for _ in range(n_steps):
            stats = self.collect_step()
            collect_stats.append(stats)
        
        if self.buffer.size < self.wm_window:
            return {"status": "warming_up"}
        
        # 2. 更新World Model
        wm_stats = self.update_world_model()
        
        # 3. 更新Policy (warmup后)
        policy_stats = {}
        if self.iteration >= self.warmup_iters:
            policy_stats = self.update_policy()
        
        self.iteration += 1
        
        # 合并统计
        return {
            **wm_stats,
            **policy_stats,
            "collect_reward": sum(s["reward"] for s in collect_stats) / len(collect_stats),
            "iteration": self.iteration,
        }
```

---

### **阶段5：集成和训练脚本（Week 4）**

#### 5.1 新训练脚本

**文件**: `scripts/rsl_rl/train_supermimic.py`

```python
"""Train with SuperMimic algorithm"""
import argparse
import sys
from isaaclab.app import AppLauncher

# Args
parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="G1-Inspire-HOI-v0")
parser.add_argument("--num_envs", type=int, default=4096)
parser.add_argument("--headless", action="store_true", default=True)
parser.add_argument("--device", type=str, default="cuda:0")
parser.add_argument("--max_iterations", type=int, default=50000)
parser.add_argument("--seed", type=int, default=42)

# SuperMimic specific
parser.add_argument("--buffer_capacity", type=int, default=1000)
parser.add_argument("--utd_ratio", type=float, default=0.4)
parser.add_argument("--imagination_horizon", type=int, default=32)
parser.add_argument("--lr", type=float, default=2e-4)
parser.add_argument("--use_amp", action="store_true", default=True)

AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()

# Launch
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import torch
import gymnasium as gym
from datetime import datetime
import os

import isaaclab_tasks
import g1_hoi_learning.tasks

from g1_hoi_learning.algorithms.supermimic.world_model import HOIWorldModel
from g1_hoi_learning.algorithms.supermimic.networks import MotionEncoderPolicy, Critic
from g1_hoi_learning.algorithms.supermimic.algorithm import SuperMimicHOI

def main():
    # 创建环境
    env = gym.make(args.task, num_envs=args.num_envs, device=args.device)
    
    # 创建网络
    # TODO: 根据env确定维度
    obs_dim = 100  # placeholder
    goal_dim = 500  # placeholder
    action_dim = 53
    
    world_model = HOIWorldModel(
        action_dim=action_dim,
        use_amp=args.use_amp
    )
    
    policy = MotionEncoderPolicy(
        obs_dim=obs_dim,
        goal_dim=goal_dim,
        action_dim=action_dim,
        use_amp=args.use_amp
    )
    
    critic = Critic(in_dim=obs_dim + goal_dim + 10)
    
    # 创建算法
    algo = SuperMimicHOI(
        env=env,
        world_model=world_model,
        policy=policy,
        critic=critic,
        buffer_capacity=args.buffer_capacity,
        utd_ratio=args.utd_ratio,
        imagination_horizon=args.imagination_horizon,
        lr=args.lr,
        device=args.device,
    )
    
    # 训练循环
    log_dir = f"logs/supermimic/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    os.makedirs(log_dir, exist_ok=True)
    
    for it in range(args.max_iterations):
        stats = algo.train_iteration()
        
        if it % 50 == 0:
            print(f"Iter {it}: {stats}")
        
        # TODO: 保存checkpoint, logging等
    
    env.close()
    simulation_app.close()

if __name__ == "__main__":
    main()
```

---

## 🧪 测试和验证策略

### Phase 1测试：组件级

```python
# test_world_model.py
def test_world_model_forward():
    """测试World Model前向传播"""
    wm = HOIWorldModel(action_dim=53)
    state = create_dummy_state(batch_size=16)
    action = torch.randn(16, 53)
    xi = torch.randn(16, 10)
    
    state_next = wm.step(state, action, xi)
    assert state_next.root_pos.shape == (16, 3)
    # ... 其他检查

def test_buffer():
    """测试Replay Buffer"""
    buffer = HOIReplayBuffer(capacity=100, num_envs=10)
    for _ in range(50):
        buffer.add(...)
    
    windows = buffer.sample_windows(batch_size=32, window_length=8)
    assert windows["states"].shape == (32, 8, 132)
```

### Phase 2测试：集成测试

```python
def test_training_loop():
    """测试一次完整迭代"""
    env = create_test_env(num_envs=128)
    algo = SuperMimicHOI(env, ...)
    
    stats = algo.train_iteration()
    assert "wm_loss" in stats
```

### Phase 3验证：对比实验

1. **Baseline**: 当前PPO在一个简单HOI任务（如floorlamp）
2. **SuperMimic**: 同样任务，相同环境数
3. **对比指标**:
   - 样本效率（达到同样return所需步数）
   - 训练时间
   - 最终性能
   - 稳定性（多次运行）

---

## 📊 预期收益和风险

### 预期收益
- ✅ **样本效率提升10-50倍**（基于SuperMimic论文结果）
- ✅ **训练时间缩短**（小时级 → 分钟级）
- ✅ **更稳定的训练曲线**

### 主要风险
- ⚠️ **World Model难以准确建模接触动力学**
  - 缓解：初期在接触较少的任务上验证
- ⚠️ **实现复杂度高**
  - 缓解：渐进式开发，充分测试
- ⚠️ **超参数调优**
  - 缓解：先使用SuperMimic论文的参数，再针对HOI调整

---

## 📅 时间线总结

| 阶段 | 时间 | 里程碑 |
|------|------|--------|
| 阶段1 | Week 1 | 状态表示、旋转工具、归一化 |
| 阶段2 | Week 2 | World Model、Replay Buffer |
| 阶段3 | Week 2-3 | 策略网络改造 |
| 阶段4 | Week 3-4 | 训练算法实现 |
| 阶段5 | Week 4 | 集成测试、训练脚本 |
| 验证 | Week 5-6 | 对比实验、调优 |

**总计：6周达到可用版本**

---

## 🚀 下一步行动

1. **立即开始**: 实现`state_utils.py`和`rotations.py`（1-2天）
2. **并行开发**: World Model和Buffer可以并行（3-4天）
3. **集成点**: Week 3开始整合训练循环
4. **持续测试**: 每个组件完成后立即单元测试

是否需要我针对某个具体模块提供更详细的代码实现？
