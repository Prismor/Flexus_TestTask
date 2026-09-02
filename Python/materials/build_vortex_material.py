# =============================================================================
#  build_vortex_material.py
#
#  LVL 6 (bonus) - builds M_Vortex: a whirlpool. The FBM sampling domain is
#  twisted around the centre (twist grows toward it), warped by a second FBM
#  (fbm(p + fbm(p)) - organic tendrils), and a smooth funnel pulls the middle
#  down. Painted waves add on top. Shaded as iridescent liquid metal with a
#  pulsing emissive core at the funnel and foam on painted activity.
#
#  Two Custom nodes (vertex/pixel split, same reason as M_Boss - WPO
#  compiles in the vertex shader where CameraVector does not exist).
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_vortex_material.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

PACKAGE_PATH = "/Game/LiquidSim/Materials"
MATERIAL_NAME = "M_Vortex"
INSTANCE_NAME = "MI_Vortex_Default"
INCLUDE_PATH = "/Project/LiquidSim.ush"

ML = unreal.MaterialEditingLibrary
AL = unreal.EditorAssetLibrary

DISPLACE_CODE = """FLiquidSimVortexDisplace D = LiquidSim_VortexDisplace(
    WorldNormal, UV, Time, HeightMap, HeightMapSampler,
    NoiseSize, NoiseSpeed, NoiseAmplitude,
    NoiseSeed, NoiseType, NoiseOctaves, Lacunarity, Persistence,
    SwirlStrength, SwirlTightness, SwirlSpeed, WarpStrength,
    FunnelDepth, FunnelTightness, PaintAmplitude);
Normal = D.Normal;
PaintHeight = D.PaintHeight;
CentreDist = D.CentreDist;
return D.Offset;"""

SHADE_CODE = """LS_Surface S = LiquidSim_VortexShade(
    DisplacedNormal, CameraVec, UV, Time, PaintHeight, CentreDist,
    ColorA, ColorB, ColorC, CoreColor, FoamColor,
    CoreGlow, CoreTightness, PulseSpeed, PulseAmount,
    ActivitySensitivity, FoamIntensity, RoughnessIdle, RoughnessActive,
    SparkleScale, SparkleIntensity,
    BandArms, BandTwist, BandNoiseScale, BandNoiseAmount, BandContrast,
    LineNoiseSize, LineNoiseSpeed, LineNoiseSeed, LineLacunarity, LinePersistence,
    LineSwirlStrength, LineSwirlTightness, LineSwirlSpeed);
Emissive = S.Emissive;
Roughness = S.Roughness;
return S.BaseColor;"""

DISPLACE_SCALARS = [
    ("NoiseSize", 4.0),
    ("NoiseSpeed", 0.6),
    ("NoiseAmplitude", 4.0),
    ("NoiseSeed", 3.0),
    ("NoiseType", 2.0),      # ridged - torn creased look
    ("NoiseOctaves", 4.0),
    ("Lacunarity", 2.0),
    ("Persistence", 0.5),
    ("SwirlStrength", 5.5),  # 6.0 stretched the noise lattice into visible repeats
    ("SwirlTightness", 4.0),
    ("SwirlSpeed", 0.4),
    ("WarpStrength", 1.5),
    ("FunnelDepth", 6.0),      # a flat plate: the swirl is shading, not geometry
                          # LiquidSim.ush multiplies the WHOLE height by
                          # noiseAmplitude, so 150 here meant 3300 cm - a
                          # 33 m spike through a 7 m plane.
    ("FunnelTightness", 10.0),
    ("PaintAmplitude", 220.0),
]

SHADE_SCALARS = [
    ("CoreGlow", 2.0),
    ("CoreTightness", 110.0),
    ("PulseSpeed", 2.0),
    ("PulseAmount", 0.35),
    ("ActivitySensitivity", 6.0),
    ("FoamIntensity", 0.6),
    ("RoughnessIdle", 0.25),
    ("RoughnessActive", 0.06),
    # Band shaping - all on the instance so the look can be dialled in without
    # rebuilding the material.
    ("BandArms", 3.0),          # spiral arm count
    ("BandTwist", 34.0),        # how tightly the arms wind toward the centre
    ("BandNoiseScale", 42.0),   # grain size of the colour noise
    ("BandNoiseAmount", 0.22),  # how much that grain breaks up the bands
    ("BandContrast", 1.9),      # >1 sharpens bands into thin lines
    # The colour streaks are generated on the SAME KIND of swirled coordinates
    # as the height field, so they are dragged around by the vortex instead of
    # sitting on top of it. They get their OWN parameters rather than reusing
    # the displace node's: two Custom nodes cannot share a pin name, and having
    # them separate means the streak density can be tuned without touching the
    # geometry. Defaults mirror the displace values.
    ("LineNoiseSize", 3.0),
    ("LineNoiseSpeed", 0.25),
    ("LineNoiseSeed", 5.0),
    ("LineLacunarity", 2.0),
    ("LinePersistence", 0.5),
    ("LineSwirlStrength", 5.5),
    ("LineSwirlTightness", 4.0),
    ("LineSwirlSpeed", 0.4),
    ("SparkleScale", 260.0),
    ("SparkleIntensity", 0.3),
]

COLOR_PARAMS = [
    ("ColorA", unreal.LinearColor(0.55, 0.05, 0.65, 1.0)),   # grazing violet-magenta
    ("ColorB", unreal.LinearColor(0.10, 0.15, 0.60, 1.0)),   # mid deep blue
    ("ColorC", unreal.LinearColor(0.10, 0.90, 0.90, 1.0)),   # facing aqua
    ("CoreColor", unreal.LinearColor(0.60, 1.60, 2.00, 1.0)),  # hot cyan-white (HDR)
    ("FoamColor", unreal.LinearColor(1.0, 1.0, 1.0, 1.0)),
]


def log(msg):
    unreal.log("[Vortex] {0}".format(msg))


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
    # steep funnel walls flip triangles on the coarse 100x100 grid - without
    # two-sided the flipped faces render as black triangles
    mat.set_editor_property("two_sided", True)
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
        mat, -350, 0, DISPLACE_CODE, "Vortex Displace",
        ["WorldNormal", "UV", "Time", "HeightMap"] + [n for n, _ in DISPLACE_SCALARS],
        [("Normal", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
         ("PaintHeight", unreal.CustomMaterialOutputType.CMOT_FLOAT1),
         ("CentreDist", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])

    ML.connect_material_expressions(vertex_normal, "", displace, "WorldNormal")
    ML.connect_material_expressions(texcoord, "", displace, "UV")
    ML.connect_material_expressions(time_node, "", displace, "Time")
    ML.connect_material_expressions(height_tex, "", displace, "HeightMap")

    shade = make_custom(
        mat, 0, 0, SHADE_CODE, "Vortex Shade",
        ["DisplacedNormal", "CameraVec", "UV", "Time", "PaintHeight", "CentreDist"]
        + [n for n, _ in COLOR_PARAMS]
        + [n for n, _ in SHADE_SCALARS],
        [("Emissive", unreal.CustomMaterialOutputType.CMOT_FLOAT3),
         ("Roughness", unreal.CustomMaterialOutputType.CMOT_FLOAT1)])

    ML.connect_material_expressions(displace, "Normal", shade, "DisplacedNormal")
    ML.connect_material_expressions(displace, "PaintHeight", shade, "PaintHeight")
    ML.connect_material_expressions(displace, "CentreDist", shade, "CentreDist")
    ML.connect_material_expressions(cam_vec, "", shade, "CameraVec")
    ML.connect_material_expressions(texcoord, "", shade, "UV")
    ML.connect_material_expressions(time_node, "", shade, "Time")

    y = 350
    for name, default in DISPLACE_SCALARS + SHADE_SCALARS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Vortex")
        target = shade if name in dict(SHADE_SCALARS) else displace
        ML.connect_material_expressions(p, "", target, name)
        y += 70

    for name, default in COLOR_PARAMS:
        p = ML.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -800, y)
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", default)
        p.set_editor_property("group", "Vortex")
        ML.connect_material_expressions(p, "", shade, name)
        y += 130

    unreal.LiquidSimMaterialHelpers.connect_to_world_position_offset(mat, displace, "None")
    ML.connect_material_property(displace, "Normal", unreal.MaterialProperty.MP_NORMAL)
    ML.connect_material_property(shade, "", unreal.MaterialProperty.MP_BASE_COLOR)
    ML.connect_material_property(shade, "Emissive", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    ML.connect_material_property(shade, "Roughness", unreal.MaterialProperty.MP_ROUGHNESS)

    metallic = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, 0, 550)
    metallic.set_editor_property("parameter_name", "Metallic")
    metallic.set_editor_property("default_value", 0.55)
    metallic.set_editor_property("group", "Vortex")
    ML.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)

    specular = ML.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, 0, 650)
    specular.set_editor_property("parameter_name", "Specular")
    specular.set_editor_property("default_value", 1.0)
    specular.set_editor_property("group", "Vortex")
    ML.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)


def make_instance(mat):
    full_path = "{0}/{1}".format(PACKAGE_PATH, INSTANCE_NAME)
    if AL.does_asset_exist(full_path):
        AL.delete_asset(full_path)

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mi = tools.create_asset(INSTANCE_NAME, PACKAGE_PATH, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    ML.set_material_instance_parent(mi, mat)
    # painting on the vortex is retired (its controller is gone, and stale
    # RT contents times a big amplitude produced ragged spikes) - zero the
    # paint contribution entirely on the placed instance
    ML.set_material_instance_scalar_parameter_value(mi, "PaintAmplitude", 0.0)
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
