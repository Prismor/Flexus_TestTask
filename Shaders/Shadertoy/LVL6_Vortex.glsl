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

float LS_HeightVortex(float2 uv, float time, LS_NoiseParams np,
                      float swirlStrength, float swirlTightness, float swirlSpeed,
                      float warpStrength, float funnelDepth, float funnelTightness)
{
	float2 c = uv - 0.5;
	float r = length(c);

	float angle = swirlStrength * exp(-r * swirlTightness) + time * swirlSpeed;
	float sa = sin(angle);
	float ca = cos(angle);
	float2 swirled = float2(c.x * ca - c.y * sa, c.x * sa + c.y * ca) + 0.5;

	float3 p = float3(swirled * np.Size, time * np.Speed);

	LS_NoiseParams warpNp = np;
	warpNp.Seed = np.Seed + 9.0;
	warpNp.Type = 1.0;
	warpNp.Octaves = 2.0;
	float warp = LS_FBM(p + 3.7, warpNp);

	float noise = LS_FBM(p + warp * warpStrength, np);

	// close to the core the rotation stretches the noise lattice into visible
	// repeated streaks - fade it out there, the funnel carries that region
	float noiseFade = smoothstep(0.0, 0.12, r);

	float basin = exp(-r * r * funnelTightness * 0.30);
	float throat = exp(-r * r * funnelTightness * 3.20);
	float funnel = -funnelDepth * (0.42 * basin + 0.58 * throat);

	funnel *= 1.0 - smoothstep(0.40, 0.50, max(abs(c.x), abs(c.y)));

	return noise * noiseFade + funnel;
}

// ---- LVL 6: vortex ---------------------------------------------------------

// Colour is sampled on the SAME rotated/swirled coordinates the height field uses
// (see LS_HeightVortex), so the bands wind and drift with the geometry, not the camera.
LS_Surface LS_ShadeVortex(float3 displacedNormal, float3 viewDir, float2 uv, float time,
                          float centreDist,
                          float3 colorA, float3 colorB, float3 colorC,
                          float3 coreColor, float3 foamColor,
                          float coreGlow, float coreTightness,
                          float pulseSpeed, float pulseAmount,
                          float roughIdle, float roughActive,
                          float sparkleScale, float sparkleIntensity,
                          float bandArms, float bandTwist, float bandNoiseScale,
                          float bandNoiseAmount, float bandContrast,
                          LS_NoiseParams np, float swirlStrength, float swirlTightness,
                          float swirlSpeed)
{
	LS_Surface s;
	s.Offset = float3(0.0, 0.0, 0.0);
	s.Normal = displacedNormal;
	float2 cc = uv - 0.5;
	float r = length(cc);

	float angle = swirlStrength * exp(-r * swirlTightness) + time * swirlSpeed;
	float sa = sin(angle);
	float ca = cos(angle);
	float2 swirled = float2(cc.x * ca - cc.y * sa, cc.x * sa + cc.y * ca) + 0.5;

	LS_NoiseParams lineNp = np;
	lineNp.Type = 2.0;
	lineNp.Octaves = 3.0;
	float lines = LS_FBM(float3(swirled * bandNoiseScale, time * 0.08), lineNp);

	// A slow arm-count modulation keeps large-scale structure under the streaks.
	float ang2 = atan2(cc.y, cc.x);
	float arms = sin(ang2 * bandArms - r * bandTwist + time * pulseSpeed * 0.6);

	// Streaks tighten toward the eye of the vortex: that radial pull is what
	// makes it read as a portal rather than a flat swirl pattern.
	float pull = 1.0 - smoothstep(0.0, 0.42, r);

	float band = 0.5
	           + (lines - 0.5) * 0.85
	           + arms * 0.20
	           + pull * 0.18;
	band = saturate(band + bandNoiseAmount * (lines - 0.5));

	// Contrast sharpens the streaks into thin lines instead of soft washes.
	band = saturate((band - 0.5) * bandContrast + 0.5);

	float3 swirlCol = lerp(colorA, colorB, smoothstep(0.0, 0.5, band));
	swirlCol = lerp(swirlCol, colorC, smoothstep(0.42, 1.0, band));

	// A little genuine view dependence on top - a sheen, not the base colour.
	float sheen = pow(1.0 - saturate(dot(normalize(displacedNormal), normalize(viewDir))), 4.0);
	s.BaseColor = swirlCol * (1.0 + sheen * 0.35);

	float pulse = 1.0 + pulseAmount * sin(time * pulseSpeed);
	float core = exp(-centreDist * centreDist * coreTightness) * pulse;

	float ndotv = saturate(dot(normalize(displacedNormal), normalize(viewDir)));
	float rim = pow(1.0 - ndotv, 3.0) * core;
	float sparkle = LS_Sparkle(uv, displacedNormal, viewDir, time, sparkleScale, 0.03);

	s.Emissive = coreColor * core * coreGlow
	           + foamColor * rim * 0.6
	           + foamColor * sparkle * sparkleIntensity;
	s.Roughness = lerp(roughIdle, roughActive, saturate(core));
	return s;
}

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
