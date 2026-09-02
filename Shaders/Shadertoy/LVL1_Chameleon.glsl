// HLSL -> GLSL compatibility shim.
#define float2 vec2
#define float3 vec3
#define float4 vec4
#define lerp  mix
#define frac  fract
#define atan2 atan
#define saturate(x) clamp((x), 0.0, 1.0)

// What a displaced surface hands back to the material pins.
struct LS_Surface
{
	float3 Offset;    // World Position Offset (along the surface normal)
	float3 Normal;    // normal recalculated for the displaced shape
	float3 BaseColor;
	float3 Emissive;
	float  Roughness;
};

LS_Surface LS_ShadeChameleon(float3 worldNormal, float3 viewDir,
                             float3 colorA, float3 colorB, float3 colorC,
                             float roughA, float roughB, float roughC,
                             float3 reflectionColor, float3 highlightColor,
                             float reflectivity, float gradientBoost,
                             float fresnelPower, float gradientShift)
{
	float3 n = normalize(worldNormal);
	float3 v = normalize(viewDir);
	float ndotv = pow(saturate(dot(n, v)), max(gradientShift, 0.1));

	// same banding curve for roughness as for colour
	float roughLow  = lerp(roughA, roughB, smoothstep(0.0, 0.55, ndotv));
	float roughHigh = lerp(roughB, roughC, smoothstep(0.45, 1.0, ndotv));

	float3 colLow  = lerp(colorA, colorB, smoothstep(0.0, 0.55, ndotv));
	float3 colHigh = lerp(colorB, colorC, smoothstep(0.45, 1.0, ndotv));

	LS_Surface s;
	s.Offset = float3(0.0, 0.0, 0.0);
	s.Normal = n;
	s.Roughness = lerp(roughLow, roughHigh, smoothstep(0.45, 0.55, ndotv));
	s.BaseColor = lerp(colLow, colHigh, smoothstep(0.45, 0.55, ndotv));

	float fresnel = pow(1.0 - ndotv, max(fresnelPower, 0.1));
	s.Emissive = reflectionColor * highlightColor * fresnel * reflectivity
	           + s.BaseColor * gradientBoost;
	return s;
}

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
