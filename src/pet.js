// Kiwi Codex-v2 rig: the same original pixels as src/kiwi.js, on a fixed stage.
// Stage 768x832 = 4x the 192x208 atlas cell. Sprite scale 0.96 source px/stage px,
// ground line y=800, horizontal centre x=384 for every state (no per-frame crop).
import * as THREE from 'three';

export const STAGE = { W: 768, H: 832, K: 0.96, GROUND: 800, CX: 384, DOWNSAMPLE: 4 };

const vert = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

// ---------------------------------------------------------------- front rig
const frontFrag = /* glsl */ `
precision highp float;
varying vec2 vUv;
uniform sampler2D uPlate, uEyes, uWarp, uMasks, uLegs;
uniform vec2 uSize, uStage, uOrigin;  // origin: stage px of source (0,0); uK: scale
uniform float uK;
uniform float uBreath; uniform vec2 uBreathAmp;
uniform vec2 uEyeC[2]; uniform vec2 uEyeR[2];
uniform vec2 uLid;          // per-eye closure 0..1 (L, R as seen on screen)
uniform vec2 uGaze;         // eye offset inside the face (source px)
uniform vec2 uEyeSX;        // per-eye horizontal foreshortening (1 = original)
uniform vec3 uHead;         // dx, dy, tilt(rad) about the neck
uniform vec2 uMuzzle;       // extra muzzle/nose parallax (source px)
uniform vec3 uEarL, uEarR;  // dx, dy, hinge rotation(rad)
uniform vec2 uLegL, uLegR;  // lift (source px), rotation (rad)
uniform vec2 uSquash;       // sx, sy about the ground anchor
uniform vec2 uTrans;        // whole-body translation (source px)
uniform vec2 uAnchor;       // ground anchor (source px)

vec4 tex(sampler2D s, vec2 p) { return texture2D(s, vec2(p.x / uSize.x, 1.0 - p.y / uSize.y)); }
vec2 rot(float a, vec2 v) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }

const vec2 NECK = vec2(259.0, 300.0);
const vec2 EAR_L = vec2(150.0, 100.0);
const vec2 EAR_R = vec2(370.0, 100.0);
const vec2 KNEE_L = vec2(180.0, 432.0);
const vec2 KNEE_R = vec2(340.0, 432.0);

// forward displacement of a source point
vec2 D(vec2 q) {
  vec3 w = tex(uWarp, q).rgb;     // body, rigid(head+torso), chest
  vec4 m = tex(uMasks, q);        // head, earL, earR, muzzle
  vec4 lg = tex(uLegs, q);        // legL, legR
  vec2 d = vec2(uBreath * uBreathAmp.y * w.b * clamp((q.x - 258.0) / 80.0, -1.5, 1.5),
                -uBreath * uBreathAmp.x * w.g);
  d += m.r * (rot(uHead.z, q - NECK) + NECK - q + uHead.xy);
  d += m.a * uMuzzle;
  d += m.g * (rot(uEarL.z, q - EAR_L) + EAR_L - q + uEarL.xy);
  d += m.b * (rot(uEarR.z, q - EAR_R) + EAR_R - q + uEarR.xy);
  float ramp = smoothstep(432.0, 500.0, q.y);
  d += lg.r * (vec2(0.0, -uLegL.x * ramp) + rot(uLegL.y * ramp, q - KNEE_L) + KNEE_L - q);
  d += lg.g * (vec2(0.0, -uLegR.x * ramp) + rot(uLegR.y * ramp, q - KNEE_R) + KNEE_R - q);
  return d;
}

// eye with an upper lid: lid clip for partial closure, thin arc when fully shut
vec4 eyeAt(vec2 q, int i, float c) {
  vec2 C = uEyeC[i]; vec2 R = uEyeR[i];
  vec2 e = q - uGaze - C;
  e.x /= (i == 0 ? uEyeSX.x : uEyeSX.y);
  if (abs(e.x) > R.x + 8.0 || abs(e.y) > R.y + 8.0) return vec4(0.0);
  if (c <= 0.001) return tex(uEyes, C + e);
  float nx = clamp(e.x / R.x, -1.0, 1.0);
  // lid edge: descends from above the eye to 30% below centre, bowing slightly down
  float lid = -R.y * 1.05 + c * (1.35 * R.y) + 2.2 * c * (1.0 - nx * nx);
  vec4 open = tex(uEyes, C + e);
  open *= smoothstep(lid - 0.8, lid + 0.8, e.y);
  // lid shading: the skin just above the lid edge darkens slightly
  // closed: squash the original eye pixels into a soft arc
  float s = 0.075;
  float pivot = 0.30 * R.y;
  float bend = 3.0 * (1.0 - nx * nx);
  vec4 acc = vec4(0.0);
  for (int k = 0; k < 5; k++) {
    float oy = (float(k) - 2.0) / 5.0;
    acc += tex(uEyes, C + vec2(e.x, pivot + (e.y + oy - bend - pivot) / s));
  }
  vec4 shut = acc / 5.0;
  float f = smoothstep(0.78, 0.97, c);
  return mix(open, shut, f);
}

void main() {
  vec2 sp = vec2(vUv.x * uStage.x, (1.0 - vUv.y) * uStage.y);    // stage px, y down
  vec2 p = (sp - uOrigin) / uK;                                     // source px
  p = uAnchor + (p - uTrans - uAnchor) / uSquash;                   // undo global
  vec2 q = p;
  for (int i = 0; i < 8; i++) q = p - D(q);                         // invert local warp
  vec4 base = tex(uPlate, q);
  vec4 e0 = eyeAt(q, 0, uLid.x);
  vec4 e1 = eyeAt(q, 1, uLid.y);
  vec4 eye = e0.a > e1.a ? e0 : e1;
  vec3 col = mix(base.rgb, eye.rgb, eye.a);
  float a = base.a;
  gl_FragColor = vec4(col * a, a);
}`;

// ---------------------------------------------------------------- side rig
const sideFrag = /* glsl */ `
precision highp float;
varying vec2 vUv;
uniform sampler2D uPlate, uEye, uMasks, uMasks2;
uniform vec2 uSize, uStage, uOrigin;
uniform float uK;
uniform vec4 uLegRot;     // leg shear px: front pair, -, hind pair, -
uniform vec4 uLegLift;    // source px
uniform vec2 uBody;       // body bob dx, dy
uniform vec3 uHead;       // dx, dy, tilt
uniform vec2 uEar;        // ear swing rad, ear dy
uniform float uTail;      // tail rotation rad
uniform float uLid;
uniform vec2 uEyeC; uniform vec2 uEyeR;
uniform vec4 uHip0, uHip1;    // pivots: nf.xy nf2.zw / nh.xy fh.zw
uniform vec2 uNeck, uEarRoot, uTailRoot;
uniform float uFlip;          // 1 = mirror horizontally (running-right)

vec4 tex(sampler2D s, vec2 p) { return texture2D(s, vec2(p.x / uSize.x, 1.0 - p.y / uSize.y)); }
vec2 rot(float a, vec2 v) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }

// leg swing as a shear below the hip line (x offset in source px at the paw)
vec2 leg(vec2 q, vec2 hip, float sx, float lift) {
  float ramp = smoothstep(hip.y, hip.y + 70.0, q.y);
  return vec2(sx * ramp, -lift * ramp);
}

vec2 D(vec2 q) {
  vec4 L = tex(uMasks, q);    // nf, ff, nh, fh
  vec4 M = tex(uMasks2, q);   // head, ear, tail, body
  vec2 d = M.a * uBody;
  d += M.r * (rot(uHead.z, q - uNeck) + uNeck - q + uHead.xy);
  d += M.g * (rot(uEar.x, q - uEarRoot) + uEarRoot - q + vec2(0.0, uEar.y));
  d += M.b * (rot(uTail, q - uTailRoot) + uTailRoot - q);
  d += L.r * leg(q, uHip0.xy, uLegRot.x, uLegLift.x);
  d += L.g * leg(q, uHip0.zw, uLegRot.y, uLegLift.y);
  d += L.b * leg(q, uHip1.xy, uLegRot.z, uLegLift.z);
  d += L.a * leg(q, uHip1.zw, uLegRot.w, uLegLift.w);
  return d;
}

void main() {
  vec2 sp = vec2(vUv.x * uStage.x, (1.0 - vUv.y) * uStage.y);
  if (uFlip > 0.5) sp.x = uStage.x - sp.x;
  vec2 p = (sp - uOrigin) / uK;
  vec2 q = p;
  for (int i = 0; i < 8; i++) q = p - D(q);
  vec4 base = tex(uPlate, q);
  vec2 e = q - uEyeC;
  vec4 eye = vec4(0.0);
  if (abs(e.x) < uEyeR.x + 8.0 && abs(e.y) < uEyeR.y + 8.0) {
    float nx = clamp(e.x / uEyeR.x, -1.0, 1.0);
    float lid = -uEyeR.y * 1.05 + uLid * (1.35 * uEyeR.y) + 2.0 * uLid * (1.0 - nx * nx);
    eye = tex(uEye, q) * smoothstep(lid - 0.8, lid + 0.8, e.y);
    float s = 0.08, pivot = 0.3 * uEyeR.y;
    vec4 shut = vec4(0.0);
    for (int k = 0; k < 5; k++) {
      float oy = (float(k) - 2.0) / 5.0;
      shut += tex(uEye, uEyeC + vec2(e.x, pivot + (e.y + oy - 2.5 * (1.0 - nx * nx) - pivot) / s));
    }
    eye = mix(eye, shut / 5.0, smoothstep(0.78, 0.97, uLid));
  }
  vec3 col = mix(base.rgb, eye.rgb, eye.a);
  gl_FragColor = vec4(col * base.a, base.a);
}`;

async function loadTex(url) {
  const t = await new THREE.TextureLoader().loadAsync(url);
  t.colorSpace = THREE.NoColorSpace;
  t.premultiplyAlpha = false;
  t.generateMipmaps = false;
  t.minFilter = t.magFilter = THREE.LinearFilter;
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  return t;
}

const V2 = (x = 0, y = 0) => new THREE.Vector2(x, y);
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const V4 = (a = 0, b = 0, c = 0, d = 0) => new THREE.Vector4(a, b, c, d);

export async function loadPet(base = './assets/derived/') {
  const layout = await (await fetch(base + 'layout.json')).json();
  const [plate, eyes, warp, masks, legs] = await Promise.all(
    ['plate.png', 'eyes.png', 'warp.png', 'front_masks.png', 'front_legs.png'].map((n) => loadTex(base + n)));
  const [W, H] = layout.size;
  const K = STAGE.K;
  const frontAnchor = { x: 260, y: layout.ground_y + 1 };   // bottom-centre of the paws
  const front = {
    uPlate: { value: plate }, uEyes: { value: eyes }, uWarp: { value: warp }, uMasks: { value: masks }, uLegs: { value: legs },
    uSize: { value: V2(W, H) }, uStage: { value: V2(STAGE.W, STAGE.H) }, uK: { value: K },
    uOrigin: { value: V2(STAGE.CX - frontAnchor.x * K, STAGE.GROUND - frontAnchor.y * K) },
    uAnchor: { value: V2(frontAnchor.x, frontAnchor.y) },
    uEyeC: { value: layout.eyes.map((e) => V2(e.cx + 0.5, e.cy + 0.5)) },
    uEyeR: { value: layout.eyes.map((e) => V2(e.rx, e.ry)) },
    uBreath: { value: 0 }, uBreathAmp: { value: V2(1.6, 1.3) },
    uLid: { value: V2() }, uGaze: { value: V2() }, uEyeSX: { value: V2(1, 1) }, uHead: { value: V3() }, uMuzzle: { value: V2() },
    uEarL: { value: V3() }, uEarR: { value: V3() }, uLegL: { value: V2() }, uLegR: { value: V2() },
    uSquash: { value: V2(1, 1) }, uTrans: { value: V2() },
  };
  const mat = (uniforms, fragmentShader) => new THREE.ShaderMaterial({
    uniforms, vertexShader: vert, fragmentShader, transparent: true, depthTest: false, depthWrite: false,
    premultipliedAlpha: true, blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  const quad = new THREE.PlaneGeometry(STAGE.W, STAGE.H);
  const frontMesh = new THREE.Mesh(quad, mat(front, frontFrag));
  frontMesh.position.set(STAGE.W / 2, STAGE.H / 2, 0);

  let side = null, sideMesh = null, sideLayout = null;
  try {
    sideLayout = await (await fetch(base + 'side_layout.json')).json();
    const [sp, se, sm, sm2] = await Promise.all(
      ['side_plate.png', 'side_eye.png', 'side_masks.png', 'side_masks2.png'].map((n) => loadTex(base + n)));
    const s = sideLayout;
    side = {
      uPlate: { value: sp }, uEye: { value: se }, uMasks: { value: sm }, uMasks2: { value: sm2 },
      uSize: { value: V2(...s.size) }, uStage: { value: V2(STAGE.W, STAGE.H) }, uK: { value: K },
      uOrigin: { value: V2(STAGE.CX - s.anchor[0] * K, STAGE.GROUND - s.anchor[1] * K) },
      uLegRot: { value: V4() }, uLegLift: { value: V4() }, uBody: { value: V2() }, uHead: { value: V3() },
      uEar: { value: V2() }, uTail: { value: 0 }, uLid: { value: 0 },
      uEyeC: { value: V2(...s.eye.c) }, uEyeR: { value: V2(...s.eye.r) },
      uHip0: { value: V4(...s.hips.nf, ...s.hips.ff) }, uHip1: { value: V4(...s.hips.nh, ...s.hips.fh) },
      uNeck: { value: V2(...s.neck) }, uEarRoot: { value: V2(...s.ear_root) }, uTailRoot: { value: V2(...s.tail_root) },
      uFlip: { value: 0 },
    };
    sideMesh = new THREE.Mesh(quad, mat(side, sideFrag));
    sideMesh.position.set(STAGE.W / 2, STAGE.H / 2, 0);
  } catch { /* side rig not built yet */ }

  const scene = new THREE.Scene();
  scene.add(frontMesh);
  if (sideMesh) scene.add(sideMesh);
  const camera = new THREE.OrthographicCamera(0, STAGE.W, STAGE.H, 0, -1, 1);

  /** Apply a pose object (see poses.js) to the uniforms. */
  function apply(pose) {
    const isSide = pose.rig === 'side';
    frontMesh.visible = !isSide;
    if (sideMesh) sideMesh.visible = isSide;
    if (isSide) {
      if (!side) throw new Error('side rig assets missing');
      const s = pose;
      side.uLegRot.value.set(...(s.legRot || [0, 0, 0, 0]));
      side.uLegLift.value.set(...(s.legLift || [0, 0, 0, 0]));
      side.uBody.value.set(...(s.body || [0, 0]));
      side.uHead.value.set(...(s.head || [0, 0, 0]));
      side.uEar.value.set(...(s.ear || [0, 0]));
      side.uTail.value = s.tail || 0;
      side.uLid.value = s.lid || 0;
      side.uFlip.value = s.flip ? 1 : 0;
      return;
    }
    const f = front, p = pose;
    f.uBreath.value = p.breath || 0;
    f.uBreathAmp.value.set(...(p.breathAmp || [1.6, 1.3]));
    f.uLid.value.set(...(p.lid || [0, 0]));
    f.uGaze.value.set(...(p.gaze || [0, 0]));
    f.uEyeSX.value.set(...(p.eyeSX || [1, 1]));
    f.uHead.value.set(...(p.head || [0, 0, 0]));
    f.uMuzzle.value.set(...(p.muzzle || [0, 0]));
    f.uEarL.value.set(...(p.earL || [0, 0, 0]));
    f.uEarR.value.set(...(p.earR || [0, 0, 0]));
    f.uLegL.value.set(...(p.legL || [0, 0]));
    f.uLegR.value.set(...(p.legR || [0, 0]));
    f.uSquash.value.set(...(p.squash || [1, 1]));
    f.uTrans.value.set(...(p.trans || [0, 0]));
  }

  function makeRenderer(canvas, opts = {}) {
    const r = new THREE.WebGLRenderer({ canvas, alpha: true, premultipliedAlpha: true, antialias: false,
      preserveDrawingBuffer: !!opts.preserveDrawingBuffer });
    r.setClearColor(0x000000, 0);
    r.outputColorSpace = THREE.LinearSRGBColorSpace;
    return r;
  }
  return { layout, sideLayout, hasSide: !!side, scene, camera, apply, makeRenderer };
}
