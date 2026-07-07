import bpy, math, random
random.seed(19)
A="/root/eternal-fall/assets"
PREVIEW=True
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='GPU'
sc.cycles.samples=28 if PREVIEW else 110; sc.cycles.use_denoising=True
try: sc.cycles.denoiser='OPTIX'
except: pass
pf=bpy.context.preferences.addons['cycles'].preferences
pf.compute_device_type='OPTIX'; pf.refresh_devices()
for d in pf.devices: d.use=(d.type=='OPTIX')
sc.render.resolution_x=960 if PREVIEW else 1920
sc.render.resolution_y=540 if PREVIEW else 1080
sc.render.image_settings.file_format='PNG'
try: sc.view_settings.view_transform='AgX'
except: pass
def load(p): return bpy.data.images.load(p)
# dim world (disk must pop)
w=bpy.data.worlds.new("W"); sc.world=w; w.use_nodes=True; nt=w.node_tree; nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment'); env.image=load(f"{A}/milkyway_8k.jpg")
bg=nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value=0.35
ow=nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(env.outputs['Color'],bg.inputs['Color']); nt.links.new(bg.outputs['Background'],ow.inputs['Surface'])
CEN=(8,55,5); TILT=math.radians(42)
# event horizon: pure black sphere
bpy.ops.mesh.primitive_uv_sphere_add(radius=6,segments=96,ring_count=48,location=CEN)
bh=bpy.context.active_object; bpy.ops.object.shade_smooth()
bm=bpy.data.materials.new("bh"); bm.use_nodes=True; bn=bm.node_tree; bn.nodes.clear()
emb=bn.nodes.new('ShaderNodeEmission'); emb.inputs['Color'].default_value=(0,0,0,1); emb.inputs['Strength'].default_value=0
ob=bn.nodes.new('ShaderNodeOutputMaterial'); bn.links.new(emb.outputs['Emission'],ob.inputs['Surface'])
bh.data.materials.append(bm)
# accretion disk = flat emissive TORUS (real ring geometry, no alpha tricks)
bpy.ops.mesh.primitive_torus_add(major_radius=13, minor_radius=7.0, major_segments=160, minor_segments=32, location=CEN)
disk=bpy.context.active_object; disk.scale=(1,1,0.05); disk.rotation_euler=(TILT,0,math.radians(12))
bpy.ops.object.shade_smooth()
dm=bpy.data.materials.new("disk"); dm.use_nodes=True; dn=dm.node_tree; dn.nodes.clear()
tc=dn.nodes.new('ShaderNodeTexCoord')
flat=dn.nodes.new('ShaderNodeVectorMath'); flat.operation='MULTIPLY'; flat.inputs[1].default_value=(1,1,0)
ln=dn.nodes.new('ShaderNodeVectorMath'); ln.operation='LENGTH'
dn.links.new(tc.outputs['Object'],flat.inputs[0]); dn.links.new(flat.outputs['Vector'],ln.inputs[0])
mr=dn.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value=6.0; mr.inputs['From Max'].default_value=20.0
dn.links.new(ln.outputs['Value'],mr.inputs['Value'])
ramp=dn.nodes.new('ShaderNodeValToRGB'); dn.links.new(mr.outputs['Result'],ramp.inputs['Fac'])
ramp.color_ramp.elements[0].position=0.0; ramp.color_ramp.elements[0].color=(1.0,0.96,0.86,1)
ramp.color_ramp.elements[1].position=1.0; ramp.color_ramp.elements[1].color=(0.55,0.03,0.0,1)
m1=ramp.color_ramp.elements.new(0.30); m1.color=(1.0,0.45,0.08,1)
noise=dn.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=10.0; noise.inputs['Detail'].default_value=8.0
dn.links.new(tc.outputs['Object'],noise.inputs['Vector'])
# brightness: hotter toward the inner edge, times turbulence; moderate so it does not blow out
inv=dn.nodes.new('ShaderNodeMath'); inv.operation='SUBTRACT'; inv.inputs[0].default_value=1.0
dn.links.new(mr.outputs['Result'],inv.inputs[1])
hot=dn.nodes.new('ShaderNodeMath'); hot.operation='POWER'; hot.inputs[1].default_value=1.6
dn.links.new(inv.outputs['Value'],hot.inputs[0])
mul=dn.nodes.new('ShaderNodeMath'); mul.operation='MULTIPLY'; mul.inputs[1].default_value=5.5
dn.links.new(hot.outputs['Value'],mul.inputs[0])
trb=dn.nodes.new('ShaderNodeMath'); trb.operation='MULTIPLY'
dn.links.new(mul.outputs['Value'],trb.inputs[0]); dn.links.new(noise.outputs['Fac'],trb.inputs[1])
add=dn.nodes.new('ShaderNodeMath'); add.operation='ADD'; add.inputs[1].default_value=0.6
dn.links.new(trb.outputs['Value'],add.inputs[0])
emo=dn.nodes.new('ShaderNodeEmission'); dn.links.new(ramp.outputs['Color'],emo.inputs['Color']); dn.links.new(add.outputs['Value'],emo.inputs['Strength'])
do=dn.nodes.new('ShaderNodeOutputMaterial'); dn.links.new(emo.outputs['Emission'],do.inputs['Surface'])
disk.data.materials.append(dm)
# character
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=f"{A}/characters/astrodog.glb")
newo=[o for o in bpy.data.objects if o not in before]
dog=bpy.data.objects.new("Dog",None); sc.collection.objects.link(dog)
for o in newo:
    if o.parent is None: o.parent=dog
dog.scale=(0.9,0.9,0.9)
# faint rim light on character
bpy.ops.object.light_add(type='SUN',location=(20,-8,10)); sun=bpy.context.active_object
sun.data.energy=1.4; sun.data.color=(1.0,0.7,0.5); sun.rotation_euler=(math.radians(64),0,math.radians(-40))
# camera chase toward the black hole
bpy.ops.object.camera_add(location=(0,-6,0.6)); cam=bpy.context.active_object; sc.camera=cam
cam.data.lens=34; cam.data.dof.use_dof=True; cam.data.dof.focus_object=dog; cam.data.dof.aperture_fstop=3.5
con=cam.constraints.new('TRACK_TO'); con.target=dog; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'
try: bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
except: pass
NF=192; sc.frame_start=1; sc.frame_end=NF; sc.render.fps=24
dog.location=(-0.6,8.0,0.2); dog.keyframe_insert('location',frame=1)
dog.location=(1.2,32.0,1.0); dog.keyframe_insert('location',frame=NF)
dog.rotation_euler=(math.radians(84),0,math.radians(150)); dog.keyframe_insert('rotation_euler',frame=1)
dog.rotation_euler=(math.radians(150),math.radians(60),math.radians(420)); dog.keyframe_insert('rotation_euler',frame=NF)
cam.location=(-0.6,1.0,0.7); cam.keyframe_insert('location',frame=1)
cam.location=(1.2,24.5,1.7); cam.keyframe_insert('location',frame=NF)
disk.rotation_euler=(TILT,0,math.radians(12)); disk.keyframe_insert('rotation_euler',frame=1)
disk.rotation_euler=(TILT,0,math.radians(40)); disk.keyframe_insert('rotation_euler',frame=NF)
sc.render.filepath="/root/bh_seq/f_"
print("RENDER BH"); bpy.ops.render.render(animation=True); print("DONE")
