# scene_craft2.py — LOTTO 2 mezzi 3D alta qualità (Cycles/OptiX): navetta, Soyuz, lander, sonda, capsula, stazione, detriti.
# Più dettaglio GEOMETRICO (greeble) = alta qualità che sopravvive all'export GLB (le texture procedurali no).
# Orientamento: "avanti/su" = +Z in Blender → +Y in three (export_yup). Output: lineup2.png + un GLB per mezzo.
import bpy, math, os
A = os.environ.get('EF_ASSETS', "/root/eternal-fall/assets")   # VM: /root/...; Mac: passa EF_ASSETS=<repo>/assets
OUT = os.environ.get('EF_OUT', "/root/craft_out")
PREVIEW = False
RES = int(os.environ.get('EF_RES', '2600' if not PREVIEW else '1600'))
SAMP = int(os.environ.get('EF_SAMP', '170' if not PREVIEW else '48'))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.samples=SAMP; sc.cycles.use_denoising=True
# device CROSS-PLATFORM: OptiX (VM NVIDIA) / METAL (Mac Apple Silicon) / CUDA / CPU
pf=bpy.context.preferences.addons['cycles'].preferences; _best=None
for _dt in ('OPTIX','METAL','CUDA','HIP','ONEAPI'):
    try:
        pf.compute_device_type=_dt; pf.refresh_devices()
        if any(d.type==_dt for d in pf.devices): _best=_dt; break
    except Exception: pass
if _best:
    for d in pf.devices: d.use=(d.type==_best)
    sc.cycles.device='GPU'
    try: sc.cycles.denoiser=('OPTIX' if _best=='OPTIX' else 'OPENIMAGEDENOISE')
    except Exception: pass
else:
    sc.cycles.device='CPU'
    try: sc.cycles.denoiser='OPENIMAGEDENOISE'
    except Exception: pass
print("CYCLES device:", _best or 'CPU')
sc.render.resolution_x=RES; sc.render.resolution_y=int(RES*0.30)
sc.render.film_transparent=True; sc.render.image_settings.file_format='PNG'; sc.render.image_settings.color_mode='RGBA'
try: sc.view_settings.view_transform='AgX'; sc.view_settings.look='AgX - Medium High Contrast'
except Exception: pass

def load(p):
    img=bpy.data.images.load(p)
    try: img.colorspace_settings.name='sRGB'
    except Exception: pass
    return img
w=bpy.data.worlds.new("W"); sc.world=w; w.use_nodes=True; nt=w.node_tree; nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment'); env.image=load(f"{A}/milkyway_8k.jpg")
bg=nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value=0.5   # più luce → metalli più leggibili
wo=nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(env.outputs['Color'],bg.inputs['Color']); nt.links.new(bg.outputs['Background'],wo.inputs['Surface'])
bpy.ops.object.light_add(type='SUN', location=(10,-8,12)); s=bpy.context.active_object
s.data.energy=5.0; s.data.angle=math.radians(1.0); s.data.color=(1.0,0.96,0.9); s.rotation_euler=(math.radians(58),math.radians(10),math.radians(-40))
bpy.ops.object.light_add(type='SUN', location=(-12,-6,4)); f=bpy.context.active_object
f.data.energy=0.9; f.data.color=(0.5,0.62,0.95); f.rotation_euler=(math.radians(70),0,math.radians(130))

def mat(name,base,rough,metal,emis=None,emis_s=0.0):
    m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*base,1); b.inputs['Roughness'].default_value=rough; b.inputs['Metallic'].default_value=metal
    if emis is not None:
        try: b.inputs['Emission Color'].default_value=(*emis,1); b.inputs['Emission Strength'].default_value=emis_s
        except Exception:
            try: b.inputs['Emission'].default_value=(*emis,1); b.inputs['Emission Strength'].default_value=emis_s
            except Exception: pass
    return m
M={'white':mat('white',(0.90,0.90,0.92),0.4,0.15),'black':mat('black',(0.05,0.05,0.06),0.5,0.3),
   'tile':mat('tile',(0.14,0.14,0.16),0.7,0.1),  # piastrelle termiche navetta
   'steel':mat('steel',(0.86,0.88,0.92),0.16,1.0),'engine':mat('engine',(0.10,0.09,0.09),0.5,0.85),
   'gold':mat('gold',(1.0,0.72,0.26),0.32,1.0),'foil':mat('foil',(0.95,0.80,0.42),0.45,0.9),
   'solar':mat('solar',(0.03,0.05,0.17),0.18,0.4,emis=(0.02,0.05,0.17),emis_s=0.3),
   'tank':mat('tank',(0.72,0.42,0.20),0.6,0.1),  # serbatoio esterno arancio
   'nozzle':mat('nozzle',(0.12,0.11,0.10),0.35,0.9),'glow':mat('glow',(1.0,0.6,0.25),0.5,0.0,emis=(1.0,0.55,0.22),emis_s=14.0),
   'red':mat('red',(0.75,0.10,0.09),0.4,0.3,emis=(0.9,0.05,0.03),emis_s=3.0),'green':mat('green',(0.10,0.8,0.2),0.4,0.2,emis=(0.05,0.9,0.15),emis_s=3.0),
   'dish':mat('dish',(0.92,0.92,0.94),0.35,0.2)}

_objs=[]
def add(prim,name,craft,matn,loc=(0,0,0),rot=(0,0,0),scale=(1,1,1),**kw):
    if prim=='cyl': bpy.ops.mesh.primitive_cylinder_add(vertices=kw.get('v',28),radius=kw.get('r',1),depth=kw.get('d',1),location=loc)
    elif prim=='cone': bpy.ops.mesh.primitive_cone_add(vertices=kw.get('v',28),radius1=kw.get('r1',1),radius2=kw.get('r2',0),depth=kw.get('d',1),location=loc)
    elif prim=='box': bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    elif prim=='sph': bpy.ops.mesh.primitive_uv_sphere_add(segments=kw.get('v',20),ring_count=kw.get('rc',10),radius=kw.get('r',1),location=loc)
    o=bpy.context.active_object; o.name=name
    if prim in ('cyl','cone','sph'): bpy.ops.object.shade_smooth()
    o.rotation_euler=tuple(math.radians(a) for a in rot); o.scale=scale; o.data.materials.append(M[matn]); _objs.append((craft,o)); return o

# ---- helper: bande/anelli greeble su un cilindro (dettaglio alta qualità) ----
def rings(c,mn,cx,z0,z1,r,n,rr=1.02,dd=0.05):
    for k in range(n):
        z=z0+(z1-z0)*(k+0.5)/n; add('cyl',c+'_r%d'%k,c,mn,loc=(cx,0,z),r=r*rr,d=dd,v=28)

# ============ NAVETTA + SERBATOIO + BOOSTER (shuttle stack) ============
def shuttle(cx):
    c='shuttle'
    add('cyl',c+'_tank',c,'tank',loc=(cx,0,0.0),r=0.55,d=3.4,v=32)                 # serbatoio esterno arancio
    add('cone',c+'_tanknose',c,'tank',loc=(cx,0,1.9),r1=0.55,r2=0.12,d=0.7,v=32)
    for sgn in (-1,1):                                                             # 2 SRB bianchi
        add('cyl',c+'_srb%d'%sgn,c,'white',loc=(cx+sgn*0.78,0,-0.2),r=0.26,d=3.2,v=24)
        add('cone',c+'_srbn%d'%sgn,c,'white',loc=(cx+sgn*0.78,0,1.55),r1=0.26,r2=0.0,d=0.5,v=24)
        add('cone',c+'_srbnz%d'%sgn,c,'nozzle',loc=(cx+sgn*0.78,0,-1.95),r1=0.18,r2=0.12,d=0.3,v=18)
    # orbiter sul fianco del serbatoio (naso in su)
    ox=cx-0.72
    add('cyl',c+'_fus',c,'tile',loc=(ox,0,0.3),r=0.26,d=2.4,rot=(0,0,0),v=24)      # fusoliera
    add('cone',c+'_fusn',c,'white',loc=(ox,0,1.65),r1=0.26,r2=0.06,d=0.7,v=24)     # muso
    for sgn in (-1,1):                                                             # ali a delta (box tozzo inclinato)
        add('box',c+'_wing%d'%sgn,c,'white',loc=(ox+sgn*0.02,sgn*0.5,-0.35),rot=(0,0,sgn*8),scale=(0.55,0.9,0.06))
    add('box',c+'_tail',c,'white',loc=(ox,0,-0.7),rot=(0,0,0),scale=(0.05,0.28,0.5))  # deriva verticale
    add('cone',c+'_me',c,'nozzle',loc=(ox,0,-1.0),r1=0.16,r2=0.11,d=0.28,v=18)     # motore principale
    add('cone',c+'_flame',c,'glow',loc=(cx,0,-2.3),r1=0.5,r2=0.05,d=1.3,v=24)

# ============ SOYUZ (core + 4 booster tapered) ============
def soyuz(cx):
    c='soyuz'
    add('cyl',c+'_core',c,'white',loc=(cx,0,0.2),r=0.24,d=2.6,v=28); rings(c,'black',cx,-0.9,1.4,0.24,3)
    add('cone',c+'_shroud',c,'white',loc=(cx,0,1.85),r1=0.24,r2=0.08,d=1.0,v=28)
    add('cyl',c+'_esc',c,'red',loc=(cx,0,2.5),r=0.03,d=0.5,v=8)                    # torre di salvataggio
    for k in range(4):                                                            # 4 booster conici (la "stella" Soyuz)
        a=k/4*6.2832
        add('cone',c+'_b%d'%k,c,'white',loc=(cx+math.cos(a)*0.34,math.sin(a)*0.34,-0.55),r1=0.20,r2=0.10,d=1.9,v=22)
        add('cone',c+'_bn%d'%k,c,'green',loc=(cx+math.cos(a)*0.34,math.sin(a)*0.34,0.5),r1=0.10,r2=0.0,d=0.5,v=18,emis_s=0)
        add('cone',c+'_bnz%d'%k,c,'nozzle',loc=(cx+math.cos(a)*0.34,math.sin(a)*0.34,-1.6),r1=0.11,r2=0.08,d=0.2,v=16)
    add('cone',c+'_flame',c,'glow',loc=(cx,0,-2.0),r1=0.45,r2=0.05,d=1.2,v=24)

# ============ LANDER lunare (LEM) ============
def lander(cx):
    c='lander'
    add('cyl',c+'_desc',c,'gold',loc=(cx,0,-0.3),r=0.55,d=0.55,v=8)               # stadio discesa ottagonale (foil oro)
    for k in range(4):                                                            # 4 zampe
        a=k/4*6.2832+0.785
        add('cyl',c+'_leg%d'%k,c,'steel',loc=(cx+math.cos(a)*0.55,math.sin(a)*0.55,-0.7),rot=(math.degrees(a)*0+30,0,math.degrees(a)),r=0.02,d=0.7,v=6)
        add('cyl',c+'_pad%d'%k,c,'steel',loc=(cx+math.cos(a)*0.8,math.sin(a)*0.8,-1.0),r=0.09,d=0.04,v=10)
    add('cyl',c+'_asc',c,'foil',loc=(cx,0,0.15),r=0.34,d=0.42,v=10)               # stadio risalita
    add('sph',c+'_dome',c,'white',loc=(cx,0,0.42),r=0.32,v=18)
    add('cyl',c+'_win',c,'black',loc=(cx,0.30,0.35),r=0.08,d=0.06,rot=(90,0,0),v=8)
    add('cyl',c+'_ant',c,'steel',loc=(cx,0,0.9),r=0.008,d=0.5,v=6)
    add('cone',c+'_dish',c,'dish',loc=(cx+0.25,0,0.6),r1=0.14,r2=0.02,d=0.08,rot=(40,0,0),v=20)

# ============ SONDA interplanetaria (Voyager-like) ============
def probe(cx):
    c='probe'
    add('cyl',c+'_bus',c,'gold',loc=(cx,0,0),r=0.3,d=0.28,v=10)                   # bus decagonale
    add('cone',c+'_dish',c,'dish',loc=(cx,0,0.45),r1=0.62,r2=0.05,d=0.32,v=40)    # grande parabola
    add('cyl',c+'_feed',c,'steel',loc=(cx,0,0.72),r=0.02,d=0.35,v=6)
    add('box',c+'_boom',c,'engine',loc=(cx+0.9,0,-0.1),scale=(1.4,0.04,0.04))     # braccio strumenti
    add('cyl',c+'_rtg0',c,'engine',loc=(cx+1.6,0,-0.1),r=0.07,d=0.5,rot=(0,90,0),v=10)  # RTG
    add('cyl',c+'_rtg1',c,'engine',loc=(cx+1.85,0,-0.1),r=0.07,d=0.5,rot=(0,90,0),v=10)
    add('box',c+'_mag',c,'steel',loc=(cx-1.1,0,0.1),scale=(1.8,0.02,0.02))        # magnetometro lungo
    add('sph',c+'_inst',c,'white',loc=(cx+0.6,0.2,-0.1),r=0.06,v=12)

# ============ CAPSULA equipaggio (Dragon/Orion) ============
def capsule(cx):
    c='capsule'
    add('cone',c+'_cap',c,'white',loc=(cx,0,0.35),r1=0.5,r2=0.28,d=0.7,v=28)      # cono tronco
    add('cyl',c+'_dock',c,'steel',loc=(cx,0,0.78),r=0.12,d=0.14,v=18)            # portello
    add('cyl',c+'_shield',c,'tile',loc=(cx,0,-0.05),r=0.52,d=0.08,v=28)          # scudo termico
    add('cyl',c+'_trunk',c,'white',loc=(cx,0,-0.55),r=0.5,d=0.85,v=28); rings(c,'black',cx,-0.9,-0.2,0.5,2)
    for k in range(3):                                                           # pannelli solari a fascia sul trunk
        a=k/3*6.2832
        add('box',c+'_sp%d'%k,c,'solar',loc=(cx+math.cos(a)*0.53,math.sin(a)*0.53,-0.55),rot=(0,0,math.degrees(a)),scale=(0.04,0.5,0.7))
    for k in range(4):                                                           # thruster
        a=k/4*6.2832
        add('cone',c+'_th%d'%k,c,'nozzle',loc=(cx+math.cos(a)*0.42,math.sin(a)*0.42,0.15),r1=0.04,r2=0.02,d=0.08,v=8)

# ============ STAZIONE spaziale modulare (rotante lenta) ============
def station(cx):
    c='station'
    add('cyl',c+'_m1',c,'white',loc=(cx,0,0),r=0.3,d=1.6,rot=(0,90,0),v=24);
    add('cyl',c+'_m2',c,'white',loc=(cx,0,0.6),r=0.26,d=1.0,rot=(90,0,0),v=24)    # modulo perpendicolare
    add('cyl',c+'_node',c,'foil',loc=(cx,0,0),r=0.33,d=0.35,v=18)
    add('box',c+'_truss',c,'steel',loc=(cx,0,0),scale=(3.2,0.05,0.05))           # trave centrale
    for sgn in (-1,1):
        for j in (0,1):                                                          # 4 grandi array solari
            add('box',c+'_sa%d_%d'%(sgn,j),c,'solar',loc=(cx+sgn*1.4,0,(j*2-1)*0.5),scale=(1.1,0.02,0.8))
            add('cyl',c+'_sb%d_%d'%(sgn,j),c,'steel',loc=(cx+sgn*0.8,0,(j*2-1)*0.25),r=0.02,d=0.6,rot=(0,90,0),v=6)
    add('box',c+'_rad',c,'white',loc=(cx,0,-0.9),scale=(1.6,0.02,0.4))           # radiatore
    add('cyl',c+'_dock',c,'black',loc=(cx-1.7,0,0),r=0.1,d=0.15,rot=(0,90,0),v=12)

# ============ DETRITO / relitto (drammatico) ============
def debris(cx):
    c='debris'
    add('box',c+'_hull',c,'foil',loc=(cx,0,0),rot=(20,35,10),scale=(0.5,0.4,0.9))
    add('box',c+'_break',c,'engine',loc=(cx+0.3,0.2,0.4),rot=(50,10,30),scale=(0.3,0.25,0.3))
    add('box',c+'_panel',c,'solar',loc=(cx-0.6,0,-0.2),rot=(70,20,15),scale=(1.1,0.02,0.5))
    add('box',c+'_panel2',c,'solar',loc=(cx+0.7,-0.3,-0.3),rot=(30,60,40),scale=(0.7,0.02,0.4))
    add('cyl',c+'_pipe',c,'steel',loc=(cx-0.2,0.3,0.2),r=0.03,d=0.9,rot=(40,30,0),v=8)
    add('cyl',c+'_pipe2',c,'steel',loc=(cx+0.1,-0.2,-0.1),r=0.025,d=0.7,rot=(80,10,50),v=8)

CRAFT=[('shuttle',shuttle,-15.0),('soyuz',soyuz,-10.5),('lander',lander,-6.5),('probe',probe,-2.0),
       ('capsule',capsule,2.5),('station',station,7.5),('debris',debris,13.0)]
for name,fn,cx in CRAFT: fn(cx)

# camera contact sheet
bpy.ops.object.camera_add(location=(-1.5,-24,0)); cam=bpy.context.active_object; sc.camera=cam
cam.data.type='ORTHO'; cam.data.ortho_scale=34.0
from mathutils import Vector
cam.rotation_euler=(Vector((-1.5,0,0.3))-Vector((-1.5,-24,0))).to_track_quat('-Z','Z').to_euler()
os.makedirs(OUT,exist_ok=True)
sc.render.filepath=os.path.join(OUT,"lineup2.png")
print("RENDER LINEUP2",RES); bpy.ops.render.render(write_still=True); print("DONE lineup2")

# export GLB per mezzo
for name,fn,cx in CRAFT:
    objs=[o for (cn,o) in _objs if cn==name]
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.empty_add(location=(cx,0,0)); root=bpy.context.active_object; root.name=name+'_root'
    for o in objs: o.select_set(True)
    root.select_set(True); bpy.context.view_layer.objects.active=root
    bpy.ops.object.parent_set(type='OBJECT',keep_transform=True)
    root.location=(0,0,0)
    bpy.ops.object.select_all(action='DESELECT'); root.select_set(True)
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,name+".glb"),use_selection=True,export_format='GLB',export_yup=True,export_apply=True)
    print("EXPORT",name)
print("ALL CRAFT2 DONE")
