"""
Generate Paraíso do Morumbi SVG with boundary traced from Google Maps screenshot.
"""
import requests, math, sys, io, time
from _compat import enable_utf8_stdout, svg_dir
enable_utf8_stdout()
_SVG = svg_dir()

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
SVG_WIDTH = 1200
SVG_HEIGHT = 1600
PADDING = 40

def fetch(query, label, retries=3):
    for url in OVERPASS_URLS:
        for attempt in range(retries):
            try:
                server = url.split("//")[1].split("/")[0]
                print(f"  [{label}] {server} attempt {attempt+1}...", flush=True)
                resp = requests.post(url, data={"data": query}, timeout=240)
                if resp.status_code in (429, 504):
                    time.sleep(40*(attempt+1)); continue
                resp.raise_for_status()
                data = resp.json()
                print(f"  [{label}] Got {len(data['elements'])} elements", flush=True)
                return data
            except Exception as e:
                print(f"  [{label}] Error: {e}", flush=True)
                if attempt < retries-1: time.sleep(30*(attempt+1))
        print(f"  [{label}] Failed on {server}, next...", flush=True)
    raise Exception(f"All failed for {label}")

def mercator(lat, lon):
    x = lon * math.pi / 180
    y = math.log(math.tan(math.pi / 4 + lat * math.pi / 360))
    return x, y

# Boundary traced from Google Maps screenshot (red dashed line)
# Clockwise from north
BOUNDARY = [
    (-23.6095, -46.7260), (-23.6098, -46.7248), (-23.6100, -46.7238),
    (-23.6108, -46.7220), (-23.6115, -46.7200), (-23.6122, -46.7185),
    (-23.6135, -46.7170), (-23.6148, -46.7155), (-23.6162, -46.7142),
    (-23.6178, -46.7130), (-23.6190, -46.7120), (-23.6205, -46.7112),
    (-23.6220, -46.7115), (-23.6235, -46.7118), (-23.6250, -46.7125),
    (-23.6262, -46.7132), (-23.6275, -46.7142), (-23.6285, -46.7155),
    (-23.6295, -46.7170), (-23.6302, -46.7185), (-23.6310, -46.7200),
    (-23.6318, -46.7215), (-23.6325, -46.7235), (-23.6330, -46.7252),
    (-23.6335, -46.7270), (-23.6332, -46.7288), (-23.6315, -46.7298),
    (-23.6295, -46.7302), (-23.6270, -46.7300), (-23.6248, -46.7295),
    (-23.6225, -46.7288), (-23.6205, -46.7282), (-23.6185, -46.7280),
    (-23.6165, -46.7285), (-23.6148, -46.7290), (-23.6132, -46.7288),
    (-23.6118, -46.7278), (-23.6108, -46.7270), (-23.6095, -46.7260),
]

print("=== PARAISO DO MORUMBI (Google Maps boundary) ===", flush=True)

all_lats = [p[0] for p in BOUNDARY]
all_lons = [p[1] for p in BOUNDARY]
margin = 0.004
s, w, n, e = min(all_lats)-margin, min(all_lons)-margin, max(all_lats)+margin, max(all_lons)+margin

hw_types = "motorway|trunk|primary|secondary|tertiary|residential|living_street|unclassified"
q = f"""
[out:json][timeout:120];
(
  way["highway"~"^({hw_types})$"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["waterway"~"^(river|stream|canal)$"]({s},{w},{n},{e});
);
out body; >; out skel qt;
"""
data = fetch(q, "roads")
nodes, ways = {}, []
for el in data["elements"]:
    if el["type"] == "node": nodes[el["id"]] = (el["lat"], el["lon"])
    elif el["type"] == "way": ways.append(el)

def classify(way):
    tags = way.get("tags", {})
    hw = tags.get("highway", "")
    if hw in ("motorway","trunk","primary"): return "major_road"
    elif hw in ("secondary","tertiary"): return "secondary_road"
    elif hw in ("residential","living_street","unclassified"): return "residential_road"
    elif tags.get("natural") == "water": return "water_area"
    elif tags.get("waterway") in ("river","stream","canal"): return "waterway"
    return "other"

classified = {"major_road":[],"secondary_road":[],"residential_road":[],"water_area":[],"waterway":[]}
for w in ways:
    cat = classify(w)
    if cat in classified:
        coords = [nodes[nid] for nid in w.get("nodes",[]) if nid in nodes]
        if coords: classified[cat].append(coords)

all_pts = list(BOUNDARY)
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
    .major-road { fill: none; stroke: #d44; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
    .secondary-road { fill: none; stroke: #e88; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
    .residential-road { fill: none; stroke: #bbb; stroke-width: 0.8; stroke-linecap: round; }
    .water-area { fill: #b3d9ff; stroke: #6699cc; stroke-width: 0.5; }
    .waterway { fill: none; stroke: #6699cc; stroke-width: 1.5; stroke-linecap: round; }
    .title { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 32px; font-weight: bold; fill: #222; }
    .subtitle { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 14px; fill: #888; }
</style>""")
bd = path(BOUNDARY) + " Z"
svg.append(f'<defs><clipPath id="boundary-clip"><path d="{bd}"/></clipPath></defs>')
svg.append(f'<path class="boundary" d="{bd}"/>')
clip = ' clip-path="url(#boundary-clip)"'
for cat, cls in [("water_area","water-area"),("waterway","waterway"),("residential_road","residential-road"),("secondary_road","secondary-road"),("major_road","major-road")]:
    if classified[cat]:
        svg.append(f'<g class="{cls}"{clip}>')
        for coords in classified[cat]:
            close = " Z" if cat == "water_area" else ""
            svg.append(f'<path d="{path(coords)}{close}"/>')
        svg.append('</g>')
svg.append(f'<text class="title" x="{SVG_WIDTH/2}" y="35" text-anchor="middle">PARAISO DO MORUMBI</text>')
svg.append(f'<text class="subtitle" x="{SVG_WIDTH/2}" y="55" text-anchor="middle">OpenStreetMap data</text>')
svg.append('</svg>')

with open((_SVG / "paraiso_morumbi_map.svg"), "w", encoding="utf-8") as f:
    f.write("\n".join(svg))
print(f"\nSAVED: paraiso_morumbi_map.svg")
for cat in classified: print(f"  {cat}: {len(classified[cat])}")
