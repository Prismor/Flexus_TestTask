# =============================================================================
#  fix_rt_clamp.py
#
#  Sets AddressX/AddressY to Clamp on every simulation render target.
#
#  WHY: a wave reaching the edge of a paint surface reappeared on the OPPOSITE
#  edge. A render target defaults to Wrap addressing, so when the simulation
#  samples a neighbour just past u=1 it reads from u=0 - the far side of the
#  same surface - and the disturbance teleports across.
#
#  saturate() on the sample UVs inside LiquidSim.ush was tried first and did NOT
#  fix it, so the addressing is pinned on the asset itself where nothing can
#  bypass it.
#
#   UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=".../fix_rt_clamp.py"
#       -unattended -nosplash -nopause -noxgeshadercompile
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

AL = unreal.EditorAssetLibrary
BASE = "/Game/LiquidSim/Textures"
NAMES = ["RT_Height_A", "RT_Height_B", "RT_Height_C", "RT_Height_D",
         "RT_Height_E", "RT_Height_F", "RT_Height_G", "RT_Height_H"]


def log(msg):
    unreal.log("[RTClamp] {0}".format(msg))


log("=== start ===")
fixed = 0
for name in NAMES:
    path = "{0}/{1}".format(BASE, name)
    rt = AL.load_asset(path)
    if rt is None:
        log("  !! missing {0}".format(name))
        continue

    before_x = rt.get_editor_property("address_x")
    before_y = rt.get_editor_property("address_y")

    rt.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    rt.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)

    AL.save_asset(path)
    fixed += 1
    log("  {0}: {1}/{2} -> CLAMP/CLAMP".format(name, before_x, before_y))

log("=== done: {0} render target(s) clamped ===".format(fixed))

unreal.SystemLibrary.quit_editor()
