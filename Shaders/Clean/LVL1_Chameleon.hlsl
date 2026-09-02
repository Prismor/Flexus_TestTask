// =============================================================================
//  Chameleon
//
//  View-angle iridescence with per-band roughness and a Fresnel-weighted
//  reflection. No displacement - this one is pure shading.
//
//  Portable HLSL - no engine API. The same text compiles in Unreal and Unity;
//  for GLSL add the six-line prelude (see Shaders/Shadertoy/).
// =============================================================================

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
