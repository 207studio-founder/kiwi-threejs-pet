import { loadPet, STAGE } from './pet.js';
import { V2_ROWS, LOOK_ANGLES, statePoses, lookPose, neutralPose, frameAt } from './poses.js';

const $ = (id) => document.getElementById(id);
const pet = await loadPet();

// preview canvas renders the full 768x832 stage; the 1x cell view is a 4x box-reduced copy
const view = $('view');
const r = pet.makeRenderer(view, { preserveDrawingBuffer: true });
r.setPixelRatio(1);
r.setSize(STAGE.W, STAGE.H, false);

// off-screen export renderer (same stage)
const exCanvas = document.createElement('canvas');
const ex = pet.makeRenderer(exCanvas, { preserveDrawingBuffer: true });
ex.setPixelRatio(1);
ex.setSize(STAGE.W, STAGE.H, false);

function poseFor(state, tMs) {
  if (state === 'look') return lookPose(ui.angle);
  if (state === 'neutral') return neutralPose();
  return statePoses(state)[frameAt(state, tMs)];
}

/** Render a v2 state at time t (ms) with the v2 frame durations (as the app would show it). */
function renderState(state, tMs, renderer = r) {
  pet.apply(poseFor(state, tMs));
  renderer.render(pet.scene, pet.camera);
}
/** Render a look direction (degrees clockwise from up). */
function renderLook(deg, renderer = r) {
  pet.apply(lookPose(deg));
  renderer.render(pet.scene, pet.camera);
}

const blobOf = () => new Promise((res) => exCanvas.toBlob(res, 'image/png'));
async function renderPoseBlob(pose) {
  pet.apply(pose);
  ex.render(pet.scene, pet.camera);
  return blobOf();
}

/** List of every stage frame that goes into the atlas. */
function atlasJobs() {
  const jobs = [];
  for (const row of V2_ROWS) {
    if (row.state.startsWith('running-') && !pet.hasSide) continue;
    statePoses(row.state).forEach((pose, i) => jobs.push({ dir: row.state, name: `${String(i).padStart(2, '0')}.png`, pose }));
  }
  LOOK_ANGLES.forEach((deg, i) => jobs.push({ dir: 'look', name: `${String(i).padStart(2, '0')}_${String(deg * 10).padStart(4, '0')}.png`, pose: lookPose(deg) }));
  jobs.push({ dir: 'neutral', name: 'neutral.png', pose: neutralPose() });
  return jobs;
}

/**
 * Render every atlas frame at stage resolution, save under export/codex-v2/stage/,
 * then ask the local server to run tools/build_codex.py (downsample + assemble + validate).
 */
async function exportCodexAtlas({ build = true, only } = {}) {
  const jobs = atlasJobs().filter((j) => !only || only.includes(j.dir));
  for (const [i, j] of jobs.entries()) {
    const blob = await renderPoseBlob(j.pose);
    const res = await fetch(`/api/codex/stage/${j.dir}/${j.name}`, { method: 'POST', body: blob });
    if (!res.ok) throw new Error(`save ${j.dir}/${j.name}: ${res.status}`);
    $('status').textContent = `stage ${i + 1}/${jobs.length}`;
  }
  if (!build) return { frames: jobs.length };
  const out = await (await fetch('/api/codex/build', { method: 'POST' })).json();
  $('status').textContent = `build exit ${out.exit}`;
  return out;
}

// ---------------------------------------------------------------- UI
const ui = { state: 'idle', playing: true, t: 0, angle: 0, auto: true };
const sel = $('state');
for (const s of [...V2_ROWS.map((r) => r.state), 'look', 'neutral']) sel.add(new Option(s, s));
sel.onchange = () => { ui.state = sel.value; ui.t = 0; };
$('play').onclick = () => { ui.playing = !ui.playing; $('play').textContent = ui.playing ? '일시정지' : '재생'; };
$('angle').oninput = (e) => { ui.angle = +e.target.value; ui.auto = false; };
$('autolook').onchange = (e) => { ui.auto = e.target.checked; };
document.querySelectorAll('[data-bg]').forEach((b) => { b.onclick = () => { document.body.dataset.bg = b.dataset.bg; }; });
$('export').onclick = () => exportCodexAtlas().then((o) => console.log(o)).catch((e) => { $('status').textContent = String(e); });

const cell = $('cell').getContext('2d');
const cellBig = $('cellbig').getContext('2d');
let last = performance.now();
function tick(now) {
  const dt = now - last; last = now;
  if (ui.playing) { ui.t += dt; if (ui.state === 'look' && ui.auto) ui.angle = (ui.angle + dt * 0.09) % 360; }
  renderState(ui.state, ui.t);
  // 1x cell preview (browser downscale, preview only; export uses exact box filter)
  cell.clearRect(0, 0, 192, 208);
  cell.imageSmoothingQuality = 'high';
  cell.drawImage(view, 0, 0, 192, 208);
  cellBig.imageSmoothingEnabled = false;
  cellBig.clearRect(0, 0, 576, 624);
  cellBig.drawImage($('cell'), 0, 0, 576, 624);
  const f = ui.state === 'look' ? `${ui.angle.toFixed(1)}°` : (ui.state === 'neutral' ? '-' : frameAt(ui.state, ui.t));
  $('readout').textContent = `${ui.state} frame ${f}`;
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

window.pet = { renderState, renderLook, exportCodexAtlas, atlasJobs, STAGE, V2_ROWS, LOOK_ANGLES, ui };
document.body.dataset.ready = '1';
