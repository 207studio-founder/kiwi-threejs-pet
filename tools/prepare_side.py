"""Side-view layers for running-left/right, cut from the same source sheet.

Outputs (assets/derived/): side_crop.png, side_base.png, side_plate.png, side_eye.png,
side_masks.png (R near-front leg, G far-front leg, B near-hind leg, A far-hind leg),
side_masks2.png (R head+ear, G ear, B tail, A body), side_layout.json

Run: .venv/bin/python tools/prepare_side.py   (set KIWI_DEBUG_DIR for overlays)
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare_assets import bleed, local_mean  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets/source/kiwi_turnaround.webp")
OUT = os.path.join(ROOT, "assets/derived")
DBG = os.environ.get("KIWI_DEBUG_DIR")
CROP = (500, 150, 1310, 740)  # side panel; character bbox x 529..1280, y 197..696 (sheet px)

# hand annotations in side-crop px (filled after inspection)
PAW_FG = [(215, 528, 38, 13), (152, 518, 20, 12), (620, 525, 34, 14), (535, 520, 36, 12)]
FLOOR_BG = [
    [(270, 530), (312, 530), (312, 552), (270, 552)],
    [(542, 533), (572, 533), (572, 546), (542, 546)],
    [(0, 550), (809, 550), (809, 589), (0, 589)],
]
EYE_SEED = (122, 165)
LEGS = {
    "nf": [(180, 452), (292, 452), (292, 500), (272, 552), (176, 552), (176, 500)],
    "ff": [(118, 468), (178, 468), (178, 552), (118, 552)],
    "nh": [(578, 438), (686, 438), (676, 520), (668, 552), (580, 552)],
    "fh": [(486, 460), (577, 460), (577, 548), (486, 548)],
}
HEAD_POLY = [(28, 190), (58, 110), (120, 58), (200, 44), (290, 58), (330, 120), (322, 200), (252, 240),
             (170, 252), (80, 246), (32, 216)]
EAR_POLY = [(200, 84), (290, 78), (332, 130), (362, 250), (347, 302), (290, 348), (228, 348), (168, 300),
            (152, 230), (168, 140)]
TAIL_POLY = [(585, 300), (640, 258), (700, 228), (762, 196), (792, 258), (788, 342), (742, 412), (680, 424),
             (618, 382), (588, 342)]
# the four legs are swung as front pair / hind pair (near and far legs overlap in the
# side drawing and cannot be separated without inventing hidden pixels)
PAIR = {"front": [(96, 448), (308, 448), (318, 562), (92, 562)],
        "hind": [(468, 440), (702, 440), (708, 562), (462, 562)]}
PIVOTS = {"nf": [235, 452], "ff": [158, 468], "nh": [622, 440], "fh": [533, 462],
          "neck": [232, 272], "ear_root": [248, 100], "tail_root": [612, 332]}


def save_rgba(name, arr):
    cv2.imwrite(os.path.join(OUT, name), cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))


def matte(img, f, bg, dist):
    H, W = dist.shape
    gc = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    gc[dist > 18] = cv2.GC_PR_FGD
    core = cv2.erode((dist > 45).astype(np.uint8), np.ones((5, 5), np.uint8))
    gc[core > 0] = cv2.GC_FGD
    flat = (dist < 9).astype(np.uint8)
    n, lab = cv2.connectedComponents(flat, connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    gc[np.isin(lab, list(edge))] = cv2.GC_BGD
    for (cx, cy, rx, ry) in PAW_FG:
        cv2.ellipse(gc, (cx, cy), (rx, ry), 0, 0, 360, cv2.GC_FGD, -1)
    for poly in FLOOR_BG:
        cv2.fillPoly(gc, [np.array(poly, np.int32)], cv2.GC_BGD)
    b = np.zeros((1, 65)); fg = np.zeros((1, 65))
    cv2.grabCut(img, gc, None, b, fg, 6, cv2.GC_INIT_WITH_MASK)
    hard = np.isin(gc, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hard, connectivity=8)
    hard = (lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lab = cv2.connectedComponents(1 - hard, connectivity=4)
    out = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    hard = np.where(np.isin(lab, list(out)), 0, 1).astype(np.uint8)
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    hard[(dist < 22) & (cv2.erode(hard, np.ones((7, 7), np.uint8)) == 0)] = 0
    return hard


def main():
    sheet = cv2.cvtColor(cv2.imread(SRC), cv2.COLOR_BGR2RGB)
    x0, y0, x1, y1 = CROP
    img = sheet[y0:y1, x0:x1].copy()
    H, W = img.shape[:2]
    cv2.imwrite(os.path.join(OUT, "side_crop.png"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    f = img.astype(np.float32)
    border = np.concatenate([f[:6].reshape(-1, 3), f[-6:].reshape(-1, 3), f[:, :6].reshape(-1, 3), f[:, -6:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((f - bg) ** 2).sum(-1))
    hard = matte(img, f, bg, dist)

    # soft edge + despill: same recipe as the front (prepare_assets.py)
    band = cv2.dilate(hard, np.ones((5, 5), np.uint8)) - cv2.erode(hard, np.ones((5, 5), np.uint8))
    fg_local = local_mean(f, cv2.erode(hard, np.ones((7, 7), np.uint8)), 9)
    num = ((f - bg) * (fg_local - bg)).sum(-1)
    den = ((fg_local - bg) ** 2).sum(-1) + 1e-3
    a_est = np.clip(num / den, 0, 1)
    alpha = hard.astype(np.float32)
    alpha[band > 0] = a_est[band > 0]
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.6) * cv2.dilate(hard, np.ones((3, 3), np.uint8))
    alpha[cv2.erode(hard, np.ones((5, 5), np.uint8)) > 0] = 1.0
    alpha = np.clip(alpha, 0, 1)
    a3 = alpha[..., None]
    col = np.where(a3 > 0.02, (f - (1 - a3) * bg) / np.maximum(a3, 0.02), fg_local)
    col = np.where(a3 < 0.999, np.clip(0.2 * col + 0.8 * fg_local, 0, 255), f)
    inner = hard - cv2.erode(hard, np.ones((9, 9), np.uint8))
    fg_deep = local_mean(f, cv2.erode(hard, np.ones((13, 13), np.uint8)), 6)
    proj = ((f - fg_deep) * (bg - fg_deep)).sum(-1) / (((bg - fg_deep) ** 2).sum(-1) + 1e-3)
    mix = np.clip(proj, 0, 0.45)[..., None]
    unmixed = np.clip((col - mix * bg) / (1 - mix), 0, 255)
    col = np.where((inner > 0)[..., None], col + 0.6 * (unmixed - col), col)
    col = bleed(np.clip(col, 0, 255), alpha > 0.5, 12)
    a8 = (alpha * 255 + 0.5).astype(np.uint8)
    save_rgba("side_base.png", np.dstack([col.astype(np.uint8), a8]))

    # eye: cut + inpaint socket (ESTIMATE), eye layer reproduces the original exactly
    lum = f.mean(-1)
    ex, ey = EYE_SEED
    win = 40
    sub = (lum[ey - win:ey + win, ex - win:ex + win] < 130).astype(np.uint8)
    n, lab = cv2.connectedComponents(sub)
    ys, xs = np.nonzero(lab == lab[win, win])
    ys = ys + ey - win; xs = xs + ex - win
    core = np.zeros((H, W), np.uint8); core[ys, xs] = 1
    eye_info = dict(c=[float(xs.mean() + 0.5), float(ys.mean() + 0.5)],
                    r=[float((xs.max() - xs.min() + 1) / 2), float((ys.max() - ys.min() + 1) / 2)])
    hull = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    socket = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    plate = cv2.inpaint(col.astype(np.uint8), socket, 9, cv2.INPAINT_TELEA).astype(np.float32)
    rng = np.random.default_rng(7)
    ring = cv2.dilate(socket, np.ones((15, 15), np.uint8)) - socket
    hi = f - cv2.GaussianBlur(f, (0, 0), 2.0)
    g = hi[ring > 0]
    plate[socket > 0] += g[rng.integers(0, len(g), int(socket.sum()))] * 0.9
    fe = cv2.GaussianBlur(socket.astype(np.float32), (0, 0), 1.2)[..., None]
    plate = col * (1 - fe) + np.clip(plate, 0, 255) * fe
    save_rgba("side_plate.png", np.dstack([plate.astype(np.uint8), a8]))
    skin = plate.mean(-1)
    ea = np.clip((skin - lum) / np.maximum(skin - 45.0, 1), 0, 1) * hull
    need = cv2.GaussianBlur(np.clip(np.abs(f - plate).max(-1) / 40.0, 0, 1), (0, 0), 0.8) * socket
    ea = np.maximum(ea, need)
    erg = np.where(ea[..., None] > 0.01, (f - (1 - ea[..., None]) * plate) / np.maximum(ea[..., None], 0.01), 0)
    erg = bleed(np.clip(erg, 0, 255), ea > 0.02, 6)
    save_rgba("side_eye.png", np.dstack([erg.astype(np.uint8), (ea * 255 + 0.5).astype(np.uint8)]))

    ys_fg = np.nonzero(hard.any(1))[0]
    xs_fg = np.nonzero(hard.any(0))[0]
    ground = int(ys_fg.max())
    layout = dict(size=[W, H], crop=list(CROP), eye=eye_info, ground_y=ground,
                  bbox=[int(xs_fg.min()), int(ys_fg.min()), int(xs_fg.max()), ground],
                  anchor=[float((xs_fg.min() + xs_fg.max()) / 2), float(ground + 1)])
    if LEGS:
        masks(H, W, layout)
    with open(os.path.join(OUT, "side_layout.json"), "w") as fp:
        json.dump(layout, fp, indent=2)
    if DBG:
        os.makedirs(DBG, exist_ok=True)
        c = (col * a3 + np.array([255, 0, 255]) * (1 - a3)).astype(np.uint8)
        for x in range(0, W, 20):
            c[:, x] = (c[:, x] * 0.6 + np.array([0, 255, 0]) * 0.4).astype(np.uint8) if x % 100 else (0, 160, 0)
        for y in range(0, H, 20):
            c[y] = (c[y] * 0.6 + np.array([0, 255, 0]) * 0.4).astype(np.uint8) if y % 100 else (0, 160, 0)
        cv2.imwrite(os.path.join(DBG, "side_grid.png"), cv2.cvtColor(c, cv2.COLOR_RGB2BGR))
        cv2.imwrite(os.path.join(DBG, "side_plate.png"), cv2.cvtColor((plate * a3).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print(json.dumps(layout))


def masks(H, W, layout):
    def pm(polys):
        m = np.zeros((H, W), np.uint8)
        for p in polys:
            cv2.fillPoly(m, [np.array(p, np.int32)], 1)
        return m
    fe = lambda m, s: np.clip(cv2.GaussianBlur(m.astype(np.float32), (0, 0), s), 0, 1)
    zero = np.zeros((H, W), np.float32)
    legs = [fe(pm([PAIR["front"]]), 6), zero, fe(pm([PAIR["hind"]]), 6), zero]
    head = np.clip(fe(pm([HEAD_POLY, EAR_POLY]), 8) * 1.3, 0, 1)
    ear = fe(pm([EAR_POLY]), 5)
    yy = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
    ear *= np.clip((yy - PIVOTS["ear_root"][1]) / 60.0, 0, 1)
    tail = fe(pm([TAIL_POLY]), 6)
    body = 1 - np.clip((yy - 455) / 65.0, 0, 1) ** 2 * (3 - 2 * np.clip((yy - 455) / 65.0, 0, 1))  # paws stay down
    for a, name in ((np.dstack(legs), "side_masks.png"), (np.dstack([head, ear, tail, body]), "side_masks2.png")):
        save_rgba(name, (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    layout["hips"] = {k: PIVOTS[k] for k in ("nf", "ff", "nh", "fh")}
    layout["neck"] = PIVOTS["neck"]
    layout["ear_root"] = PIVOTS["ear_root"]
    layout["tail_root"] = PIVOTS["tail_root"]
    if DBG:
        base = cv2.imread(os.path.join(OUT, "side_crop.png")).astype(np.float32)
        for m, c in zip([legs[0], legs[2], head, ear, tail], [(0, 0, 255), (255, 0, 0), (0, 128, 255), (0, 255, 0), (255, 0, 255)]):
            base = base * (1 - 0.35 * m[..., None]) + np.array(c) * 0.35 * m[..., None]
        for k in ("nf", "ff", "nh", "fh", "neck", "ear_root", "tail_root"):
            cv2.circle(base, tuple(int(v) for v in PIVOTS[k]), 4, (0, 0, 0), -1)
        cv2.imwrite(os.path.join(DBG, "side_masks_overlay.png"), base.astype(np.uint8))


if __name__ == "__main__":
    main()
