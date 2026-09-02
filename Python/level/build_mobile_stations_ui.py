# =============================================================================
#  build_mobile_stations_ui.py
#
#  MOBILE ONLY. Turns L_FlexusTest_Mobile into something usable on a phone:
#  one fixed camera per station, plus an ALiquidSimStationDirector holding the
#  list, so the on-screen picker can jump between them.
#
#  WHY: with the virtual joysticks removed there is no navigation at all, and
#  even in the compact grid each station is only ~300 px. A camera per station
#  puts one station on the whole screen - which is also what makes painting on
#  the interactive ones practical, since the brush finally has a big target.
#
#  Idempotent: existing FX_StationCam_* and the director are deleted and rebuilt,
#  so it is safe to re-run after moving stations around.
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/build_mobile_stations_ui.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import math
import unreal

MOBILE_MAP = "/Game/LiquidSim/Maps/L_FlexusTest_Mobile"

# Station index -> label shown in the picker. Order here is the picker order.
# (index, label, is_interactive). Interactive stations keep a single finger for
# the brush; on the others a single finger orbits the camera instead.
LABELS = [
    (0, "LVL1  Chameleon", False),
    (1, "LVL2  Perlin", False),
    (2, "LVL3  Paint", True),
    (3, "LVL4  Waves", True),
    (4, "LVL5  Boss", True),
    (5, "LVL6  Vortex", False),
    (6, "LVL7  Rain", False),
    (7, "LVL8  Lava", False),
]

# Orbit radius per station. The director spawns ONE camera and orbits it around
# the station centre, so no CameraActors are placed in the level any more - the
# framing follows the station even if it moves. A plane is 700 uu across and the
# camera FOV is 75 deg, so ~1150 uu frames it with margin for the picker bar.
ORBIT_DISTANCE = 1150.0

# Which station the build opens on. 2 = LVL3 Paint, the first interactive one,
# so the demo starts on something you can immediately touch.
START_INDEX = 0

LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()


def log(msg):
    unreal.log("[StationsUI] {0}".format(msg))


def station_centre(index):
    """Centre of a station = the plane if it has one, otherwise the mean of its
    shapes (station 0 is three separate chameleon meshes, not one plane)."""
    plane_label = "FX_Plane_{0}".format(index)
    shapes = []
    for actor in EAS.get_all_level_actors():
        label = actor.get_actor_label()
        if label == plane_label:
            return actor.get_actor_location()
        if label.startswith("FX_Shape_{0}_".format(index)):
            shapes.append(actor.get_actor_location())
    if shapes:
        return unreal.Vector(
            sum(v.x for v in shapes) / len(shapes),
            sum(v.y for v in shapes) / len(shapes),
            sum(v.z for v in shapes) / len(shapes))
    return None


def main():
    log("=== start ===")
    LES.load_level(MOBILE_MAP)

    # Clear anything a previous run made, so re-running never stacks duplicates.
    removed = 0
    for actor in list(EAS.get_all_level_actors()):
        label = actor.get_actor_label()
        if label.startswith("FX_StationCam_") or isinstance(actor, unreal.LiquidSimStationDirector):
            EAS.destroy_actor(actor)
            removed += 1
    if removed:
        log("removed {0} actor(s) from a previous run".format(removed))

    stations = []
    for index, text, interactive in LABELS:
        centre = station_centre(index)
        if centre is None:
            log("  !! station {0} has no actors - skipped".format(index))
            continue

        entry = unreal.LiquidSimStation()
        entry.set_editor_property("label", text)
        entry.set_editor_property("centre", centre)
        entry.set_editor_property("distance", ORBIT_DISTANCE)
        entry.set_editor_property("interactive", interactive)   # UE strips the b prefix for bools
        stations.append(entry)

        log("  {0}: centre=({1:.0f},{2:.0f},{3:.0f})  orbit r={4:.0f}".format(
            text, centre.x, centre.y, centre.z, ORBIT_DISTANCE))

    director = EAS.spawn_actor_from_class(
        unreal.LiquidSimStationDirector, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator())
    if director is None:
        log("!! failed to spawn the director - aborting without saving")
        return
    director.set_actor_label("FX_StationDirector")
    director.set_editor_property("stations", stations)
    director.set_editor_property("start_index", START_INDEX)
    log("director holds {0} station(s)".format(len(stations)))

    # Install the game mode that carries the picker HUD. A HUD class cannot be
    # placed in a level, so the world settings have to name a game mode.
    ws_done = False
    for actor in EAS.get_all_level_actors():
        if isinstance(actor, unreal.WorldSettings):
            actor.set_editor_property("default_game_mode", unreal.LiquidSimGameMode)
            ws_done = True
            log("world settings: default_game_mode = LiquidSimGameMode")
    if not ws_done:
        log("!! no WorldSettings actor found - HUD will not appear")

    saved = LES.save_current_level()
    log("save_current_level -> {0}".format("OK" if saved else "FAILED"))
    log("=== done ===")


main()

unreal.SystemLibrary.quit_editor()
