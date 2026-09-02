# =============================================================================
#  build_shadertoy.py
#
#  Generates the GLSL / Shadertoy ports of every LiquidSim effect from the
#  SINGLE source of truth: Shaders/LiquidSimCore.ush. The core is pure math
#  with no engine API, so porting it is a mechanical text transform:
#  prepend a compatibility prelude that maps HLSL spellings onto GLSL ones.
#  Nothing about the maths is rewritten or duplicated - if the core changes,
#  re-running this script updates every port.
#
#  Outputs:
#    Shaders/Shadertoy/<Level>.glsl   - paste into shadertoy.com
#    Shaders/Shadertoy/viewer.html    - runs every effect live, no site needed
#
#  Run:  python Python/docs/build_shadertoy.py
#
#  Author: Max Okhrimenko
# =============================================================================

import os

from _viewer_template import EFFECT_INFO, VIEWER_HTML
from _core_deps import pruned_core, strip_comment_blocks

# Three levels up: this file sits in Python/<group>/, so the project root is
# two directories above the script's own folder.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE_PATH = os.path.join(ROOT, "Shaders", "LiquidSimCore.ush")
OUT_DIR = os.path.join(ROOT, "Shaders", "Shadertoy")

# Same idea as build_clean_shaders.py: each port gets only the core functions
# it actually calls, not the whole library. Lists match the entry points in
# build_clean_shaders.py's EFFECTS (the paint family shares one call graph -
# LVL3/4/5 differ only in which LS_Shade* they call).
ENTRY_SYMBOLS = {
    "LVL1_Chameleon":   ["LS_Surface", "LS_ShadeChameleon"],
    "LVL2_Displacement": ["LS_Surface", "LS_NoiseParams", "LS_HeightPerlin",
                          "LS_SurfaceFromHeights", "LS_HeightRamp"],
    "LVL3_PaintedGel":  ["LS_BrushParams", "LS_SimParams", "LS_WaveTapDistance",
                         "LS_PaintStep", "LS_Surface", "LS_SurfaceFromHeights",
                         "LS_HeightRamp", "LS_ShadePainted"],
    "LVL4_Water":       ["LS_BrushParams", "LS_SimParams", "LS_WaveTapDistance",
                         "LS_PaintStep", "LS_Surface", "LS_SurfaceFromHeights",
                         "LS_HeightRamp", "LS_ShadePainted"],
    "LVL5_Boss":        ["LS_Surface", "LS_NoiseParams", "LS_HeightPerlin",
                         "LS_SurfaceFromHeights", "LS_BossDisplace",
                         "LS_Iridescent", "LS_Sparkle", "LS_ShadeBoss",
                         "LS_BrushParams", "LS_SimParams", "LS_WaveTapDistance",
                         "LS_PaintStep"],
    "LVL6_Vortex":      ["LS_Surface", "LS_NoiseParams", "LS_HeightVortex",
                         "LS_SurfaceFromHeights", "LS_Sparkle",
                         "LS_ShadeVortex"],
    "LVL7_Rain":        ["LS_Surface", "LS_NoiseParams", "LS_HeightRain",
                         "LS_SurfaceFromHeights", "LS_WetPatchMask",
                         "LS_ShadeRain", "LS_ValueNoise"],
    "LVL8_Lava":        ["LS_Surface", "LS_NoiseParams", "LS_Voronoi",
                         "LS_HeightLava", "LS_LavaHeat", "LS_SurfaceFromHeights",
                         "LS_ShadeLava"],
}

# -----------------------------------------------------------------------------
#  HLSL -> GLSL compatibility prelude.
#  These are the ONLY differences between the two languages that the core
#  actually uses - which is why the core is written the way it is.
# -----------------------------------------------------------------------------
PRELUDE = """// HLSL -> GLSL compatibility shim.
#define float2 vec2
#define float3 vec3
#define float4 vec4
#define lerp  mix
#define frac  fract
#define atan2 atan
#define saturate(x) clamp((x), 0.0, 1.0)
"""


def load_core():
    """Read the core library and strip the HLSL-only pragma."""
    with open(CORE_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    return text.replace("#pragma once", "").strip()


# -----------------------------------------------------------------------------
#  Shared demo scaffolding: turns a height field into a lit image so each
#  effect can be judged on its own. This is presentation only - none of it is
#  part of the library.
# -----------------------------------------------------------------------------
HEIGHTFIELD_MAIN = """
// ---------------------------------------------------------------- demo ----
// Lights the height field: central differences -> normal -> diffuse +
// specular + emissive, then a filmic-ish tonemap so HDR glow rolls off.
void mainImage(out vec4 fragColor, in vec2 fragCoord)
{
    vec2 uv = fragCoord / iResolution.xy;
    float t = iTime;

    float tap = 0.004;
    float hC = LSDemo_Height(uv, t);
    float hU = LSDemo_Height(uv + vec2(tap, 0.0), t);
    float hV = LSDemo_Height(uv + vec2(0.0, tap), t);

    vec3 N = normalize(vec3((hC - hU) * LSDEMO_RELIEF / tap,
                            (hC - hV) * LSDEMO_RELIEF / tap, 1.0));

    vec3 base, emissive;
    float rough;
    LSDemo_Shade(uv, t, N, hC, base, emissive, rough);

    vec3 L = normalize(vec3(0.45, 0.55, 0.70));
    vec3 V = vec3(0.0, 0.0, 1.0);
    float diffuse = max(dot(N, L), 0.0);
    float shininess = mix(8.0, 128.0, 1.0 - clamp(rough, 0.0, 1.0));
    float specular = pow(max(dot(reflect(-L, N), V), 0.0), shininess);

    vec3 col = base * (0.25 + 0.75 * diffuse)
             + vec3(1.0) * specular * (1.0 - rough)
             + emissive;

    col = col / (1.0 + col);
    col = pow(col, vec3(1.0 / 2.2));
    fragColor = vec4(col, 1.0);
}
"""

# -----------------------------------------------------------------------------
#  Per-effect blocks. Each defines its parameters (the same names that are
#  material-instance parameters in Unreal), a height function and a shading
#  function. Everything they call lives in the core above them.
# -----------------------------------------------------------------------------

EFFECT_DISPLACEMENT = """
// ============================ LVL 2 - Perlin displacement ==================
// Instance parameters: NoiseSize, NoiseSpeed, Amplitude, NoiseSeed,
// NoiseType, NoiseOctaves, Lacunarity, Persistence, ColorLow/Mid/High.
#define LSDEMO_RELIEF 0.25
#define LSDEMO_NOISE_SIZE 5.0
#define LSDEMO_NOISE_SPEED 0.16
#define LSDEMO_OCTAVES 3.0
#define LSDEMO_PERSISTENCE 0.45

LS_NoiseParams LSDemo_Noise()
{
    LS_NoiseParams np;
    np.Size = LSDEMO_NOISE_SIZE;
    np.Speed = LSDEMO_NOISE_SPEED;
    np.Seed = 0.0;
    np.Type = 1.0;          // 0 value / 1 Perlin / 2 ridged
    np.Octaves = LSDEMO_OCTAVES;
    np.Lacunarity = 2.0;
    np.Persistence = LSDEMO_PERSISTENCE;
    return np;
}

float LSDemo_Height(vec2 uv, float t)
{
    return LS_HeightPerlin(uv, t, LSDemo_Noise());
}

void LSDemo_Shade(vec2 uv, float t, vec3 N, float h,
                  out vec3 base, out vec3 emissive, out float rough)
{
    base = LS_HeightRamp(saturate(h * 0.5 + 0.5),
                         vec3(0.08, 0.20, 0.80),   // ColorLow  - deep blue
                         vec3(0.06, 0.45, 0.42),   // ColorMid  - teal
                         vec3(0.22, 0.85, 0.28));  // ColorHigh - green crests
    emissive = vec3(0.0);
    rough = 0.22;
}
"""

EFFECT_VORTEX = """
// ================================ LVL 6 - Vortex ===========================
// Instance parameters: SwirlStrength/Tightness/Speed, WarpStrength,
// FunnelDepth/Tightness, ColorA/B/C, CoreColor/Glow/Tightness, Pulse*,
// BandArms/Twist/NoiseScale/NoiseAmount/Contrast, Line* (the colour bands'
// own copy of the noise/swirl params - see LS_ShadeVortex in the guide).
//
// SwirlStrength drives BOTH the funnel rotation (geometry) and the colour
// line rotation (shading) below - one slider, so the two never drift apart.
#define LSDEMO_RELIEF 0.30
#define LSDEMO_SWIRL_STRENGTH 5.5
#define LSDEMO_SWIRL_SPEED 0.4
#define LSDEMO_FUNNEL_DEPTH 0.9
#define LSDEMO_BAND_ARMS 3.0
#define LSDEMO_BAND_TWIST 34.0

LS_NoiseParams LSDemo_Noise()
{
    LS_NoiseParams np;
    np.Size = 4.0;
    np.Speed = 0.6;
    np.Seed = 3.0;
    np.Type = 2.0;          // ridged - torn creased folds
    np.Octaves = 4.0;
    np.Lacunarity = 2.0;
    np.Persistence = 0.5;
    return np;
}

float LSDemo_Height(vec2 uv, float t)
{
    return LS_HeightVortex(uv, t, LSDemo_Noise(),
                           LSDEMO_SWIRL_STRENGTH,
                           4.0,   // SwirlTightness
                           LSDEMO_SWIRL_SPEED,
                           1.5,   // WarpStrength
                           LSDEMO_FUNNEL_DEPTH,
                           10.0); // FunnelTightness
}

void LSDemo_Shade(vec2 uv, float t, vec3 N, float h,
                  out vec3 base, out vec3 emissive, out float rough)
{
    vec3 V = vec3(0.0, 0.0, 1.0);
    LS_NoiseParams lineNp;
    lineNp.Size = 3.0; lineNp.Speed = 0.25; lineNp.Seed = 5.0;
    lineNp.Type = 2.0; lineNp.Octaves = 3.0;
    lineNp.Lacunarity = 2.0; lineNp.Persistence = 0.5;
    LS_Surface s = LS_ShadeVortex(N, V, uv, t, length(uv - 0.5),
        vec3(0.55, 0.05, 0.65),   // ColorA - grazing violet
        vec3(0.10, 0.15, 0.60),   // ColorB - deep blue
        vec3(0.10, 0.90, 0.90),   // ColorC - facing aqua
        vec3(0.60, 1.60, 2.00),   // CoreColor (HDR)
        vec3(1.0),                // FoamColor
        2.0, 110.0, 2.0, 0.35,    // CoreGlow, CoreTightness, Pulse*
        0.25, 0.06,               // roughness idle / active
        260.0, 0.3,               // sparkle scale / intensity
        LSDEMO_BAND_ARMS, LSDEMO_BAND_TWIST,
        42.0,                     // BandNoiseScale
        0.22, 1.9,                // band noise amount / contrast
        lineNp, LSDEMO_SWIRL_STRENGTH,
        4.0,                      // LineSwirlTightness - matches geometry's SwirlTightness above
        LSDEMO_SWIRL_SPEED);       // matches geometry's SwirlSpeed above
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

EFFECT_RAIN = """
// ================================= LVL 7 - Rain ============================
// Instance parameters: DropRate, RingSpeed, RingWidth, RingFrequency,
// DropDensity, SizeVariation, WetPatchScale/Contrast, WetDarkening.
// In the engine the ground albedo is a real PBR texture set; here it is a
// procedural stand-in so the file needs no assets.
#define LSDEMO_RELIEF 0.6
#define LSDEMO_DROP_RATE 0.9
#define LSDEMO_RING_SPEED 0.32
#define LSDEMO_DROP_DENSITY 0.75
#define LSDEMO_WET_SCALE 3.5

float LSDemo_Height(vec2 uv, float t)
{
    return LS_HeightRain(uv, t,
                         LSDEMO_DROP_RATE,
                         LSDEMO_RING_SPEED,
                         0.06,  // RingWidth
                         55.0,  // RingFrequency
                         LSDEMO_DROP_DENSITY,
                         0.7);  // SizeVariation
}

void LSDemo_Shade(vec2 uv, float t, vec3 N, float h,
                  out vec3 base, out vec3 emissive, out float rough)
{
    LS_NoiseParams np;
    np.Size = 1.0; np.Speed = 1.0; np.Seed = 4.0;
    np.Type = 1.0; np.Octaves = 3.0; np.Lacunarity = 2.0; np.Persistence = 0.5;

    float wet = LS_WetPatchMask(uv, t, np, LSDEMO_WET_SCALE, 1.2);

    // stand-in for the asphalt texture: fine speckle + coarse blotches
    float grain = LS_ValueNoise(vec3(uv * 260.0, 0.0)) * 0.5 + 0.5;
    float blotch = LS_ValueNoise(vec3(uv * 14.0, 5.0)) * 0.5 + 0.5;
    vec3 ground = vec3(0.10, 0.105, 0.11) * (0.75 + 0.5 * grain) * (0.85 + 0.3 * blotch);

    LS_Surface s = LS_ShadeRain(N, h, ground,
        0.55,   // GroundRoughness
        wet,
        0.45,   // WetDarkening
        0.55,   // RoughnessDry
        0.05);  // RoughnessWet
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

EFFECT_LAVA = """
// ================================= LVL 8 - Lava ============================
// Instance parameters: NoiseSize/Speed/Seed/Octaves, WarpStrength,
// CrackThreshold, CrackSharpness, GlowStrength, EmberScale/Speed/Amount,
// StoneScale, StoneAmount, ThinCrackScale, ThinCrackDepth, VeinGlow,
// ColorRock/Ember/Hot/Core.
//
// CrackThreshold drives BOTH where the crust cracks open (geometry) and
// where the heat glow starts (shading) - one slider for both. Values below
// match Python/materials/build_lava_material.py's final tuned instance -
// this demo drifted stale from it once before (0.35 instead of 0.82 made
// almost the whole crust read as "hot", not just the cracks).
#define LSDEMO_RELIEF 0.35
#define LSDEMO_CRACK_THRESHOLD 0.82
#define LSDEMO_EMBER_AMOUNT 0.30
#define LSDEMO_GLOW_STRENGTH 2.5
#define LSDEMO_STONE_AMOUNT 0.07
#define LSDEMO_NOISE_SIZE 7.5
#define LSDEMO_NOISE_SPEED 0.06
// ThinCrackScale is the one that actually shapes the crack NETWORK you see -
// NoiseSize above only shapes the big underlying plates, which barely read
// in this flat demo. Shared between the height call and the heat call below
// so the crust cracks open exactly where the glow starts.
#define LSDEMO_CRACK_SCALE 10.0

LS_NoiseParams LSDemo_Noise()
{
    LS_NoiseParams np;
    np.Size = LSDEMO_NOISE_SIZE;
    np.Speed = LSDEMO_NOISE_SPEED;  // lava crawls - turn this up to see it move
    np.Seed = 7.0;
    np.Type = 2.0;          // ridged - plate boundaries
    np.Octaves = 3.0;
    np.Lacunarity = 2.0;
    np.Persistence = 0.45;
    return np;
}

float LSDemo_Height(vec2 uv, float t)
{
    return LS_HeightLava(uv, t, LSDemo_Noise(),
                         1.3,    // WarpStrength
                         22.0,   // StoneScale
                         LSDEMO_STONE_AMOUNT,
                         LSDEMO_CRACK_SCALE,
                         0.08,   // ThinCrackDepth
                         LSDEMO_CRACK_THRESHOLD);
}

void LSDemo_Shade(vec2 uv, float t, vec3 N, float h,
                  out vec3 base, out vec3 emissive, out float rough)
{
    LS_NoiseParams np = LSDemo_Noise();
    float heat = LS_LavaHeat(uv, t, h, np,
                             LSDEMO_CRACK_THRESHOLD,
                             4.5,   // CrackSharpness
                             6.0,   // EmberScale
                             0.15,  // EmberSpeed
                             LSDEMO_EMBER_AMOUNT,
                             LSDEMO_CRACK_SCALE,
                             0.22); // VeinGlow

    LS_Surface s = LS_ShadeLava(vec3(0.0, 0.0, 1.0), 0.0, 0.0, 0.0, 0.0,
        heat, t, uv,
        vec3(0.010, 0.005, 0.004),  // ColorRock
        vec3(0.35,  0.03,  0.005),  // ColorEmber
        vec3(1.20,  0.22,  0.02),   // ColorHot
        vec3(2.00,  0.95,  0.20),   // ColorCore
        LSDEMO_GLOW_STRENGTH,
        0.75,   // RoughnessRock
        0.35);  // RoughnessHot
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

# ---- LVL 1 needs a shaded object, not a height field -------------------------
EFFECT_CHAMELEON = """
// ============================== LVL 1 - Chameleon ==========================
// Instance parameters: ColorA/B/C, RoughnessA/B/C, Reflectivity,
// GradientBoost, FresnelPower, GradientShift, HighlightColor.
// Rendered on an analytic sphere so the whole view-angle range is visible at
// once - in the engine this material sits on real meshes.
#define LSDEMO_FRESNEL_POWER 5.5
#define LSDEMO_GRADIENT_SHIFT 2.2
#define LSDEMO_REFLECTIVITY 0.15
#define LSDEMO_GRADIENT_BOOST 0.15

void mainImage(out vec4 fragColor, in vec2 fragCoord)
{
    vec2 p = (2.0 * fragCoord - iResolution.xy) / iResolution.y;

    // ray-sphere intersection (sphere at origin, radius 1, camera on -Z)
    vec3 ro = vec3(0.0, 0.0, -3.0);
    vec3 rd = normalize(vec3(p, 1.5));
    float b = dot(ro, rd);
    float c = dot(ro, ro) - 1.0;
    float disc = b * b - c;

    vec3 col = vec3(0.02, 0.02, 0.025);   // studio backdrop

    if (disc > 0.0)
    {
        float dist = -b - sqrt(disc);
        vec3 pos = ro + rd * dist;

        vec3 n = normalize(pos);
        vec3 V = -rd;

        // stand-in for the cubemap: a soft two-light studio environment
        vec3 R = reflect(-V, n);
        float sky = saturate(R.y * 0.5 + 0.5);
        vec3 reflection = mix(vec3(0.05, 0.06, 0.08), vec3(0.85, 0.90, 1.0), sky);

        LS_Surface s = LS_ShadeChameleon(n, V,
            vec3(1.00, 0.25, 0.85),   // ColorA - grazing magenta
            vec3(0.50, 0.20, 0.95),   // ColorB - violet
            vec3(0.00, 0.95, 1.00),   // ColorC - facing cyan
            0.25, 0.15, 0.10,         // RoughnessA/B/C
            reflection,
            vec3(1.0),                // HighlightColor
            LSDEMO_REFLECTIVITY,
            LSDEMO_GRADIENT_BOOST,
            LSDEMO_FRESNEL_POWER,
            LSDEMO_GRADIENT_SHIFT);

        vec3 L = normalize(vec3(0.5, 0.7, -0.6));
        float diffuse = max(dot(n, L), 0.0);
        float shininess = mix(16.0, 200.0, 1.0 - s.Roughness);
        float specular = pow(max(dot(reflect(-L, n), V), 0.0), shininess);

        col = s.BaseColor * (0.2 + 0.8 * diffuse)
            + vec3(1.0) * specular * (1.0 - s.Roughness)
            + s.Emissive;
    }

    col = col / (1.0 + col);
    col = pow(col, vec3(1.0 / 2.2));
    fragColor = vec4(col, 1.0);
}
"""

# ---- LVL 3/4/5 are a two-pass simulation -------------------------------------
# Buffer A runs LS_PaintStep into an RGBA buffer; Image reads it and shades.
SIM_BUFFER = """
// =========================== SIMULATION PASS (Buffer A) ====================
//  Shadertoy setup: create "Buffer A", paste this pass into it, and set its
//  iChannel0 to Buffer A itself (that self-reference IS the ping-pong).
//  Hold the left mouse button over the canvas to paint.
//
//  Buffer channels: R = height, G = velocity, B = wetness.
void mainImage(out vec4 fragColor, in vec2 fragCoord)
{
    vec2 uv = fragCoord / iResolution.xy;
    float texel = 1.0 / iResolution.y;

    vec3 prev = texture(iChannel0, uv).rgb;
    if (iFrame == 0) { prev = vec3(0.0); }

    // neighbour average: doubles as the smoothing target and the wave
    // laplacian. The tap distance is UV-based so the simulation behaves
    // identically at any resolution (see LS_WaveTapDistance).
    float tapD = LS_WaveTapDistance(texel, LSDEMO_WAVE_TAP);
    float avg = 0.25 * (texture(iChannel0, uv + vec2(tapD, 0.0)).r
                      + texture(iChannel0, uv - vec2(tapD, 0.0)).r
                      + texture(iChannel0, uv + vec2(0.0, tapD)).r
                      + texture(iChannel0, uv - vec2(0.0, tapD)).r);

    LS_BrushParams brush;
    brush.Pos = iMouse.xy / iResolution.xy;
    // Shadertoy exposes no previous-frame mouse, so the capsule collapses to
    // a point here. In Unreal the controller passes the real previous UV
    // (see LiquidSimPaintController.cpp) and fast strokes stay continuous.
    brush.PrevPos = brush.Pos;
    brush.Radius = LSDEMO_BRUSH_RADIUS;
    brush.Softness = LSDEMO_BRUSH_SOFTNESS;
    brush.Depth = LSDEMO_BRUSH_DEPTH;
    brush.RimHeight = LSDEMO_BRUSH_RIM;
    brush.RimOffset = 1.2;
    brush.RimWidth = 0.4;
    brush.Raggedness = LSDEMO_RAGGEDNESS;
    brush.Strength = (iMouse.z > 0.0) ? 1.0 : 0.0;

    LS_SimParams sim;
    sim.Decay = LSDEMO_DECAY;
    sim.DecayVariation = LSDEMO_DECAY_VAR;
    sim.Viscosity = LSDEMO_VISCOSITY;
    sim.SpringDamp = 0.995;
    sim.VelocityMax = 0.5;
    sim.Smoothing = LSDEMO_SMOOTHING;
    sim.WetnessDecay = LSDEMO_WETNESS_DECAY;
    sim.MaxHeight = 0.5;
    sim.DeltaTime = min(iTimeDelta, 0.05);

    fragColor = vec4(LS_PaintStep(prev, avg, uv, brush, sim), 1.0);
}
"""

SIM_IMAGE_HEADER = """
// ============================= DISPLAY PASS (Image) ========================
//  Reads the simulation buffer (iChannel0 = Buffer A) and shades it.
"""

SIM_IMAGE_MAIN = """
void mainImage(out vec4 fragColor, in vec2 fragCoord)
{
    vec2 uv = fragCoord / iResolution.xy;
    float t = iTime;
    float tap = 0.004;

    vec3 hvw = texture(iChannel0, uv).rgb;
    float hC = hvw.r;
    float hU = texture(iChannel0, uv + vec2(tap, 0.0)).r;
    float hV = texture(iChannel0, uv + vec2(0.0, tap)).r;

    vec3 N = normalize(vec3((hC - hU) * LSDEMO_RELIEF / tap,
                            (hC - hV) * LSDEMO_RELIEF / tap, 1.0));

    vec3 base, emissive;
    float rough;
    LSDemo_ShadeSim(uv, t, N, hC, hvw.b, base, emissive, rough);

    vec3 L = normalize(vec3(0.45, 0.55, 0.70));
    vec3 V = vec3(0.0, 0.0, 1.0);
    float diffuse = max(dot(N, L), 0.0);
    float shininess = mix(8.0, 160.0, 1.0 - clamp(rough, 0.0, 1.0));
    float specular = pow(max(dot(reflect(-L, N), V), 0.0), shininess);

    vec3 col = base * (0.25 + 0.75 * diffuse)
             + vec3(1.0) * specular * (1.0 - rough)
             + emissive;

    col = col / (1.0 + col);
    col = pow(col, vec3(1.0 / 2.2));
    fragColor = vec4(col, 1.0);
}
"""

SIM_SHADE_PAINTED = """
// ---- LVL 3: thick green gel, paint stays forever --------------------------
// Viscosity 0 and Smoothing 0 ARE the identity of this level - paint sits
// where it lands and never spreads. Fixed, not sliders: dial them up and
// this stops being "gel" and turns into LVL4.
#define LSDEMO_RELIEF 0.5
#define LSDEMO_WAVE_TAP 0.004
#define LSDEMO_BRUSH_RADIUS 0.07
#define LSDEMO_BRUSH_SOFTNESS 0.9
#define LSDEMO_BRUSH_DEPTH 1.2
#define LSDEMO_BRUSH_RIM 0.35
#define LSDEMO_RAGGEDNESS 0.5
#define LSDEMO_DECAY_FIXED 1.0
#define LSDEMO_DECAY LSDEMO_DECAY_FIXED
#define LSDEMO_DECAY_VAR_FIXED 0.0
#define LSDEMO_DECAY_VAR LSDEMO_DECAY_VAR_FIXED
#define LSDEMO_VISCOSITY_FIXED 0.0
#define LSDEMO_VISCOSITY LSDEMO_VISCOSITY_FIXED
#define LSDEMO_SMOOTHING_FIXED 0.0
#define LSDEMO_SMOOTHING LSDEMO_SMOOTHING_FIXED
#define LSDEMO_WETNESS_DECAY 1.0

void LSDemo_ShadeSim(vec2 uv, float t, vec3 N, float h, float wetness,
                     out vec3 base, out vec3 emissive, out float rough)
{
    LS_Surface s = LS_ShadePainted(vec3(0.0, 0.0, 1.0), h, h, h, wetness, 0.0,
        vec3(0.13, 0.42, 0.02),    // ColorBase - matte apple green
        vec3(0.002, 0.05, 0.03),   // ColorLow  - near-black folds
        vec3(0.08, 0.65, 0.10),    // ColorMid  - vivid green
        vec3(0.95, 1.00, 0.15),    // ColorHigh - yellow crests
        9.0,    // HeightColorScale
        1.6,    // WetSensitivity
        0.45,   // RoughnessDry
        0.1);   // RoughnessWet
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

SIM_SHADE_WATER = """
// ---- LVL 4: water, shallow press, rings spread and ring out ---------------
// Viscosity IS the headline knob here - it is what turns a dent into a
// travelling ring (measured stability ceiling: 2.0). Brush shape, raggedness
// and smoothing are fixed: they set the splash, not the wave behaviour.
#define LSDEMO_RELIEF 0.8
#define LSDEMO_WAVE_TAP 0.004
#define LSDEMO_BRUSH_RADIUS_FIXED 0.05
#define LSDEMO_BRUSH_RADIUS LSDEMO_BRUSH_RADIUS_FIXED
#define LSDEMO_BRUSH_SOFTNESS_FIXED 1.6
#define LSDEMO_BRUSH_SOFTNESS LSDEMO_BRUSH_SOFTNESS_FIXED
#define LSDEMO_BRUSH_DEPTH 8.0
#define LSDEMO_BRUSH_RIM_FIXED 2.0
#define LSDEMO_BRUSH_RIM LSDEMO_BRUSH_RIM_FIXED
#define LSDEMO_RAGGEDNESS_FIXED 0.0
#define LSDEMO_RAGGEDNESS LSDEMO_RAGGEDNESS_FIXED
#define LSDEMO_DECAY 0.998
#define LSDEMO_DECAY_VAR 0.004
#define LSDEMO_VISCOSITY 2.0
#define LSDEMO_SMOOTHING_FIXED 0.1
#define LSDEMO_SMOOTHING LSDEMO_SMOOTHING_FIXED
#define LSDEMO_WETNESS_DECAY 0.996

void LSDemo_ShadeSim(vec2 uv, float t, vec3 N, float h, float wetness,
                     out vec3 base, out vec3 emissive, out float rough)
{
    LS_Surface s = LS_ShadePainted(vec3(0.0, 0.0, 1.0), h, h, h, wetness, 0.0,
        vec3(0.08, 0.28, 0.55),    // ColorBase - open water
        vec3(0.005, 0.04, 0.22),   // ColorLow  - deep troughs
        vec3(0.10, 0.32, 0.60),    // ColorMid
        vec3(0.95, 0.98, 1.00),    // ColorHigh - foam crests
        12.0,   // HeightColorScale
        1.8,    // WetSensitivity
        0.05,   // RoughnessDry
        0.03);  // RoughnessWet
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

SIM_SHADE_BOSS = """
// ---- LVL 5: boss - noise + paint, iridescent fluid, glowing troughs -------
// This level's identity is the SHADING response, not the brush - so the
// paint/sim constants are fixed and ActivitySensitivity/TroughGlow/
// FoamIntensity/SparkleIntensity (the real instance parameters) are live.
#define LSDEMO_RELIEF 0.7
#define LSDEMO_WAVE_TAP 0.004
#define LSDEMO_BRUSH_RADIUS_FIXED 0.08
#define LSDEMO_BRUSH_RADIUS LSDEMO_BRUSH_RADIUS_FIXED
#define LSDEMO_BRUSH_SOFTNESS_FIXED 1.0
#define LSDEMO_BRUSH_SOFTNESS LSDEMO_BRUSH_SOFTNESS_FIXED
#define LSDEMO_BRUSH_DEPTH_FIXED 5.0
#define LSDEMO_BRUSH_DEPTH LSDEMO_BRUSH_DEPTH_FIXED
#define LSDEMO_BRUSH_RIM_FIXED 1.2
#define LSDEMO_BRUSH_RIM LSDEMO_BRUSH_RIM_FIXED
#define LSDEMO_RAGGEDNESS_FIXED 0.3
#define LSDEMO_RAGGEDNESS LSDEMO_RAGGEDNESS_FIXED
#define LSDEMO_DECAY_FIXED 0.996
#define LSDEMO_DECAY LSDEMO_DECAY_FIXED
#define LSDEMO_DECAY_VAR_FIXED 0.003
#define LSDEMO_DECAY_VAR LSDEMO_DECAY_VAR_FIXED
#define LSDEMO_VISCOSITY_FIXED 1.5
#define LSDEMO_VISCOSITY LSDEMO_VISCOSITY_FIXED
#define LSDEMO_SMOOTHING_FIXED 0.15
#define LSDEMO_SMOOTHING LSDEMO_SMOOTHING_FIXED
#define LSDEMO_WETNESS_DECAY 0.995
#define LSDEMO_ACTIVITY_SENSITIVITY 2.5
#define LSDEMO_TROUGH_GLOW 3.0
#define LSDEMO_FOAM_INTENSITY 0.5
#define LSDEMO_SPARKLE_INTENSITY 0.35

void LSDemo_ShadeSim(vec2 uv, float t, vec3 N, float h, float wetness,
                     out vec3 base, out vec3 emissive, out float rough)
{
    LS_NoiseParams np;
    np.Size = 5.0; np.Speed = 0.3; np.Seed = 0.0;
    np.Type = 1.0; np.Octaves = 3.0; np.Lacunarity = 2.0; np.Persistence = 0.45;
    float noiseH = LS_HeightPerlin(uv, t, np);

    LS_Surface s = LS_ShadeBoss(N, vec3(0.0, 0.0, 1.0), uv, t,
        h, noiseH, wetness,
        vec3(0.010, 0.010, 0.014),  // BaseDarkColor - dormant liquid
        vec3(0.35, 0.05, 0.85),     // ColorA - grazing violet
        vec3(0.95, 0.15, 0.75),     // ColorB - magenta
        vec3(0.35, 0.65, 1.00),     // ColorC - facing blue
        vec3(1.00, 0.35, 0.03),     // TroughColor - hot orange
        vec3(0.15, 0.30, 1.00),     // EdgeColor - dithered blue rim
        vec3(1.0),                  // FoamColor
        LSDEMO_ACTIVITY_SENSITIVITY,
        6.0,                        // TroughSensitivity
        LSDEMO_TROUGH_GLOW,
        1.2,                        // InteriorGlow
        0.6,                        // EdgeDither
        LSDEMO_FOAM_INTENSITY,
        0.35,                       // IdleBreathing
        0.12, 0.08,                 // RoughnessIdle/Active
        260.0,                      // SparkleScale
        LSDEMO_SPARKLE_INTENSITY);
    base = s.BaseColor;
    emissive = s.Emissive;
    rough = s.Roughness;
}
"""

# name -> (kind, blocks)
EFFECTS = [
    ("LVL1_Chameleon", "single", [EFFECT_CHAMELEON]),
    ("LVL2_Displacement", "heightfield", [EFFECT_DISPLACEMENT]),
    ("LVL3_PaintedGel", "sim", [SIM_SHADE_PAINTED]),
    ("LVL4_Water", "sim", [SIM_SHADE_WATER]),
    ("LVL5_Boss", "sim", [SIM_SHADE_BOSS]),
    ("LVL6_Vortex", "heightfield", [EFFECT_VORTEX]),
    ("LVL7_Rain", "heightfield", [EFFECT_RAIN]),
    ("LVL8_Lava", "heightfield", [EFFECT_LAVA]),
]


def build_effect(core, name, kind, blocks):
    """Assemble one self-contained Shadertoy source."""
    if kind == "single":
        return PRELUDE + "\n" + core + "\n" + blocks[0]

    if kind == "heightfield":
        return PRELUDE + "\n" + core + "\n" + blocks[0] + HEIGHTFIELD_MAIN

    # Two-pass simulation. Both passes need the SAME struct/function library,
    # so it is written once here; only the two mainImage bodies differ. For
    # an actual Shadertoy paste: this file is the Image tab: for Buffer A,
    # copy the file again and swap its mainImage for the one below.
    image = (PRELUDE + "\n" + core + "\n" + blocks[0]
             + SIM_IMAGE_HEADER + SIM_IMAGE_MAIN)
    return image + "\n\n/* ==== BUFFER A's mainImage - same library as above; " \
        "paste this file into a second Shadertoy tab and swap in this one ====\n" \
        + SIM_BUFFER + "\n*/\n"


def glsl_for_viewer(core, name, kind, blocks):
    """Return (imageSrc, bufferSrc|None) with no comment wrapper, for WebGL."""
    if kind == "single":
        return PRELUDE + "\n" + core + "\n" + blocks[0], None
    if kind == "heightfield":
        return PRELUDE + "\n" + core + "\n" + blocks[0] + HEIGHTFIELD_MAIN, None
    image = PRELUDE + "\n" + core + "\n" + blocks[0] + SIM_IMAGE_HEADER + SIM_IMAGE_MAIN
    buffer_pass = PRELUDE + "\n" + core + "\n" + blocks[0] + SIM_BUFFER
    return image, buffer_pass


def main():
    full_core = load_core()
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    viewer_data = []
    for name, kind, blocks in EFFECTS:
        core = strip_comment_blocks(pruned_core(full_core, ENTRY_SYMBOLS[name]))
        src = build_effect(core, name, kind, blocks)
        path = os.path.join(OUT_DIR, name + ".glsl")
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        print("wrote {0} ({1} chars)".format(path, len(src)))

        image, buf = glsl_for_viewer(core, name, kind, blocks)
        viewer_data.append((name, kind, image, buf))

    write_viewer(viewer_data)



# Constants worth exposing as live controls in the viewer. Anything not listed
# stays a #define - a slider per constant would be noise, not control.
# LSDEMO_RELIEF is deliberately absent: it is demo-only normal strength, not
# a real material parameter on any of the 8 instances.
# name -> (label, min, max, step)
SLIDER_SPEC = {
    "LSDEMO_BRUSH_RADIUS":   ("Brush radius",    0.01, 0.25,  0.005),
    "LSDEMO_BRUSH_DEPTH":    ("Brush depth",     0.0,  12.0,  0.1),
    "LSDEMO_BRUSH_SOFTNESS": ("Brush softness",  0.2,  3.0,   0.05),
    "LSDEMO_BRUSH_RIM":      ("Rim",             0.0,  3.0,   0.05),
    "LSDEMO_DECAY":          ("Decay",           0.95, 1.0,   0.001),
    "LSDEMO_DECAY_VAR":      ("Decay variation", 0.0,  0.02,  0.0005),
    "LSDEMO_RAGGEDNESS":     ("Raggedness",      0.0,  1.0,   0.02),
    "LSDEMO_VISCOSITY":      ("Viscosity",       0.0,  2.0,   0.02),
    "LSDEMO_SMOOTHING":      ("Smoothing",       0.0,  1.0,   0.02),
    "LSDEMO_SWIRL_STRENGTH": ("Swirl",           0.0,  8.0,   0.1),
    "LSDEMO_SWIRL_SPEED":    ("Swirl speed",     0.0,  1.5,   0.02),
    "LSDEMO_FUNNEL_DEPTH":   ("Funnel depth",    0.0,  2.0,   0.02),
    "LSDEMO_BAND_ARMS":      ("Band arms",       1.0,  8.0,   1.0),
    "LSDEMO_BAND_TWIST":     ("Band twist",      0.0,  60.0,  1.0),
    "LSDEMO_DROP_RATE":      ("Drop rate",       0.0,  2.0,   0.05),
    "LSDEMO_RING_SPEED":     ("Ring speed",      0.05, 1.0,   0.01),
    "LSDEMO_DROP_DENSITY":   ("Drop density",    0.0,  1.0,   0.02),
    "LSDEMO_WET_SCALE":      ("Wet patch size",  0.5,  8.0,   0.1),
    "LSDEMO_CRACK_THRESHOLD": ("Crack threshold", 0.5, 0.95,  0.01),
    "LSDEMO_EMBER_AMOUNT":   ("Ember glow",      0.0,  1.0,   0.02),
    "LSDEMO_GLOW_STRENGTH":  ("Glow strength",   0.0,  4.0,   0.1),
    "LSDEMO_STONE_AMOUNT":   ("Stone bumps",     0.0,  1.0,   0.02),
    "LSDEMO_CRACK_SCALE":    ("Crack scale",     3.0,  25.0,  0.5),
    "LSDEMO_NOISE_SIZE":     ("Noise size",      1.0,  16.0,  0.1),
    "LSDEMO_NOISE_SPEED":    ("Noise speed",     0.0,  1.0,   0.01),
    "LSDEMO_OCTAVES":        ("Octaves",         1.0,  6.0,   1.0),
    "LSDEMO_PERSISTENCE":    ("Persistence",     0.1,  0.9,   0.02),
    "LSDEMO_FRESNEL_POWER":  ("Fresnel power",   0.5,  10.0,  0.1),
    "LSDEMO_GRADIENT_SHIFT": ("Gradient shift",  0.5,  5.0,   0.05),
    "LSDEMO_REFLECTIVITY":   ("Reflectivity",    0.0,  1.0,   0.02),
    "LSDEMO_GRADIENT_BOOST": ("Gradient boost",  0.0,  1.0,   0.02),
    "LSDEMO_ACTIVITY_SENSITIVITY": ("Activity",  0.5,  6.0,   0.1),
    "LSDEMO_TROUGH_GLOW":    ("Trough glow",     0.0,  6.0,   0.1),
    "LSDEMO_FOAM_INTENSITY": ("Foam",            0.0,  1.5,   0.02),
    "LSDEMO_SPARKLE_INTENSITY": ("Sparkle",      0.0,  1.0,   0.02),
}

_DEFINE_RE = __import__("re").compile(
    r"^[ 	]*#define[ 	]+(LSDEMO_[A-Z_0-9]+)[ 	]+([-0-9.]+)[ 	]*$",
    __import__("re").MULTILINE)


def hoist_sliders(*sources):
    """Turn tunable #defines into uniforms so the viewer can drive them live.

    Returns (declarations, slider list). EVERY occurrence of a hoisted define is
    removed: a port concatenates several sections and can define the same name
    more than once, which would shadow the uniform.
    """
    found = {}
    for src in sources:
        if not src:
            continue
        for name, value in _DEFINE_RE.findall(src):
            if name in SLIDER_SPEC and name not in found:
                found[name] = float(value)

    def strip(m):
        return "" if m.group(1) in found else m.group(0)

    cleaned = [(_DEFINE_RE.sub(strip, src) if src else src) for src in sources]
    decls = chr(10).join("uniform float %s;" % n for n in sorted(found))
    sliders = [
        {"name": n, "label": SLIDER_SPEC[n][0], "min": SLIDER_SPEC[n][1],
         "max": SLIDER_SPEC[n][2], "step": SLIDER_SPEC[n][3], "value": v}
        for n, v in sorted(found.items())
    ]
    return cleaned, decls, sliders


def write_viewer(effects):
    """A single self-contained WebGL2 page that runs every effect live."""
    import json

    payload = []
    for name, kind, image, buf in effects:
        subtitle, params, stat = EFFECT_INFO.get(name, ("", "", ""))
        (image, buf), decls, sliders = hoist_sliders(image, buf)
        # image and buf are both FULL self-contained programs (WebGL compiles
        # each independently, so each needs its own copy of every helper).
        # The code shown in "Show GLSL" only needs the shared library once -
        # showing it twice back to back reads as duplicated code, not two
        # different shaders.
        if kind == "sim":
            display = image + ("\n\n/* ==== BUFFER A's mainImage - same "
                "library as the Image pass above; paste this file into a "
                "second Shadertoy tab and swap in this one ====\n"
                + SIM_BUFFER + "\n*/\n")
        else:
            display = image
        payload.append({
            "name": name,
            "kind": kind,
            "image": image,
            "buffer": buf,
            "display": display,
            "decls": decls,
            "sliders": sliders,
            "subtitle": subtitle,
            "params": params,
            "stat": stat,
        })

    html = VIEWER_HTML.replace("__EFFECT_DATA__", json.dumps(payload))
    path = os.path.join(OUT_DIR, "viewer.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote {0} ({1} chars)".format(path, len(html)))


if __name__ == "__main__":
    main()
