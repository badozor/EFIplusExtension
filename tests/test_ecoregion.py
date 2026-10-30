"""Ecoregion from the coordinates.

The EFI+ layer is not public: the tests build a small invented layer (squares)
with the same attributes. Set EFI_ECOREG_LAYER to also test the real layer.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import shapefile
from efiplus import ecoregion as E, schema as S, validate
from efiplus.examples import example_input1

WGS84_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
# Invented squares (lon_min, lat_min, lon_max, lat_max): not the real ecoregions.
SQUARES = {4: (7.5, 45.5, 10.0, 47.5), 13: (-2.0, 45.5, 7.5, 50.0), 17: (-10.0, 51.5, -6.0, 55.0)}


@pytest.fixture
def layer(tmp_path):
    p = tmp_path / "eco.shp"
    with shapefile.Writer(str(p), shapeType=shapefile.POLYGON) as w:
        w.field("AREA_ID", "N", 4)
        w.field("NAME", "C", 40)
        for i, (x0, y0, x1, y1) in SQUARES.items():
            w.poly([[(x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)]])
            w.record(i, E.ILLIES_NAMES[i])
    p.with_suffix(".prj").write_text(WGS84_PRJ)
    E.set_layer(str(p))
    yield p
    E.set_layer(None)


def test_mapping_tables():
    efi = {v for v in E.ILLIES_TO_EFI.values() if v}
    assert efi == set(S.ECOREGIONS) and len(E.ILLIES_NAMES) == 25
    assert {S.ECOREG_ALIASES[str(k)] for k in E.EFI_TO_ILLIES.values()} == set(S.ECOREGIONS)


def test_no_layer_disables_the_map(monkeypatch, tmp_path):
    monkeypatch.delenv(E.ENV_VAR, raising=False)
    monkeypatch.setattr(E, "LOCAL_DIR", tmp_path / "none")
    E.set_layer(None)
    assert not E.available()
    df = example_input1().astype(object)
    df["Ecoreg"] = ""
    res = validate.check(df)
    assert not res.ok and all(i.level == "error" for i in res.issues if i.column == "Ecoreg")


def test_lookup(layer):
    assert E.status()[0]
    h = E.lookup(8.5, 46.5)
    assert (h.illies_id, h.efi_name, h.outside_km) == (4, "Alps", 0.0)
    assert E.lookup(-8.0, 53.0).efi_name is None                  # 17: not in EFI+
    h = E.lookup(7.55, 46.5)                                       # ~4 km from square 13
    assert h.illies_id == 4 and h.neighbours[0][0] == 13
    h = E.lookup(8.5, 47.55)                                       # ~6 km outside the map
    assert h.illies_id == 4 and 0 < h.outside_km < 10
    assert not E.lookup(20.0, 60.0).found                          # far from every polygon


def _sample(**kw):
    df = example_input1().astype(object)
    df = df[df["Site.code"] == "FR0002"].copy()                    # 2.5 E, 48.2 N: square 13
    for k, v in kw.items():
        df[k] = v
    return df


def _eco_issues(df):
    res = validate.check(df)
    return res, [i for i in res.issues if i.column == "Ecoreg"]


def test_missing_ecoregion_filled(layer):
    res, iss = _eco_issues(_sample(Ecoreg=""))
    assert res.ok and len(iss) == 1 and iss[0].level == "warning"
    assert (res.input1["Ecoreg"] == "Western Plains").all()


def test_missing_ecoregion_outside_efi(layer):
    res, iss = _eco_issues(_sample(Ecoreg="NoData", Longitude=-8.0, Latitude=53.0))
    assert not res.ok and "not covered by EFI+" in iss[0].message


def test_given_ecoregion_disagrees(layer):
    res, iss = _eco_issues(_sample(Ecoreg="Alps"))
    assert res.ok and len(iss) == 1 and iss[0].level == "warning"
    assert res.input1["Ecoreg"].iloc[0] == "Alps"                  # the user's value is kept


def test_given_ecoregion_near_border_accepted(layer):
    res, iss = _eco_issues(_sample(Ecoreg="Alps", Longitude=7.45, Latitude=46.5))
    assert res.ok and not iss


def test_illies_number_and_layer_names_accepted():
    for v in ("13", 13, 13.0, "Western plains"):
        res, _ = _eco_issues(_sample(Ecoreg=v))
        assert res.ok and (res.input1["Ecoreg"] == "Western Plains").all(), v
    res, _ = _eco_issues(_sample(Ecoreg="17"))                     # Ireland: not an EFI+ ecoregion
    assert not res.ok


def test_missing_coordinates_and_ecoregion(layer):
    res, iss = _eco_issues(_sample(Ecoreg="", Longitude=-999))
    assert not res.ok and any(i.level == "error" for i in iss)


@pytest.mark.skipif(not os.environ.get(E.ENV_VAR), reason="EFI_ECOREG_LAYER not set (EFI+ layer not public)")
def test_real_layer_examples():
    E.set_layer(None)
    for code, g in example_input1().groupby("Site.code"):
        r = g.iloc[0]
        assert E.lookup(r.Longitude, r.Latitude).efi_name == r.Ecoreg, code
    assert E.lookup(-6.26, 53.35).illies_id == 17
