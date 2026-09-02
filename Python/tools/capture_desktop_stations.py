# =============================================================================
#  capture_desktop_stations.py
#
#  Renders one still per station from the DESKTOP level (the full-detail,
#  non-optimised materials) so they can be reviewed without opening the editor
#  by hand.
#
#  Uses a SceneCaptureComponent2D into a render target and writes the pixels
#  out directly. take_high_res_screenshot() was tried first and is asynchronous
#  - the script quits the editor before the file is ever written.
#
#  Read-only apart from the temporary capture target, which is deleted at the
#  end. The level itself is never saved.
#
#   UnrealEditor.exe <uproject> -noxgeshadercompile -nosplash ^
#       -ExecCmds="py .../capture_desktop_stations.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import math
import os
import unreal

MAP = "/Game/LiquidSim/Maps/L_FlexusTest"
OUT = "E:/GitHub/Flexus_TestTask/Saved/StationShots"
RT_PATH = "/Game/LiquidSim/Textures/RT_Capture_Tmp"
SIZE = (1280, 720)

# label -> file name. Station 0 is three separate chameleon shapes.
TARGETS = [
    ("FX_Shape_0_0", "LVL1_chameleon"),
    ("FX_Plane_1", "LVL2_perlin"),
    ("FX_Plane_2", "LVL3_paint"),
    ("FX_Plane_3", "LVL4_waves"),
    ("FX_Plane_4", "LVL5_boss"),
    ("FX_Plane_5", "LVL6_vortex"),
    ("FX_Plane_6", "LVL7_rain"),
    ("FX_Plane_7", "LVL8_lava"),
]

LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()
AL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()


def log(m):
    unreal.log("[Capture] {0}".format(m))


def main():
    log("=== start ===")
    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    LES.load_level(MAP)

    if AL.does_asset_exist(RT_PATH):
        AL.delete_asset(RT_PATH)
    rt = AT.create_asset("RT_Capture_Tmp", "/Game/LiquidSim/Textures",
                         unreal.TextureRenderTarget2D,
                         unreal.TextureRenderTargetFactoryNew())
    rt.set_editor_property("size_x", SIZE[0])
    rt.set_editor_property("size_y", SIZE[1])
    rt.set_editor_property("render_target_format",
                           unreal.TextureRenderTargetFormat.RTF_RGBA8)

    cap = EAS.spawn_actor_from_class(unreal.SceneCapture2D,
                                     unreal.Vector(0, 0, 0), unreal.Rotator())
    comp = cap.get_editor_property("capture_component2d")
    comp.set_editor_property("texture_target", rt)
    comp.set_editor_property("capture_source",
                             unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    comp.set_editor_property("fov_angle", 75.0)

    # Warm the shader cache first. The first attempt captured the default
    # checkerboard for every station: SceneCapture renders immediately, while
    # material shaders are still compiling asynchronously, so the fallback
    # material is what lands in the frame.
    log("  warming shaders...")
    for path in [
        "/Game/LiquidSim/Materials/M_Chameleon",
        "/Game/LiquidSim/Materials/M_Displacement",
        "/Game/LiquidSim/Materials/M_PaintedSurface",
        "/Game/LiquidSim/Materials/M_Boss",
        "/Game/LiquidSim/Materials/M_Vortex",
        "/Game/LiquidSim/Materials/M_Rain",
        "/Game/LiquidSim/Materials/M_Lava",
    ]:
        m = AL.load_asset(path)
        if m is not None:
            unreal.MaterialEditingLibrary.recompile_material(m)
    unreal.SystemLibrary.collect_garbage()
    log("  shaders warm")

    located = {}
    for a in EAS.get_all_level_actors():
        located[a.get_actor_label()] = a.get_actor_location()

    shot = 0
    for label, name in TARGETS:
        if label not in located:
            log("  !! {0} not in level".format(label))
            continue
        centre = located[label]

        # Same framing the mobile orbit camera uses: 1150 uu back, 38 deg down.
        dist, pitch, yaw = 1150.0, -38.0, 90.0
        pr, yr = math.radians(pitch), math.radians(yaw)
        cp = math.cos(pr)
        loc = unreal.Vector(centre.x - cp * math.cos(yr) * dist,
                            centre.y - cp * math.sin(yr) * dist,
                            centre.z - math.sin(pr) * dist)
        cap.set_actor_location(loc, False, False)
        cap.set_actor_rotation(unreal.Rotator(0.0, pitch, yaw), False)

        # Several captures in a row: the first frame after a camera move is
        # often still the previous one, and one-shot capture caught it.
        for _ in range(8):
            comp.call_method("CaptureScene")

        path = "{0}/{1}.png".format(OUT, name)
        unreal.RenderingLibrary.export_render_target(cap, rt, OUT, "{0}.png".format(name))
        shot += 1
        log("  {0} -> {1}".format(label, path))

    EAS.destroy_actor(cap)
    if AL.does_asset_exist(RT_PATH):
        AL.delete_asset(RT_PATH)

    log("=== done: {0} shot(s) in {1} ===".format(shot, OUT))


main()

unreal.SystemLibrary.quit_editor()
