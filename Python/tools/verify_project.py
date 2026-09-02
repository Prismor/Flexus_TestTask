# =============================================================================
#  verify_project.py
#
#  Read-only health check of the whole project, run headlessly. Answers the
#  question "does everything actually still work" without opening the editor
#  by hand:
#
#    - every material compiles, and how many instructions it costs
#    - both levels load, and their actors are intact
#    - the paint controllers still point at real planes and render targets
#    - the mobile level has its picker director, with a centre per station
#    - the desktop level is untouched by the mobile work
#
#  Saves nothing.
#
#   UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=".../verify_project.py"
#       -unattended -nosplash -nopause -AllowCommandletRendering -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

AL = unreal.EditorAssetLibrary
ML = unreal.MaterialEditingLibrary

MATERIALS = [
    "/Game/LiquidSim/Materials/M_Chameleon",
    "/Game/LiquidSim/Materials/M_Displacement",
    "/Game/LiquidSim/Materials/M_PaintBrush",
    "/Game/LiquidSim/Materials/M_PaintedSurface",
    "/Game/LiquidSim/Materials/M_Boss",
    "/Game/LiquidSim/Materials/M_Vortex",
    "/Game/LiquidSim/Materials/M_Rain",
    "/Game/LiquidSim/Materials/M_Lava",
]

MOBILE_MATERIALS = [
    "/Game/LiquidSim/Materials/Mobile/M_Displacement_Mobile",
    "/Game/LiquidSim/Materials/Mobile/M_Vortex_Mobile",
    "/Game/LiquidSim/Materials/Mobile/M_Rain_Mobile",
    "/Game/LiquidSim/Materials/Mobile/M_Lava_Mobile",
]

problems = []


def log(msg):
    unreal.log("[Verify] {0}".format(msg))


def fail(msg):
    problems.append(msg)
    unreal.log_error("[Verify] FAIL: {0}".format(msg))


def check_materials():
    log("--- materials ---")
    for path in MATERIALS + MOBILE_MATERIALS:
        mat = AL.load_asset(path)
        if mat is None:
            fail("missing material {0}".format(path))
            continue
        # MaterialStatistics has no num_errors field in 5.8 - a material that
        # failed to compile reports zero instructions instead, which is the
        # signal used here.
        try:
            stats = ML.get_statistics(mat)
            instr = stats.num_pixel_shader_instructions
            samplers = stats.num_samplers
        except Exception as e:
            fail("{0}: could not read statistics ({1})".format(path.split('/')[-1], e))
            continue
        ok = instr > 0
        log("  {0} {1:<28} {2:>5} instr, {3} samplers".format(
            "OK " if ok else "ERR", path.split('/')[-1], instr, samplers))
        if not ok:
            fail("{0} reports 0 instructions - it did not compile".format(path.split('/')[-1]))


def check_level(map_path, expect_director):
    log("--- level {0} ---".format(map_path.split('/')[-1]))
    LES = unreal.LevelEditorSubsystem()
    EAS = unreal.EditorActorSubsystem()
    LES.load_level(map_path)

    actors = EAS.get_all_level_actors()
    log("  actors: {0}".format(len(actors)))

    planes = 0
    controllers = 0
    director = None
    for a in actors:
        label = a.get_actor_label()
        if label.startswith("FX_Plane") or label.startswith("FX_Shape"):
            planes += 1
        if isinstance(a, unreal.LiquidSimPaintController):
            controllers += 1
            tp = a.get_editor_property("target_plane")
            ra = a.get_editor_property("render_target_a")
            rb = a.get_editor_property("render_target_b")
            pm = a.get_editor_property("paint_material")
            if tp is None:
                fail("{0} has no target_plane".format(label))
            if ra is None or rb is None:
                fail("{0} is missing a render target".format(label))
            if pm is None:
                fail("{0} has no paint material".format(label))
        if isinstance(a, unreal.LiquidSimStationDirector):
            director = a

    log("  surfaces: {0}, paint controllers: {1}".format(planes, controllers))
    if planes == 0:
        fail("{0} has no surfaces".format(map_path))
    if controllers != 3:
        fail("{0} has {1} paint controllers, expected 3".format(map_path, controllers))

    if expect_director:
        if director is None:
            fail("mobile level has no station director")
        else:
            stations = director.get_editor_property("stations")
            log("  station director: {0} station(s)".format(len(stations)))
            if len(stations) != 8:
                fail("director holds {0} stations, expected 8".format(len(stations)))
            for i, st in enumerate(stations):
                centre = st.get_editor_property("centre")
                dist = st.get_editor_property("distance")
                label = st.get_editor_property("label")
                if dist <= 0.0:
                    fail("station {0} ({1}) has distance {2}".format(i, label, dist))
                log("    {0:<18} centre=({1:.0f},{2:.0f},{3:.0f}) r={4:.0f}".format(
                    label, centre.x, centre.y, centre.z, dist))
    elif director is not None:
        fail("desktop level unexpectedly contains a station director")


log("=== verify start ===")
check_materials()
check_level("/Game/LiquidSim/Maps/L_FlexusTest", False)
check_level("/Game/LiquidSim/Maps/L_FlexusTest_Mobile", True)

log("=== verify done: {0} problem(s) ===".format(len(problems)))
for p in problems:
    log("  PROBLEM: {0}".format(p))

unreal.SystemLibrary.quit_editor()
