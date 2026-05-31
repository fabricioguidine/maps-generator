# Architecture

`maps-generator` is a set of independent command-line generators that each turn
open geodata into a styled SVG. There is no framework and no shared runtime
state — every script is a self-contained pipeline.

## Layout

```
scripts/
  _compat.py            Cross-platform helpers: enable_utf8_stdout(), svg_dir().
  gen_mg_maps.py        MG/SP states, cities, neighborhoods, mesoregions.
  gen_ufjf.py           UFJF campus (roads, paths, buildings).
  gen_paraiso_v3.py     Paraíso do Morumbi (hand-traced boundary).
  gen_ibge_zona_mata.py Zona da Mata via the IBGE mesoregion boundary.
  generate_maps.py      Boundary-first multi-target generator.
  generate_paraiso.py   Earlier Paraíso variant.
svg/                    Generated output (gitignored, created on demand).
tests/                  Offline e2e suite.
```

## Pipeline (per target)

1. **Fetch** boundary + features from Overpass/IBGE (retry across mirrors, back off on 429/504).
2. **Parse** elements into nodes / ways / relations.
3. **Stitch** boundary way-segments into closed polygons.
4. **Classify** ways (major/secondary/residential road, waterway, water area, building).
5. **Project** lat/lon to Mercator and scale to the SVG viewport.
6. **Serialize** to SVG with a boundary clip-path and per-layer styling.
7. **Save** to `svg/<name>.svg`.

Steps 2–7 are pure and deterministic; only step 1 needs the network.

## Cross-platform strategy

- `_compat.enable_utf8_stdout()` replaces the old
  `sys.stdout = io.TextIOWrapper(...)` hack — it uses `reconfigure()` and is a
  no-op when stdout is captured/redirected, so it works under Windows consoles,
  POSIX shells and pytest alike.
- `_compat.svg_dir()` resolves the output directory from the file location
  (`<repo>/svg`) instead of a cwd-relative `../svg/`, so scripts work no matter
  where they're launched from, and creates it if missing.
- `.gitattributes` normalizes line endings to LF.
- CI runs the offline e2e suite on ubuntu/macos/windows × Python 3.11–3.13.

## Testing

`tests/test_e2e.py` imports the real generator module, exercises the offline
pipeline (parse → stitch → build boundaries → classify → project → render) with
synthetic OSM data, validates the emitted SVG as XML, and byte-compiles every
script so syntax regressions are caught on all three operating systems. The
network half is intentionally not exercised in CI (rate-limited third-party
endpoints).
