import bpy, math, random
random.seed(11)
A="/root/eternal-fall/assets"
PREVIEW=True
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='GPU'
sc.cycles.samples=24 if PREVIEW else 96; sc.cycles.use_denoising=True
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
# world
w=bpy.data.worlds.new("W"); sc.world=w; w.use_nodes=True; nt=w.node_tree; nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment'); env.image=load(f"{A}/milkyway_8k.jpg")
bg=nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value=1.05
ow=nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(env.outputs['Color'],bg.inputs['Color']); nt.links.new(bg.outputs['Background'],ow.inputs['Surface'])
# Saturn (tilted so rings read)
TILT=math.radians(24)
bpy.ops.mesh.primitive_uv_sphere_add(radius=13,segments=160,ring_count=80,location=(9,58,6))
planet=bpy.context.active_object; bpy.ops.object.shade_smooth()
pm=bpy.data.materials.new("S"); pm.use_nodes=True; pb=pm.node_tree.nodes['Principled BSDF']
tx=pm.node_tree.nodes.new('ShaderNodeTexImage'); tx.image=load(f"{A}/4k_saturn.jpg")
pm.node_tree.links.new(tx.outputs['Color'],pb.inputs['Base Color']); pb.inputs['Roughness'].default_value=1.0
planet.data.materials.append(pm)
planet.rotation_euler=(TILT,0,math.radians(10))
# RING: flat disk with radial-mapped ring texture
bpy.ops.mesh.primitive_circle_add(vertices=256, radius=30, fill_type='NGON', location=planet.location)
ring=bpy.context.active_object; ring.rotation_euler=(TILT,0,math.radians(10))
rmat=bpy.data.materials.new("ring"); rmat.use_nodes=True; rn=rmat.node_tree; rn.nodes.clear()
tc=rn.nodes.new('ShaderNodeTexCoord')
sub=rn.nodes.new('ShaderNodeVectorMath'); sub.operation='SUBTRACT'; sub.inputs[1].default_value=(0.5,0.5,0.0)
ln=rn.nodes.new('ShaderNodeVectorMath'); ln.operation='LENGTH'
mr=rn.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value=0.20; mr.inputs['From Max'].default_value=0.5
cxyz=rn.nodes.new('ShaderNodeCombineXYZ'); cxyz.inputs['Y'].default_value=0.5
rimg=rn.nodes.new('ShaderNodeTexImage'); rimg.image=load(f"{A}/2k_saturn_ring_alpha.png"); rimg.extension='EXTEND'
em=rn.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value=1.0
tr=rn.nodes.new('ShaderNodeBsdfTransparent')
mix=rn.nodes.new('ShaderNodeMixShader'); out=rn.nodes.new('ShaderNodeOutputMaterial')
rn.links.new(tc.outputs['Generated'],sub.inputs[0]); rn.links.new(sub.outputs['Vector'],ln.inputs[0])
rn.links.new(ln.outputs['Value'],mr.inputs['Value']); rn.links.new(mr.outputs['Result'],cxyz.inputs['X'])
rn.links.new(cxyz.outputs['Vector'],rimg.inputs['Vector'])
rn.links.new(rimg.outputs['Color'],em.inputs['Color'])
rn.links.new(rimg.outputs['Alpha'],mix.inputs['Fac'])
rn.links.new(tr.outputs['BSDF'],mix.inputs[1]); rn.links.new(em.outputs['Emission'],mix.inputs[2])
rn.links.new(mix.outputs['Shader'],out.inputs['Surface'])
ring.data.materials.append(rmat)
# character
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=f"{A}/characters/astrodog.glb")
newo=[o for o in bpy.data.objects if o not in before]
dog=bpy.data.objects.new("Dog",None); sc.collection.objects.link(dog)
for o in newo:
    if o.parent is None: o.parent=dog
dog.scale=(0.9,0.9,0.9)
# sun
bpy.ops.object.light_add(type='SUN',location=(28,-8,15)); sun=bpy.context.active_object
sun.data.energy=4.2; sun.data.angle=math.radians(1); sun.data.color=(1.0,0.96,0.9)
sun.rotation_euler=(math.radians(60),math.radians(6),math.radians(-46))
# camera chase
bpy.ops.object.camera_add(location=(0,-6,0.6)); cam=bpy.context.active_object; sc.camera=cam
cam.data.lens=32; cam.data.dof.use_dof=True; cam.data.dof.focus_object=dog; cam.data.dof.aperture_fstop=3.2
con=cam.constraints.new('TRACK_TO'); con.target=dog; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'
try: bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
except: pass
NF=192; sc.frame_start=1; sc.frame_end=NF; sc.render.fps=24
dog.location=(-0.7,7.0,0.2); dog.keyframe_insert('location',frame=1)
dog.location=(1.6,30.0,1.2); dog.keyframe_insert('location',frame=NF)
dog.rotation_euler=(math.radians(84),0,math.radians(160)); dog.keyframe_insert('rotation_euler',frame=1)
dog.rotation_euler=(math.radians(140),math.radians(50),math.radians(380)); dog.keyframe_insert('rotation_euler',frame=NF)
cam.location=(-0.7,0.4,0.8); cam.keyframe_insert('location',frame=1)
cam.location=(1.6,23.0,1.9); cam.keyframe_insert('location',frame=NF)
sc.render.filepath="/root/sat_seq/f_"
print("RENDER SAT"); bpy.ops.render.render(animation=True); print("DONE")
