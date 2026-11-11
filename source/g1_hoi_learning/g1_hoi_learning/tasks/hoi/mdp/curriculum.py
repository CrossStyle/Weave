"""物体质量课程学习管理器

基本思路：
- 从较轻的物体质量开始训练
- 每隔一定 iteration 评估成功率
- 成功率达到阈值后增加物体质量
- 包含回退机制和最少训练步数保护
"""

import json
import os
from dataclasses import dataclass

import torch
from torch.utils.tensorboard import SummaryWriter

from isaaclab.envs import ManagerBasedRLEnv
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass

from .commands import MotionCommand
from .terminations import motion_clip_end


@configclass
class MassCurriculumCfg:
    """物体质量课程学习配置"""

    # 启用课程学习
    enabled: bool = True

    # 质量范围 (kg)
    initial_mass: float = 2.0  # 初始质量
    final_mass: float = 10.0  # 目标质量
    mass_increment: float = 0.5  # 每次增量

    # 评估参数
    eval_interval: int = 50  # 每多少 iteration 评估一次
    eval_episodes: int = 50  # 每次评估多少 episode（已废弃，使用 eval_sample_ratio）
    success_threshold: float = 0.8  # 晋升阈值
    
    # 评估优化参数
    eval_sample_ratio: float = 0.1  # 评估时抽样比例（0.5 = 50% 环境，可加速评估）
    eval_early_stop_ratio: float = 0.9  # Early stopping 阈值（0.9 = 90% 环境完成就停止）
    eval_min_envs_per_object: int = 20  # 每个物体至少评估的环境数

    # 保护机制
    min_iterations_per_stage: int = 50  # 每个阶段最少训练步数
    max_failures: int = 3  # 连续多少次不达标后回退
    allow_regression: bool = True  # 是否允许回退到上一阶段


class MassCurriculumManager:
    """物体质量课程学习管理器

    在训练过程中逐步增加物体质量，提升策略鲁棒性。
    """

    def __init__(
        self,
        cfg: MassCurriculumCfg,
        env,
        log_dir: str | None = None,
        tb_writer: SummaryWriter | None = None,
    ):
        """
        Args:
            env: RslRlVecEnvWrapper 包装后的环境（与 eval.py 一致，step 返回 4 个值）
        """
        self.cfg = cfg
        # vec_env 用于 reset/step（4 值 API，extras 中含 time_outs）
        # env 为底层 ManagerBasedRLEnv，用于访问 scene 和各 manager
        self.vec_env = env
        self.env: ManagerBasedRLEnv = env.unwrapped
        self.device = self.env.device
        self.log_dir = log_dir
        self.tb_writer = tb_writer

        # 当前状态
        self.current_mass = cfg.initial_mass
        self.stage = 0
        self.iteration = 0
        self.last_eval_iteration = 0
        self.consecutive_failures = 0
        self.stage_start_iteration = 0

        # 历史记录
        self.history = []

        # 获取 motion command 和 termination manager
        self.command: MotionCommand = self.env.command_manager.get_term("motion")
        self.term_mgr = self.env.termination_manager

        # 初始化物体质量
        self._set_object_mass(self.current_mass)

        print(f"\n{'='*60}")
        print(f"[MassCurriculum] 课程学习已启动")
        print(f"  初始质量: {self.current_mass:.1f} kg")
        print(f"  目标质量: {self.cfg.final_mass:.1f} kg")
        print(f"  增量步长: {self.cfg.mass_increment:.1f} kg")
        print(f"  评估间隔: {self.cfg.eval_interval} iterations")
        print(f"  成功阈值: {self.cfg.success_threshold*100:.0f}%")
        print(f"{'='*60}\n")

    def _set_object_mass(self, mass: float) -> None:
        """设置所有环境中物体的质量"""
        # 获取物体的 rigid body properties
        object_asset = self.env.scene["object"]
        if hasattr(object_asset, "root_physx_view"):
            # 设置质量（为所有环境设置相同质量）
            # 注意：Isaac Sim 的 PhysX tensors 需要 CPU 张量
            masses = torch.full((self.env.num_envs,), mass, dtype=torch.float32, device="cpu")
            # 生成所有环境的索引
            indices = torch.arange(self.env.num_envs, dtype=torch.int32, device="cpu")
            object_asset.root_physx_view.set_masses(masses, indices=indices)

    def should_evaluate(self) -> bool:
        """判断是否需要评估"""
        if not self.cfg.enabled:
            return False

        # 检查是否到了评估间隔
        if self.iteration - self.last_eval_iteration < self.cfg.eval_interval:
            return False

        # 检查当前阶段是否达到最少训练步数
        stage_iterations = self.iteration - self.stage_start_iteration
        if stage_iterations < self.cfg.min_iterations_per_stage:
            return False

        return True

    def evaluate(self, actor_critic) -> dict:
        """评估当前策略的成功率
        
        使用训练时的环境-物体-clip 分配，但禁用 RSI 从头开始评估。
        支持抽样评估和 early stopping 以加速评估过程。
        分物体统计评估结果，每个环境只评估第一个episode。

        Args:
            actor_critic: RSL-RL 的 ActorCritic 模块

        Returns:
            dict: 包含 success_rate, progress_rate, 和详细指标（整体 + 分物体）
        """
        print(f"\n[MassCurriculum] 开始评估 (iteration {self.iteration}, 质量 {self.current_mass:.1f}kg)...")
        
        n = self.env.num_envs
        num_objects = self.command.motion.num_objects
        
        # 抽样评估环境（分层抽样，确保每个物体都有代表）
        if self.cfg.eval_sample_ratio < 1.0:
            sample_size = max(
                int(n * self.cfg.eval_sample_ratio),
                num_objects * self.cfg.eval_min_envs_per_object
            )
            
            # 分层抽样：每个物体抽相同数量
            sampled_envs = []
            per_object_samples = sample_size // num_objects
            
            for obj_idx in range(num_objects):
                obj_mask = (self.command.env_object == obj_idx)
                obj_env_ids = obj_mask.nonzero().flatten()
                if len(obj_env_ids) > per_object_samples:
                    # 随机抽样
                    perm = torch.randperm(len(obj_env_ids), device=self.device)[:per_object_samples]
                    sampled_envs.append(obj_env_ids[perm])
                else:
                    sampled_envs.append(obj_env_ids)
            
            eval_env_ids = torch.cat(sampled_envs).sort()[0]  # 排序方便调试
            eval_mask = torch.zeros(n, dtype=torch.bool, device=self.device)
            eval_mask[eval_env_ids] = True
            
            print(f"[MassCurriculum] 抽样评估: {len(eval_env_ids)}/{n} 环境 "
                  f"({self.cfg.eval_sample_ratio*100:.0f}%, 每物体 ~{per_object_samples})")
        else:
            eval_mask = torch.ones(n, dtype=torch.bool, device=self.device)
            eval_env_ids = torch.arange(n, device=self.device)
        
        # 禁用 RSI，从 clip 开头评估（与 eval.py 保持一致）
        original_rsi = self.command.cfg.rsi
        self.command.cfg.rsi = False
        
        try:
            # 统计变量（只统计被抽样的环境）
            env_finished = torch.zeros(n, dtype=torch.bool, device=self.device)
            env_success = torch.zeros(n, dtype=torch.bool, device=self.device)
            env_steps = torch.zeros(n, dtype=torch.long, device=self.device)
            
            # Reset 环境（现在从 time_steps=0 开始，不使用 RSI）
            obs, _ = self.vec_env.reset()
            
            # Reset policy 状态
            actor_critic.reset()

            # 记录每个环境的 clip 长度和物体 ID
            clip_ids = self.command.env_clip.clone()
            env_clip_len = self.command.motion.clip_lengths[clip_ids]
            env_object_ids = self.command.env_object.clone()
            
            # 最大步数
            max_steps = int(env_clip_len[eval_env_ids].max().item()) + 5

            step_count = 0
            while step_count < max_steps:
                # 检查 early stopping（只检查被抽样的环境）
                eval_finished = env_finished[eval_mask]
                if eval_finished.all():
                    break
                
                # Early stopping: 如果大部分环境已完成
                if self.cfg.eval_early_stop_ratio < 1.0:
                    finished_ratio = eval_finished.float().mean()
                    if finished_ratio >= self.cfg.eval_early_stop_ratio:
                        print(f"[MassCurriculum] Early stop: {eval_finished.sum()}/{len(eval_env_ids)} 环境完成 "
                              f"({finished_ratio*100:.1f}% >= {self.cfg.eval_early_stop_ratio*100:.0f}%)")
                        break
                
                with torch.no_grad():
                    actions = actor_critic.act_inference(obs)
                
                # Step environment
                obs, rewards, dones, extras = self.vec_env.step(actions)
                
                # Reset policy 状态
                actor_critic.reset(dones)
                
                # 从 extras 获取 time_outs
                time_outs = extras.get("time_outs", torch.zeros_like(dones, dtype=torch.bool))
                
                # 反推 terminated（失败终止）
                terminated = dones.bool() & ~time_outs

                # 更新步数（只统计被抽样且未完成的环境）
                active = eval_mask & ~env_finished
                env_steps += active.long()

                # 更新统计（只处理被抽样的环境）
                newly_done = dones.bool() & eval_mask & ~env_finished

                if newly_done.any():
                    # 获取终止条件标志
                    clip_end_flags = self.term_mgr.get_term("clip_end") if "clip_end" in self.term_mgr.active_terms else None

                    # 判断成功
                    if clip_end_flags is not None:
                        env_success |= newly_done & clip_end_flags & ~terminated
                    
                    # 标记已完成的环境
                    env_finished |= newly_done

                step_count += 1
            
            # 只统计被抽样的环境
            eval_success = env_success[eval_mask]
            eval_finished = env_finished[eval_mask]
            eval_steps = env_steps[eval_mask]
            eval_clip_len = env_clip_len[eval_mask]
            eval_object_ids = env_object_ids[eval_mask]
            
            # 整体统计
            success_rate = float(eval_success.float().mean())
            episodes_evaluated = int(eval_finished.sum())
            successes = int(eval_success.sum())
            
            progress = (eval_steps.float() / eval_clip_len.clamp(min=1).float()).clamp(max=1.0)
            progress_rate = float(progress.mean())
            
            avg_steps = float(eval_steps.float().mean())

            # 分物体统计
            per_object_stats = {}
            object_names = self.command.motion.object_names
            
            for obj_idx in range(num_objects):
                obj_mask = (eval_object_ids == obj_idx)
                if obj_mask.any():
                    obj_success = eval_success[obj_mask]
                    obj_finished = eval_finished[obj_mask]
                    obj_progress = progress[obj_mask]
                    
                    obj_name = object_names[obj_idx]
                    obj_success_rate = float(obj_success.float().mean())
                    obj_episodes = int(obj_finished.sum())
                    obj_successes = int(obj_success.sum())
                    obj_progress_rate = float(obj_progress.mean())
                    
                    per_object_stats[obj_name] = {
                        "success_rate": obj_success_rate,
                        "progress_rate": obj_progress_rate,
                        "episodes": obj_episodes,
                        "successes": obj_successes,
                        "num_envs": int(obj_mask.sum()),
                    }

            result = {
                "success_rate": success_rate,
                "progress_rate": progress_rate,
                "episodes": episodes_evaluated,
                "successes": successes,
                "avg_steps": avg_steps,
                "current_mass": self.current_mass,
                "stage": self.stage,
                "per_object": per_object_stats,
                "eval_envs": len(eval_env_ids),
                "total_envs": n,
            }

            # 打印整体结果
            print(f"[MassCurriculum] 评估完成 (整体): 成功率 {success_rate*100:.1f}% ({successes}/{episodes_evaluated}), "
                  f"进度率 {progress_rate*100:.1f}%, 平均步数 {avg_steps:.1f}")
            
            # 打印分物体结果
            if per_object_stats:
                print(f"[MassCurriculum] 分物体结果:")
                for obj_name, stats in per_object_stats.items():
                    print(f"  {obj_name}: 成功率 {stats['success_rate']*100:.1f}% "
                          f"({stats['successes']}/{stats['episodes']}), "
                          f"进度率 {stats['progress_rate']*100:.1f}%")

            return result
        
        finally:
            # 恢复原始 RSI 设置
            self.command.cfg.rsi = original_rsi

    def update(self, eval_result: dict) -> None:
        """根据评估结果更新课程

        Args:
            eval_result: evaluate() 返回的评估结果
        """
        success_rate = eval_result["success_rate"]
        self.last_eval_iteration = self.iteration

        # 记录到历史
        history_entry = {
            "iteration": self.iteration,
            "stage": self.stage,
            "mass": self.current_mass,
            "success_rate": success_rate,
            "episodes": eval_result["episodes"],
            "successes": eval_result["successes"],
            "per_object": eval_result.get("per_object", {}),
        }
        self.history.append(history_entry)

        # 记录到 tensorboard
        if self.tb_writer is not None:
            self.tb_writer.add_scalar("curriculum/mass", self.current_mass, self.iteration)
            self.tb_writer.add_scalar("curriculum/stage", self.stage, self.iteration)
            self.tb_writer.add_scalar("curriculum/success_rate", success_rate, self.iteration)
            self.tb_writer.add_scalar("curriculum/progress_rate", eval_result["progress_rate"], self.iteration)
            
            # 记录分物体的统计
            per_object = eval_result.get("per_object", {})
            for obj_name, stats in per_object.items():
                self.tb_writer.add_scalar(f"curriculum/success_rate_{obj_name}", stats["success_rate"], self.iteration)
                self.tb_writer.add_scalar(f"curriculum/progress_rate_{obj_name}", stats["progress_rate"], self.iteration)

        # 判断是否晋升
        if success_rate >= self.cfg.success_threshold:
            # 成功！增加质量
            self.consecutive_failures = 0

            if self.current_mass < self.cfg.final_mass:
                old_mass = self.current_mass
                self.current_mass = min(self.current_mass + self.cfg.mass_increment, self.cfg.final_mass)
                self.stage += 1
                self.stage_start_iteration = self.iteration

                self._set_object_mass(self.current_mass)

                print(f"\n{'='*60}")
                print(f"[MassCurriculum] 🎉 晋升到下一阶段！")
                print(f"  阶段: {self.stage-1} -> {self.stage}")
                print(f"  质量: {old_mass:.1f} kg -> {self.current_mass:.1f} kg")
                print(f"  成功率: {success_rate*100:.1f}%")
                print(f"{'='*60}\n")

                # 保存 checkpoint
                if self.log_dir is not None:
                    self._save_checkpoint()
            else:
                print(f"[MassCurriculum] 已达到目标质量 {self.cfg.final_mass:.1f} kg，课程学习完成！")

        else:
            # 失败，增加失败计数
            self.consecutive_failures += 1
            print(f"[MassCurriculum] 未达标 ({success_rate*100:.1f}% < {self.cfg.success_threshold*100:.0f}%), "
                  f"连续失败 {self.consecutive_failures}/{self.cfg.max_failures}")

            # 是否需要回退
            if self.cfg.allow_regression and self.consecutive_failures >= self.cfg.max_failures:
                if self.current_mass > self.cfg.initial_mass:
                    old_mass = self.current_mass
                    self.current_mass = max(self.current_mass - self.cfg.mass_increment, self.cfg.initial_mass)
                    self.stage = max(0, self.stage - 1)
                    self.consecutive_failures = 0
                    self.stage_start_iteration = self.iteration

                    self._set_object_mass(self.current_mass)

                    print(f"\n{'='*60}")
                    print(f"[MassCurriculum] ⚠️  回退到上一阶段")
                    print(f"  阶段: {self.stage+1} -> {self.stage}")
                    print(f"  质量: {old_mass:.1f} kg -> {self.current_mass:.1f} kg")
                    print(f"{'='*60}\n")
                else:
                    print(f"[MassCurriculum] 已经是初始质量，无法继续回退")
                    self.consecutive_failures = 0  # 重置计数

    def _save_checkpoint(self) -> None:
        """保存课程学习的 checkpoint"""
        if self.log_dir is None:
            return

        curriculum_dir = os.path.join(self.log_dir, "curriculum")
        os.makedirs(curriculum_dir, exist_ok=True)

        checkpoint_file = os.path.join(curriculum_dir, f"stage_{self.stage}_mass_{self.current_mass:.1f}kg.json")

        checkpoint = {
            "iteration": self.iteration,
            "stage": self.stage,
            "current_mass": self.current_mass,
            "consecutive_failures": self.consecutive_failures,
            "history": self.history,
        }

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

        print(f"[MassCurriculum] 保存 checkpoint: {checkpoint_file}")

    def step(self) -> None:
        """每次训练 iteration 调用一次"""
        self.iteration += 1

    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "enabled": self.cfg.enabled,
            "iteration": self.iteration,
            "stage": self.stage,
            "current_mass": self.current_mass,
            "target_mass": self.cfg.final_mass,
            "consecutive_failures": self.consecutive_failures,
            "stage_iterations": self.iteration - self.stage_start_iteration,
        }

    def save_summary(self) -> None:
        """保存课程学习的总结"""
        if self.log_dir is None:
            return

        curriculum_dir = os.path.join(self.log_dir, "curriculum")
        os.makedirs(curriculum_dir, exist_ok=True)

        summary_file = os.path.join(curriculum_dir, "summary.json")

        summary = {
            "config": {
                "initial_mass": self.cfg.initial_mass,
                "final_mass": self.cfg.final_mass,
                "mass_increment": self.cfg.mass_increment,
                "eval_interval": self.cfg.eval_interval,
                "success_threshold": self.cfg.success_threshold,
            },
            "final_status": self.get_status(),
            "history": self.history,
        }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\n[MassCurriculum] 保存训练总结: {summary_file}")
