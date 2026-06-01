<div align="center">
<img src=".github/assets/banner.svg" alt="maps-generator" width="100%">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.x+-blue.svg)](https://www.python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#)
</div>

> Render Brazilian regional maps to standalone SVG from OpenStreetMap and IBGE data.

A small collection of self-contained Python scripts that fetch administrative boundaries and road/water networks for Brazilian regions, project them with a Web Mercator transform, and draw styled, clipped SVG maps. Covered regions include Minas Gerais and Sao Paulo states, the Zona da Mata mesoregion, the UFJF campus, Juiz de Fora and its neighborhoods, and the Paraiso do Morumbi area.

## Features

- Fetches administrative boundaries and highways/waterways from the OpenStreetMap [Overpass API](https://overpass-api.de), with automatic failover between two Overpass mirrors and retry/backoff on HTTP 429/504.
- Downloads the Zona da Mata mesoregion boundary directly from the IBGE malhas API (mesoregion code 3112) as GeoJSON.
- Stitches multi-segment relation boundaries into closed polygons.
- Projects all coordinates with Web Mercator, then auto-scales and centers them into a fixed 1200x1600 canvas.
- Classifies ways into major roads, secondary roads, residential roads, footpaths (UFJF only), buildings (UFJF only), water areas, and waterways, each with its own SVG style.
- Clips roads and water to the region boundary via an SVG `clipPath`.
- Splits large bounding boxes into halves or quadrants to keep Overpass queries within timeout limits.

## How it works

```mermaid
flowchart LR
    A[Region target] --> B{Boundary source}
    B -->|Overpass relation| C[Fetch admin boundary]
    B -->|IBGE malhas API| D[Download GeoJSON]
    B -->|Hardcoded polygon| E[Built-in coordinates]
    C --> F[Stitch segments into polygon]
    D --> F
    E --> F
    F --> G[Compute bbox + margin]
    G --> H[Fetch roads & water via Overpass]
    H --> I[Classify ways by tag]
    I --> J[Mercator project + scale to 1200x1600]
    J --> K[Render styled SVG, clipped to boundary]
    K --> L[(.svg file)]
```

Each script is independent; there is no shared library. Boundaries come from one of three sources depending on the script: live Overpass administrative relations, the IBGE malhas API, or coordinate polygons hardcoded in the script.

## Requirements

- Python 3.x
- The [`requests`](https://pypi.org/project/requests/) package (the only third-party dependency; everything else is standard library).
- Network access to the Overpass API mirrors and, for the Zona da Mata script, the IBGE malhas API.

```powershell
pip install requests
```

## Usage

The scripts read no flags; the only inputs some accept are positional target names. Run them from inside the `scripts/` directory, because several write their output to a sibling `..\svg\` folder.

```powershell
cd scripts
```

Generate the default set of Minas Gerais / Zona da Mata maps (MG state, SP state, Juiz de Fora, Cataguases, Zona da Mata, JF neighborhoods):

```powershell
python gen_mg_maps.py
```

Generate only specific targets by passing their names:

```powershell
python gen_mg_maps.py mg jf zona_da_mata
```

Available `gen_mg_maps.py` targets: `mg`, `sp_state`, `jf`, `cataguases`, `zona_da_mata`, `dom_bosco`, `sao_mateus`, `vale_ipe`, `haidee`.

Generate the Sao Paulo city / Zona Sul / Morumbi / Paraiso set:

```powershell
python generate_maps.py
python generate_maps.py saopaulo morumbi paraiso
```

Available `generate_maps.py` targets: `saopaulo`, `zonasul`, `morumbi`, `paraiso`, `campinas`.

Generate the standalone single-region maps (no arguments):

```powershell
python gen_ibge_zona_mata.py
python gen_ufjf.py
python gen_paraiso_v3.py
python generate_paraiso.py
```

Note: `gen_mg_maps.py`, `gen_ufjf.py`, and `gen_ibge_zona_mata.py` write into `..\svg\`, so that folder must exist (`mkdir ..\svg`). `generate_maps.py`, `gen_paraiso_v3.py`, and `generate_paraiso.py` write into the current directory.

## Output

Each run writes one or more `.svg` files (1200x1600, white background, OpenStreetMap/IBGE attribution in the subtitle). Examples by script:

| Script | Output file(s) |
|---|---|
| `gen_mg_maps.py` | `mg_map.svg`, `sp_state_map.svg`, `jf_map.svg`, `cataguases_map.svg`, `zona_da_mata_map.svg`, `jf_dom_bosco_map.svg`, `jf_sao_mateus_map.svg`, `jf_vale_ipe_map.svg`, `cataguases_haidee_map.svg` |
| `generate_maps.py` | `saopaulo_map.svg`, `zonasul_map.svg`, `morumbi_map.svg`, `paraiso_morumbi_map.svg`, `campinas_map.svg` |
| `gen_ibge_zona_mata.py` | `zona_da_mata_map.svg` |
| `gen_ufjf.py` | `ufjf_map.svg` |
| `gen_paraiso_v3.py`, `generate_paraiso.py` | `paraiso_morumbi_map.svg` |

Generated SVGs are gitignored (`svg/*.svg`); regenerate them with the scripts.

## Project structure

```
maps-generator/
  scripts/
    gen_mg_maps.py              # MG/SP states, JF, Cataguases, Zona da Mata, JF neighborhoods
    generate_maps.py            # Sao Paulo city, Zona Sul, Morumbi, Paraiso, Campinas
    gen_ibge_zona_mata.py       # Zona da Mata via IBGE malhas API (code 3112)
    gen_ufjf.py                 # UFJF campus with buildings and footpaths
    gen_paraiso_v3.py           # Paraiso do Morumbi, GeoSampa OD-zone polygon
    generate_paraiso.py         # Paraiso do Morumbi, Google Maps-traced polygon
    sp_state_ibge_boundary.json # Vendored IBGE Sao Paulo boundary dataset
  LICENSE
  README.md
```

## License

MIT. See [LICENSE](LICENSE).
