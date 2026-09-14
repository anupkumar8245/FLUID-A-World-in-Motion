import bpy,json,time,math,sys,argparse
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--previews',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root)
scene=bpy.context.scene
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
scene.cycles.device='GPU'
manifest={'version':1,'units':'meters','coordinate_basis':'Blender Z-up right-handed','assets':{},'instances':[],'camera_samples':[],'lights':[]}
sources={o.data.name:o.name for o in bpy.data.objects if o.type=='MESH' and any(c.name.startswith('SRC_') for c in o.users_collection)}
data={}
def record(obj,matrix,name):
    key=obj.data.name;asset=sources.get(key,key)
    data[asset]=obj.data
    manifest['assets'][asset]={'file':asset+'.fbx','materials':[m.name if m else '' for m in obj.data.materials],'vertices':len(obj.data.vertices),'polygons':len(obj.data.polygons)}
    loc,rot,scale=matrix.decompose()
    manifest['instances'].append({'asset':asset,'name':name,'location':list(loc),'quaternion_wxyz':list(rot),'scale':list(scale)})
for o in bpy.data.collections['01_ENVIRONMENT'].objects:
    if o.type=='MESH':record(o,o.matrix_world,o.name)
dg=bpy.context.evaluated_depsgraph_get();groups={'CoralHabitat','RibbonHabitat','TrumpetHabitat','SeaFanHabitat','SuspendedParticulates'}
counts={k:0 for k in groups}
for inst in dg.object_instances:
    if inst.is_instance and inst.parent and inst.parent.original.name in groups and inst.object.type=='MESH':
        par=inst.parent.original.name;counts[par]+=1
        record(inst.object.original,inst.matrix_world.copy(),par+'_'+str(counts[par]))
print('GN_INSTANCE_COUNTS',counts,flush=True)
for frame in range(1,721,12):
    scene.frame_set(frame);cam=scene.camera
    manifest['camera_samples'].append({'frame':frame-1,'position':list(cam.location),'quaternion_wxyz':list(cam.rotation_euler.to_quaternion())})
scene.frame_set(720);manifest['camera_samples'].append({'frame':719,'position':list(scene.camera.location),'quaternion_wxyz':list(scene.camera.rotation_euler.to_quaternion())})
for o in bpy.data.collections['03_LIGHTING'].objects:
    manifest['lights'].append({'name':o.name,'type':o.data.type,'location':list(o.location),'quaternion_wxyz':list(o.rotation_euler.to_quaternion()),'color':list(o.data.color),'energy':o.data.energy,'size':getattr(o.data,'size',getattr(o.data,'shadow_soft_size',1))})

# Geometry-based clearance check along camera route (rendering/atmospheric geometry excluded).
trees=[]
for o in bpy.data.collections['01_ENVIRONMENT'].objects:
    if o.type=='MESH' and (o.name.startswith(('Cliff','Talus','ReefRock','RelicArc')) or o.name=='SM_Seafloor'):
        verts=[o.matrix_world@v.co for v in o.data.vertices]; polys=[list(f.vertices) for f in o.data.polygons]
        trees.append((o.name,BVHTree.FromPolygons(verts,polys)))
checks=[]
for frame in range(1,721,12):
    scene.frame_set(frame);pos=scene.camera.location.copy();near=[]
    for name,tree in trees:
        hit=tree.find_nearest(pos,1.0)
        if hit and hit[0] is not None:near.append({'object':name,'distance':hit[3]})
    checks.append({'frame':frame,'clearance_1m':not near,'near':near})
navchecks=[]
for y in range(-28,49,2):
    pos=Vector((0,y,3));near=[]
    for name,tree in trees:
        hit=tree.find_nearest(pos,.5)
        if hit and hit[0] is not None:near.append(name)
    navchecks.append({'position':list(pos),'clearance_0_5m':not near,'near':near})
(root/'docs/navigation_checks.json').write_text(json.dumps({'camera_route':checks,'central_navigation_route':navchecks,'scope':'Nearest-surface samples only; not a complete swept-volume or Unreal gameplay test.'},indent=2))

if a.previews:
    timings=[]
    for frame,name in [(360,'V1_Garden'),(650,'V1_Threshold')]:
        scene.frame_set(frame);scene.render.filepath=str(root/'renders/previews'/f'{name}.png');t=time.perf_counter();bpy.ops.render.render(write_still=True);timings.append({'frame':frame,'seconds':time.perf_counter()-t})
    scene.frame_set(1);cam=scene.camera
    old=cam.location.copy();oldrot=cam.rotation_euler.copy()
    cam.location=(0,-6,3);cam.rotation_euler=(Vector((0,52,13))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(root/'renders/previews/V1_Navigation.png');t=time.perf_counter();bpy.ops.render.render(write_still=True);timings.append({'view':'navigation','seconds':time.perf_counter()-t})
    cam.location=old;cam.rotation_euler=oldrot
    (root/'docs/view_metrics.json').write_text(json.dumps(timings,indent=2))

# A deliberately asymmetric marker lets the Unreal importer verify its axis/unit conversion.
vs=[(3+sx*.1,5+sy*.2,7+sz*.3) for sx,sy,sz in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
me=bpy.data.meshes.new('SM_AxisCalibration');me.from_pydata(vs,[],[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]);data[me.name]=me
manifest['assets'][me.name]={'file':me.name+'.fbx','materials':[],'vertices':8,'polygons':6}
temp=bpy.data.collections.new('TEMP_EXPORT');scene.collection.children.link(temp)
for name,me in data.items():
    o=bpy.data.objects.new(name,me);temp.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    bpy.ops.export_scene.fbx(filepath=str(root/'exports/unreal'/f'{name}.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,global_scale=1,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',use_mesh_modifiers=True,mesh_smooth_type='FACE',use_custom_props=False,bake_anim=False,path_mode='STRIP')
    bpy.data.objects.remove(o,do_unlink=True)
bpy.data.collections.remove(temp)
(root/'exports/unreal/scene_manifest.json').write_text(json.dumps(manifest,indent=2))
print('FLUID_EXPORT_OK',len(data),'assets',len(manifest['instances']),'instances',flush=True)
