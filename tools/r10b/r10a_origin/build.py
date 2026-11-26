"""Draft the four R10-A sheets from PR30 data and the existing model meshes."""
from pathlib import Path
from collections import Counter
from hashlib import file_digest
import json
import math
import re
import subprocess
import sys

sys.dont_write_bytecode=True
from draft import *
from shapely import affinity
from shapely.ops import polylabel, unary_union
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parent
R7=ROOT.with_name("WP0_R7_20261125")
R8=ROOT.with_name("WP0_R8_20261125")
R9=ROOT.with_name("WP0_R9_기술도면집")
REPO=R7/"checkout"
R8OUT=R8/"delivery"
MODEL=R7/"source_geometry"
PR30="1164fc0f58d943598d8e48146a02fcb3214c852e"
sys.path[:0]=[str(REPO/"src"),str(REPO/"engine"),str(REPO/"studies/wp0_r7"),str(R8/"code")]
from t14s.planner import plan_floor,hatch_lines
from t14s.source import load_floor
from t14s.model import LAYER_ORDER
import book_views as bv
import validate_r7 as v7
from common_r8 import FINAL,make_core
from interfaces_r8 import door_profiles

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def sha(p):
    with p.open("rb") as f:return file_digest(f,"sha256").hexdigest()

M=bv.Model(MODEL,MODEL/"raw_slices/camera_bounds.json")
P=v7.mesh_view(read(R8/"_rejected/R8_PROPOSAL_MESHES.json"))
ED=v7.mesh_view(read(R8/"_rejected/R8_EDITED_TRIANGLES.json"))
WALK=read(R8OUT/"R8_WALKABILITY.json")
ST=read(R8OUT/"R8_3D_CLASH.json")
OS=read(R8OUT/"R8_STRUCTURAL_ASSUMPTIONS.json")["OS1"]
FF=M.floors
WW=WALK["cores"]["2F D"]
SEAM=WW["slab_slot_bounds_m"]
XSEC=(SEAM[0]+SEAM[2])/2
G=load_floor("2F")
PR=plan_floor("2F")
AX=[i for i in PR.items if i.layer=="A-GRID"]
XGRID=sorted([(i.ref.split()[-1],i.geom.bounds[0]) for i in AX if abs(i.geom.bounds[0]-i.geom.bounds[2])<.01],key=lambda i:i[1])
YGRID=sorted([(i.ref.split()[-1],i.geom.bounds[1]) for i in AX if abs(i.geom.bounds[1]-i.geom.bounds[3])<.01],key=lambda i:i[1])
PICKS={}
SRC_INFO={}
EVID={}
BR=next(o for o in P.bld if o["kind"]=="bridge" and o.get("core")=="D" and o.get("floor")=="2F")
DECK=v7.top(BR)
BOUND=box(*G.cores["D"])
PROPOSED_GRID="기둥 중심 기준 축"
MODELS=read(R9/"R9_SOURCE_HASH_MANIFEST.json")["files"]
SOURCE_PDF=R9/"WP0_R9_A2_기술도면집.pdf"

def mas():
    entries=[]
    for r in read(MODEL/"1F_master_current.json")["objects"]:
        if not r["name"].startswith("Core_D_"):
            continue
        world=np.array(r["verts"])
        world[:,:2]-=[9,18]
        entries.append(dict(name=r["name"],kind=r["props"]["kind"],verts=world.tolist(),faces=r["tris"]))
    return v7.mesh_view(entries)

MASTER=mas()
TITLE=["2층 전체 건축 평면도","전체 건축 종단면도","코어 D 상세 평·단면도","E2 브리지 구조 상세 연구도"]
IDS=["A-201","A-301","A-501","S-401"]

def locked_sources():
    same=subprocess.check_output(["git","-C",str(REPO),"diff","--name-only",PR30,"HEAD","--",
                                 "src/t14s","data/t14s/source_slices","engine","src/upper_layouts.py"],encoding="utf-8").strip()
    if same:
        raise RuntimeError(f"PR30 sources diverged: {same}")
    for i in MODELS:
        p=Path(i["absolute_path"])
        if p.is_file() and (p.suffix==".glb" or p.name=="1F_master.blend" or p.name==SOURCE_PDF.name):
            SRC_INFO[str(p.resolve())]=sha(p)
            assert SRC_INFO[str(p.resolve())]==i["r9_sha256"]
    SRC_INFO[str(SOURCE_PDF.resolve())]=sha(SOURCE_PDF)
    old=read(R9/"R9_OUTPUT_QA.json")["sha256"]
    assert SRC_INFO[str(SOURCE_PDF.resolve())]==old and len(SRC_INFO)>=3

def objects(core="D",floor=None,group=None,types=None):
    return [o for o in P.bld if o.get("core")==core and (not floor or o.get("floor")==floor)
            and (not group or o.get("group")==group) and not o.get("group","").startswith("OPTION ")
            and (not types or o["kind"] in types)]

def top_faces(o):
    return v7.top(o)

def cuts(mesh,objs,ax,station):
    nr=np.zeros(3);nr[ax]=1
    u=np.zeros(2);u[1-ax]=1
    result=[]
    for o in objs:
        tri=mesh.tris(o)
        if not len(tri) or tri[:,:,ax].min()>=station or tri[:,:,ax].max()<=station:
            continue
        da=tri[:,:,ax]
        selected=(da.min(axis=1)<=station)&(da.max(axis=1)>=station)
        poly=bv._cut_polygon(tri[selected],nr,station,u)
        if not poly.is_empty:
            result.append((o,poly))
    return result

def layer_geo(v,rows,axis,station,model=P,proposal=True,exclude=None):
    result=[]
    for o,g in cuts(model,rows,axis,station):
        g=g.intersection(v.win)
        if g.is_empty:continue
        k=o["kind"]
        if exclude and k in exclude:continue
        if k in {"core_wall","partition_wall","column"}:
            v.geo(g,.36,BLACK,CAND if proposal else EXIST)
        elif k in {"slab","stair","landing","vestibule","roof","bridge","threshold"}:
            v.geo(g,.36,INK if proposal else BLACK,CAND if proposal else EXIST)
        elif k in {"door","door_frame"}:
            v.geo(g,.16,INK)
        else:
            v.geo(g,.17,INK if proposal else GRAY)
        result.append((o,g))
    return result

def lvl(v,z,text_label,left=True):
    p=v.p
    x,y=v.xy(v.x0,z)
    qx=v.r[0] if left else v.r[2]
    rule(p,x,y,v.r[2],y,.10,LIGHT,GRID)
    mid=qx-4.7 if left else qx+4.7
    circle(p,mid,y,1.0,.16,BLACK,WHITE)
    rule(p,mid-1.5,y,mid+1.5,y,.11)
    rule(p,mid,y-1.5,mid,y+1.5,.11)
    text(p,mid+3 if not left else mid-2.3,y-.82,text_label,6.5,align="left" if not left else "right",halo=True)

def plan_grid(v):
    p=v.p
    for key,x in XGRID:
        xx,_=v.xy(x,0)
        rule(p,xx,57,xx,348,.10,LIGHT,GRID)
        symbol(p,xx,38,key,None,3.25)
    for key,y in YGRID:
        _,yy=v.xy(0,y)
        rule(p,51,yy,355,yy,.10,LIGHT,GRID)
        symbol(p,37,yy,key,None,3.25)
    gx=[v.xy(x,36) for _,x in XGRID]
    gy=[v.xy(-9,y) for _,y in YGRID]
    for q in (gx,gy):
        for a,b in zip(q,q[1:]):
            dim(p,a,b,-12 if q is gx else -11,f"{math.dist(a,b)/v.k*1000:,.0f}")
        total=f"{math.dist(q[0],q[-1])/v.k*1000:,.0f}"
        if q is gx:
            dim(p,q[0],q[-1],-19,total)
        else:
            dim(p,(31,q[0][1]),(31,q[-1][1]),-6,total)

def approved_room_run(poly):
    return poly.difference(BOUND)

def core_shell_plan(v,objects,z):
    for o,g in bv.plan_cut(type("Clip",(),{"bld":objects,"tris":lambda self,o:P.tris(o)})(),z,
             {"core_wall","partition_wall","door_frame","door","guard"},v.win.bounds):
        wall=o["kind"] in {"core_wall","partition_wall"}
        v.geo(g,.35 if wall else .16,INK,CAND if wall else None)

def stairs_plan(v,stack,z,show_all=False):
    rows=objects(group=f"STAIR D {stack}",types={"stair","landing","stair_rail"})
    base=FF[stack.split("-")[0]]
    levels=sorted({o["zmax"] for o in rows if o["kind"]=="landing"})
    # Outline each tread below the 1.50 m plan cut. Retain an overhead projection above it.
    for o in sorted(rows,key=lambda q:q["zmax"]):
        geom=top_faces(o)
        k=o["kind"]
        if k=="stair_rail" and (o["zmin"]>z or o["zmax"]<base):continue
        below=o["zmax"]<=z+.001
        if k=="stair" and o["zmax"]>z+2.2 and not show_all:continue
        v.geo(geom,.115 if k=="stair" else .15,INK if below else LIGHT,
              None,DASH if not below else None)
    return levels

def core_doors(v,fl):
    q=WALK["cores"].get(f"{fl} D")
    c=make_core("D",FINAL,q["selected_nominal_width_m"],q["outer_door_center_offset_m"]) if q else make_core("D",FINAL)
    for i,door in enumerate(c.doors):
        _,closed,opened,_,hinge,_,_,blade=door_profiles(door,i)
        length=(np.asarray(blade(0).centroid.coords[0])-hinge)@closed*2-.002
        arc=LineString([hinge+length*(math.cos(a)*closed+math.sin(a)*opened) for a in np.linspace(0,math.pi/2,31)])
        v.geo(arc,.115,INK,None,DASH)
        v.geo(blade(90),.15,INK)
    return c

def north(p,x,y):
    rad=math.radians(G.north_deg)
    circle(p,x,y,8.1,.14,BLACK)
    d=np.array([math.sin(rad),-math.cos(rad)])
    arrow(p,np.array([x,y])-d*5,np.array([x,y])+d*7,size=2.45)
    text(p,*(np.array([x,y])+d*11),"N",10,True,align='center')

def roomname(r):
    name=re.sub(r" \(\d+\)$","",r["name"]).replace("화장실 여자 화장실","여자 화장실").replace("화장실 남자 화장실","남자 화장실").replace("화장실 장애인 화장실","장애인 화장실").replace("화장실 공용·장애인 겸용","공용·장애인 화장실")
    return name.replace("식음 점포 (객석)","식음 점포 객석")

def plan(doc):
    p=sheet(doc,IDS[0],["2층 전체","건축 평면도"],"1:200",["A-301  A–A 종단","A-501  코어 D","S-401  E2 접합"],["기준 2F FFL +6.0004 m","절단면 FFL +1.50 m","실 구성·가구는 PR #30 검토","CH는 전 실 미확인"])
    v=View(p,IDS[0],200,(-12,-20,48,37),(49,67))
    p.set_rotation(0)
    frame(p,(395,39,520,291),.17)
    text(p,399,47,"2F 실 목록",11,True)
    text(p,515,47,"면적 ㎡  ·  CH 천장고",6.8,align='right',col=GRAY)
    rule(p,395,52,520,52,.24)
    for i,(x,c) in enumerate([(402,"실번호"),(429,"실명"),(489,"면적"),(512,"CH")]):
        text(p,x,58,c,7.4,True,align='center')
    for x in (410,476,500):
        rule(p,x,52,x,291,.11,LIGHT)
    v.geo(G.slab,0,BLACK,(.989,.990,.989))
    over=load_floor("3F").slab
    v.geo(over.boundary.difference(G.slab.boundary.buffer(.14)),.102,LIGHT,None,DASH)
    under=load_floor("1F").slab
    v.geo(under.boundary.difference(G.slab.buffer(.14)),.10,LIGHT,None,"[2 2] 0")
    h=G.outline.difference(G.slab)
    for g in sorted(parts(h,{"Polygon"}),key=lambda item:-item.area)[:9]:
        if g.area>9:
            v.geo(g.boundary,.15,GRAY,None,DASH)
            if g.area>55:
                clearance=g.difference(unary_union([t.outer for t in G.tubes.values()]+[DECK]).buffer(.48))
                areas=list(parts(clearance,{"Polygon"}))
                if areas:
                    pt=polylabel(max(areas,key=lambda x:x.area),tolerance=.18)
                    v.pt(pt.x,pt.y,"하부 OPEN",7.8,True,col=GRAY,align='center',halo=True)
    plan_grid(v)
    win=BOUND.buffer(.02)
    model_a10=[]
    for item in sorted(PR.items,key=lambda i:LAYER_ORDER[i.layer]):
        l,g=item.layer,item.geom
        if l in {"A-CIRC","A-CIRC-SVC","A-ZONE","A-GRID","A-FLOOR-HATCH","A-RAIL","A-ANNO-TAGS","A-ANNO-DIMS","A-ANNO-SYMB","A-ANNO-TEXT"}:
            continue
        if g.intersects(win) and l in {"A-WALL-CORE","A-DOOR","A-STAR","A-WALL-EXT"}:
            g=g.difference(win)
        if l=="A-WALL-EXT":
            v.geo(g,.25,BLACK); continue
        if l=="A-COLS":
            v.geo(g,.37,BLACK,BLACK); continue
        if l=="A-WALL-PART":
            v.geo(g,.30 if 'cubicle' not in item.ref else .16,GRAY,EXIST if item.fill else None);continue
        if l=="A-WALL-CORE":
            fill=EXIST if item.fill and 'footprint' not in item.ref else None
            v.geo(g,.40 if 'footprint' in item.ref else .30,BLACK,fill);continue
        if l=="A-GLAZ":
            v.geo(g,.23,BLACK,EXIST if item.fill else None);continue
        pal=.11 if l in {"A-FURN","A-FIXT","A-STAR-PROJ"} else .15
        v.geo(g,pal,GRAY,PALE if item.fill and l in {"A-TUBE","A-FURN","A-FIXT"} else None,
              DASH if item.dash or l=="A-STAR-PROJ" else None)
    cands=objects(floor="2F")
    v.geo(DECK,.24,INK,CAND)
    land=[o for o in P.bld if o.get("floor")=="2F" and o.get("group","").startswith("ESC ") and o["kind"] in {"escalator_deck","guard"}]
    for o in land:
        v.geo(top_faces(o),.17,INK,CAND if o["kind"]=="escalator_deck" else None)
    for o in cands:
        if o["kind"] in {"guard","threshold","vestibule","landing"}:
            v.geo(top_faces(o),.14,INK)
    low=FF["2F"]
    stairs_plan(v,"2F-3F",low+1.5)
    core_shell_plan(v,cands,low+1.5)
    core_doors(v,"2F")
    for r in PR.rooms:
        n=int(r["id"])
        yy=60+n*8.25
        rule(p,395,yy-3.6,520,yy-3.6,.1,LIGHT)
        name=roomname(r)
        text(p,402,yy+1.5,"2-"+r["id"],7.45,True,align='center')
        text(p,414,yy+1.5,name,7.75)
        text(p,497,yy+1.5,f"{r['poly'].area:,.1f}",7.45,align='right')
        text(p,511,yy+1.5,"—",7,align='center')
        pos=r.get("label")
        if pos and r["poly"].covers(Point(pos["cx"],pos["cy"])):
            x,y=v.xy(pos["cx"],pos["cy"])
        else:
            pt=r["poly"].representative_point();x,y=v.xy(pt.x,pt.y)
        if n in {2,3,8,10,11,16,20,25}:
            show="객석" if n!=10 else r["name"]
            text(p,x,y-3.55,show,8 if n!=10 else 10,True,align='center',halo=True)
        tag(p,x,y,"2-"+r["id"],5.45)
        model_a10.append(dict(id="2-"+r["id"],name=name,area=round(r["poly"].area,4),centre_paper_mm=(x,y),ceiling_height=None,grade=r["prov"]))
    for k in ("A","B","C","D"):
        a=G.cores[k]
        cx=(a[0]+a[2])/2
        if k!="D":
            v.pt(cx,a[1]+.55,"코어 "+k,6.6,True,align='center',halo=True)
    v.pt(-7.3,-17.1,"코어 D",6.6,True,align='center',halo=True)
    v.pt(-6.28,-12.92,"UP",5.9,True,align='right',halo=True)
    for i,txt in enumerate(PR.texts):
        if txt.s in ("UP","DN") and not win.covers(Point(txt.x,txt.y)):
            v.pt(txt.x,txt.y,txt.s,5.5,True,align='center',halo=True)
    for k in ("T1","T2","T3","T4","FR"):
        t=G.tubes[k]
        v.pt(*t.center,k,6.6,True,align='center',halo=True)
    for i,r in enumerate([a for a in WALK["escalators"] if a["floor"]=="2F"]):
        x,y=r["real_comb_edge_xy"]
        yy=y+1.15 if i==0 else y-1.55
        v.pt(x,yy,"하차" if r['role']=="arrive" else "승차",6.3,True,align='center',halo=True)
    sx,_=v.xy(XSEC,0)
    for y1,y2 in [(61,76),(328,347)]:
        rule(p,sx,y1,sx,y2,.22,BLACK,GRID)
    rule(p,sx,76,sx,328,.115,LIGHT,GRID)
    for yy in (61,347):
        symbol(p,sx,yy,"A","A-301",4.75)
        arrow(p,(sx+5,yy),(sx+12,yy),BLACK,size=2.7)
    leader(p,v.xy(-4.18,-2.4),(107,268),"01","S-401")
    leader(p,v.xy(-4.92,-14.8),(111,326),"01","A-501")
    north(p,362,73)
    text(p,361,89,"북각 "+str(G.north_deg)+"°",6.3,col=GRAY,align='center')
    rule(p,395,300,520,300,.23)
    text(p,397,306,"표기 및 원본 구분",8.8,True)
    for i,str_ in enumerate(["평면형 구획·설비·가구는 PR #30 설계 후보.","코어 D·브리지·콤 이음은 R8 연구 형상.","—  천장고 미확인. 모형 층고는 A-301.","위·아래층 투영 경계는 가는 점선.","치수 mm · 레벨 m · 동선 증거는 R9 N-2F."]):
        text(p,397,313+i*6.3,str_,7.65,col=GRAY)
    v.bar(10,57,378)
    view_caption(p,326,390,"01","2층 건축 평면도",200,520)
    EVID["A-201"]=dict(PR30_source_commit=PR30,source_slice_sha256=G.slice_sha256,rooms=model_a10,
        grid={"x":XGRID,"y":YGRID},section={"x":XSEC,"direction":"+X","target":"A-301"},
        architectural_model_items=dict(Counter(i.layer for i in PR.items if i.layer not in {"A-CIRC","A-CIRC-SVC"})),
        removed_layers=["A-CIRC","A-CIRC-SVC"],unknown_ceiling_count=len(model_a10))

def project_section(v,mesh,obj,ax,sign,span=None):
    tri=mesh.tris(obj)
    if span:
        nr=np.zeros(3); nr[ax]=1.
        if tri[:,:,ax].max()<span[0] or tri[:,:,ax].min()>span[1]:
            return None
        tri=bv._clip_half(tri,nr,span[0])
        if len(tri):tri=bv._clip_half(tri,-nr,-span[1])
    if not len(tri):return None
    u=np.zeros(2);u[1-ax]=sign
    return bv.silhouette(tri,u,np.zeros(2))

def full_section(doc):
    p=sheet(doc,IDS[1],["전체 건축","종단면도"],"1:250",["A-201  A–A 절단 위치","A-501  코어 D 실상세","S-401  2F E2 접합"],["절단 X = -4.200 m","+X 방향, 우측은 남측","코어 상자는 표현 외곽","점선은 뒤쪽 투영"])
    v=View(p,IDS[1],250,(-37.5,-12.4,22.2,78),(103,25))
    keys={}
    p.draw_rect(rect(99,336,101,380),width=0,color=None,fill=(.965,.965,.965))
    for name,z in FF.items():
        y=v.xy(v.x0,z)[1]
        rule(p,104,y,v.r[2]+2,y,.1,LIGHT,GRID)
        text(p,70,y-.65,f"{name}  {z:+.3f}",7.35,name in {"B2","1F","2F","7F","15F"},align='right')
        circle(p,74,y,.95,.13,BLACK)
        rule(p,74.9,y,100,y,.11,LIGHT)
    for (a,b),(c,dz) in zip(FF.items(),list(FF.items())[1:]):
        y1,y2=v.xy(0,b)[1],v.xy(0,dz)[1]
        dim(p,(92,y1),(92,y2),0,f"{(dz-b)*1000:,.0f}",vertical=True)
    cutrecords=[]
    old=cuts(M,M.bld,0,XSEC)
    oldnames={o["name"] for o,_ in old}
    floor_segments={}
    bridge_hits=[]
    projected=[]
    for o in M.bld:
        k=o["kind"]
        name=o["name"]
        if k not in {"stair","ramp","tube_wall","shaft","column"}:
            continue
        if k in {"tube_wall","shaft","column"} and name in oldnames:
            continue
        if k=="column":
            continue
        g=project_section(v,M,o,0,-1,(XSEC+.002,7.20))
        if g is None or g.is_empty:continue
        v.geo(g.boundary,.12,GRAY,None,DASH)
        projected.append(name)
    for o,g in sorted(old,key=lambda pair:pair[0]["kind"] in {"slab","roof"}):
        name,k=o["name"],o["kind"]
        g=affinity.scale(g,xfact=-1,origin=(0,0))
        if k=="core_wall":
            v.geo(g.boundary,.18,GRAY,None,DASH)
        elif k in {"slab","roof","column"}:
            v.geo(g,.38,BLACK,EXIST)
            if k=="slab" and o.get("floor") in FF:
                floor_segments.setdefault(o["floor"],[]).append(g)
        elif k in {"stair","ramp","tube_wall","shaft"}:
            v.geo(g,.19,BLACK,PALE)
        elif k=="facade" and ("glass" in name or "mullion" in name):
            v.geo(g,.16,GRAY)
        else:
            v.geo(g,.11,GRAY)
        cutrecords.append(dict(name=name,kind=k,section_bounds=list(g.bounds)))
    for o,g in cuts(P,objects(types={"bridge","stair","landing","threshold","vestibule"}),0,XSEC):
        zscale=affinity.scale(g,xfact=-1,origin=(0,0))
        if o["kind"]=="bridge":
            v.geo(zscale,.37,INK,CAND)
            bridge_hits.append((o["name"],zscale))
        elif o["kind"]!="vestibule":
            v.geo(zscale,.17,INK,CAND)
    assert len(bridge_hits)==2
    for i,(name,b) in enumerate(bridge_hits):
        pt=b.representative_point()
        x,y=v.xy(pt.x,pt.y)
        leader(p,(x,y),(371,y-5),"01","S-401" if name.startswith("2F") else "7F D")
    for label,z,panel_x in [("서측 캡슐 / 에스컬레이터 투영",20.1,-9),("서측 서비스 튜브",50.1,-8.8),("코어 D 표현 외곽",65.9,15),
                            ("T1 램프 튜브 투영",48.3,5),("T3 승강기 튜브 투영",66.7,-23.5),("남측 OPEN",14.4,10)]:
        v.pt(panel_x,z,label,7.0,True,col=GRAY,align='center',halo=True)
    programs=[]
    name_map={"F&B":"식음","garden":"정원","판매":"판매","서비스":"서비스","문화·엔터":"문화·엔터"}
    for fl,z in FF.items():
        f=load_floor(fl)
        vals=[]
        for i in f.zones:
            if i["poly"].intersects(LineString([(XSEC,-39),(XSEC,46)])) and i.get("program_floor") in {fl,None}:
                n=name_map.get(i["name_ko"],i["name_ko"])
                if n not in vals:vals.append(n)
        if vals:programs.append((fl,z,vals))
        y=v.xy(0,z)[1]
        text(p,409,y-.7,fl,7.3,True)
        text(p,420,y-.7," · ".join(vals) if vals else "프로그램 대조 대기",7.25,col=GRAY)
        if fl in {"B2","B1","1F","2F","3F","5F","8F","10F","11F","12F","13F","14F"} and vals:
            pos=-14.4 if fl in {"B2","2F","5F","8F","10F","11F","13F"} else -26.4
            v.pt(pos,z+1.68,vals[0],7.2,False,col=GRAY,align='center',halo=True)
    max_roof=max(max(h["section_bounds"][1::2]) for h in cutrecords if h["kind"]=="roof")
    rx,ry=v.xy(-30,max_roof)
    text(p,409,ry+.8,f"지붕 절단 최대 +{max_roof:.3f} m",7.55,True)
    text(p,409,21,"PR #30 층별 프로그램",8.65,True)
    text(p,409,27,"절단축 교차 기준 · 시공 구획 미확인",6.6,col=GRAY)
    for key,y in YGRID:
        xx,yy=v.xy(-y,76.8)
        rule(p,xx,yy+6.4,xx,v.r[3]-.4,.095,(.85,.86,.86),GRID)
        symbol(p,xx,yy-4.1,key,None,2.8)
    coords=[v.xy(-y,76.8) for _,y in reversed(YGRID)]
    for a,b in zip(coords,coords[1:]):
        dim(p,a,b,5.9,f"{math.dist(a,b)/v.k*1000:,.0f}")
    # Show the area of the upper gardens and voids from the program-model footprint.
    for fl in ("6F","15F"):
        z=FF[fl]
        f=load_floor(fl)
        for i in f.zones:
            if i["name_ko"]=="garden":
                span=i["poly"].intersection(LineString([(XSEC,-38),(XSEC,39)]))
                for end in parts(span,{"LineString"}):
                    station=-(end.bounds[1]+end.bounds[3])/2
                    v.pt(station,z+1.92,"정원 계획",7.4,True,col=INK,align='center',halo=True)
    text(p,409,377,"표기 치수 mm · 레벨 m",7,col=GRAY)
    v.bar(10,112,394)
    view_caption(p,352,395,"01","A–A 전체 종단면",250,518)
    EVID["A-301"]=dict(cut_axis="X",value=XSEC,direction="+X",source_levels=FF,roof_max=max_roof,
                       original_cuts=cutrecords,projected_objects=projected,projection_window_x_m=[XSEC,7.20],
                       core_original_grade="expression envelope",proposed_bridge_cuts=[x[0] for x in bridge_hits],
                       floor_programs=programs)

def small_plan(v,fl,stack):
    z=FF[fl]
    ss=ST["staircase"][f"D {stack}"]
    cands=objects(floor=fl)
    for o in cands:
        if o["kind"] in {"threshold","vestibule","landing","bridge"}:
            v.geo(top_faces(o),.14,INK,CAND if o["kind"]=="bridge" else None)
    stairs_plan(v,stack,z+1.5,show_all=True)
    core_shell_plan(v,cands,z+1.5)
    c=core_doors(v,fl)
    # Draw direction only through the flight footprint and stop at the core window.
    for i,flight in enumerate(c.flights):
        a=np.array(flight.start); d=np.array(flight.direction)
        x=a+d*flight.length*.55
        left=np.array([-d[1],d[0]])
        label=tuple(x+left*.12)
        v.pt(*label,str(i+1),6.2,True,align='center',halo=True)
        if i==0:
            arrow(v.p,v.xy(*(a+d*.14)),v.xy(*(a+d*.77)),INK,.18,1.8)
    v.pt(-8.28,-13.9,"UP",6.2,True,align='center',halo=True)
    if fl=="2F":
        v.pt(-6.28,-12.62,"DN",6.25,True,align='right',halo=True)
    v.pt(-3.96,-16.55,"부속실",7.4,True,col=INK,align='center',halo=True)
    v.pt(-3.96,-17.05,f"{z:+.3f}",6.6,align='center',halo=True)
    v.pt(-5.53,-12.81,"주 계단참",6.3,True,align='center',halo=True)
    bx0,by0,bx1,by1=c.bounds
    v.dim((bx0,by1),(bx1,by1),-8)
    v.dim((bx0,by0),(bx0,by1),-8)
    vx0,vy0,vx1,vy1=c.vestibule.bounds
    v.dim((vx0,by0),(vx1,by0),7)
    for i,door in enumerate(c.doors):
        x,y=door.hinge
        v.dim((x,y),(x,door.closed_end[1]),9 if i==0 else -10)
    return ss,c

def flight_key(p,x,y,ss,fl,end):
    text(p,x,y,"층고 "+f"{ss['floor_to_floor_m']*1000:,.0f}",8.8,True)
    text(p,x,y+5.7,"순유효폭  "+f"{ss['clear_width_m']*1000:,.0f}",7.6,col=GRAY)
    for i,(n,z) in enumerate(zip(ss["risers"],ss["landing_elevations_m"]),1):
        at=y+13+(i-1)*12.2
        rule(p,x,at-3.6,x+86,at-3.6,.12,LIGHT)
        text(p,x,at,f"{i}갈래",7.35,True)
        text(p,x+14,at,f"{n}R × {ss['riser_mm']:.2f}",7.3)
        text(p,x+86,at,f"{z:+.3f} m",6.85,align='right')
        text(p,x+14,at+4.3,f"{n-1}T × {ss['going_mm']:.0f} = {(n-1)*ss['going_mm']:,.0f}",6.8,col=GRAY)
    if fl=="2F":
        text(p,x,y+66,f"문틀 사이 {WW['movement'][0]['jamb_to_jamb_m']*1000:,.0f}  ·  90° 순개구 {WW['movement'][0]['measured_clear_along_opening_m']*1000:,.0f}",6.8)
    else:
        text(p,x,y+66,"1F 후보 문의 순개구 검증 보류.",6.8)
    text(p,x,y+72,"R = 챌면  /  T = 디딤판 · 단위 mm",6.55,col=GRAY)

def core(doc):
    p=sheet(doc,IDS[2],["코어 D","상세 평·단면도"],"1:50",["A-201  코어 위치","A-301  건물 A–A","S-401  E2 접합"],["A0 후보 6×6 m 유지","1F 마스터와 중첩 대조","두 문 제품·정착 미확인","A1/A2 비교는 R9 A-D"])
    v1=View(p,"A-501/01",50,(-9.6,-18.45,-2.1,-11.45),(43,40))
    v2=View(p,"A-501/02",50,(-9.6,-18.45,-2.1,-11.45),(43,218))
    s1,c=small_plan(v1,"1F","1F-2F")
    s2,_=small_plan(v2,"2F","2F-3F")
    view_caption(p,41,195,"01","1F→2F 계단 후보 평면",50,310)
    view_caption(p,41,375,"02","2F→3F 계단 후보 평면",50,310)
    flight_key(p,212,56,s1,"1F","2F")
    flight_key(p,212,234,s2,"2F","3F")
    steps=[o for o in objects(types={"stair"}) if o["group"] in {"STAIR D 1F-2F","STAIR D 2F-3F"}]
    limits=[(float(P.tris(o)[:,:,0].min()),float(P.tris(o)[:,:,0].max())) for o in steps]
    xm0=c.bounds[0]
    candidates=np.arange(xm0+.4,xm0+2.15,.05)
    scores={round(x,2):sum(a+.015<x<b-.015 for a,b in limits) for x in candidates}
    eligible=[x for x,score in scores.items() if score==max(scores.values())]
    core_x=eligible[len(eligible)//2]
    for v in (v1,v2):
        a,b=v.xy(core_x,-18.33),v.xy(core_x,-11.58)
        line(p,[a,b],.115,GRAY,GRID)
        symbol(p,b[0],b[1]+4,"B","03",3.5)
        arrow(p,(b[0]+4,b[1]+4),(b[0]+11,b[1]+4),BLACK,size=2)
    v=View(p,"A-501/03",50,(-18.6,-.26,-11.26,11.35),(351,58))
    for fl in ("1F","2F","3F"):
        lvl(v,FF[fl],f"{fl}  {FF[fl]:+.3f}")
    enclosures=[o for o in objects(types={"core_wall","partition_wall","door","door_frame","vestibule","landing"})
                if o.get("floor") in {"1F","2F","3F"} and not o["group"].startswith("STAIR ")]
    for stack in ("1F-2F","2F-3F"):
        projected=[project_section(v,P,o,0,1,(core_x+.45,c.bounds[2]-.23)) for o in objects(group=f"STAIR D {stack}",types={"stair","landing"})]
        underlay=unary_union([g for g in projected if g is not None and not g.is_empty])
        v.geo(underlay.boundary,.14,LIGHT,None,DASH)
    actual=cuts(P,[o for o in enclosures if o["kind"] in {"core_wall","partition_wall"}],0,core_x)
    shell=unary_union([g for _,g in actual])
    v.geo(shell,.37,BLACK,CAND)
    actual+=layer_geo(v,enclosures,0,core_x,exclude={"vestibule","landing","core_wall","partition_wall"})
    for stack in ("1F-2F","2F-3F"):
        actual+=layer_geo(v,objects(group=f"STAIR D {stack}"),0,core_x)
    for stack,zlo,zhi in [("1F-2F",FF["1F"],FF["2F"]),("2F-3F",FF["2F"],FF["3F"])]:
        ss=ST["staircase"][f"D {stack}"]
        steps=[g for o,g in actual if o["kind"]=="stair" and o["group"].endswith(stack)]
        merged=unary_union(steps)
        x0,z0,x1,z1=merged.bounds
        v.dim((x0,z0-.15),(x1,z0-.15),5)
        v.pt(x0+.22,z1+.22,f"R {ss['riser_mm']:.2f}  ·  T {ss['going_mm']:.0f}",7.1,True,col=INK,halo=True)
        lon=ss["landing_elevations_m"][1]
        ax,by=v.xy(x1,lon)
        rule(p,ax,by,ax+11,by,.12,INK)
        text(p,ax+12,by-1.35,f"{lon:+.3f}",7.0,True,col=INK,halo=True)
    mask=[o for o in MASTER.bld if o["kind"]=="stair"]
    mc=cuts(MASTER,mask,0,core_x)
    assert mc and len(actual)>8
    for o,g in mc:
        v.geo(g.boundary,.20,BROWN,None,"[3 1.4] 0")
    off=ST["approved_1F_interface"]["D"]
    az=off["approved_flight_top_levels_m"]
    rz=off["R8_flight_landing_levels_m"]
    idx=max(range(4),key=lambda i:abs(az[i]-rz[i]))
    for i,(o,n) in enumerate(zip(az,rz),1):
        if abs(o-n)<.003:continue
        a=v.xy(-13.15,o);b=v.xy(-13.15,n)
        for zx,zz,col in [(a,o,BROWN),(b,n,INK)]:
            rule(p,zx[0]-12,zx[1],zx[0]+22,zx[1],.15,col,"[2 1] 0")
        label=f"Δ {abs(o-n)*1000:,.1f}"
        ay=(a[1]+b[1])/2
        rule(p,a[0]+22,ay,503,ay,.115,GRAY)
        text(p,509,ay+.95,label,7.0,True,col=BROWN,align='right',halo=True)
    view_caption(p,332,308,"03",f"B–B 실제 절단 · X {core_x:.2f} m",50,517)
    rule(p,330,318,518,318,.21)
    text(p,331,326,"1F 승인 마스터 대비",9.2,True)
    line(p,[(331,333),(346,333)],.23,BROWN,"[3 1.4] 0")
    text(p,349,334,"1F 승인 계단 절단 외곽",7.4)
    line(p,[(331,340),(346,340)],.24,INK)
    text(p,349,341,"A0 연구 형상 절단",7.4)
    for i,s in enumerate([
        f"2F 받침 레벨 차이 {off['2F_top_level_difference_m']*1000:.1f} mm.",
        f"중간 참 최대 편차 {abs(az[idx]-rz[idx])*1000:.1f} mm.",
        "디딤판·참 메시 외곽 · 구조판 및 마감 미확인.",
        "승인 1F 계단과 연구 스택의 통합 보류."]):
        text(p,331,349+i*5.9,s,7.35,col=GRAY)
    text(p,212,151,"부속실·문 및 레벨",8.6,True)
    text(p,212,158,"두 개의 방화문은 후보 사양.",7.2,col=GRAY)
    text(p,212,164,"개방 각도별 동선은 R9 V-01.",7.2,col=GRAY)
    v2.bar(2,41,389)
    EVID["A-501"]=dict(core="D",left_views=["1F-2F","2F-3F"],stacks=[s1,s2],
                       section_x_m=core_x,master_meshes=[o["name"] for o,_ in mc],
                       intersecting_steps=sorted(o["name"] for o,_ in actual if o["kind"]=="stair"),
                       actual_section_meshes=[o["name"] for o,_ in actual],match=off,
                       max_landing_mismatch_mm=abs(az[idx]-rz[idx])*1000)

def ref_mark(p,v,key,points,target,placement):
    for a,b in zip(points,points[1:]):
        rule(p,*v.xy(*a),*v.xy(*b),.14,BLACK,GRID)
    for i,co in enumerate(placement):
        symbol(p,*v.xy(*co),key,target,3.5)

def slab_source(z,fl,adjusted=False):
    s=[o for o in M.bld if o["kind"]=="slab" and o.get("floor")==fl]
    if not s:
        s=[o for o in M.bld if o["kind"]=="slab" and abs(M.tris(o)[:,:,2].max()-z)<.03]
    return s

def structure(doc):
    p=sheet(doc,IDS[3],["E2 브리지","구조 상세 연구도"],"1:100 · 1:75 · 1:25",["A-201  2F 접합 위치","A-301  A–A 종단","A-501  코어 D"],["2F D 대표 E2 접합","OS-1 양단 지지 가정","실 지점·앵커·배근 미확인","제작·구조 승인 보류"])
    z=FF["2F"]
    v=View(p,"S-401/01",100,(-10.6,-18.7,1.6,6.3),(57,60))
    joint=objects(floor="2F",types={"guard","threshold","interface"})
    direct=[o for o in joint if ("E2" in o["name"] or "RETURN" in o["name"] or "SEAM" in o["name"])]
    iface=[o for o in direct if o["kind"]=="interface"]
    assert len(iface)==2
    si={r["name"]:top_faces(r) for r in iface}
    anchors={1:next(g for n,g in si.items() if "interface 1" in n),
             2:next(g for n,g in si.items() if "interface 2" in n)}
    pN=[anchors[i].centroid for i in (1,2)]
    assert abs(DECK.area-57.715)<.00001
    v.geo(G.slab,.24,BLACK,EXIST)
    v.geo(BOUND,.28,GRAY,None,DASH)
    v.geo(DECK,.42,INK,CAND)
    for o in direct:
        g=top_faces(o)
        if o["kind"]=="interface":
            v.geo(g,.18,BROWN,None,DASH)
        else:
            v.geo(g,.14,GRAY)
    for y in (5.,-12.):
        v.geo(LineString([(-10.45,y),(1.35,y)]),.12,LIGHT,None,GRID)
    for k,x in XGRID[:2]:
        xx,yy=v.xy(x,6.1)
        rule(p,xx,yy-4,xx,v.r[3],.11,GRAY,GRID)
        symbol(p,xx,yy-6,k,None,3.2)
    for k,y in YGRID:
        if v.y0<y<v.y1:
            x1,y1=v.xy(v.x0,y)
            rule(p,x1,y1,v.r[2],y1,.11,GRAY,GRID)
            symbol(p,x1-5,y1,k,None,3.2)
    v.dim((SEAM[0],4.99),(SEAM[2],4.99),-11)
    v.dim((XSEC,5),(XSEC,-12),40)
    v.geo(LineString([(XSEC,5.2),(XSEC,-12.4)]),.15,BLACK,None,GRID)
    ref_mark(p,v,"B",[(-6.6,-3.5),(-2.3,-3.5)],"03",[(-6.6,-3.5),(-2.3,-3.5)])
    v.pt(XSEC,-6.7,"PL-01",8.4,True,col=INK,align='center',halo=True)
    for i,pt in enumerate(pN,1):
        after=(169,85) if i==2 else (169,248)
        leader(p,v.xy(pt.x,pt.y),after,f"0{3+i}","S-401")
    leader(p,v.xy(-3.22,-7.82),(150,192),"G-01",None)
    v.pt(-7.7,-15.95,"코어 D",7.2,True,align='center',halo=True)
    v.pt(-7.2,5.68,"SL-01",7.1,True,align='center',halo=True)
    view_caption(p,36,324,"01","구조 연구 평면 · 2F D",100,175)
    v.bar(5,43,338)
    # The dimensions and level relationships come from the 3D deck and supporting reference geometry.
    sec=View(p,"S-401/02",75,(-14.2,4.3,8.2,8.25),(201,53))
    src=slab_source(z,"2F")
    assert src
    layer_geo(sec,src,0,XSEC,model=M,proposal=False)
    layer_geo(sec,[BR]+direct,0,XSEC)
    outline=cuts(M,[o for o in M.bld if o["name"]=="A-VERT-STRS_D"],0,XSEC)
    for _,g in outline:sec.geo(g.boundary,.17,GRAY,None,DASH)
    lvl(sec,z,"FFL",left=True)
    sec.dim((-12,z),(5,z),12)
    sec.pt(-11.9,7.42,"코어 북측 경계",7.6,True,halo=True)
    sec.pt(5.25,7.42,"슬래브 단부",7.6,True,halo=True)
    view_caption(p,194,120,"02","A–A 브리지 종단 · X = -4.200 m",75,520)
    cross=View(p,"S-401/03",25,(-6.1,5.25,-2.3,7.55),(192,135))
    mid_y=(5-12)/2
    layer_geo(cross,[BR]+direct,1,mid_y)
    cross.dim((SEAM[0],z),(SEAM[2],z),18)
    cross.dim((SEAM[2],BR["zmin"]),(SEAM[2],BR["zmax"]),12)
    lvl(cross,z,f"+{z:.3f}",left=True)
    view_caption(p,191,234,"03","B–B 브리지 횡단",25,346)
    x1=354
    text(p,x1,139,"부재 및 검토 구간",9.6,True)
    for i,(name,description) in enumerate([("PL-01","연구 데크 · 실제 메시 250 mm"),("G-01","난간 연구 형상 · 단부 고정 미확인"),
                      ("IF-01","코어측 후보 구간 · 지지벽 실측 필요"),("IF-02","슬래브측 후보 구간 · 정착 미확인"),
                      ("SL-01","원본 슬래브 · 배근 자료 미확보")]):
        y=151+i*10.4
        rule(p,x1,y-4.3,518,y-4.3,.13,LIGHT)
        text(p,x1,y,name,7.3,True,col=INK if i<2 else BLACK)
        text(p,x1+25,y,description,7.45)
    text(p,x1,207,"OS-1  ·  지지점 및 정착 보류",8.5,True,col=BROWN)
    text(p,x1,214,"17,000은 평면 간격. 편심·비틀림과",7.7,col=GRAY)
    text(p,x1,219,"양단의 하중 전달 및 처짐·진동 검토 필요.",7.7,col=GRAY)
    core=View(p,"S-401/04",25,(-4.4,5.25,-.55,7.5),(191,250))
    y_if1=pN[0].y
    m_core=[o for o in M.bld if o["name"]=="A-VERT-STRS_D"]
    core_cuts=cuts(M,m_core,1,y_if1)
    contact_distance=min((abs(g.bounds[2]-anchors[1].bounds[0]) for _,g in core_cuts),default=None)
    for _,g in core_cuts:core.geo(g.boundary,.22,GRAY,None,DASH)
    layer_geo(core,[BR]+direct,1,y_if1,exclude={"interface"})
    for _,g in cuts(P,[iface[0]],1,y_if1):
        core.geo(g.boundary,.23,BROWN,None,DASH)
    xx,yy=core.xy(pN[0].x,5.64)
    arrow(p,(xx+17,yy-17),(xx,yy),BROWN,.18,1.7)
    text(p,xx+15,yy-18.3,"IF-01",7.45,True,col=BROWN)
    core.pt(-4.0,7.08,"코어 표현 경계",7.55,True,halo=True)
    lvl(core,z,"FFL",left=True)
    seam=View(p,"S-401/05",25,(3.4,5.25,7.18,7.5),(365,250))
    slab_geometry=layer_geo(seam,src,0,XSEC,model=M,proposal=False)
    layer_geo(seam,[BR]+direct,0,XSEC,exclude={"interface"})
    for _,g in cuts(P,[iface[1]],0,XSEC):seam.geo(g.boundary,.23,BROWN,None,DASH)
    level_rail=[o for o in ED.bld if o.get("source") in WW["source_rails"]]
    layer_geo(seam,level_rail,0,XSEC,model=ED,proposal=False)
    xx,yy=seam.xy(pN[1].y,5.64)
    arrow(p,(xx+20,yy-16),(xx,yy),BROWN,.18,1.7)
    text(p,xx+19,yy-17.5,"IF-02",7.45,True,col=BROWN)
    lvl(seam,z,"FFL",left=True)
    seam.pt(3.91,6.23,"PL-01",7.3,True,col=INK,halo=True)
    seam.pt(6.21,6.23,"SL-01",7.3,True,halo=True)
    seam.pt(4.73,6.84,"연구용 이음 덮개",7.2,True,col=INK,halo=True)
    pxy=seam.xy(4.997,z-.014)
    arrow(p,seam.xy(5.15,6.69),pxy,INK,.15,1.65)
    if slab_geometry:
        _,g=slab_geometry[0]
        sx,sz,ex,h=g.bounds
        seam.dim((6.58,sz),(6.58,h),12)
    cover=next(o for o in direct if o["name"].startswith("SEAM "))
    _,a,_,b=top_faces(cover).bounds
    seam.dim((a,z),(b,z),-20)
    core.pt(-2.18,6.22,"PL-01",7.3,True,col=INK,halo=True)
    view_caption(p,191,352,"04",f"코어측 · Y {y_if1:.2f} m",25,345)
    view_caption(p,365,352,"05","슬래브측 · X -4.20 m",25,518)
    for i,s in enumerate(["갈색 점선은 R8 접합 검토 체적의 단면. 04의 코어 외곽은 원본 표현 박스.",
        "검증 필요  /  실 지점 좌표 · 하부 기존 보/벽 단면과 배근 · 정착·받침 · 하중·변위.",
        "OS-1 양단 지지방식 검토 · 중간 기둥 없음 · 실제 상세 및 시공 설계 보류."]):
        text(p,192,364+6*i,s,7.35,col=GRAY)
    cross.bar(2,428,384)
    EVID["S-401"]=dict(core="2F D",deck_area_m2=DECK.area,deck_thickness_m=BR["zmax"]-BR["zmin"],
                       gap_m=17.,bridge_width_m=SEAM[2]-SEAM[0],ends={f"IF-0{i}":list(g.bounds) for i,g in anchors.items()},
                       core_section_y=y_if1,slab_section_x=XSEC,transverse_section_y=mid_y,
                       expression_core_edge_to_assumed_interface_m=contact_distance,
                       structure_status="BLOCKED_STRUCTURAL_EVIDENCE",structure_inputs=OS)

def main():
    locked_sources()
    out=ROOT/"review_packet"
    target=out/"pdf"
    target.mkdir(parents=True,exist_ok=True)
    full=fitz.open()
    for func in (plan,full_section,core,structure):
        print("Build "+func.__name__,flush=True)
        func(full)
    full.set_toc([[1,f"{code} {title}",i+1] for i,(code,title) in enumerate(zip(IDS,TITLE))])
    full.set_metadata(dict(title="WP0 R10-A · 대표 도면 4장",subject="독립 검수용",author="WP0 연구"))
    full.subset_fonts()
    final=target/"WP0_R10A_Representative_A2.pdf"
    full.save(final,garbage=4,deflate=True)
    for s,expected in zip(full,IDS):
        assert expected in s.get_text() and len(s.get_image_info())==0
    for path,digest in SRC_INFO.items():
        assert sha(Path(path))==digest
    validation=out/"validation"
    validation.mkdir(exist_ok=True)
    data=dict(sheets=EVID,calculated_dimensions=SCALE_CHECKS,graphical_scales=GEOM,
              normalized_geometry_at_draft_clip=NORMALIZED,
              labels=BBOX,protected_local_sources=[dict(path=path,sha256=digest) for path,digest in SRC_INFO.items()],
              pdf_sha256=sha(final))
    (validation/"R10A_GEOMETRY.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(final.resolve(),flush=True)

if __name__=="__main__":
    main()




