"""Small synthetic dataset (5 samples) used for the demo and the tests.

The values are invented to exercise the engine (salmonid, cyprinid,
Mediterranean, boat sampling, low catch). They do not describe real sites.
"""
import pandas as pd

from . import schema as S

_SITES = {
    "CH0001": dict(Day=12, Month=9, Year=2007, Longitude=7.9, Latitude=46.7, slope=8.5, tjul=16.5, tjan=-1.5,
                   fp="No", ws="Nival", geo="Sinuous", dist=12, area=45, sed="Gravel/Pebble/Cobble",
                   eco="Alps", eft="T.1", medit=0, fished=600, method="Wading", loc="Main channel",
                   sp=[("Salmo trutta fario", 85, 60, 25), ("Cottus gobio", 40, 40, 0), ("Phoxinus phoxinus", 22, 22, 0)]),
    "FR0002": dict(Day=3, Month=10, Year=2008, Longitude=2.5, Latitude=48.2, slope=0.8, tjul=19.5, tjan=3.2,
                   fp="Yes", ws="Pluvial", geo="Meand regular", dist=140, area=2100, sed="Sand",
                   eco="Western Plains", eft="T.15", medit=0, fished=3500, method="Boat", loc="Main channel",
                   sp=[("Rutilus rutilus", 120, 110, 10), ("Abramis brama", 15, 5, 10), ("Perca fluviatilis", 30, 25, 5),
                       ("Esox lucius", 4, 1, 3), ("Gobio gobio", 60, 60, 0), ("Barbus barbus", 8, 3, 5),
                       ("Chondrostoma nasus", 12, 6, 6), ("Anguilla anguilla", 3, 0, 3)]),
    "DE0003": dict(Day=20, Month=8, Year=2006, Longitude=10.4, Latitude=50.1, slope=3.1, tjul=17.8, tjan=-0.8,
                   fp="Yes", ws="Pluvial", geo="Meand tortous", dist=35, area=310, sed="Gravel/Pebble/Cobble",
                   eco="Central Highlands", eft="T.3", medit=0, fished=1200, method="Wading", loc="Main channel",
                   sp=[("Salmo trutta fario", 30, 22, 8), ("Thymallus thymallus", 12, 7, 5), ("Cottus gobio", 55, 55, 0),
                       ("Barbatula barbatula", 40, 40, 0), ("Alburnoides bipunctatus", 18, 18, 0), ("Gobio gobio", 25, 25, 0)]),
    "ES0004": dict(Day=15, Month=9, Year=2008, Longitude=-4.2, Latitude=40.3, slope=2.0, tjul=24.5, tjan=5.5,
                   fp="No", ws="Pluvial", geo="Braided", dist=60, area=800, sed="Gravel/Pebble/Cobble",
                   eco="Iberian Peninsula", eft="T.15", medit=1, fished=900, method="Wading", loc="Mixed",
                   sp=[("Barbus barbus", 14, 8, 6), ("Gobio gobio", 9, 9, 0), ("Anguilla anguilla", 2, 0, 2)]),
    "PL0005": dict(Day=1, Month=7, Year=2008, Longitude=19.8, Latitude=52.3, slope=0.5, tjul=18.6, tjan=-3.0,
                   fp="Yes", ws="Pluvial", geo="Naturally constraint no mob", dist=80, area=950, sed="Sand",
                   eco="Central Plains", eft="T.6", medit=0, fished=1500, method="Wading", loc="Main channel",
                   sp=[("Rutilus rutilus", 10, 10, 0), ("Perca fluviatilis", 6, 6, 0), ("Esox lucius", 2, 1, 1)]),
}


def example_input1() -> pd.DataFrame:
    rows = []
    for code, d in _SITES.items():
        for sp, tot, below, over in d["sp"]:
            rows.append({
                "Site.code": code, "Day": d["Day"], "Month": d["Month"], "Year": d["Year"],
                "Longitude": d["Longitude"], "Latitude": d["Latitude"], "Actual.river.slope": d["slope"],
                "Temp.jul": d["tjul"], "Temp.jan": d["tjan"], "Floodplain.site": d["fp"],
                "Water.source.type": d["ws"], "Geomorph.river.type": d["geo"], "Distance.from.source": d["dist"],
                "Area.ctch": d["area"], "Natural.sediment": d["sed"], "Ecoreg": d["eco"], "Eft.type": d["eft"],
                "Medit": d["medit"], "Species": sp, "Total.number.run1": tot, "Number.length.below.150": below,
                "Number.length.over.150": over, "Fished.area": d["fished"], "Method": d["method"],
                "Sampling.location": d["loc"], "Flow.regime": "Permanent", "Lakes.upstream": "No",
            })
    return pd.DataFrame(rows, columns=S.INPUT_COLUMNS)


def example_input2() -> pd.DataFrame:
    rows = []
    for code, d in _SITES.items():
        rec = {c: S.NODATA for c in S.DIAD_SPECIES_COLUMNS}
        rec["Anguilla anguilla historic"] = "Yes"
        rec["Anguilla anguilla present"] = "Yes" if code in ("FR0002", "ES0004") else "No"
        rec["Salmo salar historic"] = "Yes"
        rec["Salmo salar present"] = "No"
        if code == "FR0002":
            rec["Alosa alosa historic"] = "Yes"
            rec["Alosa alosa present"] = "No"
        rec.update({k: d[k] for k in ("Day", "Month", "Year", "Longitude", "Latitude")})
        rec["Site.code"] = code
        rows.append(rec)
    return pd.DataFrame(rows, columns=S.DIAD_COLUMNS)
