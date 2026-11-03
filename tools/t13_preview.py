import json, sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
sys.path.insert(0,"src")
import program_planner as PP
plt.rcParams["font.family"]="Malgun Gothic"
d=json.load(open("tests/fixtures/t13_geom_1F.json",encoding="utf-8"))
I=PP.input_from_dump(d)
var=sys.argv[1]
P=PP.plan_program(var,I)
R=PP.qa(P,I)
print(json.dumps({k:v for k,v in R.items() if k!="area_table"},ensure_ascii=False,indent=1))
print(R["area_table"])
fig,ax=plt.subplots(figsize=(13,13))
cols={"M":"#cde","P":"#dec","S":"#edc","C":"#ffd"}
def draw(g,**kw):
    for p in PP.polys(g):
        x,y=p.exterior.xy; ax.fill(x,y,**kw)
        for h in p.interiors:
            xx,yy=zip(*h.coords); ax.fill(xx,yy,color="white")
for zid,g in P["zones"].items():
    if g.is_empty: continue
    pal={"M01":"#f4a","M02":"#8cf","M03":"#fc6","M04":"#f96","M05":"#9d9","M06":"#ddd","P01":"#cfc","P02":"#9fd","P03":"#af8","P04":"#fe8","S01":"#f88","S02":"#fcb","S03":"#caf","S04":"#ccc","C01":"#fcf","C02":"#cef","C03":"#ffb","C04":"#dde"}
    draw(g,fc=pal[zid],ec="#668",lw=.6,alpha=.85)
    r=g.representative_point(); ax.text(r.x,r.y,zid,fontsize=8,ha="center",weight="bold",color="#224")
for fl in P["flows"]:
    xs,ys=fl["line"].xy; ax.plot(xs,ys,"r--" if fl["kind"]=="service" else "r-",lw=1)
for it in P["furniture"]:
    for g,k in it["parts"]:
        if k=="body":
            for p in PP.polys(g): x,y=p.exterior.xy; ax.fill(x,y,fc="white",ec="#333",lw=.5)
        else:
            if g.geom_type=="LineString": ax.plot(*g.xy,color="#555",lw=.4)
for c in I["cols"]: draw(c,fc="k")
for n,s in I["lifts"].items(): draw(s,fc="none",ec="k",lw=1)
draw(I["capsule"],fc="none",ec="k",lw=1)
draw(I["rooms"],fc="#999",ec="k")
draw(I["walls"],fc="k")
for e in P["entries"]: ax.plot(*e["center"],"ms",ms=6); ax.text(e["center"][0]+.4,e["center"][1]+.4,e["id"][6:12],fontsize=6)
ax.set_aspect("equal"); ax.set_xlim(-2,56); ax.set_ylim(-2,56)
fig.savefig("outputs/T13_work/plan_%s_preview.png"%var,dpi=75)

