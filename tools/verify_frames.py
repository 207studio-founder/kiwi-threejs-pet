"""Numeric checks on an exported PNG sequence (no-shadow export recommended).

Usage: .venv/bin/python tools/verify_frames.py export/check_noshadow
Prints: canvas consistency, rest-frame vs base.png diff, paw-region stability,
loop seam, eye-darkness at full blink, edge halo over black, bbox margins.
"""
import glob
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "kiwi_idle_*.png")))
meta = json.load(open(os.path.join(d, "sequence.json")))
lay = json.load(open(os.path.join(ROOT, "assets/derived/layout.json")))
rd = lambda p: cv2.cvtColor(cv2.imread(p, cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA).astype(np.int16)
frames = [rd(f) for f in files]
res = {}
res["n_frames"] = len(frames)
res["sizes"] = sorted({f.shape for f in frames})
base = rd(os.path.join(ROOT, "assets/derived/base.png"))
plate = rd(os.path.join(ROOT, "assets/derived/plate.png"))
f0 = frames[0]
# rest pose (t=0: breath 0, eyes open) vs base.png  (premultiplied compare)
pm = lambda a: a[..., :3].astype(np.float32) * a[..., 3:4] / 255.0
res["t0_vs_base_max_premul_diff"] = float(np.abs(pm(f0) - pm(base)).max())
res["t0_vs_base_alpha_max_diff"] = int(np.abs(f0[..., 3] - base[..., 3]).max())
# paws: rows at/below the paw top line must never change
py = lay["paw_top_y"]
paw = np.stack([f[py:, :, :] for f in frames])
res["paw_rows_max_change_over_loop"] = int(np.abs(paw - paw[0]).max())
# loop seam: last frame -> first frame step compared with typical step
steps = [float(np.abs(frames[i + 1] - frames[i]).mean()) for i in range(len(frames) - 1)]
res["seam_step_mean_abs"] = float(np.abs(frames[0] - frames[-1]).mean())
res["typical_step_mean_abs_median"] = float(np.median(steps))
res["max_step_mean_abs"] = float(max(steps))
# darkest remaining eye pixels at the most-closed frame (closed line should be thin)
lum = lambda a: a[..., :3].mean(-1)
def eye_dark(f):
    L = lum(f)
    return sum(int((L[int(e["cy"] - 35):int(e["cy"] + 35), int(e["cx"] - 22):int(e["cx"] + 22)] < 110).sum())
               for e in lay["eyes"])
dark_counts = [eye_dark(f) for f in frames]
res["dark_px_open"] = dark_counts[0]
res["dark_px_min_over_loop"] = min(dark_counts)
res["dark_px_min_frame"] = int(np.argmin(dark_counts))
# edge halo: semi-transparent pixels composited on black, compared with interior neighbours
a = f0[..., 3]
edge = (a > 20) & (a < 235)
res["edge_px"] = int(edge.sum())
res["edge_mean_rgb_unpremul"] = [round(float(v), 1) for v in f0[..., :3][edge].mean(0)]
res["interior_mean_rgb"] = [round(float(v), 1) for v in f0[..., :3][a == 255].mean(0)]
# bbox over whole loop vs canvas
union = np.zeros(a.shape, bool)
for f in frames:
    union |= f[..., 3] > 0
ys, xs = np.nonzero(union)
res["union_bbox_xyxy"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
res["canvas_wh"] = [a.shape[1], a.shape[0]]
print(json.dumps(res, indent=1))
