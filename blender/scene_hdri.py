# scene_hdri.py — genera un HDRI AMBIENTE equirettangolare 360° (Cycles/OptiX) per il Modello A.
# Base stellare = milkyway_8k reale + nebulosa procedurale colorata (teal/magenta/ambra) + una stella-eroe calda.
# Output: Radiance .hdr equirect → in Three.js via RGBELoader → scene.environment + backdrop.
# PREVIEW=True: 2048x1024 @ 24 samples (~secondi). False: 8192x4096 @ 110 (finale).
import bpy, math
A = "/root/eternal-fall/assets"
OUT = "/root/hdri_out/space_env.hdr"
PREVIEW = False   # finale 4096x2048 (equirect env web-friendly)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'GPU'
sc.cycles.samples = 24 if PREVIEW else 110
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPTIX'
except Exception as e: print("denoiser", e)
pf = bpy.context.preferences.addons['cycles'].preferences
pf.compute_device_type = 'OPTIX'; pf.refresh_devices()
for d in pf.devices: d.use = (d.type == 'OPTIX')
print("DEVICES:", [(d.name, d.type, d.use) for d in pf.devices])

sc.render.resolution_x = 2048 if PREVIEW else 2048   # 2048x1024 equirect = ~7MB HDR, web-friendly
sc.render.resolution_y = 1024 if PREVIEW else 1024
sc.render.image_settings.file_format = 'HDR'   # Radiance HDR (RGBE) → leggero per il web
# linear/HDR: NIENTE view transform bruciato dentro (l'HDRI resta lineare; il tone-map lo fa Three.js/AgX)
try: sc.view_settings.view_transform = 'Raw'
except Exception:
    try: sc.view_settings.view_transform = 'Standard'
    except Exception: pass

def load(p):
    img = bpy.data.images.load(p);
    try: img.colorspace_settings.name = 'sRGB'
    except Exception: pass
    return img

# ---------- WORLD: stelle reali + nebulosa procedurale ----------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld')
bg  = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0

env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = load(f"{A}/milkyway_8k.jpg")

# direzione di vista come coordinate 3D per la nebulosa
tc = nt.nodes.new('ShaderNodeTexCoord')
mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])

# nebulosa: noise dettagliato → color ramp (teal→viola→ambra)
noise = nt.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 2.4
noise.inputs['Detail'].default_value = 9.0
noise.inputs['Roughness'].default_value = 0.72
nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])

ramp = nt.nodes.new('ShaderNodeValToRGB')
cr = ramp.color_ramp
cr.elements[0].position = 0.42; cr.elements[0].color = (0, 0, 0, 1)
cr.elements[1].position = 0.60; cr.elements[1].color = (0.015, 0.16, 0.20, 1)   # teal profondo
e2 = cr.elements.new(0.76); e2.color = (0.20, 0.045, 0.28, 1)                    # viola/magenta
e3 = cr.elements.new(0.90); e3.color = (0.34, 0.14, 0.05, 1)                     # ambra calda
nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

# maschera larga: la nebulosa appare a chiazze, non ovunque
mask = nt.nodes.new('ShaderNodeTexNoise')
mask.inputs['Scale'].default_value = 0.9
mask.inputs['Detail'].default_value = 3.0
nt.links.new(mp.outputs['Vector'], mask.inputs['Vector'])
maskpow = nt.nodes.new('ShaderNodeMath'); maskpow.operation = 'POWER'
maskpow.inputs[1].default_value = 2.4
nt.links.new(mask.outputs['Fac'], maskpow.inputs[0])

nebmul = nt.nodes.new('ShaderNodeVectorMath'); nebmul.operation = 'SCALE'
nebmul.inputs['Scale'].default_value = 1.75   # intensità nebulosa (più ricca)
nt.links.new(ramp.outputs['Color'], nebmul.inputs[0])
nebmask = nt.nodes.new('ShaderNodeVectorMath'); nebmask.operation = 'MULTIPLY'
nt.links.new(nebmul.outputs['Vector'], nebmask.inputs[0])
mask3 = nt.nodes.new('ShaderNodeCombineXYZ')
nt.links.new(maskpow.outputs['Value'], mask3.inputs['X'])
nt.links.new(maskpow.outputs['Value'], mask3.inputs['Y'])
nt.links.new(maskpow.outputs['Value'], mask3.inputs['Z'])
nt.links.new(mask3.outputs['Vector'], nebmask.inputs[1])

# combina: stelle (env) + nebulosa (add)
addc = nt.nodes.new('ShaderNodeVectorMath'); addc.operation = 'ADD'
nt.links.new(env.outputs['Color'], addc.inputs[0])
nt.links.new(nebmask.outputs['Vector'], addc.inputs[1])
nt.links.new(addc.outputs['Vector'], bg.inputs['Color'])
nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

# ---------- STELLA-EROE (chiave di luce direzionale nell'HDRI) ----------
bpy.ops.mesh.primitive_uv_sphere_add(radius=6, location=(60, 22, 14)); star = bpy.context.active_object
bpy.ops.object.shade_smooth()
sm = bpy.data.materials.new("star"); sm.use_nodes = True; sn = sm.node_tree; sn.nodes.clear()
se = sn.nodes.new('ShaderNodeEmission'); se.inputs['Color'].default_value = (1.0, 0.88, 0.66, 1); se.inputs['Strength'].default_value = 9   # stella-eroe morbida (era 60 = bruciava)
so = sn.nodes.new('ShaderNodeOutputMaterial'); sn.links.new(se.outputs['Emission'], so.inputs['Surface'])
star.data.materials.append(sm)

# ---------- CAMERA PANORAMICA EQUIRETTANGOLARE all'origine ----------
bpy.ops.object.camera_add(location=(0, 0, 0)); cam = bpy.context.active_object; sc.camera = cam
cam.data.type = 'PANO'
try: cam.data.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    try: cam.data.cycles.panorama_type = 'EQUIRECTANGULAR'
    except Exception as e: print("pano", e)
cam.rotation_euler = (math.radians(90), 0, math.radians(-90))   # orienta l'equirect

sc.render.filepath = OUT
print("RENDER HDRI", sc.render.resolution_x, "x", sc.render.resolution_y, "samples", sc.cycles.samples)
bpy.ops.render.render(write_still=True)
print("DONE", OUT)
