"""Generate UFJF campus map with buildings, paths, and roads."""
import requests, math, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

URLS = ['https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']
SVG_W, SVG_H, PAD = 1200, 1600, 40

def fetch(q, label):
    for url in URLS:
        for a in range(3):
            try:
                r = requests.post(url, data={'data':q}, timeout=240)
                if r.status_code in (429,504): time.sleep(40*(a+1)); continue
                r.raise_for_status(); d=r.json(); print(f'  [{label}] {len(d["elements"])} els',flush=True); return d
            except Exception as e:
                print(f'  [{label}] {e}',flush=True); time.sleep(30*(a+1))
    raise Exception(f'fail {label}')

def mercator(la,lo): return (lo*math.pi/180, math.log(math.tan(math.pi/4+la*math.pi/360)))

print('=== UFJF ===',flush=True)

# Get UFJF campus boundary
q1 = """
[out:json][timeout:120];
(
  rel["name"~"Universidade Federal de Juiz de Fora",i]["amenity"="university"];
  rel["name"~"UFJF",i]["amenity"="university"];
  way["name"~"Universidade Federal de Juiz de Fora",i]["amenity"="university"];
  way["name"~"UFJF",i]["amenity"="university"];
  rel["name"~"Universidade Federal de Juiz de Fora",i]["landuse"];
  way["name"~"Universidade Federal de Juiz de Fora",i]["landuse"];
);
out body; >; out skel qt;
"""
data = fetch(q1, 'boundary')
nodes, ways, rels = {}, [], []
for el in data['elements']:
    if el['type']=='node': nodes[el['id']]=(el['lat'],el['lon'])
    elif el['type']=='way': ways.append(el)
    elif el['type']=='relation': rels.append(el)

print(f'  Nodes:{len(nodes)} Ways:{len(ways)} Rels:{len(rels)}',flush=True)

# Build boundary from relations
wmap = {w['id']:w for w in ways}
boundaries = []
for rel in rels:
    tags = rel.get('tags',{})
    wids = {m['ref'] for m in rel.get('members',[]) if m['type']=='way' and m.get('role') in ('outer','')}
    segs = []
    for wid in wids:
        if wid in wmap:
            coords = [nodes[nid] for nid in wmap[wid].get('nodes',[]) if nid in nodes]
            if coords: segs.append(coords)
    if segs:
        s = list(segs[0]); used={0}; changed=True
        while changed:
            changed=False
            for i,seg in enumerate(segs):
                if i in used or not seg: continue
                if s[-1]==seg[0]: s.extend(seg[1:]); used.add(i); changed=True
                elif s[-1]==seg[-1]: s.extend(reversed(seg[:-1])); used.add(i); changed=True
                elif s[0]==seg[-1]: s=seg[:-1]+s; used.add(i); changed=True
                elif s[0]==seg[0]: s=list(reversed(seg[1:]))+s; used.add(i); changed=True
        boundaries.append(s)
        print(f'  Boundary from rel: {tags.get("name","?")} ({len(s)} pts)',flush=True)

if not boundaries:
    for w in ways:
        tags = w.get('tags',{})
        if tags.get('amenity')=='university' or tags.get('landuse'):
            coords = [nodes[nid] for nid in w.get('nodes',[]) if nid in nodes]
            if coords and len(coords)>10:
                boundaries.append(coords)
                print(f'  Boundary from way: {tags.get("name","?")} ({len(coords)} pts)',flush=True)

if not boundaries:
    print('  No OSM boundary, using approximate campus polygon',flush=True)
    boundaries = [[
        (-21.7715,-43.3755),(-21.7710,-43.3730),(-21.7712,-43.3700),
        (-21.7718,-43.3670),(-21.7730,-43.3648),(-21.7745,-43.3635),
        (-21.7765,-43.3630),(-21.7785,-43.3635),(-21.7800,-43.3648),
        (-21.7810,-43.3665),(-21.7815,-43.3690),(-21.7812,-43.3720),
        (-21.7805,-43.3745),(-21.7790,-43.3760),(-21.7770,-43.3765),
        (-21.7750,-43.3762),(-21.7730,-43.3758),(-21.7715,-43.3755),
    ]]

lats=[p[0] for b in boundaries for p in b]
lons=[p[1] for b in boundaries for p in b]
m=0.003; s,w,n,e=min(lats)-m,min(lons)-m,max(lats)+m,max(lons)+m

# Fetch roads + buildings
hw='motorway|trunk|primary|secondary|tertiary|residential|living_street|unclassified|service|footway|path|cycleway'
q2 = f"""
[out:json][timeout:120];
(
  way["highway"~"^({hw})$"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["waterway"~"^(river|stream|canal)$"]({s},{w},{n},{e});
  way["building"]({s},{w},{n},{e});
);
out body; >; out skel qt;
"""
time.sleep(5)
data2 = fetch(q2, 'roads+buildings')
for el in data2['elements']:
    if el['type']=='node': nodes[el['id']]=(el['lat'],el['lon'])
    elif el['type']=='way': ways.append(el)

def classify(w):
    t=w.get('tags',{});h=t.get('highway','')
    if h in ('motorway','trunk','primary'): return 'major_road'
    elif h in ('secondary','tertiary'): return 'secondary_road'
    elif h in ('residential','living_street','unclassified','service'): return 'residential_road'
    elif h in ('footway','path','cycleway'): return 'footpath'
    elif t.get('building'): return 'building'
    elif t.get('natural')=='water': return 'water_area'
    elif t.get('waterway') in ('river','stream','canal'): return 'waterway'
    return 'other'

cl={'major_road':[],'secondary_road':[],'residential_road':[],'footpath':[],'building':[],'water_area':[],'waterway':[]}
seen=set()
for w in ways:
    wid=w.get('id')
    if wid in seen: continue
    seen.add(wid)
    c=classify(w)
    if c in cl:
        coords=[nodes[nid] for nid in w.get('nodes',[]) if nid in nodes]
        if coords: cl[c].append(coords)

all_pts=[]
for b in boundaries: all_pts.extend(b)
for v in cl.values():
    for coords in v: all_pts.extend(coords)
proj=[mercator(la,lo) for la,lo in all_pts]
xs=[p[0] for p in proj];ys=[p[1] for p in proj]
mnx,mxx=min(xs),max(xs);mny,mxy=min(ys),max(ys)
dw=mxx-mnx or 0.001;dh=mxy-mny or 0.001
drw=SVG_W-2*PAD;drh=SVG_H-2*PAD
scale=min(drw/dw,drh/dh)
ox=PAD+(drw-dw*scale)/2;oy=PAD+(drh-dh*scale)/2

def to_svg(la,lo):
    x,y=mercator(la,lo);return((x-mnx)*scale+ox,(mxy-y)*scale+oy)
def path(coords):
    pts=[to_svg(la,lo) for la,lo in coords]
    return 'M'+' L'.join(f'{p[0]:.2f},{p[1]:.2f}' for p in pts)

svg=[]
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}">')
svg.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="white"/>')
svg.append("""<style>
    .boundary{fill:#f0f0e8;stroke:#333;stroke-width:2;fill-opacity:0.3}
    .building{fill:#d4c4a8;stroke:#b0a080;stroke-width:0.3}
    .major-road{fill:none;stroke:#d44;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}
    .secondary-road{fill:none;stroke:#e88;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
    .residential-road{fill:none;stroke:#999;stroke-width:0.8;stroke-linecap:round}
    .footpath{fill:none;stroke:#aaa;stroke-width:0.4;stroke-dasharray:3,2;stroke-linecap:round}
    .water-area{fill:#b3d9ff;stroke:#6699cc;stroke-width:0.5}
    .waterway{fill:none;stroke:#6699cc;stroke-width:1.5;stroke-linecap:round}
    .title{font-family:'Helvetica Neue',Arial,sans-serif;font-size:32px;font-weight:bold;fill:#222}
    .subtitle{font-family:'Helvetica Neue',Arial,sans-serif;font-size:14px;fill:#888}
</style>""")

clip_d=' '.join(path(b)+' Z' for b in boundaries)
svg.append(f'<defs><clipPath id="boundary-clip"><path d="{clip_d}" clip-rule="nonzero"/></clipPath></defs>')
for b in boundaries: svg.append(f'<path class="boundary" d="{path(b)} Z"/>')
clip=' clip-path="url(#boundary-clip)"'

for cat,cls in [('water_area','water-area'),('waterway','waterway'),('building','building'),
                ('footpath','footpath'),('residential_road','residential-road'),
                ('secondary_road','secondary-road'),('major_road','major-road')]:
    if cl.get(cat):
        svg.append(f'<g class="{cls}"{clip}>')
        for coords in cl[cat]:
            close=' Z' if cat in ('water_area','building') else ''
            svg.append(f'<path d="{path(coords)}{close}"/>')
        svg.append('</g>')

svg.append(f'<text class="title" x="{SVG_W/2}" y="35" text-anchor="middle">UFJF</text>')
svg.append(f'<text class="subtitle" x="{SVG_W/2}" y="55" text-anchor="middle">Universidade Federal de Juiz de Fora</text>')
svg.append('</svg>')

with open('../svg/ufjf_map.svg','w',encoding='utf-8') as f: f.write('\n'.join(svg))
print(f'\nSAVED: ufjf_map.svg')
for c in cl: print(f'  {c}: {len(cl[c])}')
