# =============================================================================
#  build_test_level.py
#
#  Builds L_FlexusTest: five level stations in a row, spaced from the REAL
#  mesh bounds so nothing overlaps, each with its own framing camera and
#  label. LVL1 shows the chameleon material on three different shapes with
#  three preset instances (like the reference video's preset cycling);
#  LVL2-5 use the client's subdivided PlaneMesh.fbx, scaled to a uniform
#  footprint. LVL3/4/5 each get their own ALiquidSimPaintController wired to
#  their own render-target pair - press Play, hold LMB over a plane, paint.
#
#  Needs the FULL GUI editor (level ops crash the headless commandlet):
#   UnrealEditor.exe Flexus_TestTask.uproject -noxgeshadercompile -nosplash ^
#       -ExecCmds="py E:/GitHub/Flexus_TestTask/Python/level/build_test_level.py"
#
#  Author: Max Okhrimenko
# =============================================================================

import unreal

MAP_PATH = "/Game/LiquidSim/Maps/L_FlexusTest"
MATERIALS_PATH = "/Game/LiquidSim/Materials"
TEXTURES_PATH = "/Game/LiquidSim/Textures"
CLIENT_MESH_SOURCE = "E:/GitHub/Flexus_TestTask/Reference/PlaneMesh.fbx"
CLIENT_MESH_DEST_PATH = "/Game/LiquidSim/Meshes"
CLIENT_MESH_DEST_NAME = "SM_PlaneMesh"

SKY_CUBE_CANDIDATES = [
    "/Engine/MapTemplates/Sky/DaylightAmbientCubemap",
    "/Engine/EngineResources/GrayLightTextureCube",
    "/Engine/EngineResources/DefaultTextureCube",
]

PLANE_FOOTPRINT = 700.0   # cm - every displaced plane is scaled to this size
STATION_GAP = 450.0       # cm of clear air between stations

AL = unreal.EditorAssetLibrary
LES = unreal.LevelEditorSubsystem()
EAS = unreal.EditorActorSubsystem()


def log(msg):
    unreal.log("[TestLevel] {0}".format(msg))


def load_mi(name):
    mi = AL.load_asset("{0}/{1}".format(MATERIALS_PATH, name))
    if mi is None:
        raise RuntimeError("{0} not found - build materials first".format(name))
    return mi


def load_rt(name):
    rt = AL.load_asset("{0}/{1}".format(TEXTURES_PATH, name))
    if rt is None:
        raise RuntimeError("{0} not found - run build_render_targets.py first".format(name))
    return rt


def import_client_mesh():
    full_path = "{0}/{1}".format(CLIENT_MESH_DEST_PATH, CLIENT_MESH_DEST_NAME)
    if AL.does_asset_exist(full_path):
        log("reusing already-imported {0}".format(full_path))
        return AL.load_asset(full_path)

    task = unreal.AssetImportTask()
    task.filename = CLIENT_MESH_SOURCE
    task.destination_path = CLIENT_MESH_DEST_PATH
    task.destination_name = CLIENT_MESH_DEST_NAME
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    mesh = AL.load_asset(full_path)
    if mesh is None:
        raise RuntimeError("failed to import {0}".format(CLIENT_MESH_SOURCE))
    log("imported {0}".format(full_path))
    return mesh


def disable_nanite(mesh):
    """CRITICAL for displacement: FBX import enables Nanite by default, and
    under DX12/SM6 Nanite actually renders - and Nanite IGNORES World
    Position Offset, silently killing every displaced surface (on DX11 it
    fell back to the regular mesh path, which is why displacement worked
    before the Lumen/DX12 switch)."""
    nanite = mesh.get_editor_property("nanite_settings")
    was_enabled = nanite.get_editor_property("enabled")
    log("nanite on {0}: was {1}".format(mesh.get_name(), was_enabled))
    if was_enabled:
        mesh.modify()
        nanite.set_editor_property("enabled", False)
        # set_editor_property fires PostEditChange, which rebuilds the mesh
        mesh.set_editor_property("nanite_settings", nanite)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        log("nanite DISABLED on {0} (WPO now works under DX12)".format(mesh.get_name()))


def clear_previous_actors():
    for actor in EAS.get_all_level_actors():
        if actor.get_actor_label().startswith("FX_"):
            EAS.destroy_actor(actor)


def add_environment(row_center_x):
    """Full environment: sun + atmosphere sky + fog + skylight + floor +
    post-process. Without a real sky the level reads flat and metallic
    surfaces go black (nothing to reflect)."""
    sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 800))
    sun.set_actor_label("FX_Sun")
    sun.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-45.0, yaw=35.0), False)
    sun_comp = sun.get_editor_property("light_component")
    sun_comp.set_editor_property("atmosphere_sun_light", True)

    atmosphere = EAS.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
    atmosphere.set_actor_label("FX_SkyAtmosphere")

    fog = EAS.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, -100))
    fog.set_actor_label("FX_Fog")

    # realtime-captured skylight picks the atmosphere up for ambient and
    # reflections (what Lumen wants); the cubemap fallback covers the first
    # frames before any capture happens
    sky = EAS.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 400))
    sky.set_actor_label("FX_SkyLight")
    sky_comp = sky.get_editor_property("light_component")
    sky_comp.set_editor_property("source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE)
    sky_comp.set_editor_property("real_time_capture", True)
    sky_comp.set_editor_property("intensity", 1.0)
    sky_comp.recapture_sky()

    # floor: big dark plane so the stations sit in a space, not a void
    floor_mesh = AL.load_asset("/Engine/BasicShapes/Plane.Plane")
    floor = EAS.spawn_actor_from_object(floor_mesh, unreal.Vector(row_center_x, 0.0, -3.0),
                                        unreal.Rotator(0.0, 0.0, 0.0))
    floor.set_actor_label("FX_Floor")
    floor.set_actor_scale3d(unreal.Vector(140.0, 60.0, 1.0))

    # bloom so emissive cores/foam glow properly
    ppv = EAS.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    ppv.set_actor_label("FX_PostProcess")
    ppv.set_editor_property("unbound", True)
    settings = ppv.get_editor_property("settings")
    settings.set_editor_property("override_bloom_intensity", True)
    settings.set_editor_property("bloom_intensity", 1.2)
    ppv.set_editor_property("settings", settings)


def add_label(index, text, x, z=260.0):
    # cameras sit at -Y looking +Y, so the text must face -Y (yaw 270)
    label_actor = EAS.spawn_actor_from_class(
        unreal.TextRenderActor, unreal.Vector(x, 0.0, z),
        unreal.Rotator(roll=0.0, pitch=0.0, yaw=270.0))
    label_actor.set_actor_label("FX_Label_{0}".format(index))
    text_comp = label_actor.get_editor_property("text_render")
    text_comp.set_text(text)
    text_comp.set_world_size(42.0)
    text_comp.set_text_render_color(unreal.Color(255, 255, 255, 255))
    return label_actor


def add_camera(index, x, offset_y, height, look_at):
    cam_location = unreal.Vector(x, offset_y, height)
    cam_rotation = unreal.MathLibrary.find_look_at_rotation(cam_location, look_at)
    camera = EAS.spawn_actor_from_class(unreal.CameraActor, cam_location, cam_rotation)
    camera.set_actor_label("FX_Cam_{0}".format(index))
    return camera


def add_shape_station(index, x):
    """LVL1: the SAME chameleon instance on three different shapes, so the
    view-angle gradient is what varies - not the preset. Chrome/Gold/Cobalt
    preset instances exist as assets for the demo video's preset-cycling
    (swap them in the material slot)."""
    shapes = [
        ("/Engine/BasicShapes/Sphere.Sphere", unreal.Vector(x, 0.0, 130.0), 2.6),
        ("/Engine/BasicShapes/Cylinder.Cylinder", unreal.Vector(x, -260.0, 100.0), 2.0),
        ("/Engine/BasicShapes/Cone.Cone", unreal.Vector(x, 260.0, 100.0), 2.0),
    ]
    chameleon = load_mi("MI_Chameleon_Default")
    for i, (mesh_path, location, scale) in enumerate(shapes):
        mesh = AL.load_asset(mesh_path)
        actor = EAS.spawn_actor_from_object(mesh, location, unreal.Rotator(0.0, 0.0, 0.0))
        actor.set_actor_label("FX_Shape_{0}_{1}".format(index, i))
        actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        actor.get_editor_property("static_mesh_component").set_material(0, chameleon)
    add_label(index, "LVL1 - Chameleon", x)
    add_camera(index, x, -620.0, 300.0, unreal.Vector(x, 0.0, 120.0))
    log("placed station {0}: LVL1 shapes".format(index))


def add_plane_station(index, x, label, mi_name, client_mesh, plane_scale):
    plane = EAS.spawn_actor_from_object(client_mesh, unreal.Vector(x, 0.0, 0.0),
                                        unreal.Rotator(0.0, 0.0, 0.0))
    plane.set_actor_label("FX_Plane_{0}".format(index))
    plane.set_actor_scale3d(unreal.Vector(plane_scale, plane_scale, plane_scale))
    plane.get_editor_property("static_mesh_component").set_material(0, load_mi(mi_name))
    add_label(index, label, x)
    # reference demos: camera low over the plane, looking down its length
    add_camera(index, x, -PLANE_FOOTPRINT * 0.95, 430.0, unreal.Vector(x, 0.0, 0.0))
    log("placed station {0}: {1}".format(index, label))
    return plane


def add_paint_controller(index, plane, rt_a_name, rt_b_name, paint_mi,
                         decay, viscosity, brush_radius=0.09, brush_depth=0.08,
                         softness=1.4, smoothing=0.3, wetness_decay=1.0,
                         decay_variation=0.0):
    # viscosity is the per-texel spring stiffness (0 = no oscillation, paint
    # just sits), decay the damping - see LiquidSim_PaintStep in the .ush.
    # LMB paints, RMB levels the surface flat.
    controller = EAS.spawn_actor_from_class(
        unreal.LiquidSimPaintController,
        plane.get_actor_location() + unreal.Vector(0.0, 0.0, 50.0))
    controller.set_actor_label("FX_Controller_{0}".format(index))
    controller.set_editor_property("target_plane", plane)
    controller.set_editor_property("render_target_a", load_rt(rt_a_name))
    controller.set_editor_property("render_target_b", load_rt(rt_b_name))
    controller.set_editor_property("paint_material", paint_mi)
    controller.set_editor_property("decay_speed", decay)
    controller.set_editor_property("viscosity", viscosity)
    controller.set_editor_property("brush_radius", brush_radius)
    controller.set_editor_property("brush_depth", brush_depth)
    controller.set_editor_property("brush_softness", softness)
    controller.set_editor_property("rim_height", 0.025)
    controller.set_editor_property("smoothing", smoothing)
    controller.set_editor_property("wetness_decay", wetness_decay)
    controller.set_editor_property("decay_variation", decay_variation)
    log("controller {0}: decay={1} viscosity={2} -> {3}/{4}".format(
        index, decay, viscosity, rt_a_name, rt_b_name))
    return controller


def main():
    log("=== build start ===")

    client_mesh = import_client_mesh()
    disable_nanite(client_mesh)
    box = client_mesh.get_bounding_box()
    size = box.max - box.min
    mesh_footprint = max(size.x, size.y)
    plane_scale = PLANE_FOOTPRINT / mesh_footprint
    log("client mesh footprint: {0:.1f} cm -> scale {1:.3f}".format(mesh_footprint, plane_scale))

    spacing = PLANE_FOOTPRINT + STATION_GAP

    if AL.does_asset_exist(MAP_PATH):
        log("loading existing map {0}".format(MAP_PATH))
        LES.load_level(MAP_PATH)
    else:
        log("creating new map {0}".format(MAP_PATH))
        LES.new_level(MAP_PATH)

    clear_previous_actors()
    add_environment(spacing * 2.5)

    # the headless material build only sees DefaultTextureCube (gray) in its
    # asset registry; here in the full editor the sky cubemap exists, so
    # upgrade the chameleon instances' reflection to it
    for cube_path in SKY_CUBE_CANDIDATES:
        if AL.does_asset_exist(cube_path):
            cube = AL.load_asset(cube_path)
            for mi_name in ["MI_Chameleon_Default", "MI_Chameleon_Chrome",
                            "MI_Chameleon_Gold", "MI_Chameleon_Cobalt"]:
                mi = AL.load_asset("{0}/{1}".format(MATERIALS_PATH, mi_name))
                if mi is not None:
                    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                        mi, "ReflectionCube", cube)
                    AL.save_loaded_asset(mi)
            log("chameleon instances ReflectionCube -> {0}".format(cube_path))
            break

    paint_mi = load_mi("MI_PaintBrush_Default")

    # station 0: LVL1 on shapes
    add_shape_station(0, 0.0)

    # stations 1-5: displaced planes
    plane_2 = add_plane_station(1, spacing * 1, "LVL2 - Perlin Displacement",
                                "MI_Displacement_Default", client_mesh, plane_scale)
    plane_3 = add_plane_station(2, spacing * 2, "LVL3 - Paint (PIE: hold LMB)",
                                "MI_PaintedSurface_Default", client_mesh, plane_scale)
    plane_4 = add_plane_station(3, spacing * 3, "LVL4 - Waves (PIE: hold LMB)",
                                "MI_PaintedSurface_Waves", client_mesh, plane_scale)
    plane_5 = add_plane_station(4, spacing * 4, "LVL5 - Boss (PIE: hold LMB)",
                                "MI_Boss_Default", client_mesh, plane_scale)
    # bonus stations: the vortex is pure procedural show (its painting read
    # as noise against the swirl - feedback said it adds nothing, so no
    # controller here), and the rain is fully procedural by design
    add_plane_station(5, spacing * 5, "LVL6 - Vortex (bonus)",
                      "MI_Vortex_Default", client_mesh, plane_scale)
    add_plane_station(6, spacing * 6, "LVL7 - Rain (bonus)",
                      "MI_Rain_Default", client_mesh, plane_scale)

    # paint controllers (viscosity = spring stiffness, decay = damping;
    # LMB paints): LVL3 keeps paint forever with heavy edge smoothing and a
    # big reference-style brush, LVL4 - smaller softer brush, big bouncy
    # waves, slightly uneven slow fade, LVL5 - gentle spring
    add_paint_controller(2, plane_3, "RT_Height_A", "RT_Height_B", paint_mi,
                         1.0, 0.0, brush_radius=0.12, brush_depth=0.12,
                         softness=1.6, smoothing=0.35, wetness_decay=1.0)
    add_paint_controller(3, plane_4, "RT_Height_C", "RT_Height_D", paint_mi,
                         0.998, 0.045, brush_radius=0.05, brush_depth=0.16,
                         softness=1.6, smoothing=0.25, wetness_decay=0.996,
                         decay_variation=0.004)
    add_paint_controller(4, plane_5, "RT_Height_E", "RT_Height_F", paint_mi,
                         0.998, 0.03, brush_radius=0.08, brush_depth=0.12,
                         softness=1.4, smoothing=0.25, wetness_decay=0.997,
                         decay_variation=0.003)

    # overview camera down the row
    row_center = unreal.Vector(spacing * 3.0, 0.0, 0.0)
    cam_location = unreal.Vector(row_center.x, -2400.0, 1100.0)
    cam_rotation = unreal.MathLibrary.find_look_at_rotation(cam_location, row_center)
    overview = EAS.spawn_actor_from_class(unreal.CameraActor, cam_location, cam_rotation)
    overview.set_actor_label("FX_Cam_Overview")
    unreal.UnrealEditorSubsystem().set_level_viewport_camera_info(cam_location, cam_rotation)

    LES.save_current_level()
    log("saved {0}".format(MAP_PATH))
    log("=== build done ===")


main()

unreal.SystemLibrary.quit_editor()
