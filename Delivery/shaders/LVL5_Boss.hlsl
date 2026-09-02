// =============================================================================
//  Boss - everything combined
//
//  Procedural noise displacement and painted displacement are summed per
//  tap, then shaded as an iridescent fluid over a near-black idle base,
//  with glowing troughs, a dithered coverage edge, foam and glitter.
//
//  Portable HLSL - no engine API. The same text compiles in Unreal and Unity;
//  for GLSL add the six-line prelude (see Shaders/Shadertoy/).
// =============================================================================

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
