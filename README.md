# LiquidSim — FLEXUS test task

A liquid-simulation shader test task for Unreal Engine 5.8. Eight effects —
five required plus three bonus (vortex, rain, lava) — built on one portable
HLSL core shared between the real Unreal materials and a live WebGL demo.

## Effects

| Level | Effect | Technique | UE cost (instructions) |
|---|---|---|---|
| 1 | Chameleon | View-angle iridescence, per-band roughness | 332 |
| 2 | Displacement | Animated Perlin noise pushes the surface along its normal | 991 |
| 3 | Paint | Finger/mouse paints into a render target that holds its shape | 253 + 316 |
| 4 | Waves | Same simulation as Paint with viscosity turned up — ripples that travel and decay | 253 + 316 |
| 5 | Boss | Noise and paint combined before the normal is rebuilt, iridescent shading | 1147 |
| 6 | Vortex (bonus) | Rotated, domain-warped noise pulled into a funnel; colour rotates with it | 2488 |
| 7 | Rain (bonus) | Three layered grids of drops, each a damped expanding ring | 932 |
| 8 | Lava (bonus) | Ridged-noise crack network on a drifting crust, black-body glow | 3051 |

## How it's built

All the math lives in one file, `Shaders/LiquidSimCore.ush` — plain functions
over floats, no engine calls at all. A thin adapter (`Shaders/LiquidSim.ush`)
samples textures and feeds the core's output into Unreal's Custom material
nodes. The same core, unchanged, is what `Delivery/interactive.html` and the
Shadertoy ports in `Shaders/Shadertoy/` are generated from — a six-line
compatibility prelude is all HLSL needs to also read as GLSL. Editing the
core updates every version at once; there is no hand-copied duplicate to
drift out of sync.

## Try it live

Download `Delivery/interactive.html` and open it in a browser — all 8
effects run in WebGL with sliders for the real material parameters, and the
GLSL source for each is one click away.

## Delivery

- **Video + APK:** see the [Releases](../../releases) page (too large for git)
- **Per-effect shader source:** `Delivery/shaders/` — both HLSL (Unreal) and GLSL
- **Interactive demo:** `Delivery/interactive.html`

## Requirements

Unreal Engine 5.8. Open `Flexus_TestTask.uproject`; the level `L_FlexusTest`
loads on start. First editor launch after a shader change recompiles once
and takes a few minutes.
