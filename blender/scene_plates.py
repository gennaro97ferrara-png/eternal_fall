# scene_plates.py — plate BILLBOARD fotoreali dei pianeti (Cycles/OptiX) per il Modello A.
# Ogni pianeta: sfera texture reale + atmosfera fresnel, camera ORTOGRAFICA (nessuna distorsione prospettica),
# sfondo TRASPARENTE (Film>Transparent) → PNG RGBA, AgX bakato (in Three.js: material.toneMapped=false).
# Saturno: anelli PROCEDURALI (Wave 'RINGS' + alpha) → evita il bug alpha-radiale della texture anello.
import bpy, math
A = "/root/eternal-fall/assets"
PREVIEW = False   # False = 2048 quadrato @ 128 samp (finale)
RES = 1024 if PREVIEW else 2048
SAMP = 40 if PREVIEW else 128

def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
    sc.cycles.samples = SAMP; sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = 'OPTIX'
    except Exception: pass
    pf = bpy.context.preferences.addons['cycles'].preferences
    pf.compute_device_type = 'OPTIX'; pf.refresh_devices()
    for d in pf.devices: d.use = (d.type == 'OPTIX')
    sc.render.resolution_x = RES; sc.render.resolution_y = RES
    sc.render.film_transparent = True                       # sfondo trasparente → alpha
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        sc.view_settings.view_transform = 'Filmic'
    return sc

def load(p, srgb=True):
    img = bpy.data.images.load(p)
    try: img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    except Exception: pass
    return img

def add_world(sc, strength=0.25):
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = load(f"{A}/milkyway_8k.jpg")
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(env.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

def add_sun(energy=4.0, rot=(62, 8, -40), color=(1.0, 0.95, 0.86)):
    bpy.ops.object.light_add(type='SUN'); s = bpy.context.active_object
    s.data.energy = energy; s.data.angle = math.radians(1.0); s.data.color = color
    s.rotation_euler = (math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2]))
    return s

def add_camera(sc, ortho_scale, loc=(0, -14, 2.5), aim=(0, 0, 0)):
    from mathutils import Vector
    bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho_scale
    cam.data.clip_start = 0.01; cam.data.clip_end = 1000.0
    d = Vector(aim) - Vector(loc)                       # rotazione ESPLICITA (no TRACK_TO: inaffidabile in headless)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam

def planet_material(name, texfile, rough=1.0, bump=1.0, tilt_z=24):
    m = bpy.data.materials.new(name); m.use_nodes = True; bsdf = m.node_tree.nodes['Principled BSDF']
    tx = m.node_tree.nodes.new('ShaderNodeTexImage'); tx.image = load(f"{A}/{texfile}.jpg")
    m.node_tree.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs: bsdf.inputs['Specular IOR Level'].default_value = 0.12
    # micro-rilievo dalla luminanza texture
    try:
        bump_n = m.node_tree.nodes.new('ShaderNodeBump'); bump_n.inputs['Strength'].default_value = min(0.35, 0.05*bump)
        m.node_tree.links.new(tx.outputs['Color'], bump_n.inputs['Height'])
        m.node_tree.links.new(bump_n.outputs['Normal'], bsdf.inputs['Normal'])
    except Exception: pass
    return m

def add_atmo(radius, loc, col=(0.50, 0.64, 1.0), strength=1.2, blend=0.20):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=128, ring_count=64, location=loc)
    a = bpy.context.active_object; bpy.ops.object.shade_smooth()
    am = bpy.data.materials.new("Atmo"); am.use_nodes = True; nt = am.node_tree; nt.nodes.clear()
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = blend
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*col, 1); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader'); o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(lw.outputs['Fresnel'], mix.inputs['Fac']); nt.links.new(tr.outputs['BSDF'], mix.inputs[1])
    nt.links.new(em.outputs['Emission'], mix.inputs[2]); nt.links.new(mix.outputs['Shader'], o.inputs['Surface'])
    am.blend_method = 'BLEND' if hasattr(am, 'blend_method') else am.blend_method
    a.data.materials.append(am)
    return a

def add_rings(inner=1.28, outer=2.30, tilt=(3, 0, 0)):
    # anello REALE: toro appiattito nel piano equatoriale, texture 2k_saturn_ring_alpha mappata RADIALMENTE
    # (distanza dal centro in coord OGGETTO → U) con COLORE + ALPHA veri. Camera alta → ellisse.
    R = (inner + outer) / 2.0; minor = (outer - inner) / 2.0
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=minor, major_segments=256, minor_segments=4, location=(0, 0, 0))
    ring = bpy.context.active_object; ring.scale = (1, 1, 0.001); bpy.ops.object.shade_flat()
    ring.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), math.radians(tilt[2]))
    m = bpy.data.materials.new("Ring"); m.use_nodes = True; nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sub = nt.nodes.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(tc.outputs['Generated'], sub.inputs[0])                     # Generated centrato: raggio dal centro bbox
    dist = nt.nodes.new('ShaderNodeVectorMath'); dist.operation = 'LENGTH'
    nt.links.new(sub.outputs['Vector'], dist.inputs[0])
    inner_g = (inner / outer) * 0.5                                          # raggio generato: inner→inner_g, outer→0.5
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = inner_g; mr.inputs['From Max'].default_value = 0.5
    mr.inputs['To Min'].default_value = 0.02; mr.inputs['To Max'].default_value = 0.98
    nt.links.new(dist.outputs['Value'], mr.inputs['Value'])
    uv = nt.nodes.new('ShaderNodeCombineXYZ'); uv.inputs['Y'].default_value = 0.5   # U = raggio, V = centro strip
    nt.links.new(mr.outputs['Result'], uv.inputs['X'])
    img = nt.nodes.new('ShaderNodeTexImage'); img.image = load(f"{A}/2k_saturn_ring_alpha.png", srgb=True); img.extension = 'EXTEND'
    print("RING img:", (img.image.name, tuple(img.image.size)) if img.image else "NONE")
    nt.links.new(uv.outputs['Vector'], img.inputs['Vector'])
    nt.links.new(img.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(img.outputs['Alpha'], bsdf.inputs['Alpha'])               # gap tra le bande = alpha reale
    bsdf.inputs['Roughness'].default_value = 0.85
    if 'Specular IOR Level' in bsdf.inputs: bsdf.inputs['Specular IOR Level'].default_value = 0.10
    ring.data.materials.append(m)   # ★ il materiale va ASSEGNATO alla mesh (mancava → anello grigio di default)
    return ring

def render_one(cfg):
    sc = setup_scene()
    add_world(sc, strength=cfg.get('world', 0.25))
    add_sun(energy=cfg.get('sun', 4.0), rot=cfg.get('sunrot', (62, 8, -40)))
    cam = add_camera(sc, cfg['ortho'], loc=cfg.get('camloc', (0, -14, 2.5)))
    # pianeta
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=192, ring_count=96, location=(0, 0, 0))
    p = bpy.context.active_object; bpy.ops.object.shade_smooth()
    p.data.materials.append(planet_material(cfg['name'], cfg['tex'], rough=cfg.get('rough', 1.0), bump=cfg.get('bump', 1.0)))
    p.rotation_euler = (math.radians(6), 0, math.radians(cfg.get('spin', 24)))
    add_atmo(1.028, (0, 0, 0), col=cfg.get('atmo', (0.50, 0.64, 1.0)), strength=cfg.get('atmoS', 1.1), blend=cfg.get('atmoB', 0.20))
    if cfg.get('rings'): add_rings()
    sc.render.filepath = cfg['out']
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    print("DIAG", cfg['name'], "meshes=", len(meshes), "cam@", tuple(round(x, 2) for x in cam.location),
          "camrot=", tuple(round(math.degrees(a), 1) for a in cam.rotation_euler),
          "ortho=", cam.data.ortho_scale, "sun_ok=", any(o.type == 'LIGHT' for o in bpy.data.objects))
    print("RENDER PLATE", cfg['name'], RES, "samp", SAMP)
    bpy.ops.render.render(write_still=True)
    print("DONE", cfg['out'])

# --- Giove: fill grande, atmosfera calda ---
render_one({'name': 'jupiter', 'tex': '4k_jupiter', 'ortho': 2.35, 'bump': 1.4,
            'atmo': (1.0, 0.72, 0.42), 'atmoS': 1.0, 'atmoB': 0.22, 'spin': 30,
            'out': '/root/plate_out/jupiter.png'})

# --- Saturno: frame largo per gli anelli, camera PIÙ ALTA (ellisse), anello nel piano equatoriale ---
render_one({'name': 'saturn', 'tex': '4k_saturn', 'ortho': 5.2, 'bump': 1.3, 'rings': True,
            'atmo': (0.95, 0.85, 0.62), 'atmoS': 0.8, 'atmoB': 0.18, 'spin': 18, 'sunrot': (52, 6, -50),
            'camloc': (0, -13, 6.0),   # ~25° sopra il piano degli anelli
            'out': '/root/plate_out/saturn.png'})
print("ALL PLATES DONE")
