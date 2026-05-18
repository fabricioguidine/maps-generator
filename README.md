# maps-generator

Python scripts that render Brazilian regional maps to SVG. Each script in `scripts/` produces one or more files in `svg/` (gitignored — regenerate with the scripts).

## Scripts

| Script | Output |
|---|---|
| `gen_mg_maps.py` | Minas Gerais state and sub-regions |
| `gen_ibge_zona_mata.py` | IBGE-defined Zona da Mata mesoregion |
| `gen_ufjf.py` | UFJF campus / Juiz de Fora context |
| `gen_paraiso_v3.py`, `generate_paraiso.py` | Paraíso (neighborhood / locality) |
| `generate_maps.py` | Aggregate driver for the larger maps |

`sp_state_ibge_boundary.json` is a vendored IBGE boundary used by the São Paulo state map.

## Run

```powershell
python scripts\generate_maps.py
```

Outputs land in `svg/`. Some files are large (the MG state map is ~70 MB) because the IBGE polygon detail is preserved.
