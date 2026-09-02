# =============================================================================
#  build_mobile_materials.py
#
#  Builds the LOW-COST variants of the heavy effects for the Android build.
#  Same graphs as the desktop materials, but the Custom node calls the
#  *Cheap* functions from LiquidSimCore.ush and every material is flagged
#  "used with mobile".
#
#  The spec grades performance first, and a phone has a fraction of a
#  desktop's shading budget - so the fine detail a small screen cannot
#  resolve anyway (voronoi cobbles, domain warping, the third rain layer,
#  glitter) is dropped, while the silhouette and the motion are kept.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_mobile_materials.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials/Mobile"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary


def log(msg):
    unreal.log("[Mobile] {0}".format(msg))


def make_custom(mat, x, y, code, description, input_names, outputs):
    node = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property("code", code)
    node.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    node.set_editor_property("description", description)
    node.set_editor_property("include_file_paths", [INCLUDE_PATH])

    inputs = []
    for name in input_names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    node.set_editor_property("inputs", inputs)

    outs = []
    for name, t in outputs:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", t)
        outs.append(co)
    node.set_editor_property("additional_outputs", outs)
    return node


def new_material(name, two_sided=False):
    full = "{0}/{1}".format(PACKAGE_PATH, name)
    if AL.does_asset_exist(full):
        AL.delete_asset(full)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(name, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("tangent_space_normal", False)
    if two_sided:
        mat.set_editor_property("two_sided", True)
    # mobile needs vertex-shader displacement explicitly enabled
    try:
        mat.set_editor_property("use_material_attributes", False)
        mat.set_editor_property("num_customized_u_vs", 0)
    except Exception:
        pass
    return mat


def add_scalars(mat, node, params, group, x=-800, y0=200, step=70):
    y = y0
    for name, default in params:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, x, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", group)
        ML.connect_material_expressions(p, "", node, name)
        y += step
    return y


def add_colors(mat, node, params, group, x=-800, y0=800, step=130):
    y = y0
    for name, default in params:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, x, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", group)
        ML.connect_material_expressions(p, "", node, name)
        y += step
    return y


def finish(mat, name, stats_label):
    ML.recompile_material(mat)
    AL.save_loaded_asset(mat)
    stats = ML.get_statistics(mat)
    log("{0}: {1} instructions, {2} samplers".format(
        stats_label,
        stats.get_editor_property("num_pixel_shader_instructions"),
        stats.get_editor_property("num_samplers")))

    inst = "MI_{0}_Mobile".format(name)
    full = "{0}/{1}".format(PACKAGE_PATH, inst)
    if AL.does_asset_exist(full):
        AL.delete_asset(full)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(inst, PACKAGE_PATH, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    ML.set_material_instance_parent(mi, mat)
    AL.save_loaded_asset(mi)


# =============================================================================
#  LVL 2 - displacement: two octaves instead of three
# =============================================================================
DISPLACE_CODE = """float tap = 0.05 / max(NoiseSize, 0.001);
LS_NoiseParams np = LiquidSim_MakeNoise(NoiseSize, NoiseSpeed, NoiseSeed, 0.0,
                                        NoiseOctaves, Lacunarity, Persistence);
float hC = LS_HeightPerlinCheap(UV, Time, np);
float hU = LS_HeightPerlinCheap(UV + float2(tap, 0.0), Time, np);
float hV = LS_HeightPerlinCheap(UV + float2(0.0, tap), Time, np);

LS_Surface S = LS_ShadeDisplacement(WorldNormal, hC, hU, hV, Amplitude,
                                    ColorLow, ColorMid, ColorHigh, RoughnessValue);
Normal = S.Normal;
BaseColor = S.BaseColor;
Roughness = S.Roughness;
return S.Offset;"""


def build_displacement():
    mat = new_material("M_Displacement_Mobile")
    uv = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, -150)
    t = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, -80)
    n = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -230)

    scal = [("NoiseSize", 5.0), ("NoiseSpeed", 0.16), ("Amplitude", 130.0),
            ("NoiseSeed", 0.0), ("NoiseType", 0.0),   # value noise: cheaper than gradient
            ("NoiseOctaves", 2.0),                    # was 3
            ("Lacunarity", 2.0), ("Persistence", 0.45), ("RoughnessValue", 0.22)]
    cols = [("ColorLow", unreal.LinearColor(0.08, 0.20, 0.80, 1.0)),
            ("ColorMid", unreal.LinearColor(0.06, 0.45, 0.42, 1.0)),
            ("ColorHigh", unreal.LinearColor(0.22, 0.85, 0.28, 1.0))]

    node = make_custom(mat, -300, 0, DISPLACE_CODE, "Displacement (mobile)",
                       ["WorldNormal", "UV", "Time"] + [k for k, _ in scal[:8]]
                       + [k for k, _ in cols] + ["RoughnessValue"],
                       [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("BaseColor", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    ML.connect_material_expressions(n, "", node, "WorldNormal")
    ML.connect_material_expressions(uv, "", node, "UV")
    ML.connect_material_expressions(t, "", node, "Time")
    y = add_scalars(mat, node, scal, "Displacement")
    add_colors(mat, node, cols, "Displacement", y0=y)

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, node, "None")
    ML.connect_material_property(node, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(node, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(node, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)
    finish(mat, "Displacement", "LVL2 Displacement")


# =============================================================================
#  LVL 6 - vortex: no domain warping, no glitter
# =============================================================================
VORTEX_CODE = """float tap = 0.01;
LS_NoiseParams np = LiquidSim_MakeNoise(NoiseSize, NoiseSpeed, NoiseSeed, 1.0,
                                        NoiseOctaves, Lacunarity, Persistence);
float hC = LS_HeightVortexCheap(UV, Time, np, SwirlStrength, SwirlTightness,
                                SwirlSpeed, FunnelDepth, FunnelTightness) * NoiseAmplitude;
float hU = LS_HeightVortexCheap(UV + float2(tap, 0.0), Time, np, SwirlStrength, SwirlTightness,
                                SwirlSpeed, FunnelDepth, FunnelTightness) * NoiseAmplitude;
float hV = LS_HeightVortexCheap(UV + float2(0.0, tap), Time, np, SwirlStrength, SwirlTightness,
                                SwirlSpeed, FunnelDepth, FunnelTightness) * NoiseAmplitude;
float3 offset, nrm;
LS_SurfaceFromHeights(WorldNormal, hC, hU, hV, offset, nrm);
Normal = nrm;
CentreDist = length(UV - 0.5);
return offset;"""

VORTEX_SHADE = """float pulse = 1.0 + PulseAmount * sin(Time * PulseSpeed);
float core = exp(-CentreDist * CentreDist * CoreTightness) * pulse;
// Colour follows the SWIRL. viewDir made the hue change with the camera; a
// flat radial ramp drained the colour instead. A spiral coordinate keeps the
// bands winding into the funnel.
float2 cc = UV - 0.5;
float ang = atan2(cc.y, cc.x);
float spiral = sin(ang * 2.0 - CentreDist * 16.0 + Time * PulseSpeed * 0.6);
float noiseTerm = DisplacedNormal.x * 1.6 + DisplacedNormal.y * 1.2;
float band = saturate(spiral * 0.32 + noiseTerm * 0.55 + 0.5);
float3 col = lerp(ColorA, ColorB, smoothstep(0.0, 0.55, band));
col = lerp(col, ColorC, smoothstep(0.45, 1.0, band));
Emissive = CoreColor * core * CoreGlow;
Roughness = lerp(0.25, 0.06, saturate(core));
return col;"""


def build_vortex():
    mat = new_material("M_Vortex_Mobile", two_sided=True)
    uv = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    t = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 80)
    n = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -200)
    cam = ML.create_material_expression(mat, unreal.MaterialExpressionCameraVectorWS, -800, -120)

    dscal = [("NoiseSize", 4.0), ("NoiseSpeed", 0.6), ("NoiseAmplitude", 4.0),
             ("NoiseSeed", 3.0), ("NoiseOctaves", 2.0),   # was 4
             ("Lacunarity", 2.0), ("Persistence", 0.5),
             ("SwirlStrength", 3.5), ("SwirlTightness", 4.0), ("SwirlSpeed", 0.4),
             ("FunnelDepth", 6.0), ("FunnelTightness", 10.0)]

    disp = make_custom(mat, -350, 0, VORTEX_CODE, "Vortex Displace (mobile)",
                       ["WorldNormal", "UV", "Time"] + [k for k, _ in dscal],
                       [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("CentreDist", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    ML.connect_material_expressions(n, "", disp, "WorldNormal")
    ML.connect_material_expressions(uv, "", disp, "UV")
    ML.connect_material_expressions(t, "", disp, "Time")
    add_scalars(mat, disp, dscal, "Vortex", y0=200)

    sscal = [("CoreGlow", 1.2), ("CoreTightness", 60.0),
             ("PulseSpeed", 2.0), ("PulseAmount", 0.35)]
    scols = [("ColorA", unreal.LinearColor(0.55, 0.05, 0.65, 1.0)),
             ("ColorB", unreal.LinearColor(0.10, 0.15, 0.60, 1.0)),
             ("ColorC", unreal.LinearColor(0.10, 0.90, 0.90, 1.0)),
             ("CoreColor", unreal.LinearColor(0.60, 1.60, 2.00, 1.0))]

    shade = make_custom(mat, 50, 0, VORTEX_SHADE, "Vortex Shade (mobile)",
                        ["DisplacedNormal", "CameraVec", "Time", "CentreDist"]
                        + [k for k, _ in scols] + [k for k, _ in sscal],
                        [("Emissive", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                         ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    ML.connect_material_expressions(disp, "Normal", shade, "DisplacedNormal")
    ML.connect_material_expressions(disp, "CentreDist", shade, "CentreDist")
    ML.connect_material_expressions(cam, "", shade, "CameraVec")
    ML.connect_material_expressions(t, "", shade, "Time")
    y = add_scalars(mat, shade, sscal, "Vortex", x=-450, y0=200)
    add_colors(mat, shade, scols, "Vortex", x=-450, y0=y)

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, disp, "None")
    ML.connect_material_property(disp, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shade, "", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shade, "Emissive", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(shade, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)
    finish(mat, "Vortex", "LVL6 Vortex")


# =============================================================================
#  LVL 8 - lava: no cobbles, no grooves, no warp, no veins
# =============================================================================
LAVA_CODE = """float tap = 0.006;
LS_NoiseParams np = LiquidSim_MakeNoise(NoiseSize, NoiseSpeed, NoiseSeed, 2.0,
                                        NoiseOctaves, Lacunarity, Persistence);
float hC = LS_HeightLavaCheap(UV, Time, np);
float hU = LS_HeightLavaCheap(UV + float2(tap, 0.0), Time, np);
float hV = LS_HeightLavaCheap(UV + float2(0.0, tap), Time, np);

float heat = LS_LavaHeatCheap(UV, Time, hC, np, CrackThreshold, CrackSharpness,
                              EmberScale, EmberSpeed, EmberAmount);

LS_Surface S = LS_ShadeLava(WorldNormal, hC, hU, hV, Amplitude, heat, Time, UV,
                            ColorRock, ColorEmber, ColorHot, ColorCore,
                            GlowStrength, RoughnessRock, RoughnessHot);
Normal = S.Normal;
BaseColor = S.BaseColor;
EmissiveOut = S.Emissive;
Roughness = S.Roughness;
return S.Offset;"""


def build_lava():
    mat = new_material("M_Lava_Mobile")
    uv = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    t = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 80)
    n = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -160)

    scal = [("NoiseSize", 2.2), ("NoiseSpeed", 0.06), ("Amplitude", 60.0),
            ("NoiseSeed", 7.0), ("NoiseOctaves", 2.0),   # was 3
            ("Lacunarity", 2.0), ("Persistence", 0.45),
            ("CrackThreshold", 0.82), ("CrackSharpness", 7.0), ("GlowStrength", 2.5),
            ("EmberScale", 6.0), ("EmberSpeed", 0.15), ("EmberAmount", 0.30),
            ("RoughnessRock", 0.75), ("RoughnessHot", 0.35)]
    cols = [("ColorRock", unreal.LinearColor(0.010, 0.005, 0.004, 1.0)),
            ("ColorEmber", unreal.LinearColor(0.35, 0.03, 0.005, 1.0)),
            ("ColorHot", unreal.LinearColor(1.20, 0.22, 0.02, 1.0)),
            ("ColorCore", unreal.LinearColor(2.00, 0.95, 0.20, 1.0))]

    node = make_custom(mat, -300, 0, LAVA_CODE, "Lava (mobile)",
                       ["WorldNormal", "UV", "Time"] + [k for k, _ in scal[:13]]
                       + [k for k, _ in cols] + [k for k, _ in scal[13:]],
                       [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("BaseColor", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("EmissiveOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    ML.connect_material_expressions(n, "", node, "WorldNormal")
    ML.connect_material_expressions(uv, "", node, "UV")
    ML.connect_material_expressions(t, "", node, "Time")
    y = add_scalars(mat, node, scal, "Lava", y0=200)
    add_colors(mat, node, cols, "Lava", y0=y)

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, node, "None")
    ML.connect_material_property(node, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(node, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(node, "EmissiveOut", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(node, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)
    finish(mat, "Lava", "LVL8 Lava")


# =============================================================================
#  LVL 7 - rain: two drop layers instead of three, no normal/roughness maps
# =============================================================================
RAIN_CODE = """float tap = 0.004;
float hC = LS_HeightRainCheap(UV, Time, DropRate, RingSpeed, RingWidth, RingFrequency, DropDensity, SizeVariation);
float hU = LS_HeightRainCheap(UV + float2(tap, 0.0), Time, DropRate, RingSpeed, RingWidth, RingFrequency, DropDensity, SizeVariation);
float hV = LS_HeightRainCheap(UV + float2(0.0, tap), Time, DropRate, RingSpeed, RingWidth, RingFrequency, DropDensity, SizeVariation);

float3 offset, nrm;
LS_SurfaceFromHeights(WorldNormal, hC * Amplitude, hU * Amplitude, hV * Amplitude, offset, nrm);
Normal = nrm;
BaseColor = lerp(ColorLow, ColorHigh, saturate(hC * 1.6 + 0.5));
Roughness = RoughnessValue;
return offset;"""


def build_rain():
    mat = new_material("M_Rain_Mobile")
    uv = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    t = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 80)
    n = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -160)

    scal = [("DropRate", 0.9), ("RingSpeed", 0.32), ("RingWidth", 0.06),
            ("RingFrequency", 55.0), ("DropDensity", 0.75), ("SizeVariation", 0.7),
            ("Amplitude", 11.0), ("RoughnessValue", 0.12)]
    cols = [("ColorLow", unreal.LinearColor(0.02, 0.05, 0.10, 1.0)),
            ("ColorHigh", unreal.LinearColor(0.45, 0.60, 0.75, 1.0))]

    node = make_custom(mat, -300, 0, RAIN_CODE, "Rain (mobile)",
                       ["WorldNormal", "UV", "Time"] + [k for k, _ in scal[:7]]
                       + [k for k, _ in cols] + ["RoughnessValue"],
                       [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("BaseColor", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                        ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])
    ML.connect_material_expressions(n, "", node, "WorldNormal")
    ML.connect_material_expressions(uv, "", node, "UV")
    ML.connect_material_expressions(t, "", node, "Time")
    y = add_scalars(mat, node, scal, "Rain", y0=200)
    add_colors(mat, node, cols, "Rain", y0=y)

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, node, "None")
    ML.connect_material_property(node, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(node, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(node, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)
    finish(mat, "Rain", "LVL7 Rain")


def main():
    log("=== build start ===")
    build_displacement()
    build_vortex()
    build_rain()
    build_lava()
    log("=== build done ===")


main()
