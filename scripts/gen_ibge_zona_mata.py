"""
Generate Zona da Mata (MG) map using IBGE mesoregion boundary.
IBGE code 3112 = Zona da Mata.
"""
import requests, math, sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
SVG_WIDTH = 1200
SVG_HEIGHT = 1600
PADDING = 40

def fetch_overpass(query, label, retries=3):
    for url in OVERPASS_URLS:
        for attempt in range(retries):
            try:
                server = url.split("//")[1].split("/")[0]
                print(f"  [{label}] {server} attempt {attempt+1}...", flush=True)
                resp = requests.post(url, data={"data": query}, timeout=300)
                if resp.status_code in (429, 504):
                    time.sleep(45*(attempt+1)); continue
                resp.raise_for_status()
                data = resp.json()
                print(f"  [{label}] Got {len(data['elements'])} elements", flush=True)
                return data
            except Exception as e:
                print(f"  [{label}] Error: {e}", flush=True)
                if attempt < retries-1: time.sleep(35*(attempt+1))
        print(f"  [{label}] Failed, next...", flush=True)
    raise Exception(f"All failed for {label}")

def mercator(lat, lon):
    x = lon * math.pi / 180
    y = math.log(math.tan(math.pi / 4 + lat * math.pi / 360))
    return x, y

print("=== ZONA DA MATA - MG ===", flush=True)

# Step 1: Download IBGE boundary
print("  Downloading IBGE mesoregion boundary...", flush=True)
ibge_url = "https://servicodados.ibge.gov.br/api/v3/malhas/mesorregioes/3112?formato=application/vnd.geo+json"
resp = requests.get(ibge_url, timeout=60)
resp.raise_for_status()
geojson = resp.json()

# Extract coordinates (IBGE gives [lon, lat])
raw_coords = geojson["features"][0]["geometry"]["coordinates"][0]
# Simplify: keep every 3rd point to reduce SVG size (3847 -> ~1280 points)
simplified = raw_coords[::3] + [raw_coords[-1]]
boundary = [(lat, lon) for lon, lat in simplified]
print(f"  Boundary: {len(boundary)} points (simplified from {len(raw_coords)})", flush=True)

# Step 2: Compute bbox
all_lats = [p[0] for p in boundary]
all_lons = [p[1] for p in boundary]
m = 0.01
s, w, n, e = min(all_lats)-m, min(all_lons)-m, max(all_lats)+m, max(all_lons)+m
mid_lat = (s+n)/2; mid_lon = (w+e)/2
print(f"  Bbox: {s:.2f},{w:.2f},{n:.2f},{e:.2f}", flush=True)

# Step 3: Fetch roads in 4 quadrants (major + secondary only)
all_nodes, all_ways = {}, []
for qname, qs, qw, qn, qe in [("SW",s,w,mid_lat,mid_lon),("SE",s,mid_lon,mid_lat,e),
                                 ("NW",mid_lat,w,n,mid_lon),("NE",mid_lat,mid_lon,n,e)]:
    q = f"""
[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary)$"]({qs},{qw},{qn},{qe});
  way["waterway"="river"]({qs},{qw},{qn},{qe});
);
out body; >; out skel qt;
"""
    d = fetch_overpass(q, f"roads_{qname}")
    for el in d["elements"]:
        if el["type"] == "node": all_nodes[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "way": all_ways.append(el)
    time.sleep(10)

# Classify
def classify(way):
    tags = way.get("tags", {})
    hw = tags.get("highway", "")
    if hw in ("motorway","trunk","primary"): return "major_road"
    elif hw == "secondary": return "secondary_road"
    elif tags.get("waterway") == "river": return "waterway"
    return "other"

classified = {"major_road":[],"secondary_road":[],"waterway":[]}
seen = set()
for w in all_ways:
    wid = w.get("id")
    if wid in seen: continue
    seen.add(wid)
    cat = classify(w)
    if cat in classified:
        coords = [all_nodes[nid] for nid in w.get("nodes",[]) if nid in all_nodes]
        if coords: classified[cat].append(coords)

# Build SVG
all_pts = list(boundary)
for cl in classified.values():
    for coords in cl: all_pts.extend(coords)

proj = [mercator(lat, lon) for lat, lon in all_pts]
xs = [p[0] for p in proj]; ys = [p[1] for p in proj]
min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
dw = max_x-min_x; dh = max_y-min_y
draw_w = SVG_WIDTH-2*PADDING; draw_h = SVG_HEIGHT-2*PADDING
scale = min(draw_w/dw, draw_h/dh)
ox = PADDING+(draw_w-dw*scale)/2; oy = PADDING+(draw_h-dh*scale)/2

def to_svg(lat, lon):
    x, y = mercator(lat, lon)
    return ((x-min_x)*scale+ox, (max_y-y)*scale+oy)
def path(coords):
    pts = [to_svg(lat, lon) for lat, lon in coords]
    return "M" + " L".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">')
svg.append(f'<rect width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="white"/>')
svg.append("""<style>
    .boundary { fill: #f5f5f5; stroke: #333; stroke-width: 2; fill-opacity: 0.2; }
    .major-road { fill: none; stroke: #d44; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .secondary-road { fill: none; stroke: #e88; stroke-width: 1.0; stroke-linecap: round; stroke-linejoin: round; }
    .waterway { fill: none; stroke: #6699cc; stroke-width: 1.5; stroke-linecap: round; }
    .title { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 32px; font-weight: bold; fill: #222; }
    .subtitle { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 14px; fill: #888; }
</style>""")
bd = path(boundary) + " Z"
svg.append(f'<defs><clipPath id="boundary-clip"><path d="{bd}"/></clipPath></defs>')
svg.append(f'<path class="boundary" d="{bd}"/>')
clip = ' clip-path="url(#boundary-clip)"'
for cat, cls in [("waterway","waterway"),("secondary_road","secondary-road"),("major_road","major-road")]:
    if classified[cat]:
        svg.append(f'<g class="{cls}"{clip}>')
        for coords in classified[cat]:
            svg.append(f'<path d="{path(coords)}"/>')
        svg.append('</g>')
svg.append(f'<text class="title" x="{SVG_WIDTH/2}" y="35" text-anchor="middle">ZONA DA MATA — MG</text>')
svg.append(f'<text class="subtitle" x="{SVG_WIDTH/2}" y="55" text-anchor="middle">IBGE / OpenStreetMap</text>')
svg.append('</svg>')

with open("../svg/zona_da_mata_map.svg", "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print(f"\nSAVED: zona_da_mata_map.svg")
for cat in classified: print(f"  {cat}: {len(classified[cat])}")
