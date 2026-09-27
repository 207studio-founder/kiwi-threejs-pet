// Kiwi front idle — 2.5D rig on the original illustration.
// Every visible pixel comes from assets/derived/*.png (cut from the source sheet);
// motion is a small inverse-warp of those pixels, a function of t only.
import * as THREE from 'three';

export const LOOP = 6.0;          // seconds; everything below is periodic in LOOP
const BREATH_PERIOD = LOOP / 2;   // 2 breaths per loop (~20 / min, resting dog)
const BREATH_UP_PX = 1.6;         // head/torso rise at full inhale (source px)
const BREATH_CHEST_PX = 1.3;      // chest widening at full inhale (source px)
// blink keys: start time (s). close 0.08s, hold 0.05s, open 0.15s
const BLINKS = [1.70, 4.30, 4.62];
const B_CLOSE = 0.08, B_HOLD = 0.05, B_OPEN = 0.15;

const smooth = (x) => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };
const wrap = (t) => ((t % LOOP) + LOOP) % LOOP;

/** Pure pose function: the whole animation state at time t. */
export function pose(t, enabled = {}) {
  const on = { breath: true, blink: true, tail: true, ...enabled };
  const tt = wrap(t);
  // breathing: slightly faster inhale than exhale, still exactly periodic
  let ph = (tt % BREATH_PERIOD) / BREATH_PERIOD;
  ph = ph + 0.07 * Math.sin(2 * Math.PI * ph);
  const breath = on.breath ? 0.5 - 0.5 * Math.cos(2 * Math.PI * ph) : 0;
  let close = 0;
  if (on.blink) {
    for (const s of BLINKS) {
      const u = tt - s;
      let c = 0;
      if (u >= 0 && u < B_CLOSE) c = smooth(u / B_CLOSE);
      else if (u >= B_CLOSE && u < B_CLOSE + B_HOLD) c = 1;
      else if (u >= B_CLOSE + B_HOLD && u < B_CLOSE + B_HOLD + B_OPEN) c = 1 - smooth((u - B_CLOSE - B_HOLD) / B_OPEN);
      close = Math.max(close, c);
    }
  }
  // tail: not visible from the front in the reference -> no visible channel.
  return { t: tt, breath, close, tail: 0 };
}

const vert = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;

const frag = /* glsl */ `
precision highp float;
varying vec2 vUv;
uniform sampler2D uPlate, uEyes, uWarp;
uniform vec2 uSize;
uniform float uBreath, uClose, uShadow;
uniform vec2 uEyeC[2];
uniform vec2 uEyeR[2];
uniform vec3 uChest;      // cx, cy, half-width
uniform vec4 uShadowE;    // cx, cy, rx, ry
uniform vec2 uAmp;        // up px, chest px

vec4 tex(sampler2D s, vec2 p) { return texture2D(s, vec2(p.x / uSize.x, 1.0 - p.y / uSize.y)); }

void main() {
  vec2 p = vec2(vUv.x * uSize.x, (1.0 - vUv.y) * uSize.y);      // source px, y down
  vec3 w = tex(uWarp, p).rgb;                                   // r body, g rigid, b chest
  vec2 d = vec2(uBreath * uAmp.y * w.b * clamp((p.x - uChest.x) / uChest.z, -1.5, 1.5),
                -uBreath * uAmp.x * w.g);
  vec2 q = p - d;                                               // inverse warp
  vec4 base = tex(uPlate, q);

  // eyes: squash toward a pivot below the centre and bend into a soft arc when
  // closed. Pixels are the original eye pixels; the plate underneath has no eye.
  vec4 eye = vec4(0.0);
  if (uClose > 0.0) {
    for (int i = 0; i < 2; i++) {
      vec2 e = q - uEyeC[i];
      vec2 R = uEyeR[i];
      if (abs(e.x) < R.x + 8.0 && abs(e.y) < R.y + 8.0) {
        float s = mix(1.0, 0.075, uClose);
        float pivot = 0.30 * R.y;
        float nx = clamp(e.x / R.x, -1.0, 1.0);
        float bend = uClose * uClose * 3.0 * (1.0 - nx * nx);
        vec4 acc = vec4(0.0);
        for (int k = 0; k < 5; k++) {                           // box filter across the squash
          float oy = (float(k) - 2.0) / 5.0;
          float sy = pivot + (e.y + oy - bend - pivot) / s;
          acc += tex(uEyes, uEyeC[i] + vec2(e.x, sy));
        }
        eye = acc / 5.0;
      }
    }
  } else {
    eye = tex(uEyes, q);
  }
  vec3 col = mix(base.rgb, eye.rgb, eye.a);
  float a = base.a;

  // optional fixed contact shadow (not from the source; the source shadow was removed)
  vec2 sd = (p - uShadowE.xy) / uShadowE.zw;
  float sa = uShadow * 0.22 * (1.0 - smoothstep(0.35, 1.0, length(sd)));
  vec3 scol = vec3(0.36, 0.25, 0.14);
  // premultiplied: character over shadow
  vec3 pc = col * a + scol * sa * (1.0 - a);
  float pa = a + sa * (1.0 - a);
  gl_FragColor = vec4(pc, pa);
}
`;

async function loadTex(url) {
  const tex = await new THREE.TextureLoader().loadAsync(url);
  tex.colorSpace = THREE.NoColorSpace;       // pass pixel values through untouched
  tex.premultiplyAlpha = false;
  tex.generateMipmaps = false;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  return tex;
}

/** Loads assets and returns a factory for renderers sharing the same material. */
export async function loadKiwi(base = './assets/derived/') {
  const layout = await (await fetch(base + 'layout.json')).json();
  const [plate, eyes, warp] = await Promise.all(
    ['plate.png', 'eyes.png', 'warp.png'].map((n) => loadTex(base + n)));
  const [W, H] = layout.size;
  const uniforms = {
    uPlate: { value: plate }, uEyes: { value: eyes }, uWarp: { value: warp },
    uSize: { value: new THREE.Vector2(W, H) },
    uBreath: { value: 0 }, uClose: { value: 0 }, uShadow: { value: 1 },
    uEyeC: { value: layout.eyes.map((e) => new THREE.Vector2(e.cx + 0.5, e.cy + 0.5)) },
    uEyeR: { value: layout.eyes.map((e) => new THREE.Vector2(e.rx, e.ry)) },
    uChest: { value: new THREE.Vector3(layout.chest.cx, layout.chest.cy, 80) },
    uShadowE: { value: new THREE.Vector4(W / 2, layout.ground_y - 2, 150, 10) },
    uAmp: { value: new THREE.Vector2(BREATH_UP_PX, BREATH_CHEST_PX) },
  };
  const material = new THREE.ShaderMaterial({
    uniforms, vertexShader: vert, fragmentShader: frag,
    transparent: true, premultipliedAlpha: true, depthTest: false, depthWrite: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  const scene = new THREE.Scene();
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(W, H), material);
  mesh.position.set(W / 2, H / 2, 0);
  scene.add(mesh);
  // fixed camera: exactly the source canvas, 1 unit = 1 source pixel
  const camera = new THREE.OrthographicCamera(0, W, H, 0, -1, 1);

  function apply(t, enabled) {
    const s = pose(t, enabled);
    uniforms.uBreath.value = s.breath;
    uniforms.uClose.value = s.close;
    uniforms.uShadow.value = enabled?.shadow === false ? 0 : 1;
    return s;
  }

  function makeRenderer(canvas, opts = {}) {
    const r = new THREE.WebGLRenderer({
      canvas, alpha: true, premultipliedAlpha: true, antialias: false,
      preserveDrawingBuffer: !!opts.preserveDrawingBuffer,
    });
    r.setClearColor(0x000000, 0);
    r.outputColorSpace = THREE.LinearSRGBColorSpace; // no output transform; shader is raw
    return r;
  }

  return { W, H, layout, uniforms, scene, camera, apply, makeRenderer, LOOP };
}

/**
 * Deterministic frame renderer for export. Same canvas size, scale and
 * placement for every t (no per-frame crop / zoom / recentring).
 */
export function createFrameRenderer(kiwi, scale = 1) {
  const canvas = document.createElement('canvas');
  const r = kiwi.makeRenderer(canvas, { preserveDrawingBuffer: true });
  r.setPixelRatio(1);
  r.setSize(Math.round(kiwi.W * scale), Math.round(kiwi.H * scale), false);
  return {
    canvas,
    width: canvas.width, height: canvas.height,
    /** render time t (seconds) -> PNG Blob */
    async renderFrame(t, enabled = {}) {
      kiwi.apply(t, enabled);
      r.render(kiwi.scene, kiwi.camera);
      return new Promise((res) => canvas.toBlob(res, 'image/png'));
    },
    dispose() { r.dispose(); r.forceContextLoss(); },
  };
}
