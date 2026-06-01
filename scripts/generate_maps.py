"""
Generate all SVG maps with correct road coverage.
Fetches boundaries first, computes bbox from them, then fetches roads.
"""
import requests, math, sys, io, time, json
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
                    wait = 40 * (attempt + 1)
                    print(f"  [{label}] HTTP {resp.status_code}, waiting {wait}s...", flush=True)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                print(f"  [{label}] Got {len(data['elements'])} elements", flush=True)
                return data
            except Exception as e:
                print(f"  [{label}] Error: {e}", flush=True)
                if attempt < retries - 1:
                    time.sleep(30 * (attempt + 1))
        print(f"  [{label}] Failed on {server}, trying next...", flush=True)
    raise Exception(f"All servers failed for {label}")

def mercator(lat, lon):
    x = lon * math.pi / 180
    y = math.log(math.tan(math.pi / 4 + lat * math.pi / 360))
    return x, y

def parse_elements(data):
    nodes, ways, rels = {}, [], []
    for el in data["elements"]:
        if el["type"] == "node": nodes[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "way": ways.append(el)
        elif el["type"] == "relation": rels.append(el)
    return nodes, ways, rels

def way_to_coords(way, nodes):
    return [nodes[nid] for nid in way.get("nodes", []) if nid in nodes]

def stitch(segments):
    if not segments: return []
    s = list(segments[0]); used = {0}; changed = True
    while changed:
        changed = False
        for i, seg in enumerate(segments):
            if i in used or not seg: continue
            if s[-1] == seg[0]: s.extend(seg[1:]); used.add(i); changed = True
            elif s[-1] == seg[-1]: s.extend(reversed(seg[:-1])); used.add(i); changed = True
            elif s[0] == seg[-1]: s = seg[:-1] + s; used.add(i); changed = True
            elif s[0] == seg[0]: s = list(reversed(seg[1:])) + s; used.add(i); changed = True
    return s

def build_boundaries(rels, ways, nodes):
    wmap = {w["id"]: w for w in ways}
    polys, names = [], []
    for rel in rels:
        tags = rel.get("tags", {})
        if tags.get("boundary") != "administrative": continue
        wids = {m["ref"] for m in rel.get("members", []) if m["type"] == "way" and m.get("role") in ("outer", "")}
        segs = [way_to_coords(wmap[wid], nodes) for wid in wids if wid in wmap]
        segs = [s for s in segs if s]
        if segs:
            poly = stitch(segs)
            if poly: polys.append(poly); names.append(tags.get("name", "?"))
    return polys, names

def bbox_from_boundaries(boundaries, margin=0.01):
    """Compute bbox from boundary polygons with margin."""
    all_lats = [p[0] for b in boundaries for p in b]
    all_lons = [p[1] for b in boundaries for p in b]
    return (min(all_lats)-margin, min(all_lons)-margin, max(all_lats)+margin, max(all_lons)+margin)

def classify_way(way):
    tags = way.get("tags", {})
    hw = tags.get("highway", "")
    if hw in ("motorway","trunk","primary"): return "major_road"
    elif hw in ("secondary","tertiary"): return "secondary_road"
    elif hw == "residential": return "residential_road"
    elif tags.get("natural") == "water": return "water_area"
    elif tags.get("waterway") in ("river","stream","canal"): return "waterway"
    return "other"

def render_svg(title, filename, boundaries, classified):
    all_pts = []
    for cl in classified.values():
        for coords in cl: all_pts.extend(coords)
    for b in boundaries: all_pts.extend(b)
    if not all_pts: print(f"  ERROR: No data for {title}!"); return

    proj = [mercator(lat, lon) for lat, lon in all_pts]
    xs = [p[0] for p in proj]; ys = [p[1] for p in proj]
    min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
    dw = max_x - min_x or 0.001; dh = max_y - min_y or 0.001
    draw_w = SVG_WIDTH - 2*PADDING; draw_h = SVG_HEIGHT - 2*PADDING
    scale = min(draw_w/dw, draw_h/dh)
    ox = PADDING + (draw_w - dw*scale)/2; oy = PADDING + (draw_h - dh*scale)/2

    def to_svg(lat, lon):
        x, y = mercator(lat, lon)
        return ((x-min_x)*scale+ox, (max_y-y)*scale+oy)
    def path(coords):
        pts = [to_svg(lat, lon) for lat, lon in coords]
        if not pts: return ""
        return "M" + " L".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts)

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">')
    svg.append(f'<rect width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="white"/>')
    svg.append("""<style>
    .boundary { fill: #f5f5f5; stroke: #333; stroke-width: 1.5; fill-opacity: 0.2; }
    .major-road { fill: none; stroke: #d44; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .secondary-road { fill: none; stroke: #e88; stroke-width: 1.0; stroke-linecap: round; stroke-linejoin: round; }
    .residential-road { fill: none; stroke: #ccc; stroke-width: 0.4; stroke-linecap: round; }
    .water-area { fill: #b3d9ff; stroke: #6699cc; stroke-width: 0.5; }
    .waterway { fill: none; stroke: #6699cc; stroke-width: 1.2; stroke-linecap: round; }
    .title { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 32px; font-weight: bold; fill: #222; }
    .subtitle { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 14px; fill: #888; }
</style>""")
    if boundaries:
        clip_d = " ".join(path(b) + " Z" for b in boundaries)
        svg.append(f'<defs><clipPath id="boundary-clip"><path d="{clip_d}" clip-rule="nonzero"/></clipPath></defs>')
        for b in boundaries: svg.append(f'<path class="boundary" d="{path(b)} Z"/>')
    clip = ' clip-path="url(#boundary-clip)"' if boundaries else ''
    for cat, cls in [("water_area","water-area"),("waterway","waterway"),("residential_road","residential-road"),("secondary_road","secondary-road"),("major_road","major-road")]:
        if classified.get(cat):
            svg.append(f'<g class="{cls}"{clip}>')
            for coords in classified[cat]:
                close = " Z" if cat == "water_area" else ""
                svg.append(f'<path d="{path(coords)}{close}"/>')
            svg.append('</g>')
    svg.append(f'<text class="title" x="{SVG_WIDTH/2}" y="35" text-anchor="middle">{title}</text>')
    svg.append(f'<text class="subtitle" x="{SVG_WIDTH/2}" y="55" text-anchor="middle">OpenStreetMap data</text>')
    svg.append('</svg>')
    with open(filename, "w", encoding="utf-8") as f: f.write("\n".join(svg))
    print(f"  SAVED: {filename}")
    for cat in ["major_road","secondary_road","residential_road","water_area","waterway"]:
        if classified.get(cat): print(f"    {cat}: {len(classified[cat])}")

def fetch_roads_chunked(bbox, label, include_residential=False):
    """Fetch roads in bbox, splitting N-S if needed."""
    s, w, n, e = bbox
    mid = (s + n) / 2
    halves = [(s, w, mid, e, "south"), (mid, w, n, e, "north")]

    all_nodes, all_ways = {}, []
    hw_filter = "motorway|trunk|primary|secondary|tertiary"
    if include_residential:
        hw_filter += "|residential"

    for bs, bw, bn, be, half in halves:
        q = f"""
[out:json][timeout:180];
(
  way["highway"~"^({hw_filter})$"]({bs},{bw},{bn},{be});
  way["natural"="water"]({bs},{bw},{bn},{be});
  way["waterway"~"^(river|stream|canal)$"]({bs},{bw},{bn},{be});
);
out body; >; out skel qt;
"""
        data = fetch(q, f"{label}_{half}")
        n2, w2, _ = parse_elements(data)
        all_nodes.update(n2)
        all_ways.extend(w2)
        time.sleep(8)

    return all_nodes, all_ways

def generate_map(title, filename, boundary_query, include_residential=False):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}", flush=True)

    # Step 1: Fetch boundaries
    data = fetch(boundary_query, "boundaries")
    bnodes, bways, brels = parse_elements(data)
    boundaries, bnames = build_boundaries(brels, bways, bnodes)
    print(f"  Boundaries: {bnames}", flush=True)

    if not boundaries:
        print("  ERROR: No boundaries found!")
        return

    # Step 2: Compute bbox from actual boundaries
    bbox = bbox_from_boundaries(boundaries, margin=0.005)
    print(f"  Computed bbox: {bbox}", flush=True)

    # Step 3: Fetch roads using correct bbox
    time.sleep(10)
    rnodes, rways = fetch_roads_chunked(bbox, "roads", include_residential)

    # Merge nodes
    all_nodes = {**bnodes, **rnodes}

    # Classify
    classified = {"major_road":[],"secondary_road":[],"residential_road":[],"water_area":[],"waterway":[]}
    for w in rways:
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, all_nodes)
            if c: classified[cat].append(c)

    render_svg(title, filename, boundaries, classified)


# ============================================================
# PARAÍSO DO MORUMBI - use convex hull from research
# ============================================================
def gen_paraiso():
    print(f"\n{'='*50}")
    print(f"  PARAÍSO DO MORUMBI")
    print(f"{'='*50}", flush=True)

    # Boundary from research (convex hull of all streets)
    boundary_coords = [
        (-23.6182940, -46.7253122),
        (-23.6190118, -46.7228308),
        (-23.6192136, -46.7209820),
        (-23.6253681, -46.7198287),
        (-23.6253342, -46.7180403),
        (-23.6265138, -46.7235362),
        (-23.6250787, -46.7263790),
        (-23.6249205, -46.7265294),
        (-23.6248373, -46.7265768),
        (-23.6247509, -46.7266333),
        (-23.6246179, -46.7266424),
        (-23.6244806, -46.7266385),
        (-23.6241427, -46.7265889),
        (-23.6238709, -46.7265407),
        (-23.6182940, -46.7253122),
    ]
    boundaries = [boundary_coords]
    bbox = bbox_from_boundaries(boundaries, margin=0.003)
    print(f"  Bbox: {bbox}", flush=True)

    # Fetch roads
    s, w, n, e = bbox
    q = f"""
[out:json][timeout:120];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential)$"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["waterway"~"^(river|stream|canal)$"]({s},{w},{n},{e});
);
out body; >; out skel qt;
"""
    data = fetch(q, "paraiso_roads")
    nodes, ways, _ = parse_elements(data)

    classified = {"major_road":[],"secondary_road":[],"residential_road":[],"water_area":[],"waterway":[]}
    for w in ways:
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, nodes)
            if c: classified[cat].append(c)

    render_svg("PARAÍSO DO MORUMBI", "paraiso_morumbi_map.svg", boundaries, classified)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["saopaulo", "zonasul", "morumbi", "paraiso"]

    ZONA_SUL_DISTRICTS = [
        "Santo Amaro", "Campo Belo", "Campo Grande", "Cidade Ademar",
        "Jabaquara", "Pedreira", "Saúde", "Cursino", "Sacomã",
        "Cidade Dutra", "Grajaú", "Jardim Ângela", "Marsilac",
        "Parelheiros", "Campo Limpo", "Jardim São Luís", "Socorro",
        "Capão Redondo", "Vila Andrade", "Moema", "Ipiranga", "Vila Mariana"
    ]

    MORUMBI_DISTRICTS = [
        "Morumbi", "Vila Andrade", "Vila Sônia", "Butantã",
        "Campo Limpo", "Jardim São Luís", "Santo Amaro", "Itaim Bibi"
    ]

    for target in targets:
        if target == "saopaulo":
            q = """
[out:json][timeout:180];
rel["name"="São Paulo"]["admin_level"="8"]["boundary"="administrative"];
out body; >; out skel qt;
"""
            generate_map("SÃO PAULO", "saopaulo_map.svg", q)

        elif target == "zonasul":
            nf = "|".join(ZONA_SUL_DISTRICTS)
            q = f"""
[out:json][timeout:180];
area["name"="São Paulo"]["admin_level"="8"]->.sp;
rel["boundary"="administrative"]["admin_level"="9"]["name"~"^({nf})$"](area.sp);
out body; >; out skel qt;
"""
            generate_map("ZONA SUL — SÃO PAULO", "zonasul_map.svg", q)

        elif target == "morumbi":
            nf = "|".join(MORUMBI_DISTRICTS)
            q = f"""
[out:json][timeout:180];
area["name"="São Paulo"]["admin_level"="8"]->.sp;
rel["boundary"="administrative"]["admin_level"="9"]["name"~"^({nf})$"](area.sp);
out body; >; out skel qt;
"""
            generate_map("REGIÃO DO MORUMBI — SÃO PAULO", "morumbi_map.svg", q, include_residential=True)

        elif target == "paraiso":
            gen_paraiso()

        elif target == "campinas":
            q = """
[out:json][timeout:180];
rel["name"="Campinas"]["admin_level"="8"]["boundary"="administrative"];
out body; >; out skel qt;
"""
            generate_map("CAMPINAS", "campinas_map.svg", q)

        else:
            print(f"Unknown: {target}")

        if target != targets[-1]:
            print("  Waiting 15s...", flush=True)
            time.sleep(15)
