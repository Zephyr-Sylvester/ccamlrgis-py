"""Data source citations. CCAMLR geospatial rules 8 and 9
(geospatial_operations-main/README.md, endorsed by the Scientific
Committee in 2023, SC-CAMLR-42 para 2.30): analyses cite CCAMLR data
layers by name/version/URL (rule 8), and maps cite their data sources and
projection (rule 9). `load.py`'s WFS loaders stash the rule-8 string onto
every layer they return via `.attrs["citation"]`; `plot.basemap()`'s
`attribution=` renders the rule-9 caption.
"""

import datetime

# key -> (human-readable layer name, WFS typeName), one entry per load_*
# function in load.py.
LAYER_INFO = {
    "asds": ("Statistical Areas, Subareas and Divisions", "statistical_areas_6932"),
    "ssrus": ("Small Scale Research Units", "ssrus_6932"),
    "coastline": ("Coastline", "coastline_v1_6932"),
    "rbs": ("Research Blocks", "research_blocks_6932"),
    "ssmus": ("Small Scale Management Units", "ssmus_6932"),
    "mas": ("Management Areas", "omas_6932"),
    "mpas": ("Marine Protected Areas", "mpas_6932"),
    "eezs": ("Exclusive Economic Zones", "eez_6932"),
}

WFS_URL_TEMPLATE = (
    "https://gis.ccamlr.org/geoserver/gis/ows?service=WFS&version=1.0.0"
    "&request=GetFeature&outputFormat=json&typeName=gis:{type_name}"
)


def layer_citation(layer, year=None, version=None):
    """The CCAMLR rule-8 citation string for a loaded layer:
    "CCAMLR. (Year). Geographical data layer: (Layer name). Version
    (Version), URL: (URL)".

    `layer` is a load_* key: one of "asds", "ssrus", "coastline", "rbs",
    "ssmus", "mas", "mpas", "eezs" (case-insensitive).

    `year` defaults to the current year -- the live WFS response carries
    no citation year itself, so this stands in for "year accessed".
    `version` defaults to `year` too, for the same reason: the WFS has no
    exposed dataset-version field to read a real one from. Pass an
    explicit `version=` if a specific published version is known.
    """
    key = layer.lower()
    if key not in LAYER_INFO:
        raise ValueError(f"Unknown layer {layer!r}; choose from {sorted(LAYER_INFO)}")
    name, type_name = LAYER_INFO[key]
    year = year or datetime.date.today().year
    version = version or year
    url = WFS_URL_TEMPLATE.format(type_name=type_name)
    return f"CCAMLR. ({year}). Geographical data layer: {name}. Version {version}, URL: {url}"
