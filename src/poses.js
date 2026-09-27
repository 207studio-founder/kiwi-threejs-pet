// Export-specific key poses for every Codex v2 row. Units: source pixels
// (x 0.24 in the 192x208 cell) and radians. Frames are authored per state
// against the v2 durations; nothing is sampled from the 6 s preview loop.

export const V2_ROWS = [
  { state: 'idle', row: 0, durations: [280, 110, 110, 140, 140, 320] },
  { state: 'running-right', row: 1, durations: [120, 120, 120, 120, 120, 120, 120, 220] },
  { state: 'running-left', row: 2, durations: [120, 120, 120, 120, 120, 120, 120, 220] },
  { state: 'waving', row: 3, durations: [140, 140, 140, 280] },
  { state: 'jumping', row: 4, durations: [140, 140, 140, 140, 280] },
  { state: 'failed', row: 5, durations: [140, 140, 140, 140, 140, 140, 140, 240] },
  { state: 'waiting', row: 6, durations: [150, 150, 150, 150, 150, 260] },
  { state: 'running', row: 7, durations: [120, 120, 120, 120, 120, 220] },
  { state: 'review', row: 8, durations: [150, 150, 150, 150, 150, 280] },
];
export const LOOK_ANGLES = Array.from({ length: 16 }, (_, i) => i * 22.5);

const NEUTRAL = { rig: 'front' };
export const neutralPose = () => ({ ...NEUTRAL });

const lids = (l, r = l) => [l, r];

/** Look: angle in degrees, clockwise from 12 o'clock. Screen dir = (sin, -cos), y down. */
export function lookPose(deg) {
  const a = (deg * Math.PI) / 180;
  const vx = Math.sin(a), vy = -Math.cos(a);
  const up = Math.max(0, -vy), down = Math.max(0, vy);
  return {
    rig: 'front',
    // layered parallax: nose/muzzle (front-most) > eyes > head outline > ears (back, lagging)
    gaze: [18 * vx, 12 * vy],
    head: [14 * vx, 8 * vy - 2 * up, 0],
    muzzle: [24 * vx, 15 * vy],
    // the eye on the side the face turns toward is further away: foreshorten it
    eyeSX: [1 - 0.35 * Math.max(0, -vx), 1 - 0.35 * Math.max(0, vx)],
    // the ear on the side being turned toward tucks in more than the far ear
    earL: [-vx * (vx > 0 ? 2 : 7), 6 * up - 3 * down, -0.06 * vx],
    earR: [-vx * (vx > 0 ? 7 : 2), 6 * up - 3 * down, -0.06 * vx],
    lid: lids(0.38 * down),
  };
}

function frontIdle() {
  const f = (breath, lid, ear = 0) => ({ rig: 'front', breath, breathAmp: [3.0, 2.2], lid: lids(lid),
    earL: [0, ear, 0], earR: [0, ear, 0] });
  return [f(0, 0), f(0.2, 0.55), f(0.35, 1), f(0.6, 0.3), f(1, 0, 0.6), f(0.55, 0, 0.4)];
}

function waving() {
  const f = (lift, rot, tilt, earR, breath = 0.3) => ({ rig: 'front', breath,
    legL: [lift, rot], head: [0, 0, tilt], earL: [0, 0, 0.02], earR: [0, -earR, -0.06 * earR / 5] });
  return [f(24, 0.06, -0.03, 2), f(56, 0.14, -0.06, 5), f(50, -0.02, -0.07, 5), f(10, 0.02, -0.02, 1)];
}

function jumping() {
  return [
    { rig: 'front', squash: [1.05, 0.92], head: [0, 3, 0], lid: lids(0.25), earL: [0, 3, -0.03], earR: [0, 3, 0.03] },
    { rig: 'front', trans: [0, -60], squash: [0.97, 1.05], earL: [0, 8, -0.05], earR: [0, 8, 0.05], legL: [-4, 0], legR: [-4, 0] },
    { rig: 'front', trans: [0, -110], earL: [0, -8, 0.10], earR: [0, -8, -0.10], legL: [14, 0.05], legR: [14, -0.05], gaze: [0, -3] },
    { rig: 'front', squash: [1.06, 0.91], earL: [0, 7, -0.04], earR: [0, 7, 0.04], lid: lids(0.3) },
    { rig: 'front', squash: [1.0, 1.0], earL: [0, 2, 0], earR: [0, 2, 0], breath: 0.4 },
  ];
}

function failed() {
  const f = (k, lid = 0.45, breath = 0) => ({ rig: 'front', breath,
    head: [0, 10 * k, 0.02 * k], muzzle: [0, 7 * k], gaze: [0, 6 * k],
    earL: [3 * k, 8 * k, -0.07 * k], earR: [-3 * k, 8 * k, 0.07 * k],
    lid: lids(Math.max(lid * k, 0)) });
  return [f(0.35), f(0.75), f(1, 0.5, -0.8), f(1, 1, -1), f(1, 0.7, -0.6), f(0.95, 0.5, -0.3), f(0.85, 0.5, 0), f(0.6, 0.45, 0)];
}

function waiting() {
  const f = (t, lid = 0) => ({ rig: 'front', head: [0, -3 * t / 0.11, t], gaze: [2, -5], muzzle: [1, -4],
    earL: [0, 1, 0.02], earR: [0, -5 * t / 0.11, -0.08 * t / 0.11], lid: lids(lid), breath: 0.4 });
  return [f(0.03), f(0.08), f(0.11), f(0.11, 1), f(0.09), f(0.05)];
}

function running() {
  const f = (l, r, bob, tilt) => ({ rig: 'front', legL: [l, 0], legR: [r, 0],
    head: [0, 4 + bob, tilt], muzzle: [0, 5], gaze: [0, 7], lid: lids(0.25),
    earL: [0, -bob, 0.03 * Math.sign(tilt)], earR: [0, bob, 0.03 * Math.sign(tilt)] });
  return [f(13, 0, 1.5, 0.02), f(2, 6, -0.5, 0), f(0, 13, 1.5, -0.02), f(6, 2, -0.5, 0), f(13, 0, 1.5, 0.02), f(3, 8, 0, -0.01)];
}

function review() {
  const gx = [-8, -3, 3, 8, 3, -3];
  return gx.map((x, i) => ({ rig: 'front', gaze: [x, 6], muzzle: [x * 0.5, 5], head: [x * 0.3, 5, 0.006 * x],
    lid: lids(i === 4 ? 0.9 : 0.35), earL: [0, -1, 0.02], earR: [0, -1, -0.02] }));
}

function runningSide(flip) {
  const out = [];
  for (let i = 0; i < 8; i++) {
    const ph = (i / 8) * 2 * Math.PI;
    const s = Math.sin(ph), c = Math.cos(ph);
    const A = 11;                       // paw travel (source px) front/back
    const liftF = 7 * Math.max(0, -c), liftH = 7 * Math.max(0, c);  // lift while the paw travels forward (-x)
    out.push({
      rig: 'side', flip,
      // front pair and hind pair swing in opposite phase (trot-like cadence);
      // shear +x = paw moves backward for the left-facing drawing
      legRot: [A * s, 0, -A * s, 0],
      legLift: [liftF, 0, liftH, 0],
      body: [0, -3 * (1 - Math.cos(2 * ph)) / 2],
      head: [0, -2.5 * (1 - Math.cos(2 * ph - 0.6)) / 2, 0.02 * Math.sin(2 * ph)],
      ear: [0.07 * Math.sin(2 * ph - 1.0), 0],
      tail: 0.16 * Math.sin(ph + 0.8),
    });
  }
  return out;
}

const BUILDERS = {
  idle: frontIdle, waving, jumping, failed, waiting, running, review,
  'running-left': () => runningSide(false),
  'running-right': () => runningSide(true),
};

/** Key poses for a v2 state (one per atlas cell). */
export function statePoses(state) {
  const b = BUILDERS[state];
  if (!b) throw new Error(`unknown state ${state}`);
  return b();
}

/** Frame index shown at time t (ms) using the v2 durations, looping. */
export function frameAt(state, tMs) {
  const d = V2_ROWS.find((r) => r.state === state).durations;
  const total = d.reduce((a, b) => a + b, 0);
  let t = ((tMs % total) + total) % total;
  for (let i = 0; i < d.length; i++) { if (t < d[i]) return i; t -= d[i]; }
  return d.length - 1;
}
