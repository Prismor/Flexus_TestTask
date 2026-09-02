# =============================================================================
#  build_lava_material.py
#
#  LVL 8 (bonus) - builds M_Lava: slow ridged-FBM rock plates with molten
#  glowing cracks. The ridged noise's sharp valleys become the cracks; the
#  deeper the valley, the hotter the emissive, with a slow pulse. One
#  vertex-safe Custom node (no camera needed).
#
#  The placed station is up to the user (the level is hand-maintained):
#  drag MI_Lava_Default onto a copy of the client plane.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_lava_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Lava"
INSTANCE_NAME = "MI_Lava_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

SHADER_CODE = """LS_Surface S = LiquidSim_LavaShader(
    WorldNormal, UV, Time,
    NoiseSize, NoiseSpeed, Amplitude,
    NoiseSeed, NoiseOctaves, Lacunarity, Persistence, WarpStrength,
    CrackThreshold, CrackSharpness, GlowStrength,
    EmberScale, EmberSpeed, EmberAmount,
    StoneScale, StoneAmount, ThinCrackScale, ThinCrackDepth, VeinGlow,
    ColorRock, ColorEmber, ColorHot, ColorCore,
    RoughnessRock, RoughnessHot);
Normal = S.Normal;
BaseColor = S.BaseColor;
Roughness = S.Roughness;
EmissiveOut = S.Emissive;
return S.Offset;"""

# CrackThreshold sits INSIDE the ridged FBM's actual range - the previous
# -0.15 was below almost all values, so no cracks ever lit up and the
# surface read as plain gray-black noise
# wide domain-warped molten rivers between dark plates, hot core inside
SCALAR_PARAMS = [
    ("NoiseSize", 7.5),
    ("NoiseSpeed", 0.06),     # lava moves slowly
    ("Amplitude", 42.0),
    ("NoiseSeed", 7.0),
    ("NoiseOctaves", 3.0),
    ("Lacunarity", 2.0),
    ("Persistence", 0.45),
    ("WarpStrength", 1.3),
    ("CrackThreshold", 0.82),
    ("CrackSharpness", 4.5),  # tighter crust/melt boundary
    ("GlowStrength", 2.5),
    ("EmberScale", 6.0),
    ("EmberSpeed", 0.15),
    ("EmberAmount", 0.30),    # now MULTIPLIES heat, so it no longer lifts the cold floor
    ("StoneScale", 22.0),
    ("StoneAmount", 0.07),
    ("ThinCrackScale", 10.0),
    ("ThinCrackDepth", 0.08),
    ("VeinGlow", 0.22),       # veins are accents, not a second heat source
    ("RoughnessRock", 0.75),
    ("RoughnessHot", 0.35),
]

# 4-stop heat gradient: crust -> smouldering dark red -> orange -> HDR core
COLOR_PARAMS = [
    # 0.030 measured out at 0.09-0.15 linear on screen under this scene lighting
    # (roughly 3-5x), which reads as grey-brown stone rather than cooled basalt.
    # A third of that lands near 0.04 linear - dark enough that the molten
    # channels are the only bright thing on the surface.
    ("ColorRock", unreal.LinearColor(0.010, 0.005, 0.004, 1.0)),
    ("ColorEmber", unreal.LinearColor(0.35, 0.03, 0.005, 1.0)),
    ("ColorHot", unreal.LinearColor(1.20, 0.22, 0.02, 1.0)),
    ("ColorCore", unreal.LinearColor(2.00, 0.95, 0.20, 1.0)),
]


def log(msg):
    unreal.log("[Lava] {0}".format(msg))


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
    texcoord = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, 0)
    time_node = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -700, 100)
    vertex_normal = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -700, -150)

    shader = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
    shader.set_editor_property("code", SHADER_CODE)
    shader.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shader.set_editor_property("description", "Lava Shader")
    shader.set_editor_property("include_file_paths", [INCLUDE_PATH])

    input_names = (["WorldNormal", "UV", "Time"]
                   + [n for n, _ in SCALAR_PARAMS[:19]]
                   + [n for n, _ in COLOR_PARAMS]
                   + [n for n, _ in SCALAR_PARAMS[19:]])
    inputs = []
    for name in input_names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    shader.set_editor_property("inputs", inputs)

    outs = []
    for name, out_type in [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("BaseColor", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("EmissiveOut", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)]:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", out_type)
        outs.append(co)
    shader.set_editor_property("additional_outputs", outs)

    ML.connect_material_expressions(vertex_normal, "", shader, "WorldNormal")
    ML.connect_material_expressions(texcoord, "", shader, "UV")
    ML.connect_material_expressions(time_node, "", shader, "Time")

    y = 250
    for name, default in SCALAR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Lava")
        ML.connect_material_expressions(p, "", shader, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Lava")
        ML.connect_material_expressions(p, "", shader, name)
        y += 130

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, shader, "None")
    ML.connect_material_property(shader, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shader, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shader, "EmissiveOut", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(shader, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 500)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 0.5)
    specular.set_editor_property("group", "Lava")
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
