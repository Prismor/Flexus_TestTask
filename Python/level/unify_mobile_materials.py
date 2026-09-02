# =============================================================================
#  unify_mobile_materials.py
#
#  Points L_FlexusTest_Mobile at the SAME materials the desktop level uses, so
#  there is one visual version of every effect instead of two.
#
#  WHY: the mobile variants drifted from the full ones more than once - a colour
#  left at an old value here, a threshold tuned there - and each time the phone
#  showed something different from the editor. Since the brief is judged on
#  visual aesthetics as well as performance, two different looks is the worse
#  trade. The cheap materials stay in the project as a fallback if the measured
#  cost turns out to be too high on real hardware.
#
#  The mobile level keeps everything else that makes it mobile: the 4x2 station
#  grid, the picker director, the fixed-exposure volume.
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/unify_mobile_materials.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MOBILE_MAP = "/Game/LiquidSim/Maps/L_FlexusTest_Mobile"
FULL_PATH = "/Game/LiquidSim/Materials"

AL = unreal.EditorAssetLibrary
LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()

# cheap instance -> the full-detail instance it should be replaced by
SWAP = {
    "MI_Displacement_Mobile": "MI_Displacement_Default",
    "MI_Vortex_Mobile": "MI_Vortex_Default",
    "MI_Rain_Mobile": "MI_Rain_Default",
    "MI_Lava_Mobile": "MI_Lava_Default",
}


def log(msg):
    unreal.log("[Unify] {0}".format(msg))


def main():
    log("=== start ===")
    LES.load_level(MOBILE_MAP)

    swapped = 0
    for actor in EAS.get_all_level_actors():
        comp = actor.get_component_by_class(unreal.StaticMeshComponent)
        if comp is None:
            continue
        for slot in range(comp.get_num_materials()):
            mat = comp.get_material(slot)
            if mat is None:
                continue
            name = mat.get_name()
            if name not in SWAP:
                continue
            full = AL.load_asset("{0}/{1}".format(FULL_PATH, SWAP[name]))
            if full is None:
                log("  !! {0} missing".format(SWAP[name]))
                continue
            comp.set_material(slot, full)
            swapped += 1
            log("  {0}: {1} -> {2}".format(actor.get_actor_label(), name, SWAP[name]))

    log("materials unified: {0}".format(swapped))

    saved = LES.save_current_level()
    log("save_current_level -> {0}".format("OK" if saved else "FAILED"))
    log("=== done ===")


main()

unreal.SystemLibrary.quit_editor()
