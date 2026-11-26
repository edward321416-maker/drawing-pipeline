from pathlib import Path
import sys
from collections import Counter
import json
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parent
r7=root.with_name('WP0_R7_20261125'); repo=r7/'checkout'
for d in ['engine','src']:
    sys.path.insert(0,str(repo/d))
from t14s.planner import plan_floor
from t14s.source import load_floor, north_angle_deg
from book_views import Model
g=load_floor('2F')
d=plan_floor('2F')
print('floor',g.slab.bounds,g.outline.bounds,north_angle_deg(),g.cores)
print('data',list(vars(g)),'items',Counter(i.layer for i in d.items)); print('meta',list(d.meta))
for r in d.rooms:
    print({k:(v.bounds if hasattr(v,'bounds') else v) for k,v in r.items()})
for layer in ('A-GRID','A-WALL-EXT','A-WALL-PART','A-TUBE','A-GLAZ','A-STAR','A-DOOR','A-FLOOR-OPEN','A-STAR-PROJ'):
    print(layer,[(i.ref,i.pen,i.fill,i.geom.geom_type) for i in d.items if i.layer==layer][:25])
m=Model(r7/'source_geometry',r7/'source_geometry/raw_slices/camera_bounds.json')
print('model kinds',Counter(o['kind'] for o in m.bld),'floors',m.floors)
print('stairs',[(o['name'],o.get('floor'),m.tris(o).min(axis=(0,1)),m.tris(o).max(axis=(0,1))) for o in m.bld if o['kind'] in ('ground','garden','roof') or 'STRS_D' in o['name']][:23])
r8=root.with_name('WP0_R8_20261125')
w=json.loads((r8/'delivery/R8_3D_CLASH.json').read_text(encoding='utf-8-sig'))
for k in ('approved_1F_interface','staircase'):
 val=w[k]; print(k,str(val)[:5500])
m8=json.loads((r8/'_rejected/R8_PROPOSAL_MESHES.json').read_text(encoding='utf-8-sig'))
from collections import defaultdict
cnt=defaultdict(Counter)
for o in m8:
 if o.get('core')=='D' and o.get('group') and not o['group'].startswith('OPTION'):
     cnt[o['group']][o['kind']]+=1
print('r8groups D',dict(cnt))
f=json.loads((r7/'source_geometry/1F_master_current.json').read_text(encoding='utf-8-sig'))
for o in f['objects']:
 if o['name'].startswith('Core_D_'):
    print('MASTER',o['name'],o['props'],'z',min(v[2] for v in o['verts']),max(v[2] for v in o['verts']))

