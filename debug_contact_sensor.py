"""Debug script to check contact sensor initialization."""
import torch
import sys
import os

# Add isaaclab to path if needed
sys.path.append("d:/code/robot/isaaclab/isaaclab-2.3.0/source")

from omni.isaac.lab.app import AppLauncher

# Launch the simulation
app_launcher = AppLauncher({"headless": True})
simulation_app = app_launcher.app

# Import after simulation app is created
from isaaclab_tasks.utils.hydra import hydra_task_config

# Load the config
from omegaconf import DictConfig
import hydra
from hydra import compose, initialize

with initialize(version_base=None, config_path="./configs/track"):
    cfg = compose(config_name="train", overrides=[
        "task=G1-Inspire-HOI-v0",
        "curriculum=true",
        "agent.policy.compile=false"
    ])

print("=" * 80)
print("DEBUG: Checking environment configuration")
print("=" * 80)

# Try to create the environment
try:
    from g1_hoi_learning.tasks.hoi import make_g1_hoi_learning_env
    
    env_cfg = cfg.task
    print(f"\nEnvironment config loaded: {env_cfg.env.scene}")
    
    # Check if object is configured
    if hasattr(env_cfg.env.scene, 'object'):
        print(f"Object config: {env_cfg.env.scene.object}")
    else:
        print("WARNING: No object in scene config!")
    
    # Check contact sensor config
    if hasattr(env_cfg.env.scene, 'contact_sensor'):
        sensor_cfg = env_cfg.env.scene.contact_sensor
        print(f"\nContact sensor config:")
        print(f"  prim_path: {sensor_cfg.prim_path}")
        print(f"  filter count: {len(sensor_cfg.filter_prim_paths_expr)}")
        print(f"  history_length: {sensor_cfg.history_length}")
    
    # Try to create environment
    print("\n" + "=" * 80)
    print("Creating environment...")
    print("=" * 80)
    env = make_g1_hoi_learning_env(env_cfg, motion_files=env_cfg.motion_files)
    
    print(f"\nEnvironment created successfully!")
    print(f"Number of environments: {env.num_envs}")
    
    # Check the contact sensor
    if "contact_sensor" in env.scene:
        sensor = env.scene["contact_sensor"]
        print(f"\nContact sensor found:")
        print(f"  Device: {sensor.device}")
        print(f"  Num bodies: {sensor._num_bodies}")
        
        # Reset and take a step to initialize data
        env.reset()
        print(f"\nAfter reset:")
        if sensor.data.force_matrix_w is not None:
            print(f"  force_matrix_w shape: {sensor.data.force_matrix_w.shape}")
            print(f"  Expected shape: (num_envs={env.num_envs}, num_bodies={sensor._num_bodies}, num_filters=54, 3)")
        else:
            print(f"  force_matrix_w is None!")
        
        # Take a step
        actions = torch.zeros(env.num_envs, env.action_space.shape[0], device=env.device)
        env.step(actions)
        
        print(f"\nAfter first step:")
        if sensor.data.force_matrix_w is not None:
            print(f"  force_matrix_w shape: {sensor.data.force_matrix_w.shape}")
        else:
            print(f"  force_matrix_w is None!")
    else:
        print("\nWARNING: contact_sensor not found in scene!")
    
    print("\n" + "=" * 80)
    print("SUCCESS: Environment initialized without errors")
    print("=" * 80)
    
except Exception as e:
    print("\n" + "=" * 80)
    print("ERROR during environment creation:")
    print("=" * 80)
    import traceback
    traceback.print_exc()

finally:
    simulation_app.close()
