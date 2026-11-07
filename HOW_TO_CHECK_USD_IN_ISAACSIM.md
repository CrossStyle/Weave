# IsaacSim GUI 中检查 USD 文件的步骤

## 1. 启动 IsaacSim
```bash
# 在你的 isaaclab conda 环境中
cd D:\code\robot\Weave
# 启动 IsaacSim（根据你的安装路径）
```

## 2. 在 GUI 中打开 USD 文件
- File → Open
- 导航到: source/g1_hoi_learning/g1_hoi_learning/objects/ladder/ladder_collision.usd

## 3. 查看刚体信息

### 方法 A: 使用 Stage 面板
1. 打开 Window → Stage（如果还没打开）
2. 在 Stage 树中浏览所有 Prim
3. 查找带有以下图标的 Prim：
   - 🔵 表示 RigidBody
   - 🟢 表示 Collision

### 方法 B: 使用 Property 面板
1. 在 Stage 中选择一个 Prim
2. 打开 Window → Property
3. 查看 "Physics" 部分：
   - 是否有 "RigidBodyAPI"
   - 是否有 "CollisionAPI"
   - 是否有 "MassAPI"

### 方法 C: 使用 Physics Inspector
1. Window → Physics → Physics Inspector
2. 会显示场景中所有的刚体和碰撞体

## 4. 关键检查点

### ✓ 正常的 USD 应该包含：
```
/World
  └─ /Object (或其他名称)
      ├─ RigidBodyAPI ✓
      ├─ CollisionAPI ✓
      └─ MassAPI ✓
```

### ❌ 有问题的 USD 可能是：
```
/World
  └─ /Object
      └─ /SomeMesh
          ├─ 只有 Mesh，没有 RigidBodyAPI ✗
          └─ 或者完全是空的 ✗
```

## 5. 对比检查

同时打开这两个文件进行对比：
- ladder_collision.usd（有问题）
- h_frame/hframe_collision.usd（正常工作）

看看它们的结构有什么不同。

## 6. 常见问题

### 问题：USD 文件只有 Mesh，没有 RigidBody
**原因**: 文件是纯几何文件，没有物理属性
**解决**: 需要在 USD 中添加 Physics API

### 问题：RigidBody 存在但 ContactSensor 检测不到
**原因**: 
- activate_contact_sensors=True 没生效
- 或者 Physics Material 配置问题

### 问题：num_bodies = 0
**原因**: 
- USD 文件是 articulation（关节体）而不是 rigid object
- 或者 root prim 下没有直接的 RigidBody 子节点
