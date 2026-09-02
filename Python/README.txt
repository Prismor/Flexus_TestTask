Build scripts
=============

Every material and both levels are built by script, never by hand in the editor.
That is deliberate: a material rebuilt from a script is reproducible, and the
parameter defaults live in version control instead of inside a .uasset.

  materials/   one script per material, plus the render targets
  level/       the two levels, station layout, picker, post process
  docs/        documentation and shader-extract generators
  tools/       verification and capture helpers

Run any of them like this (the -noxgeshadercompile is NOT optional on this
machine - XGE hangs the editor without it):

  UnrealEditor-Cmd.exe <uproject> -run=pythonscript ^
      -script="<abs/forward/slash/path.py>" ^
      -unattended -nosplash -nopause -AllowCommandletRendering -noxgeshadercompile

Scripts that touch a LEVEL need the full editor instead, and must end with
unreal.SystemLibrary.quit_editor():

  UnrealEditor.exe <uproject> -noxgeshadercompile -nosplash -ExecCmds="py <path>"


Start here
----------
  tools/verify_project.py     checks every material compiles and both levels are
                              intact. Run it after any change.

  materials/build_*.py        rebuild one material. ALWAYS rerun these after
                              editing a .ush - the shader change does not reach
                              an existing material on its own.

  level/unify_mobile_materials.py
                              points the mobile level at the full-detail
                              materials (the current setup).


Do not run
----------
  level/build_test_level.py   regenerates the DESKTOP level from scratch and
                              would wipe the hand-made layout. Kept for
                              reference only.
