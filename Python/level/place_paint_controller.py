# =============================================================================
#  place_paint_controller.py
#
#  Wires the LVL3/4 station (FX_Plane_3) up for live painting: spawns
#  ALiquidSimPaintController, points it at the station's plane and the
#  RT_Height_A/B ping-pong pair, and gives the station's own mesh a runtime
#  dynamic instance of M_PaintedSurface so the controller can update its
#  HeightMap parameter every tick.
#
#  Needs the full GUI editor (spawning actors needs LevelEditorSubsystem):
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py Python/level/place_paint_controller.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MAP_PATH = "/Game/LiquidSim/Maps/L_FlexusTest"
MATERIALS_PATH = "/Game/LiquidSim/Materials"
STATION_LABEL = "FX_Plane_3"  # LVL4 - Waves station

AL = unreal.EditorAssetLibrary
LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()


def log(msg):
    unreal.log("[PaintController] {0}".format(msg))


def find_actor(label):
    for actor in EAS.get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def main():
    log("=== build start ===")
    LES.load_level(MAP_PATH)

    for actor in EAS.get_all_level_actors():
        if actor.get_actor_label() == "FX_PaintController":
            EAS.destroy_actor(actor)

    station = find_actor(STATION_LABEL)
    if station is None:
        raise RuntimeError("station {0} not found - run build_test_level.py first".format(STATION_LABEL))

    paint_material = AL.load_asset("{0}/M_PaintBrush".format(MATERIALS_PATH))
    surface_material = AL.load_asset("{0}/MI_PaintedSurface_Default".format(MATERIALS_PATH))
    rt_a = AL.load_asset("/Game/LiquidSim/Textures/RT_Height_A")
    rt_b = AL.load_asset("/Game/LiquidSim/Textures/RT_Height_B")
    if None in (paint_material, surface_material, rt_a, rt_b):
        raise RuntimeError("missing one of M_PaintBrush / MI_PaintedSurface_Default / RT_Height_A / RT_Height_B")

    # A runtime dynamic instance so the controller can change HeightMap every
    # tick - the station's static instance stays untouched for the other
    # (non-interactive) demo stations.
    mesh_comp = station.get_editor_property("static_mesh_component")
    display_mid = unreal.MaterialInstanceDynamic.create(surface_material, station)
    mesh_comp.set_material(0, display_mid)

    mesh = mesh_comp.get_editor_property("static_mesh")
    bounds = mesh.get_bounds()
    plane_world_size = max(bounds.box_extent.x, bounds.box_extent.y) * 2.0

    controller = EAS.spawn_actor_from_class(
        unreal.LiquidSimPaintController, station.get_actor_location(), unreal.Rotator(0.0, 0.0, 0.0))
    controller.set_actor_label("FX_PaintController")
    controller.set_editor_property("target_plane", station)
    controller.set_editor_property("render_target_a", rt_a)
    controller.set_editor_property("render_target_b", rt_b)
    controller.set_editor_property("paint_material", paint_material)
    controller.set_editor_property("display_material", display_mid)
    controller.set_editor_property("plane_world_size", plane_world_size)
    controller.set_editor_property("viscosity", 6.0)  # LVL4: oscillating waves

    LES.save_current_level()
    log("wired FX_PaintController to {0} (PlaneWorldSize={1:.0f})".format(STATION_LABEL, plane_world_size))
    log("=== build done ===")


main()
unreal.SystemLibrary.quit_editor()
