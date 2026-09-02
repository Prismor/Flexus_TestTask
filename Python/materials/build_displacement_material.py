# =============================================================================
#  build_displacement_material.py
#
#  LVL 2 - builds M_Displacement: a plane displaced by hand-rolled animated
#  Perlin/FBM noise (World Position Offset), normal recalculated afterwards,
#  and the surface colored BY HEIGHT (deep blue valleys -> teal -> green
#  crests, like the reference demo). The ENTIRE material is one Custom node
#  calling LiquidSim_DisplacementShader - the noise itself is HLSL in
#  LiquidSim.ush, which is what makes noise type / seed / octaves real
#  instance parameters (UE's native Noise node can't expose those).
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_displacement_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Displacement"
INSTANCE_NAME = "MI_Displacement_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

SHADER_CODE = """LS_Surface S = LiquidSim_DisplacementShader(
    WorldNormal, UV, Time,
    NoiseSize, NoiseSpeed, Amplitude,
    NoiseSeed, NoiseType, NoiseOctaves, Lacunarity, Persistence,
    ColorLow, ColorMid, ColorHigh, RoughnessValue);
Normal = S.Normal;
BaseColor = S.BaseColor;
Roughness = S.Roughness;
return S.Offset;"""

SCALAR_PARAMS = [
    # name, default   (reference video: ~6-8 bumps across, ~10% amplitude;
    # octaves raised to 5 for finer surface detail)
    # feedback: bigger bumps (lower frequency), bigger amplitude, slower
    ("NoiseSize", 5.0),
    ("NoiseSpeed", 0.16),
    ("Amplitude", 130.0),
    ("NoiseSeed", 0.0),
    ("NoiseType", 1.0),      # 0 value, 1 Perlin/gradient, 2 ridged
    ("NoiseOctaves", 3.0),   # feedback: 5 octaves read as small-scale noise
    ("Lacunarity", 2.0),
    ("Persistence", 0.45),
    ("RoughnessValue", 0.22),
]

# valleys stay a rich BLUE rather than dropping into near-black
COLOR_PARAMS = [
    ("ColorLow", unreal.LinearColor(0.08, 0.20, 0.80, 1.0)),   # bright royal blue
    ("ColorMid", unreal.LinearColor(0.06, 0.45, 0.42, 1.0)),   # teal
    ("ColorHigh", unreal.LinearColor(0.22, 0.85, 0.28, 1.0)),  # saturated green
]


def log(msg):
    unreal.log("[Displacement] {0}".format(msg))


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
    # The Custom node outputs a WORLD-space normal (what central difference
    # naturally produces) - take the Normal pin as world space.
    mat.set_editor_property("tangent_space_normal", False)
    log("created {0}".format(full_path))
    return mat


def build_graph(mat):
    texcoord = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -800, -150)
    time_node = ML.create_material_expression(mat, unreal.MaterialExpressionTime, -800, -50)
    vertex_normal = ML.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -800, -280)

    shader = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
    shader.set_editor_property("code", SHADER_CODE)
    shader.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shader.set_editor_property("description", "Displacement Shader")
    shader.set_editor_property("include_file_paths", [INCLUDE_PATH])

    input_names = (["WorldNormal", "UV", "Time"]
                   + [n for n, _ in SCALAR_PARAMS[:8]]
                   + [n for n, _ in COLOR_PARAMS]
                   + ["RoughnessValue"])
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

    y = 100
    for name, default in SCALAR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Displacement")
        ML.connect_material_expressions(p, "", shader, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Displacement")
        ML.connect_material_expressions(p, "", shader, name)
        y += 130

    # MP_WorldPositionOffset is UMETA(Hidden) - unreachable from Python's
    # connect_material_property, so a custom plugin C++ helper wires it.
    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, shader, "None")
    ML.connect_material_property(shader, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shader, "BaseColor", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shader, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 500)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 0.9)
    specular.set_editor_property("group", "Displacement")
    ML.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)


def make_instance(mat):
    # UE material instances have no enum-dropdown parameter type, so the
    # "noise type dropdown" is three ready preset instances - picking one in
    # the mesh's material slot IS the dropdown.
    presets = [
        (INSTANCE_NAME, []),
        ("MI_Displacement_Value", [("NoiseType", 0.0)]),
        ("MI_Displacement_Perlin", [("NoiseType", 1.0)]),
        ("MI_Displacement_Ridged", [("NoiseType", 2.0)]),
    ]
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    for name, overrides in presets:
        full_path = "{0}/{1}".format(PACKAGE_PATH, name)
        if AL.does_asset_exist(full_path):
            AL.delete_asset(full_path)
        mi = tools.create_asset(name, PACKAGE_PATH, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        ML.set_material_instance_parent(mi, mat)
        for param, value in overrides:
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

    make_instance(mat)
    log("=== build done ===")


main()
