# EFI+ calculator (Python GUI for efitools-1.3)

Local web interface to compute the new European Fish Index (EFI+) with the R engine
**efitools-1.3**, following Part II of the *Manual for the application of the new European
Fish Index – EFI+* (June 2009): data input (Excel file or manual form), checks, "Run script",
output.

Two front-ends share the same core (`efiplus/`):

| | Streamlit | NiceGUI |
|---|---|---|
| Start | `streamlit run app_streamlit.py` | `python app_nicegui.py` |
| URL | http://localhost:8501 | http://localhost:8080 |
| Windows launcher | `run_streamlit.bat` | `run_nicegui.bat` |

## Requirements

- Python ≥ 3.10 and `pip install -r requirements.txt`
- R ≥ 3.5 (tested with R 4.3.3). Package MASS (shipped with R).
  `Rscript` is found on the PATH, in `C:\Program Files\R\R-*\bin`, or set its path in the
  sidebar or with the environment variable `EFI_RSCRIPT`.

## Workflow (as in the manual)

1. **Insert data**
   - *Excel file*: download the blank `EFI+SpreadSheet.xlsx` (drop-down lists, ranges in the
     header comments) or the filled example; upload it. Sheet `input1 all actual variables`
     (one row per sample × species) and optional `input2 all diadromous variables`.
     A semicolon-separated `Input.txt` is accepted too.
   - *Manual*: one sample at a time (selection lists for categories, ranges for numbers,
     searchable species list, optional diadromous species). "Get Excel copy" saves the input.
2. **Check**: categories against allowed classes, numbers against Table 16, site variables
   constant within a sample, length classes adding up to the total, matching samples
   between input1 and input2, sampling period (August–November). Errors block the run.
   Common spellings are recoded with a warning (e.g. `Meandering regular` → `Meand regular`).
3. **Run script**: writes `input.txt` (and `diadromous.txt`) and calls `main.R` or
   `maindiad.R` with Rscript.
4. **Output**: summary with classes and comments, the four groups of the manual, chart,
   `NewEFI+output.xlsx` (grouped output, class colours, inputs, R log) and raw `output.txt`.

## Layout

```
app_streamlit.py, app_nicegui.py   front-ends
efiplus/                           core: schema, validate, engine, excel_io, ui_common, examples
engine/                            efitools-1.3 (main.R, maindiad.R, internal/, CHANGES.txt)
assets/                            EFI+ logo and favicon
docs/                              manuals (PDF) shown in Help
tests/test_core.py                 pytest: checks, engine run, Excel round trip
```

## efitools-1.3

The engine shipped in `engine/` is efitools-1.3 (details in `engine/CHANGES.txt`):

- **Bug fix**: `Hist.ric.diadromous` and `Present.ric.diadromous` were swapped in 1.2
  (`RecodeNameOutputDiad`). `Ids.ric.diadromous` was already correct. On the test data,
  only these two columns differ from 1.2.
- **Compatibility** (computation unchanged): `directory` read from `EFI_DIR`; absolute file
  paths accepted; arguments read with `commandArgs(trailingOnly = TRUE)` (works with
  `Rscript`); `comment.char = "£"` replaced by `""` (refused by R 4.x in UTF-8).

Tested with R 4.3.3. No comparison with R 2.8.1 (the version used in 2009) was possible here.

## Known issue (not corrected)

- `commentDate`: the test `month > 11 & month < 8` is never true, so `Comments.date` is always
  "Nothing to report". The GUI check adds its own warning for months outside August–November.

## Open points

- `Eft.type` (FAME European fish type) is required by the engine but not listed in Table 14 of
  the manual. The GUI accepts `T.1` … `T.15` and `T.NA`; only T.5, T.6, T.14, T.15 change the
  result (Cyprinid). The list of valid types should be confirmed.
- Year range: Table 16 says 1950–2020; the GUI accepts up to the current year.
- The example data (`efiplus/examples.py`) are invented to show the workflow.

## Tests

```
python -m pytest tests/
```
