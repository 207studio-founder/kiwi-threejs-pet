import { loadKiwi, createFrameRenderer, pose, LOOP } from './kiwi.js';
import { zipStore } from './zip.js';

const $ = (id) => document.getElementById(id);
const kiwi = await loadKiwi();
const stage = $('stage');
const canvas = $('view');
const renderer = kiwi.makeRenderer(canvas);

const state = { playing: true, t: 0, speed: 1, enabled: { breath: true, blink: true, tail: true, shadow: false } };

// ---- layout: keep the source aspect, anchor the ground line at the bottom-centre
function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const box = stage.getBoundingClientRect();
  const s = Math.min(box.width / kiwi.W, box.height / kiwi.H);
  const cw = Math.floor(kiwi.W * s), ch = Math.floor(kiwi.H * s);
  renderer.setPixelRatio(dpr);
  renderer.setSize(cw, ch, true);
  canvas.style.left = `${Math.round((box.width - cw) / 2)}px`;
  canvas.style.top = `${Math.round(box.height - ch)}px`;
}
new ResizeObserver(resize).observe(stage);
resize();

// ---- UI
const slider = $('time');
slider.max = LOOP;
$('play').onclick = () => { state.playing = !state.playing; syncUI(); };
slider.oninput = () => { state.playing = false; state.t = +slider.value; syncUI(); };
$('speed').onchange = (e) => { state.speed = +e.target.value; };
for (const k of Object.keys(state.enabled)) {
  const el = $('en-' + k);
  el.checked = state.enabled[k];
  el.onchange = () => { state.enabled[k] = el.checked; };
}
document.querySelectorAll('[data-bg]').forEach((b) => {
  b.onclick = () => { stage.dataset.bg = b.dataset.bg; document.querySelectorAll('[data-bg]').forEach((x) => x.classList.toggle('on', x === b)); };
});
$('ref').onchange = (e) => { $('refimg').hidden = !e.target.checked; };
function syncUI() {
  $('play').textContent = state.playing ? '일시정지' : '재생';
  slider.value = state.t.toFixed(3);
  const p = pose(state.t, state.enabled);
  $('readout').textContent = `t=${state.t.toFixed(3)}s / ${LOOP}s · breath ${p.breath.toFixed(2)} · blink ${p.close.toFixed(2)}`;
}
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' && e.target.type !== 'checkbox' && e.target.type !== 'range') return;
  if (e.code === 'Space') { e.preventDefault(); state.playing = !state.playing; syncUI(); }
  if (e.code === 'ArrowRight' || e.code === 'ArrowLeft') {
    state.playing = false;
    state.t = ((state.t + (e.code === 'ArrowRight' ? 1 : -1) / 30) % LOOP + LOOP) % LOOP;
    syncUI();
  }
});

// small pet-size preview (downscaled copy of the live canvas)
const mini = $('mini').getContext('2d');

let last = performance.now();
function frame(now) {
  const dt = (now - last) / 1000; last = now;
  if (state.playing) state.t = (state.t + dt * state.speed) % LOOP;
  kiwi.apply(state.t, state.enabled);
  renderer.render(kiwi.scene, kiwi.camera);
  const m = $('mini');
  mini.clearRect(0, 0, m.width, m.height);
  mini.imageSmoothingQuality = 'high';
  mini.drawImage(canvas, 0, 0, m.width, m.height);
  if (state.playing) syncUI();
  requestAnimationFrame(frame);
}
syncUI();
requestAnimationFrame(frame);

// ---- export API ------------------------------------------------------------
/**
 * Render one frame at time t as a transparent PNG Blob.
 * Canvas size = source size * scale for every call (fixed framing).
 */
const frameRenderers = new Map();   // one GL context per scale, reused (contexts are limited)
function frameRenderer(scale) {
  if (!frameRenderers.has(scale)) frameRenderers.set(scale, createFrameRenderer(kiwi, scale));
  return frameRenderers.get(scale);
}
async function renderFrame(t, { scale = 1, enabled = state.enabled } = {}) {
  return frameRenderer(scale).renderFrame(t, enabled);
}

/** Render the whole loop: frames t = i / fps, i = 0 .. fps*LOOP-1 (t=LOOP == t=0). */
async function renderSequence({ fps = 30, scale = 1, enabled = state.enabled, onFrame } = {}) {
  const fr = frameRenderer(scale);
  const n = Math.round(fps * LOOP);
  const out = [];
  for (let i = 0; i < n; i++) {
    const blob = await fr.renderFrame(i / fps, enabled);
    const name = `kiwi_idle_${String(i).padStart(4, '0')}.png`;
    out.push({ name, blob });
    onFrame?.(i, n, name, blob);
  }
  return { frames: out, width: fr.width, height: fr.height, fps, loop: LOOP };
}

/** Save a sequence to ./export/<dir>/ through the local dev server (no external upload). */
async function exportToServer({ dir = 'idle_front', fps = 30, scale = 1, enabled = state.enabled } = {}) {
  const status = $('status');
  const seq = await renderSequence({
    fps, scale, enabled,
    onFrame: async () => {},
  });
  for (const [i, f] of seq.frames.entries()) {
    const r = await fetch(`/api/export/${encodeURIComponent(dir)}/${f.name}`, { method: 'POST', body: f.blob });
    if (!r.ok) throw new Error(`save failed: ${f.name} ${r.status}`);
    status.textContent = `저장 중 ${i + 1}/${seq.frames.length}`;
  }
  const meta = { fps, loop_seconds: LOOP, frames: seq.frames.length, width: seq.width, height: seq.height,
    scale, enabled, ground_y_px: Math.round(kiwi.layout.ground_y * scale), note: 'fixed canvas; no per-frame crop' };
  await fetch(`/api/export/${encodeURIComponent(dir)}/sequence.json`, { method: 'POST', body: JSON.stringify(meta, null, 2) });
  status.textContent = `export/${dir}/ 에 ${seq.frames.length}장 저장`;
  return meta;
}

async function downloadZip({ fps = 30, scale = 1 } = {}) {
  const status = $('status');
  const seq = await renderSequence({ fps, scale, onFrame: (i, n) => { status.textContent = `렌더 ${i + 1}/${n}`; } });
  const files = await Promise.all(seq.frames.map(async (f) => ({ name: f.name, data: new Uint8Array(await f.blob.arrayBuffer()) })));
  const zip = zipStore(files);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([zip], { type: 'application/zip' }));
  a.download = `kiwi_idle_${fps}fps_x${scale}.zip`;
  a.click();
  status.textContent = `ZIP ${files.length}장`;
}

$('exp-server').onclick = () => exportToServer({ fps: +$('fps').value, scale: +$('scale').value }).catch((e) => { $('status').textContent = String(e); });
$('exp-zip').onclick = () => downloadZip({ fps: +$('fps').value, scale: +$('scale').value });

window.kiwi = { LOOP, pose, renderFrame, renderSequence, exportToServer, downloadZip, state, W: kiwi.W, H: kiwi.H, layout: kiwi.layout };
document.body.dataset.ready = '1';
