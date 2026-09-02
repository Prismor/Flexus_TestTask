# =============================================================================
#  build_boss_material.py
#
#  LVL 5 (Boss) - builds M_Boss: every previous technique in one material.
#  Two Custom nodes (the engine-forced vertex/pixel split - CameraVector
#  does not exist in the vertex shader where WPO compiles):
#    Boss Displace - FBM noise + painted heightmap ADDED per tap (additive
#        blend, like the reference), heights sampled inside the node.
#    Boss Shade    - near-black idle base breathing with the noise,
#        iridescent fluid where paint is active, emissive troughs, foam.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_boss_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Boss"
INSTANCE_NAME = "MI_Boss_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

DISPLACE_CODE = """FLiquidSimBossDisplace D = LiquidSim_BossDisplace(
    WorldNormal, UV, Time, HeightMap, HeightMapSampler,
    NoiseSize, NoiseSpeed, NoiseAmplitude,
    NoiseSeed, NoiseType, NoiseOctaves, Lacunarity, Persistence,
    PaintAmplitude);
Normal = D.Normal;
NoiseHeight = D.NoiseHeight;
PaintHeight = D.PaintHeight;
Wetness = D.Wetness;
return D.Offset;"""

SHADE_CODE = """LS_Surface S = LiquidSim_BossShade(
    DisplacedNormal, CameraVec, UV, Time, PaintHeight, NoiseHeight, Wetness,
    BaseDarkColor, ColorA, ColorB, ColorC, TroughColor, EdgeColor, FoamColor,
    ActivitySensitivity, TroughSensitivity,
    TroughGlow, InteriorGlow, EdgeDither, FoamIntensity,
    IdleBreathing, RoughnessIdle, RoughnessActive,
    SparkleScale, SparkleIntensity);
Emissive = S.Emissive;
Roughness = S.Roughness;
return S.BaseColor;"""

DISPLACE_SCALARS = [
    ("NoiseSize", 5.0),
    ("NoiseSpeed", 0.3),
    ("NoiseAmplitude", 60.0),
    ("NoiseSeed", 0.0),
    ("NoiseType", 1.0),
    ("NoiseOctaves", 3.0),   # 4 octaves + big paint amplitude read as ragged
    ("Lacunarity", 2.0),
    ("Persistence", 0.45),
    ("PaintAmplitude", 300.0),
]

# ActivitySensitivity multiplies the wetness coverage (0..1);
# TroughSensitivity multiplies negative height for the hot trough color
SHADE_SCALARS = [
    ("ActivitySensitivity", 2.5),
    ("TroughSensitivity", 6.0),
    ("TroughGlow", 3.0),
    ("InteriorGlow", 1.2),
    ("EdgeDither", 0.6),
    ("FoamIntensity", 0.5),
    ("IdleBreathing", 0.35),
    ("RoughnessIdle", 0.12),   # glossy dark surface - visible reflections
    ("RoughnessActive", 0.08),
    ("SparkleScale", 260.0),
    ("SparkleIntensity", 0.35),
]

# reference still: violet/magenta fluid body, scattered blue edge pixels on
# the coverage boundary, hot orange heart inside the stroke
COLOR_PARAMS = [
    ("BaseDarkColor", unreal.LinearColor(0.010, 0.010, 0.014, 1.0)),
    ("ColorA", unreal.LinearColor(0.35, 0.05, 0.85, 1.0)),   # grazing deep violet
    ("ColorB", unreal.LinearColor(0.95, 0.15, 0.75, 1.0)),   # mid magenta-pink
    ("ColorC", unreal.LinearColor(0.35, 0.65, 1.00, 1.0)),   # facing soft blue
    ("TroughColor", unreal.LinearColor(1.00, 0.35, 0.03, 1.0)),
    ("EdgeColor", unreal.LinearColor(0.15, 0.30, 1.00, 1.0)),
    ("FoamColor", unreal.LinearColor(1.0, 1.0, 1.0, 1.0)),
]


def log(msg):
    unreal.log("[Boss] {0}".format(msg))


def make_custom(mat, x, y, code, description, input_names, additional_outputs):
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
    for name, out_type in additional_outputs:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", out_type)
        outs.append(co)
    node.set_editor_property("additional_outputs", outs)
    return node


def make_material():
    full_path = "{0}/{1}".format(PACKAGE_PATH, MATERIAL_NAME)
    if AL.does_asset_exist(full_path):
        log("deleting previous {0}".format(full_path))
        AL.delete_asset(full_path)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MATERIAL_NAME, PACKAGE_PATH, unreal.Material,
                             unreal.MaterialFactoryNew())
    if mat is None:
        raise RuntimeError("could not create material asset")

    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("tangent_space_normal", False)
    log("created {0}".format(full_path))
    return mat


def build_graph(mat):
    texcoord = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, 0)
    time_node = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, 100)
    vertex_normal = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -200)
    cam_vec = ML.create_material_expression(mat, unreal.MaterialExpressionCameraVectorWS, -800, -100)

    height_tex = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -800, 200)
    height_tex.set_editor_property("parameter_name", "HeightMap")

    displace = make_custom(
        mat, -350, 0, DISPLACE_CODE, "Boss Displace",
        ["WorldNormal", "UV", "Time", "HeightMap"] + [n for n, _ in DISPLACE_SCALARS],
        [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
         ("NoiseHeight", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
         ("PaintHeight", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
         ("Wetness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])

    ML.connect_material_expressions(vertex_normal, "", displace, "WorldNormal")
    ML.connect_material_expressions(texcoord, "", displace, "UV")
    ML.connect_material_expressions(time_node, "", displace, "Time")
    ML.connect_material_expressions(height_tex, "", displace, "HeightMap")

    shade = make_custom(
        mat, 0, 0, SHADE_CODE, "Boss Shade",
        ["DisplacedNormal", "CameraVec", "UV", "Time", "PaintHeight", "NoiseHeight", "Wetness"]
        + [n for n, _ in COLOR_PARAMS]
        + [n for n, _ in SHADE_SCALARS],
        [("Emissive", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
         ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])

    ML.connect_material_expressions(displace, "Normal", shade, "DisplacedNormal")
    ML.connect_material_expressions(displace, "NoiseHeight", shade, "NoiseHeight")
    ML.connect_material_expressions(displace, "PaintHeight", shade, "PaintHeight")
    ML.connect_material_expressions(displace, "Wetness", shade, "Wetness")
    ML.connect_material_expressions(cam_vec, "", shade, "CameraVec")
    ML.connect_material_expressions(texcoord, "", shade, "UV")
    ML.connect_material_expressions(time_node, "", shade, "Time")

    y = 350
    for name, default in DISPLACE_SCALARS + SHADE_SCALARS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Boss")
        target = shade if name in dict(SHADE_SCALARS) else displace
        ML.connect_material_expressions(p, "", target, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Boss")
        ML.connect_material_expressions(p, "", shade, name)
        y += 130

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, displace, "None")
    ML.connect_material_property(displace, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shade, "", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shade, "Emissive", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(shade, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    metallic = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, 0, 550)
    metallic.set_editor_property("parameter_name", "Metallic")
    metallic.set_editor_property("default_value", 0.3)
    metallic.set_editor_property("group", "Boss")
    ML.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, 0, 650)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 1.0)
    specular.set_editor_property("group", "Boss")
    ML.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)


def make_instance(mat):
    full_path = "{0}/{1}".format(PACKAGE_PATH, INSTANCE_NAME)
    if AL.does_asset_exist(full_path):
        AL.delete_asset(full_path)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(INSTANCE_NAME, PACKAGE_PATH, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    ML.set_material_instance_parent(mi, mat)
    AL.save_loaded_asset(mi)
    log("created {0}".format(full_path))


def main():
    log("=== build start ===")
    mat = make_material()
    build_graph(mat)

    ML.recompile_material(mat)
    AL.save_loaded_asset(mat)
    log("material compiled and saved")

    stats = ML.get_statistics(mat)
    log("shader instructions (base pass): {0}".format(
        stats.get_editor_property("num_pixel_shader_instructions")))
    log("texture samplers used: {0}".format(
        stats.get_editor_property("num_samplers")))

    make_instance(mat)
    log("=== build done ===")


main()
