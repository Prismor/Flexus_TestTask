# -*- coding: utf-8 -*-
#  The gallery page template used by build_shadertoy.py. Kept in its own file
#  because it is a large chunk of HTML/JS and would otherwise bury the
#  generator logic.

# Per-effect copy shown on the cards: (subtitle, key parameters, UE cost).
# Instruction counts are base-pass numbers from the Unreal material editor
# stats panel, measured on the shipped material instances.
EFFECT_INFO = {
    "LVL1_Chameleon": ("Iridescent shell",
                       "ColorA/B/C · RoughnessA/B/C · FresnelPower · GradientShift",
                       "UE base pass: 332 instructions · 4 samplers"),
    "LVL2_Displacement": ("Animated Perlin relief",
                          "NoiseSize · NoiseSpeed · Octaves · Lacunarity · Persistence",
                          "UE base pass: 991 instructions · 3 samplers"),
    "LVL3_PaintedGel": ("Thick gel, paint stays",
                        "BrushRadius · BrushDepth · Raggedness · Smoothing",
                        "UE: sim 253 + display 316 instructions"),
    "LVL4_Water": ("Rings that travel outward",
                   "Viscosity 2.0 · Decay · VelocityMax · WaveTapUV",
                   "UE: sim 253 + display 316 instructions"),
    "LVL5_Boss": ("Noise, paint and iridescence",
                  "PaintAmplitude · ActivitySensitivity · TroughGlow · Sparkle",
                  "UE base pass: 1147 instructions · 4 samplers"),
    "LVL6_Vortex": ("Domain-warped whirlpool",
                    "SwirlStrength · SwirlTightness · WarpStrength · FunnelDepth",
                    "UE base pass: 2488 instructions · 4 samplers"),
    "LVL7_Rain": ("Drop rings on wet ground",
                  "DropRate · RingSpeed · DropDensity · WetPatchScale",
                  "UE base pass: 932 instructions · 3 samplers"),
    "LVL8_Lava": ("Crust, cobbles and molten veins",
                  "CrackThreshold · EmberAmount · StoneScale · VeinGlow",
                  "UE base pass: 3051 instructions · 3 samplers"),
}

VIEWER_HTML = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shader gallery</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&display=swap">

<style>
  /* Light palette on bare :root - cool neutrals biased toward the teal
     signal accent taken from the water and displacement shaders. */
  :root {
    --ground:  #eef2f3;
    --surface: #ffffff;
    --line:    #d9e2e4;
    --ink:     #101a1d;
    --muted:   #5c6d73;
    --accent:  #0e7c74;
    --accent-soft: rgba(14, 124, 116, .10);
    --shadow:  0 1px 2px rgba(16, 26, 29, .05), 0 8px 24px rgba(16, 26, 29, .05);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ground:  #0c1113;
      --surface: #141b1e;
      --line:    #222e32;
      --ink:     #e2eaec;
      --muted:   #84969c;
      --accent:  #4ecdc4;
      --accent-soft: rgba(78, 205, 196, .12);
      --shadow:  0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.32);
    }
  }
  :root[data-theme="dark"] {
    --ground:  #0c1113;
    --surface: #141b1e;
    --line:    #222e32;
    --ink:     #e2eaec;
    --muted:   #84969c;
    --accent:  #4ecdc4;
    --accent-soft: rgba(78, 205, 196, .12);
    --shadow:  0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.32);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 56px 24px 80px;
    background: var(--ground);
    color: var(--ink);
    font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 40px; }

  header { display: flex; flex-direction: column; gap: 14px; max-width: 60ch; }
  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--accent); margin: 0;
  }
  h1 {
    font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
    font-weight: 700; font-size: clamp(30px, 4.5vw, 44px); line-height: 1.1;
    letter-spacing: -.02em; margin: 0; text-wrap: balance;
  }
  header p { margin: 0; color: var(--muted); }
  header p code {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: .88em;
    background: var(--accent-soft); color: var(--accent);
    padding: 1px 6px; border-radius: 4px;
  }

  .grid { display: grid; gap: 22px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }

  .card {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 10px; overflow: hidden; box-shadow: var(--shadow);
    display: flex; flex-direction: column;
  }
  .card-head {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 12px; padding: 14px 16px 12px;
  }
  .card-head h2 {
    font-family: Archivo, ui-sans-serif, system-ui, sans-serif;
    font-size: 15px; font-weight: 600; margin: 0; letter-spacing: -.005em;
  }
  .card-head .sub { display: block; font-family: "IBM Plex Sans", sans-serif;
    font-weight: 400; font-size: 13px; color: var(--muted); }
  .tag {
    flex: none; font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase;
    padding: 3px 7px; border-radius: 999px;
    background: var(--accent-soft); color: var(--accent);
  }
  .tag.static { background: transparent; color: var(--muted); border: 1px solid var(--line); }

  canvas {
    touch-action: none;  /* a drag must paint, not scroll the page */
    width: 100%; aspect-ratio: 4 / 3; display: block;
    background: #05080a; border-block: 1px solid var(--line); cursor: crosshair;
  }
  canvas:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .card.static canvas { cursor: default; }

  .sliders { padding: 0 14px 12px; }
  .slider { margin-bottom: 9px; }
  .slider label { display:flex; justify-content:space-between; gap:8px;
    font-size:11.5px; color:#8b95a2; margin-bottom:4px; }
  .slider .sval { font-family:ui-monospace,monospace; color:#c3d3de; font-size:11px; }
  .slider input[type=range]{ width:100%; height:3px; -webkit-appearance:none;
    appearance:none; background:#2a313b; border-radius:2px; outline:none; }
  .slider input[type=range]::-webkit-slider-thumb{ -webkit-appearance:none;
    width:12px; height:12px; border-radius:50%; background:#7fb4d4; cursor:pointer; }
  .slider input[type=range]::-moz-range-thumb{ width:12px; height:12px; border:0;
    border-radius:50%; background:#7fb4d4; cursor:pointer; }
  .params {
    padding: 11px 16px 13px; font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11.5px; line-height: 1.55; color: var(--muted);
    font-variant-numeric: tabular-nums; word-break: break-word;
  }
  .params .stat { margin-top: 5px; color: var(--accent); font-size: 11px; }
  .err {
    padding: 12px 16px; font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11.5px; color: #d1495b; white-space: pre-wrap;
    border-top: 1px solid var(--line);
  }

  .code-toggle, .reset-btn {
    margin: 0 16px 13px; padding: 6px 10px; align-self: flex-start;
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px;
    letter-spacing: .04em; color: var(--muted); background: transparent;
    border: 1px solid var(--line); border-radius: 5px; cursor: pointer;
  }
  .code-toggle:hover, .reset-btn:hover { color: var(--ink); border-color: var(--accent); }
  .reset-btn { margin-bottom: 8px; }
  .codebox {
    display: none; margin: 0; padding: 14px 16px; max-height: 480px;
    overflow: auto; border-top: 1px solid var(--line);
    background: #05080a; color: #c3d3de;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px; line-height: 1.6; white-space: pre;
  }
  .card.code-open .codebox { display: block; }

  footer { color: var(--muted); font-size: 13.5px; max-width: 68ch; }
  footer code {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: .9em;
    background: var(--accent-soft); color: var(--accent);
    padding: 1px 6px; border-radius: 4px;
  }
</style>

<div class="wrap">
  <header>
    <h1>Shader gallery</h1>
  </header>

  <div class="grid" id="grid"></div>

  <footer>
    Levels 3&ndash;5 are a real ping-pong simulation &mdash; one buffer holds
    height, velocity and paint coverage, each frame reading the last. Drag to paint.
  </footer>
</div>

<script>
const EFFECTS = __EFFECT_DATA__;
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const VS = `#version 300 es
in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

function fsWrap(body, decls){
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
${decls || ''}
out vec4 _fragColor;
${body}
void main(){ vec4 c; mainImage(c, gl_FragCoord.xy); _fragColor = c; }`;
}

function compile(gl, type, src){
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh);
    gl.deleteShader(sh);
    throw new Error(log);
  }
  return sh;
}

function program(gl, fsSrc, decls){
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, VS));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fsWrap(fsSrc, decls)));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  return p;
}

function uniforms(gl, p){
  return {
    res:   gl.getUniformLocation(p, 'iResolution'),
    time:  gl.getUniformLocation(p, 'iTime'),
    dt:    gl.getUniformLocation(p, 'iTimeDelta'),
    frame: gl.getUniformLocation(p, 'iFrame'),
    mouse: gl.getUniformLocation(p, 'iMouse'),
    mousePrev: gl.getUniformLocation(p, 'iMousePrev'),
    chan:  gl.getUniformLocation(p, 'iChannel0'),
  };
}

function makeTarget(gl, w, h){
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const fbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  return {tex, fbo};
}

function showErr(card, msg){
  const d = document.createElement('div');
  d.className = 'err';
  d.textContent = msg;
  card.appendChild(d);
}

function boot(card, eff){
  const canvas = card.querySelector('canvas');
  const gl = canvas.getContext('webgl2', {antialias:false, alpha:false});
  if (!gl) { showErr(card, 'WebGL2 is unavailable in this browser.'); return; }
  if (eff.kind === 'sim' && !gl.getExtension('EXT_color_buffer_float')) {
    showErr(card, 'Float render targets are unavailable, so the simulation cannot run here.');
    return;
  }

  let imgProg, bufProg;
  try {
    imgProg = program(gl, eff.image, eff.decls);
    if (eff.buffer) bufProg = program(gl, eff.buffer, eff.decls);
  } catch (e) { showErr(card, e.message); return; }

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const vbo = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  // Live controls. Each slider drives a real uniform in BOTH passes - the
  // simulation buffer and the shading pass share the same constants, so a value
  // changed here has to reach both or they disagree mid-frame.
  const live = {};
  (eff.sliders || []).forEach(function(sp){
    live[sp.name] = {
      value: sp.value,
      img: gl.getUniformLocation(imgProg, sp.name),
      buf: bufProg ? gl.getUniformLocation(bufProg, sp.name) : null
    };
  });
  const sliderBox = card.querySelector('.sliders');
  (eff.sliders || []).forEach(function(sp){
    const row = document.createElement('div');
    row.className = 'slider';
    const lab = document.createElement('label');
    const nm = document.createElement('span'); nm.textContent = sp.label;
    const vv = document.createElement('span'); vv.className = 'sval';
    vv.textContent = (+sp.value).toFixed(3);
    lab.appendChild(nm); lab.appendChild(vv);
    const inp = document.createElement('input');
    inp.type = 'range'; inp.min = sp.min; inp.max = sp.max;
    inp.step = sp.step; inp.value = sp.value;
    inp.addEventListener('input', function(){
      live[sp.name].value = parseFloat(inp.value);
      vv.textContent = parseFloat(inp.value).toFixed(3);
    });
    row.appendChild(lab); row.appendChild(inp);
    sliderBox.appendChild(row);
  });
  function applyLive(which){
    for (const k in live) {
      const loc = live[k][which];
      if (loc) gl.uniform1f(loc, live[k].value);
    }
  }

  // Only render while the card is actually on screen. Eight shaders of this
  // weight running at once choke an integrated GPU - the page looked frozen on
  // weaker machines even though every shader had compiled fine.
  let visible = true;
  if ('IntersectionObserver' in window) {
    visible = false;
    new IntersectionObserver(function(entries){
      visible = entries[0].isIntersecting;
    }, {rootMargin: '80px'}).observe(canvas);
  }

  const uImg = uniforms(gl, imgProg);
  const uBuf = bufProg ? uniforms(gl, bufProg) : null;

  let W = 0, H = 0, targets = null, cur = 0, frame = 0;
  const mouse = {x:0, y:0, px:0, py:0, down:0};

  // LVL3's paint never decays by design ("stays forever"), so a long play
  // session just fills the canvas solid - frame 0 is the buffer shader's own
  // signal to treat the target as empty, so rewinding to it clears the paint
  // without touching the compiled programs or resizing anything.
  card.resetSim = function(){ frame = 0; };

  canvas.addEventListener('pointerdown', e => {
    mouse.down = 1;
    canvas.setPointerCapture(e.pointerId);
    move(e); mouse.px = mouse.x; mouse.py = mouse.y;
  });
  canvas.addEventListener('pointerup', () => { mouse.down = 0; });
  canvas.addEventListener('pointercancel', () => { mouse.down = 0; });
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

  let last = performance.now(), t0 = performance.now();

  function render(now){
    if (!card.isConnected) return;
    resize();
    const dt = Math.min((now - last) / 1000, 0.05); last = now;
    const time = (now - t0) / 1000;

    gl.bindVertexArray(vao);

    if (bufProg) {
      const src = targets[cur], dst = targets[1 - cur];
      gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fbo);
      gl.viewport(0, 0, W, H);
      gl.useProgram(bufProg);
      gl.uniform3f(uBuf.res, W, H, 1);
      gl.uniform1f(uBuf.time, time);
      gl.uniform1f(uBuf.dt, dt);
      gl.uniform1i(uBuf.frame, frame);
      gl.uniform4f(uBuf.mouse, mouse.x, mouse.y, mouse.down, 0);
      applyLive('buf');
      gl.uniform4f(uBuf.mousePrev, mouse.px, mouse.py, mouse.down, 0);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, src.tex);
      gl.uniform1i(uBuf.chan, 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      cur = 1 - cur;
      mouse.px = mouse.x; mouse.py = mouse.y;
    }

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.useProgram(imgProg);
    gl.uniform3f(uImg.res, W, H, 1);
    gl.uniform1f(uImg.time, time);
    gl.uniform1f(uImg.dt, dt);
    gl.uniform1i(uImg.frame, frame);
    gl.uniform4f(uImg.mouse, mouse.x, mouse.y, mouse.down, 0);
    gl.uniform4f(uImg.mousePrev, mouse.px, mouse.py, mouse.down, 0);
    applyLive('img');
    if (bufProg) {
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, targets[cur].tex);
      gl.uniform1i(uImg.chan, 0);
    }
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    frame++;
    // Reduced motion: draw a few frames so the panel is not blank, then hold.
    if (!visible) { setTimeout(() => requestAnimationFrame(render), 250); return; }
    if (REDUCED && frame > 3 && !mouse.down) { setTimeout(() => requestAnimationFrame(render), 400); return; }
    requestAnimationFrame(render);
  }
  requestAnimationFrame(render);
}

const grid = document.getElementById('grid');
for (const eff of EFFECTS) {
  const isSim = eff.kind === 'sim';
  const card = document.createElement('div');
  card.className = 'card' + (isSim ? '' : ' static');
  const level = eff.name.slice(0, 4);
  const title = eff.name.slice(5).replace(/([a-z])([A-Z])/g, '$1 $2');
  // Only LVL3's paint never decays ("stays forever" is the whole point of
  // that level) - LVL4/LVL5 already fade on their own, so a reset button
  // there would just be noise.
  const needsReset = level === 'LVL3';
  card.innerHTML =
    '<div class="card-head">' +
      '<h2>' + level + ' &middot; ' + title + '<span class="sub">' + eff.subtitle + '</span></h2>' +
      '<span class="tag' + (isSim ? '' : ' static') + '">' + (isSim ? 'Interactive' : 'Procedural') + '</span>' +
    '</div>' +
    '<canvas tabindex="0" aria-label="' + title + ' shader preview"></canvas>' +
    '<div class="params">' + eff.params +
      (eff.stat ? '<div class="stat">' + eff.stat + '</div>' : '') + '</div>' +
    '<div class="sliders"></div>' +
    (needsReset ? '<button type="button" class="reset-btn">Reset</button>' : '') +
    '<button type="button" class="code-toggle">Show GLSL</button>' +
    '<pre class="codebox"><code></code></pre>';
  grid.appendChild(card);
  boot(card, eff);

  if (needsReset) {
    card.querySelector('.reset-btn').addEventListener('click', function(){
      card.resetSim();
    });
  }

  // Code is the same GLSL that just got compiled above - set once, on first
  // open, instead of bloating every card's HTML with it up front.
  const btn = card.querySelector('.code-toggle');
  const box = card.querySelector('.codebox code');
  let codeLoaded = false;
  btn.addEventListener('click', function(){
    const open = card.classList.toggle('code-open');
    btn.textContent = open ? 'Hide GLSL' : 'Show GLSL';
    if (open && !codeLoaded) {
      box.textContent = eff.display;
      codeLoaded = true;
    }
  });
}
</script>
"""
