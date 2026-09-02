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

// Voronoi F1: distance to the nearest of a scattered point set. Used for
// the cobblestone bumps on the lava crust.
float LS_Voronoi(float2 p)
{
	float2 i = floor(p);
	float2 f = frac(p);
	float dmin = 8.0;

	for (int y = -1; y <= 1; ++y)
	{
		for (int x = -1; x <= 1; ++x)
		{
			float2 g = float2(float(x), float(y));
			float2 o = LS_Hash33(float3(i + g, 0.0)).xy;
			float2 r = g + o - f;
			dmin = min(dmin, dot(r, r));
		}
	}
	return sqrt(dmin);
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

float LS_HeightLava(float2 uv, float time, LS_NoiseParams np, float warpStrength,
                    float stoneScale, float stoneAmount,
                    float thinCrackScale, float thinCrackDepth, float crackThreshold)
{
	float2 drift = float2(0.06, 0.021) * time * np.Speed;
	float3 p = float3((uv + drift) * np.Size, time * np.Speed * 0.35);

	// A second, slower-moving noise bends the sample point before the plate
	// field reads it - domain warp, so the plate edges curl instead of tiling.
	LS_NoiseParams warpNp = np;
	warpNp.Seed = np.Seed + 4.0;
	warpNp.Type = 1.0;
	warpNp.Octaves = 2.0;
	float warp = LS_FBM(p * 0.5 + 7.3, warpNp);

	float plates = LS_FBM(p + warp * warpStrength, np);

	// Only where a plate boundary runs hot (plates >= crackThreshold) do the
	// detail terms below get to touch the height at all.
	float crustMask = smoothstep(crackThreshold, crackThreshold + 0.3, plates);

	// Voronoi cells bump the crust up - cobblestone, not cracks.
	float stones = smoothstep(0.45, 0.05, LS_Voronoi(uv * stoneScale)) * stoneAmount;

	// A separate, independent noise field for the thin surface grooves - see
	// LS_LavaHeat for why this can't be the same field as the plates.
	LS_NoiseParams thinNp = np;
	thinNp.Seed = np.Seed + 23.0;
	thinNp.Type = 2.0;
	thinNp.Octaves = 2.0;
	float thin = LS_FBM(float3(uv * thinCrackScale, 2.7), thinNp);
	float groove = smoothstep(0.45, 0.75, thin) * thinCrackDepth;

	return plates + (stones - groove) * crustMask;
}

// Heat field of the lava crust, shared by height detail and shading.
float LS_LavaHeat(float2 uv, float time, float plateHeight, LS_NoiseParams np,
                  float crackThreshold, float crackSharpness,
                  float emberScale, float emberSpeed, float emberAmount,
                  float thinCrackScale, float veinGlow)
{
	LS_NoiseParams crackNp = np;
	crackNp.Seed = np.Seed + 23.0;
	crackNp.Type = 2.0;
	crackNp.Octaves = 2.0;

	// The network drifts with the crust instead of sitting still on it.
	float2 crackUV = uv + float2(0.06, 0.021) * time * np.Speed;
	float thin = LS_FBM(float3(crackUV * thinCrackScale, 2.7), crackNp);

	float width = 1.0 / max(crackSharpness, 0.001);

	float shoulder = smoothstep(crackThreshold - width * 2.6, crackThreshold - width * 0.4, thin);
	float flank    = smoothstep(crackThreshold - width * 0.9, crackThreshold + width * 0.5, thin);
	float core     = smoothstep(crackThreshold + width * 0.2, crackThreshold + width * 0.9, thin);

	// Weighted so the eye reads a slope into the crack rather than an edge:
	// most of the area is shoulder, and only the very middle is molten.
	float heat = saturate(shoulder * 0.30 + flank * 0.45 + core * 0.55);

	heat *= 0.75 + 0.25 * saturate(1.0 - plateHeight);

	LS_NoiseParams emberNp = np;
	emberNp.Seed = np.Seed + 11.0;
	emberNp.Type = 1.0;
	emberNp.Octaves = 2.0;
	emberNp.Size = 1.0;
	float ember = LS_FBM(float3(uv * emberScale, time * emberSpeed), emberNp) * 0.5 + 0.5;
	heat = saturate(heat * (1.0 + ember * emberAmount));

	// veinGlow brightens the very centre of a channel, keeping the hottest
	// pixels a thin line inside an already thin crack.
	float spine = smoothstep(crackThreshold + width * 0.5, crackThreshold + width, thin);
	return saturate(heat + spine * veinGlow);
}

LS_Surface LS_ShadeLava(float3 worldNormal, float hC, float hU, float hV, float amplitude,
                        float heat, float time, float2 uv,
                        float3 colorRock, float3 colorEmber, float3 colorHot, float3 colorCore,
                        float glowStrength, float roughRock, float roughHot)
{
	LS_Surface s;
	LS_SurfaceFromHeights(worldNormal, hC * amplitude, hU * amplitude, hV * amplitude,
	                      s.Offset, s.Normal);

	float3 warm = lerp(colorRock, colorEmber, smoothstep(0.05, 0.45, heat));
	float3 hot  = lerp(warm, colorHot, smoothstep(0.30, 0.75, heat));
	float3 col  = lerp(hot, colorCore, smoothstep(0.65, 1.0, heat));

	float pulse = 0.85 + 0.15 * sin(time * 1.1 + uv.x * 9.0 + uv.y * 5.0);

	s.BaseColor = colorRock * lerp(1.0, 0.20, smoothstep(0.60, 0.95, heat));

	float coreBoost = 1.0 + smoothstep(0.82, 1.0, heat) * 1.5;
	s.Emissive = col * pow(heat, 1.4) * glowStrength * pulse * coreBoost;

	s.Emissive += colorEmber * 0.030 * pulse;

	// Molten channels are wet-looking and glossy, crust is matte and rough.
	s.Roughness = lerp(roughRock, roughHot, smoothstep(0.25, 0.85, heat));
	return s;
}

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
