import bpy, math, random
random.seed(3)
A="/root/eternal-fall/assets"
PREVIEW=True
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='GPU'
sc.cycles.samples=28 if PREVIEW else 110; sc.cycles.use_denoising=True
try: sc.cycles.denoiser='OPTIX'
except: pass
# MOTION BLUR (realism in fast motion)
sc.render.use_motion_blur=True
try: sc.render.motion_blur_shutter=0.55
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
# world (dim, star will light the dust)
w=bpy.data.worlds.new("W"); sc.world=w; w.use_nodes=True; nt=w.node_tree; nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment'); env.image=load(f"{A}/milkyway_8k.jpg")
bg=nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value=0.8
ow=nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(env.outputs['Color'],bg.inputs['Color']); nt.links.new(bg.outputs['Background'],ow.inputs['Surface'])
# DESTINATION: a bright star we fall toward (backlights everything)
bpy.ops.mesh.primitive_uv_sphere_add(radius=3.2,location=(2,66,5)); star=bpy.context.active_object; bpy.ops.object.shade_smooth()
sm=bpy.data.materials.new("star"); sm.use_nodes=True; sn=sm.node_tree; sn.nodes.clear()
se=sn.nodes.new('ShaderNodeEmission'); se.inputs['Color'].default_value=(1.0,0.85,0.6,1); se.inputs['Strength'].default_value=45
so=sn.nodes.new('ShaderNodeOutputMaterial'); sn.links.new(se.outputs['Emission'],so.inputs['Surface']); star.data.materials.append(sm)
bpy.ops.object.light_add(type='POINT',location=(2,66,5)); kl=bpy.context.active_object; kl.data.energy=60000; kl.data.color=(1.0,0.86,0.66); kl.data.shadow_soft_size=3
# JUPITER passing on the right
bpy.ops.mesh.primitive_uv_sphere_add(radius=12,segments=160,ring_count=80,location=(20,34,7)); jup=bpy.context.active_object; bpy.ops.object.shade_smooth()
jm=bpy.data.materials.new("J"); jm.use_nodes=True; jb=jm.node_tree.nodes['Principled BSDF']
jt=jm.node_tree.nodes.new('ShaderNodeTexImage'); jt.image=load(f"{A}/4k_jupiter.jpg")
jm.node_tree.links.new(jt.outputs['Color'],jb.inputs['Base Color']); jb.inputs['Roughness'].default_value=1.0
jup.data.materials.append(jm); jup.rotation_euler=(math.radians(8),0,math.radians(30))
# a MOON passing close on the left
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.2,segments=96,ring_count=48,location=(-6,17,-3)); moon=bpy.context.active_object; bpy.ops.object.shade_smooth()
mm=bpy.data.materials.new("M"); mm.use_nodes=True; mb=mm.node_tree.nodes['Principled BSDF']
mb.inputs['Base Color'].default_value=(0.4,0.38,0.36,1); mb.inputs['Roughness'].default_value=1.0
disp=mm.node_tree.nodes.new('ShaderNodeTexNoise'); disp.inputs['Scale'].default_value=8
moon.data.materials.append(mm)
# DEBRIS FIELD along the flight path (parallax + immersion), motion-blurred as they whip by
rmat=bpy.data.materials.new("rock"); rmat.use_nodes=True; rbb=rmat.node_tree.nodes['Principled BSDF']
rbb.inputs['Base Color'].default_value=(0.05,0.045,0.04,1); rbb.inputs['Roughness'].default_value=1.0
for i in range(44):
    yy=random.uniform(6,58)
    near=random.random()<0.4
    rad=random.uniform(0.12,0.5) if near else random.uniform(0.3,1.2)
    off=random.uniform(1.2,4.0) if near else random.uniform(4,12)
    ang=random.uniform(0,6.28)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=rad,location=(2+math.cos(ang)*off, yy, 4+math.sin(ang)*off))
    r=bpy.context.active_object; r.data.materials.append(rmat)
    r.scale=(random.uniform(0.7,1.5),random.uniform(0.7,1.5),random.uniform(0.7,1.5))
    r.rotation_euler=(random.uniform(0,3),random.uniform(0,3),random.uniform(0,3))
# CHARACTER (small, parented to camera, backlit silhouette)
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=f"{A}/characters/astrodog.glb")
newo=[o for o in bpy.data.objects if o not in before]
dog=bpy.data.objects.new("Dog",None); sc.collection.objects.link(dog)
for o in newo:
    if o.parent is None: o.parent=dog
dog.scale=(0.42,0.42,0.42)
# CAMERA falls forward toward the star; motion blur makes it filmic
bpy.ops.object.camera_add(location=(0,-3,1.2)); cam=bpy.context.active_object; sc.camera=cam
cam.data.lens=26; cam.data.dof.use_dof=True; cam.data.dof.aperture_fstop=3.6
tgt=bpy.data.objects.new("Aim",None); sc.collection.objects.link(tgt); tgt.location=(2,66,5)
con=cam.constraints.new('TRACK_TO'); con.target=tgt; con.track_axis='TRACK_NEGATIVE_Z'; con.up_axis='UP_Y'
cam.data.dof.focus_object=dog
try: bpy.context.preferences.edit.keyframe_new_interpolation_type='LINEAR'
except: pass
NF=144; sc.frame_start=1; sc.frame_end=NF; sc.render.fps=24
cam.location=(0,-3,1.2);  cam.keyframe_insert('location',frame=1)
cam.location=(2.0,40,4.0); cam.keyframe_insert('location',frame=NF)   # long forward fall
# dog flies just ahead of + below the aim → small, lower-third, backlit silhouette by the star
dog.location=(-0.4,3.0,0.0);  dog.keyframe_insert('location',frame=1)
dog.location=(1.5,45.0,2.6);  dog.keyframe_insert('location',frame=NF)
dog.rotation_euler=(math.radians(70),0,math.radians(120)); dog.keyframe_insert('rotation_euler',frame=1)
dog.rotation_euler=(math.radians(150),math.radians(70),math.radians(430)); dog.keyframe_insert('rotation_euler',frame=NF)
jup.rotation_euler=(math.radians(8),0,math.radians(30)); jup.keyframe_insert('rotation_euler',frame=1)
jup.rotation_euler=(math.radians(8),0,math.radians(34)); jup.keyframe_insert('rotation_euler',frame=NF)
sc.render.filepath="/root/imm_seq/f_"
print("RENDER IMMERSIVE"); bpy.ops.render.render(animation=True); print("DONE")
