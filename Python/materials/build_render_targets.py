# =============================================================================
#  build_render_targets.py
#
#  Creates the four ping-pong render target pairs - one per interactive
#  station:
#      RT_Height_A / RT_Height_B  -> LVL3 (persistent paint)
#      RT_Height_C / RT_Height_D  -> LVL4 (damped spring waves)
#      RT_Height_E / RT_Height_F  -> LVL5 (boss)
#      RT_Height_G / RT_Height_H  -> LVL6 (vortex)
#  Format is RGBA16f: R = height, G = per-texel velocity (damped spring),
#  B = accumulated wetness/paint coverage (hole-free gradient coloring).
#  1024x1024 - 512 read as visibly low-res on the displaced surfaces.
#
#  Existing RTs are DELETED and recreated so a format change actually
#  applies. All start black (flat); the controller re-clears on BeginPlay.
#
#   UnrealEditor-Cmd.exe Flexus_TestTask.uproject -run=pythonscript ^
#       -script="Python/materials/build_render_targets.py" -unattended -nosplash ^
#       -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

TEXTURES_PATH = "/Game/LiquidSim/Textures"
MATERIALS_PATH = "/Game/LiquidSim/Materials"
RT_SIZE = 1024  # feedback: 512 read as "low resolution" - crisper relief now

AL = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary

RT_NAMES = ["RT_Height_A", "RT_Height_B", "RT_Height_C", "RT_Height_D",
            "RT_Height_E", "RT_Height_F", "RT_Height_G", "RT_Height_H"]

# display instance -> the RT its HeightMap shows before any painting
DISPLAY_BINDINGS = [
    ("MI_PaintedSurface_Default", "RT_Height_A"),
    ("MI_PaintedSurface_Waves", "RT_Height_C"),
    ("MI_Boss_Default", "RT_Height_E"),
    ("MI_Vortex_Default", "RT_Height_G"),
]


def log(msg):
    unreal.log("[RenderTargets] {0}".format(msg))


def make_render_target(name):
    # deleting-and-recreating fails while material instances still reference
    # the RT, so a format change is applied to the EXISTING asset in place -
    # setting render_target_format reinitializes the resource on save
    full_path = "{0}/{1}".format(TEXTURES_PATH, name)
    if AL.does_asset_exist(full_path):
        rt = AL.load_asset(full_path)
        log("updating existing {0}".format(full_path))
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        rt = tools.create_asset(name, TEXTURES_PATH, unreal.TextureRenderTarget2D,
                                unreal.TextureRenderTargetFactoryNew())
        log("created {0}".format(full_path))
    if rt is None:
        raise RuntimeError("could not create or load {0}".format(full_path))

    rt.set_editor_property("size_x", RT_SIZE)
    rt.set_editor_property("size_y", RT_SIZE)
    # RGBA16f: R = height, G = velocity, B = wetness (paint coverage)
    rt.set_editor_property("render_target_format", unreal.TextureRenderTargetFormat.RTF_RGBA16F)
    rt.set_editor_property("clear_color", unreal.LinearColor(0.0, 0.0, 0.0, 0.0))
    unreal.RenderingLibrary.clear_render_target2d(None, rt, unreal.LinearColor(0, 0, 0, 0))
    AL.save_loaded_asset(rt)
    return rt


def main():
    log("=== build start ===")
    rts = {name: make_render_target(name) for name in RT_NAMES}

    for instance_name, rt_name in DISPLAY_BINDINGS:
        mi = AL.load_asset("{0}/{1}".format(MATERIALS_PATH, instance_name))
        if mi is not None:
            ML.set_material_instance_texture_parameter_value(mi, "HeightMap", rts[rt_name])
            AL.save_loaded_asset(mi)
            log("pointed {0}.HeightMap at {1}".format(instance_name, rt_name))
        else:
            log("WARNING: {0} not found yet".format(instance_name))

    log("=== build done ===")


main()
