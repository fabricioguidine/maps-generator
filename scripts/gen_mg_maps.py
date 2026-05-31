"""
Generate maps for MG locations: Minas Gerais state, SP state, Juiz de Fora,
JF neighborhoods, Cataguases, Zona da Mata, etc.
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
        print(f"  [{label}] Failed on {server}, next...", flush=True)
    raise Exception(f"All failed for {label}")

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
    return [nodes[nid] for nid in way.get("nodes",[]) if nid in nodes]

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
        wids = {m["ref"] for m in rel.get("members",[]) if m["type"]=="way" and m.get("role") in ("outer","")}
        segs = [way_to_coords(wmap[wid], nodes) for wid in wids if wid in wmap]
        segs = [s for s in segs if s]
        if segs:
            poly = stitch(segs)
            if poly: polys.append(poly); names.append(tags.get("name","?"))
    return polys, names

def classify_way(way):
    tags = way.get("tags", {})
    hw = tags.get("highway", "")
    if hw in ("motorway","trunk","primary"): return "major_road"
    elif hw in ("secondary","tertiary"): return "secondary_road"
    elif hw in ("residential","living_street","unclassified"): return "residential_road"
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
    dw = max_x-min_x or 0.001; dh = max_y-min_y or 0.001
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
    .boundary { fill: #f5f5f5; stroke: #333; stroke-width: 1.5; fill-opacity: 0.2; }
    .major-road { fill: none; stroke: #d44; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .secondary-road { fill: none; stroke: #e88; stroke-width: 1.0; stroke-linecap: round; stroke-linejoin: round; }
    .residential-road { fill: none; stroke: #bbb; stroke-width: 0.3; stroke-linecap: round; }
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
    filepath = str(_SVG / filename)
    with open(filepath, "w", encoding="utf-8") as f: f.write("\n".join(svg))
    print(f"  SAVED: {filename}")
    for cat in classified:
        if classified[cat]: print(f"    {cat}: {len(classified[cat])}")

def generate_state(name, admin_level, filename, title):
    """Generate state map (major roads only, split into grid)."""
    print(f"\n{'='*50}\n  {title}\n{'='*50}", flush=True)
    q = f"""
[out:json][timeout:300];
rel["name"="{name}"]["admin_level"="{admin_level}"]["boundary"="administrative"];
out body; >; out skel qt;
"""
    data = fetch(q, "boundary")
    bnodes, bways, brels = parse_elements(data)
    boundaries, bnames = build_boundaries(brels, bways, bnodes)
    print(f"  Boundaries: {bnames}", flush=True)
    if not boundaries: print("  ERROR: No boundary!"); return

    all_lats = [p[0] for b in boundaries for p in b]
    all_lons = [p[1] for b in boundaries for p in b]
    m = 0.01
    s, w, n, e = min(all_lats)-m, min(all_lons)-m, max(all_lats)+m, max(all_lons)+m
    mid_lat = (s+n)/2; mid_lon = (w+e)/2

    # States: only major + secondary roads, split into 4 quadrants
    all_nodes = dict(bnodes)
    all_ways = list(bways)
    quads = [("SW",s,w,mid_lat,mid_lon),("SE",s,mid_lon,mid_lat,e),
             ("NW",mid_lat,w,n,mid_lon),("NE",mid_lat,mid_lon,n,e)]

    for qname, qs, qw, qn, qe in quads:
        q = f"""
[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary)$"]({qs},{qw},{qn},{qe});
  way["waterway"="river"]({qs},{qw},{qn},{qe});
);
out body; >; out skel qt;
"""
        d = fetch(q, f"roads_{qname}")
        nn, ww, _ = parse_elements(d)
        all_nodes.update(nn); all_ways.extend(ww)
        time.sleep(8)

    classified = {"major_road":[],"secondary_road":[],"water_area":[],"waterway":[]}
    seen = set()
    for w in all_ways:
        wid = w.get("id")
        if wid in seen: continue
        seen.add(wid)
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, all_nodes)
            if c: classified[cat].append(c)

    render_svg(title, filename, boundaries, classified)

def generate_city(name, filename, title, include_residential=True):
    """Generate city map with full detail."""
    print(f"\n{'='*50}\n  {title}\n{'='*50}", flush=True)
    q = f"""
[out:json][timeout:180];
rel["name"="{name}"]["admin_level"="8"]["boundary"="administrative"];
out body; >; out skel qt;
"""
    data = fetch(q, "boundary")
    bnodes, bways, brels = parse_elements(data)
    boundaries, bnames = build_boundaries(brels, bways, bnodes)
    print(f"  Boundaries: {bnames}", flush=True)
    if not boundaries: print("  ERROR: No boundary!"); return

    all_lats = [p[0] for b in boundaries for p in b]
    all_lons = [p[1] for b in boundaries for p in b]
    m = 0.005
    s, w, n, e = min(all_lats)-m, min(all_lons)-m, max(all_lats)+m, max(all_lons)+m
    mid_lat = (s+n)/2; mid_lon = (w+e)/2

    hw = "motorway|trunk|primary|secondary|tertiary"
    if include_residential: hw += "|residential|living_street|unclassified"

    all_nodes = dict(bnodes); all_ways = list(bways)
    for qname, qs, qw, qn, qe in [("S",s,w,mid_lat,e),("N",mid_lat,w,n,e)]:
        q = f"""
[out:json][timeout:180];
(
  way["highway"~"^({hw})$"]({qs},{qw},{qn},{qe});
  way["natural"="water"]({qs},{qw},{qn},{qe});
  way["waterway"~"^(river|stream|canal)$"]({qs},{qw},{qn},{qe});
);
out body; >; out skel qt;
"""
        d = fetch(q, f"roads_{qname}")
        nn, ww, _ = parse_elements(d)
        all_nodes.update(nn); all_ways.extend(ww)
        time.sleep(8)

    classified = {"major_road":[],"secondary_road":[],"residential_road":[],"water_area":[],"waterway":[]}
    seen = set()
    for w in all_ways:
        wid = w.get("id")
        if wid in seen: continue
        seen.add(wid)
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, all_nodes)
            if c: classified[cat].append(c)

    render_svg(title, filename, boundaries, classified)

def generate_neighborhood(city, neighborhood_names, filename, title, admin_levels="9|10"):
    """Generate neighborhood map. Tries OSM boundaries first, falls back to bbox."""
    print(f"\n{'='*50}\n  {title}\n{'='*50}", flush=True)

    name_filter = "|".join(neighborhood_names)
    q = f"""
[out:json][timeout:120];
area["name"="{city}"]["admin_level"="8"]->.city;
(
  rel["boundary"="administrative"]["admin_level"~"^({admin_levels})$"]["name"~"^({name_filter})$",i](area.city);
  rel["boundary"="administrative"]["name"~"^({name_filter})$",i](area.city);
);
out body; >; out skel qt;
"""
    data = fetch(q, "boundary")
    bnodes, bways, brels = parse_elements(data)
    boundaries, bnames = build_boundaries(brels, bways, bnodes)
    print(f"  Boundaries: {bnames}", flush=True)

    if not boundaries:
        print("  No OSM boundary found, skipping...", flush=True)
        return

    all_lats = [p[0] for b in boundaries for p in b]
    all_lons = [p[1] for b in boundaries for p in b]
    m = 0.003
    s, w, n, e = min(all_lats)-m, min(all_lons)-m, max(all_lats)+m, max(all_lons)+m

    hw = "motorway|trunk|primary|secondary|tertiary|residential|living_street|unclassified"
    q = f"""
[out:json][timeout:120];
(
  way["highway"~"^({hw})$"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["waterway"~"^(river|stream|canal)$"]({s},{w},{n},{e});
);
out body; >; out skel qt;
"""
    data = fetch(q, "roads")
    rnodes, rways, _ = parse_elements(data)
    all_nodes = {**bnodes, **rnodes}

    classified = {"major_road":[],"secondary_road":[],"residential_road":[],"water_area":[],"waterway":[]}
    for w in rways:
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, all_nodes)
            if c: classified[cat].append(c)

    render_svg(title, filename, boundaries, classified)

def generate_mesoregion(state, region_name, filename, title):
    """Generate mesoregion/macroregion map."""
    print(f"\n{'='*50}\n  {title}\n{'='*50}", flush=True)
    # Try mesoregion (admin_level 5 or 6) or named region
    q = f"""
[out:json][timeout:180];
(
  rel["name"~"{region_name}",i]["boundary"="administrative"];
  rel["name"~"{region_name}",i]["type"="boundary"];
);
out body; >; out skel qt;
"""
    data = fetch(q, "boundary")
    bnodes, bways, brels = parse_elements(data)
    boundaries, bnames = build_boundaries(brels, bways, bnodes)
    print(f"  Boundaries: {bnames}", flush=True)

    if not boundaries:
        print("  No boundary found, trying IBGE mesoregion...", flush=True)
        # Try with different tags
        q2 = f"""
[out:json][timeout:180];
rel["name"~"Zona da Mata",i];
out body; >; out skel qt;
"""
        data = fetch(q2, "boundary_v2")
        bnodes, bways, brels = parse_elements(data)
        boundaries, bnames = build_boundaries(brels, bways, bnodes)
        print(f"  Boundaries v2: {bnames}", flush=True)

    if not boundaries:
        print("  ERROR: No boundary found!")
        return

    all_lats = [p[0] for b in boundaries for p in b]
    all_lons = [p[1] for b in boundaries for p in b]
    m = 0.01
    s, w, n, e = min(all_lats)-m, min(all_lons)-m, max(all_lats)+m, max(all_lons)+m
    mid_lat = (s+n)/2; mid_lon = (w+e)/2

    all_nodes = dict(bnodes); all_ways = list(bways)
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
        d = fetch(q, f"roads_{qname}")
        nn, ww, _ = parse_elements(d)
        all_nodes.update(nn); all_ways.extend(ww)
        time.sleep(8)

    classified = {"major_road":[],"secondary_road":[],"water_area":[],"waterway":[]}
    seen = set()
    for w in all_ways:
        wid = w.get("id")
        if wid in seen: continue
        seen.add(wid)
        cat = classify_way(w)
        if cat in classified:
            c = way_to_coords(w, all_nodes)
            if c: classified[cat].append(c)

    render_svg(title, filename, boundaries, classified)

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else [
        "mg", "sp_state", "jf", "cataguases", "zona_da_mata",
        "dom_bosco", "sao_mateus", "vale_ipe", "haidee"
    ]

    for t in targets:
        try:
            if t == "mg":
                generate_state("Minas Gerais", "4", "mg_map.svg", "MINAS GERAIS")
            elif t == "sp_state":
                generate_state("São Paulo", "4", "sp_state_map.svg", "SÃO PAULO (Estado)")
            elif t == "jf":
                generate_city("Juiz de Fora", "jf_map.svg", "JUIZ DE FORA")
            elif t == "cataguases":
                generate_city("Cataguases", "cataguases_map.svg", "CATAGUASES")
            elif t == "zona_da_mata":
                generate_mesoregion("Minas Gerais", "Zona da Mata", "zona_da_mata_map.svg", "ZONA DA MATA — MG")
            elif t == "dom_bosco":
                generate_neighborhood("Juiz de Fora", ["Dom Bosco"], "jf_dom_bosco_map.svg", "DOM BOSCO — JUIZ DE FORA")
            elif t == "sao_mateus":
                generate_neighborhood("Juiz de Fora", ["São Mateus"], "jf_sao_mateus_map.svg", "SÃO MATEUS — JUIZ DE FORA")
            elif t == "vale_ipe":
                generate_neighborhood("Juiz de Fora", ["Vale do Ipê", "Vale do Ipe"], "jf_vale_ipe_map.svg", "VALE DO IPÊ — JUIZ DE FORA")
            elif t == "haidee":
                generate_neighborhood("Cataguases", ["Haidée", "Haidee"], "cataguases_haidee_map.svg", "HAIDÉE — CATAGUASES")
            else:
                print(f"Unknown target: {t}")
        except Exception as e:
            print(f"  FAILED {t}: {e}", flush=True)

        if t != targets[-1]:
            print("  Waiting 12s...", flush=True)
            time.sleep(12)

    print("\n=== ALL DONE ===")
