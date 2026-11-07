import numpy as np
import os

root = r"D:\code\robot\Weave"

# src = "./data/train/woodchair_987clip.npz"
# src = "./data/test/woodchair_46clip_var5.npz"
src = "./data/datasets/Weave/rollout/test/woodchair_rollout.npz"
dst = "./data/datasets/Weave/rollout/train/sub17_woodchair_005.npz"

data = np.load(root + src, allow_pickle=True)

motion_lengths = data["motion_lengths"]
clip_starts = np.concatenate([[0], np.cumsum(motion_lengths)])

# include_list = ["sub17_woodchair_005", "sub17_woodchair_020", "sub17_woodchair_015", "sub17_woodchair_010"]
include_list = ["sub17_woodchair_005"]
motion_names = data["motion_names"]

frame_keys = {
    "joint_pos",
    "joint_vel",
    "body_pos_w",
    "body_quat_w",
    "body_lin_vel_w",
    "body_ang_vel_w",
    "object_pos_w",
    "object_quat_w",
    "object_lin_vel_w",
    "object_ang_vel_w",
    "contact_label",
}
metadata_keys = {"motion_lengths", "object_names", "motion_names"}
results = []
for motion_id, motion_name in enumerate(motion_names):
    for include_id in include_list:
        if include_id in motion_name:
            result = {
                key: (
                    data[key][clip_starts[motion_id]:clip_starts[motion_id+1]].copy() if key in frame_keys
                    else data[key][motion_id].copy() if key in metadata_keys
                    else data[key].copy()
                )
                for key in data.files
            }
            results.append(result)

# ---- 新加的：合并成和原来一样的结构 ----
if len(results) == 0:
    print("没有匹配到")
else:
    merged = {}
    for key in results[0].keys():
        if key in frame_keys:
            # 帧级别：把所有clip在时间轴上拼起来 [T1+T2+... , ...]
            merged[key] = np.concatenate([r[key] for r in results], axis=0)
        elif key in metadata_keys:
            # clip级别：每个clip一个值，堆成数组
            # motion_lengths 是 int，motion_names/object_names 是字符串
            try:
                merged[key] = np.array([r[key] for r in results])
            except:
                merged[key] = np.array([r[key] for r in results], dtype=object)
        else:
            # 全局配置之类的，只存一份就行
            merged[key] = results[0][key]
    save_path = os.path.join(root, dst.lstrip("./"))
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    np.savez_compressed(save_path, **merged)
    print(f"已保存到 {save_path}")
    print(f"新的 motion_lengths: {merged['motion_lengths']}")
    print(f"总帧数: {merged['joint_pos'].shape[0]}")