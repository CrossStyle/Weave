# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to train RL agent with RSL-RL and mass curriculum learning."""

"""Launch Isaac Sim Simulator first."""

import argparse
import sys

# Windows: torch 必须在启动 Isaac Sim 之前导入，否则 Kit 先加载的 DLL 会和 torch 的冲突
# 在 debug 模式下尤其重要，因为 debugpy 会先加载一些 DLL
import torch  # noqa: F401

from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# add argparse arguments
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL and curriculum learning.")
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
parser.add_argument("--video_interval", type=int, default=2000, help="Interval between video recordings (in steps).")
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument("--max_iterations", type=int, default=None, help="RL Policy training iterations.")
parser.add_argument(
    "--distributed", action="store_true", default=False, help="Run training with multiple GPUs or nodes."
)
parser.add_argument("--export_io_descriptors", action="store_true", default=False, help="Export IO descriptors.")
parser.add_argument(
    "--ray-proc-id", "-rid", type=int, default=None, help="Automatically configured by Ray integration, otherwise None."
)
# 课程学习相关参数
parser.add_argument("--curriculum", action="store_true", default=False, help="Enable mass curriculum learning.")
parser.add_argument("--initial_mass", type=float, default=20.0, help="Initial object mass (kg).")
parser.add_argument("--final_mass", type=float, default=20.0, help="Final object mass (kg).")
parser.add_argument("--mass_increment", type=float, default=1.0, help="Mass increment per stage (kg).")
parser.add_argument("--eval_interval", type=int, default=200, help="Curriculum evaluation interval (iterations).")
parser.add_argument("--eval_episodes", type=int, default=400, help="Number of episodes per evaluation.")  # （已废弃，使用 eval_sample_ratio）
parser.add_argument("--eval_sample_ratio", type=float, default=0.5, help="评估时抽样比例（0.5 = 50% 环境，可加速评估）")
parser.add_argument("--eval_early_stop_ratio", type=float, default=0.9, help="Early stopping 阈值（0.9 = 90% 环境完成就停止）")
parser.add_argument("--eval_min_envs_per_object", type=int, default=20, help="每个物体至少评估的环境数")
parser.add_argument("--success_threshold", type=float, default=0.8, help="Success rate threshold for promotion.")
parser.add_argument("--min_iterations", type=int, default=200, help="Minimum iterations per curriculum stage.")
parser.add_argument("--max_failures", type=int, default=3, help="Maximum consecutive failures before rollback.")
parser.add_argument(
    "--allow_regression",
    action=argparse.BooleanOptionalAction,
    default=True,
    help="Allow rollback on failure (use --no-allow_regression to disable).",
)
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# default to headless mode for training; pass --no-headless or override with --headless False to enable GUI
parser.set_defaults(headless=True)
args_cli, hydra_args = parser.parse_known_args()

# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Check for minimum supported RSL-RL version."""

import importlib.metadata as metadata
import platform

from packaging import version

# check minimum supported rsl-rl version
RSL_RL_VERSION = "3.0.1"
installed_version = metadata.version("rsl-rl-lib")
if version.parse(installed_version) < version.parse(RSL_RL_VERSION):
    if platform.system() == "Windows":
        cmd = [r".\isaaclab.bat", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    else:
        cmd = ["./isaaclab.sh", "-p", "-m", "pip", "install", f"rsl-rl-lib=={RSL_RL_VERSION}"]
    print(
        f"Please install the correct version of RSL-RL.\nExisting version is: '{installed_version}'"
        f" and required version is: '{RSL_RL_VERSION}'.\nTo install the correct version, run:"
        f"\n\n\t{' '.join(cmd)}\n"
    )
    exit(1)

"""Rest everything follows."""

import logging
import os
import time
from datetime import datetime

import gymnasium as gym
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import (
    DirectMARLEnv,
    DirectMARLEnvCfg,
    DirectRLEnvCfg,
    ManagerBasedRLEnvCfg,
    multi_agent_to_single_agent,
)
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils.dict import print_dict
from isaaclab.utils.io import dump_yaml

from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

# import logger
logger = logging.getLogger(__name__)

import g1_hoi_learning.tasks  # noqa: F401
from g1_hoi_learning.tasks.hoi.mdp.curriculum import MassCurriculumCfg, MassCurriculumManager
from g1_hoi_learning.tasks.hoi.mdp.terminations import motion_clip_end

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.deterministic = False
torch.backends.cudnn.benchmark = False


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Train with RSL-RL agent and optional mass curriculum learning."""
    # override configurations with non-hydra CLI arguments
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
    agent_cfg.max_iterations = (
        args_cli.max_iterations if args_cli.max_iterations is not None else agent_cfg.max_iterations
    )

    # set the environment seed
    # note: certain randomizations occur in the environment initialization so we set the seed here
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
    # check for invalid combination of CPU device with distributed training
    if args_cli.distributed and args_cli.device is not None and "cpu" in args_cli.device:
        raise ValueError(
            "Distributed training is not supported when using CPU device. "
            "Please use GPU device (e.g., --device cuda) for distributed training."
        )

    # multi-gpu training configuration
    if args_cli.distributed:
        env_cfg.sim.device = f"cuda:{app_launcher.local_rank}"
        agent_cfg.device = f"cuda:{app_launcher.local_rank}"

        # set seed to have diversity in different threads
        seed = agent_cfg.seed + app_launcher.local_rank
        env_cfg.seed = seed
        agent_cfg.seed = seed

    # 课程学习：添加 clip_end termination（评估需要）
    if args_cli.curriculum:
        if not hasattr(env_cfg, "terminations"):
            raise ValueError("Environment config must have terminations attribute for curriculum learning.")
        env_cfg.terminations.clip_end = DoneTerm(func=motion_clip_end, params={"command_name": "motion"}, time_out=True)

    # specify directory for logging experiments
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Logging experiment in directory: {log_root_path}")
    # specify directory for logging runs: {time-stamp}_{run_name}
    log_dir = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # The Ray Tune workflow extracts experiment name using the logging line below, hence, do not
    # change it (see PR #2346, comment-2819298849)
    print(f"Exact experiment name requested from command line: {log_dir}")
    if agent_cfg.run_name:
        log_dir += f"_{agent_cfg.run_name}"
    log_dir = os.path.join(log_root_path, log_dir)

    # set the IO descriptors export flag if requested
    if isinstance(env_cfg, ManagerBasedRLEnvCfg):
        env_cfg.export_io_descriptors = args_cli.export_io_descriptors
    else:
        logger.warning(
            "IO descriptors are only supported for manager based RL environments. No IO descriptors will be exported."
        )

    # set the log directory for the environment (works for all environment types)
    env_cfg.log_dir = log_dir

    # create isaac environment
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # convert to single-agent instance if required by the RL algorithm
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # save resume path before creating a new log_dir
    if agent_cfg.resume:
        # Allow --load_run to be a direct path to a run dir; otherwise treat it as a
        # run-name regex within this experiment.
        load_run_abs = os.path.abspath(agent_cfg.load_run)
        if os.path.isdir(load_run_abs):
            resume_path = get_checkpoint_path(
                os.path.dirname(load_run_abs), os.path.basename(load_run_abs), agent_cfg.load_checkpoint
            )
        else:
            resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)

    # wrap for video recording
    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join(log_dir, "videos", "train"),
            "step_trigger": lambda step: step % args_cli.video_interval == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    start_time = time.time()

    # wrap around environment for rsl-rl
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    # create runner from rsl-rl
    if agent_cfg.class_name != "OnPolicyRunner":
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=log_dir, device=agent_cfg.device)
    # write git state to logs
    runner.add_git_repo_to_log(__file__)
    # load the checkpoint
    if agent_cfg.resume:
        print(f"[INFO]: Loading model checkpoint from: {resume_path}")
        # load previously trained model
        runner.load(resume_path)

    # dump the configuration into log-directory
    dump_yaml(os.path.join(log_dir, "params", "env.yaml"), env_cfg)
    dump_yaml(os.path.join(log_dir, "params", "agent.yaml"), agent_cfg)

    # 初始化课程学习管理器
    curriculum_manager = None
    if args_cli.curriculum:
        curriculum_cfg = MassCurriculumCfg(
            enabled=True,
            initial_mass=args_cli.initial_mass,
            final_mass=args_cli.final_mass,
            mass_increment=args_cli.mass_increment,
            eval_interval=args_cli.eval_interval,
            eval_episodes=args_cli.eval_episodes,
            success_threshold=args_cli.success_threshold,

            eval_sample_ratio=args_cli.eval_sample_ratio,
            eval_early_stop_ratio=args_cli.eval_early_stop_ratio,
            eval_min_envs_per_object=args_cli.eval_min_envs_per_object,

            min_iterations_per_stage=args_cli.min_iterations,
            max_failures=args_cli.max_failures,
            allow_regression=args_cli.allow_regression,
        )
        curriculum_manager = MassCurriculumManager(
            cfg=curriculum_cfg,
            env=env,
            log_dir=log_dir,
            tb_writer=runner.writer if hasattr(runner, "writer") else None,
        )
        dump_yaml(os.path.join(log_dir, "params", "curriculum.yaml"), curriculum_cfg)

    # 自定义训练循环，集成课程学习
    if curriculum_manager is not None:
        train_with_curriculum(runner, curriculum_manager, agent_cfg.max_iterations)
    else:
        # 标准训练
        runner.learn(num_learning_iterations=agent_cfg.max_iterations, init_at_random_ep_len=True)

    print(f"Training time: {round(time.time() - start_time, 2)} seconds")

    # 保存课程学习总结
    if curriculum_manager is not None:
        curriculum_manager.save_summary()

    # close the simulator
    env.close()


def train_with_curriculum(runner: OnPolicyRunner, curriculum: MassCurriculumManager, max_iterations: int):
    """训练循环，集成课程学习评估和更新

    Args:
        runner: RSL-RL OnPolicyRunner
        curriculum: 课程学习管理器
        max_iterations: 最大训练迭代数
    """
    print("\n[INFO] 开始带课程学习的训练...")

    # 获取 policy 模块（MuonPPO 使用 self.policy，不是 actor_critic）
    # 不使用 get_inference_policy，避免 inference_mode 冲突
    actor_critic = runner.alg.policy
    
    remaining_iterations = max_iterations
    
    while remaining_iterations > 0:
        # 当前总进度
        current_progress = max_iterations - remaining_iterations
        
        # 计算下次评估前可以训练多少步
        iterations_until_eval = min(curriculum.cfg.eval_interval, remaining_iterations)
        
        # 检查当前阶段是否满足最少训练步数（使用训练后的 iteration 来判断）
        stage_iterations = current_progress - curriculum.stage_start_iteration
        min_iters_needed = curriculum.cfg.min_iterations_per_stage - stage_iterations
        if min_iters_needed > 0:
            iterations_until_eval = min(min_iters_needed, remaining_iterations)
        
        print(f"\n[INFO] 训练 {iterations_until_eval} iterations (总进度: {current_progress}/{max_iterations})...")
        
        # 训练这一段
        runner.learn(num_learning_iterations=iterations_until_eval, init_at_random_ep_len=(current_progress == 0))
        
        # 更新进度
        remaining_iterations -= iterations_until_eval
        curriculum.iteration = max_iterations - remaining_iterations
        
        # 记录课程学习状态到 tensorboard
        if hasattr(runner, "writer") and runner.writer is not None:
            status = curriculum.get_status()
            runner.writer.add_scalar("curriculum/current_mass", status["current_mass"], curriculum.iteration)
            runner.writer.add_scalar("curriculum/stage", status["stage"], curriculum.iteration)
            runner.writer.add_scalar("curriculum/stage_iterations", status["stage_iterations"], curriculum.iteration)
        
        # 检查是否需要评估
        if remaining_iterations > 0 and curriculum.should_evaluate():
            print(f"\n[INFO] 开始课程学习评估 (iteration {curriculum.iteration})...")
            
            # 保存当前训练状态
            runner.save(os.path.join(runner.log_dir, f"model_{curriculum.iteration}.pt"))
            
            # 评估
            eval_result = curriculum.evaluate(actor_critic)
            
            # 更新课程
            curriculum.update(eval_result)
            
            # 评估后重置环境，确保训练状态一致性
            print(f"[INFO] 评估完成，重置环境继续训练...\n")
            runner.env.reset()
    
    print("\n[INFO] 课程学习训练完成！")


if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    simulation_app.close()
