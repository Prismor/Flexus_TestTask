# =============================================================================
#  build_chameleon_material.py
#
#  LVL 1 - builds M_Chameleon: one Custom node holds the entire shader
#  (LiquidSim_ChameleonShader in LiquidSim.ush) - iridescent 3-color ramp by
#  view angle, per-color-band roughness, and a real cubemap reflection kick
#  sampled inside the node. Reference-video defaults: facing cyan, mid deep
#  blue, grazing magenta, glossy metal response.
#
#  Also creates the preset instances the reference video cycles through:
#  MI_Chameleon_Default / _Chrome / _Gold / _Cobalt.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_chameleon_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Chameleon"
INCLUDE_PATH = "/Project/LiquidSim.ush"

# first existing engine cubemap wins; DaylightAmbientCubemap is a real sky
CUBE_CANDIDATES = [
    "/Engine/MapTemplates/Sky/DaylightAmbientCubemap",
    "/Engine/EngineResources/GrayLightTextureCube",
    "/Engine/EngineResources/DefaultTextureCube",
]

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

SHADER_CODE = ("return LiquidSim_ChameleonShader(WorldNormal, CameraVec, "
               "ColorA, ColorB, ColorC, RoughnessA, RoughnessB, RoughnessC, "
               "Cube, CubeSampler, HighlightColor, Reflectivity, GradientBoost, "
               "FresnelPower, GradientShift, Emissive, Roughness);")

# name, [(param, value)...] - the preset cycling from the reference video
INSTANCES = [
    ("MI_Chameleon_Default", []),
    ("MI_Chameleon_Chrome", [
        ("ColorA", unreal.LinearColor(0.90, 0.95, 1.00, 1.0)),
        ("ColorB", unreal.LinearColor(0.85, 0.90, 0.95, 1.0)),
        ("ColorC", unreal.LinearColor(0.95, 0.97, 1.00, 1.0)),
        ("RoughnessA", 0.08), ("RoughnessB", 0.06), ("RoughnessC", 0.05),
        ("Metallic", 1.0),
    ]),
    ("MI_Chameleon_Gold", [
        ("ColorA", unreal.LinearColor(0.60, 0.25, 0.05, 1.0)),
        ("ColorB", unreal.LinearColor(1.00, 0.55, 0.12, 1.0)),
        ("ColorC", unreal.LinearColor(1.00, 0.80, 0.35, 1.0)),
        ("RoughnessA", 0.30), ("RoughnessB", 0.20), ("RoughnessC", 0.15),
        ("Metallic", 1.0),
    ]),
    ("MI_Chameleon_Cobalt", [
        ("ColorA", unreal.LinearColor(0.05, 0.08, 0.40, 1.0)),
        ("ColorB", unreal.LinearColor(0.12, 0.25, 0.90, 1.0)),
        ("ColorC", unreal.LinearColor(0.50, 0.70, 1.00, 1.0)),
        ("RoughnessA", 0.12), ("RoughnessB", 0.10), ("RoughnessC", 0.08),
        ("Metallic", 1.0),
    ]),
]


def log(msg):
    unreal.log("[Chameleon] {0}".format(msg))


def find_cube_asset():
    # does_asset_exist first: load_asset on a missing path logs an Error
    # that flips the commandlet exit code. The headless registry only sees
    # DefaultTextureCube; build_test_level.py (full GUI editor, complete
    # registry) upgrades the instances to the nicer sky cubemap afterwards.
    for path in CUBE_CANDIDATES:
        if AL.does_asset_exist(path):
            log("using reflection cubemap: {0}".format(path))
            return AL.load_asset(path)
    raise RuntimeError("no engine cubemap found among candidates")


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
    log("created {0}".format(full_path))
    return mat


def build_graph(mat, cube_asset):
    world_normal = ML.create_material_expression(mat, unreal.MaterialExpressionPixelNormalWS, -750, -150)
    cam_vec = ML.create_material_expression(mat, unreal.MaterialExpressionCameraVectorWS, -750, 0)

    cube = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -750, 120)
    cube.set_editor_property("parameter_name", "ReflectionCube")
    cube.set_editor_property("texture", cube_asset)

    shader = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -300, 0)
    shader.set_editor_property("code", SHADER_CODE)
    shader.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    shader.set_editor_property("description", "Chameleon Shader")
    shader.set_editor_property("include_file_paths", [INCLUDE_PATH])

    inputs = []
    for name in ["WorldNormal", "CameraVec", "ColorA", "ColorB", "ColorC",
                 "RoughnessA", "RoughnessB", "RoughnessC", "Cube",
                 "HighlightColor", "Reflectivity", "GradientBoost", "FresnelPower",
                 "GradientShift"]:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    shader.set_editor_property("inputs", inputs)

    outs = []
    for name, out_type in [("Emissive", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
                           ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)]:
        co = unreal.CustomOutput()
        co.set_editor_property("output_name", name)
        co.set_editor_property("output_type", out_type)
        outs.append(co)
    shader.set_editor_property("additional_outputs", outs)

    ML.connect_material_expressions(world_normal, "", shader, "WorldNormal")
    ML.connect_material_expressions(cam_vec, "", shader, "CameraVec")
    ML.connect_material_expressions(cube, "", shader, "Cube")

    # feedback: the gradient must READ - hotter, more saturated stops
    for name, default, y in [
        ("ColorA", unreal.LinearColor(1.00, 0.25, 0.85, 1.0), 250),
        ("ColorB", unreal.LinearColor(0.50, 0.20, 0.95, 1.0), 390),
        ("ColorC", unreal.LinearColor(0.00, 0.95, 1.00, 1.0), 530),
        ("HighlightColor", unreal.LinearColor(1.0, 1.0, 1.0, 1.0), 670),
    ]:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -750, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Chameleon")
        ML.connect_material_expressions(p, "", shader, name)

    # Reflectivity toned down and GradientBoost added so the view-angle
    # color ramp reads instead of drowning in metallic reflection
    for name, default, y in [
        ("RoughnessA", 0.25, 810),
        ("RoughnessB", 0.15, 880),
        ("RoughnessC", 0.10, 950),
        # feedback: smaller main highlight; GradientShift widens the violet/
        # magenta bands so the object is not one flat blue
        ("Reflectivity", 0.15, 1020),
        ("GradientBoost", 0.15, 1090),
        ("FresnelPower", 5.5, 1160),
        ("GradientShift", 2.2, 1230),
    ]:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -750, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Chameleon")
        ML.connect_material_expressions(p, "", shader, name)

    ML.connect_material_property(shader, "", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shader, "Emissive", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(shader, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    metallic = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 400)
    metallic.set_editor_property("parameter_name", "Metallic")
    metallic.set_editor_property("default_value", 0.25)
    metallic.set_editor_property("group", "Chameleon")
    ML.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -300, 500)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 0.6)
    specular.set_editor_property("group", "Chameleon")
    ML.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)


def make_instances(mat):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    for name, overrides in INSTANCES:
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
    cube_asset = find_cube_asset()
    mat = make_material()
    build_graph(mat, cube_asset)

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
