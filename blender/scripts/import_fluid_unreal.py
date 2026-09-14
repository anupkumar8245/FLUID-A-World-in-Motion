"""Build V1 in a dedicated /Game/FluidWorld namespace. Run in the validation project first.
The published assets require only Unreal runtime classes, not Python or a custom plugin.
"""
import unreal as u,json,math,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2] if Path(__file__).parent.name=='scripts' else Path(__file__).parent/'v1_staging'
BASE='/Game/FluidWorld'
start=time.perf_counter()
manifest=json.loads((ROOT/'exports/unreal/scene_manifest.json').read_text())
materials=json.loads((ROOT/'docs/material_manifest.json').read_text())
assets=u.AssetToolsHelpers.get_asset_tools();lib=u.EditorAssetLibrary
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
meshsub=u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
subobjects=u.get_engine_subsystem(u.SubobjectDataSubsystem)
assert Path(u.Paths.get_project_file_path()).name=='FluidValidation.uproject','Build in the isolated validation project; migrate the reviewed folder afterwards.'

def import_file(path,dest,mesh=False):
    task=u.AssetImportTask();task.filename=str(path);task.destination_path=dest
    task.automated=True;task.replace_existing=True;task.save=True
    if mesh:
        opt=u.FbxImportUI();opt.import_mesh=True;opt.import_materials=False;opt.import_textures=False
        opt.automated_import_should_detect_type=False;opt.mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH
        opt.static_mesh_import_data.combine_meshes=True
        opt.static_mesh_import_data.convert_scene=True;opt.static_mesh_import_data.convert_scene_unit=True
        opt.static_mesh_import_data.auto_generate_collision=False
        task.options=opt
    assets.import_asset_tasks([task])
    result=u.load_asset(dest+'/'+path.stem)
    assert result,'Import failed: '+str(path)
    return result

textures={p.stem:import_file(p,BASE+'/Textures') for p in (ROOT/'blender/textures').glob('*.png')}
ml=u.MaterialEditingLibrary;mats={}
for name,spec in materials.items():
    path=BASE+'/Materials/'+name
    mat=u.load_asset(path) if lib.does_asset_exist(path) else assets.create_asset(name,BASE+'/Materials',u.Material,u.MaterialFactoryNew())
    ml.delete_all_material_expressions(mat);mat.set_editor_property('two_sided',True)
    mat.set_editor_property('used_with_instanced_static_meshes',True)
    def const(value,prop,y):
        iscolor=isinstance(value,list)
        node=ml.create_material_expression(mat,u.MaterialExpressionConstant3Vector if iscolor else u.MaterialExpressionConstant,-320,y)
        node.set_editor_property('constant' if iscolor else 'r',u.LinearColor(*value,1) if iscolor else value)
        ml.connect_material_property(node,'',prop)
    if spec['texture']:
        node=ml.create_material_expression(mat,u.MaterialExpressionTextureSample,-320,0)
        node.set_editor_property('texture',textures[spec['texture']]);ml.connect_material_property(node,'RGB',u.MaterialProperty.MP_BASE_COLOR)
    else:const(spec['color'],u.MaterialProperty.MP_BASE_COLOR,0)
    const(spec['roughness'],u.MaterialProperty.MP_ROUGHNESS,180)
    const(spec['metallic'],u.MaterialProperty.MP_METALLIC,300)
    if spec['emission']:const([c*spec['emission'] for c in spec['color']],u.MaterialProperty.MP_EMISSIVE_COLOR,420)
    ml.recompile_material(mat);lib.save_loaded_asset(mat);mats[name]=mat

meshes={}
for name,spec in manifest['assets'].items():
    obj=import_file(ROOT/'exports/unreal'/spec['file'],BASE+'/Meshes',True)
    for i,material in enumerate(spec['materials']):obj.set_material(i,mats[material])
    body=obj.get_editor_property('body_setup')
    if body:body.set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    lib.save_loaded_asset(obj);meshes[name]=obj
cal=meshes['SM_AxisCalibration'].get_bounds().origin
assert abs(cal.x-300)<.01 and abs(cal.y+500)<.01 and abs(cal.z-700)<.01, 'FBX basis/unit calibration failed'

def position(v):return u.Vector(v[0]*100,-v[1]*100,v[2]*100)
def rotation(q):
    w,x,y,z=q
    return u.Quat(-x,y,-z,w).rotator()
def transform(rec):return u.Transform(position(rec['location']),rotation(rec['quaternion_wxyz']),u.Vector(*rec['scale']))
def spawn(cls,name,loc=None,rot=None,folder='Environment'):
    actor=actors.spawn_actor_from_class(cls,loc or u.Vector(),rot or u.Rotator())
    assert actor,name
    actor.set_actor_label(name);actor.set_folder_path('FLUID/'+folder)
    return actor
MAP=BASE+'/Maps/L_AbyssalGarden'
if lib.does_asset_exist(MAP):
    assert level.load_level(MAP)
    for old in actors.get_all_level_actors():
        if str(old.get_folder_path()).startswith('FLUID'):actors.destroy_actor(old)
else:assert level.new_level(MAP),'New level failed'
groups={}
for rec in manifest['instances']:groups.setdefault(rec['asset'],[]).append(rec)
placement_counts={}
for name,records in groups.items():
    actor=spawn(u.Actor,'Instances_'+name)
    actor.root_component.set_mobility(u.ComponentMobility.STATIC)
    handles=subobjects.k2_gather_subobject_data_for_instance(actor)
    params=u.AddNewSubobjectParams(parent_handle=handles[0],new_class=u.InstancedStaticMeshComponent)
    handle,reason=subobjects.add_new_subobject(params)
    component=u.SubobjectDataBlueprintFunctionLibrary.get_associated_object(u.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    assert isinstance(component,u.InstancedStaticMeshComponent),str(reason)
    component.set_static_mesh(meshes[name]);component.set_mobility(u.ComponentMobility.STATIC)
    solid=name.startswith(('SM_Basalt','SM_Seafloor','SM_RelicArc'))
    component.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS if solid else u.CollisionEnabled.NO_COLLISION)
    if solid:component.set_collision_profile_name('BlockAll')
    for rec in records:component.add_instance(transform(rec),world_space=True)
    placement_counts[name]=component.get_instance_count()
    assert placement_counts[name]==len(records)
    print('FLUID_PLACED',name,len(records),flush=True)

# Directions of Blender cameras and area/spot lights use -Z forward and Y up.
def view_rotation(q):
    w,x,y,z=q
    forward=[-2*(x*z+w*y),-2*(y*z-w*x),-(1-2*(x*x+y*y))]
    up=[2*(x*y-w*z),1-2*(x*x+z*z),2*(y*z+w*x)]
    return u.MathLibrary.make_rot_from_xz(u.Vector(forward[0],-forward[1],forward[2]),u.Vector(up[0],-up[1],up[2]))
for rec in manifest['lights']:
    cls={'AREA':u.RectLight,'POINT':u.PointLight,'SPOT':u.SpotLight}[rec['type']]
    actor=spawn(cls,rec['name'],position(rec['location']),view_rotation(rec['quaternion_wxyz']),'Lighting')
    light=actor.get_component_by_class(u.LightComponent)
    light.set_mobility(u.ComponentMobility.MOVABLE)
    light.set_light_color(u.LinearColor(*rec['color'],1))
    light.set_editor_property('intensity_units',u.LightUnits.LUMENS)
    light.set_intensity(rec['energy'])
    light.set_editor_property('attenuation_radius',16000)
    if rec['type']=='AREA':
        light.set_editor_property('source_width',rec['size']*100)
        light.set_editor_property('source_height',rec['size']*100)
    elif rec['type']=='POINT':light.set_editor_property('source_radius',rec['size']*30)
    else:
        light.set_editor_property('inner_cone_angle',5)
        light.set_editor_property('outer_cone_angle',9)
    light.set_editor_property('volumetric_scattering_intensity',.65)
fog=spawn(u.ExponentialHeightFog,'Atmosphere_Underwater',folder='Atmosphere')
fc=fog.get_component_by_class(u.ExponentialHeightFogComponent)
fc.set_editor_property('fog_density',.018)
fc.set_editor_property('fog_height_falloff',.001)
fc.set_editor_property('fog_inscattering_luminance',u.LinearColor(.005,.035,.045,1))
fc.set_volumetric_fog(True)
fc.set_editor_property('volumetric_fog_scattering_distribution',.35)
fc.set_editor_property('volumetric_fog_albedo',u.Color(95,180,185,255))
fc.set_editor_property('volumetric_fog_emissive',u.LinearColor(.02,.10,.13,1))
fc.set_volumetric_fog_distance(22000)
fill=spawn(u.PointLight,'L_WaterAmbientFill',u.Vector(0,0,1500),folder='Lighting').get_component_by_class(u.PointLightComponent)
fill.set_mobility(u.ComponentMobility.MOVABLE);fill.set_editor_property('intensity_units',u.LightUnits.LUMENS)
fill.set_intensity(8000);fill.set_light_color(u.LinearColor(.08,.4,.5,1))
fill.set_editor_property('attenuation_radius',16000);fill.set_editor_property('cast_shadows',False)
post=spawn(u.PostProcessVolume,'PP_Underwater',folder='Atmosphere')
post.set_editor_property('unbound',True)
settings=post.get_editor_property('settings')
for name,value in {'override_auto_exposure_method':True,'auto_exposure_method':u.AutoExposureMethod.AEM_MANUAL,'override_auto_exposure_bias':True,'auto_exposure_bias':-1.0,'override_auto_exposure_apply_physical_camera_exposure':True,'auto_exposure_apply_physical_camera_exposure':False,'override_bloom_intensity':True,'bloom_intensity':.35}.items():settings.set_editor_property(name,value)
post.set_editor_property('settings',settings)

# Native DefaultPawn provides mouse-look and flying controls without simulation code.
spawn(u.PlayerStart,'PlayerStart_Descent',position([-3,-30,8]),view_rotation(manifest['camera_samples'][0]['quaternion_wxyz']),'Navigation')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
world.get_world_settings().set_editor_property('default_game_mode',u.GameModeBase)
cam=spawn(u.CineCameraActor,'CAM_Descent',position(manifest['camera_samples'][0]['position']),view_rotation(manifest['camera_samples'][0]['quaternion_wxyz']),'Cameras')
cc=cam.get_cine_camera_component()
film=cc.get_editor_property('filmback');film.sensor_width=36;film.sensor_height=20.25;cc.set_editor_property('filmback',film)
cc.set_editor_property('current_focal_length',27)
focus=cc.get_editor_property('focus_settings');focus.focus_method=u.CameraFocusMethod.DISABLE;cc.set_editor_property('focus_settings',focus)
sequence_path=BASE+'/Cinematics/LS_V1_Descent'
if lib.does_asset_exist(sequence_path):
    seq=u.load_asset(sequence_path)
    for binding in seq.get_bindings():binding.remove()
    for track in seq.get_tracks():seq.remove_track(track)
else:seq=assets.create_asset('LS_V1_Descent',BASE+'/Cinematics',u.LevelSequence,u.LevelSequenceFactoryNew())
seq.set_display_rate(u.FrameRate(24,1));seq.set_playback_start(0);seq.set_playback_end(720)
binding=seq.add_possessable(cam)
section=binding.add_track(u.MovieScene3DTransformTrack).add_section();section.set_range(0,720)
channels=section.get_all_channels()
for sample in manifest['camera_samples']:
    pos=position(sample['position']);rot=view_rotation(sample['quaternion_wxyz'])
    values=[pos.x,pos.y,pos.z,rot.roll,rot.pitch,rot.yaw,1,1,1]
    for channel,value in zip(channels,values):channel.add_key(u.FrameNumber(sample['frame']),value,interpolation=u.MovieSceneKeyInterpolation.LINEAR)
cut=seq.add_track(u.MovieSceneCameraCutTrack).add_section();cut.set_range(0,720)
bid=u.MovieSceneObjectBindingID();bid.set_editor_property('guid',binding.get_id());cut.set_camera_binding_id(bid)
sa=spawn(u.LevelSequenceActor,'Cinematic_Descent',folder='Cameras');sa.set_sequence(seq)
lib.save_loaded_asset(seq)
level.set_level_viewport_camera_info(cam.get_actor_location(),cam.get_actor_rotation(),'None')
assert level.save_current_level()
report={'engine':u.SystemLibrary.get_engine_version(),'build_seconds':time.perf_counter()-start,'map':MAP,'sequence':sequence_path,'unique_meshes':len(meshes),'placements':sum(placement_counts.values()),'instance_groups':placement_counts,'calibration_cm':[cal.x,cal.y,cal.z],'collision':'Complex-as-simple on terrain, basalt and relic arcs; decorative flora has no collision.','navigation':'Native GameModeBase + DefaultPawn. Gameplay test pending.','visual_validation':'Pending Unreal rendered screenshot; Blender and Unreal shading are separate.'}
(ROOT/'docs/unreal_build.json').write_text(json.dumps(report,indent=2))
print('FLUID_UNREAL_BUILD_OK',report['placements'],flush=True)
