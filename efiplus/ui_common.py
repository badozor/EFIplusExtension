"""Content shared by the Streamlit and NiceGUI front-ends."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import schema as S

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
ASSETS_DIR = ROOT / "assets"
LOGO = ASSETS_DIR / "efiplus_logo.png"
FAVICON = ASSETS_DIR / "favicon.png"
STAR_STRIPE_CSS = "linear-gradient(90deg, " + ", ".join(
    f"{c} {i * 20}% {(i + 1) * 20}%" for i, c in enumerate(S.CLASS_COLORS.values())) + ")"

APP_TITLE = "EFI+ calculator"
APP_SUBTITLE = "New European Fish Index (EFI+), computed with the R engine efitools-1.3"

WORKFLOW = [
    ("Insert data", "Upload the EFI+ Excel spreadsheet (several samples) or type one sample at a time."),
    ("Check", "Categories are checked against the allowed classes, numbers against the ranges of Table 16."),
    ("Run script", "The checked data are written as input.txt (and diadromous.txt) and processed by efitools-1.3."),
    ("Output", "Observed and expected metrics, partial and aggregated indices, final class and comments."),
]

# Manual Part II, Table 17 (comments of the output) + wording actually written by efitools-1.3.
COMMENTS_TABLE = pd.DataFrame([
    ("Sampling date", "Nothing to report", "Sampling within the EFI+ period (August to November)."),
    ("Sampling date", "Inadequate date", "Outside the sampling period: handle the result with care."),
    ("River zone", "Nothing to report / Initial.classification.correct",
     "The initial river type agrees with the proportion of salmonid type species."),
    ("River zone", "To be checked by user",
     "Initial river type not in agreement with the proportion of salmonid type species: confirm the type and the index."),
    ("Sampling location", "Nothing to report", "The main channel has been sampled."),
    ("Sampling location", "Fish index to be used with caution", "Main channel and connected water bodies sampled."),
    ("Sampling location", "Fish index inadequate", "Only backwaters have been sampled."),
    ("Sampling effort", "Nothing to report", "30 fish or more caught."),
    ("Sampling effort", "Fish index to be used with caution", "Less than 30 fish caught."),
    ("Species richness", "Nothing to report", "Species richness moderate or high."),
    ("Species richness", "Fish index most often inadequate", "Only one species (manual: 'to be used with caution')."),
    ("Method", "Fish index to be used with caution", "Boat sampling."),
], columns=["Topic", "Comment", "Explanation"])

OUTPUT_DEFINITIONS = {
    "Obs.dens.HINTOL.inf.150": "Observed density (ind./100 m²) of habitat-intolerant fish ≤ 150 mm",
    "Obs.dens.O2INTOL": "Observed density (ind./100 m²) of oxygen-intolerant fish",
    "Obs.ric.RH.PAR": "Observed number of rheophilic-spawning species",
    "Obs.dens.LITH": "Observed density (ind./100 m²) of lithophilic fish",
    "Exp.dens.HINTOL.inf150": "Expected value of Obs.dens.HINTOL.inf.150 (reference models)",
    "Exp.dens.O2INTOL": "Expected value of Obs.dens.O2INTOL",
    "Exp.ric.RH.PAR": "Expected value of Obs.ric.RH.PAR",
    "Exp.dens.LITH": "Expected value of Obs.dens.LITH",
    "Ids.dens.HINTOL.inf.150": "Partial index (0-1)",
    "Ids.dens.O2INTOL": "Partial index (0-1)",
    "Ids.ric.RH.PAR": "Partial index (0-1)",
    "Ids.dens.LITH": "Partial index (0-1)",
    "Aggregated.score.Salmonid.zone": "Mean of the O2INTOL and HINTOL.inf.150 partial indices",
    "Aggregated.score.Cyprinid.zone": "Mean of the RH.PAR and LITH partial indices",
    "FishIndex": "Final index for the river zone retained (River.zone)",
    "FishIndex.class": "Ecological class: 1 High, 2 Good, 3 Moderate, 4 Poor, 5 Bad",
    "Hist.ric.diadromous": "Historical number of diadromous species (historic or present = Yes)",
    "Present.ric.diadromous": "Present number of diadromous species",
    "Ids.ric.diadromous": "Present / historical diadromous richness (close to 0: migration barriers likely)",
}

KNOWN_ENGINE_ISSUES = [
    "commentDate() tests `month > 11 & month < 8`, which is never true: Comments.date is always "
    "'Nothing to report'. The GUI adds its own warning during the check for months outside August-November.",
]

ENGINE_CHANGES = [
    "efitools-1.3 fixes RecodeNameOutputDiad: in 1.2, Hist.ric.diadromous received the present richness "
    "and Present.ric.diadromous the historical one. Ids.ric.diadromous was already correct.",
]


def variables_table() -> pd.DataFrame:
    rows = []
    for v in S.INPUT_VARS:
        if v.name == "Species":
            allowed = f"{len(S.SPECIES)} species of the EFI+ guild table"
        elif v.choices:
            allowed = ", ".join(map(str, v.choices))
        elif v.vmin is not None:
            allowed = f"{v.vmin:g} to {v.vmax:g}"
        else:
            allowed = "free text"
        rows.append({
            "Column (R name)": v.name, "Label": v.label, "Level": v.level,
            "Mandatory": "yes" if v.mandatory else "no", "Type": v.kind,
            "Unit": v.unit, "Allowed values": allowed, "Notes": v.help,
        })
    return pd.DataFrame(rows)


def class_summary(output: pd.DataFrame) -> pd.DataFrame:
    if "FishIndex.class" not in output:
        return pd.DataFrame()
    c = output["FishIndex.class"].value_counts(dropna=False)
    rows = []
    for k, lab in S.CLASS_LABELS.items():
        rows.append({"Class": k, "Status": lab, "Samples": int(c.get(k, 0))})
    na = int(output["FishIndex.class"].isna().sum())
    if na:
        rows.append({"Class": None, "Status": "Not computed", "Samples": na})
    return pd.DataFrame(rows)


def docs_available() -> list[Path]:
    return sorted(DOCS_DIR.glob("*.pdf")) if DOCS_DIR.is_dir() else []


def empty_species_frame(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "Species": pd.Series([None] * n, dtype=object),
        "Total.number.run1": pd.Series([None] * n, dtype="Int64"),
        "Number.length.below.150": pd.Series([None] * n, dtype="Int64"),
        "Number.length.over.150": pd.Series([None] * n, dtype="Int64"),
    })


def build_manual_rows(site: dict, species: pd.DataFrame) -> pd.DataFrame:
    """Combine one sample's site variables with its species table into input1 rows."""
    sp = species.dropna(subset=["Species"])
    sp = sp[sp["Species"].astype(str).str.strip() != ""]
    rows = []
    for _, r in sp.iterrows():
        rec = {k: site.get(k) for k in S.INPUT_COLUMNS}
        for c in ("Species", "Total.number.run1", "Number.length.below.150", "Number.length.over.150"):
            val = r.get(c)
            rec[c] = None if pd.isna(val) else val
        rows.append(rec)
    return pd.DataFrame(rows, columns=S.INPUT_COLUMNS)


def site_defaults() -> dict:
    d = {v.name: None for v in S.SAMPLE_VARS}
    d.update({"Floodplain.site": "No", "Water.source.type": "Pluvial", "Geomorph.river.type": "Sinuous",
              "Natural.sediment": "Gravel/Pebble/Cobble", "Ecoreg": "Central Highlands", "Eft.type": "T.1",
              "Medit": 0, "Method": "Wading", "Sampling.location": "Main channel",
              "Flow.regime": "Permanent", "Lakes.upstream": "No"})
    return d


def ecoregion_hint(lon, lat) -> tuple[str | None, str]:
    """Ecoregion given by the map for the manual forms: (efitools name or None, short text)."""
    from . import ecoregion
    try:
        lon, lat = float(lon), float(lat)
    except (TypeError, ValueError):
        return None, "Type the coordinates to get the ecoregion from the map."
    vl, va = S.VAR_BY_NAME["Longitude"], S.VAR_BY_NAME["Latitude"]
    if not (vl.vmin <= lon <= vl.vmax and va.vmin <= lat <= va.vmax):
        return None, "Coordinates out of range."
    ok, msg = ecoregion.status()
    if not ok:
        return None, msg
    h = ecoregion.lookup(lon, lat)
    if not h.found:
        return None, f"Map: no ecoregion within {h.outside_km:g} km."
    if h.efi_name is None:
        return None, f"Map: {h.label()}, not covered by EFI+."
    txt = f"Map: {h.label()}."
    if h.neighbours:
        n, dkm = h.neighbours[0]
        txt += f" {dkm:g} km from Illies {n} '{ecoregion.illies_name(n)}': check."
    return h.efi_name, txt
