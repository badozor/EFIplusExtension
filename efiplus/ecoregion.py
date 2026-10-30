"""Ecoregion of a site from its coordinates (Illies ecoregions, WFD Annex XI).

No map is shipped with the GUI. The user gives a local polygon layer of the
Illies ecoregions (ESRI shapefile .shp or GeoJSON), for example the layer
Ecoregions_Project_WGS84.shp of the EFI+ project (ECOREG1), whose names are
those of the "SIG table" quoted in efiminus.R (prepRegEco).

The layer is searched in this order: path given in the GUI, environment
variable EFI_ECOREG_LAYER, first .shp/.geojson file in the folder local/ecoregions/
of the GUI (ignored by git). Without a layer the function is disabled and the
ecoregion must be typed, as before.

Layer requirements: polygons, one attribute with the Illies number 1-25
(AREA_ID, ILLIES_ID or ILLIES), optional name (NAME). The coordinate system is
read from the .prj file (WGS84 assumed when there is none).

Method: point in polygon. Distances are computed in ETRS89-LAEA (EPSG:3035).
- A point outside every polygon gets the nearest ecoregion if it is closer
  than ``max_dist_km`` (default 10 km); otherwise no ecoregion.
- ``near_km`` (default 5 km) flags sites close to another ecoregion.
  Both defaults are choices of this GUI, not values of the EFI+ manual.

efitools only knows 16 of the 25 Illies ecoregions (see ILLIES_TO_EFI).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LOCAL_DIR = Path(__file__).resolve().parent.parent / "local" / "ecoregions"
ENV_VAR = "EFI_ECOREG_LAYER"
ID_FIELDS = ("AREA_ID", "ILLIES_ID", "ILLIES", "illies_id")
NAME_FIELDS = ("NAME", "name")

# Illies number -> name expected by efitools (schema.ECOREGIONS); None = not covered by EFI+.
ILLIES_TO_EFI = {
    1: "Iberian Peninsula",       # Ibero-Macaronesian region
    2: "Pyrenees",
    3: "Italy",                   # Italy and Corsica
    4: "Alps",
    5: None,                      # Dinaric western Balkan
    6: None,                      # Hellenic western Balkan
    7: None,                      # Eastern Balkan
    8: "Western Highlands",
    9: "Central Highlands",
    10: "The Carpathians",
    11: "Hungarian Lowlands",
    12: "Pontic Province",
    13: "Western Plains",
    14: "Central Plains",
    15: "Baltic Province",
    16: "Eastern Plains",
    17: None,                     # Ireland and Northern Ireland
    18: "Great Britain",          # England
    19: None,                     # Iceland
    20: "Borealic Uplands",
    21: None,                     # Tundra
    22: "Fenno-Scandian Shield",
    23: None,                     # Taiga
    24: None,                     # The Caucasus
    25: None,                     # Caspic depression
}
EFI_TO_ILLIES = {v: k for k, v in ILLIES_TO_EFI.items() if v}
# Names of the WFD Annex XI, used when the layer has no name attribute.
ILLIES_NAMES = {
    1: "Iberic-Macaronesian region", 2: "Pyrenees", 3: "Italy, Corsica and Malta", 4: "Alps",
    5: "Dinaric western Balkan", 6: "Hellenic western Balkan", 7: "Eastern Balkan",
    8: "Western highlands", 9: "Central highlands", 10: "The Carpathians", 11: "Hungarian lowlands",
    12: "Pontic province", 13: "Western plains", 14: "Central plains", 15: "Baltic province",
    16: "Eastern plains", 17: "Ireland and Northern Ireland", 18: "Great Britain", 19: "Iceland",
    20: "Borealic uplands", 21: "Tundra", 22: "Fenno-Scandian shield", 23: "Taiga",
    24: "The Caucasus", 25: "Caspic depression",
}

_user_path: str | None = None


@dataclass(frozen=True)
class Hit:
    illies_id: int | None      # Illies number (1-25), None if no ecoregion found
    illies_name: str           # name in the layer
    efi_name: str | None       # name expected by efitools, None if not covered by EFI+
    outside_km: float          # distance to the polygon (0 if the point is inside)
    neighbours: tuple          # ((illies_id, distance_km), ...) of other ecoregions within near_km

    @property
    def found(self) -> bool:
        return self.illies_id is not None

    def label(self) -> str:
        return f"Illies {self.illies_id} '{self.illies_name}'" if self.found else "no ecoregion"


def set_layer(path: str | None) -> None:
    """Path chosen in the GUI (empty = automatic search)."""
    global _user_path
    _user_path = (path or "").strip() or None


def find_layer(user_path: str | None = None) -> Path | None:
    for cand in (user_path or _user_path, os.environ.get(ENV_VAR)):
        if cand and Path(cand).expanduser().is_file():
            return Path(cand).expanduser().resolve()
    if LOCAL_DIR.is_dir():
        for pat in ("*.shp", "*.geojson", "*.json"):
            found = sorted(LOCAL_DIR.glob(pat))
            if found:
                return found[0].resolve()
    return None


def libs_ok() -> bool:
    try:
        import pyproj  # noqa: F401
        import shapefile  # noqa: F401
        import shapely  # noqa: F401
    except ImportError:
        return False
    return True


def status(user_path: str | None = None) -> tuple[bool, str]:
    """(usable, message) for the GUI."""
    if not libs_ok():
        return False, "Python packages shapely, pyproj and pyshp are missing."
    p = find_layer(user_path)
    if p is None:
        return False, "No ecoregion layer: the ecoregion must be typed."
    try:
        ids = _load(str(p), p.stat().st_mtime)[0]
    except Exception as e:  # noqa: BLE001
        return False, f"The ecoregion layer cannot be read: {e}"
    return True, f"{p.name}: {len(set(ids))} ecoregions."


def available() -> bool:
    return status()[0]


def _read_features(path: Path):
    """Yield (properties, geojson geometry) and return the CRS WKT (None = WGS84)."""
    if path.suffix.lower() == ".shp":
        import shapefile
        prj = path.with_suffix(".prj")
        wkt = prj.read_text(encoding="latin-1") if prj.is_file() else None
        with shapefile.Reader(str(path), encoding="latin-1") as r:
            feats = [(rec.as_dict(), shp.__geo_interface__) for rec, shp in zip(r.iterRecords(), r.iterShapes())]
        return feats, wkt
    fc = json.loads(path.read_text(encoding="utf-8"))
    return [(f.get("properties") or {}, f["geometry"]) for f in fc["features"]], None


@lru_cache(maxsize=2)
def _load(path: str, mtime: float):
    import numpy as np
    import pyproj
    import shapely
    from shapely.geometry import shape

    feats, wkt = _read_features(Path(path))
    src = pyproj.CRS.from_wkt(wkt) if wkt else pyproj.CRS.from_epsg(4326)
    to_laea = pyproj.Transformer.from_crs(src, "EPSG:3035", always_xy=True).transform
    from_wgs = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True).transform

    def project(xy):
        return np.column_stack(to_laea(xy[:, 0], xy[:, 1]))

    ids, names, geoms = [], {}, []
    for props, geom in feats:
        key = next((k for k in ID_FIELDS if k in props), None)
        if key is None:
            raise ValueError(f"no Illies number attribute ({', '.join(ID_FIELDS)})")
        i = int(props[key])
        if i not in ILLIES_TO_EFI:
            raise ValueError(f"Illies number {i} not in 1-25")
        nk = next((k for k in NAME_FIELDS if k in props), None)
        ids.append(i)
        names[i] = str(props[nk]) if nk else ILLIES_NAMES[i]
        geoms.append(shapely.make_valid(shapely.transform(shape(geom), project)))
    if not geoms:
        raise ValueError("empty layer")
    shapely.prepare(geoms)
    return ids, names, geoms, shapely.STRtree(geoms), from_wgs


def _layer():
    p = find_layer()
    if p is None:
        raise RuntimeError("no ecoregion layer")
    return _load(str(p), p.stat().st_mtime)


def lookup(lon: float, lat: float, near_km: float = 5.0, max_dist_km: float = 10.0) -> Hit:
    """Ecoregion of one point given in decimal degrees WGS84."""
    import shapely

    ids, names, geoms, tree, from_wgs = _layer()
    pt = shapely.Point(*from_wgs(float(lon), float(lat)))
    inside = tree.query(pt, predicate="intersects")
    if len(inside):
        k, dist = int(inside[0]), 0.0
    else:
        k = int(tree.query_nearest(pt)[0])
        dist = geoms[k].distance(pt) / 1000
        if dist > max_dist_km:
            return Hit(None, "", None, round(dist, 1), ())
    i = ids[k]
    near = {}
    for j in tree.query(pt, predicate="dwithin", distance=near_km * 1000):
        n = ids[int(j)]
        if n != i:
            d = round(geoms[int(j)].distance(pt) / 1000, 1)
            near[n] = min(d, near.get(n, d))
    return Hit(i, names[i], ILLIES_TO_EFI.get(i), round(dist, 1),
               tuple(sorted(near.items(), key=lambda t: t[1])))


def illies_name(illies_id: int) -> str:
    try:
        return _layer()[1].get(illies_id, ILLIES_NAMES.get(illies_id, ""))
    except RuntimeError:
        return ILLIES_NAMES.get(illies_id, "")
