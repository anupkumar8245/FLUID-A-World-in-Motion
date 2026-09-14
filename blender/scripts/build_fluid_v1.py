"""FLUID V1. Deterministic Blender 5.1 environment builder; no fluid simulation.
Run: blender -b --factory-startup -P build_fluid_v1.py -- --root OUTPUT
"""
import bpy, math, random, json, time, argparse, sys
from pathlib import Path
from mathutils import Vector, noise
import numpy as np

args = argparse.ArgumentParser()
args.add_argument('--root', required=True)
args.add_argument('--render', action='store_true')
opts = args.parse_args(sys.argv[sys.argv.index('--')+1:])
ROOT = Path(opts.root)
for d in ['blender/scenes','blender/assets','blender/textures','blender/scripts','exports/unreal','exports/webgpu','renders/previews','renders/cinematics','docs']:
    (ROOT/d).mkdir(parents=True, exist_ok=True)
random.seed(1209)
started=time.perf_counter()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.name='FLUID | The Abyssal Garden'
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
scene.render.engine='CYCLES'
scene.cycles.samples=64
scene.cycles.use_denoising=True
scene.cycles.max_bounces=7; scene.cycles.volume_bounces=1
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use=d.type=='OPTIX'
    scene.cycles.device='GPU'
except Exception: scene.cycles.device='CPU'
scene.render.resolution_x=1440; scene.render.resolution_y=810
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.fps=24; scene.frame_start=1; scene.frame_end=720
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=-0.2
scene.world=bpy.data.worlds.new('WORLD_DeepWater')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.018,0.07,0.11,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.08

def coll(name,parent=None):
    c=bpy.data.collections.new(name); (parent or scene.collection).children.link(c); return c
C={k:coll(k) for k in ['01_ENVIRONMENT','02_PROCEDURAL_SYSTEMS','03_LIGHTING','04_ATMOSPHERE','05_CAMERAS','06_EXPORT_PROXIES','90_ASSET_SOURCES']}
geology=coll('SRC_Geology',C['90_ASSET_SOURCES']); flora=coll('SRC_Vegetation',C['90_ASSET_SOURCES']); landmark=coll('SRC_Landmark',C['90_ASSET_SOURCES'])
C['90_ASSET_SOURCES'].hide_render=True
C['06_EXPORT_PROXIES'].hide_render=True

def link(obj,c):
    for old in list(obj.users_collection): old.objects.unlink(obj)
    c.objects.link(obj)
    return obj

def texmap(name,base):
    n=512; yy,xx=np.mgrid[0:n,0:n].astype(np.float32)/n
    h=np.zeros((n,n),dtype=np.float32)
    rng=random.Random(55)
    for freq,amp in [(2,.30),(5,.18),(11,.12),(23,.08),(47,.035),(101,.016)]:
        for j in range(3):
            a=rng.randint(1,freq); b=freq-a
            h+=amp*np.sin(2*np.pi*(a*xx+b*yy)+rng.uniform(0,6.28))/3
    h=np.clip(.52+h,0,1)
    rgb=np.stack([np.clip(v*(.62+h*.72),0,1) for v in base],axis=-1)
    rgba=np.concatenate([rgb,np.ones((n,n,1),np.float32)],axis=-1)
    im=bpy.data.images.new(name,width=n,height=n)
    im.pixels.foreach_set(rgba.ravel()); im.filepath_raw=str(ROOT/'blender/textures'/f'{name}.png'); im.file_format='PNG'; im.save()
    return im
stone_tex=texmap('T_Basalt_BaseColor',(0.17,0.23,0.25))
sand_tex=texmap('T_Sediment_BaseColor',(0.20,0.27,0.27))

materials={}
def mat(name,color,rough=.6,emit=0,texture=None,metal=.0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    nt=m.node_tree; p=nt.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough; p.inputs['Metallic'].default_value=metal
    if emit:
        p.inputs['Emission Color'].default_value=(*color,1); p.inputs['Emission Strength'].default_value=emit
    if texture:
        t=nt.nodes.new('ShaderNodeTexImage'); t.image=texture
        nt.links.new(t.outputs['Color'],p.inputs['Base Color'])
    if not emit:
        t=nt.nodes.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value=65; t.inputs['Detail'].default_value=5
        b=nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.65; b.inputs['Distance'].default_value=.085
        nt.links.new(t.outputs['Fac'],b.inputs['Height']); nt.links.new(b.outputs['Normal'],p.inputs['Normal'])
    materials[name]={'color':color,'roughness':rough,'emission':emit,'metallic':metal,'texture':texture.name if texture else None}
    return m
stone=mat('M_Basalt',(0.10,.16,.18),.84,texture=stone_tex)
sand=mat('M_Sediment',(.16,.24,.25),.93,texture=sand_tex)
stem=mat('M_OrganicDark',(.018,.09,.085),.5)
fanmat=mat('M_FanCopper',(.24,.065,.028),.55)
cyan=mat('M_BiolumeCyan',(.012,.65,.42),.32,1.5)
blue=mat('M_BiolumeBlue',(.025,.25,1),.35,2.4)
amber=mat('M_BiolumeAmber',(1,.22,.015),.38,2.1)
ringmat=mat('M_AncientCeramic',(.17,.26,.24),.48,texture=stone_tex,metal=.22)

def mesh(name,verts,faces,c,material,uvs=None):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); c.objects.link(o)
    if material: me.materials.append(material)
    for p in me.polygons: p.use_smooth=True
    uv=me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        for li in p.loop_indices:
            v=me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv=(v.x*.12,v.y*.12) if uvs is None else uvs[me.loops[li].vertex_index]
    return o

def tube_data(points,radii,sides=7):
    vs=[]; fs=[]; uv=[]
    for i,p in enumerate(points):
        p=Vector(p); d=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])
        d.normalize(); helper=Vector((0,0,1)) if abs(d.z)<.9 else Vector((1,0,0))
        a=d.cross(helper).normalized(); b=d.cross(a).normalized()
        for j in range(sides):
            v=p+radii[i]*(a*math.cos(j*math.tau/sides)+b*math.sin(j*math.tau/sides))
            vs.append(v); uv.append((j/sides,i/max(1,len(points)-1)))
        if i:
            for j in range(sides):
                fs.append(((i-1)*sides+j,(i-1)*sides+(j+1)%sides,i*sides+(j+1)%sides,i*sides+j))
    fs.append(tuple(reversed(range(sides)))); fs.append(tuple((len(points)-1)*sides+j for j in range(sides)))
    return vs,fs,uv

def tubes(name,branches,c,material,sides=7):
    verts=[]; faces=[]; uv=[]
    for pts,rs in branches:
        v,f,u=tube_data(pts,rs,sides); off=len(verts); verts+=v; faces += [tuple(j+off for j in face) for face in f]; uv+=u
    return mesh(name,verts,faces,c,material,uv)

def rock(name,seed):
    rng=random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6,radius=1)
    o=bpy.context.object; o.name=name; link(o,geology)
    for v in o.data.vertices:
        q=v.co.copy(); f=noise.noise_vector(q*2.4+Vector((seed*.73,0,0)))
        fine=noise.noise(q*19+Vector((seed,0,0)))
        v.co=q*(1+.24*f.x+.035*math.sin(q.z*24)+.055*fine)+Vector((.08*f.y,.08*f.z,0))
        if v.co.z<-.55: v.co.z=-.55+(v.co.z+.55)*.25
    o.data.materials.append(stone)
    for p in o.data.polygons:p.use_smooth=True
    return o
rocks=[rock(f'SM_Basalt_{i:02}',i+2) for i in range(4)]

# Coral branching is generated by design rules, then instanced with Geometry Nodes.
def coral_asset(name,seed):
    rng=random.Random(seed); branches=[]; tips=[]
    def branch(start,direction,length,radius,depth):
        start=Vector(start); direction=Vector(direction).normalized()
        pts=[start+direction*length*t/5+Vector((.035*math.sin(t),0,.022*t*t)) for t in range(6)]
        branches.append((pts,[radius*(1-.83*t/5) for t in range(6)]))
        if depth:
            for s in [-1,1]:
                direct=direction+Vector((s*rng.uniform(.5,.9),rng.uniform(-.25,.25),rng.uniform(.1,.45)))
                branch(pts[-1],direct,length*.64,radius*.61,depth-1)
        else: tips.append(pts[-1])
    for i in range(3): branch((0,0,0),(math.sin(i*2.1)*.3,math.cos(i*2.1)*.3,1),rng.uniform(.55,.9),.09,3)
    o=tubes(name,branches,flora,stem,6)
    vv=[];ff=[]
    for p in tips:
        off=len(vv);r=rng.uniform(.042,.075)
        for i in range(7):
            lat=math.pi*i/6
            for j in range(10):
                a=math.tau*j/10;vv.append(p+Vector((r*math.sin(lat)*math.cos(a),r*math.sin(lat)*math.sin(a),r*1.3*math.cos(lat))))
                if i:ff.append((off+(i-1)*10+j,off+(i-1)*10+(j+1)%10,off+i*10+(j+1)%10,off+i*10+j))
    tip=mesh(name+'_LuminousTips',vv,ff,flora,cyan)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True);tip.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.join()
    return o
corals=[coral_asset(f'SM_CoralBranch_{i:02}',i+5) for i in range(3)]

def fan_asset():
    branches=[]
    for i in range(29):
        a=-1.1+2.2*i/28
        pts=[(math.sin(a)*t*.13,math.sin(t*.6+a)*.035,.14+math.cos(a)*t*.14) for t in range(16)]
        branches.append((pts,[.027*(1-.6*t/15) for t in range(16)]))
    for t in [4,7,10,13,15]:
        pts=[(math.sin(-1.1+2.2*i/28)*t*.13,math.sin(t*.6-1.1+2.2*i/28)*.035,.14+math.cos(-1.1+2.2*i/28)*t*.14) for i in range(29)]
        branches.append((pts,[.014]*29))
    o=tubes('SM_SeaFan',branches,flora,fanmat,5)
    rim=tubes('SM_SeaFan_Lume',[(branches[-1][0],[.019]*29)],flora,amber,5)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);rim.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.join()
    return o
fan=fan_asset()

def ribbon_asset():
    verts=[];faces=[]
    for j in range(7):
        a=j*2.399; height=1.6+.9*math.sin(j*1.7)**2
        for i in range(17):
            t=i/16; center=Vector((.25*math.cos(a)+.4*math.sin(t*3+a)*t,.25*math.sin(a)+.35*math.sin(t*4+a)*t,height*t))
            side=Vector((math.cos(a+t),math.sin(a+t),0)); width=.10*math.sin(math.pi*t)**.7+.007
            verts.extend([center-side*width,center+side*width])
            if i: k=j*34+2*i; faces.append((k-2,k-1,k+1,k))
    return mesh('SM_RibbonKelp',verts,faces,flora,cyan)
kelp=ribbon_asset()

def cup_asset():
    vs=[];fs=[]; uv=[]
    for i in range(16):
        t=i/15; r=.10+.5*t**2
        z=1.1*t
        for j in range(32):
            a=j*math.tau/32; rr=r*(1+.06*math.sin(9*a))
            vs.append((rr*math.cos(a),rr*math.sin(a),z+.045*math.sin(5*a)*t*t));uv.append((j/32,t))
            if i:fs.append(((i-1)*32+j,(i-1)*32+(j+1)%32,i*32+(j+1)%32,i*32+j))
    o=mesh('SM_TrumpetCoral',vs,fs,flora,stem,uv)
    p=[(.60*math.cos(a),.60*math.sin(a),1.1+.045*math.sin(5*a)) for a in np.linspace(0,math.tau,65)]
    rim=tubes('Cup_Rim',[(p,[.027]*65)],flora,blue,6)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);rim.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.join()
    return o
cup=cup_asset()

def instance(proto,name,location,scale=(1,1,1),rot=(0,0,0),collection=None):
    o=bpy.data.objects.new(name,proto.data); (collection or C['01_ENVIRONMENT']).objects.link(o)
    o.location=location;o.scale=scale;o.rotation_euler=rot;o['source_asset']=proto.name
    return o
def floorheight(x,y):
    return -.8+.7*math.sin(x*.08+y*.035)+.36*math.sin(y*.17+x*.11)+.25*noise.noise(Vector((x*.16,y*.16,5)))

verts=[];faces=[]
nx,ny=100,130
for iy in range(ny+1):
    y=-45+iy*1.45
    for ix in range(nx+1):
        x=-72+ix*1.44; verts.append((x,y,floorheight(x,y)))
        if ix and iy:
            k=iy*(nx+1)+ix;faces.append((k-nx-2,k-nx-1,k,k-1))
terrain=mesh('SM_Seafloor',verts,faces,C['01_ENVIRONMENT'],sand)
terrain['export_role']='environment';terrain['collision']='complex_static'

# Geology establishes a broad, clear corridor; no cliff crosses the central route.
for side in [-1,1]:
    for row,y in enumerate([-14,7,27,53,81,112]):
        x=side*(23+random.uniform(-2,7))
        sx=random.uniform(7,12);sy=random.uniform(9,17);sz=random.uniform(13,25)
        if row==0: x=side*25;sz=20
        instance(rocks[row%4],f'Cliff_{side}_{row}',(x,y,sz*.45-2),(sx,sy,sz),(0,random.uniform(-.25,.25),random.random()*6.28))
        for j in range(3):
            xx=x+random.uniform(-9,9);yy=y+random.uniform(-10,10)
            instance(rocks[(row+j)%4],f'Talus_{side}_{row}_{j}',(xx,yy,floorheight(xx,yy)),(random.uniform(2,6),random.uniform(2,6),random.uniform(2,6)),(0,0,random.random()*6.28))
for i in range(65):
    x=random.choice([-1,1])*random.uniform(7.5,23);y=random.uniform(-28,100)
    s=random.uniform(.3,2.2)
    instance(random.choice(rocks),f'ReefRock_{i:03}',(x,y,floorheight(x,y)),(s,s*.85,s*.6),(0,0,random.random()*6.28))

# Landmark: fractured, eroded ring with inset luminous seams and a suspended core.
for seg,(a0,a1) in enumerate([(-.25,2.10),(2.34,3.95),(4.20,5.75)]):
    angles=np.linspace(a0,a1,100)
    pts=[(14*math.cos(a),0,15+17*math.sin(a)) for a in angles]
    rs=[1.15+.25*math.sin(a*7)+.10*math.sin(a*19) for a in angles]
    proto=tubes(f'SM_RelicArc_{seg}',[(pts,rs)],landmark,ringmat,12)
    instance(proto,f'RelicArc_{seg}',(0,52,0),rot=(.10,0,.08))
    pts2=[(12.9*math.cos(a),-.75,15+15.7*math.sin(a)) for a in angles]
    seam=tubes(f'SM_RelicSeam_{seg}',[(pts2,[.065]*len(pts2))],landmark,cyan,7)
    instance(seam,f'RelicSeam_{seg}',(0,52,0),rot=(.10,0,.08))
for i in range(15):
    a=-.20+i*math.tau/15
    if 2.10<a<2.34 or 3.95<a<4.20: continue
    p=Vector((14*math.cos(a),52,15+17*math.sin(a)))
    o=instance(rocks[i%4],f'RelicStoneRib_{i}',p,(1.2,2.1,1.8),(0,a,.08))
for i in range(7):
    x=math.sin(i*2.1)*3; y=52+math.cos(i*2.1)*1.7; z=7+i*2.6
    instance(rocks[i%4],f'SuspendedRelic_{i}',(x,y,z),(.55,.7,1.6),(0,.3*i,.7*i))
corepts=[(.35*math.sin(z*.5),51,6+z) for z in np.linspace(0,20,90)]
core=tubes('SM_RelicSpine',[(corepts,[.032]*90)],C['01_ENVIRONMENT'],amber,6)
for i in range(3):
    a=np.linspace(0,math.tau,80)
    pts=[((2.1+i*.35)*math.cos(t),51+(2.1+i*.35)*math.sin(t),11+i*4) for t in a]
    tubes(f'SM_CoreOrbit_{i}',[(pts,[.025]*80)],C['01_ENVIRONMENT'],amber,5)

# Curated near-camera flora provides scale and recognizable silhouettes.
for i in range(22):
    x=random.choice([-1,1])*random.uniform(5,16);y=random.uniform(-24,36)
    proto=fan if i%3==0 else corals[i%3]
    s=random.uniform(.8,1.8)
    instance(proto,f'HeroFlora_{i:02}',(x,y,floorheight(x,y)),(s,s,s),(0,0,random.uniform(-1.2,1.2)))

def scatter(name,proto,density,seed,scale_min,scale_max):
    # Custom emitter follows terrain, leaving the navigable center unobstructed.
    vv=[];ff=[]
    for side in [-1,1]:
        off=len(vv); X=13;Y=39
        for j in range(Y+1):
            y=-30+j*3.5
            for i in range(X+1):
                x=side*(7.5+i*1.2);vv.append((x,y,floorheight(x,y)+.02))
                if i and j:
                    k=off+j*(X+1)+i;ff.append((k-X-2,k-X-1,k,k-1))
    o=mesh(name,vv,ff,C['02_PROCEDURAL_SYSTEMS'],None)
    ng=bpy.data.node_groups.new('GN_'+name,'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    d=ng.interface.new_socket(name='Density',in_out='INPUT',socket_type='NodeSocketFloat');d.default_value=density;d.min_value=0;d.max_value=1
    sd=ng.interface.new_socket(name='Seed',in_out='INPUT',socket_type='NodeSocketInt');sd.default_value=seed
    n=ng.nodes;l=ng.links
    inp=n.new('NodeGroupInput');inp.location=(-600,80)
    out=n.new('NodeGroupOutput');out.location=(360,80)
    dist=n.new('GeometryNodeDistributePointsOnFaces');dist.location=(-350,80)
    l.new(inp.outputs['Geometry'],dist.inputs['Mesh']);l.new(inp.outputs['Density'],dist.inputs['Density']);l.new(inp.outputs['Seed'],dist.inputs['Seed'])
    info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=proto;info.inputs['As Instance'].default_value=True;info.location=(-350,-160)
    ins=n.new('GeometryNodeInstanceOnPoints');ins.location=(100,80)
    l.new(dist.outputs['Points'],ins.inputs['Points']);l.new(info.outputs['Geometry'],ins.inputs['Instance'])
    rand=n.new('FunctionNodeRandomValue');rand.data_type='FLOAT';rand.inputs['Min'].default_value=scale_min;rand.inputs['Max'].default_value=scale_max;rand.inputs['Seed'].default_value=seed+91;rand.location=(-150,-180)
    l.new(rand.outputs['Value'],ins.inputs['Scale'])
    r=n.new('FunctionNodeRandomValue');r.data_type='FLOAT_VECTOR';r.inputs['Min'].default_value=(-.08,-.08,0);r.inputs['Max'].default_value=(.08,.08,6.28);r.inputs['Seed'].default_value=seed+7;r.location=(-150,-370)
    l.new(r.outputs['Value'],ins.inputs['Rotation']);l.new(ins.outputs['Instances'],out.inputs['Geometry'])
    mod=o.modifiers.new('Procedural habitat scattering','NODES');mod.node_group=ng
    o['export_role']='realize_for_export';return o
scatter('CoralHabitat',corals[1],.045,15,.4,1.4)
scatter('RibbonHabitat',kelp,.025,34,.35,1.15)
scatter('TrumpetHabitat',cup,.035,21,.3,1.3)
scatter('SeaFanHabitat',fan,.015,78,.4,1.1)

# Suspended particulates: a separate Geometry Nodes volume distribution, no dynamics.
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.025)
mote=bpy.context.object;mote.name='SM_SuspendedMote';link(mote,flora);mote.data.materials.append(cyan)
pv=[(random.uniform(-24,24),random.uniform(-30,110),random.uniform(.5,42)) for _ in range(1500)]
pm=mesh('SuspendedParticulates',pv,[],C['04_ATMOSPHERE'],None)
ng=bpy.data.node_groups.new('GN_SuspendedParticulates','GeometryNodeTree')
ng.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');ng.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
n=ng.nodes;l=ng.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=mote;info.inputs['As Instance'].default_value=True
ins=n.new('GeometryNodeInstanceOnPoints');l.new(inp.outputs['Geometry'],ins.inputs['Points']);l.new(info.outputs['Geometry'],ins.inputs['Instance']);l.new(ins.outputs['Instances'],out.inputs['Geometry'])
mod=pm.modifiers.new('Mote instancing','NODES');mod.node_group=ng

fog=bpy.data.materials.new('M_UnderwaterVolume');fog.use_nodes=True
nt=fog.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');vol=nt.nodes.new('ShaderNodeVolumePrincipled')
vol.inputs['Density'].default_value=.007;vol.inputs['Color'].default_value=(.10,.30,.34,1);vol.inputs['Anisotropy'].default_value=.35;nt.links.new(vol.outputs['Volume'],out.inputs['Volume'])
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,45,26));fogbox=bpy.context.object;fogbox.name='Atmosphere_Underwater';fogbox.scale=(180,210,110);link(fogbox,C['04_ATMOSPHERE']);fogbox.data.materials.append(fog);fogbox.display_type='WIRE'

def light(name,kind,loc,color,power,size=10,target=None):
    d=bpy.data.lights.new(name,kind);d.energy=power;d.color=color
    if kind=='AREA':d.shape='DISK';d.size=size
    if kind=='POINT':d.shadow_soft_size=size
    if kind=='SPOT':d.spot_size=.22;d.spot_blend=.6;d.shadow_soft_size=.8
    o=bpy.data.objects.new(name,d);C['03_LIGHTING'].objects.link(o);o.location=loc
    if target:o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o
light('L_SurfaceCanopy','AREA',(0,24,48),(.20,.75,1),38000,65,(0,30,0))
light('L_ForegroundSoft','AREA',(-7,-16,14),(.12,.55,.6),4200,18,(0,5,0))
light('L_RelicRim','AREA',(0,67,26),(.10,.85,.72),24000,22,(0,46,12))
light('L_RelicWarm','POINT',(0,46,16),(1,.31,.07),2100,7)
for i in range(3):light(f'L_Shaft_{i}','SPOT',(-20+i*15,25+i*15,55),(.22,.65,1),50000,1,(-10+i*12,45+i*14,-4))

camdata=bpy.data.cameras.new('CAM_Descent');cam=bpy.data.objects.new('CAM_Descent',camdata);C['05_CAMERAS'].objects.link(cam);scene.camera=cam
camdata.lens=27;camdata.clip_end=400;camdata.dof.use_dof=False
path=[(1,(-3,-30,8),(0,50,16)),(240,(5,-9,7),(0,52,15)),(480,(-4,12,9),(0,52,17)),(720,(1,31,12),(0,52,18))]
for frame,pos,target in path:
    cam.location=pos;cam.rotation_euler=(Vector(target)-Vector(pos)).to_track_quat('-Z','Y').to_euler()
    cam.keyframe_insert(data_path='location',frame=frame);cam.keyframe_insert(data_path='rotation_euler',frame=frame)
    scene.timeline_markers.new(['Descent','Garden passage','Relic approach','Threshold'][len(scene.timeline_markers)],frame=frame)
scene.frame_set(1)
scene['project']='FLUID — A World in Motion';scene['version']='V1 Cinematic Ocean';scene['seed']=1209
scene['navigation']='Open central corridor: x=-5..5, y=-30..50, z=3..15 meters. No solver or creatures.'
scene['source_policy']='Procedural asset families remain editable. Export copies are evaluated separately.'

# Compositor glare keeps highlights local rather than washing the entire scene.
scene.use_nodes=True
try:
    tree=scene.compositing_node_group
except AttributeError:
    tree=None
if tree is None:
    tree=bpy.data.node_groups.new('COMP_Underwater','CompositorNodeTree')
    scene.compositing_node_group=tree
tree.nodes.clear();rl=tree.nodes.new('CompositorNodeRLayers');gl=tree.nodes.new('CompositorNodeGlare');gl.inputs['Type'].default_value='Fog Glow';gl.inputs['Quality'].default_value='High';gl.inputs['Strength'].default_value=.25
out=tree.nodes.new('NodeGroupOutput');tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
tree.links.new(rl.outputs['Image'],gl.inputs['Image']);tree.links.new(gl.outputs['Image'],out.inputs['Image'])

# Save asset families without replacing the main scene.
C['90_ASSET_SOURCES'].hide_viewport=True
for im in [stone_tex,sand_tex]: im.filepath='//../textures/'+im.name+'.png'
for family,collection in [('geology',geology),('vegetation',flora),('landmark',landmark)]:
    bpy.data.libraries.write(str(ROOT/'blender/assets'/f'{family}.blend'),{collection},fake_user=True,compress=True)
for im in [stone_tex,sand_tex]: im.filepath='//../textures/'+im.name+'.png'
scene.render.filepath=str(ROOT/'renders/previews'/'V1_Entrance.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blender/scenes/FLUID_V1_Environment.blend'))
(ROOT/'docs/material_manifest.json').write_text(json.dumps(materials,indent=2))
(ROOT/'docs/build_metrics.json').write_text(json.dumps({'blender':bpy.app.version_string,'build_seconds':time.perf_counter()-started,'objects':len(bpy.data.objects),'mesh_datablocks':len(bpy.data.meshes),'geometry_node_groups':len([g for g in bpy.data.node_groups if g.bl_idname=='GeometryNodeTree']),'frames':720,'fps':24,'seed':1209},indent=2))
if opts.render:
    t=time.perf_counter();bpy.ops.render.render(write_still=True)
    (ROOT/'docs/preview_metrics.json').write_text(json.dumps({'seconds':time.perf_counter()-t,'samples':scene.cycles.samples,'resolution':[scene.render.resolution_x,scene.render.resolution_y],'frame':scene.frame_current,'device':scene.cycles.device},indent=2))
print('FLUID_BUILD_OK',str(ROOT),flush=True)
