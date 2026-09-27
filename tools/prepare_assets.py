"""Derive Kiwi front-view layers from the untouched source sheet.

Input : assets/source/kiwi_turnaround.webp (read-only, never modified)
Output: assets/derived/
  front_crop.png     front panel crop, original pixels (reference)
  alpha_matte.png    character matte (0..255)
  base.png           RGBA, background removed + edge despill, eyes still present
  plate.png          RGBA, same as base but eye sockets inpainted (ESTIMATED fur)
  eyes.png           RGBA, eyes only (cut from original pixels)
  warp.png           R = body weight for breathing, G = head/ear rigid weight,
                     B = chest-expansion weight
  layout.json        pixel coordinates used by the runtime (eyes, paw line, ...)

Run: .venv/bin/python tools/prepare_assets.py
"""
import json
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets/source/kiwi_turnaround.webp")
OUT = os.path.join(ROOT, "assets/derived")
DBG = os.environ.get("KIWI_DEBUG_DIR")

# Front panel crop in source pixels (character bbox is x 41..478, y 194..694).
CROP = (0, 150, 520, 740)  # x0, y0, x1, y1


def save(name, arr):
    path = os.path.join(OUT, name)
    if arr.ndim == 3 and arr.shape[2] == 4:
        cv2.imwrite(path, cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))
    elif arr.ndim == 3:
        cv2.imwrite(path, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    else:
        cv2.imwrite(path, arr)


def dbg(name, arr):
    if DBG:
        os.makedirs(DBG, exist_ok=True)
        cv2.imwrite(os.path.join(DBG, name), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if arr.ndim == 3 else arr)


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet = cv2.cvtColor(cv2.imread(SRC, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    x0, y0, x1, y1 = CROP
    img = sheet[y0:y1, x0:x1].copy()
    H, W = img.shape[:2]
    save("front_crop.png", img)
    f = img.astype(np.float32)

    # ---- background model: the flat cream colour sampled on the crop border
    border = np.concatenate([f[:6].reshape(-1, 3), f[-6:].reshape(-1, 3),
                             f[:, :6].reshape(-1, 3), f[:, -6:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((f - bg) ** 2).sum(-1))

    # ---- matte via GrabCut, seeded conservatively
    gc = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    gc[dist > 18] = cv2.GC_PR_FGD
    core = (dist > 45).astype(np.uint8)
    core = cv2.erode(core, np.ones((5, 5), np.uint8))
    gc[core > 0] = cv2.GC_FGD
    # sure background: near-flat colour connected to the border
    flat = (dist < 9).astype(np.uint8)
    n, lab = cv2.connectedComponents(flat, connectivity=4)
    edge_labels = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    sure_bg = np.isin(lab, list(edge_labels))
    gc[sure_bg] = cv2.GC_BGD
    # hand-placed hints for the low-contrast ground (paws vs shadowed floor)
    for (cx, cy, rx, ry) in PAW_ELLIPSES:
        cv2.ellipse(gc, (cx, cy), (rx, ry), 0, 0, 360, cv2.GC_FGD, -1)
    for poly in FLOOR_BG_POLYS:
        cv2.fillPoly(gc, [np.array(poly, np.int32)], cv2.GC_BGD)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    hard = np.isin(gc, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)
    # keep the single largest component, fill holes
    n, lab, stats, _ = cv2.connectedComponentsWithStats(hard, connectivity=8)
    biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    hard = (lab == biggest).astype(np.uint8)
    inv = 1 - hard
    n, lab = cv2.connectedComponents(inv, connectivity=4)
    outside = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    hard = np.where(np.isin(lab, list(outside)), 0, 1).astype(np.uint8)
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # background specks trapped in concave notches between fur tufts
    near_edge = cv2.erode(hard, np.ones((7, 7), np.uint8)) == 0
    hard[(dist < 22) & near_edge] = 0
    # ---- soft edge: estimate alpha in a thin band from colour distance to bg
    band = cv2.dilate(hard, np.ones((5, 5), np.uint8)) - cv2.erode(hard, np.ones((5, 5), np.uint8))
    # alpha from projection of pixel onto line bg -> local fg colour
    fg_local = local_mean(f, cv2.erode(hard, np.ones((7, 7), np.uint8)), 9)
    num = ((f - bg) * (fg_local - bg)).sum(-1)
    den = ((fg_local - bg) ** 2).sum(-1) + 1e-3
    a_est = np.clip(num / den, 0, 1)
    alpha = hard.astype(np.float32)
    alpha[band > 0] = a_est[band > 0]
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.6) * cv2.dilate(hard, np.ones((3, 3), np.uint8))
    alpha[cv2.erode(hard, np.ones((5, 5), np.uint8)) > 0] = 1.0
    alpha = np.clip(alpha, 0, 1)

    # ---- despill: un-mix the cream background from semi-transparent edge pixels
    a3 = alpha[..., None]
    col = np.where(a3 > 0.02, (f - (1 - a3) * bg) / np.maximum(a3, 0.02), fg_local)
    col = np.where(a3 < 0.999, np.clip(0.2 * col + 0.8 * fg_local, 0, 255), f)
    col = np.clip(col, 0, 255)
    # the opaque rim 1-4 px inside the edge is still ~30% mixed with the cream
    # background (would read as a light halo on dark backdrops): unmix it
    inner = hard - cv2.erode(hard, np.ones((9, 9), np.uint8))
    fg_deep = local_mean(f, cv2.erode(hard, np.ones((13, 13), np.uint8)), 6)
    proj = ((f - fg_deep) * (bg - fg_deep)).sum(-1) / (((bg - fg_deep) ** 2).sum(-1) + 1e-3)
    mix = np.clip(proj, 0, 0.45)[..., None]
    unmixed = np.clip((col - mix * bg) / (1 - mix), 0, 255)
    col = np.where((inner > 0)[..., None], col + 0.6 * (unmixed - col), col)
    # bleed colour outwards so bilinear sampling / warping never pulls in bg
    col = bleed(col, alpha > 0.5, 12)

    a8 = (alpha * 255 + 0.5).astype(np.uint8)
    save("alpha_matte.png", a8)
    base = np.dstack([col.astype(np.uint8), a8])
    save("base.png", base)

    # ---- eyes: dark ellipses; cut them out, inpaint the sockets (ESTIMATE)
    eyes_mask = np.zeros((H, W), np.uint8)
    eye_info = []
    lum = f.mean(-1)
    for (ex, ey) in EYE_SEEDS:
        win = 34
        sub = lum[ey - win:ey + win, ex - win:ex + win] < 130
        n, lab = cv2.connectedComponents(sub.astype(np.uint8))
        l = lab[win, win]
        ys, xs = np.nonzero(lab == l)
        ys = ys + ey - win
        xs = xs + ex - win
        m = np.zeros((H, W), np.uint8)
        m[ys, xs] = 1
        cx, cy = xs.mean(), ys.mean()
        eye_info.append(dict(cx=float(cx), cy=float(cy),
                             rx=float((xs.max() - xs.min() + 1) / 2), ry=float((ys.max() - ys.min() + 1) / 2)))
        eyes_mask |= m
    # soft eye alpha: include the anti-aliased rim
    eye_core = eyes_mask
    eye_hull = cv2.dilate(eye_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    # plate: inpaint the hull + a ring so no dark rim survives
    socket = cv2.dilate(eye_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    plate_rgb = cv2.inpaint(col.astype(np.uint8), socket, 9, cv2.INPAINT_TELEA).astype(np.float32)
    # re-add fine felt grain sampled from the surrounding skin so the patch is not glassy
    rng = np.random.default_rng(7)
    ring = cv2.dilate(socket, np.ones((15, 15), np.uint8)) - socket
    hi = f - cv2.GaussianBlur(f, (0, 0), 2.0)
    grain = hi[ring > 0]
    idx = rng.integers(0, len(grain), size=int(socket.sum()))
    plate_rgb[socket > 0] += grain[idx] * 0.9
    plate_rgb = np.clip(plate_rgb, 0, 255)
    feather = cv2.GaussianBlur(socket.astype(np.float32), (0, 0), 1.2)
    plate_rgb = col * (1 - feather[..., None]) + plate_rgb * feather[..., None]
    plate = np.dstack([plate_rgb.astype(np.uint8), a8])
    save("plate.png", plate)

    # eyes layer: original pixels, alpha = how dark relative to the local skin
    skin = plate_rgb.mean(-1)
    eye_a = np.clip((skin - lum) / np.maximum(skin - 45.0, 1), 0, 1)
    eye_a *= eye_hull
    # the socket also carries soft lid shading that the inpaint removed: give the
    # eye layer just enough alpha that eyes-over-plate reproduces the original
    need = np.abs(f - plate_rgb).max(-1) / 40.0
    need = cv2.GaussianBlur(np.clip(need, 0, 1), (0, 0), 0.8) * socket
    eye_a = np.maximum(eye_a, np.clip(need, 0, 1))
    eye_rgb = np.where(eye_a[..., None] > 0.01,
                       (f - (1 - eye_a[..., None]) * plate_rgb) / np.maximum(eye_a[..., None], 0.01), 0)
    eye_rgb = np.clip(eye_rgb, 0, 255)
    eye_rgb = bleed(eye_rgb, eye_a > 0.02, 6)
    eyes = np.dstack([eye_rgb.astype(np.uint8), (eye_a * 255 + 0.5).astype(np.uint8)])
    save("eyes.png", eyes)

    # ---- warp weights ----------------------------------------------------
    ys_fg = np.nonzero(hard.any(1))[0]
    top_y, bot_y = int(ys_fg.min()), int(ys_fg.max())
    yy = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
    # body weight: 0 at/below the paw tops, smooth rise to 1 at the neck line
    body = smoothstep(PAW_TOP_Y, NECK_Y, yy)
    # head + ears move rigidly: hand-drawn region, heavily feathered
    head = np.zeros((H, W), np.uint8)
    cv2.ellipse(head, HEAD_ELLIPSE[:2], HEAD_ELLIPSE[2:], 0, 0, 360, 1, -1)
    for poly in EAR_POLYS:
        cv2.fillPoly(head, [np.array(poly, np.int32)], 1)
    head_w = cv2.GaussianBlur(head.astype(np.float32), (0, 0), 9)
    head_w = np.clip(head_w * 1.25, 0, 1)
    rigid = np.maximum(body, head_w)
    # chest expansion (horizontal) centred on the cream bib
    cx, cy, sx, sy = CHEST_GAUSS
    xx = np.arange(W, dtype=np.float32)[None, :].repeat(H, 0)
    chest = np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2))
    chest *= (1 - head_w)
    chest *= smoothstep(PAW_TOP_Y - 2, PAW_TOP_Y - 40, yy)  # never touch the paws
    warp = np.dstack([body, rigid, chest])
    save("warp.png", (np.clip(warp, 0, 1) * 255 + 0.5).astype(np.uint8))

    layout = dict(
        size=[W, H], crop=list(CROP), bg=[float(v) for v in bg],
        eyes=eye_info, paw_top_y=PAW_TOP_Y, neck_y=NECK_Y, ground_y=bot_y, top_y=top_y,
        chest=dict(cx=cx, cy=cy),
    )
    with open(os.path.join(OUT, "layout.json"), "w") as fp:
        json.dump(layout, fp, indent=2)

    if DBG:
        for name, bgc in (("black", (0, 0, 0)), ("white", (255, 255, 255)), ("magenta", (255, 0, 255))):
            c = (col * a3 + np.array(bgc) * (1 - a3)).astype(np.uint8)
            dbg(f"comp_{name}.png", c)
        dbg("plate_black.png", (plate_rgb * a3).astype(np.uint8))
        dbg("warp.png", (np.clip(warp, 0, 1) * 255).astype(np.uint8))
    print(json.dumps(layout))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return (t * t * (3 - 2 * t)).astype(np.float32)


def local_mean(f, mask, k):
    m = mask.astype(np.float32)
    s = cv2.GaussianBlur(f * m[..., None], (0, 0), k)
    w = cv2.GaussianBlur(m, (0, 0), k)[..., None]
    out = s / np.maximum(w, 1e-4)
    return bleed(out, w[..., 0] > 1e-3, 40)


def bleed(col, valid, iters):
    """Push valid colours outward into invalid pixels (for clean bilinear edges)."""
    col = col.copy()
    valid = valid.astype(np.uint8)
    k = np.ones((3, 3), np.float32)
    for _ in range(iters):
        v = valid.astype(np.float32)
        s = cv2.filter2D(col * v[..., None], -1, k, borderType=cv2.BORDER_REPLICATE)
        c = cv2.filter2D(v, -1, k, borderType=cv2.BORDER_REPLICATE)
        grow = (valid == 0) & (c > 0)
        col[grow] = s[grow] / c[grow][..., None]
        valid = valid | grow.astype(np.uint8)
    return col


# ---- hand-authored annotations (crop pixel coordinates) -------------------
EYE_SEEDS = [(198, 176), (320, 176)]
PAW_ELLIPSES = [(184, 521, 36, 15), (335, 521, 36, 15)]
# shaded floor seen between the front legs and the contact strip under the paws
FLOOR_BG_POLYS = [
    [(236, 498), (278, 498), (284, 527), (292, 531), (300, 547), (218, 547), (226, 531), (232, 527)],
    [(0, 543), (519, 543), (519, 589), (0, 589)],
]
PAW_TOP_Y = 492  # paw mounds start at ~497; everything below is frozen
NECK_Y = 290
HEAD_ELLIPSE = (256, 170, 118, 110)
EAR_POLYS = [
    [(160, 80), (120, 90), (70, 160), (42, 240), (60, 300), (100, 340), (160, 335), (170, 260), (165, 150)],
    [(360, 80), (400, 90), (450, 160), (478, 240), (460, 300), (420, 340), (360, 335), (350, 260), (355, 150)],
]
CHEST_GAUSS = (258, 390, 80, 70)

if __name__ == "__main__":
    main()
