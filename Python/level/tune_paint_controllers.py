# =============================================================================
#  tune_paint_controllers.py
#
#  SURGICAL parameter update for the existing LiquidSimPaintController actors
#  in L_FlexusTest. Finds them by label, sets ONLY the listed properties, and
#  saves. Never deletes, spawns, or moves anything - the level layout is
#  hand-maintained now (build_test_level.py is retired to reference-only,
#  do NOT run it against the curated level).
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/tune_paint_controllers.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MAP_PATH = "/Game/LiquidSim/Maps/L_FlexusTest"

# label -> {property: value}
# BrushDepth/RimHeight are now RATES per second (gradual layered pressing);
# viscosity lowered everywhere - the old stiffness made the rebound
# overshoot upward and jerk
TUNING = {
    "FX_Controller_2": {  # gel: ragged edges, NO self-levelling at all
        "brush_radius": 0.07,
        "brush_depth": 1.2,
        "rim_height": 0.35,
        "brush_softness": 0.9,
        "smoothing": 0.0,
        "raggedness": 0.5,
    },
    "FX_Controller_3": {  # water: rings that actually travel and ring out.
        "viscosity": 2.0,     # 2.0 is the measured stability ceiling
        "brush_depth": 8.0,   # the laplacian eats most of the press
        "rim_height": 2.0,
        "smoothing": 0.1,
        "raggedness": 0.0,
    },
    "FX_Controller_4": {  # boss: distinct from water - waves linger longer,
        "viscosity": 1.5,     # spreads, softer than open water
        "brush_depth": 5.0,
        "rim_height": 1.2,
        "brush_softness": 1.0,
        "smoothing": 0.15,
        "raggedness": 0.3,
        "decay_speed": 0.996,
        "wetness_decay": 0.995,
    },
}

LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()


def log(msg):
    unreal.log("[TuneControllers] {0}".format(msg))


def main():
    log("=== tune start ===")
    LES.load_level(MAP_PATH)

    touched = 0
    for actor in EAS.get_all_level_actors():
        label = actor.get_actor_label()
        if label not in TUNING:
            continue
        actor.modify()
        for prop, value in TUNING[label].items():
            actor.set_editor_property(prop, value)
            log("{0}.{1} = {2}".format(label, prop, value))
        touched += 1

    if touched != len(TUNING):
        log("WARNING: expected {0} controllers, found {1}".format(len(TUNING), touched))

    LES.save_current_level()
    log("saved (only property changes, nothing added or removed)")
    log("=== tune done ===")


main()

unreal.SystemLibrary.quit_editor()
