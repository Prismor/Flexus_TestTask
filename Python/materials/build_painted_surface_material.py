# =============================================================================
#  build_painted_surface_material.py
#
#  LVL 3/4 display material - M_PaintedSurface: ONE Custom node samples the
#  painted heightmap (TextureObject input, centre + 2 taps) inside itself,
#  displaces, rebuilds the normal, colors by signed height and gets glossier
#  where paint disturbed the surface.
#
#  Two instances:
#    MI_PaintedSurface_Default - LVL3 look (green gel, persistent paint)
#    MI_PaintedSurface_Waves   - LVL4 look (glossy slate liquid, big waves)
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_painted_surface_material.py" -unattended ^
#       -nosplash -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_PaintedSurface"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

SHADER_CODE = """LS_Surface S = LiquidSim_PaintedSurfaceShader(
    WorldNormal, UV, HeightMap, HeightMapSampler, Amplitude,
    ColorBase, ColorLow, ColorMid, ColorHigh,
    HeightColorScale, WetSensitivity, RoughnessDry, RoughnessWet);
Normal = S.Normal;
BaseColor = S.BaseColor;
Roughness = S.Roughness;
return S.Offset;"""

# WetSensitivity now multiplies the accumulated WETNESS channel (0..1), not
# |height| - coverage is solid and gradient-smooth
SCALAR_PARAMS = [
    ("Amplitude", 200.0),
    ("HeightColorScale", 9.0),
    ("WetSensitivity", 1.6),
    ("RoughnessDry", 0.45),
    ("RoughnessWet", 0.1),
]

# LVL3 green gel: much stronger color separation by depth (feedback: "colors
# too uniform") - near-black deep folds, vivid mid green, hot yellow crests
COLOR_PARAMS = [
    ("ColorBase", unreal.LinearColor(0.13, 0.42, 0.02, 1.0)),
    ("ColorLow", unreal.LinearColor(0.002, 0.05, 0.03, 1.0)),
    ("ColorMid", unreal.LinearColor(0.08, 0.65, 0.10, 1.0)),
    ("ColorHigh", unreal.LinearColor(0.95, 1.00, 0.15, 1.0)),
]

# waves = WATER (feedback): blue by default, glossy with бліки, darker
# saturated blue where pressed, white foam crests
WAVES_OVERRIDES = [
    ("ColorBase", unreal.LinearColor(0.08, 0.28, 0.55, 1.0)),
    ("ColorLow", unreal.LinearColor(0.005, 0.04, 0.22, 1.0)),
    ("ColorMid", unreal.LinearColor(0.10, 0.32, 0.60, 1.0)),
    ("ColorHigh", unreal.LinearColor(0.95, 0.98, 1.00, 1.0)),
    ("HeightColorScale", 12.0),
    ("RoughnessDry", 0.05),
    ("RoughnessWet", 0.03),
    ("WetSensitivity", 1.8),
    ("Amplitude", 300.0),
]


def log(msg):
    unreal.log("[PaintedSurface] {0}".format(msg))


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
    vertex_normal = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -700, -150)

    height_tex = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -700, 130)
    height_tex.set_editor_property("parameter_name", "HeightMap")
    # Clamp addressing, forced on the SAMPLER. Setting it on the render target
    # asset alone was not enough: a texture object in a Custom node samples
    # through the world group settings by default, which are Wrap, so a wave
    # reaching the edge still read its neighbour from the opposite edge and
    # reappeared there.
    height_tex.set_editor_property(
        "sampler_source", unreal.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS)

    shader = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
    shader.set_editor_property("code", SHADER_CODE)
    shader.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shader.set_editor_property("description", "Painted Surface Shader")
    shader.set_editor_property("include_file_paths", [INCLUDE_PATH])

    input_names = (["WorldNormal", "UV", "HeightMap"]
                   + [n for n, _ in SCALAR_PARAMS[:1]]
                   + [n for n, _ in COLOR_PARAMS]
                   + [n for n, _ in SCALAR_PARAMS[1:]])
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
    ML.connect_material_expressions(height_tex, "", shader, "HeightMap")

    y = 300
    for name, default in SCALAR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "PaintedSurface")
        ML.connect_material_expressions(p, "", shader, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "PaintedSurface")
        ML.connect_material_expressions(p, "", shader, name)
        y += 130

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, shader, "None")
    ML.connect_material_property(shader, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shader, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shader, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 500)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 1.0)
    specular.set_editor_property("group", "PaintedSurface")
    ML.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)


def make_instances(mat):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    for name, overrides in [("MI_PaintedSurface_Default", []),
                            ("MI_PaintedSurface_Waves", WAVES_OVERRIDES)]:
        full_path = "{0}/{1}".format(PACKAGE_PATH, name)
        if AL.does_asset_exist(full_path):
            AL.delete_asset(full_path)
        mi = tools.create_asset(name, PACKAGE_PATH, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        ML.set_material_instance_parent(mi, mat)
        for param, value in overrides:
            if isinstance(value, unreal.LinearColor):
                ML.set_material_instance_vector_parameter_value(mi, param, value)
            else:
                ML.set_material_instance_scalar_parameter_value(mi, param, value)
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

    make_instances(mat)
    log("=== build done ===")


main()
