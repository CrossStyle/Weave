# Object ID Registry 使用说明

## 问题描述

之前的实现存在一个问题：

- **训练时**：使用多个物体（如 9 个），`num_objects=9`，object_id 是 0-8
- **Eval/Play 时**：只加载一个物体的 motion（如 ladder），`num_objects=1`，object_id 变成 0
- **冲突**：同一个物体（ladder）在训练时 ID=某个值，在 eval 时 ID=0，导致 policy 无法识别

## 解决方案

引入**全局物体 ID 注册表**，确保每个物体在训练、验证、部署时使用**相同的固定 ID**。

## 实现

### 1. 全局注册表 (`object_registry.py`)

```python
OBJECT_ID_REGISTRY = {
    "clothesstand": 0,
    "floorlamp": 1,
    "largebox": 2,
    "largetable": 3,
    "smallbox": 4,
    "smalltable": 5,
    "tripod": 6,
    "whitechair": 7,
    "woodchair": 8,
    "hframe": 9,
    "ladder": 10,
}
```

### 2. 自动映射

- **训练时**（多个物体）：
  - Motion 包含 ["woodchair", "ladder", "hframe"]
  - 映射到全局 ID：[8, 10, 9]
  - `object_id` one-hot 维度：**11**（全局注册表大小）

- **Eval 时**（单个物体）：
  - Motion 只包含 ["ladder"]
  - 映射到全局 ID：[10]
  - `object_id` one-hot 维度：**仍然是 11**
  - **ladder 的 ID 保持为 10，与训练时一致！**

## 使用方法

### 添加新物体

在 `object_registry.py` 中添加：

```python
OBJECT_ID_REGISTRY = {
    # ... existing objects ...
    "new_object": 11,  # 下一个可用 ID
}
```

### 训练时自动使用

不需要修改训练代码，系统会自动：
1. 从 motion 文件读取 `object_names`
2. 查找全局注册表获取 ID
3. 生成固定大小的 one-hot 编码（11 维）

### Eval/Play 时

```bash
# 单个物体 eval - 使用与训练相同的 ID
python scripts/rsl_rl/eval.py --task=G1-Inspire-HOI-v0 \
    --config-dir ./configs/track --config-name eval \
    env.commands.motion.motion_files=[./data/test/ladder_8s.npz]
```

ladder 的 ID 保持为 10，policy 能正确识别。

## 技术细节

### 修改的文件

1. **`object_registry.py`** (新增)
   - 全局 ID 注册表
   - ID 查询函数

2. **`commands.py`**
   ```python
   self.object_name_to_id = {name: get_object_id(name) for name in self.object_names}
   self.object_ids = [self.object_name_to_id[name] for name in self.object_names]
   ```

3. **`observations.py`**
   ```python
   def object_id_onehot(env, command_name) -> torch.Tensor:
       # 使用全局注册表大小
       num_objects_global = get_num_objects()
       # 映射到全局 ID
       global_ids = [command.motion.object_ids[local_id] for local_id in ...]
   ```

### 向后兼容

- `command.motion.num_objects`: 保留，表示**当前 motion 包含的物体数量**
- `command.motion.object_names`: 保留，当前 motion 的物体名称
- `command.motion.object_ids`: 新增，对应的**全局 ID 列表**
- `command.env_object`: 保留，表示**局部索引**（0, 1, 2, ...）
- 观测中的 `object_id`: 使用**全局 ID**，维度固定为 11

## 优势

1. ✅ **训练和 eval 使用相同的 object_id**
2. ✅ **支持单物体 eval/play**（不再报错）
3. ✅ **支持多物体训练**
4. ✅ **ID 固定，易于调试**
5. ✅ **真机部署时 ID 一致**

## 示例

### 训练（3 个物体）

```yaml
# train.yaml
env:
  commands:
    motion:
      motion_files:
        - ./data/train/woodchair_46clip.npz
        - ./data/train/ladder_8s.npz
        - ./data/train/hframe_20clip.npz
```

结果：
- `motion.object_names = ["woodchair", "ladder", "hframe"]`
- `motion.object_ids = [8, 10, 9]`
- `object_id` one-hot 维度：**11**

### Eval（1 个物体）

```yaml
# eval.yaml
env:
  commands:
    motion:
      motion_files:
        - ./data/test/ladder_8s.npz
      eval_mode: true
```

结果：
- `motion.object_names = ["ladder"]`
- `motion.object_ids = [10]`
- `object_id` one-hot 维度：**11**（与训练一致）
- ladder 在位置 10 为 1，其他位置为 0

### 真机部署

```python
# 手动指定物体 ID
obs_interface = RealRobotObservation(
    robot_interface=robot,
    pose_estimator=pose_est,
    motion_planner=planner,
    object_id=10,  # ladder 的全局 ID
)
```

Policy 收到的 `object_id` one-hot 在位置 10 为 1，与训练/eval 完全一致。

## 注意事项

1. **添加新物体时必须更新注册表**
2. **不要修改已有物体的 ID**（会破坏已训练的模型）
3. **注册表大小影响网络输入维度**（当前 11 维）
4. **所有环境（训练/eval/真机）使用同一个注册表**
