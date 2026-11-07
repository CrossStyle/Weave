# RobotLab 65 Bodies vs Weave 54 Bodies 问题解决

## 🔍 问题

**RobotLab实际情况**:
- 使用USD模型 (`g1_29dof_with_inspire_rev_1_0.usd`)
- 输出65个bodies
- 关节数量: 53 (与Weave一致)

**Weave期望**:
- 54个bodies

**差异**: 11个额外的bodies

---

## 💡 可能的原因

### USD vs URDF差异

1. **可视化链接**: USD可能包含额外的可视化mesh links
2. **手指关节**: 每个手指关节可能生成了额外的body
3. **辅助links**: 如TCP点、传感器attach点等
4. **分层结构**: USD的层级结构可能产生中间links

### 65个bodies的构成（推测）

```
Base body: 1
Torso/Waist: 3
Arms (2×7): 14
Legs (2×5): 10
Hands base: 2
Finger links: ?
----
Subtotal: 30+

额外的35个可能是:
- 手指的proximal, intermediate links
- 拇指的额外关节
- 可视化辅助links
```

---

## ✅ 三种解决方案

### 方案1: 保持所有65个bodies (推荐先尝试)

**优点**: 
- 保留完整数据
- 不丢失任何信息
- 与RobotLab完全一致

**缺点**:
- Weave可能需要适配

**使用方法**:
```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping keep_all
```

**验证**:
```bash
# 检查Weave是否能加载
python scripts/visualize_reference_motion.py \
    --motion_file weave_motion.npz

# 如果报错，说明Weave需要54个bodies，使用方案2
```

---

### 方案2: 只使用前54个bodies

**优点**:
- 符合Weave的期望
- 简单直接

**缺点**:
- 可能丢失部分手指link信息
- 需要确认前54个是哪些

**使用方法**:
```bash
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output weave_motion.npz \
    --object-name h_frame \
    --body-mapping first_54
```

**需要验证**: 前54个bodies是否包含所有关键links

---

### 方案3: 精确映射（最佳但需要分析）

**步骤**:

1. **识别65个bodies的具体内容**:
```python
import numpy as np

# 加载RobotLab输出
data = np.load('robotlab_output.npz')
print(f"Body count: {data['body_pos_w'].shape[1]}")

# 如果RobotLab脚本有body_names，打印出来
# 或者在生成时加上body names输出
```

2. **找出Weave的54个bodies是哪些**:
```python
# 查看Weave的参考数据
weave_data = np.load('data/train/woodchair_987clip.npz')
print(f"Weave body count: {weave_data['body_pos_w'].shape[1]}")

# 在Weave代码中找body names
# source/g1_hoi_learning/g1_hoi_learning/robots/g1_inspire.py
```

3. **创建精确映射**:
```python
# 在convert_robotlab_to_weave.py中添加
BODY_MAPPING_65_TO_54 = [
    # 需要根据实际body names确定
    # 例如: 0, 1, 2, ..., 跳过某些可视化links
]
```

---

## 🔬 诊断步骤

### 步骤1: 检查RobotLab输出的body内容

修改 `pkl_to_nqz_inspire.py`，在保存时添加body names:

```python
# 在RobotLab的pkl_to_nqz_inspire.py中
log = {
    # ... 现有字段 ...
    "body_names": robot.body_names,  # 添加这行
}
```

重新生成数据，然后检查:
```python
import numpy as np
data = np.load('robotlab_output.npz', allow_pickle=True)
print("RobotLab body names:")
for i, name in enumerate(data['body_names']):
    print(f"  {i}: {name}")
```

### 步骤2: 对比Weave的body结构

在Weave中运行:
```python
from g1_hoi_learning.robots import G1_INSPIRE_CFG
from isaaclab.app import AppLauncher

# 初始化Isaac
app_launcher = AppLauncher(...)
simulation_app = app_launcher.app

# 加载机器人
from isaaclab.assets import Articulation
robot = Articulation(G1_INSPIRE_CFG)

print(f"Weave body count: {len(robot.body_names)}")
print("Weave body names:")
for i, name in enumerate(robot.body_names):
    print(f"  {i}: {name}")
```

### 步骤3: 创建映射

对比两边的body names，创建映射:
```python
# 例如，如果发现RobotLab的body顺序是:
# 0-29: 主要bodies (匹配Weave)
# 30-53: 手指proximal (需要)
# 54-64: 手指intermediate或可视化links (可能不需要)

# 那么映射就是:
body_indices = list(range(54))  # 取前54个
```

---

## 🚀 推荐工作流程

### 第一步: 快速测试（方案1）

```bash
# 保持所有65个bodies
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output test_65bodies.npz \
    --object-name h_frame \
    --body-mapping keep_all

# 尝试在Weave中加载
python scripts/visualize_reference_motion.py \
    --motion_file test_65bodies.npz
```

**如果成功**: 
- ✅ 太好了！Weave可以处理65个bodies
- 继续使用这个方案

**如果失败**（报错body数量）:
- 进入第二步

---

### 第二步: 使用前54个（方案2）

```bash
# 只用前54个bodies
python scripts/convert_robotlab_to_weave.py \
    --input robotlab_output.npz \
    --output test_54bodies.npz \
    --object-name h_frame \
    --body-mapping first_54

# 测试
python scripts/visualize_reference_motion.py \
    --motion_file test_54bodies.npz
```

**如果成功**:
- ✅ 可以工作！
- 检查手指动作是否正常
- 如果手指有问题，说明丢失了重要的bodies

**如果手指不正常**:
- 进入第三步

---

### 第三步: 精确映射（方案3）

1. 输出两边的body names (按上面诊断步骤)
2. 手动创建映射
3. 修改转换脚本使用精确映射
4. 重新转换和测试

---

## 🛠️ 修改转换脚本支持自定义映射

如果需要方案3，在 `convert_robotlab_to_weave.py` 中添加:

```python
# 在文件开头定义映射
BODY_MAPPING_65_TO_54 = None  # 如果知道映射，在这里定义

def map_bodies(body_data, mapping_strategy, custom_mapping=None):
    """映射body数据"""
    if mapping_strategy == "keep_all":
        return body_data
    elif mapping_strategy == "first_54":
        return body_data[:, :54, ...]
    elif mapping_strategy == "custom" and custom_mapping:
        return body_data[:, custom_mapping, ...]
    return body_data

# 在convert_single_motion中使用
body_pos_w = map_bodies(robotlab_data['body_pos_w'], body_mapping, BODY_MAPPING_65_TO_54)
```

---

## 📊 预期结果

### 方案1成功的标志
```
✓ Weave加载65 bodies的motion
✓ 可视化正常
✓ 训练可以启动
```

### 方案2成功的标志
```
✓ Weave加载54 bodies的motion
✓ 主要动作正常
⚠ 手指动作可能不精确（如果丢失了手指links）
```

### 方案3成功的标志
```
✓ Weave加载54 bodies的motion
✓ 所有动作完全正常
✓ 包括细微的手指动作
```

---

## 💡 建议

1. **先试方案1**: 最简单，保留完整信息
2. **如果方案1不行，用方案2**: 快速解决
3. **如果需要精确控制，用方案3**: 需要额外分析

**最有可能的情况**: 
- 方案1会工作，因为Weave应该可以处理不同的body数量
- 如果不行，方案2应该足够，额外的11个bodies可能是辅助links

---

## 🔍 进一步调查

如果你能提供:
1. RobotLab输出的body names列表
2. Weave期望的body names列表

我可以创建精确的映射！

**临时解决方案**: 先用 `--body-mapping keep_all`，看看是否能工作。
