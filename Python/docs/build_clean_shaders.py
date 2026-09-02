# =============================================================================
#  build_clean_shaders.py
#
#  Splits the core library into ONE CLEAN FILE PER EFFECT, so each shader can
#  be read on its own without scrolling past code it does not use.
#
#  Each file contains exactly the functions that effect needs - resolved
#  automatically by following the call graph - so the files can never drift
#  out of sync with Shaders/LiquidSimCore.ush.
#
#  Output: Shaders/Clean/<Level>.hlsl
#  Run:    python Python/docs/build_clean_shaders.py
#
#  Author: Max Okhrimenko
# =============================================================================

import io
import os

from _core_deps import parse_blocks, resolve, strip_comment_blocks

# Three levels up: this file sits in Python/<group>/, so the project root is
# two directories above the script's own folder.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE = os.path.join(ROOT, "Shaders", "LiquidSimCore.ush")
OUT_DIR = os.path.join(ROOT, "Shaders", "Clean")

# ---- what each effect needs at the top level; dependencies are resolved ------
# (filename, title, short English description, entry-point symbols)
EFFECTS = [
    ("LVL1_Chameleon", "Chameleon",
     "View-angle iridescence with per-band roughness and a Fresnel-weighted\n"
     "reflection. No displacement - this one is pure shading.",
     ["LS_Surface", "LS_ShadeChameleon"]),

    ("LVL2_Displacement", "Perlin displacement",
     "Animated fractal noise pushes the surface along its normal, and the\n"
     "normal is rebuilt from three height samples so lighting follows the\n"
     "new shape. Colour is mapped from height.",
     ["LS_Surface", "LS_NoiseParams", "LS_HeightPerlin",
      "LS_SurfaceFromHeights", "LS_HeightRamp", "LS_ShadeDisplacement"]),

    ("LVL3_Paint", "Render-target painting",
     "The interactive simulation. One RGBA buffer holds height, velocity and\n"
     "paint coverage; every frame it is redrawn from the previous one\n"
     "(ping-pong) with a new brush stamp added. Viscosity 0 means the paint\n"
     "just stays - that is this level.",
     ["LS_BrushParams", "LS_SimParams", "LS_WaveTapDistance", "LS_PaintStep",
      "LS_Surface", "LS_SurfaceFromHeights", "LS_HeightRamp", "LS_ShadePainted"]),

    ("LVL4_Waves", "Damped travelling waves",
     "Exactly the same simulation as LVL3 with Viscosity turned up: the\n"
     "laplacian coupling turns the dent into rings that travel outward and\n"
     "ring down. Measured stability ceiling is 2.0.",
     ["LS_BrushParams", "LS_SimParams", "LS_WaveTapDistance", "LS_PaintStep",
      "LS_Surface", "LS_SurfaceFromHeights", "LS_HeightRamp", "LS_ShadePainted"]),

    ("LVL5_Boss", "Boss - everything combined",
     "Procedural noise displacement and painted displacement are summed per\n"
     "tap, then shaded as an iridescent fluid over a near-black idle base,\n"
     "with glowing troughs, a dithered coverage edge, foam and glitter.",
     ["LS_Surface", "LS_NoiseParams", "LS_HeightPerlin", "LS_SurfaceFromHeights",
      "LS_BossDisplace", "LS_Iridescent", "LS_Sparkle", "LS_ShadeBoss"]),

    ("LVL6_Vortex", "Vortex",
     "The noise domain is rotated by an angle that grows toward the centre\n"
     "and warped by a second noise, then a smooth funnel pulls the middle\n"
     "down. Colour is sampled along that same rotated coordinate, so the\n"
     "thin line-bands wind with the geometry instead of the camera, and a\n"
     "radial pull brightens them toward the centre for a portal look.",
     ["LS_Surface", "LS_NoiseParams", "LS_HeightVortex", "LS_SurfaceFromHeights",
      "LS_Sparkle", "LS_ShadeVortex"]),

    ("LVL7_Rain", "Rain ripples",
     "Three offset grids of cells; each cell spawns one drop with its own\n"
     "position, phase and size, and each drop is a cosine ring damped by age.\n"
     "Wet patches darken the ground and make it glossy.",
     ["LS_Surface", "LS_NoiseParams", "LS_HeightRain", "LS_SurfaceFromHeights",
      "LS_WetPatchMask", "LS_ShadeRain"]),

    ("LVL8_Lava", "Lava",
     "Warped ridged noise shapes big winding plates; the cool crust gets\n"
     "voronoi cobbles and thin grooves. Heat runs along its own low-octave\n"
     "crack network, not the plate valleys - those stayed too round to read\n"
     "as thin lines. Albedo darkens as it heats, so only the glow reads as\n"
     "light, the way real molten rock does.",
     ["LS_Surface", "LS_NoiseParams", "LS_Voronoi", "LS_HeightLava",
      "LS_LavaHeat", "LS_SurfaceFromHeights", "LS_ShadeLava"]),
]

HEADER = """// =============================================================================
//  {title}
//
{desc}
//
//  Portable HLSL - no engine API. The same text compiles in Unreal and Unity;
//  for GLSL add the six-line prelude (see Shaders/Shadertoy/).
// =============================================================================

"""


def main():
    text = io.open(CORE, encoding="utf-8").read()
    blocks = parse_blocks(text)
    print("parsed {0} definitions from the core".format(len(blocks)))

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    for fname, title, desc, entries in EFFECTS:
        missing = [e for e in entries if e not in blocks]
        if missing:
            print("  !! {0}: unknown symbols {1}".format(fname, missing))

        order = resolve(entries, blocks)
        body = strip_comment_blocks("\n\n".join(blocks[s] for s in order))

        desc_lines = "\n".join("//  " + l for l in desc.splitlines())
        out = HEADER.format(title=title, desc=desc_lines) + body + "\n"

        path = os.path.join(OUT_DIR, fname + ".hlsl")
        io.open(path, "w", encoding="utf-8", newline="\n").write(out)
        print("  {0:<22} {1:>2} functions, {2:>6} chars".format(
            fname + ".hlsl", len(order), len(out)))


if __name__ == "__main__":
    main()
