"""EFI+ calculator, NiceGUI front-end.

Run with:  python app_nicegui.py      (then open http://localhost:8080)
"""
from __future__ import annotations

import datetime as dt
import os

import pandas as pd
from nicegui import app, run, ui

from efiplus import __version__, ecoregion, engine, excel_io, schema as S, ui_common as U, validate
from efiplus.examples import example_input1, example_input2

if U.ASSETS_DIR.is_dir():
    app.add_static_files("/assets", str(U.ASSETS_DIR))

PRIMARY = S.EFI_BLUE
PRIMARY_DARK = S.EFI_BLUE_DARK


def records(df: pd.DataFrame) -> list[dict]:
    d = df.astype(object).where(df.notna(), None)
    return d.to_dict("records")


def grid(df: pd.DataFrame, height: int = 320, extra_cols: dict | None = None, **opts) -> ui.aggrid:
    cols = []
    for c in df.columns:
        cd = {"field": c, "headerName": c, "sortable": True, "filter": True, "resizable": True}
        if extra_cols and c in extra_cols:
            cd.update(extra_cols[c])
        cols.append(cd)
    g = ui.aggrid({"columnDefs": cols, "rowData": records(df), "defaultColDef": {"minWidth": 90},
                   "autoSizeStrategy": {"type": "fitCellContents"},
                   "suppressFieldDotNotation": True, **opts}, theme="balham")
    g.style(f"height:{height}px")
    return g


CLASS_STYLE_JS = (
    "params => { const c = {1:'%s',2:'%s',3:'%s',4:'%s',5:'%s'}[params.value];"
    " return c ? {backgroundColor: c, color: [1,2,5].includes(params.value) ? 'white' : 'black', fontWeight: 600} : null; }"
    % tuple(S.CLASS_COLORS[k] for k in range(1, 6))
)
NUM_FMT_JS = "params => (typeof params.value === 'number' && !Number.isInteger(params.value)) ? params.value.toFixed(3) : params.value"


class State:
    def __init__(self):
        self.raw1 = self.raw2 = None
        self.source = None
        self.notes: list[str] = []
        self.check: validate.CheckResult | None = None
        self.result: engine.RunResult | None = None
        self.manual1 = pd.DataFrame(columns=S.INPUT_COLUMNS)
        self.manual2 = pd.DataFrame(columns=S.DIAD_COLUMNS)
        self.rscript = engine.find_rscript() or ""
        self.ecolayer = ""

    def set_dataset(self, raw1, raw2, source, notes=()):
        self.raw1, self.raw2, self.source, self.notes = raw1, raw2, source, list(notes)
        self.check = validate.check(raw1, raw2)
        self.result = None


@ui.page("/")
def main_page():
    st = State()
    ui.colors(primary=PRIMARY)
    ui.add_css(f"""
      .efi-card {{border-left: 4px solid {PRIMARY};}}
      .q-tab-panel {{padding: 8px 4px;}}
      .efi-header {{background: white; color: {PRIMARY_DARK}; border-bottom: 5px solid transparent;
                   border-image: {U.STAR_STRIPE_CSS} 1;}}
      .text-h4, .text-h5 {{color: {PRIMARY_DARK};}}
      .ag-theme-balham .row-error {{background:#f8d7da !important;}}
      .ag-theme-balham .row-warning {{background:#fff3cd !important;}}
    """)

    with ui.header(elevated=True).classes("efi-header items-center justify-between q-py-xs"):
        with ui.row().classes("items-center gap-3"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat dense").style(f"color:{PRIMARY_DARK}")
            if U.LOGO.is_file():
                ui.image("/assets/" + U.LOGO.name).props("fit=contain no-spinner no-transition").style("height:46px;width:100px")
            ui.label(U.APP_TITLE).classes("text-h6 text-weight-medium")
        ui.label(f"GUI v{__version__} · engine efitools-1.3").classes("text-caption text-grey-7")

    with ui.left_drawer(value=True).classes("bg-grey-1") as drawer:
        with ui.tabs().props("vertical align=left").classes("w-full") as tabs:
            t_home = ui.tab("Home", icon="home")
            t_excel = ui.tab("Insert data: Excel", icon="upload_file")
            t_manual = ui.tab("Insert data: manual", icon="edit_note")
            t_check = ui.tab("Check and run", icon="fact_check")
            t_res = ui.tab("Results", icon="insights")
            t_help = ui.tab("Help", icon="help_outline")
        ui.separator().classes("my-2")
        ui.label("R engine").classes("text-subtitle2")
        r_input = ui.input("Path to Rscript", value=st.rscript).classes("w-full").props("dense")

        @ui.refreshable
        def r_status():
            rs = engine.find_rscript(r_input.value)
            missing = engine.check_engine()
            if rs and not missing:
                ui.label("✅ " + engine.r_version(rs)).classes("text-positive text-caption")
            if not rs:
                ui.label("⛔ Rscript not found. Install R from cran.r-project.org.").classes("text-negative text-caption")
            if missing:
                ui.label("⛔ Engine files missing: " + ", ".join(missing)).classes("text-negative text-caption")
            if st.source:
                ui.separator().classes("my-2")
                ui.label("Current dataset").classes("text-subtitle2")
                ui.label(st.source).classes("text-caption")
        r_status()
        r_input.on("blur", lambda: (setattr(st, "rscript", r_input.value), r_status.refresh()))

        ui.label("Ecoregion map (optional)").classes("text-subtitle2 q-mt-sm")
        e_input = ui.input("Path to the ecoregion layer", value=st.ecolayer).classes("w-full").props("dense")
        e_input.tooltip("Optional. Polygon layer of the Illies ecoregions (.shp or .geojson, attribute AREA_ID = Illies number). Used to fill or check the ecoregion from the coordinates. Can also be set with EFI_ECOREG_LAYER or by copying the layer to local/ecoregions/.")

        @ui.refreshable
        def e_status():
            ok, msg = ecoregion.status(e_input.value)
            ui.label(("✅ " if ok else "ℹ️ ") + msg).classes(("text-positive" if ok else "text-grey-7") + " text-caption")
        e_status()

        def set_ecolayer():
            st.ecolayer = e_input.value
            ecoregion.set_layer(e_input.value)
            e_status.refresh()
        e_input.on("blur", set_ecolayer)

    def go(tab):
        tabs.set_value(tab)

    def load_dataset(raw1, raw2, source, notes=()):
        st.set_dataset(raw1, raw2, source, notes)
        check_view.refresh()
        r_status.refresh()
        go(t_check)

    # ------------------------------------------------------------------ panels
    with ui.tab_panels(tabs, value=t_home).classes("w-full").props("animated=false"):

        # ---------------- Home
        with ui.tab_panel(t_home):
            with ui.row().classes("items-center gap-6 no-wrap"):
                if U.LOGO.is_file():
                    ui.image("/assets/" + U.LOGO.name).props("fit=contain no-spinner no-transition").style("width:240px;height:115px")
                with ui.column().classes("gap-1"):
                    ui.label(U.APP_TITLE).classes("text-h4")
                    ui.label(U.APP_SUBTITLE).classes("text-subtitle1 text-grey-8")
                    ui.label("Improvement and Spatial Extension of the European Fish Index "
                             "(EFI+ project, EC contract 044096)").classes("text-caption text-grey-7")
            with ui.row().classes("w-full gap-4 q-mt-md"):
                for i, (t, d) in enumerate(U.WORKFLOW, start=1):
                    with ui.card().classes("efi-card").style("width:230px"):
                        ui.label(f"{i}. {t}").classes("text-bold")
                        ui.label(d).classes("text-caption")
            ui.label("Start").classes("text-h6 q-mt-lg")
            with ui.row().classes("gap-3"):
                ui.button("Upload an Excel file", icon="upload_file", on_click=lambda: go(t_excel))
                ui.button("Enter a sample manually", icon="edit_note", on_click=lambda: go(t_manual))
                ui.button("Try with the example data", icon="science",
                          on_click=lambda: load_dataset(example_input1(), example_input2(),
                                                        "Example dataset (5 invented samples)")).props("outline")
            ui.label("The example data are invented to show the workflow. They do not describe real sites.") \
                .classes("text-caption text-grey-7")

        # ---------------- Excel
        with ui.tab_panel(t_excel):
            ui.label("Insert data: Excel file").classes("text-h5")
            ui.markdown(f"Two sheets: **{S.SHEET_INPUT1}** (one row per sample × species) and "
                        f"**{S.SHEET_INPUT2}** (optional, one row per sample). Missing values: `-999` for "
                        "numbers, `NoData` for text.")
            with ui.row().classes("gap-3"):
                ui.button("Blank EFI+ spreadsheet", icon="download",
                          on_click=lambda: ui.download.content(excel_io.build_template(False), "EFI+SpreadSheet.xlsx"))
                ui.button("Filled example", icon="download",
                          on_click=lambda: ui.download.content(excel_io.build_template(True),
                                                               "EFI+SpreadSheet_example.xlsx")).props("outline")

            async def on_upload(e):
                try:
                    data = await e.file.read()
                    d1, d2, notes = excel_io.read_workbook(data)
                except Exception as ex:  # noqa: BLE001
                    ui.notify(f"The file cannot be read: {ex}", type="negative", multi_line=True)
                    return
                upl.reset()
                load_dataset(d1, d2, f"File: {e.file.name}", notes)

            upl = ui.upload(label="EFI+ spreadsheet (.xlsx, .xls) or Input.txt: click or drop the file",
                            on_upload=on_upload, auto_upload=True, max_files=1) \
                .props('accept=".xlsx,.xls,.txt,.csv"').classes("w-full q-mt-md")

        # ---------------- Manual
        with ui.tab_panel(t_manual):
            ui.label("Insert data: manual").classes("text-h5")
            ui.label("One sample at a time. Fields marked * are mandatory. Manual data are not stored: "
                     "download an Excel copy to keep them.").classes("text-caption text-grey-7")
            d = U.site_defaults()
            f: dict = {}

            def num(name):
                v = S.VAR_BY_NAME[name]
                lab = f"{v.label}{' (' + v.unit + ')' if v.unit else ''} *"
                w = ui.number(lab, min=v.vmin, max=v.vmax, validation={
                    f"{v.vmin:g} to {v.vmax:g}": lambda x, a=v.vmin, b=v.vmax: x is None or a <= x <= b})
                w.tooltip(f"Range {v.vmin:g} to {v.vmax:g}" + (f". {v.help}" if v.help else ""))
                return w.classes("col")

            def cat(name):
                v = S.VAR_BY_NAME[name]
                w = ui.select(list(v.choices), value=d[name], label=v.label + (" *" if v.mandatory else ""))
                if v.help:
                    w.tooltip(v.help)
                return w.classes("col")

            with ui.card().classes("w-full"):
                ui.label("Location and date").classes("text-subtitle1 text-bold")
                with ui.row().classes("w-full no-wrap gap-3"):
                    f["Site.code"] = ui.input("Site code *", placeholder="e.g. DE0001").classes("col")
                    f["date"] = ui.input("Sampling date * (YYYY-MM-DD)", value="2008-09-15").classes("col")
                    with f["date"].add_slot("append"):
                        icon = ui.icon("event").classes("cursor-pointer")
                        with ui.menu() as m:
                            ui.date().bind_value(f["date"]).props("mask=YYYY-MM-DD")
                        icon.on("click", m.open)
                    f["Longitude"] = num("Longitude")
                    f["Latitude"] = num("Latitude")
                ui.label("Environment").classes("text-subtitle1 text-bold q-mt-sm")
                with ui.row().classes("w-full no-wrap gap-3"):
                    for n in ("Ecoreg", "Eft.type", "Medit"):
                        f[n] = cat(n)
                    f["Area.ctch"] = num("Area.ctch")
                eco_hint = ui.label(U.ecoregion_hint(None, None)[1]).classes("text-caption text-grey-7")

                def update_ecoreg(_=None):
                    name, txt = U.ecoregion_hint(f["Longitude"].value, f["Latitude"].value)
                    eco_hint.text = txt
                    if name:
                        f["Ecoreg"].value = name

                f["Longitude"].on_value_change(update_ecoreg)
                f["Latitude"].on_value_change(update_ecoreg)
                with ui.row().classes("w-full no-wrap gap-3"):
                    for n in ("Distance.from.source", "Actual.river.slope", "Temp.jan", "Temp.jul"):
                        f[n] = num(n)
                with ui.row().classes("w-full no-wrap gap-3"):
                    for n in ("Geomorph.river.type", "Floodplain.site", "Water.source.type", "Natural.sediment"):
                        f[n] = cat(n)
                with ui.row().classes("w-full no-wrap gap-3"):
                    for n in ("Flow.regime", "Lakes.upstream"):
                        f[n] = cat(n)
                    ui.element("div").classes("col")
                    ui.element("div").classes("col")
                ui.label("Sampling").classes("text-subtitle1 text-bold q-mt-sm")
                with ui.row().classes("w-full no-wrap gap-3"):
                    for n in ("Method", "Sampling.location"):
                        f[n] = cat(n)
                    f["Fished.area"] = num("Fished.area")
                    ui.element("div").classes("col")

                ui.label("Fish caught in run 1").classes("text-subtitle1 text-bold q-mt-md")
                ui.label("Type to search the EFI+ species list. If '> 150 mm' is left empty it is computed as "
                         "total − '≤ 150 mm'. Numbers can be corrected in the table (double-click).") \
                    .classes("text-caption text-grey-7")
                with ui.row().classes("w-full items-end no-wrap gap-3"):
                    sp_sel = ui.select(list(S.SPECIES), with_input=True, label="Species *",
                                       clearable=True).classes("col-5")
                    sp_tot = ui.number("Total run 1 *", min=1, precision=0).classes("col")
                    sp_below = ui.number("≤ 150 mm *", min=0, precision=0).classes("col")
                    sp_over = ui.number("> 150 mm", min=0, precision=0).classes("col")

                    def add_species():
                        if not sp_sel.value or sp_tot.value is None or sp_below.value is None:
                            ui.notify("Species, total and number ≤ 150 mm are required.", type="warning")
                            return
                        tot, below = int(sp_tot.value), int(sp_below.value)
                        over = int(sp_over.value) if sp_over.value is not None else tot - below
                        if over < 0:
                            ui.notify("Number ≤ 150 mm is larger than the total.", type="warning")
                            return
                        if any(r["Species"] == sp_sel.value for r in sp_grid.options["rowData"]):
                            ui.notify("Species already in the table.", type="warning")
                            return
                        sp_grid.options["rowData"].append({
                            "Species": sp_sel.value, "Total.number.run1": tot,
                            "Number.length.below.150": below, "Number.length.over.150": over})
                        sp_grid.update()
                        for w in (sp_sel, sp_tot, sp_below, sp_over):
                            w.value = None
                    ui.button("Add species", icon="add", on_click=add_species)
                sp_grid = ui.aggrid({
                    "columnDefs": [
                        {"field": "Species", "headerName": "Species", "flex": 3, "checkboxSelection": True},
                        {"field": "Total.number.run1", "headerName": "Total run 1", "editable": True, "flex": 1,
                         "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 1, "precision": 0}},
                        {"field": "Number.length.below.150", "headerName": "≤ 150 mm", "editable": True, "flex": 1,
                         "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 0, "precision": 0}},
                        {"field": "Number.length.over.150", "headerName": "> 150 mm", "editable": True, "flex": 1,
                         "cellEditor": "agNumberCellEditor", "cellEditorParams": {"min": 0, "precision": 0}},
                    ],
                    "rowData": [], "rowSelection": "multiple", "suppressFieldDotNotation": True,
                    "stopEditingWhenCellsLoseFocus": True,
                    "overlayNoRowsTemplate": "No species yet",
                }, theme="balham").style("height:220px")

                async def remove_species():
                    sel = {r["Species"] for r in await sp_grid.get_selected_rows()}
                    sp_grid.options["rowData"] = [r for r in await sp_grid.get_client_data()
                                                  if r["Species"] not in sel]
                    sp_grid.update()
                ui.button("Remove selected species", icon="remove", on_click=remove_species).props("flat dense")

                with ui.expansion("Diadromous species (optional)", icon="waves").classes("w-full"):
                    use_diad = ui.checkbox("Record diadromous species for this sample")
                    ui.label("Historical: Yes / No / NoData. Present: Yes / No.").classes("text-caption")
                    diad_grid = ui.aggrid({
                        "columnDefs": [
                            {"field": "Species", "flex": 2},
                            {"field": "historic", "editable": True, "flex": 1, "cellEditor": "agSelectCellEditor",
                             "cellEditorParams": {"values": list(S.DIAD_CHOICES)}},
                            {"field": "present", "editable": True, "flex": 1, "cellEditor": "agSelectCellEditor",
                             "cellEditorParams": {"values": list(S.DIAD_CHOICES)}},
                        ],
                        "rowData": [{"Species": s.strip(), "historic": S.NODATA, "present": S.NODATA}
                                    for s in S.DIADROMOUS_SPECIES],
                        "stopEditingWhenCellsLoseFocus": True,
                    }, theme="balham").style("height:300px")

                async def add_sample():
                    code = (f["Site.code"].value or "").strip()
                    if not code:
                        ui.notify("Site code is mandatory.", type="warning")
                        return
                    try:
                        day = dt.date.fromisoformat(f["date"].value)
                    except (TypeError, ValueError):
                        ui.notify("Sampling date must be YYYY-MM-DD.", type="warning")
                        return
                    site = {k: w.value for k, w in f.items() if k in S.INPUT_COLUMNS}
                    site.update({"Site.code": code, "Day": day.day, "Month": day.month, "Year": day.year})
                    sp = pd.DataFrame(await sp_grid.get_client_data())
                    if sp.empty or "Species" not in sp:
                        sp = U.empty_species_frame(0)
                    sp = sp.replace({"": None})
                    rows = U.build_manual_rows(site, sp)
                    if rows.empty:
                        ui.notify("Enter at least one species.", type="warning")
                        return
                    st.manual1 = pd.concat([st.manual1, rows], ignore_index=True)
                    if use_diad.value:
                        rec = {c: S.NODATA for c in S.DIAD_SPECIES_COLUMNS}
                        for s_, r in zip(S.DIADROMOUS_SPECIES, await diad_grid.get_client_data()):
                            rec[f"{s_} historic"], rec[f"{s_} present"] = r["historic"], r["present"]
                        rec.update({k: site[k] for k in S.DIAD_KEY_COLUMNS})
                        st.manual2 = pd.concat([st.manual2, pd.DataFrame([rec])], ignore_index=True)
                    ui.notify(f"Sample {code} added ({len(rows)} species).", type="positive")
                    sp_grid.options["rowData"] = []
                    sp_grid.update()
                    manual_list.refresh()

                ui.button("Add this sample", icon="add_circle", on_click=add_sample).classes("q-mt-sm")

            @ui.refreshable
            def manual_list():
                ui.label("Samples entered").classes("text-h6 q-mt-md")
                if st.manual1.empty:
                    ui.label("No sample yet.").classes("text-grey-7")
                    return
                summ = st.manual1.groupby(S.KEY_COLUMNS, sort=False).size().reset_index(name="Species")
                grid(summ, height=160)
                with ui.row().classes("gap-3 q-mt-sm"):
                    ui.button("Check these samples", icon="fact_check", on_click=lambda: load_dataset(
                        st.manual1.copy(), st.manual2.copy() if not st.manual2.empty else None,
                        f"Manual input ({len(summ)} samples)"))
                    ui.button("Get Excel copy of input data", icon="download", on_click=lambda: ui.download.content(
                        excel_io.frames_to_excel_copy(st.manual1, st.manual2),
                        f"EFI+input_manual_{excel_io.timestamp()}.xlsx")).props("outline")

                    def clear():
                        st.manual1 = pd.DataFrame(columns=S.INPUT_COLUMNS)
                        st.manual2 = pd.DataFrame(columns=S.DIAD_COLUMNS)
                        manual_list.refresh()
                    ui.button("Clear all samples", icon="delete", on_click=clear).props("flat color=negative")
            manual_list()

        # ---------------- Check and run
        with ui.tab_panel(t_check):
            @ui.refreshable
            def check_view():
                ui.label("Check and run").classes("text-h5")
                res = st.check
                if res is None:
                    ui.label("No data loaded yet.").classes("text-grey-7")
                    with ui.row():
                        ui.button("Upload an Excel file", on_click=lambda: go(t_excel)).props("outline")
                        ui.button("Enter a sample manually", on_click=lambda: go(t_manual)).props("outline")
                    return
                ui.label(st.source).classes("text-caption text-grey-7")
                for n in st.notes:
                    ui.label(n).classes("text-caption text-grey-7")
                n_s = res.input1[S.KEY_COLUMNS].drop_duplicates().shape[0] if not res.input1.empty else 0
                with ui.row().classes("gap-4 q-my-sm"):
                    for lab, val, col in (("Samples", n_s, "grey-9"), ("Species records", len(res.input1), "grey-9"),
                                          ("Errors", len(res.errors), "negative" if res.errors else "grey-9"),
                                          ("Warnings", len(res.warnings), "warning" if res.warnings else "grey-9")):
                        with ui.card().classes("efi-card q-pa-sm").style("min-width:150px"):
                            ui.label(lab).classes("text-caption")
                            ui.label(str(val)).classes(f"text-h5 text-{col}")
                if res.issues:
                    fr = res.issues_frame()
                    grid(fr, height=min(360, 60 + 32 * len(fr)), extra_cols={"row": {"headerName": "Excel row"}},
                         rowClassRules={"row-error": "data.level === 'error'",
                                        "row-warning": "data.level === 'warning'"})
                if res.errors:
                    ui.label("⛔ Correct the errors in the original file (or in the form) and load it again. "
                             "The computation is blocked while errors remain.").classes("text-negative q-mt-sm")
                elif res.warnings:
                    ui.label("⚠️ No blocking error. Read the warnings before running the script.").classes("text-warning q-mt-sm")
                else:
                    ui.label("✅ No error, no warning.").classes("text-positive q-mt-sm")

                if not res.input1.empty:
                    with ui.tabs().classes("q-mt-md") as itabs:
                        a = ui.tab("See the R-Input file")
                        b = ui.tab("See the R-Input-Diadromous file")
                    with ui.tab_panels(itabs, value=a).classes("w-full"):
                        with ui.tab_panel(a):
                            grid(res.input1, height=300)
                        with ui.tab_panel(b):
                            if res.input2 is not None:
                                grid(res.input2, height=300)
                            else:
                                ui.label("No diadromous data: main.R will be used (no diadromous index).")

                async def do_run():
                    btn.disable()
                    spinner.set_visibility(True)
                    try:
                        r = await run.io_bound(engine.run, res.input1, res.input2, r_input.value or None)
                        st.result = r
                        results_view.refresh()
                        go(t_res)
                    except engine.EngineError as ex:
                        ui.notify(str(ex), type="negative", multi_line=True, timeout=0, close_button=True)
                    finally:
                        btn.enable()
                        spinner.set_visibility(False)

                with ui.row().classes("items-center q-mt-md"):
                    btn = ui.button("Run script", icon="play_arrow", on_click=do_run)
                    spinner = ui.spinner(size="lg")
                    spinner.set_visibility(False)
                    if not res.ok or not engine.find_rscript(r_input.value) or engine.check_engine():
                        btn.disable()
            check_view()

        # ---------------- Results
        with ui.tab_panel(t_res):
            @ui.refreshable
            def results_view():
                ui.label("Results").classes("text-h5")
                r = st.result
                if r is None:
                    ui.label("Run the script first (menu Check and run).").classes("text-grey-7")
                    return
                out = excel_io.order_output(r.output)
                ui.label(f"{st.source} · {r.script} · {r.rscript}").classes("text-caption text-grey-7")
                with ui.row().classes("gap-3 q-my-sm"):
                    with ui.card().classes("efi-card q-pa-sm").style("min-width:110px"):
                        ui.label("Samples").classes("text-caption")
                        ui.label(str(len(out))).classes("text-h5")
                    for row in U.class_summary(out).itertuples(index=False):
                        color = S.CLASS_COLORS.get(row.Class, "#999")
                        with ui.card().classes("q-pa-sm").style(f"min-width:110px;border-left:6px solid {color}"):
                            ui.label(f"{row.Class or '–'} · {row.Status}").classes("text-caption")
                            ui.label(str(row.Samples)).classes("text-h5")

                cols_summary = ["Site.code", "Day", "Month", "Year", "Ecoregion", "River.zone", "FishIndex",
                                "FishIndex.class", "Comments.river.zone", "Comments.sampling.effort",
                                "Comments.sampling.location", "Comments.method"]
                views = {"Summary": [c for c in cols_summary if c in out], "All columns": list(out.columns)}
                for g_, cs in S.OUTPUT_GROUPS.items():
                    views[g_] = ["Site.code"] + [c for c in cs if c in out and c != "Site.code"]
                fmt = {c: {":valueFormatter": NUM_FMT_JS} for c in out.columns if out[c].dtype.kind == "f"}
                fmt["FishIndex.class"] = {":cellStyle": CLASS_STYLE_JS}
                for c in U.OUTPUT_DEFINITIONS:
                    fmt.setdefault(c, {})["headerTooltip"] = U.OUTPUT_DEFINITIONS[c]

                @ui.refreshable
                def table(view="Summary"):
                    grid(out[views[view]], height=min(420, 70 + 30 * len(out)), extra_cols=fmt)
                ui.toggle(list(views), value="Summary", on_change=lambda e: table.refresh(e.value)).props("dense no-caps")
                table()

                if "FishIndex" in out and out["FishIndex"].notna().any():
                    dd = out[["Site.code", "FishIndex", "FishIndex.class"]].dropna(subset=["FishIndex"])
                    ui.echart({
                        "title": {"text": "Fish index by sample", "textStyle": {"fontSize": 14}},
                        "tooltip": {}, "grid": {"left": 40, "right": 10, "bottom": 60},
                        "xAxis": {"type": "category", "data": dd["Site.code"].tolist(), "axisLabel": {"rotate": 45}},
                        "yAxis": {"type": "value", "min": 0, "max": 1},
                        "series": [{"type": "bar", "data": [
                            {"value": round(float(v), 3),
                             "itemStyle": {"color": S.CLASS_COLORS.get(int(k), "#999") if pd.notna(k) else "#999"}}
                            for v, k in zip(dd["FishIndex"], dd["FishIndex.class"])]}],
                    }).style("height:300px").classes("w-full q-mt-md")

                meta = {"Source": st.source, "Script": r.script, "Rscript": r.rscript,
                        "R version": engine.r_version(r.rscript), "GUI version": __version__,
                        "Date": dt.datetime.now().isoformat(timespec="seconds")}
                with ui.row().classes("gap-3 q-mt-md"):
                    ui.button("NewEFI+output.xlsx", icon="download", on_click=lambda: ui.download.content(
                        excel_io.build_output_workbook(r.output, st.check.input1, st.check.input2, r.log, meta),
                        f"NewEFI+output_{excel_io.timestamp()}.xlsx"))
                    ui.button("output.txt (raw R output)", icon="download", on_click=lambda: ui.download.content(
                        r.output.to_csv(sep=";", index=False), "output.txt")).props("outline")
                with ui.expansion("R log (info.out)", icon="terminal").classes("w-full q-mt-sm"):
                    ui.code(r.log, language="text").classes("w-full")
            results_view()

        # ---------------- Help
        with ui.tab_panel(t_help):
            ui.label("Help").classes("text-h5")
            with ui.tabs() as htabs:
                h1 = ui.tab("Input variables")
                h2 = ui.tab("Output")
                h3 = ui.tab("Comments")
                h4 = ui.tab("Documents")
                h5 = ui.tab("Engine notes")
            with ui.tab_panels(htabs, value=h1).classes("w-full"):
                with ui.tab_panel(h1):
                    ui.label("Manual Part II, Tables 14 and 16, and efitools-1.3 exchange format. "
                             "Missing values: -999 (numbers), NoData (text).").classes("text-caption")
                    grid(U.variables_table(), height=520)
                    with ui.expansion(f"Species list ({len(S.SPECIES)})").classes("w-full"):
                        grid(pd.DataFrame({"Species": S.SPECIES}), height=300)
                with ui.tab_panel(h2):
                    grid(pd.DataFrame([{"Group": g_, "Column": c, "Definition": U.OUTPUT_DEFINITIONS.get(c, "")}
                                       for g_, cs in S.OUTPUT_GROUPS.items() for c in cs]), height=520)
                with ui.tab_panel(h3):
                    grid(U.COMMENTS_TABLE, height=420)
                with ui.tab_panel(h4):
                    docs = U.docs_available()
                    if not docs:
                        ui.label("Put the PDF manuals in the docs/ folder to make them available here.")
                    for p in docs:
                        ui.button(p.name, icon="menu_book",
                                  on_click=lambda p=p: ui.download.file(p)).props("flat no-caps align=left")
                    ui.markdown("[R Project](https://www.r-project.org) · "
                                "[European River and Catchment Database (CCM2)](https://ccm.jrc.ec.europa.eu)")
                with ui.tab_panel(h5):
                    ui.markdown("**Remaining issue (not corrected)**")
                    for i in U.KNOWN_ENGINE_ISSUES:
                        ui.markdown(f"- {i}")
                    ui.markdown("**Changes in efitools-1.3**")
                    for i in U.ENGINE_CHANGES:
                        ui.markdown(f"- {i}")
                    ui.label("Compatibility changes in main.R and maindiad.R: directory read from EFI_DIR, "
                             "absolute file paths accepted, arguments read with commandArgs(trailingOnly = TRUE), "
                             "comment.char = \"\" (the original '£' is not a single byte in UTF-8). "
                             "See CHANGES.txt in the engine folder.").classes("text-caption")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title=U.APP_TITLE, port=int(os.environ.get("EFI_PORT", 8080)), reload=False,
           show=os.environ.get("EFI_NO_BROWSER") is None, favicon=U.FAVICON if U.FAVICON.is_file() else "🐟")
