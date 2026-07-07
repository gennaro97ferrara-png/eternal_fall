# scene_craft.py — modelli 3D realistici di RAZZI + elementi spaziali (Cycles/OptiX).
# Ognuno: orientato con NASO +Y, motore -Y, centrato → pronto per l'iniezione GLB in Three.js
# (la class RocketShip orienta il gruppo lungo la velocità con l'asse +Y).
# Output: (1) un RENDER "contact sheet" in fila (RGBA, lit da HDRI) per valutare la qualità;
#         (2) un GLB per ogni mezzo in /root/craft_out/<nome>.glb
import bpy, math
A = "/root/eternal-fall/assets"
PREVIEW = False
RES = 1600 if PREVIEW else 2400
SAMP = 48 if PREVIEW else 160

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'
sc.cycles.samples = SAMP; sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPTIX'
except Exception: pass
pf = bpy.context.preferences.addons['cycles'].preferences
pf.compute_device_type = 'OPTIX'; pf.refresh_devices()
for d in pf.devices: d.use = (d.type == 'OPTIX')
sc.render.resolution_x = RES; sc.render.resolution_y = int(RES*0.42)
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
try:
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception: pass

def load(p, srgb=True):
    img = bpy.data.images.load(p)
    try: img.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    except Exception: pass
    return img

# world: HDRI milkyway SOLO per illuminare (film trasparente nasconde lo sfondo)
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = load(f"{A}/milkyway_8k.jpg")
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.35
wout = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(env.outputs['Color'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], wout.inputs['Surface'])
# sole key drammatico + fill freddo
bpy.ops.object.light_add(type='SUN', location=(10, -8, 12)); sun = bpy.context.active_object
sun.data.energy = 4.5; sun.data.angle = math.radians(1.0); sun.data.color = (1.0, 0.96, 0.9)
sun.rotation_euler = (math.radians(58), math.radians(10), math.radians(-40))
bpy.ops.object.light_add(type='SUN', location=(-12, -6, 4)); fill = bpy.context.active_object
fill.data.energy = 0.7; fill.data.color = (0.5, 0.62, 0.95); fill.rotation_euler = (math.radians(70), 0, math.radians(130))

# ---------- materiali (Principled → glTF-friendly) ----------
def mat(name, base, rough, metal, emis=None, emis_s=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*base, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emis is not None:
        try: b.inputs['Emission Color'].default_value = (*emis, 1); b.inputs['Emission Strength'].default_value = emis_s
        except Exception:
            try: b.inputs['Emission'].default_value = (*emis, 1); b.inputs['Emission Strength'].default_value = emis_s
            except Exception: pass
    return m
M = {
  'white':  mat('white',  (0.90,0.90,0.92), 0.42, 0.15),
  'black':  mat('black',  (0.045,0.045,0.05),0.5,  0.25),
  'steel':  mat('steel',  (0.80,0.82,0.86), 0.17, 1.0),
  'engine': mat('engine', (0.09,0.085,0.08),0.55, 0.75),
  'gold':   mat('gold',   (1.0,0.72,0.26),  0.34, 1.0),
  'solar':  mat('solar',  (0.03,0.05,0.16), 0.20, 0.35, emis=(0.02,0.05,0.16), emis_s=0.25),
  'glow':   mat('glow',   (1.0,0.6,0.25),   0.5,  0.0,  emis=(1.0,0.55,0.22), emis_s=14.0),
  'nozzle': mat('nozzle', (0.12,0.11,0.10), 0.35, 0.9),
  'red':    mat('red',    (0.7,0.12,0.10),  0.45, 0.3),
}

_objs = []   # (craft_name, object)
def add(prim, name, craft, matn, loc=(0,0,0), rot=(0,0,0), scale=(1,1,1), **kw):
    if prim == 'cyl': bpy.ops.mesh.primitive_cylinder_add(vertices=kw.get('v',32), radius=kw.get('r',1), depth=kw.get('d',1), location=loc)
    elif prim == 'cone': bpy.ops.mesh.primitive_cone_add(vertices=kw.get('v',32), radius1=kw.get('r1',1), radius2=kw.get('r2',0), depth=kw.get('d',1), location=loc)
    elif prim == 'box': bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    elif prim == 'sph': bpy.ops.mesh.primitive_uv_sphere_add(segments=kw.get('v',24), ring_count=kw.get('rc',12), radius=kw.get('r',1), location=loc)
    o = bpy.context.active_object; o.name = name; bpy.ops.object.shade_smooth() if prim in ('cyl','cone','sph') else None
    o.rotation_euler = tuple(math.radians(a) for a in rot); o.scale = scale
    o.data.materials.append(M[matn]); _objs.append((craft, o)); return o

# ---------- RAZZO A: "Ascent" (slanciato bianco, tipo Falcon) ----------
def rocket_ascent(cx):
    c = 'rocket_ascent'
    add('cyl', c+'_body', c, 'white', loc=(cx,0,0.2), r=0.30, d=2.6, v=40)
    add('cyl', c+'_band', c, 'black', loc=(cx,0,-0.75), r=0.305, d=0.28, v=40)     # interstadio
    add('cone', c+'_nose', c, 'white', loc=(cx,0,1.85), r1=0.30, r2=0.0, d=0.9, v=40)
    add('cyl', c+'_eng',  c, 'engine', loc=(cx,0,-1.28), r=0.34, d=0.34, v=40)      # sezione motori
    for k in range(9):                                                             # 9 ugelli
        a = k/9*6.2832; rr = 0.0 if k==8 else 0.20
        add('cone', c+'_noz%d'%k, c, 'nozzle', loc=(cx+math.cos(a)*rr, math.sin(a)*rr, -1.52), r1=0.06, r2=0.045, d=0.14, v=16)
    for k in range(4):                                                             # 4 grid-fin in alto
        a = k/4*6.2832
        add('box', c+'_fin%d'%k, c, 'black', loc=(cx+math.cos(a)*0.34, math.sin(a)*0.34, 1.15), rot=(0,0,math.degrees(a)), scale=(0.22,0.03,0.22))
    add('cone', c+'_flame', c, 'glow', loc=(cx,0,-1.95), r1=0.16, r2=0.02, d=0.7, v=20)

# ---------- RAZZO B: "Heavy" (multi-stadio, tipo Saturn V) ----------
def rocket_heavy(cx):
    c = 'rocket_heavy'
    add('cyl', c+'_s1', c, 'white', loc=(cx,0,-0.7), r=0.5, d=1.7, v=44)            # stadio 1 largo
    for k in range(4):                                                             # bande nere roll-pattern
        add('cyl', c+'_b%d'%k, c, 'black', loc=(cx,0,-1.35+k*0.42), r=0.505, d=0.10, v=44)
    add('cone', c+'_i1', c, 'white', loc=(cx,0,0.35), r1=0.5, r2=0.36, d=0.5, v=44) # interstadio conico
    add('cyl', c+'_s2', c, 'white', loc=(cx,0,0.95), r=0.36, d=0.9, v=40)
    add('cone', c+'_i2', c, 'white', loc=(cx,0,1.6), r1=0.36, r2=0.24, d=0.4, v=40)
    add('cyl', c+'_s3', c, 'white', loc=(cx,0,2.0), r=0.24, d=0.55, v=36)
    add('cone', c+'_capsule', c, 'steel', loc=(cx,0,2.45), r1=0.24, r2=0.10, d=0.4, v=36)
    add('cyl', c+'_tower', c, 'red', loc=(cx,0,2.85), r=0.02, d=0.5, v=8)           # torre di salvataggio
    for k in range(5):                                                             # 5 ugelli (F-1)
        a = k/4*6.2832; rr = 0 if k==4 else 0.30
        add('cone', c+'_noz%d'%k, c, 'nozzle', loc=(cx+math.cos(a)*rr, math.sin(a)*rr, -1.7), r1=0.13, r2=0.09, d=0.3, v=20)
    add('cone', c+'_flame', c, 'glow', loc=(cx,0,-2.2), r1=0.34, r2=0.04, d=1.1, v=24)

# ---------- RAZZO C: "Steel" (acciaio lucido, tipo Starship) ----------
def rocket_steel(cx):
    c = 'rocket_steel'
    add('cyl', c+'_body', c, 'steel', loc=(cx,0,0.0), r=0.40, d=2.4, v=48)
    add('cone', c+'_nose', c, 'steel', loc=(cx,0,1.75), r1=0.40, r2=0.0, d=1.1, v=48)
    for k in range(2):                                                             # 2 flap superiori
        s = 1 if k==0 else -1
        add('box', c+'_fwd%d'%k, c, 'steel', loc=(cx+0.42*s,0,1.0), rot=(0,15*s,0), scale=(0.10,0.34,0.5))
    for k in range(2):                                                             # 2 flap inferiori
        s = 1 if k==0 else -1
        add('box', c+'_aft%d'%k, c, 'steel', loc=(cx+0.5*s,0,-0.9), rot=(0,10*s,0), scale=(0.12,0.5,0.6))
    for k in range(3):                                                             # 3 raptor
        a = k/3*6.2832
        add('cone', c+'_noz%d'%k, c, 'nozzle', loc=(cx+math.cos(a)*0.18, math.sin(a)*0.18, -1.35), r1=0.10, r2=0.07, d=0.2, v=18)
    add('cone', c+'_flame', c, 'glow', loc=(cx,0,-1.75), r1=0.22, r2=0.03, d=0.85, v=22)

# ---------- SATELLITE: corpo oro + pannelli solari + antenna ----------
def satellite(cx):
    c = 'satellite'
    add('box', c+'_body', c, 'gold', loc=(cx,0,0), scale=(0.5,0.5,0.7))
    for k in range(2):                                                             # 2 ali solari
        s = 1 if k==0 else -1
        add('box', c+'_boom%d'%k, c, 'engine', loc=(cx+0.5*s,0,0), scale=(0.5,0.03,0.03))
        add('box', c+'_panel%d'%k, c, 'solar', loc=(cx+1.4*s,0,0), scale=(1.3,0.02,0.6))
    add('cyl', c+'_dish_arm', c, 'engine', loc=(cx,0,0.55), r=0.02, d=0.3, v=8)
    add('cone', c+'_dish', c, 'white', loc=(cx,0,0.78), r1=0.28, r2=0.05, d=0.16, rot=(0,0,0), v=28)
    add('cyl', c+'_ant', c, 'steel', loc=(cx,0.25,0.35), r=0.008, d=0.5, rot=(90,0,0), v=6)

# posiziona i mezzi in fila (asse X), naso verso +Z per il render in piedi
CRAFT = [('rocket_ascent', rocket_ascent, -6.0), ('rocket_heavy', rocket_heavy, -2.0),
         ('rocket_steel', rocket_steel, 2.0), ('satellite', satellite, 6.0)]
for name, fn, cx in CRAFT:
    fn(cx)

# NB: costruiti con asse +Z (Blender su). Per l'export GLB li ruoto in +Y? Three.js RocketShip usa +Y.
# Qui li teniamo +Z per il render in piedi; l'export li ruota di -90° X → naso +Y.

# ---------- camera per il contact sheet ----------
bpy.ops.object.camera_add(location=(0, -20, 0)); cam = bpy.context.active_object; sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 18.0
from mathutils import Vector
cam.rotation_euler = (Vector((0,0,0.4)) - Vector((0,-20,0))).to_track_quat('-Z','Z').to_euler()

sc.render.filepath = "/root/craft_out/lineup.png"
print("RENDER CRAFT LINEUP", RES); bpy.ops.render.render(write_still=True); print("DONE lineup")

# ---------- export GLB per mezzo (ruotati naso +Y) ----------
import os
os.makedirs("/root/craft_out", exist_ok=True)
for name, fn, cx in CRAFT:
    objs = [o for (cn, o) in _objs if cn == name]
    # sposta al centro + ruota naso +Z→+Y per l'orientamento di volo Three.js
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # parent a un empty al centro, applica offset -cx, ruota -90° X
    bpy.ops.object.empty_add(location=(cx,0,0)); root = bpy.context.active_object; root.name = name+'_root'
    for o in objs: o.select_set(True)
    root.select_set(True); bpy.context.view_layer.objects.active = root
    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
    root.location = (0,0,0)   # centra il mezzo sull'origine; export_yup converte Z-up→Y-up (naso +Z → +Y in three)
    bpy.ops.object.select_all(action='DESELECT'); root.select_set(True)
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath="/root/craft_out/%s.glb"%name, use_selection=True, export_format='GLB', export_yup=True, export_apply=True)
    print("EXPORT", name)
    # rimetti a posto per non disturbare i successivi (già esportati)
print("ALL CRAFT DONE")
