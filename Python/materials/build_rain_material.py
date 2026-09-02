# =============================================================================
#  build_rain_material.py
#
#  LVL 7 (bonus) - builds M_Rain: procedural raindrop ripples on a water
#  surface. Three offset layers of cells; every cell spawns a drop at a
#  random position/phase, each drop rings outward as a damped cosine wave.
#  Fully procedural (no interaction, no render target) and instantly
#  readable - drops, rings, water.
#
#  ONE Custom node: color needs no camera, so displacement and shading share
#  a single vertex-safe node.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_rain_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Rain"
INSTANCE_NAME = "MI_Rain_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

SHADER_CODE = """LS_Surface S = LiquidSim_RainShader(
    WorldNormal, UV, Time,
    BaseTexture, BaseTextureSampler,
    BaseNormalMap, BaseNormalMapSampler,
    BaseRoughnessMap, BaseRoughnessMapSampler,
    BaseTiling, BaseTint, NormalStrength, RoughnessMapInfluence,
    DropRate, RingSpeed, RingWidth, RingFrequency,
    DropDensity, SizeVariation, Amplitude,
    WetPatchScale, WetPatchContrast, WetDarkening,
    RoughnessDry, RoughnessWet);
Normal = S.Normal;
BaseColor = S.BaseColor;
Roughness = S.Roughness;
return S.Offset;"""

# The ground is a real texture (assign your downloaded asphalt/concrete to
# the BaseTexture parameter on the instance); rain adds wet darker glossy
# patches ("розводи") plus the drop rings rippling the surface.
# NormalStrength/RoughnessMapInfluence default to 0 - raise them after
# assigning your normal/roughness maps on the instance
SCALAR_PARAMS = [
    ("BaseTiling", 3.0),
    ("NormalStrength", 0.0),
    ("RoughnessMapInfluence", 0.0),
    ("DropRate", 0.9),
    ("RingSpeed", 0.32),
    ("RingWidth", 0.06),
    ("RingFrequency", 55.0),
    ("DropDensity", 0.75),
    ("SizeVariation", 0.7),
    ("Amplitude", 11.0),
    ("WetPatchScale", 3.5),
    ("WetPatchContrast", 1.2),
    ("WetDarkening", 0.45),
    ("RoughnessDry", 0.55),
    ("RoughnessWet", 0.05),
]

COLOR_PARAMS = [
    ("BaseTint", unreal.LinearColor(1.0, 1.0, 1.0, 1.0)),
]


def log(msg):
    unreal.log("[Rain] {0}".format(msg))


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

    base_tex = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -700, 200)
    base_tex.set_editor_property("parameter_name", "BaseTexture")

    base_normal = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -700, 280)
    base_normal.set_editor_property("parameter_name", "BaseNormalMap")

    base_rough = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -700, 360)
    base_rough.set_editor_property("parameter_name", "BaseRoughnessMap")

    shader = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
    shader.set_editor_property("code", SHADER_CODE)
    shader.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shader.set_editor_property("description", "Rain Shader")
    shader.set_editor_property("include_file_paths", [INCLUDE_PATH])

    input_names = (["WorldNormal", "UV", "Time",
                    "BaseTexture", "BaseNormalMap", "BaseRoughnessMap"]
                   + [n for n, _ in SCALAR_PARAMS]
                   + [n for n, _ in COLOR_PARAMS])
    inputs = []
    for name in input_names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    shader.set_editor_property("inputs", inputs)

    outs = []
    for name, out_type in [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("BaseColor", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)]:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", out_type)
        outs.append(co)
    shader.set_editor_property("additional_outputs", outs)

    ML.connect_material_expressions(vertex_normal, "", shader, "WorldNormal")
    ML.connect_material_expressions(texcoord, "", shader, "UV")
    ML.connect_material_expressions(time_node, "", shader, "Time")
    ML.connect_material_expressions(base_tex, "", shader, "BaseTexture")
    ML.connect_material_expressions(base_normal, "", shader, "BaseNormalMap")
    ML.connect_material_expressions(base_rough, "", shader, "BaseRoughnessMap")

    y = 250
    for name, default in SCALAR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Rain")
        ML.connect_material_expressions(p, "", shader, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Rain")
        ML.connect_material_expressions(p, "", shader, name)
        y += 130

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, shader, "None")
    ML.connect_material_property(shader, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shader, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shader, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 500)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 1.0)
    specular.set_editor_property("group", "Rain")
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
