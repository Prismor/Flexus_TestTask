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

// Three offset grids so drops don't visibly repeat on a lattice; each cell's hashed
// rnd/phase decides its one drop's position, size and timing - age = frac(time*rate + phase) loops it forever.
float LS_HeightRain(float2 uv, float time,
                    float dropRate, float ringSpeed, float ringWidth, float ringFrequency,
                    float dropDensity, float sizeVariation)
{
	float h = 0.0;

	for (int k = 0; k < 3; ++k)
	{
		float fk = float(k);
		float2 gridUV = uv * (6.0 + fk * 5.0) + fk * 17.31;
		float2 cell = floor(gridUV);
		float2 f = frac(gridUV);

		float3 seed = float3(cell, fk * 13.7);
		float3 rnd = LS_Hash33(seed);
		float2 dropPos = rnd.xy * 0.4 + 0.3;
		float phase = LS_Hash31(seed + 5.0);

		float alive = step(1.0 - dropDensity, LS_Hash31(seed + 11.0));
		float sizeMul = lerp(1.0 - sizeVariation * 0.6, 1.0 + sizeVariation, rnd.z);

		float age = frac(time * dropRate * lerp(0.8, 1.3, rnd.z) + phase);
		float dist = length(f - dropPos);
		float ringR = age * ringSpeed * sizeMul;

		float envelope = exp(-pow((dist - ringR) / max(ringWidth * sizeMul, 0.0001), 2.0));
		float borderFade = 1.0 - smoothstep(0.30, 0.45, dist);

		h += cos((dist - ringR) * ringFrequency) * envelope * borderFade
		   * (1.0 - age) * (1.0 - age) * alive * sizeMul;
	}

	return h / 3.0;
}

LS_Surface LS_ShadeRain(float3 rippleNormal, float hC, float3 groundAlbedo,
                        float groundRoughness, float wetMask,
                        float wetDarkening, float roughnessDry, float roughnessWet)
{
	LS_Surface s;
	s.Offset = float3(0.0, 0.0, 0.0); // caller supplies the displacement
	s.Normal = rippleNormal;

	s.BaseColor = groundAlbedo * lerp(1.0, 1.0 - saturate(wetDarkening), wetMask);
	s.BaseColor += saturate(hC) * wetMask * 0.15; // bright film on ring crests
	s.Emissive = float3(0.0, 0.0, 0.0);
	s.Roughness = lerp(lerp(roughnessDry, groundRoughness, 0.0), roughnessWet, wetMask);
	return s;
}

// Slow large-scale mask of wet patches / streaks left by rain.
float LS_WetPatchMask(float2 uv, float time, LS_NoiseParams np, float scale, float contrast)
{
	LS_NoiseParams wetNp = np;
	wetNp.Type = 1.0;
	wetNp.Octaves = 3.0;
	// note: "patch" is a reserved word in GLSL ES - keep this name portable
	float patchNoise = LS_FBM(float3(uv * scale, time * 0.03), wetNp);
	return saturate(0.5 + patchNoise * contrast);
}

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
