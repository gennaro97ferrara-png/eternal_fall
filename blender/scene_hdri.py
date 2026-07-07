# scene_hdri.py — HDRI AMBIENTE equirettangolare 360° (Cycles) per il Modello A — RICCO + alta risoluzione.
# Base stellare reale (milkyway) + nebulosa procedurale multi-colore + 2 stelle-eroe (calda + fredda) per luce a due toni.
# Output: Radiance .hdr equirect → Three.js RGBELoader → scene.environment + backdrop.
# CROSS-PLATFORM: device auto (OptiX/METAL/CUDA/CPU); path via env EF_ASSETS/EF_OUT/EF_RES/EF_SAMP.
import bpy, math, os
A   = os.environ.get('EF_ASSETS', "/root/eternal-fall/assets")
OUT = os.environ.get('EF_OUT', "/root/hdri_out/space_env.hdr")
RES = int(os.environ.get('EF_RES', '4096'))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('EF_SAMP', '140')); sc.cycles.use_denoising = True
# device cross-platform
pf = bpy.context.preferences.addons['cycles'].preferences; _best = None
for _dt in ('OPTIX', 'METAL', 'CUDA', 'HIP', 'ONEAPI'):
    try:
        pf.compute_device_type = _dt; pf.refresh_devices()
        if any(d.type == _dt for d in pf.devices): _best = _dt; break
    except Exception: pass
if _best:
    for d in pf.devices: d.use = (d.type == _best)
    sc.cycles.device = 'GPU'
    try: sc.cycles.denoiser = ('OPTIX' if _best == 'OPTIX' else 'OPENIMAGEDENOISE')
    except Exception: pass
else:
    sc.cycles.device = 'CPU'
    try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
print("CYCLES device:", _best or 'CPU')

sc.render.resolution_x = RES; sc.render.resolution_y = RES // 2
sc.render.image_settings.file_format = 'HDR'   # Radiance HDR (RGBE)
try: sc.view_settings.view_transform = 'Raw'   # HDRI LINEARE (il tone-map lo fa Three.js/AgX)
except Exception:
    try: sc.view_settings.view_transform = 'Standard'
    except Exception: pass

def load(p):
    img = bpy.data.images.load(p)
    try: img.colorspace_settings.name = 'sRGB'
    except Exception: pass
    return img

# ---------- WORLD: stelle reali + nebulosa RICCA ----------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld')
bg  = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.0
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = load(f"{A}/milkyway_8k.jpg")

tc = nt.nodes.new('ShaderNodeTexCoord')
mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])

# nebulosa: noise dettagliato → color ramp MULTI-COLORE (5 stop)
noise = nt.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 2.6; noise.inputs['Detail'].default_value = 12.0; noise.inputs['Roughness'].default_value = 0.74
nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])
ramp = nt.nodes.new('ShaderNodeValToRGB'); cr = ramp.color_ramp
cr.elements[0].position = 0.40; cr.elements[0].color = (0, 0, 0, 1)
cr.elements[1].position = 0.55; cr.elements[1].color = (0.010, 0.045, 0.14, 1)   # blu-notte profondo
e2 = cr.elements.new(0.66); e2.color = (0.02, 0.22, 0.30, 1)                       # teal
e3 = cr.elements.new(0.78); e3.color = (0.30, 0.06, 0.34, 1)                       # magenta
e4 = cr.elements.new(0.88); e4.color = (0.55, 0.22, 0.08, 1)                       # ambra
e5 = cr.elements.new(0.96); e5.color = (0.85, 0.62, 0.38, 1)                       # core caldo brillante
nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])

# maschera a chiazze (la nebulosa appare a regioni, non ovunque)
mask = nt.nodes.new('ShaderNodeTexNoise'); mask.inputs['Scale'].default_value = 0.95; mask.inputs['Detail'].default_value = 3.0
nt.links.new(mp.outputs['Vector'], mask.inputs['Vector'])
maskpow = nt.nodes.new('ShaderNodeMath'); maskpow.operation = 'POWER'; maskpow.inputs[1].default_value = 2.2
nt.links.new(mask.outputs['Fac'], maskpow.inputs[0])

nebmul = nt.nodes.new('ShaderNodeVectorMath'); nebmul.operation = 'SCALE'; nebmul.inputs['Scale'].default_value = 2.4   # intensità nebulosa (più ricca)
nt.links.new(ramp.outputs['Color'], nebmul.inputs[0])
nebmask = nt.nodes.new('ShaderNodeVectorMath'); nebmask.operation = 'MULTIPLY'
nt.links.new(nebmul.outputs['Vector'], nebmask.inputs[0])
mask3 = nt.nodes.new('ShaderNodeCombineXYZ')
nt.links.new(maskpow.outputs['Value'], mask3.inputs['X']); nt.links.new(maskpow.outputs['Value'], mask3.inputs['Y']); nt.links.new(maskpow.outputs['Value'], mask3.inputs['Z'])
nt.links.new(mask3.outputs['Vector'], nebmask.inputs[1])

# combina: stelle (env) + nebulosa (add)
addc = nt.nodes.new('ShaderNodeVectorMath'); addc.operation = 'ADD'
nt.links.new(env.outputs['Color'], addc.inputs[0]); nt.links.new(nebmask.outputs['Vector'], addc.inputs[1])
nt.links.new(addc.outputs['Vector'], bg.inputs['Color']); nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

# ---------- 2 STELLE-EROE (luce a due toni: calda + fredda distante) ----------
def hero_star(loc, radius, color, strength):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc); st = bpy.context.active_object; bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("star"); m.use_nodes = True; sn = m.node_tree; sn.nodes.clear()
    em = sn.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1); em.inputs['Strength'].default_value = strength
    o = sn.nodes.new('ShaderNodeOutputMaterial'); sn.links.new(em.outputs['Emission'], o.inputs['Surface']); st.data.materials.append(m)
hero_star((60, 22, 14), 6.0, (1.0, 0.88, 0.66), 9.0)     # calda (key)
hero_star((-52, -10, -20), 3.4, (0.62, 0.74, 1.0), 4.0)  # fredda distante (fill/contrasto)

# ---------- CAMERA PANORAMICA EQUIRETTANGOLARE all'origine ----------
bpy.ops.object.camera_add(location=(0, 0, 0)); cam = bpy.context.active_object; sc.camera = cam
cam.data.type = 'PANO'
try: cam.data.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    try: cam.data.cycles.panorama_type = 'EQUIRECTANGULAR'
    except Exception as e: print("pano", e)
cam.rotation_euler = (math.radians(90), 0, math.radians(-90))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
sc.render.filepath = OUT
print("RENDER HDRI", sc.render.resolution_x, "x", sc.render.resolution_y, "samples", sc.cycles.samples)
bpy.ops.render.render(write_still=True)
print("DONE", OUT)
