# =============================================================================
#  build_portfolio.py
#
#  Builds Documentation/portfolio.html - a single page pairing each effect's
#  LIVE PREVIEW with its ACTUAL CODE and an explanation, meant to be dropped
#  into a portfolio site.
#
#  The previews run the generated GLSL; the code shown is the clean per-effect
#  HLSL. Both come from Shaders/LiquidSimCore.ush, so the page can never show
#  code that differs from what actually runs.
#
#  Run:  python Python/docs/build_shadertoy.py      (previews)
#        python Python/docs/build_clean_shaders.py  (code)
#        python Python/docs/build_portfolio.py
#
#  Author: Max Okhrimenko
# =============================================================================

import io
import json
import os

from _portfolio_template import COPY, PORTFOLIO_HTML
from _viewer_template import EFFECT_INFO  # noqa: F401  (kept in sync manually)

# Three levels up: this file sits in Python/<group>/, so the project root is
# two directories above the script's own folder.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLEAN_DIR = os.path.join(ROOT, "Shaders", "Clean")
SHADERTOY_DIR = os.path.join(ROOT, "Shaders", "Shadertoy")
OUT = os.path.join(ROOT, "Documentation", "portfolio.html")

# order on the page, and which generated GLSL drives each preview
ORDER = [
    ("LVL1_Chameleon", "LVL 1", "LVL1_Chameleon"),
    ("LVL2_Displacement", "LVL 2", "LVL2_Displacement"),
    ("LVL3_Paint", "LVL 3", "LVL3_PaintedGel"),
    ("LVL4_Waves", "LVL 4", "LVL4_Water"),
    ("LVL5_Boss", "LVL 5", "LVL5_Boss"),
    ("LVL6_Vortex", "Bonus", "LVL6_Vortex"),
    ("LVL7_Rain", "Bonus", "LVL7_Rain"),
    ("LVL8_Lava", "Bonus", "LVL8_Lava"),
]

# Rebuilding the GLSL here would duplicate build_shadertoy.py, so instead we
# re-import its pieces and ask it for the same strings it writes to disk.
import build_shadertoy as st  # noqa: E402


def glsl_for(name):
    """Return (imageSrc, bufferSrc|None) for one effect, from the generator."""
    core = st.load_core()
    for eff_name, kind, blocks in st.EFFECTS:
        if eff_name == name:
            return st.glsl_for_viewer(core, eff_name, kind, blocks), kind
    raise KeyError(name)


def main():
    payload = []
    for clean_name, level, preview_name in ORDER:
        code_path = os.path.join(CLEAN_DIR, clean_name + ".hlsl")
        code = io.open(code_path, encoding="utf-8").read().rstrip()

        (image, buf), kind = glsl_for(preview_name)
        title, summary, bullets = COPY[clean_name]

        payload.append({
            "name": clean_name,
            "level": level,
            "title": title,
            "summary": summary,
            "bullets": bullets,
            "kind": kind,
            "code": code,
            "path": "Shaders/Clean/" + clean_name + ".hlsl",
            "image": image,
            "buffer": buf,
        })

    html = PORTFOLIO_HTML.replace("__EFFECT_DATA__", json.dumps(payload))

    outdir = os.path.dirname(OUT)
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(html)
    print("wrote {0} ({1:.0f} KB, {2} effects)".format(OUT, len(html) / 1024.0, len(payload)))


main()
