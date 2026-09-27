"""Extra rig layers for the Codex v2 pet (does not touch prepare_assets.py outputs).

Front (crop space of front_crop.png, 520x590):
  front_masks.png  R=head(+ears) rigid, G=left ear, B=right ear, A=muzzle+nose
  front_legs.png   R=viewer-left front leg, G=viewer-right front leg (paw+lower leg)
Side (crop of the side panel, see SIDE_CROP):
  side_crop.png, side_base.png (RGBA), side_eye.png (RGBA eye only), side_plate.png (eye inpainted)
  side_masks.png   R=near front leg, G=far front leg, B=near hind leg, A=far hind leg
  side_masks2.png  R=head(+ear), G=ear, B=tail, A=body
  side_layout.json

Run: .venv/bin/python tools/prepare_rig.py
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare_assets import bleed, local_mean, smoothstep  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets/source/kiwi_turnaround.webp")
OUT = os.path.join(ROOT, "assets/derived")
DBG = os.environ.get("KIWI_DEBUG_DIR")


def write_rgba(name, chans):
    arr = np.dstack([(np.clip(c, 0, 1) * 255 + 0.5).astype(np.uint8) for c in chans])
    cv2.imwrite(os.path.join(OUT, name), cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))
    return arr


def feather(mask, sigma):
    return np.clip(cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma), 0, 1)


def poly_mask(shape, polys):
    m = np.zeros(shape, np.uint8)
    for p in polys:
        cv2.fillPoly(m, [np.array(p, np.int32)], 1)
    return m


# ---------------------------------------------------------------- front
FRONT_EARS = [
    [(160, 80), (120, 90), (70, 160), (38, 240), (56, 305), (100, 345), (160, 340), (172, 260), (168, 150)],
    [(360, 80), (400, 90), (450, 160), (482, 240), (464, 305), (420, 345), (360, 340), (348, 260), (352, 150)],
]
FRONT_HEAD = ((259, 168), (116, 118))
FRONT_MUZZLE = ((258, 240), (58, 40))
FRONT_LEGS = [
    [(128, 425), (228, 425), (234, 560), (122, 560)],
    [(290, 425), (392, 425), (398, 560), (286, 560)],
]


def front():
    H, W = 590, 520
    head = np.zeros((H, W), np.uint8)
    cv2.ellipse(head, FRONT_HEAD[0], FRONT_HEAD[1], 0, 0, 360, 1, -1)
    fg = cv2.imread(os.path.join(OUT, "alpha_matte.png"), cv2.IMREAD_GRAYSCALE) > 0
    def grow(m, k):
        # extend a part's mask into the empty background around it (never onto other body parts),
        # so pixels it moves into are sampled from the part, not left behind as fragments
        ring = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(bool) & ~fg
        return (m.astype(bool) | ring).astype(np.uint8)
    ears = [grow(poly_mask((H, W), [p]), 41) for p in FRONT_EARS]
    head_all = np.clip(head + ears[0] + ears[1], 0, 1)
    head_w = np.clip(feather(head_all, 8) * 1.3, 0, 1)
    ear_w = [np.clip(feather(e, 6) * 1.2, 0, 1) for e in ears]
    # ear weight grows from 0 at the root (top) to 1 at the tip, so ears hinge
    yy = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
    hinge = smoothstep(95, 200, yy)
    ear_w = [e * hinge for e in ear_w]
    muz = np.zeros((H, W), np.uint8)
    cv2.ellipse(muz, FRONT_MUZZLE[0], FRONT_MUZZLE[1], 0, 0, 360, 1, -1)
    muz_w = feather(muz, 12) * (1 - np.maximum(ear_w[0], ear_w[1]))
    legs = [grow(poly_mask((H, W), [p]), 51) for p in FRONT_LEGS]
    leg_w = [feather(l, 5) for l in legs]
    write_rgba("front_masks.png", [head_w, ear_w[0], ear_w[1], muz_w])
    write_rgba("front_legs.png", [leg_w[0], leg_w[1], np.zeros((H, W)), np.ones((H, W))])
    if DBG:
        base = cv2.imread(os.path.join(OUT, "front_crop.png")).astype(np.float32)
        ov = base.copy()
        for m, c in ((head_w, (0, 0, 255)), (ear_w[0], (0, 255, 0)), (ear_w[1], (255, 0, 0)),
                     (muz_w, (255, 0, 255)), (leg_w[0], (0, 255, 255)), (leg_w[1], (255, 255, 0))):
            ov = ov * (1 - 0.35 * m[..., None]) + np.array(c) * 0.35 * m[..., None]
        os.makedirs(DBG, exist_ok=True)
        cv2.imwrite(os.path.join(DBG, "front_masks_overlay.png"), ov.astype(np.uint8))


if __name__ == "__main__":
    front()
    if "--side" in sys.argv:
        import prepare_side  # noqa: F401  (added in the side-rig step)
