// HLSL -> GLSL compatibility shim.
#define float2 vec2
#define float3 vec3
#define float4 vec4
#define lerp  mix
#define frac  fract
#define atan2 atan
#define saturate(x) clamp((x), 0.0, 1.0)

// Fractal noise settings shared by every procedural height field.
struct LS_NoiseParams
{
	float Size;         // spatial frequency: how many features across the UV
	float Speed;        // animation speed (time drives the 3rd noise axis)
	float Seed;         // domain offset - different seeds never correlate
	float Type;         // 0 = value, 1 = gradient/Perlin, 2 = ridged
	float Octaves;      // 1..6 fractal layers
	float Lacunarity;   // frequency multiplier per octave (classic: 2.0)
	float Persistence;  // amplitude multiplier per octave (classic: 0.5)
};

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

float3 LS_Hash33(float3 p)
{
	p = frac(p * float3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return frac((p.xxy + p.yxx) * p.zyx);
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

float LS_GradientNoise(float3 p)
{
	float3 i = floor(p);
	float3 f = frac(p);
	float3 u = f * f * (3.0 - 2.0 * f);

	float g000 = dot(LS_Hash33(i + float3(0.0, 0.0, 0.0)) * 2.0 - 1.0, f - float3(0.0, 0.0, 0.0));
	float g100 = dot(LS_Hash33(i + float3(1.0, 0.0, 0.0)) * 2.0 - 1.0, f - float3(1.0, 0.0, 0.0));
	float g010 = dot(LS_Hash33(i + float3(0.0, 1.0, 0.0)) * 2.0 - 1.0, f - float3(0.0, 1.0, 0.0));
	float g110 = dot(LS_Hash33(i + float3(1.0, 1.0, 0.0)) * 2.0 - 1.0, f - float3(1.0, 1.0, 0.0));
	float g001 = dot(LS_Hash33(i + float3(0.0, 0.0, 1.0)) * 2.0 - 1.0, f - float3(0.0, 0.0, 1.0));
	float g101 = dot(LS_Hash33(i + float3(1.0, 0.0, 1.0)) * 2.0 - 1.0, f - float3(1.0, 0.0, 1.0));
	float g011 = dot(LS_Hash33(i + float3(0.0, 1.0, 1.0)) * 2.0 - 1.0, f - float3(0.0, 1.0, 1.0));
	float g111 = dot(LS_Hash33(i + float3(1.0, 1.0, 1.0)) * 2.0 - 1.0, f - float3(1.0, 1.0, 1.0));

	float n = lerp(
		lerp(lerp(g000, g100, u.x), lerp(g010, g110, u.x), u.y),
		lerp(lerp(g001, g101, u.x), lerp(g011, g111, u.x), u.y),
		u.z);
	return n * 1.4; // raw range is about [-0.7,0.7] - stretch toward [-1,1]
}

float LS_FBM(float3 p, LS_NoiseParams np)
{
	p += np.Seed * 57.31;

	float sum = 0.0;
	float amp = 1.0;
	float ampTotal = 0.0;
	float3 sp = p;

	int octaves = int(clamp(np.Octaves, 1.0, 6.0));

	for (int i = 0; i < 6; ++i)
	{
		if (i >= octaves) { break; }

		float n = (np.Type < 0.5) ? LS_ValueNoise(sp) : LS_GradientNoise(sp);
		if (np.Type > 1.5) { n = 1.0 - 2.0 * abs(n); } // ridged

		sum += n * amp;
		ampTotal += amp;
		amp *= np.Persistence;
		sp *= np.Lacunarity;
	}

	return sum / max(ampTotal, 0.0001); // normalised to roughly [-1,1]
}

float3 LS_Iridescent(float3 normal, float3 viewDir, float3 a, float3 b, float3 c, float shift)
{
	float ndotv = pow(saturate(dot(normalize(normal), normalize(viewDir))), max(shift, 0.1));
	float3 low  = lerp(a, b, smoothstep(0.0, 0.55, ndotv));
	float3 high = lerp(b, c, smoothstep(0.45, 1.0, ndotv));
	return lerp(low, high, smoothstep(0.45, 0.55, ndotv));
}

// View-dependent procedural glitter: a sparse subset of hash cells lights up
// and twinkles - reads as sparkle particles without any particle system.
float LS_Sparkle(float2 uv, float3 normal, float3 viewDir, float time, float scale, float density)
{
	float2 cell = floor(uv * scale);
	float h = LS_Hash31(float3(cell, 7.0));

	float gate = step(1.0 - density, h);                       // only rare cells
	float twinkle = 0.5 + 0.5 * sin(time * 3.0 + h * 251.0);   // own phase each
	float view = pow(saturate(dot(normalize(normal), normalize(viewDir))), 2.0);
	return gate * twinkle * view;
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

float LS_HeightPerlin(float2 uv, float time, LS_NoiseParams np)
{
	return LS_FBM(float3(uv * np.Size, time * np.Speed), np);
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

void LS_BossDisplace(float3 worldNormal,
                     float noiseC, float noiseU, float noiseV, float noiseAmplitude,
                     float paintC, float paintU, float paintV, float paintAmplitude,
                     out float3 outOffset, out float3 outNormal)
{
	LS_SurfaceFromHeights(worldNormal,
		noiseC * noiseAmplitude + paintC * paintAmplitude,
		noiseU * noiseAmplitude + paintU * paintAmplitude,
		noiseV * noiseAmplitude + paintV * paintAmplitude,
		outOffset, outNormal);
}

// activity = wetness*activitySensitivity is the one value everything below keys off -
// dormant base fades in as it rises, so colour tracks the paint's own movement.
LS_Surface LS_ShadeBoss(float3 displacedNormal, float3 viewDir, float2 uv, float time,
                        float paintHeight, float noiseHeight, float wetness,
                        float3 baseDark, float3 colorA, float3 colorB, float3 colorC,
                        float3 troughColor, float3 edgeColor, float3 foamColor,
                        float activitySensitivity, float troughSensitivity,
                        float troughGlow, float interiorGlow, float edgeDither,
                        float foamIntensity, float idleBreathing,
                        float roughIdle, float roughActive,
                        float sparkleScale, float sparkleIntensity)
{
	float activity = saturate(wetness * activitySensitivity);
	float troughT = saturate(-paintHeight * troughSensitivity);

	float3 iridescent = LS_Iridescent(displacedNormal, viewDir, colorA, colorB, colorC, 1.0);
	float3 fluid = lerp(iridescent, troughColor, troughT);
	float3 idle = baseDark * (1.0 + noiseHeight * idleBreathing);

	LS_Surface s;
	s.Offset = float3(0.0, 0.0, 0.0); // displacement handled by LS_BossDisplace
	s.Normal = displacedNormal;
	s.BaseColor = lerp(idle, fluid, activity);

	// noise-dithered tint exactly on the coverage boundary
	float edgeBand = smoothstep(0.03, 0.2, activity) * (1.0 - smoothstep(0.35, 0.7, activity));
	float dither = step(0.5, LS_Hash31(float3(uv * 900.0, 1.0)));
	s.BaseColor = lerp(s.BaseColor, edgeColor, edgeBand * dither * saturate(edgeDither));

	float ndotv = saturate(dot(normalize(displacedNormal), normalize(viewDir)));
	float rim = pow(1.0 - ndotv, 3.0) * activity;
	float sparkle = LS_Sparkle(uv, displacedNormal, viewDir, time,
	                           sparkleScale, 0.015 + activity * 0.03);

	s.Emissive = troughColor * (troughT * troughT) * troughGlow
	           + troughColor * pow(saturate(wetness), 3.0) * interiorGlow
	           + foamColor * rim * foamIntensity
	           + foamColor * sparkle * sparkleIntensity * (0.3 + activity);
	s.Roughness = lerp(roughIdle, roughActive, activity);
	return s;
}

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
