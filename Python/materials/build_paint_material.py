# =============================================================================
#  build_paint_material.py
#
#  LVL 3 + LVL 4 - builds M_PaintBrush: drawn into a render target every
#  frame via DrawMaterialToRenderTarget. The RT stores float2 (R = height,
#  G = velocity), which makes wave damping a REAL damped spring per texel -
#  Viscosity is the stiffness (0 = LVL3: paint just stays), DecaySpeed the
#  damping. Brush is a gaussian dent + gaussian rim (no hard edges), and a
#  4-neighbour relaxation rounds off sharp leftovers every frame.
#
#  ONE Custom node; the previous frame's RT is a TextureObject input sampled
#  inside the node - no loose native nodes.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_paint_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_PaintBrush"
INSTANCE_NAME = "MI_PaintBrush_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

PAINT_STEP_CODE = ("return LiquidSim_PaintStep(PrevHeightMap, PrevHeightMapSampler, UV, "
                   "Decay, DecayVariation, Viscosity, SpringDamp, VelocityMax, "
                   "Smoothing, TexelSize, WaveTapUV, "
                   "BrushU, BrushV, BrushPrevU, BrushPrevV, Radius, Softness, "
                   "Depth, RimHeight, RimOffset, RimWidth, Raggedness, "
                   "BrushStrength, WetnessDecay, MaxHeight, DeltaTime);")

# BrushDepth/RimHeight are RATES (units per second, scaled by DeltaTime from
# the controller) - the surface presses down gradually in layers
SCALAR_PARAMS = [
    ("DecaySpeed", 1.0),
    ("DecayVariation", 0.0),
    ("Viscosity", 0.0),
    ("SpringDamp", 0.995),
    ("VelocityMax", 0.5),
    ("Smoothing", 0.3),
    ("TexelSize", 1.0 / 1024.0),
    ("WaveTapUV", 0.004),
    ("BrushU", 0.5),
    ("BrushV", 0.5),
    ("BrushPrevU", 0.5),
    ("BrushPrevV", 0.5),
    ("BrushRadius", 0.08),
    ("BrushSoftness", 1.2),
    ("BrushDepth", 0.6),
    ("RimHeight", 0.2),
    ("RimOffset", 1.2),
    ("RimWidth", 0.4),
    ("Raggedness", 0.0),  # per-station via the controller (water must be 0)
    ("BrushStrength", 1.0),
    ("WetnessDecay", 1.0),
    ("MaxHeight", 0.5),
    ("DeltaTime", 1.0 / 60.0),
]

# custom-node input name for each parameter (controller-facing names differ)
INPUT_NAME = {
    "DecaySpeed": "Decay",
    "BrushRadius": "Radius",
    "BrushSoftness": "Softness",
    "BrushDepth": "Depth",
}


def log(msg):
    unreal.log("[PaintBrush] {0}".format(msg))


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

    # never seen directly - only ever drawn into a render target
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    # CRITICAL: without this flag the engine clamps emissive to >= 0
    # (GetMaterialEmissive in MaterialTemplate.ush), so NEGATIVE heights -
    # the brush dents and the downward half of every oscillation - never
    # reached the render target at all. Only positive rims ever painted.
    mat.set_editor_property("allow_negative_emissive_color", True)
    log("created {0}".format(full_path))
    return mat


def build_graph(mat):
    texcoord = ML.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -700, 0)

    prev_tex = ML.create_material_expression(mat, unreal.MaterialExpressionTextureObjectParameter, -700, 120)
    prev_tex.set_editor_property("parameter_name", "PrevHeightMap")
    # Clamp addressing, forced on the SAMPLER. Setting it on the render target
    # asset alone was not enough: a texture object in a Custom node samples
    # through the world group settings by default, which are Wrap, so a wave
    # reaching the edge still read its neighbour from the opposite edge and
    # reappeared there.
    prev_tex.set_editor_property(
        "sampler_source", unreal.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS)

    paint_step = ML.create_material_expression(mat, unreal.MaterialExpressionCustom, -350, 100)
    paint_step.set_editor_property("code", PAINT_STEP_CODE)
    # float3: R = height, G = velocity, B = wetness (paint coverage)
    paint_step.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    paint_step.set_editor_property("description", "Paint Step")
    paint_step.set_editor_property("include_file_paths", [INCLUDE_PATH])

    input_names = (["PrevHeightMap", "UV"]
                   + [INPUT_NAME.get(n, n) for n, _ in SCALAR_PARAMS])
    inputs = []
    for name in input_names:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    paint_step.set_editor_property("inputs", inputs)

    ML.connect_material_expressions(prev_tex, "", paint_step, "PrevHeightMap")
    ML.connect_material_expressions(texcoord, "", paint_step, "UV")

    y = 300
    for name, default in SCALAR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -700, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Paint")
        ML.connect_material_expressions(p, "", paint_step, INPUT_NAME.get(name, name))
        y += 70

    ML.connect_material_property(paint_step, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)


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
