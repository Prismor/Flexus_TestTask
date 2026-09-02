# =============================================================================
#  build_mobile_level.py
#
#  Produces L_FlexusTest_Mobile: the same layout as the hand-maintained
#  desktop level, but with the cheap material instances and without the
#  desktop-only lighting extras.
#
#  HOW IT AVOIDS TOUCHING THE DESKTOP LEVEL:
#  the source level is loaded, edited IN MEMORY, then written out under a new
#  name with save_map(). The original .umap on disk is never saved. (An
#  earlier version duplicated the asset and then loaded the copy - that
#  crashed the editor with "World Memory Leaks" every time.)
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/build_mobile_level.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

SRC_MAP = "/Game/LiquidSim/Maps/L_FlexusTest"
DST_MAP = "/Game/LiquidSim/Maps/L_FlexusTest_Mobile"
MOBILE_PATH = "/Game/LiquidSim/Materials/Mobile"

AL = unreal.EditorAssetLibrary
LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()
UES = unreal.UnrealEditorSubsystem()

# desktop instance -> cheap replacement. Anything absent keeps its desktop
# material because it is already within a mobile budget.
SWAP = {
    "MI_Displacement_Default": "MI_Displacement_Mobile",
    "MI_Displacement_Value": "MI_Displacement_Mobile",
    "MI_Displacement_Perlin": "MI_Displacement_Mobile",
    "MI_Displacement_Ridged": "MI_Displacement_Mobile",
    "MI_Vortex_Default": "MI_Vortex_Mobile",
    "MI_Rain_Default": "MI_Rain_Mobile",
    "MI_Lava_Default": "MI_Lava_Mobile",
}


def log(msg):
    unreal.log("[MobileLevel] {0}".format(msg))


def main():
    log("=== build start ===")

    LES.load_level(SRC_MAP)
    log("loaded source level (will be saved under a NEW name, never overwritten)")

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
            replacement = AL.load_asset("{0}/{1}".format(MOBILE_PATH, SWAP[name]))
            if replacement is None:
                log("  WARNING: {0} missing".format(SWAP[name]))
                continue
            comp.set_material(slot, replacement)
            swapped += 1
            log("  {0}: {1} -> {2}".format(actor.get_actor_label(), name, SWAP[name]))

    log("materials swapped: {0}".format(swapped))

    # Desktop-only extras: a post-process volume does nothing useful on the
    # mobile renderer, and a realtime sky capture is far too expensive.
    removed = 0
    for actor in list(EAS.get_all_level_actors()):
        if isinstance(actor, unreal.PostProcessVolume):
            EAS.destroy_actor(actor)
            removed += 1
        elif isinstance(actor, unreal.SkyLight):
            comp = actor.get_editor_property("light_component")
            try:
                comp.set_editor_property("real_time_capture", False)
                log("  skylight: realtime capture off")
            except Exception as e:
                log("  skylight: could not change capture ({0})".format(e))
    log("removed {0} desktop-only actors".format(removed))

    # save_map takes a /Game package path, NOT a filename - passing an absolute
    # .umap path returns false without an error message.
    world = UES.get_editor_world()
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, DST_MAP)
    log("save_map {0} -> {1}".format(DST_MAP, "OK" if saved else "FAILED"))

    log("=== build done, saved={0} ===".format(saved))


main()

unreal.SystemLibrary.quit_editor()
