import bpy, os
d = "/root/blender_seq30"
files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
print("FILES", len(files))
sc = bpy.context.scene
sc.render.fps = 24
sc.frame_start = 1
sc.frame_end = len(files)
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080; sc.render.resolution_percentage = 100
se = sc.sequence_editor_create()
coll = se.strips
strip = coll.new_image(name="seq", filepath=os.path.join(d, files[0]), channel=1, frame_start=1)
for f in files[1:]:
    strip.elements.append(f)
sc.render.image_settings.file_format = 'FFMPEG'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.ffmpeg.gopsize = 18
sc.render.use_sequencer = True
sc.render.use_compositing = False
sc.render.filepath = "/root/eternal_fall_30s.mp4"
bpy.ops.render.render(animation=True)
print("ENCODED_DONE")
