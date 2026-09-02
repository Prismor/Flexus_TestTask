# -*- coding: utf-8 -*-
#  Page template for build_portfolio.py. Kept separate so the generator stays
#  readable. English copy: this page is meant for an international portfolio.

# key -> (title, one-line summary, [technique bullets])
COPY = {
    "LVL1_Chameleon": (
        "Chameleon",
        "View-angle iridescence with per-band roughness and a Fresnel-weighted reflection.",
        ["A three-stop colour ramp driven purely by <code>dot(N, V)</code> — a cheap stand-in for thin-film interference.",
         "Roughness is banded on the same curve as colour, so every colour zone gets its own finish.",
         "A Schlick-style Fresnel term keeps reflections at grazing angles, where they belong.",
         "<code>GradientShift</code> re-weights how much of the surface each colour band covers."]),

    "LVL2_Displacement": (
        "Perlin displacement",
        "Animated fractal noise lifts the plane, and the normal is rebuilt so lighting follows the new shape.",
        ["Hand-rolled value / Perlin / ridged FBM — noise type, seed and octave count are real instance parameters, which the engine's built-in noise node cannot expose.",
         "Time drives the third noise axis, so the field morphs instead of merely scrolling past.",
         "Central differences rebuild the normal after World Position Offset; without it the engine keeps lighting the flat original surface.",
         "Surface colour is mapped from height rather than from a texture."]),

    "LVL3_Paint": (
        "Render-target painting",
        "Interactive painting into a ping-pong buffer holding height, velocity and paint coverage.",
        ["Exactly one render-target switch per frame, as the brief requires.",
         "The brush stamps a capsule along the cursor's path between frames, so a fast stroke paints a continuous line instead of a chain of circles.",
         "Brush depth is a <em>rate</em> scaled by delta time, so pressure builds up in layers and feels the same at any framerate.",
         "A knee-compressed limiter replaces a hard clamp: below the knee height passes through untouched, so nothing decays that should not."]),

    "LVL4_Waves": (
        "Damped travelling waves",
        "The same simulation with viscosity raised: a dent becomes rings that travel outward and ring down.",
        ["The restoring force is the laplacian — neighbour average minus self — which is what makes disturbances <em>propagate</em> rather than bob in place.",
         "The velocity channel gives the surface inertia, so crests overshoot past rest instead of only sinking.",
         "The stability ceiling was measured, not guessed: at 2.0 the field loses about 99% of its energy over 500 frames; at 2.5 it gains energy and never settles.",
         "Tap distance is expressed in UV rather than texels, so the simulation behaves identically at any buffer resolution."]),

    "LVL5_Boss": (
        "Boss — everything combined",
        "Procedural and painted displacement summed per tap, shaded as iridescent fluid over a dark idle base.",
        ["Heights are combined per tap and the normal rebuilt once, so the two effects merge into a single surface instead of two stacked ones.",
         "Coverage is read from the wetness channel rather than <code>|height|</code>, which removes the uncoloured bands that appear wherever height crosses zero.",
         "An emissive core glows inside the stroke, with a noise-dithered tint exactly on its boundary.",
         "Procedural glitter appears only where the fluid is active — sparkle without a particle system."]),

    "LVL6_Vortex": (
        "Vortex",
        "A whirlpool built from a rotated, domain-warped noise field and a smooth funnel.",
        ["The sampling domain is rotated by an angle that grows toward the centre, winding the noise into a spiral.",
         "Domain warping — <code>fbm(p + fbm(p))</code> — bends the plate boundaries into organic tendrils.",
         "Noise is faded out near the core, where the rotation would otherwise stretch the lattice into visible repeated streaks.",
         "The material is two-sided: steep funnel walls flip triangles on a coarse grid, which would otherwise render as black facets."]),

    "LVL7_Rain": (
        "Rain ripples",
        "Drop rings on wet ground, over a real PBR texture set.",
        ["Three offset grids of cells; each cell spawns one drop with its own position, phase, size and speed.",
         "A border fade forces every ring to zero before its cell edge, which is what removes the visible tiling.",
         "A slow large-scale mask darkens wet patches and drops their roughness — the streaks rain leaves behind.",
         "Ground albedo, normal and roughness come from an assigned texture set, so the surface reads as a material rather than a flat picture."]),

    "LVL8_Lava": (
        "Lava",
        "Ridged plates whose deep valleys run molten, with cobbles and thin glowing veins on the crust.",
        ["Ridged FBM mirrors each octave around zero to create sharp creases; the resulting valleys become the rivers.",
         "Voronoi cobblestones and thin grooves are masked to the cool crust only, so the rivers stay smooth and liquid.",
         "A four-stop heat gradient drives colour and emissive together, so the glow is always the colour of the surface beneath it.",
         "Slow drifting ember noise keeps even cold plates smouldering — without it the crust reads as plain grey rock."]),
}

PORTFOLIO_HTML = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LiquidSim</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&display=swap">

<style>
  /* ---- Tokens. Light palette on bare :root, redefined for both dark paths.
     Cool neutrals biased toward the teal signal accent of the water shader. */
  :root {
    --ground:  #eef2f3;
    --surface: #ffffff;
    --code-bg: #f5f8f8;
    --line:    #d9e2e4;
    --ink:     #101a1d;
    --muted:   #5c6d73;
    --accent:  #0e7c74;
    --accent-soft: rgba(14, 124, 116, .10);
    --kw:      #9a3d8f;
    --typ:     #0e7c74;
    --num:     #b45309;
    --com:     #7c8b91;
    --shadow:  0 1px 2px rgba(16,26,29,.05), 0 10px 28px rgba(16,26,29,.06);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground:  #0c1113;
      --surface: #141b1e;
      --code-bg: #0f1618;
      --line:    #222e32;
      --ink:     #e2eaec;
      --muted:   #84969c;
      --accent:  #4ecdc4;
      --accent-soft: rgba(78,205,196,.12);
      --kw:      #e39ddb;
      --typ:     #4ecdc4;
      --num:     #f0b072;
      --com:     #6b7c82;
      --shadow:  0 1px 2px rgba(0,0,0,.4), 0 12px 32px rgba(0,0,0,.34);
    }
  }
  :root[data-theme="dark"] {
    --ground:  #0c1113;
    --surface: #141b1e;
    --code-bg: #0f1618;
    --line:    #222e32;
    --ink:     #e2eaec;
    --muted:   #84969c;
    --accent:  #4ecdc4;
    --accent-soft: rgba(78,205,196,.12);
    --kw:      #e39ddb;
    --typ:     #4ecdc4;
    --num:     #f0b072;
    --com:     #6b7c82;
    --shadow:  0 1px 2px rgba(0,0,0,.4), 0 12px 32px rgba(0,0,0,.34);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 60px 24px 96px;
    background: var(--ground); color: var(--ink);
    font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
    font-size: 15.5px; line-height: 1.68; -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1140px; margin: 0 auto; display: flex; flex-direction: column; gap: 56px; }

  /* ---- header ---- */
  .lede { display: flex; flex-direction: column; gap: 16px; max-width: 62ch; }
  .eyebrow {
    margin: 0; font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12px; letter-spacing: .13em; text-transform: uppercase; color: var(--accent);
  }
  h1 {
    margin: 0; font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
    font-weight: 700; font-size: clamp(32px, 5vw, 48px); line-height: 1.08;
    letter-spacing: -.022em; text-wrap: balance;
  }
  .lede p { margin: 0; color: var(--muted); }
  .lede code, .note code {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: .88em;
    background: var(--accent-soft); color: var(--accent); padding: 1px 6px; border-radius: 4px;
  }
  .facts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
  .fact {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11.5px;
    letter-spacing: .04em; padding: 5px 10px; border-radius: 999px;
    border: 1px solid var(--line); color: var(--muted);
    font-variant-numeric: tabular-nums;
  }

  /* ---- one effect ---- */
  .effect {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; overflow: hidden; box-shadow: var(--shadow);
  }
  .effect-top { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); }
  @media (max-width: 860px) { .effect-top { grid-template-columns: 1fr; } }

  .preview { position: relative; background: #05080a; border-right: 1px solid var(--line); }
  @media (max-width: 860px) { .preview { border-right: none; border-bottom: 1px solid var(--line); } }
  canvas {
    touch-action: none;  /* a drag must paint, not scroll the page */ width: 100%; aspect-ratio: 4 / 3; display: block; cursor: crosshair; }
  .effect.static canvas { cursor: default; }
  canvas:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .badge {
    position: absolute; left: 12px; top: 12px;
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10.5px;
    letter-spacing: .08em; text-transform: uppercase; padding: 4px 8px; border-radius: 999px;
    background: rgba(0,0,0,.55); color: #d8f5f2; backdrop-filter: blur(4px);
  }

  .about { padding: 22px 26px 24px; display: flex; flex-direction: column; gap: 14px; }
  .about h2 {
    margin: 0; font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
    font-size: 21px; font-weight: 600; letter-spacing: -.012em; text-wrap: balance;
  }
  .about .level {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11.5px;
    letter-spacing: .1em; color: var(--accent); text-transform: uppercase;
    display: block; margin-bottom: 5px;
  }
  .about .summary { margin: 0; color: var(--muted); }
  .about ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 8px; }
  .about li { padding-left: 2px; }
  .about li::marker { color: var(--accent); }
  .about code {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: .87em;
    background: var(--accent-soft); color: var(--accent); padding: 1px 5px; border-radius: 4px;
  }

  /* ---- code ---- */
  .code-head {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 11px 16px 11px 26px; border-top: 1px solid var(--line);
    background: var(--code-bg);
  }
  .code-head .path {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12px; color: var(--muted);
  }
  .code-actions { display: flex; gap: 8px; }
  button {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11.5px;
    letter-spacing: .04em; padding: 5px 11px; border-radius: 6px; cursor: pointer;
    border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  }
  button:hover { border-color: var(--accent); color: var(--accent); }
  button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  pre {
    margin: 0; padding: 18px 26px 24px; background: var(--code-bg);
    overflow-x: auto; max-height: 30em; overflow-y: auto;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12.5px; line-height: 1.62; tab-size: 4;
  }
  pre.collapsed { max-height: 16em; }
  code.hl .kw  { color: var(--kw); }
  code.hl .typ { color: var(--typ); }
  code.hl .num { color: var(--num); }
  code.hl .com { color: var(--com); font-style: italic; }

  .note {
    color: var(--muted); font-size: 13.5px; max-width: 70ch;
    border-top: 1px solid var(--line); padding-top: 20px;
  }
  @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
</style>

<div class="wrap">
  <header class="lede">
    <p class="eyebrow">Real-time fluid-simulation shaders</p>
    <h1>Eight effects built on one portable core</h1>
    <p>
      A simplified liquid-simulation suite: iridescent shading, animated noise
      displacement, and an interactive render-target simulation where painted
      dents turn into travelling waves. Every effect below runs live in this
      page &mdash; the same maths that drives the Unreal materials, compiled
      here as GLSL.
    </p>
    <p>
      The library (<code>LiquidSimCore.ush</code>) contains no engine calls at
      all: no texture objects, no engine types. That is what lets the identical
      HLSL compile in Unreal and Unity, and reach the browser through a
      six-line compatibility prelude. The engine-specific parts &mdash; texture
      sampling, material pins, mouse input &mdash; live in thin wrappers around it.
    </p>
    <div class="facts">
      <span class="fact">HLSL &middot; GLSL &middot; Unreal 5.8</span>
      <span class="fact">8 effects</span>
      <span class="fact">0 compile errors</span>
      <span class="fact">no geometry or compute shaders</span>
    </div>
  </header>

  <main id="effects"></main>

  <p class="note">
    Levels 3&ndash;5 are a genuine ping-pong simulation: one buffer holds height,
    velocity and paint coverage, and each frame is drawn from the previous one.
    Drag across those panels to paint into them.
  </p>
</div>

<script>
const EFFECTS = __EFFECT_DATA__;
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------- tiny HLSL highlighter: comments, types, keywords, numbers ---- */
const TYPES = /\b(float|float2|float3|float4|int|bool|void|struct|Texture2D|TextureCube|SamplerState|LS_\w+)\b/g;
const KEYWORDS = /\b(return|if|else|for|while|break|continue|out|inout|const|in)\b/g;

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function highlight(src){
  const parts = [];
  // split comments out first so keywords inside them are not coloured
  const re = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g;
  let last = 0, m;
  while ((m = re.exec(src)) !== null) {
    parts.push({t: 'code', s: src.slice(last, m.index)});
    parts.push({t: 'com',  s: m[0]});
    last = m.index + m[0].length;
  }
  parts.push({t: 'code', s: src.slice(last)});

  return parts.map(p => {
    if (p.t === 'com') return '<span class="com">' + esc(p.s) + '</span>';
    let h = esc(p.s);
    h = h.replace(TYPES, '<span class="typ">$1</span>');
    h = h.replace(KEYWORDS, '<span class="kw">$1</span>');
    h = h.replace(/\b(\d+\.?\d*(?:e-?\d+)?)\b/g, '<span class="num">$1</span>');
    return h;
  }).join('');
}

/* ---------- WebGL preview ------------------------------------------------ */
const VS = `#version 300 es
in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

function fsWrap(body){
  return `#version 300 es
precision highp float;
precision highp sampler2D;
uniform vec3  iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int   iFrame;
uniform vec4  iMouse;
uniform vec4  iMousePrev;
uniform sampler2D iChannel0;
out vec4 _fragColor;
${body}
void main(){ vec4 c; mainImage(c, gl_FragCoord.xy); _fragColor = c; }`;
}

function compile(gl, type, src){
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src); gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh); gl.deleteShader(sh); throw new Error(log);
  }
  return sh;
}
function program(gl, fsSrc){
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VS));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fsWrap(fsSrc)));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}
function uniforms(gl, p){
  const n = ['iResolution','iTime','iTimeDelta','iFrame','iMouse','iMousePrev','iChannel0'];
  const o = {};
  for (const k of n) o[k] = gl.getUniformLocation(p, k);
  return o;
}
function makeTarget(gl, w, h){
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
  for (const [k,v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR],[gl.TEXTURE_MAG_FILTER, gl.LINEAR],
                       [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE],[gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]])
    gl.texParameteri(gl.TEXTURE_2D, k, v);
  const fbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  return {tex, fbo};
}

function boot(canvas, eff){
  const gl = canvas.getContext('webgl2', {antialias:false, alpha:false});
  if (!gl) return;
  if (eff.kind === 'sim' && !gl.getExtension('EXT_color_buffer_float')) return;

  let imgProg, bufProg;
  try {
    imgProg = program(gl, eff.image);
    if (eff.buffer) bufProg = program(gl, eff.buffer);
  } catch (e) { console.error(eff.name, e.message); return; }

  const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
  const vbo = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  const uI = uniforms(gl, imgProg);
  const uB = bufProg ? uniforms(gl, bufProg) : null;

  let W = 0, H = 0, targets = null, cur = 0, frame = 0;
  const mouse = {x:0, y:0, px:0, py:0, down:0};

  canvas.addEventListener('pointerdown', e => {
    mouse.down = 1; canvas.setPointerCapture(e.pointerId);
    move(e); mouse.px = mouse.x; mouse.py = mouse.y;
  });
  canvas.addEventListener('pointerup',     () => mouse.down = 0);
  canvas.addEventListener('pointercancel', () => mouse.down = 0);
  canvas.addEventListener('pointermove', move);
  function move(e){
    const r = canvas.getBoundingClientRect();
    mouse.x = (e.clientX - r.left) / r.width * W;
    mouse.y = (1 - (e.clientY - r.top) / r.height) * H;
  }

  function resize(){
    const r = canvas.getBoundingClientRect();
    const w = Math.max(2, Math.floor(r.width * 0.8));
    const h = Math.max(2, Math.floor(w * 3 / 4));
    if (w === W && h === H) return;
    W = w; H = h; canvas.width = W; canvas.height = H;
    if (bufProg) { targets = [makeTarget(gl, W, H), makeTarget(gl, W, H)]; frame = 0; }
  }

  let last = performance.now(), t0 = performance.now(), visible = true;
  new IntersectionObserver(es => { visible = es[0].isIntersecting; },
                           {rootMargin: '200px'}).observe(canvas);

  function draw(prog, u, dt, time){
    gl.uniform3f(u.iResolution, W, H, 1);
    gl.uniform1f(u.iTime, time);
    gl.uniform1f(u.iTimeDelta, dt);
    gl.uniform1i(u.iFrame, frame);
    gl.uniform4f(u.iMouse, mouse.x, mouse.y, mouse.down, 0);
    gl.uniform4f(u.iMousePrev, mouse.px, mouse.py, mouse.down, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function render(now){
    if (!canvas.isConnected) return;
    if (!visible) { requestAnimationFrame(render); return; }
    resize();
    const dt = Math.min((now - last) / 1000, 0.05); last = now;
    const time = (now - t0) / 1000;
    gl.bindVertexArray(vao);

    if (bufProg) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets[1 - cur].fbo);
      gl.viewport(0, 0, W, H); gl.useProgram(bufProg);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, targets[cur].tex);
      gl.uniform1i(uB.iChannel0, 0);
      draw(bufProg, uB, dt, time);
      cur = 1 - cur; mouse.px = mouse.x; mouse.py = mouse.y;
    }

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H); gl.useProgram(imgProg);
    if (bufProg) {
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, targets[cur].tex);
      gl.uniform1i(uI.iChannel0, 0);
    }
    draw(imgProg, uI, dt, time);

    frame++;
    if (REDUCED && frame > 3 && !mouse.down) { setTimeout(() => requestAnimationFrame(render), 400); return; }
    requestAnimationFrame(render);
  }
  requestAnimationFrame(render);
}

/* ---------- build the page ---------------------------------------------- */
const host = document.getElementById('effects');
const wrapEl = document.querySelector('.wrap');

EFFECTS.forEach((eff, i) => {
  const isSim = eff.kind === 'sim';
  const sec = document.createElement('section');
  sec.className = 'effect' + (isSim ? '' : ' static');
  sec.id = eff.name.toLowerCase();

  sec.innerHTML =
    '<div class="effect-top">' +
      '<div class="preview">' +
        '<span class="badge">' + (isSim ? 'Interactive &mdash; drag to paint' : 'Procedural') + '</span>' +
        '<canvas tabindex="0" aria-label="' + eff.title + ' preview"></canvas>' +
      '</div>' +
      '<div class="about">' +
        '<h2><span class="level">' + eff.level + '</span>' + eff.title + '</h2>' +
        '<p class="summary">' + eff.summary + '</p>' +
        '<ul>' + eff.bullets.map(b => '<li>' + b + '</li>').join('') + '</ul>' +
      '</div>' +
    '</div>' +
    '<div class="code-head">' +
      '<span class="path">' + eff.path + '</span>' +
      '<span class="code-actions">' +
        '<button type="button" data-act="expand">Expand</button>' +
        '<button type="button" data-act="copy">Copy</button>' +
      '</span>' +
    '</div>' +
    '<pre class="collapsed"><code class="hl">' + highlight(eff.code) + '</code></pre>';

  host.appendChild(sec);
  boot(sec.querySelector('canvas'), eff);

  const pre = sec.querySelector('pre');
  sec.querySelector('[data-act="expand"]').addEventListener('click', e => {
    const open = pre.classList.toggle('collapsed');
    e.target.textContent = open ? 'Expand' : 'Collapse';
  });
  sec.querySelector('[data-act="copy"]').addEventListener('click', e => {
    navigator.clipboard.writeText(eff.code).then(() => {
      e.target.textContent = 'Copied';
      setTimeout(() => e.target.textContent = 'Copy', 1400);
    });
  });
});

// spacing between sections comes from the flex gap of .wrap
host.style.display = 'flex';
host.style.flexDirection = 'column';
host.style.gap = '32px';
</script>
"""
