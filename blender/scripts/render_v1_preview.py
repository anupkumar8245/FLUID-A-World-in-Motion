"""Render a 30-second review movie; the source scene retains its full-quality settings."""
import bpy,json,time,zlib,struct
from pathlib import Path
root=Path(__file__).resolve().parents[2] if Path(__file__).parent.name=='scripts' else Path(__file__).parent/'v1_staging'
scene=bpy.context.scene
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices: device.use=device.type=='OPTIX'
scene.cycles.device='GPU';scene.cycles.samples=16
scene.render.resolution_x=960;scene.render.resolution_y=540
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
dest=root/'renders/cinematics/preview_frames';dest.mkdir(parents=True,exist_ok=True)
start=time.perf_counter()
def complete_png(path):
    if not path.exists():return False
    data=path.read_bytes()
    if data[:8]!=b'\x89PNG\r\n\x1a\n':return False
    pos=8
    while pos+12<=len(data):
        length=struct.unpack('>I',data[pos:pos+4])[0]
        end=pos+8+length
        if end+4>len(data):return False
        if zlib.crc32(data[pos+4:end])!=struct.unpack('>I',data[end:end+4])[0]:return False
        if data[pos+4:pos+8]==b'IEND':return True
        pos=end+4
    return False
reused=0;rendered=0
for index,frame in enumerate(range(1,721,2)):
    path=dest/f'{index:04d}.png'
    if complete_png(path):
        reused+=1
        continue
    scene.frame_set(frame);scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    rendered+=1
    if index%12==0:print('FLUID_MOVIE_PROGRESS',index,360,flush=True)
(root/'docs/movie_metrics.json').write_text(json.dumps({'seconds_this_run':time.perf_counter()-start,'reused_frames':reused,'rendered_this_run':rendered,'resolution':[960,540],'samples':16,'fps':12,'frames':360,'duration_seconds':30,'note':'Review movie sampled from the 24fps source camera animation; timing excludes work before the power cut.'},indent=2))
print('FLUID_MOVIE_FRAMES_OK',flush=True)
