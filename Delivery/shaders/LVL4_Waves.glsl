// HLSL -> GLSL compatibility shim.
#define float2 vec2
#define float3 vec3
#define float4 vec4
#define lerp  mix
#define frac  fract
#define atan2 atan
#define saturate(x) clamp((x), 0.0, 1.0)

// One brush stamp of the interactive paint pass (LVL 3/4/5).
struct LS_BrushParams
{
	float2 Pos;         // cursor UV this frame
	float2 PrevPos;     // cursor UV last frame - the stamp is a capsule
	float Radius;       // stamp radius in UV space
	float Softness;     // gaussian falloff width multiplier (higher = softer)
	float Depth;        // press-down RATE, units per second
	float RimHeight;    // raised ring RATE, units per second
	float RimOffset;    // ring centre distance, in Radius units
	float RimWidth;     // ring thickness, in Radius units
	float Raggedness;   // 0 = clean round edge, 1 = torn noisy edge
	float Strength;     // 1 while painting, 0 otherwise
};

// Per-texel simulation settings of the paint pass.
struct LS_SimParams
{
	float Decay;          // per-frame damping (1 = never fades)
	float DecayVariation; // spatial jitter of Decay - uneven, organic fade
	float Viscosity;      // laplacian coupling = wave propagation speed
	float SpringDamp;     // extra velocity-only damping (kills overshoot)
	float VelocityMax;    // velocity clamp (kills spikes)
	float Smoothing;      // blend toward neighbour average (rounds edges)
	float WetnessDecay;   // how long painted COLOUR lingers
	float MaxHeight;      // soft height limit
	float DeltaTime;      // real frame time - makes rates framerate-independent
};

float LS_WaveTapDistance(float texelSize, float waveTapUV)
{
	return max(texelSize, waveTapUV);
}

// What a displaced surface hands back to the material pins.
struct LS_Surface
{
	float3 Offset;    // World Position Offset (along the surface normal)
	float3 Normal;    // normal recalculated for the displaced shape
	float3 BaseColor;
	float3 Emissive;
	float  Roughness;
};

// Hash helpers (Dave Hoskins style): cheap pseudo-random from a position.
// No textures and no sin() - so no visible periodicity or platform drift.
float LS_Hash31(float3 p)
{
	p = frac(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return frac((p.x + p.y) * p.z);
}

// Value noise: random value per lattice corner, smoothly interpolated. [-1,1]
float LS_ValueNoise(float3 p)
{
	float3 i = floor(p);
	float3 f = frac(p);
	float3 u = f * f * (3.0 - 2.0 * f); // smoothstep weights

	float c000 = LS_Hash31(i + float3(0.0, 0.0, 0.0));
	float c100 = LS_Hash31(i + float3(1.0, 0.0, 0.0));
	float c010 = LS_Hash31(i + float3(0.0, 1.0, 0.0));
	float c110 = LS_Hash31(i + float3(1.0, 1.0, 0.0));
	float c001 = LS_Hash31(i + float3(0.0, 0.0, 1.0));
	float c101 = LS_Hash31(i + float3(1.0, 0.0, 1.0));
	float c011 = LS_Hash31(i + float3(0.0, 1.0, 1.0));
	float c111 = LS_Hash31(i + float3(1.0, 1.0, 1.0));

	float n = lerp(
		lerp(lerp(c000, c100, u.x), lerp(c010, c110, u.x), u.y),
		lerp(lerp(c001, c101, u.x), lerp(c011, c111, u.x), u.y),
		u.z);
	return n * 2.0 - 1.0;
}

// 3-stop gradient by a normalised value t (0 = lowest, 1 = highest).
// Wide overlapping crossfades - the two halves never show a seam.
float3 LS_HeightRamp(float t, float3 low, float3 mid, float3 high)
{
	float3 a = lerp(low, mid, smoothstep(0.0, 0.65, t));
	float3 b = lerp(mid, high, smoothstep(0.35, 1.0, t));
	return lerp(a, b, smoothstep(0.3, 0.7, t));
}

// Central differences: cross the edge vectors from two nearby height taps to get the
// true displaced normal (the engine's own normal still thinks the surface is flat).
void LS_SurfaceFromHeights(float3 worldNormal, float hCenter, float hTapU, float hTapV,
                           out float3 outOffset, out float3 outNormal)
{
	float tapDistance = 5.0; // cm between taps in world space

	float3 n = normalize(worldNormal);
	float3 t = float3(1.0, 0.0, 0.0);
	float3 b = float3(0.0, 1.0, 0.0);

	float3 posC = n * hCenter;
	float3 posU = t * tapDistance + n * hTapU;
	float3 posV = b * tapDistance + n * hTapV;

	outOffset = posC;
	outNormal = normalize(cross(posV - posC, posU - posC));

	if (dot(outNormal, n) < 0.0) { outNormal = -outNormal; }
}

float3 LS_PaintStep(float3 prevHVW, float neighbourAvgH, float2 uv,
                    LS_BrushParams brush, LS_SimParams sim)
{
	float h = prevHVW.r;
	float v = prevHVW.g;
	float w = prevHVW.b;

	// --- viscous relaxation: round off edges left by fast strokes ---------
	h = lerp(h, neighbourAvgH, saturate(sim.Smoothing));

	float jitter = LS_ValueNoise(float3(uv * 9.0, 3.0)) * sim.DecayVariation;
	float decay = saturate(sim.Decay - abs(jitter));

	float viscosity = min(sim.Viscosity, 2.0);

	v = (v + (neighbourAvgH - h) * viscosity) * decay * saturate(sim.SpringDamp);
	v = clamp(v, -sim.VelocityMax, sim.VelocityMax); // no overshoot spikes
	h = (h + v) * decay;

	float2 fromCentre = abs(uv - 0.5) * 2.0;
	float edgeDist = max(fromCentre.x, fromCentre.y);
	float edge = 1.0 - smoothstep(0.82, 1.0, edgeDist);
	v *= edge;
	h *= edge;

	float2 seg = brush.Pos - brush.PrevPos;
	float segLen2 = dot(seg, seg);
	float segT = (segLen2 > 0.00000001) ? saturate(dot(uv - brush.PrevPos, seg) / segLen2) : 0.0;
	float dist = length(uv - (brush.PrevPos + seg * segT));

	// gaussian dent, optionally torn at the border by high-frequency noise
	float tear = 0.5 + 0.5 * LS_ValueNoise(float3(uv * 55.0, 1.0));
	float dent = exp(-(dist * dist) / max(brush.Radius * brush.Radius * brush.Softness, 0.000001));
	dent *= lerp(1.0, tear, saturate(brush.Raggedness));

	// gaussian ring just outside the dent - displaced material piling up
	float rimD = (dist - brush.Radius * brush.RimOffset) / max(brush.Radius * brush.RimWidth, 0.0001);
	float rim = exp(-rimD * rimD);

	// Depth/RimHeight are RATES: scaling by DeltaTime presses the surface
	// down gradually in layers and keeps the feel framerate-independent.
	h += (-brush.Depth * dent + brush.RimHeight * rim) * brush.Strength * sim.DeltaTime;
	w = saturate(w * saturate(sim.WetnessDecay) + dent * brush.Strength * 2.5 * sim.DeltaTime);

	float knee = sim.MaxHeight * 0.7;
	float range = max(sim.MaxHeight - knee, 0.0001);
	float mag = abs(h);
	if (mag > knee)
	{
		h = sign(h) * (knee + range * tanh((mag - knee) / range));
	}

	return float3(h, v, w);
}

// wet (from the wetness channel) gates HOW MUCH colour shows; rampT (from height) picks
// WHICH colour - coverage stays solid even where height crosses zero.
LS_Surface LS_ShadePainted(float3 worldNormal, float hC, float hU, float hV, float wetness,
                           float amplitude, float3 baseColor,
                           float3 low, float3 mid, float3 high,
                           float heightColorScale, float wetSensitivity,
                           float roughnessDry, float roughnessWet)
{
	LS_Surface s;
	LS_SurfaceFromHeights(worldNormal, hC * amplitude, hU * amplitude, hV * amplitude,
	                      s.Offset, s.Normal);

	float wet = saturate(wetness * wetSensitivity);
	float rampT = saturate(hC * heightColorScale * 0.5 + 0.5);

	s.BaseColor = lerp(baseColor, LS_HeightRamp(rampT, low, mid, high), wet);
	s.Emissive = float3(0.0, 0.0, 0.0);
	s.Roughness = lerp(roughnessDry, roughnessWet, wet);
	return s;
}

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

// ============================= DISPLAY PASS (Image) ========================
//  Reads the simulation buffer (iChannel0 = Buffer A) and shades it.

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


/* ==== BUFFER A's mainImage - same library as above; paste this file into a second Shadertoy tab and swap in this one ====

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

*/
