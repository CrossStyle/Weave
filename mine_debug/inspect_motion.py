import numpy as np
from huggingface_hub import hf_hub_download

# path = r"D:\code\robot\Weave\data\test\woodchair_46clip_var5.npz"
# path = r"D:\code\robot\Weave\data\train\woodchair_987clip.npz"
# path = r"D:\code\robot\Weave\data\test\woodchair_46clip_var5_first_motion.npz"

path = r"D:\code\robot\Weave\source\g1_hoi_learning\g1_hoi_learning\objects\hframe\h_frame_weave.npz"
data = np.load(path, allow_pickle=True)

# lengths = data["motion_lengths"]
# starts = np.concatenate([[0], np.cumsum(lengths)])
#
# i = 0  # first clip
# sl = slice(starts[i], starts[i + 1])
# print(data["motion_names"][i], data["object_names"][i], lengths[i], "frames")
# print(data["joint_pos"][sl].shape)      # (L, 53)
# print(data["body_pos_w"][sl].shape)     # (L, 54, 3)
# print(data["object_pos_w"][sl].shape)   # (L, 3)
