"""Build the Codex v2 atlas from browser-rendered stage frames.

in : export/codex-v2/stage/<state>/NN.png   (768x832, native RGBA from WebGL)
     export/codex-v2/stage/look/NN_AAAA.png, stage/neutral/neutral.png
out: export/codex-v2/frames/<state>/NN.png  (192x208, exact 4x4 premultiplied box)
     export/codex-v2/atlas.png, dist/kiwi-2d/spritesheet.webp (lossless, exact), dist/kiwi-2d/pet.json
     export/codex-v2/qa/*  (validator json + logs + exit codes, previews, direction sheet)

No resize/crop/recentre per cell: each cell is the full stage reduced 4x.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "export/codex-v2")
STAGE = os.path.join(BASE, "stage")
FRAMES = os.path.join(BASE, "frames")
QA = os.path.join(BASE, "qa")
DIST = os.path.join(ROOT, "dist/kiwi-2d")
# Optional Codex hatch-pet validators (not shipped here). Override with HATCH_PET_SCRIPTS=/path/to/scripts.
SKILL = os.environ.get("HATCH_PET_SCRIPTS", os.path.expanduser("~/.codex/skills/hatch-pet/scripts"))
CW, CH, N = 192, 208, 4
ROWS = [
    ("idle", 0, [280, 110, 110, 140, 140, 320]),
    ("running-right", 1, [120] * 7 + [220]),
    ("running-left", 2, [120] * 7 + [220]),
    ("waving", 3, [140, 140, 140, 280]),
    ("jumping", 4, [140, 140, 140, 140, 280]),
    ("failed", 5, [140] * 7 + [240]),
    ("waiting", 6, [150] * 5 + [260]),
    ("running", 7, [120] * 5 + [220]),
    ("review", 8, [150] * 5 + [280]),
]
MANIFEST = {"id": "kiwi-2d", "displayName": "Kiwi", "description": "라떼색 장모 닥스훈트 키위",
            "spritesheetPath": "spritesheet.webp", "spriteVersionNumber": 2}
PAW_ROW_CELL = 189  # source paw-top line 492 -> stage 750.1 -> cell 187.5; rows >= 189 are paw-only


def reduce4(path):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    assert a.shape == (CH * N, CW * N, 4), (path, a.shape)
    al = a[..., 3:4] / 255.0
    pm = np.concatenate([a[..., :3] * al, al], -1)
    pm = pm.reshape(CH, N, CW, N, 4).mean((1, 3))
    alpha = pm[..., 3:4]
    rgb = np.where(alpha > 0, pm[..., :3] / np.maximum(alpha, 1e-9), 0)
    out = np.concatenate([rgb, alpha * 255], -1)
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    out[out[..., 3] == 0, :3] = 0
    return out


def run(cmd, name):
    log = os.path.join(QA, f"{name}.log")
    with open(log, "w") as fp:
        p = subprocess.run(cmd, stdout=fp, stderr=subprocess.STDOUT)
    with open(log + ".exit", "w") as fp:
        fp.write(f"{p.returncode}\n")
    return p.returncode


def main():
    os.makedirs(QA, exist_ok=True)
    os.makedirs(DIST, exist_ok=True)
    report = {"rows": {}, "missing": []}
    cells = {}
    for state, row, durs in ROWS:
        sdir = os.path.join(STAGE, state)
        files = sorted(f for f in os.listdir(sdir) if f.endswith(".png")) if os.path.isdir(sdir) else []
        if len(files) != len(durs):
            report["missing"].append(f"{state}: {len(files)}/{len(durs)}")
            continue
        odir = os.path.join(FRAMES, state)
        os.makedirs(odir, exist_ok=True)
        cells[state] = []
        for i, f in enumerate(files):
            c = reduce4(os.path.join(sdir, f))
            Image.fromarray(c).save(os.path.join(odir, f"{i:02d}.png"))
            cells[state].append(c)
    look = sorted(f for f in os.listdir(os.path.join(STAGE, "look")) if f.endswith(".png"))
    assert len(look) == 16, look
    cells["look"] = [reduce4(os.path.join(STAGE, "look", f)) for f in look]
    os.makedirs(os.path.join(FRAMES, "look"), exist_ok=True)
    for f, c in zip(look, cells["look"]):
        Image.fromarray(c).save(os.path.join(FRAMES, "look", f))
    cells["neutral"] = reduce4(os.path.join(STAGE, "neutral", "neutral.png"))
    os.makedirs(os.path.join(FRAMES, "neutral"), exist_ok=True)
    Image.fromarray(cells["neutral"]).save(os.path.join(FRAMES, "neutral", "neutral.png"))

    # ---- assemble (exact paste, no resampling)
    atlas = np.zeros((11 * CH, 8 * CW, 4), np.uint8)
    for state, row, durs in ROWS:
        for i, c in enumerate(cells.get(state, [])):
            atlas[row * CH:(row + 1) * CH, i * CW:(i + 1) * CW] = c
    atlas[0:CH, 6 * CW:7 * CW] = cells["neutral"]
    for i, c in enumerate(cells["look"]):
        r, col = 9 + i // 8, i % 8
        atlas[r * CH:(r + 1) * CH, col * CW:(col + 1) * CW] = c
    atlas[atlas[..., 3] == 0, :3] = 0
    img = Image.fromarray(atlas)
    img.save(os.path.join(BASE, "atlas.png"))
    webp = os.path.join(DIST, "spritesheet.webp")
    img.save(webp, format="WEBP", lossless=True, quality=100, method=6, exact=True)
    with open(os.path.join(DIST, "pet.json"), "w") as fp:
        json.dump(MANIFEST, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    back = np.asarray(Image.open(webp).convert("RGBA"))
    report["webp_roundtrip_identical"] = bool(np.array_equal(back, atlas))
    report["atlas_size"] = list(img.size)

    # ---- validators (read-only skill scripts)
    if not os.path.isfile(os.path.join(SKILL, "validate_atlas.py")):
        report["validate_atlas_exit"] = report["inspect_frames_exit"] = "skipped (hatch-pet validators not found)"
    else:
      report["validate_atlas_exit"] = run([sys.executable, os.path.join(SKILL, "validate_atlas.py"), webp,
                                         "--require-v2", "--native-alpha",
                                         "--json-out", os.path.join(QA, "validate_atlas.json")], "validate_atlas")
      report["inspect_frames_exit"] = run([sys.executable, os.path.join(SKILL, "inspect_frames.py"),
                                         "--frames-root", FRAMES, "--native-alpha",
                                         "--json-out", os.path.join(QA, "inspect_frames.json")], "inspect_frames")

    # ---- project checks
    if "idle" in cells:
        paw = np.stack([c[PAW_ROW_CELL:] for c in cells["idle"]]).astype(int)
        report["idle_paw_rows_max_change"] = int(np.abs(paw - paw[0]).max())
    for state, row, durs in ROWS:
        cs = cells.get(state)
        if not cs:
            continue
        diffs = [float(np.abs(cs[i].astype(int) - cs[(i + 1) % len(cs)].astype(int)).mean()) for i in range(len(cs))]
        ys = [np.nonzero(c[..., 3].any(1))[0] for c in cs]
        xs = [np.nonzero(c[..., 3].any(0))[0] for c in cs]
        report["rows"][state] = {
            "frames": len(cs), "durations": durs, "loop_ms": sum(durs),
            "step_mean_abs": [round(d, 3) for d in diffs],  # last entry = wrap to frame 0
            "min_step": round(min(diffs), 3),
            "bbox_y": [int(min(y.min() for y in ys)), int(max(y.max() for y in ys))],
            "bbox_x": [int(min(x.min() for x in xs)), int(max(x.max() for x in xs))],
            "bottom_row": [int(y.max()) for y in ys],
        }
    with open(os.path.join(QA, "build_report.json"), "w") as fp:
        json.dump(report, fp, indent=1)
    previews(cells)
    print(json.dumps(report))
    ok = lambda v: v == 0 or str(v).startswith("skipped")
    sys.exit(0 if ok(report["validate_atlas_exit"]) and ok(report["inspect_frames_exit"]) else 1)


def on_bg(c, bg):
    im = Image.new("RGBA", (CW, CH), bg)
    im.alpha_composite(Image.fromarray(c))
    return im


def previews(cells):
    os.makedirs(os.path.join(QA, "previews"), exist_ok=True)
    for state, row, durs in ROWS:
        cs = cells.get(state)
        if not cs:
            continue
        for tag, bg in (("white", (255, 255, 255, 255)), ("black", (0, 0, 0, 255))):
            fr = [on_bg(c, bg).convert("RGB") for c in cs]
            fr[0].save(os.path.join(QA, "previews", f"{state}_{tag}_1x.gif"), save_all=True,
                       append_images=fr[1:], duration=durs, loop=0)
        # strip: 1x white, 1x black, 2x white
        strip = Image.new("RGB", (CW * len(cs), CH * 4), (255, 255, 255))
        for i, c in enumerate(cs):
            strip.paste(on_bg(c, (255, 255, 255, 255)).convert("RGB"), (i * CW, 0))
            strip.paste(on_bg(c, (0, 0, 0, 255)).convert("RGB"), (i * CW, CH))
        big = Image.new("RGB", (CW * 2 * len(cs), CH * 2), (255, 255, 255))
        for i, c in enumerate(cs):
            big.paste(on_bg(c, (255, 255, 255, 255)).convert("RGB").resize((CW * 2, CH * 2), Image.NEAREST), (i * CW * 2, 0))
        strip.save(os.path.join(QA, "previews", f"{state}_strip.png"))
        big.save(os.path.join(QA, "previews", f"{state}_2x.png"))
    # direction sheet: compass layout at 1x + head crops at 3x
    look = cells["look"]
    R = 500
    sheet = Image.new("RGB", (2 * R + CW + 40, 2 * R + CH + 40), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    cx, cy = sheet.width // 2, sheet.height // 2
    sheet.paste(on_bg(cells["neutral"], (255, 255, 255, 255)).convert("RGB"), (cx - CW // 2, cy - CH // 2))
    d.text((cx - 20, cy + CH // 2 + 2), "neutral", fill=(0, 0, 0))
    for i, c in enumerate(look):
        a = np.radians(i * 22.5)
        x, y = cx + R * np.sin(a), cy - R * np.cos(a)
        sheet.paste(on_bg(c, (255, 255, 255, 255)).convert("RGB"), (int(x - CW / 2), int(y - CH / 2)))
        d.text((int(x - CW / 2) + 4, int(y - CH / 2) + 2), f"{i * 22.5:g}", fill=(200, 0, 0))
    sheet.save(os.path.join(QA, "look_directions.png"))
    heads = Image.new("RGB", (8 * 180, 2 * 150), (255, 255, 255))
    for i, c in enumerate(look):
        crop = on_bg(c, (255, 255, 255, 255)).crop((36, 70, 156, 170)).resize((180, 150), Image.NEAREST)
        heads.paste(crop.convert("RGB"), ((i % 8) * 180, (i // 8) * 150))
    heads.save(os.path.join(QA, "look_heads_zoom.png"))


if __name__ == "__main__":
    main()
