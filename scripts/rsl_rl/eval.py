# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Script to evaluate a checkpoint if an RL agent from RSL-RL.
"""

"""Launch Isaac Sim Simulator first."""

import argparse
import sys
import torch  # noqa: F401
from isaaclab.app import AppLauncher

# local imports
import cli_args  # isort: skip

# add argparse arguments
parser = argparse.ArgumentParser(description="Evaluation of an RSL-RL agent.")
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
parser.add_argument(
    "--num_envs", type=int, default=None, help="Number of environments. Defaults to the number of clips."
)
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
parser.add_argument("--real-time", action="store_true", default=False, help="Run in real-time, if possible.")
parser.add_argument("--output_dir", type=str, default=None, help="Where to write metrics.json. Defaults to <run>/eval.")
parser.add_argument(
    "--video", action="store_true", default=False,
    help="After eval, save a video of one successful rollout (a random one if all failed).",
)
parser.add_argument(
    "--effort", action="store_true", default=False,
    help="Analyze and save joint effort (torque) statistics for successful rollouts.",
)
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)
# parse the arguments
args_cli, hydra_args = parser.parse_known_args()
# always enable cameras to record video
if args_cli.video:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Rest everything follows."""

import json
import os
import re
import time

import gymnasium as gym
import torch
import numpy as np
from rsl_rl.runners import OnPolicyRunner
from tqdm import tqdm

from isaacsim.core.simulation_manager import SimulationManager

from isaaclab.envs import DirectMARLEnv, DirectMARLEnvCfg, DirectRLEnvCfg, ManagerBasedRLEnvCfg, multi_agent_to_single_agent
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils.assets import retrieve_file_path

from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import get_checkpoint_path
from isaaclab_tasks.utils.hydra import hydra_task_config

import g1_hoi_learning.tasks  # noqa: F401
from g1_hoi_learning.tasks.hoi.mdp.commands import MotionCommand
from g1_hoi_learning.tasks.hoi.mdp.terminations import motion_clip_end


def read_motion_num_clips(motion_files: list[str]) -> int:
    return sum(len(np.asarray(np.load(f, allow_pickle=True)["motion_lengths"])) for f in motion_files)


def read_motion_clip_names(motion_files: list[str]) -> list[str]:
    return [str(x) for f in motion_files for x in np.asarray(np.load(f, allow_pickle=True)["motion_names"])]


class ClipEvaluator:
    """Accumulates per-clip statistics over each env's first episode.
    """

    def __init__(self, env: RslRlVecEnvWrapper, clip_names: list[str], command_name: str = "motion"):
        self.env = env.unwrapped
        self.device = self.env.device
        self.command: MotionCommand = self.env.command_manager.get_term(command_name)
        self.term_mgr = self.env.termination_manager
        self.term_names = list(self.term_mgr.active_terms)
        self.fail_names = [n for n in self.term_names if not self.term_mgr.get_term_cfg(n).time_out]
        if "clip_end" not in self.term_names:
            raise ValueError("clip-wise eval needs the 'clip_end' termination term; it is not active.")

        self.metric_keys = list(self.command.metrics)

        n = self.env.num_envs
        self.clip_ids = self.command.env_clip.clone()
        self.clip_len = self.command.motion.clip_lengths[self.clip_ids].clone()
        self.clip_names = [clip_names[int(i)] for i in self.clip_ids]

        self.finished = torch.zeros(n, dtype=torch.bool, device=self.device)
        self.success = torch.zeros(n, dtype=torch.bool, device=self.device)
        self.steps = torch.zeros(n, dtype=torch.long, device=self.device)
        self.cause = [""] * n
        self.sums = {k: torch.zeros(n, device=self.device) for k in self.metric_keys}

    @property
    def max_steps(self) -> int:
        return int(self.clip_len.max().item()) + 5

    def collect(self) -> None:
        self.command._update_metrics()
        active = (~self.finished).float()
        for k in self.metric_keys:
            self.sums[k] += self.command.metrics[k] * active
        self.steps += ~self.finished

    def update(self, dones: torch.Tensor, time_outs: torch.Tensor) -> None:
        newly = dones.bool() & ~self.finished
        if not newly.any():
            return
        terminated = dones.bool() & ~time_outs
        flags = {n: self.term_mgr.get_term(n) for n in self.term_names}
        self.success |= newly & flags["clip_end"] & ~terminated
        for i in newly.nonzero(as_tuple=False).flatten().tolist():
            if terminated[i]:
                self.cause[i] = next((n for n in self.fail_names if flags[n][i]), "unknown")
            else:
                self.cause[i] = "clip_end" if flags["clip_end"][i] else "time_out"
        self.finished |= newly

    @property
    def done(self) -> bool:
        return bool(self.finished.all())

    def results(self) -> dict:
        steps = self.steps.clamp(min=1)
        per_clip = {k: (v / steps).cpu().tolist() for k, v in self.sums.items()}
        progress = (self.steps.float() / self.clip_len.clamp(min=1).float()).clamp(max=1.0)
        success = self.success.cpu()

        def agg(mask: torch.Tensor) -> dict[str, float]:
            if not mask.any():
                return {k: float("nan") for k in self.metric_keys}
            frames = self.steps[mask].sum().float()
            return {k: float(self.sums[k][mask].sum() / frames) for k in self.metric_keys}

        return {
            "num_clips": int(self.env.num_envs),
            "success_rate": float(success.float().mean()),
            "progress_rate": float(progress.mean()),
            "metric_keys": self.metric_keys,
            "metrics_all": agg(torch.ones_like(self.success)),
            "metrics_success": agg(self.success),
            "failures": {n: self.cause.count(n) for n in self.fail_names if self.cause.count(n) > 0},
            "clips": [
                {
                    "env": i,
                    "clip_id": int(self.clip_ids[i]),
                    "name": self.clip_names[i],
                    "length": int(self.clip_len[i]),
                    "steps": int(self.steps[i]),
                    "progress": float(progress[i]),
                    "success": bool(success[i]),
                    "cause": self.cause[i],
                    **{k: per_clip[k][i] for k in self.metric_keys},
                }
                for i in range(self.env.num_envs)
            ],
        }


class JointEffortAnalyzer:
    """Records and analyzes joint efforts (torques) for successful rollouts."""

    def __init__(self, env: RslRlVecEnvWrapper, max_steps: int, robot_name: str = "robot"):
        self.env = env.unwrapped
        self.robot = self.env.scene[robot_name]
        self.device = self.env.device
        n = self.env.num_envs
        num_joints = self.robot.num_joints
        
        # Storage for trajectory data
        self.joint_pos_history = torch.zeros(max_steps, n, num_joints, device=self.device)
        self.joint_vel_history = torch.zeros(max_steps, n, num_joints, device=self.device)
        self.joint_target_history = torch.zeros(max_steps, n, num_joints, device=self.device)
        self.joint_effort_history = torch.zeros(max_steps, n, num_joints, device=self.device)
        
        # Get joint names
        self.joint_names = self.robot.joint_names
        
        # Extract effort limits and PD gains from actuator config
        self.effort_limits = torch.zeros(num_joints, device=self.device)
        self.stiffness = torch.zeros(num_joints, device=self.device)
        self.damping = torch.zeros(num_joints, device=self.device)
        self._extract_actuator_params()
        
        self.t = 0
        self.success_mask = torch.zeros(n, dtype=torch.bool, device=self.device)
        
        # Check what torque data source is available
        self.torque_source = self._detect_torque_source()
        print(f"[INFO] Joint effort analysis using: {self.torque_source}")
    
    def _detect_torque_source(self) -> str:
        """Detect what torque data source is available."""
        if hasattr(self.robot.data, 'applied_torque'):
            return "applied_torque (actual from actuator model)"
        elif hasattr(self.robot.data, 'computed_torque'):
            return "computed_torque (with manual clipping)"
        else:
            return "PD control estimation"
    
    def _extract_actuator_params(self):
        """Extract effort limits, stiffness, and damping from actuator configuration."""
        robot_cfg = self.robot.cfg
        
        for actuator_name, actuator_cfg in robot_cfg.actuators.items():
            # Get joint indices for this actuator
            joint_names = []
            for expr in actuator_cfg.joint_names_expr:
                matched_names = [name for name in self.joint_names if self._match_pattern(name, expr)]
                joint_names.extend(matched_names)
            
            for joint_name in joint_names:
                if joint_name in self.joint_names:
                    idx = self.joint_names.index(joint_name)
                    
                    # Extract effort limit (handle both effort_limit_sim and effort_limit)
                    effort_cfg = getattr(actuator_cfg, 'effort_limit_sim', None) or getattr(actuator_cfg, 'effort_limit', None)
                    if effort_cfg is not None:
                        if isinstance(effort_cfg, dict):
                            for pattern, limit in effort_cfg.items():
                                if self._match_pattern(joint_name, pattern):
                                    self.effort_limits[idx] = limit
                                    break
                        else:
                            self.effort_limits[idx] = effort_cfg
                    
                    # Extract stiffness
                    if hasattr(actuator_cfg, 'stiffness'):
                        stiff_cfg = actuator_cfg.stiffness
                        if isinstance(stiff_cfg, dict):
                            for pattern, stiff in stiff_cfg.items():
                                if self._match_pattern(joint_name, pattern):
                                    self.stiffness[idx] = stiff
                                    break
                        else:
                            self.stiffness[idx] = stiff_cfg
                    
                    # Extract damping
                    if hasattr(actuator_cfg, 'damping'):
                        damp_cfg = actuator_cfg.damping
                        if isinstance(damp_cfg, dict):
                            for pattern, damp in damp_cfg.items():
                                if self._match_pattern(joint_name, pattern):
                                    self.damping[idx] = damp
                                    break
                        else:
                            self.damping[idx] = damp_cfg
    
    def _match_pattern(self, name: str, pattern: str) -> bool:
        """Simple pattern matching for joint names (supports .* wildcards)."""
        import re
        regex_pattern = pattern.replace(".*", ".*?")
        return re.match(regex_pattern, name) is not None
    
    def record(self, joint_targets: torch.Tensor):
        """Record joint states and targets at current timestep."""
        self.joint_pos_history[self.t] = self.robot.data.joint_pos
        self.joint_vel_history[self.t] = self.robot.data.joint_vel
        self.joint_target_history[self.t] = joint_targets
        
        # Try to use actual applied torque from simulation if available
        if hasattr(self.robot.data, 'applied_torque') and self.robot.data.applied_torque is not None:
            # Use actual applied torque from the actuator model (after clipping)
            effort = self.robot.data.applied_torque
        elif hasattr(self.robot.data, 'computed_torque') and self.robot.data.computed_torque is not None:
            # Use computed torque and apply clipping manually
            effort = torch.clamp(self.robot.data.computed_torque, -self.effort_limits, self.effort_limits)
        else:
            # Fallback: estimate using PD control law
            pos_error = joint_targets - self.robot.data.joint_pos
            vel_error = -self.robot.data.joint_vel  # target velocity is 0 for position control
            effort_raw = self.stiffness * pos_error + self.damping * vel_error
            
            # Apply effort limit (clamp to [-limit, +limit])
            effort = torch.clamp(effort_raw, -self.effort_limits, self.effort_limits)
        
        self.joint_effort_history[self.t] = effort
        self.t += 1
    
    def mark_success(self, success_mask: torch.Tensor):
        """Mark which environments completed successfully."""
        self.success_mask = success_mask.bool()
    
    def analyze(self) -> dict:
        """Analyze joint efforts for successful rollouts."""
        if not self.success_mask.any():
            return {"warning": "No successful rollouts to analyze"}
        
        # Only analyze successful environments
        success_efforts = self.joint_effort_history[:self.t, self.success_mask, :]  # (T, N_success, J)
        
        results = {
            "joint_names": self.joint_names,
            "effort_limits": self.effort_limits.cpu().tolist(),
            "joint_analysis": []
        }
        
        num_joints = len(self.joint_names)
        for j in range(num_joints):
            joint_efforts = success_efforts[:, :, j]  # (T, N_success)
            effort_limit = self.effort_limits[j].item()
            
            if effort_limit > 0:
                # Compute statistics
                abs_efforts = torch.abs(joint_efforts)
                mean_effort = abs_efforts.mean().item()
                max_effort = abs_efforts.max().item()
                
                # Torque margin (limit - current)
                mean_margin = effort_limit - mean_effort
                
                # Peak ratio (current / limit)
                peak_ratio = max_effort / effort_limit if effort_limit > 0 else 0.0
                
                results["joint_analysis"].append({
                    "joint_name": self.joint_names[j],
                    "effort_limit": effort_limit,
                    "mean_effort": mean_effort,
                    "max_effort": max_effort,
                    "mean_margin": mean_margin,
                    "peak_ratio": peak_ratio,
                    "margin_percentage": (mean_margin / effort_limit * 100) if effort_limit > 0 else 0.0
                })
        
        # Overall statistics
        all_efforts = success_efforts.flatten()
        all_limits = self.effort_limits.repeat(self.t * self.success_mask.sum().item())
        
        results["overall"] = {
            "num_success_envs": int(self.success_mask.sum()),
            "num_timesteps": self.t,
            "mean_effort_all_joints": float(torch.abs(all_efforts).mean()),
            "max_effort_all_joints": float(torch.abs(all_efforts).max()),
            "mean_limit": float(all_limits[all_limits > 0].mean()) if (all_limits > 0).any() else 0.0
        }
        
        return results
    
    def save_results(self, output_path: str):
        """Save analysis results to JSON file."""
        results = self.analyze()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[INFO] Saved joint effort analysis to {output_path}")


class RolloutRecorder:
    """Stores every env's root/joint poses each step so one rollout can be replayed and filmed after eval."""

    def __init__(self, env: RslRlVecEnvWrapper, max_steps: int):
        self.env = env.unwrapped
        self.scene = self.env.scene
        n, dev = self.env.num_envs, self.env.device
        self.root_poses = {
            name: torch.zeros(max_steps, n, 7, device=dev)
            for name in [*self.scene.articulations, *self.scene.rigid_objects]
        }
        self.joint_pos = {
            name: torch.zeros(max_steps, n, self.scene[name].num_joints, device=dev)
            for name in self.scene.articulations
        }
        self.t = 0

    def record(self) -> None:
        """Call before each env.step(); frame t then holds the state the policy acted on at step t."""
        for name, buf in self.root_poses.items():
            buf[self.t] = self.scene[name].data.root_pose_w
        for name, buf in self.joint_pos.items():
            buf[self.t] = self.scene[name].data.joint_pos
        self.t += 1

    def save_video(self, env_id: int, num_frames: torch.Tensor, path: str, warmup: int = 30) -> None:
        """Kinematically replay all envs (each frozen on its last valid frame) and film them; no physics step."""
        from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

        last = (num_frames.to(self.env.device).clamp(max=self.t) - 1).clamp(min=0)
        env_ids = torch.arange(self.env.num_envs, device=self.env.device)
        frames = []
        with torch.inference_mode():
            for t in range(int(last[env_id]) + 1):
                idx = last.clamp(max=t)
                for name, buf in self.root_poses.items():
                    self.scene[name].write_root_pose_to_sim(buf[idx, env_ids])
                for name, buf in self.joint_pos.items():
                    self.scene[name].write_joint_position_to_sim(buf[idx, env_ids])
                if t == 0:
                    # headless eval never rendered, so textures/shaders are still loading at this point
                    while SimulationManager.assets_loading():
                        self.env.sim.render()
                    for _ in range(warmup):
                        self.env.render()
                frames.append(self.env.render().copy())
        if frames[0].std() < 1.0 and frames[-1].std() < 1.0:
            print("[WARN] Recorded frames look uniform; the camera may not see the scene or the renderer is not ready.")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ImageSequenceClip(frames, fps=1.0 / self.env.step_dt).write_videofile(path, logger=None)


def focus_camera(env: RslRlVecEnvWrapper, env_id: int) -> None:
    """Point the viewport camera at env ``env_id`` (keeps asset tracking if the viewer follows an asset)."""
    controller = env.unwrapped.viewport_camera_controller
    if controller is None:
        return
    controller.set_view_env_index(env_id)
    if controller.cfg.origin_type == "world":
        controller.update_view_to_env()


def print_report(res: dict) -> None:
    """Aggregate summary only; per-clip rows live in metrics.json."""
    keys = res["metric_keys"]
    width = max(len(k) for k in keys)
    n_ok = sum(c["success"] for c in res["clips"])
    n_total = res["num_clips"]
    print(f"\n===== CLIP-WISE EVALUATION  ({n_total} clips) =====")
    print(f"success_rate : {res['success_rate']:.4f}  ({n_ok}/{n_total})")
    print(f"progress_rate: {res['progress_rate']:.4f}")
    print(f"{'metric':<{width}}  {'all':>10}  {'success':>10}")
    for k in keys:
        print(f"{k:<{width}}  {res['metrics_all'][k]:>10.4f}  {res['metrics_success'][k]:>10.4f}")
    if res["failures"]:
        fail_total = sum(res["failures"].values())
        fail_strs = [f"{k}={v}({100*v//fail_total}%)" for k, v in sorted(res["failures"].items(), key=lambda x: -x[1])]
        print("failures     : " + "  ".join(fail_strs))
    print()


def print_effort_report(results: dict) -> None:
    """Print joint effort analysis summary."""
    if "warning" in results:
        print(f"\n[WARN] Joint Effort Analysis: {results['warning']}")
        return
    
    print("\n===== JOINT EFFORT ANALYSIS (Successful Rollouts Only) =====")
    print(f"Number of successful envs: {results['overall']['num_success_envs']}")
    print(f"Number of timesteps: {results['overall']['num_timesteps']}")
    print(f"\nOverall Statistics:")
    print(f"  Mean effort (all joints): {results['overall']['mean_effort_all_joints']:.2f} Nm")
    print(f"  Max effort (all joints):  {results['overall']['max_effort_all_joints']:.2f} Nm")
    print(f"  Mean limit:               {results['overall']['mean_limit']:.2f} Nm")
    
    print(f"\nPer-Joint Analysis:")
    print(f"{'Joint Name':<35} {'Limit':>8} {'Mean':>8} {'Max':>8} {'Margin':>8} {'Peak%':>8} {'Margin%':>8}")
    print("-" * 95)
    
    for joint in results['joint_analysis']:
        print(f"{joint['joint_name']:<35} "
              f"{joint['effort_limit']:>8.1f} "
              f"{joint['mean_effort']:>8.2f} "
              f"{joint['max_effort']:>8.2f} "
              f"{joint['mean_margin']:>8.2f} "
              f"{joint['peak_ratio']*100:>7.1f}% "
              f"{joint['margin_percentage']:>7.1f}%")
    
    # Highlight joints with high utilization
    high_util = [j for j in results['joint_analysis'] if j['peak_ratio'] > 0.8]
    if high_util:
        print(f"\n⚠️  High utilization joints (>80% peak):")
        for j in high_util:
            print(f"  - {j['joint_name']}: {j['peak_ratio']*100:.1f}% ({j['max_effort']:.2f}/{j['effort_limit']:.1f} Nm)")
    
    print()



@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Evaluate an RSL-RL agent clip by clip."""
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    env_cfg.commands.motion.eval_mode = True
    env_cfg.terminations.clip_end = DoneTerm(func=motion_clip_end, params={"command_name": "motion"}, time_out=True)
    num_clips = read_motion_num_clips(env_cfg.commands.motion.motion_files)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else num_clips
    print(f"[INFO] Clip-wise eval: {num_clips} clip(s) -> {env_cfg.scene.num_envs} env(s)")

    log_root_path = os.path.abspath(os.path.join("logs", "rsl_rl", agent_cfg.experiment_name))
    if args_cli.checkpoint:
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)
    log_dir = os.path.dirname(resume_path)
    env_cfg.log_dir = log_dir

    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    print(f"[INFO]: Loading model checkpoint from: {resume_path}")
    if agent_cfg.class_name != "OnPolicyRunner":
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=env.unwrapped.device)
    policy_nn = runner.alg.policy if hasattr(runner.alg, "policy") else runner.alg.actor_critic

    dt = env.unwrapped.step_dt
    obs, _ = env.reset()
    policy_nn.reset()
    evaluator = ClipEvaluator(env, read_motion_clip_names(env_cfg.commands.motion.motion_files))
    recorder = RolloutRecorder(env, evaluator.max_steps) if args_cli.video else None
    effort_analyzer = JointEffortAnalyzer(env, evaluator.max_steps) if args_cli.effort else None

    pbar = tqdm(range(evaluator.max_steps), desc="eval", unit="step", dynamic_ncols=True)
    joint_targets_fallback = torch.zeros((env.num_envs, env.unwrapped.scene["robot"].num_joints), device=env.device) if args_cli.effort else None
    
    for _ in pbar:
        if not simulation_app.is_running():
            print("[WARN] Simulation app closed before every clip finished; results are partial.")
            break
        start_time = time.time()
        with torch.inference_mode():
            if recorder is not None:
                recorder.record()
            evaluator.collect()
            actions = policy(obs)
            obs, _, dones, extras = env.step(actions)
            
            # Record joint efforts after step (only if --effort flag is enabled)
            if effort_analyzer is not None:
                try:
                    if hasattr(env.unwrapped, 'action_manager') and hasattr(env.unwrapped.action_manager, '_terms'):
                        action_term = env.unwrapped.action_manager._terms.get('policy')
                        if action_term is not None and hasattr(action_term, 'processed_actions'):
                            joint_targets = action_term.processed_actions
                            effort_analyzer.record(joint_targets)
                        else:
                            effort_analyzer.record(joint_targets_fallback)
                    else:
                        effort_analyzer.record(joint_targets_fallback)
                except Exception as e:
                    # Fallback: just record without targets (will use zeros)
                    if effort_analyzer.t == 0:
                        print(f"[WARN] Could not access joint targets for effort analysis: {e}")
                    effort_analyzer.record(joint_targets_fallback)
            
            policy_nn.reset(dones)
            evaluator.update(dones, extras["time_outs"])
        n_done, n_ok = int(evaluator.finished.sum()), int(evaluator.success.sum())
        pbar.set_postfix_str(f"done {n_done}/{env.num_envs} | ok {n_ok} | succ {n_ok / max(n_done, 1)*100:.2f}%")
        if evaluator.done:
            break
        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)
    pbar.close()

    if not evaluator.done:
        print(f"[WARN] {int((~evaluator.finished).sum())} env(s) never terminated; scored on what they ran.")

    res = evaluator.results()
    print_report(res)
    
    # Mark successful environments in effort analyzer (only if --effort flag is enabled)
    if effort_analyzer is not None:
        effort_analyzer.mark_success(evaluator.success)

    output_dir = args_cli.output_dir or os.path.join(log_dir, "eval")
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "metrics.json")
    res["checkpoint"] = resume_path
    res["motion_files"] = list(env_cfg.commands.motion.motion_files)
    with open(out_file, "w") as f:
        json.dump(res, f, indent=2)
    print(f"[INFO] Wrote {out_file}")
    
    # Save joint effort analysis (only if --effort flag is enabled)
    if effort_analyzer is not None:
        effort_file = os.path.join(output_dir, "joint_effort_analysis.json")
        effort_analyzer.save_results(effort_file)
        
        # Print effort analysis report
        effort_results = effort_analyzer.analyze()
        print_effort_report(effort_results)

    if recorder is not None and simulation_app.is_running():
        ok_ids = evaluator.success.nonzero(as_tuple=False).flatten().tolist()
        pool = ok_ids if ok_ids else list(range(env.num_envs))
        env_id = int(np.random.default_rng(agent_cfg.seed).choice(pool))
        clip = res["clips"][env_id]
        tag = "success" if clip["success"] else f"fail_{clip['cause']}"
        if not ok_ids:
            print("[WARN] No successful rollout; recording a random one instead.")
        name = re.sub(r"[^\w.-]+", "_", clip["name"])
        video_path = os.path.join(output_dir, "videos", f"env{env_id:04d}_{name}_{tag}.mp4")
        print(f"[INFO] Recording env {env_id} (clip '{clip['name']}', {tag}, {clip['steps']} steps) ...")
        focus_camera(env, env_id)
        recorder.save_video(env_id, evaluator.steps, video_path)
        print(f"[INFO] Wrote {video_path}")

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
