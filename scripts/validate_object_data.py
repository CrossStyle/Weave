"""
验证和可视化物体数据的工具脚本

用法:
    python scripts/validate_object_data.py --object woodchair
    python scripts/validate_object_data.py --object your_object --visualize
"""

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


def validate_surface(surface_path: Path) -> dict:
    """验证surface.npy文件"""
    print(f"\n{'='*60}")
    print("验证 surface.npy")
    print(f"{'='*60}")
    
    if not surface_path.exists():
        print(f"❌ 文件不存在: {surface_path}")
        return {'valid': False}
    
    try:
        surface = np.load(surface_path)
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return {'valid': False}
    
    print(f"✅ 文件加载成功")
    print(f"  - Shape: {surface.shape}")
    print(f"  - Dtype: {surface.dtype}")
    print(f"  - Size: {surface.nbytes / 1024:.2f} KB")
    
    stats = {
        'valid': True,
        'shape': surface.shape,
        'dtype': str(surface.dtype),
        'num_points': surface.shape[0],
        'min': surface.min(axis=0),
        'max': surface.max(axis=0),
        'mean': surface.mean(axis=0),
        'std': surface.std(axis=0),
    }
    
    # 检查格式
    issues = []
    if len(surface.shape) != 2:
        issues.append(f"Shape应该是2D，实际是{len(surface.shape)}D")
    if surface.shape[1] != 3:
        issues.append(f"第二维应该是3 (x,y,z)，实际是{surface.shape[1]}")
    if surface.dtype != np.float32:
        issues.append(f"Dtype应该是float32，实际是{surface.dtype}")
    
    if issues:
        print(f"\n⚠️  发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        stats['valid'] = False
    else:
        print(f"\n✅ 格式验证通过")
    
    print(f"\n统计信息:")
    print(f"  - 点数: {stats['num_points']}")
    print(f"  - X范围: [{stats['min'][0]:.3f}, {stats['max'][0]:.3f}]")
    print(f"  - Y范围: [{stats['min'][1]:.3f}, {stats['max'][1]:.3f}]")
    print(f"  - Z范围: [{stats['min'][2]:.3f}, {stats['max'][2]:.3f}]")
    print(f"  - 中心: ({stats['mean'][0]:.3f}, {stats['mean'][1]:.3f}, {stats['mean'][2]:.3f})")
    
    return stats


def validate_sdf(sdf_path: Path) -> dict:
    """验证sdf_128.npz文件"""
    print(f"\n{'='*60}")
    print("验证 sdf_128.npz")
    print(f"{'='*60}")
    
    if not sdf_path.exists():
        print(f"❌ 文件不存在: {sdf_path}")
        return {'valid': False}
    
    try:
        sdf_data = np.load(sdf_path)
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return {'valid': False}
    
    print(f"✅ 文件加载成功")
    print(f"  - Keys: {list(sdf_data.keys())}")
    print(f"  - Size: {sdf_path.stat().st_size / 1024:.2f} KB")
    
    # 必需字段
    required_keys = ['sdf', 'center', 'radius', 'grid_bound', 'resolution', 'object_name']
    optional_keys = ['mesh_sha256', 'surface_sha256', 'generator_version', 'sign_convention',
                     'surface_abs_sdf_mean', 'surface_abs_sdf_p95', 'surface_abs_sdf_max']
    
    stats = {
        'valid': True,
        'keys': list(sdf_data.keys()),
    }
    
    # 检查必需字段
    missing_keys = [k for k in required_keys if k not in sdf_data.keys()]
    if missing_keys:
        print(f"\n❌ 缺少必需字段: {missing_keys}")
        stats['valid'] = False
        return stats
    
    print(f"\n✅ 包含所有必需字段")
    
    # 检查可选字段
    present_optional = [k for k in optional_keys if k in sdf_data.keys()]
    if present_optional:
        print(f"✅ 包含可选字段: {present_optional}")
    
    # 检查SDF网格
    sdf_grid = sdf_data['sdf']
    print(f"\nSDF网格信息:")
    print(f"  - Shape: {sdf_grid.shape}")
    print(f"  - Dtype: {sdf_grid.dtype}")
    print(f"  - 分辨率: {sdf_data['resolution']}")
    print(f"  - 网格边界: {sdf_data['grid_bound']}")
    print(f"  - 值范围: [{sdf_grid.min():.3f}, {sdf_grid.max():.3f}]")
    print(f"  - 内部体素数 (负值): {(sdf_grid < 0).sum()}")
    print(f"  - 外部体素数 (正值): {(sdf_grid > 0).sum()}")
    print(f"  - 表面体素数 (≈0): {(np.abs(sdf_grid) < 0.01).sum()}")
    
    stats.update({
        'sdf_shape': sdf_grid.shape,
        'sdf_dtype': str(sdf_grid.dtype),
        'resolution': int(sdf_data['resolution']),
        'grid_bound': float(sdf_data['grid_bound']),
        'sdf_min': float(sdf_grid.min()),
        'sdf_max': float(sdf_grid.max()),
        'center': sdf_data['center'],
        'radius': float(sdf_data['radius']),
        'object_name': str(sdf_data['object_name']),
    })
    
    # 检查格式
    issues = []
    if len(sdf_grid.shape) != 3:
        issues.append(f"SDF应该是3D，实际是{len(sdf_grid.shape)}D")
    if sdf_grid.shape[0] != sdf_grid.shape[1] or sdf_grid.shape[1] != sdf_grid.shape[2]:
        issues.append(f"SDF应该是立方体网格，实际shape: {sdf_grid.shape}")
    if sdf_grid.dtype != np.float32:
        issues.append(f"SDF dtype应该是float32，实际是{sdf_grid.dtype}")
    if int(sdf_data['resolution']) != sdf_grid.shape[0]:
        issues.append(f"分辨率不匹配: resolution={sdf_data['resolution']}, shape={sdf_grid.shape[0]}")
    
    if issues:
        print(f"\n⚠️  发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        stats['valid'] = False
    else:
        print(f"\n✅ 格式验证通过")
    
    # 额外信息
    if 'generator_version' in sdf_data:
        print(f"\n元数据:")
        print(f"  - 物体名称: {sdf_data['object_name']}")
        print(f"  - 生成器版本: {sdf_data['generator_version']}")
        if 'sign_convention' in sdf_data:
            print(f"  - 符号约定: {sdf_data['sign_convention']}")
    
    return stats


def visualize_surface(surface: np.ndarray, title: str = "Surface Points"):
    """可视化表面采样点"""
    fig = plt.figure(figsize=(12, 10))
    
    # 3D散点图
    ax1 = fig.add_subplot(221, projection='3d')
    ax1.scatter(surface[:, 0], surface[:, 1], surface[:, 2], 
                c=surface[:, 2], cmap='viridis', s=1, alpha=0.6)
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    ax1.set_zlabel('Z')
    ax1.set_title(f'{title} - 3D View')
    
    # XY平面投影
    ax2 = fig.add_subplot(222)
    ax2.scatter(surface[:, 0], surface[:, 1], c=surface[:, 2], cmap='viridis', s=1, alpha=0.6)
    ax2.set_xlabel('X')
    ax2.set_ylabel('Y')
    ax2.set_title('XY Projection')
    ax2.axis('equal')
    
    # XZ平面投影
    ax3 = fig.add_subplot(223)
    ax3.scatter(surface[:, 0], surface[:, 2], c=surface[:, 1], cmap='viridis', s=1, alpha=0.6)
    ax3.set_xlabel('X')
    ax3.set_ylabel('Z')
    ax3.set_title('XZ Projection')
    ax3.axis('equal')
    
    # YZ平面投影
    ax4 = fig.add_subplot(224)
    ax4.scatter(surface[:, 1], surface[:, 2], c=surface[:, 0], cmap='viridis', s=1, alpha=0.6)
    ax4.set_xlabel('Y')
    ax4.set_ylabel('Z')
    ax4.set_title('YZ Projection')
    ax4.axis('equal')
    
    plt.tight_layout()
    return fig


def visualize_sdf(sdf_data: dict, title: str = "SDF Slices"):
    """可视化SDF切片"""
    sdf_grid = sdf_data['sdf']
    resolution = sdf_grid.shape[0]
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # 选择不同位置的切片
    slices = [
        resolution // 4,      # 1/4
        resolution // 2,      # 中间
        resolution * 3 // 4,  # 3/4
    ]
    
    # XY切片 (固定Z)
    for i, z in enumerate(slices):
        ax = axes[0, i]
        im = ax.imshow(sdf_grid[:, :, z].T, cmap='RdBu', 
                      vmin=-0.5, vmax=0.5, origin='lower')
        ax.set_title(f'XY Slice (Z={z}/{resolution})')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        plt.colorbar(im, ax=ax, label='SDF')
    
    # XZ切片 (固定Y)
    for i, y in enumerate(slices):
        ax = axes[1, i]
        im = ax.imshow(sdf_grid[:, y, :].T, cmap='RdBu', 
                      vmin=-0.5, vmax=0.5, origin='lower')
        ax.set_title(f'XZ Slice (Y={y}/{resolution})')
        ax.set_xlabel('X')
        ax.set_ylabel('Z')
        plt.colorbar(im, ax=ax, label='SDF')
    
    plt.suptitle(f'{title}\n负值=内部 (蓝), 正值=外部 (红), 0=表面 (白)')
    plt.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser(description="验证和可视化物体数据")
    parser.add_argument(
        "--object",
        type=str,
        required=True,
        help="物体名称 (例如: woodchair)"
    )
    parser.add_argument(
        "--objects-dir",
        type=str,
        default="D:/code/robot/Weave/source/g1_hoi_learning/g1_hoi_learning/objects",
        help="物体目录路径"
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="显示可视化图表"
    )
    parser.add_argument(
        "--save-plots",
        type=str,
        default=None,
        help="保存图表到指定目录"
    )
    
    args = parser.parse_args()
    
    # 路径设置
    object_dir = Path(args.objects_dir) / args.object
    if not object_dir.exists():
        print(f"❌ 物体目录不存在: {object_dir}")
        return
    
    print(f"\n{'='*60}")
    print(f"验证物体数据: {args.object}")
    print(f"目录: {object_dir}")
    print(f"{'='*60}")
    
    # 验证surface.npy
    surface_path = object_dir / "surface.npy"
    surface_stats = validate_surface(surface_path)
    
    # 验证sdf_128.npz
    sdf_path = object_dir / "sdf_128.npz"
    sdf_stats = validate_sdf(sdf_path)
    
    # 总结
    print(f"\n{'='*60}")
    print("验证总结")
    print(f"{'='*60}")
    
    if surface_stats.get('valid', False) and sdf_stats.get('valid', False):
        print("✅ 所有数据验证通过!")
    else:
        print("❌ 存在验证错误，请检查上述信息")
    
    # 可视化
    if args.visualize or args.save_plots:
        if not surface_stats.get('valid', False) or not sdf_stats.get('valid', False):
            print("\n⚠️  数据验证失败，跳过可视化")
            return
        
        print(f"\n生成可视化...")
        
        # 加载数据
        surface = np.load(surface_path)
        sdf_data = np.load(sdf_path)
        
        # 生成图表
        fig_surface = visualize_surface(surface, f"{args.object} - Surface Points")
        fig_sdf = visualize_sdf(sdf_data, f"{args.object} - SDF")
        
        # 保存或显示
        if args.save_plots:
            save_dir = Path(args.save_plots)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            surface_plot_path = save_dir / f"{args.object}_surface.png"
            sdf_plot_path = save_dir / f"{args.object}_sdf.png"
            
            fig_surface.savefig(surface_plot_path, dpi=150, bbox_inches='tight')
            fig_sdf.savefig(sdf_plot_path, dpi=150, bbox_inches='tight')
            
            print(f"\n✅ 图表已保存:")
            print(f"  - {surface_plot_path}")
            print(f"  - {sdf_plot_path}")
        
        if args.visualize:
            plt.show()


if __name__ == "__main__":
    main()
