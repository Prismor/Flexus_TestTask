// =============================================================================
//  Render-target painting
//
//  The interactive simulation. One RGBA buffer holds height, velocity and
//  paint coverage; every frame it is redrawn from the previous one
//  (ping-pong) with a new brush stamp added. Viscosity 0 means the paint
//  just stays - that is this level.
//
//  Portable HLSL - no engine API. The same text compiles in Unreal and Unity;
//  for GLSL add the six-line prelude (see Shaders/Shadertoy/).
// =============================================================================

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
