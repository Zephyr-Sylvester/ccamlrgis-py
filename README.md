# ccamlrgis (Python)

Unofficial Python port of the [CCAMLRGIS R package](https://github.com/ccamlr/CCAMLRGIS)
for producing maps and spatial layers in the CAMLR Convention Area. Not a
CCAMLR Secretariat product; authoritative data remains at
https://gis.ccamlr.org/ and https://github.com/ccamlr/data.

Status: early port in progress. See `PROGRESS.md` for what's done and what's
next, and `docs/r_to_python.md` for the R-to-Python function/argument
mapping.

## Development setup

```
mamba env create -f environment.yml
mamba activate ccamlrgis-py
pytest
```
