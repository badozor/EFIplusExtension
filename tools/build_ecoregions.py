"""Build efiplus/data/ecoregions_illies.geojson from the EFI+ ecoregion shapefile.

Source: Ecoregions_Project_WGS84.shp in archive/ECOREG1.rar (EFI+ project).
ArcGIS projection of Ecoregions.shp from Lambert azimuthal equal area to WGS84,
12/12/2008. The non-clipped layer is used: it also covers the sea, so sites near
the coast or in estuaries fall in a polygon. The clipped layer (_Cli2) is not used.

Usage (needs pyshp and shapely, as the GUI):
    python tools/build_ecoregions.py path/to/Ecoregions_Project_WGS84.shp
"""
import json
import sys
from pathlib import Path

import shapefile
import shapely
from shapely.geometry import mapping, shape

OUT = Path(__file__).resolve().parents[1] / "efiplus" / "data" / "ecoregions_illies.geojson"


def main(shp: str) -> None:
    prj = Path(shp).with_suffix(".prj").read_text(encoding="latin-1")
    assert "WGS_1984" in prj and "PROJCS" not in prj, prj
    feats = []
    with shapefile.Reader(shp, encoding="latin-1") as r:
        for rec, shp_ in sorted(zip(r.iterRecords(), r.iterShapes()), key=lambda t: t[0]["AREA_ID"]):
            geom = shapely.set_precision(shape(shp_.__geo_interface__), 1e-5)  # ~1 m
            feats.append({"type": "Feature",
                          "properties": {"AREA_ID": int(rec["AREA_ID"]), "NAME": rec["NAME"],
                                         "FRENCH_NAM": rec["FRENCH_NAM"]},
                          "geometry": mapping(geom)})
    fc = {"type": "FeatureCollection", "name": "ecoregions_illies",
          "source": "EFI+ project, archive/ECOREG1.rar, Ecoregions_Project_WGS84.shp "
                    "(Illies ecoregions, WFD Annex XI)",
          "features": feats}
    OUT.write_text(json.dumps(fc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"{OUT}: {len(feats)} ecoregions, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
