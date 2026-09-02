# =============================================================================
#  build_mobile_postprocess.py
#
#  MOBILE ONLY. Puts one unbound PostProcessVolume into L_FlexusTest_Mobile
#  with MANUAL exposure.
#
#  WHY: the lava kept reading as grey. Its crust albedo is 0.030 - almost
#  black - so it can only look grey if something is scaling the image up, and
#  that something was auto-exposure: an earlier pass removed the level's
#  PostProcessVolume as "useless on the mobile renderer", which left eye
#  adaptation running on its default. On a dark scene it lifts everything, so
#  black basalt turns grey and the molten channels clip to white.
#
#  r.DefaultFeature.AutoExposure=False in AndroidEngine.ini was tried first and
#  did NOT take effect - the volume is the reliable way to pin it.
#
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/build_mobile_postprocess.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MOBILE_MAP = "/Game/LiquidSim/Maps/L_FlexusTest_Mobile"

LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()


def log(msg):
    unreal.log("[MobilePP] {0}".format(msg))


def main():
    log("=== start ===")
    LES.load_level(MOBILE_MAP)

    # Idempotent: drop any volume a previous run made.
    for actor in list(EAS.get_all_level_actors()):
        if isinstance(actor, unreal.PostProcessVolume):
            EAS.destroy_actor(actor)
            log("  removed an existing PostProcessVolume")

    ppv = EAS.spawn_actor_from_class(
        unreal.PostProcessVolume, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator())
    if ppv is None:
        log("!! failed to spawn the volume - aborting without saving")
        return
    ppv.set_actor_label("FX_PostProcess")

    # Unbound: applies everywhere regardless of where the camera is, so it does
    # not have to enclose eight stations spread over 5000 uu.
    ppv.set_editor_property("unbound", True)
    ppv.set_editor_property("priority", 1.0)

    settings = ppv.get_editor_property("settings")

    # Manual exposure. Without the override flags the values are ignored.
    settings.set_editor_property("override_auto_exposure_method", True)
    settings.set_editor_property("auto_exposure_method",
                                 unreal.AutoExposureMethod.AEM_MANUAL)

    # With manual metering the bias IS the exposure, and 1.0 is the neutral
    # point - anything higher would re-introduce the lift being removed here.
    settings.set_editor_property("override_auto_exposure_bias", True)
    settings.set_editor_property("auto_exposure_bias", 1.0)

    # Belt and braces: pin the adaptation range too, so a build that ignores
    # the method override still cannot drift.
    settings.set_editor_property("override_auto_exposure_min_brightness", True)
    settings.set_editor_property("auto_exposure_min_brightness", 1.0)
    settings.set_editor_property("override_auto_exposure_max_brightness", True)
    settings.set_editor_property("auto_exposure_max_brightness", 1.0)

    # Bloom stays, but restrained: the molten channels should glow, not smear
    # over the crust that is meant to read as cold.
    settings.set_editor_property("override_bloom_intensity", True)
    settings.set_editor_property("bloom_intensity", 0.35)

    ppv.set_editor_property("settings", settings)
    log("  manual exposure, bias 1.0, bloom 0.35")

    saved = LES.save_current_level()
    log("save_current_level -> {0}".format("OK" if saved else "FAILED"))
    log("=== done ===")


main()

unreal.SystemLibrary.quit_editor()
