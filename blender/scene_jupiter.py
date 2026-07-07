import bpy, math
from mathutils import Vector

A = "/root/eternal-fall/assets"
OUT = "/root/blender_out/hero1.png"

# ---------- reset ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'GPU'
sc.cycles.samples = 96
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPTIX'
except Exception as e: print("denoiser", e)

# GPU prefs (OptiX on the 4090)
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.refresh_devices()
for d in prefs.devices:
    d.use = (d.type == 'OPTIX')
print("DEVICES:", [(d.name, d.type, d.use) for d in prefs.devices])

sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = OUT
# cinematic color
try: sc.view_settings.view_transform = 'AgX'
except Exception: sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'AgX - Medium High Contrast' if sc.view_settings.view_transform=='AgX' else 'None'

def load(p): return bpy.data.images.load(p)

# ---------- WORLD: Milky Way ----------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = load(f"{A}/milkyway_8k.jpg")
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 1.15
out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

# ---------- PLANET (Jupiter, big & dramatic) ----------
bpy.ops.mesh.primitive_uv_sphere_add(radius=13, segments=192, ring_count=96, location=(9, 33, 7))
planet = bpy.context.active_object; planet.name = "Jupiter"
bpy.ops.object.shade_smooth()
pm = bpy.data.materials.new("JupMat"); pm.use_nodes = True
bsdf = pm.node_tree.nodes.get('Principled BSDF')
tx = pm.node_tree.nodes.new('ShaderNodeTexImage'); tx.image = load(f"{A}/4k_jupiter.jpg"); tx.image.colorspace_settings.name='sRGB'
pm.node_tree.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 1.0
if 'Specular IOR Level' in bsdf.inputs: bsdf.inputs['Specular IOR Level'].default_value = 0.15
planet.data.materials.append(pm)
planet.rotation_euler = (math.radians(8), 0, math.radians(24))

# thin atmospheric rim (fresnel emission shell)
bpy.ops.mesh.primitive_uv_sphere_add(radius=13.5, segments=128, ring_count=64, location=planet.location)
atmo = bpy.context.active_object; atmo.name="Atmo"; bpy.ops.object.shade_smooth()
am = bpy.data.materials.new("AtmoMat"); am.use_nodes=True; ant=am.node_tree; ant.nodes.clear()
lw = ant.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value=0.20
em = ant.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value=(0.50,0.64,1.0,1); em.inputs['Strength'].default_value=1.25
tr = ant.nodes.new('ShaderNodeBsdfTransparent')
mix = ant.nodes.new('ShaderNodeMixShader'); ao = ant.nodes.new('ShaderNodeOutputMaterial')
ant.links.new(lw.outputs['Fresnel'], mix.inputs['Fac'])
ant.links.new(tr.outputs['BSDF'], mix.inputs[1]); ant.links.new(em.outputs['Emission'], mix.inputs[2])
ant.links.new(mix.outputs['Shader'], ao.inputs['Surface'])
atmo.data.materials.append(am)

# ---------- CHARACTER: astrodog (falling, seen from behind) ----------
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=f"{A}/characters/astrodog.glb")
newobj = [o for o in bpy.data.objects if o not in before]
dog_empty = bpy.data.objects.new("DogRoot", None); sc.collection.objects.link(dog_empty)
for o in newobj:
    if o.parent is None:
        o.parent = dog_empty
dog_empty.location = (-1.7, 5.0, -0.35)
dog_empty.scale = (0.82,0.82,0.82)
dog_empty.rotation_euler = (math.radians(86), math.radians(10), math.radians(196))  # back to camera, tilted as falling

# ---------- SUN (dramatic side key) ----------
bpy.ops.object.light_add(type='SUN', location=(28,-4,14))
sun = bpy.context.active_object; sun.data.energy = 4.2; sun.data.angle = math.radians(1.2)
sun.data.color = (1.0, 0.93, 0.82)
sun.rotation_euler = (math.radians(62), math.radians(8), math.radians(-38))
# faint fill
bpy.ops.object.light_add(type='SUN', location=(-20,-10,6))
fill = bpy.context.active_object; fill.data.energy=0.22; fill.data.color=(0.45,0.56,0.95)
fill.rotation_euler=(math.radians(70),0,math.radians(120))

# ---------- CAMERA ----------
bpy.ops.object.camera_add(location=(0.4, -5.0, 0.7))
cam = bpy.context.active_object; sc.camera = cam
cam.data.lens = 36
cam.data.dof.use_dof = True
cam.data.dof.focus_object = dog_empty
cam.data.dof.aperture_fstop = 2.8
tgt = bpy.data.objects.new("Aim", None); sc.collection.objects.link(tgt)
tgt.location = (1.6, 12.0, 1.4)  # between dog and planet
con = cam.constraints.new('TRACK_TO'); con.target = tgt; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'

# ---------- ANIMATION (slow, cinematic, constant motion) ----------
try: bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'   # tutti i keyframe LINEARI = moto costante (no ease)
except Exception as e: print("interp pref", e)
sc.frame_start = 1; sc.frame_end = 720; sc.render.fps = 24   # 30s
cam.location = (0.4,-5.0,0.7);  cam.keyframe_insert('location', frame=1)
cam.location = (2.6,0.2,2.1);   cam.keyframe_insert('location', frame=720)
tgt.location = (1.6,12.0,1.4);  tgt.keyframe_insert('location', frame=1)
tgt.location = (3.4,14.0,3.2);  tgt.keyframe_insert('location', frame=720)
dog_empty.rotation_euler=(math.radians(86),math.radians(10),math.radians(196)); dog_empty.keyframe_insert('rotation_euler',frame=1)
dog_empty.rotation_euler=(math.radians(72),math.radians(-6),math.radians(233));  dog_empty.keyframe_insert('rotation_euler',frame=720)
dog_empty.location=(-1.7,5.0,-0.35); dog_empty.keyframe_insert('location',frame=1)
dog_empty.location=(-1.15,5.0,0.7);  dog_empty.keyframe_insert('location',frame=720)
planet.rotation_euler=(math.radians(8),0,math.radians(24)); planet.keyframe_insert('rotation_euler',frame=1)
planet.rotation_euler=(math.radians(8),0,math.radians(42)); planet.keyframe_insert('rotation_euler',frame=720)
sc.render.filepath = "/root/blender_seq/f_"
print("RENDER ANIM 1-96")
bpy.ops.render.render(animation=True)
print("DONE")
