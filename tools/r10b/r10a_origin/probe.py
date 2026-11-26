from build import *
for fl in FF:
 g=load_floor(fl)
 print(fl,[(x['name_ko'],x['program_floor'],tuple(round(n,1) for n in x['poly'].bounds)) for x in g.zones][:9])
for o in objects(floor='2F'):
 if o['kind'] in {'interface','threshold','bridge','guard'}:
  x=P.tris(o);print(o['name'],x.min(axis=(0,1)),x.max(axis=(0,1)))
print('xgrid',XGRID,'ygrid',YGRID)
for o in M.bld:
 if o['name']=='A-FACD_glass' or 'ESCL' in o['name'] or o['kind']=='tube_wall':
  x=M.tris(o); print('GEOM',o['name'],x.min(axis=(0,1)).round(2),x.max(axis=(0,1)).round(2))

