"""Offline end-to-end tests for the map-rendering pipeline.

The generators fetch from the Overpass/IBGE network APIs, which can't run in
CI, so these tests drive the deterministic offline half — element parsing,
boundary stitching, projection and SVG serialization — with synthetic OSM
data, and assert a real, well-formed SVG comes out. Pure-Python + pathlib, so
the same suite passes on Linux, macOS and Windows.
"""
from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import gen_mg_maps as mg
import _compat

ROOT = Path(__file__).resolve().parent.parent


def test_mercator_is_finite():
    x, y = mg.mercator(-21.76, -43.35)
    assert all(v == v and abs(v) < 1e3 for v in (x, y))


def test_classify_way():
    assert mg.classify_way({"tags": {"highway": "primary"}}) == "major_road"
    assert mg.classify_way({"tags": {"highway": "secondary"}}) == "secondary_road"
    assert mg.classify_way({"tags": {"waterway": "river"}}) == "waterway"
    assert mg.classify_way({"tags": {}}) == "other"


def test_stitch_joins_segments():
    a = [(0, 0), (1, 1)]
    b = [(1, 1), (2, 2)]
    assert mg.stitch([a, b]) == [(0, 0), (1, 1), (2, 2)]


def test_parse_elements_splits_types():
    data = {"elements": [
        {"type": "node", "id": 1, "lat": -21.0, "lon": -43.0},
        {"type": "way", "id": 10, "nodes": [1]},
        {"type": "relation", "id": 100, "members": []},
    ]}
    nodes, ways, rels = mg.parse_elements(data)
    assert nodes[1] == (-21.0, -43.0)
    assert len(ways) == 1 and len(rels) == 1


def test_build_boundaries_from_synthetic_relation():
    nodes = {1: (-21.0, -43.0), 2: (-21.0, -42.9),
             3: (-21.1, -42.9), 4: (-21.1, -43.0)}
    ways = [{"id": 10, "nodes": [1, 2, 3, 4, 1]}]
    rels = [{"id": 100, "tags": {"boundary": "administrative", "name": "Box"},
             "members": [{"type": "way", "ref": 10, "role": "outer"}]}]
    polys, names = mg.build_boundaries(rels, ways, nodes)
    assert names == ["Box"]
    assert len(polys[0]) >= 4


def test_render_svg_writes_valid_file():
    boundaries = [[(-21.0, -43.0), (-21.0, -42.9),
                   (-21.1, -42.9), (-21.1, -43.0), (-21.0, -43.0)]]
    classified = {
        "major_road": [[(-21.02, -42.98), (-21.05, -42.95)]],
        "secondary_road": [],
        "residential_road": [],
        "water_area": [],
        "waterway": [[(-21.03, -42.97), (-21.06, -42.94)]],
    }
    mg.render_svg("E2E TEST", "test_e2e_map.svg", boundaries, classified)
    out = _compat.svg_dir() / "test_e2e_map.svg"
    assert out.exists() and out.stat().st_size > 0
    root = ET.fromstring(out.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")
    classes = {el.get("class") for el in root.iter()}
    assert "major-road" in classes
    out.unlink()


def test_svg_dir_is_created_and_under_repo():
    d = _compat.svg_dir()
    assert d.exists() and d.is_dir()
    assert d.parent == ROOT


def test_enable_utf8_stdout_is_safe():
    _compat.enable_utf8_stdout()


def test_all_generators_compile():
    scripts = sorted((ROOT / "scripts").glob("*.py"))
    assert scripts
    res = subprocess.run(
        [sys.executable, "-m", "py_compile", *map(str, scripts)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
