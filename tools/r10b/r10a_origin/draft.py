"""Vector drafting utilities in A2 paper millimetres."""
from datetime import datetime
import math
import fitz
import numpy as np
from shapely.geometry import box,LineString,Polygon,Point
from shapely import make_valid

K=72/25.4
BLACK=(.09,.105,.11)
GRAY=(.37,.39,.40)
LIGHT=(.73,.75,.75)
FAINT=(.89,.90,.90)
PALE=(.966,.969,.968)
INK=(.14,.32,.33)
CAND=(.82,.90,.89)
EXIST=(.85,.86,.86)
BROWN=(.50,.27,.17)
WHITE=(1,1,1)
GRID="[10 3 1 3] 0"
DASH="[4 2] 0"
FONTS={n:fitz.Font(fontfile=f"C:/Windows/Fonts/{f}") for n,f in (("Body","malgun.ttf"),("Bold","malgunbd.ttf"))}
BBOX=[]
SCALE_CHECKS=[]
GEOM=[]
NORMALIZED=[]

def point(x,y):
    return fitz.Point(x*K,y*K)

def rect(x1,y1,x2,y2):
    return fitz.Rect(x1*K,y1*K,x2*K,y2*K)

def text(p,x,y,s,size=8,bold=False,col=BLACK,align='left',halo=False,rotate=0):
    s=str(s)
    f="Bold" if bold else "Body"
    w=FONTS[f].text_length(s,fontsize=size)/K
    if align=='center': x-=w/2
    if align=='right': x-=w
    if halo and not rotate:
        p.draw_rect(rect(x-.55,y-size*.35,x+w+.55,y+.42),fill=WHITE,color=None,overlay=True)
    p.insert_text(point(x,y),s,fontsize=size,fontname=f,color=col,rotate=rotate)
    if not rotate:
        BBOX.append((p.number,x,y-size*.36,x+w,y+1.0,s))
    return w

def line(p,pts,width=.16,color=BLACK,dash=None):
    if len(pts)<2: return
    s=p.new_shape()
    s.draw_polyline([point(*q) for q in pts])
    s.finish(color=color,width=width*K,dashes=dash,closePath=False)
    s.commit()

def rule(p,x,y,x1,y1,width=.16,color=BLACK,dash=None):
    line(p,[(x,y),(x1,y1)],width,color,dash)

def frame(p,b,width=.18,fill=None,col=BLACK):
    p.draw_rect(rect(*b),color=col if width else None,width=width*K,fill=fill)

def circle(p,x,y,r,stroke=.16,color=BLACK,fill=None):
    p.draw_circle(point(x,y),r*K,width=stroke*K,color=color,fill=fill)

def parts(g,types=None):
    if g is None or g.is_empty: return
    if hasattr(g,'geoms'):
        for q in g.geoms:
            yield from parts(q,types)
    elif types is None or g.geom_type in types:
        yield g

def geom(p,fn,g,w=.18,col=BLACK,fill=None,dash=None):
    for q in parts(g):
        if q.geom_type=='Polygon':
            s=p.new_shape()
            for ring in [q.exterior,*q.interiors]:
                s.draw_polyline([point(*fn(x,y)) for x,y in ring.coords])
            s.finish(color=col if w else None,width=w*K,fill=fill,even_odd=True,dashes=dash,closePath=False)
            s.commit()
        elif q.geom_type in {'LineString','LinearRing'}:
            line(p,[fn(x,y) for x,y in q.coords],w,col,dash)

def arrow(p,a,b,color=BLACK,w=.2,size=2):
    a,b=np.array(a),np.array(b)
    d=b-a
    if np.linalg.norm(d)<.01:return
    d=d/np.linalg.norm(d)
    n=np.array([-d[1],d[0]])
    line(p,[a,b],w,color)
    line(p,[b-d*size+n*size*.42,b,b-d*size-n*size*.42],w,color)

def symbol(p,x,y,a,b=None,r=4.4):
    circle(p,x,y,r,.23,BLACK,WHITE)
    text(p,x,y+(1.0 if b is None else -1),a,7.3,True,align='center')
    if b:
        rule(p,x-r,y+.15,x+r,y+.15,.13)
        text(p,x,y+2.9,b,5.4,align='center')

def leader(p,xy,to,a,b=None):
    line(p,[xy,to],.15,GRAY)
    circle(p,*xy,.53,.12,BLACK,BLACK)
    symbol(p,*to,a,b)

def tag(p,x,y,ident,size=6.5):
    w=FONTS['Bold'].text_length(ident,fontsize=size)/K+2
    frame(p,(x-w/2,y-2.25,x+w/2,y+2.25),.13,WHITE)
    text(p,x,y+.74,ident,size,True,align='center')

def dim(p,a,b,offset,label=None,short=False,vertical=None):
    aa=np.array(a,dtype=float); bb=np.array(b,dtype=float)
    dd=bb-aa; length=np.linalg.norm(dd)
    if length<.02:return
    v=np.array([-dd[1],dd[0]])/length
    u=aa+v*offset; z=bb+v*offset
    for src,end in [(aa,u),(bb,z)]:
        rule(p,*src,*end,.105,GRAY)
        line(p,[end+[-.85,.85],end+[.85,-.85]],.13,BLACK)
    line(p,[u,z],.11,BLACK)
    if label is None:return
    cx,cy=(u+z)/2
    if abs(dd[1])<abs(dd[0]) and vertical is not True:
        text(p,cx,cy-1.15,label,6.7,align='center',halo=True)
    else:
        text(p,cx-1.0,cy+.5,label,6.5,align='right',halo=True)

class View:
    def __init__(self,p,ident,scale,world,paper):
        self.p=p
        self.s=scale
        self.k=1000/scale
        self.win=box(*world)
        self.id=ident
        self.x,self.y=paper
        self.x0,self.y0,self.x1,self.y1=world
        self.r=(self.x,self.y,self.x+(self.x1-self.x0)*self.k,self.y+(self.y1-self.y0)*self.k)
    def xy(self,x,y):
        return self.x+(x-self.x0)*self.k,self.y+(self.y1-y)*self.k
    def geo(self,g,*args,**kwargs):
        if g is not None and not g.is_empty:
            if not g.is_valid:
                NORMALIZED.append((self.id,g.geom_type,list(g.bounds)))
                g=make_valid(g)
            geom(self.p,self.xy,g.intersection(self.win),*args,**kwargs)
    def pt(self,x,y,s,*args,**kw):
        text(self.p,*self.xy(x,y),s,*args,**kw)
    def dim(self,a,b,offset,label=None):
        distance=math.dist(a,b)
        label=label if label is not None else f"{distance*1000:,.0f}"
        dim(self.p,self.xy(*a),self.xy(*b),offset,label)
        SCALE_CHECKS.append(dict(panel=self.id,scale=self.s,metres=distance,paper_mm=math.dist(self.xy(*a),self.xy(*b)),label=label))
    def bar(self,length,x,y):
        dx=self.k*length/2
        for j in range(2):
            frame(self.p,(x+j*dx,y,x+(j+1)*dx,y+1.35),.10,BLACK if j==0 else WHITE)
        for i in range(3):
            v=length/2*i
            text(self.p,x+i*dx,y-1.1,f"{v:g}"+(" m" if i==2 else ""),6.5)
        GEOM.append(dict(panel=self.id,scale=self.s,metres=length,paper_mm=2*dx,bar=[x,y,1.35]))

def view_caption(p,x,y,num,title,scale,xright):
    symbol(p,x+4.2,y-1,num,None,3.8)
    rule(p,x+9,y+1.9,xright,y+1.9,.24,BLACK)
    text(p,x+11,y,title,10.8,True)
    text(p,xright,y,f"1:{scale}",7.5,align='right')

def sheet(doc,id_,name,sc,refcodes,desc):
    p=doc.new_page(width=594*K,height=420*K)
    for n,f in (("Body","malgun.ttf"),("Bold","malgunbd.ttf")):
        p.insert_font(fontname=n,fontfile=f"C:/Windows/Fonts/{f}")
    frame(p,(14,13,580,407),.9)
    rule(p,532,13,532,407,.64)
    x=536
    breaks=(44,78,114,154,192,240,274,307,344,375)
    for y in breaks:
        rule(p,532,y,580,y,.18)
    for y,label in [(20,"PROJECT NO."),(51,"PROJECT TITLE"),(85,"DRAWING TITLE"),(121,"REFERENCES"),
                    (161,"GEOMETRY"),(199,"NOTES"),(247,"REVISION"),(281,"ISSUE"),(314,"PRINT SCALE"),
                    (351,"DATE"),(382,"DRAWING NO.")]:
        text(p,x,y,label,6,col=GRAY)
    text(p,x,34,"WP0 · R10-A",10.5,True)
    text(p,x,63,"다층 상업시설",11,True)
    text(p,x,70,"수직동선 및 접합 연구",7.5)
    for i,s in enumerate(name):
        text(p,x,96+6*i,s,9.4,True)
    for i,s in enumerate(refcodes):
        text(p,x,132+5*i,s,7.2)
    text(p,x,170,"회색·흑색 / 기준 형상",7)
    text(p,x,176,"청록 / 연구 후보",7,col=INK)
    text(p,x,182,"점선 / 투영 또는 미확인",6.9,col=GRAY)
    for i,s in enumerate(desc):
        text(p,x,208+5.7*i,s,6.8)
    text(p,x,260,"A  대표 도면 4장",7.7,True)
    text(p,x,297,"독립 검수용",9,True)
    text(p,x,327,sc,8.8,True)
    text(p,x,335,"A2 · 실제 크기 100%",7.3)
    text(p,x,366,datetime.now().strftime("%Y. %m. %d"),8.3)
    text(p,x,398,id_,17,True)
    return p

