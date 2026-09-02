# =============================================================================
#  layout_mobile_stations.py
#
#  MOBILE ONLY. Re-lays the eight demo stations of L_FlexusTest_Mobile from one
#  ~7900 uu straight row into a compact 4x2 grid, and parks the PlayerStart on a
#  fixed viewpoint that frames all of them at once.
#
#  WHY: the row is a desktop flythrough composition. On a phone every station
#  ends up about 56x17 px and the only way to reach one is to fly there on two
#  virtual thumbsticks - which is exactly what made the build unusable. In a
#  4x2 grid seen from above each station is roughly 300x300 px and nothing has
#  to be flown to.
#
#  HOW: stations are moved as WHOLE GROUPS. Every FX_* actor is bucketed by the
#  station X it currently sits at, then the whole bucket is shifted by one
#  delta. That keeps each label, shape and plane in the same relative spot
#  without hardcoding actor names.
#
#  Planes are TRANSLATED ONLY, never rotated: the shading in LiquidSimCore
#  reconstructs its basis along world X/Y, so rotating a plane would break the
#  lighting on it.
#
#  This supersedes tune_mobile_viewpoint.py (which only moved the PlayerStart
#  and left the row alone).
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/layout_mobile_stations.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MOBILE_MAP = "/Game/LiquidSim/Maps/L_FlexusTest_Mobile"

# Station X positions in the original row, in order.
ROW_X = [0.0, 1150.0, 2300.0, 3450.0, 4600.0, 5750.0, 6900.0, 7860.0]

# 4x2 grid, 1600 uu pitch. Wider than it needs to be for an overview shot:
# each station now has its own camera, and at 950 uu the neighbouring station
# leaked into frame.
COL_X = (-2400.0, -800.0, 800.0, 2400.0)
NEAR_Y = -800.0
FAR_Y = 800.0

# Station index -> grid cell. Stations 2/3/4 are the interactive painted ones,
# so they go on the near row where they are biggest and easiest to reach.
GRID = {
    1: (COL_X[0], NEAR_Y),   # LVL2 Perlin
    2: (COL_X[1], NEAR_Y),   # LVL3 Paint    <- interactive
    3: (COL_X[2], NEAR_Y),   # LVL4 Waves    <- interactive
    4: (COL_X[3], NEAR_Y),   # LVL5 Boss     <- interactive
    0: (COL_X[0], FAR_Y),    # LVL1 Chameleon
    5: (COL_X[1], FAR_Y),    # LVL6 Vortex
    6: (COL_X[2], FAR_Y),    # LVL7 Rain
    7: (COL_X[3], FAR_Y),    # LVL8 Lava
}

# Viewpoint. Eye sits 1750 uu from the grid centre along a -72 deg pitch; the
# 64 uu of APawn::BaseEyeHeight that GetPawnViewLocation() adds is subtracted
# here so the view ray lands on the grid centre.
VIEW_LOC = unreal.Vector(0.0, -541.0, 1600.0)
VIEW_ROT = unreal.Rotator(0.0, -72.0, 90.0)   # roll, pitch, yaw

LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()
UES = unreal.UnrealEditorSubsystem()


def log(msg):
    unreal.log("[Layout] {0}".format(msg))


def station_of(x):
    """Bucket a world X onto the nearest original station, or None if it is
    too far from any of them to belong to one."""
    best, best_d = None, 1e9
    for i, sx in enumerate(ROW_X):
        d = abs(x - sx)
        if d < best_d:
            best, best_d = i, d
    # half the original spacing; anything further out is not a station prop
    return best if best_d <= 500.0 else None


def main():
    log("=== start ===")
    LES.load_level(MOBILE_MAP)

    # Bucket every FX_ prop by the station it belongs to. Paint controllers sit
    # at the origin and drive their plane by pointer, so they must NOT be moved
    # (and must not be bucketed as station 0 either).
    buckets = {}
    skipped = []
    for actor in EAS.get_all_level_actors():
        label = actor.get_actor_label()
        if not label.startswith("FX_"):
            continue
        # World-wide actors must never be bucketed. The sun, sky and fog happen
        # to sit near x=0, so a naive X bucket drags them into station 0's grid
        # cell along with the chameleon shapes.
        if isinstance(actor, (unreal.LiquidSimPaintController,
                              unreal.DirectionalLight,
                              unreal.SkyLight,
                              unreal.SkyAtmosphere,
                              unreal.ExponentialHeightFog,
                              unreal.PostProcessVolume,
                              unreal.PlayerStart)):
            skipped.append(label)
            continue

        loc = actor.get_actor_location()
        idx = station_of(loc.x)
        if idx is None:
            skipped.append(label)
            continue
        buckets.setdefault(idx, []).append(actor)

    log("stations found: {0}".format(sorted(buckets.keys())))
    log("not moved: {0}".format(", ".join(sorted(skipped)) or "(nothing)"))

    missing = [i for i in GRID if i not in buckets]
    if missing:
        log("!! no actors for station(s) {0} - continuing with the rest".format(missing))

    moved = 0
    for idx in sorted(buckets):
        if idx not in GRID:
            log("  station {0}: no grid slot, left alone".format(idx))
            continue
        new_x, new_y = GRID[idx]
        dx = new_x - ROW_X[idx]
        dy = new_y - 0.0
        names = []
        for actor in buckets[idx]:
            loc = actor.get_actor_location()
            actor.set_actor_location(
                unreal.Vector(loc.x + dx, loc.y + dy, loc.z), False, False)
            names.append(actor.get_actor_label())
            moved += 1
        log("  station {0} -> ({1:.0f}, {2:.0f})  [{3}]".format(
            idx, new_x, new_y, ", ".join(sorted(names))))

    log("actors moved: {0}".format(moved))

    starts = 0
    for actor in EAS.get_all_level_actors():
        if isinstance(actor, unreal.PlayerStart):
            actor.set_actor_location(VIEW_LOC, False, False)
            actor.set_actor_rotation(VIEW_ROT, False)
            starts += 1
    if starts == 0:
        ps = EAS.spawn_actor_from_class(unreal.PlayerStart, VIEW_LOC, VIEW_ROT)
        if ps:
            ps.set_actor_label("PlayerStart_MobileView")
            starts = 1
    log("player start at ({0:.0f},{1:.0f},{2:.0f}) pitch {3:.0f} yaw {4:.0f}  (count {5})".format(
        VIEW_LOC.x, VIEW_LOC.y, VIEW_LOC.z, VIEW_ROT.pitch, VIEW_ROT.yaw, starts))

    # The mobile level is the one currently loaded, so save it in place.
    # save_map() to its own package path returns False here - it is meant for
    # writing the loaded world out under a DIFFERENT name (which is how
    # build_mobile_level.py uses it).
    saved = LES.save_current_level()
    log("save_current_level -> {0}".format("OK" if saved else "FAILED"))
    log("=== done ===")


main()

unreal.SystemLibrary.quit_editor()
