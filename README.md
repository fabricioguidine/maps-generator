# maps-generator

Standalone Python scripts that render clean, minimalist **SVG maps** of Brazilian
regions (Minas Gerais, São Paulo, Juiz de Fora and its neighborhoods, Cataguases,
Zona da Mata, the UFJF campus, …) from open data — administrative boundaries and
road/water networks pulled from the **Overpass (OpenStreetMap)** and **IBGE** APIs.

Pure Python, no system dependencies. Runs on Linux, macOS and Windows; the offline
rendering pipeline is tested on all three via CI.

## Setup

Requires Python 3.11+.

**Linux / macOS**

```bash
git clone https://github.com/fabricioguidine/maps-generator.git
cd maps-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/fabricioguidine/maps-generator.git
cd maps-generator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

Each generator runs on its own and writes SVGs into the `svg/` directory at the
repo root (created automatically — no need to run from inside `scripts/`):

```bash
python scripts/gen_mg_maps.py                 # all default MG/SP targets
python scripts/gen_mg_maps.py jf cataguases   # specific targets
python scripts/gen_ufjf.py                     # UFJF campus
python scripts/gen_paraiso_v3.py               # Paraíso do Morumbi
python scripts/gen_ibge_zona_mata.py           # Zona da Mata (IBGE boundary)
```

These hit live Overpass/IBGE endpoints, which are rate-limited — the scripts
retry across mirrors and back off automatically.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The suite is offline and deterministic: it drives element parsing, boundary
stitching, Mercator projection and SVG serialization with synthetic OSM data,
asserts a well-formed SVG is produced, and byte-compiles every generator. No
network is touched, so it runs identically on every OS. See
[ARCHITECTURE.md](ARCHITECTURE.md).

## Output

SVGs use a layered style (boundary clip-path, major/secondary/residential roads,
waterways, water areas, buildings for the campus map), 1200×1600, ready to drop
into print or web.
