"""Variable definitions for the EFI+ input files.

Sources:
- Manual for the application of the new European Fish Index (EFI+), Part II,
  Table 14 (input variables) and Table 16 (allowed ranges).
- efitools-1.3 documentation (Table 1 and 2: exchange format with R).
- efitools-1.3 code (internal/efiminus.R: prepEnv, prepRegEco) for the exact
  category codes expected by the R engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

NODATA = "NoData"
NA_NUM = -999

SHEET_INPUT1 = "input1 all actual variables"
SHEET_INPUT2 = "input2 all diadromous variables"


@dataclass(frozen=True)
class Var:
    name: str                 # column name expected by R (input.txt header)
    label: str                # label shown in the GUI (manual wording)
    kind: str                 # "str", "int", "float", "cat"
    level: str                # "sample" (constant per fishing occasion) or "species"
    mandatory: bool = True
    choices: tuple = ()
    vmin: float | None = None
    vmax: float | None = None
    unit: str = ""
    help: str = ""
    aliases: dict = field(default_factory=dict)  # accepted spellings -> code used by R


ECOREGIONS = (
    "Alps", "Baltic Province", "Borealic Uplands", "Central Highlands",
    "Central Plains", "Eastern Plains", "Great Britain", "Fenno-Scandian Shield",
    "Hungarian Lowlands", "Iberian Peninsula", "Italy", "Pontic Province",
    "Pyrenees", "The Carpathians", "Western Highlands", "Western Plains",
)

# FAME European fish types used by prepRegEco (T.5, T.6, T.14, T.15 -> Cyprinid,
# T.NA -> missing, any other type -> Salmonid).
EFT_TYPES = tuple(f"T.{i}" for i in range(1, 16)) + ("T.NA",)

SPECIES = tuple(
    s.strip() for s in (DATA_DIR / "species.txt").read_text(encoding="utf-8").splitlines() if s.strip()
)

_YEAR_MAX = max(2020, date.today().year)

INPUT_VARS: tuple[Var, ...] = (
    Var("Site.code", "Site code", "str", "sample",
        help="Code of the sampling site (e.g. country abbreviation + own code, DE0001)."),
    Var("Day", "Day", "int", "sample", vmin=1, vmax=31),
    Var("Month", "Month", "int", "sample", vmin=1, vmax=12),
    Var("Year", "Year", "int", "sample", vmin=1950, vmax=_YEAR_MAX),
    Var("Longitude", "Longitude", "float", "sample", vmin=-12, vmax=40, unit="decimal degrees WGS84"),
    Var("Latitude", "Latitude", "float", "sample", vmin=35, vmax=72, unit="decimal degrees WGS84"),
    Var("Actual.river.slope", "River slope", "float", "sample", vmin=0.001, vmax=200, unit="‰ (m/km)",
        help="Drop of altitude divided by stream segment length."),
    Var("Temp.jul", "Air temperature July", "float", "sample", vmin=-5, vmax=45, unit="°C"),
    Var("Temp.jan", "Air temperature January", "float", "sample", vmin=-25, vmax=30, unit="°C"),
    Var("Floodplain.site", "Former floodplain", "cat", "sample", choices=("Yes", "No", NODATA),
        help="Presence of a former floodplain. The R models only know Yes/No."),
    Var("Water.source.type", "Water source", "cat", "sample",
        choices=("Glacial", "Groundwater", "Nival", "Pluvial", NODATA)),
    Var("Geomorph.river.type", "Geomorphology", "cat", "sample",
        choices=("Braided", "Meand regular", "Meand tortous", "Naturally constraint no mob", "Sinuous", NODATA),
        aliases={"Meandering regular": "Meand regular", "Meandering tortuous": "Meand tortous",
                 "Meandering tortous": "Meand tortous", "Meand tortuous": "Meand tortous",
                 "Sinous": "Sinuous", "Naturally constraint": "Naturally constraint no mob"}),
    Var("Distance.from.source", "Distance from source", "float", "sample", vmin=0.01, vmax=8000, unit="km"),
    Var("Area.ctch", "Upstream drainage area", "float", "sample", vmin=1, vmax=20_000_000, unit="km²"),
    Var("Natural.sediment", "Former sediment", "cat", "sample",
        choices=("Organic", "Silt", "Sand", "Gravel/Pebble/Cobble", "Boulder/Rock", NODATA)),
    Var("Ecoreg", "Ecoregion (Illies)", "cat", "sample", choices=ECOREGIONS),
    Var("Eft.type", "European fish type (FAME EFT)", "cat", "sample", choices=EFT_TYPES,
        help="T.5, T.6, T.14, T.15 are treated as Cyprinid types by the engine; T.NA = unknown."),
    Var("Medit", "Mediterranean type", "int", "sample", choices=(0, 1, 2), vmin=0, vmax=2,
        help="Mediterranean type 1 with latitude < 45° moves the site to the Mediterranean region."),
    Var("Species", "Species name", "cat", "species", choices=SPECIES),
    Var("Total.number.run1", "Total number run 1", "int", "species", vmin=1, vmax=1_100_000),
    Var("Number.length.below.150", "Number length ≤ 150 mm", "int", "species", vmin=0, vmax=1_000_000),
    Var("Number.length.over.150", "Number length > 150 mm", "int", "species", vmin=0, vmax=1_000_000),
    Var("Fished.area", "Fished area", "float", "sample", vmin=50, vmax=100_000, unit="m²"),
    Var("Method", "Method", "cat", "sample", choices=("Wading", "Boat", "Mixed", NODATA),
        aliases={"Boating": "Boat"}),
    Var("Sampling.location", "Sampling location", "cat", "sample",
        choices=("Main channel", "Backwaters", "Mixed", NODATA)),
    Var("Flow.regime", "Flow regime", "cat", "sample", mandatory=False,
        choices=("Permanent", "Summer dry", "Winter dry", "Intermittent", NODATA)),
    Var("Lakes.upstream", "Natural lake upstream", "cat", "sample", mandatory=False,
        choices=("Yes", "No", NODATA)),
)

VAR_BY_NAME = {v.name: v for v in INPUT_VARS}
INPUT_COLUMNS = [v.name for v in INPUT_VARS]
SAMPLE_VARS = [v for v in INPUT_VARS if v.level == "sample"]
SPECIES_VARS = [v for v in INPUT_VARS if v.level == "species"]
KEY_COLUMNS = ["Site.code", "Day", "Month", "Year"]

# Diadromous species, in the order and spelling of internal/diadromousplus.txt
# (note the double space after "Alosa immaculata", kept on purpose).
DIADROMOUS_SPECIES = (
    "Acipenser naccarii", "Acipenser gueldenstadtii", "Acipenser nudiventris",
    "Acipenser stellatus", "Acipenser sturio/A. oxyrinchus", "Alosa alosa",
    "Alosa fallax", "Alosa immaculata ", "Anguilla anguilla", "Huso huso",
    "Lampetra fluviatilis", "Petromyzon marinus", "Osmerus eperlanus",
    "Salmo salar", "Salmo trutta trutta", "Platichthys flesus",
    "Coregonus spp. diadr. form",
)
DIAD_KEY_COLUMNS = ["Site.code", "Day", "Month", "Year", "Longitude", "Latitude"]
DIAD_SPECIES_COLUMNS = [f"{s} {w}" for s in DIADROMOUS_SPECIES for w in ("historic", "present")]
DIAD_COLUMNS = DIAD_SPECIES_COLUMNS + DIAD_KEY_COLUMNS
DIAD_CHOICES = ("Yes", "No", NODATA)


def norm_header(name: str) -> str:
    """Normalise a column header for tolerant matching (case, spaces, dots)."""
    return " ".join(str(name).replace(".", " ").replace("_", " ").split()).lower()


# Output columns grouped as in the manual (Part II, section 5).
OUTPUT_GROUPS = {
    "Reference and classification data": [
        "Site.code", "Day", "Month", "Year", "Longitude", "Latitude", "Ecoregion",
        "Method", "Sampling.location", "EFT.river.typology", "ST-Species", "River.zone",
    ],
    "Observed and expected metrics": [
        "Obs.dens.HINTOL.inf.150", "Obs.dens.O2INTOL", "Obs.ric.RH.PAR", "Obs.dens.LITH",
        "Exp.dens.HINTOL.inf150", "Exp.dens.O2INTOL", "Exp.ric.RH.PAR", "Exp.dens.LITH",
        "Hist.ric.diadromous", "Present.ric.diadromous", "Richness", "Captures",
    ],
    "Partial and aggregated indices": [
        "Ids.dens.HINTOL.inf.150", "Ids.dens.O2INTOL", "Ids.ric.RH.PAR", "Ids.dens.LITH",
        "Aggregated.score.Salmonid.zone", "Aggregated.score.Cyprinid.zone", "Ids.ric.diadromous",
    ],
    "Final scores": ["FishIndex", "FishIndex.class"],
    "Comments": [
        "Comments.river.zone", "Comments.method", "Comments.sampling.location",
        "Comments.richness", "Comments.sampling.effort", "Comments.date",
    ],
}

CLASS_LABELS = {1: "High", 2: "Good", 3: "Moderate", 4: "Poor", 5: "Bad"}
# Colours of the five stars of the EFI+ logo (toned down slightly for legibility).
EFI_BLUE = "#0060C0"
EFI_BLUE_DARK = "#004890"
CLASS_COLORS = {1: "#0060C0", 2: "#39A93C", 3: "#E3D52B", 4: "#E09B2F", 5: "#E0262B"}
