"""EFI+ calculator, Streamlit front-end.

Run with:  streamlit run app_streamlit.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from efiplus import __version__, ecoregion, engine, excel_io, schema as S, ui_common as U, validate

st.set_page_config(page_title=U.APP_TITLE, page_icon=str(U.FAVICON) if U.FAVICON.is_file() else "🐟", layout="wide")
if U.LOGO.is_file():
    st.logo(str(U.LOGO), size="large")
st.markdown(f"""<style>
  header[data-testid="stHeader"]::after {{content:""; position:absolute; left:0; right:0; bottom:0; height:5px;
      background:{U.STAR_STRIPE_CSS};}}
  [data-testid="stSidebarHeader"] img {{height:3.2rem;}}
  [data-testid="stHeading"] h1, .stMarkdown h1 {{color:{S.EFI_BLUE_DARK} !important;}}
  [data-testid="stMetricValue"] {{color:{S.EFI_BLUE_DARK};}}
</style>""", unsafe_allow_html=True)

ss = st.session_state
for k, v in {"raw1": None, "raw2": None, "source": None, "check": None, "result": None,
             "manual1": pd.DataFrame(columns=S.INPUT_COLUMNS),
             "manual2": pd.DataFrame(columns=S.DIAD_COLUMNS),
             "page": "Home", "rscript": engine.find_rscript() or "", "ecolayer": ""}.items():
    ss.setdefault(k, v)

if "_goto" in ss:
    ss.page = ss.pop("_goto")

PAGES = ["Home", "Insert data: Excel file", "Insert data: manual", "Check and run", "Results", "Help"]


def goto(page: str):
    ss.page = page


def jump(page: str):
    """Change page after the menu widget has been drawn."""
    ss._goto = page
    st.rerun()


def set_dataset(raw1, raw2, source):
    ss.read_notes = []
    ss.raw1, ss.raw2, ss.source = raw1, raw2, source
    ss.check = validate.check(raw1, raw2)
    ss.result = None


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"### {U.APP_TITLE}")
    st.caption(f"GUI v{__version__} · engine efitools-1.3")
    st.radio("Menu", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    st.markdown("**R engine**")
    ss.rscript = st.text_input("Path to Rscript", ss.rscript, help="Detected automatically when R is on the PATH "
                               "or in C:\\Program Files\\R. Set EFI_RSCRIPT to fix it permanently.")
    rs = engine.find_rscript(ss.rscript)
    missing = engine.check_engine()
    if rs and not missing:
        st.success(engine.r_version(rs), icon="✅")
    elif not rs:
        st.error("Rscript not found. Install R from cran.r-project.org.", icon="⛔")
    if missing:
        st.error("Engine files missing: " + ", ".join(missing), icon="⛔")
    st.markdown("**Ecoregion map** (optional)")
    ss.ecolayer = st.text_input("Path to the ecoregion layer", ss.ecolayer,
                                help="Optional. Polygon layer of the Illies ecoregions (.shp or .geojson, attribute AREA_ID = Illies number). Used to fill or check the ecoregion from the coordinates. Can also be set with EFI_ECOREG_LAYER or by copying the layer to local/ecoregions/.")
    ecoregion.set_layer(ss.ecolayer)
    eco_ok, eco_msg = ecoregion.status()
    (st.success if eco_ok else st.info)(eco_msg, icon="✅" if eco_ok else "ℹ️")
    if ss.source:
        st.divider()
        st.markdown(f"**Current dataset**  \n{ss.source}")


# ---------------------------------------------------------------- shared panels
def issues_panel(res: validate.CheckResult):
    n_s = res.input1[S.KEY_COLUMNS].drop_duplicates().shape[0] if not res.input1.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Samples", n_s)
    c2.metric("Species records", len(res.input1))
    c3.metric("Errors", len(res.errors))
    c4.metric("Warnings", len(res.warnings))
    if res.issues:
        f = res.issues_frame()
        f["row"] = f["row"].astype("Int64")
        st.dataframe(
            f.style.apply(lambda r: ["background-color:#f8d7da" if r.level == "error" else "background-color:#fff3cd"] * len(r), axis=1),
            hide_index=True, width="stretch",
            column_config={"row": st.column_config.NumberColumn("Excel row", format="%d")})
    if res.errors:
        st.error("Correct the errors in the original file (or in the form) and load it again. "
                 "The computation is blocked while errors remain.", icon="⛔")
    elif res.warnings:
        st.warning("No blocking error. Read the warnings before running the script.", icon="⚠️")
    else:
        st.success("No error, no warning.", icon="✅")


def run_button(res: validate.CheckResult):
    disabled = not res.ok or not engine.find_rscript(ss.rscript) or bool(engine.check_engine())
    if st.button("▶ Run script", type="primary", disabled=disabled, width="content"):
        with st.spinner("efitools-1.3 is running…"):
            try:
                r = engine.run(res.input1, res.input2, rscript=ss.rscript or None)
                ss.result = r
                jump("Results")
            except engine.EngineError as e:
                st.error(str(e))
                if e.log:
                    with st.expander("R log"):
                        st.code(e.log)


def show_r_inputs(res: validate.CheckResult):
    t1, t2 = st.tabs(["See the R-Input file", "See the R-Input-Diadromous file"])
    with t1:
        st.dataframe(res.input1, hide_index=True, width="stretch", height=300)
    with t2:
        if res.input2 is not None:
            st.dataframe(res.input2, hide_index=True, width="stretch", height=300)
        else:
            st.info("No diadromous data: main.R will be used (no diadromous index).")


# ---------------------------------------------------------------- pages
def page_home():
    c_logo, c_txt = st.columns([1, 3], vertical_alignment="center")
    if U.LOGO.is_file():
        c_logo.image(str(U.LOGO), width=260)
    c_txt.title(U.APP_TITLE)
    c_txt.markdown(U.APP_SUBTITLE)
    c_txt.caption("Improvement and Spatial Extension of the European Fish Index (EFI+ project, EC contract 044096)")
    cols = st.columns(len(U.WORKFLOW))
    for i, (col, (t, d)) in enumerate(zip(cols, U.WORKFLOW), start=1):
        with col.container(border=True):
            st.markdown(f"**{i}. {t}**")
            st.caption(d)
    st.markdown("#### Start")
    c1, c2, c3 = st.columns(3)
    c1.button("📄 Upload an Excel file", on_click=goto, args=("Insert data: Excel file",), width="stretch")
    c2.button("✏️ Enter a sample manually", on_click=goto, args=("Insert data: manual",), width="stretch")

    def load_example():
        from efiplus.examples import example_input1, example_input2
        set_dataset(example_input1(), example_input2(), "Example dataset (5 invented samples)")
        ss.page = "Check and run"
    c3.button("🧪 Try with the example data", on_click=load_example, width="stretch")
    st.caption("The example data are invented to show the workflow. They do not describe real sites.")


def page_excel():
    st.title("Insert data: Excel file")
    st.markdown(f"The spreadsheet has two sheets: **{S.SHEET_INPUT1}** (one row per sample × species) "
                f"and **{S.SHEET_INPUT2}** (optional, one row per sample). Missing values: `-999` for numbers, "
                "`NoData` for text.")
    c1, c2 = st.columns(2)
    c1.download_button("⬇ Blank EFI+ spreadsheet", excel_io.build_template(False),
                       "EFI+SpreadSheet.xlsx", width="stretch")
    c2.download_button("⬇ Filled example", excel_io.build_template(True),
                       "EFI+SpreadSheet_example.xlsx", width="stretch")
    up = st.file_uploader("EFI+ spreadsheet (.xlsx, .xls) or Input.txt (semicolon separated)",
                          type=["xlsx", "xls", "txt", "csv"])
    if up is not None and st.button("Send file", type="primary"):
        try:
            d1, d2, notes = excel_io.read_workbook(up.getvalue())
            set_dataset(d1, d2, f"File: {up.name}")
            ss.read_notes = notes
            jump("Check and run")
        except Exception as e:  # noqa: BLE001
            st.error(f"The file cannot be read: {e}")


def _site_form() -> dict:
    d = U.site_defaults()
    site = {}
    st.markdown("##### Location and date")
    c = st.columns(4)
    site["Site.code"] = c[0].text_input("Site code *", placeholder="e.g. DE0001").strip()
    day = c[1].date_input("Sampling date *", value=dt.date(2008, 9, 15), min_value=dt.date(1950, 1, 1),
                          max_value=dt.date.today(), format="DD/MM/YYYY")
    site["Day"], site["Month"], site["Year"] = day.day, day.month, day.year
    site["Longitude"] = c[2].number_input("Longitude *", -12.0, 40.0, value=None, format="%.6f")
    site["Latitude"] = c[3].number_input("Latitude *", 35.0, 72.0, value=None, format="%.6f")

    def num(col, name):
        v = S.VAR_BY_NAME[name]
        lab = f"{v.label}{' (' + v.unit + ')' if v.unit else ''} *"
        return col.number_input(lab, float(v.vmin), float(v.vmax), value=None, help=f"Range {v.vmin:g} to {v.vmax:g}")

    def cat(col, name):
        v = S.VAR_BY_NAME[name]
        return col.selectbox(v.label + (" *" if v.mandatory else ""), v.choices,
                             index=list(v.choices).index(d[name]), help=v.help or None)

    st.markdown("##### Environment")
    c = st.columns(4)
    eco_map, eco_txt = U.ecoregion_hint(site["Longitude"], site["Latitude"])
    v = S.VAR_BY_NAME["Ecoreg"]
    # The key changes with the map answer, so the box is reset to the ecoregion of the new coordinates.
    site["Ecoreg"] = c[0].selectbox(v.label + " *", v.choices, key=f"ecoreg_{eco_map}",
                                    index=list(v.choices).index(eco_map or d["Ecoreg"]), help=v.help)
    c[0].caption(eco_txt)
    site["Eft.type"] = cat(c[1], "Eft.type")
    site["Medit"] = cat(c[2], "Medit")
    site["Area.ctch"] = num(c[3], "Area.ctch")
    c = st.columns(4)
    site["Distance.from.source"] = num(c[0], "Distance.from.source")
    site["Actual.river.slope"] = num(c[1], "Actual.river.slope")
    site["Temp.jan"] = num(c[2], "Temp.jan")
    site["Temp.jul"] = num(c[3], "Temp.jul")
    c = st.columns(4)
    site["Geomorph.river.type"] = cat(c[0], "Geomorph.river.type")
    site["Floodplain.site"] = cat(c[1], "Floodplain.site")
    site["Water.source.type"] = cat(c[2], "Water.source.type")
    site["Natural.sediment"] = cat(c[3], "Natural.sediment")
    c = st.columns(4)
    site["Flow.regime"] = cat(c[0], "Flow.regime")
    site["Lakes.upstream"] = cat(c[1], "Lakes.upstream")
    st.markdown("##### Sampling")
    c = st.columns(4)
    site["Method"] = cat(c[0], "Method")
    site["Sampling.location"] = cat(c[1], "Sampling.location")
    site["Fished.area"] = num(c[2], "Fished.area")
    return site


def page_manual():
    st.title("Insert data: manual")
    st.caption("One sample at a time. Fields marked * are mandatory. Add as many samples as needed, "
               "then check and run. Manual data are not stored: download an Excel copy to keep them.")
    with st.container(border=True):
        site = _site_form()
        st.markdown("##### Fish caught in run 1")
        st.caption("Type to search the EFI+ species list. If '> 150 mm' is left empty it is computed as "
                   "total − '≤ 150 mm'. Numbers can be corrected in the table; select a row and press Delete to remove it.")
        ss.setdefault("sp_rows", U.empty_species_frame(0))
        c = st.columns([5, 2, 2, 2, 2], vertical_alignment="bottom")
        sp_name = c[0].selectbox("Species *", S.SPECIES, index=None, placeholder="Type to search…", key="sp_name")
        sp_tot = c[1].number_input("Total run 1 *", min_value=1, value=None, step=1, key="sp_tot")
        sp_below = c[2].number_input("≤ 150 mm *", min_value=0, value=None, step=1, key="sp_below")
        sp_over = c[3].number_input("> 150 mm", min_value=0, value=None, step=1, key="sp_over")

        def add_species():
            n, t, b, o = ss.sp_name, ss.sp_tot, ss.sp_below, ss.sp_over
            if not n or t is None or b is None:
                ss.sp_msg = "Species, total and number ≤ 150 mm are required."
                return
            o = o if o is not None else t - b
            if o < 0:
                ss.sp_msg = "Number ≤ 150 mm is larger than the total."
                return
            base = ss.get("sp_rows_edited", ss.sp_rows)
            base = base.dropna(subset=["Species"]) if not base.empty else ss.sp_rows
            ss.sp_rows = base.reset_index(drop=True)
            if n in set(ss.sp_rows["Species"]):
                ss.sp_msg = "Species already in the table."
                return
            ss.sp_rows = pd.concat([ss.sp_rows, pd.DataFrame([{
                "Species": n, "Total.number.run1": int(t), "Number.length.below.150": int(b),
                "Number.length.over.150": int(o)}])], ignore_index=True).astype(U.empty_species_frame(0).dtypes)
            ss.sp_msg = None
            ss.sp_name = ss.sp_tot = ss.sp_below = ss.sp_over = None
        c[4].button("➕ Add species", on_click=add_species, width="stretch")
        if ss.get("sp_msg"):
            st.warning(ss.sp_msg)
        sp = st.data_editor(
            ss.sp_rows, num_rows="dynamic", width="stretch", hide_index=True, disabled=["Species"],
            key=f"sp_editor_{len(ss.sp_rows)}_{ss.get('sp_reset', 0)}",
            column_config={
                "Species": st.column_config.TextColumn("Species", width="large"),
                "Total.number.run1": st.column_config.NumberColumn("Total run 1", min_value=1, step=1),
                "Number.length.below.150": st.column_config.NumberColumn("≤ 150 mm", min_value=0, step=1),
                "Number.length.over.150": st.column_config.NumberColumn("> 150 mm", min_value=0, step=1),
            })
        ss.sp_rows_edited = sp
        with st.expander("Diadromous species (optional)"):
            st.caption("Historical: Yes / No / NoData. Present: Yes / No. "
                       "If the species is present and no historical data exist, historical presence can be assumed.")
            dflt = pd.DataFrame({"Species": [s.strip() for s in S.DIADROMOUS_SPECIES],
                                 "historic": S.NODATA, "present": S.NODATA})
            use_diad = st.checkbox("Record diadromous species for this sample")
            diad = st.data_editor(dflt, hide_index=True, width="stretch", disabled=["Species"], key="diad_editor",
                                  column_config={
                                      "historic": st.column_config.SelectboxColumn(options=list(S.DIAD_CHOICES)),
                                      "present": st.column_config.SelectboxColumn(options=list(S.DIAD_CHOICES))})
        if st.button("➕ Add this sample", type="primary"):
            rows = U.build_manual_rows(site, sp)
            if not site["Site.code"]:
                st.error("Site code is mandatory.")
            elif rows.empty:
                st.error("Enter at least one species.")
            else:
                ss.manual1 = pd.concat([ss.manual1, rows], ignore_index=True)
                if use_diad:
                    rec = {c: S.NODATA for c in S.DIAD_SPECIES_COLUMNS}
                    for s_, r in zip(S.DIADROMOUS_SPECIES, diad.itertuples(index=False)):
                        rec[f"{s_} historic"], rec[f"{s_} present"] = r.historic, r.present
                    rec.update({k: site[k] for k in S.DIAD_KEY_COLUMNS})
                    ss.manual2 = pd.concat([ss.manual2, pd.DataFrame([rec])], ignore_index=True)
                ss.sp_rows = U.empty_species_frame(0)
                ss.pop("sp_rows_edited", None)
                ss.sp_reset = ss.get("sp_reset", 0) + 1
                ss.sp_added = f"Sample {site['Site.code']} added ({len(rows)} species)."
                st.rerun()
    if ss.get("sp_added"):
        st.success(ss.pop("sp_added"))

    st.markdown("#### Samples entered")
    m1 = ss.manual1
    if m1.empty:
        st.info("No sample yet.")
        return
    summary = m1.groupby(S.KEY_COLUMNS, sort=False).size().reset_index(name="Species")
    st.dataframe(summary, hide_index=True, width="stretch")
    c1, c2, c3 = st.columns(3)
    if c1.button("✔ Check these samples", type="primary", width="stretch"):
        set_dataset(m1.copy(), ss.manual2.copy() if not ss.manual2.empty else None,
                    f"Manual input ({len(summary)} samples)")
        jump("Check and run")
    c2.download_button("⬇ Get Excel copy of input data", excel_io.frames_to_excel_copy(m1, ss.manual2),
                       f"EFI+input_manual_{excel_io.timestamp()}.xlsx", width="stretch")
    if c3.button("🗑 Clear all samples", width="stretch"):
        ss.manual1 = pd.DataFrame(columns=S.INPUT_COLUMNS)
        ss.manual2 = pd.DataFrame(columns=S.DIAD_COLUMNS)
        st.rerun()


def page_check():
    st.title("Check and run")
    if ss.check is None:
        st.info("No data loaded yet.")
        c1, c2 = st.columns(2)
        c1.button("Upload an Excel file", on_click=goto, args=("Insert data: Excel file",))
        c2.button("Enter a sample manually", on_click=goto, args=("Insert data: manual",))
        return
    st.caption(ss.source)
    for n in ss.get("read_notes") or []:
        st.caption(n)
    res = ss.check
    issues_panel(res)
    if not res.input1.empty:
        show_r_inputs(res)
    run_button(res)


def _style_output(df: pd.DataFrame):
    def color(v):
        try:
            k = int(v)
            fg = "white" if k in (1, 2, 5) else "black"
            return f"background-color:{S.CLASS_COLORS[k]};color:{fg};font-weight:600"
        except (TypeError, ValueError, KeyError):
            return ""
    sty = df.style.format(precision=3, na_rep="NA")
    if "FishIndex.class" in df:
        sty = sty.map(color, subset=["FishIndex.class"])
    return sty


def page_results():
    st.title("Results")
    r = ss.result
    if r is None:
        st.info("Run the script first (menu Check and run).")
        return
    out = excel_io.order_output(r.output)
    st.caption(f"{ss.source} · {r.script} · {r.rscript}")
    summ = U.class_summary(out)
    cols = st.columns(len(summ) + 1)
    cols[0].metric("Samples", len(out))
    for col, row in zip(cols[1:], summ.itertuples(index=False)):
        col.metric(f"{row.Class or '–'} · {row.Status}", row.Samples)

    view = st.segmented_control("View", ["Summary", "All columns", *S.OUTPUT_GROUPS], default="Summary")
    if view == "Summary":
        cols_ = ["Site.code", "Day", "Month", "Year", "Ecoregion", "River.zone", "FishIndex", "FishIndex.class",
                 "Comments.river.zone", "Comments.sampling.effort", "Comments.sampling.location", "Comments.method"]
        df = out[[c for c in cols_ if c in out]]
    elif view in S.OUTPUT_GROUPS:
        df = out[["Site.code"] + [c for c in S.OUTPUT_GROUPS[view] if c in out and c != "Site.code"]]
    else:
        df = out
    st.dataframe(_style_output(df), hide_index=True, width="stretch")

    if "FishIndex" in out and out["FishIndex"].notna().any():
        st.markdown("##### Fish index by sample")
        import altair as alt
        dd = out[["Site.code", "FishIndex", "FishIndex.class"]].dropna(subset=["FishIndex"]).copy()
        dd = dd.rename(columns={"Site.code": "Site", "FishIndex.class": "Class"})
        dd["Status"] = dd["Class"].map(lambda k: S.CLASS_LABELS.get(int(k), "NA") if pd.notna(k) else "NA")
        chart = alt.Chart(dd).mark_bar().encode(
            x=alt.X("Site:N", sort=None, title=None),
            y=alt.Y("FishIndex:Q", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("Status:N", scale=alt.Scale(domain=list(S.CLASS_LABELS.values()),
                                                        range=list(S.CLASS_COLORS.values())), title="Class"),
            tooltip=["Site", alt.Tooltip("FishIndex:Q", format=".3f"), "Status"]).properties(height=260)
        st.altair_chart(chart, width="stretch")

    meta = {"Source": ss.source, "Script": r.script, "Rscript": r.rscript,
            "R version": engine.r_version(r.rscript), "GUI version": __version__,
            "Date": dt.datetime.now().isoformat(timespec="seconds")}
    xlsx = excel_io.build_output_workbook(r.output, ss.check.input1, ss.check.input2, r.log, meta)
    c1, c2 = st.columns(2)
    c1.download_button("⬇ NewEFI+output.xlsx", xlsx, f"NewEFI+output_{excel_io.timestamp()}.xlsx",
                       type="primary", width="stretch")
    c2.download_button("⬇ output.txt (raw R output)", r.output.to_csv(sep=";", index=False),
                       "output.txt", width="stretch")
    with st.expander("R log (info.out)"):
        st.code(r.log)


def page_help():
    st.title("Help")
    t1, t2, t3, t4, t5 = st.tabs(["Input variables", "Output", "Comments", "Documents", "Engine notes"])
    with t1:
        st.caption("Manual Part II, Tables 14 and 16, and efitools-1.3 exchange format. "
                   "Missing values: -999 (numbers), NoData (text).")
        st.dataframe(U.variables_table(), hide_index=True, width="stretch", height=560)
        with st.expander(f"Species list ({len(S.SPECIES)})"):
            st.dataframe(pd.DataFrame({"Species": S.SPECIES}), hide_index=True, height=300)
    with t2:
        st.dataframe(pd.DataFrame([{"Group": g, "Column": c, "Definition": U.OUTPUT_DEFINITIONS.get(c, "")}
                                   for g, cs in S.OUTPUT_GROUPS.items() for c in cs]),
                     hide_index=True, width="stretch", height=560)
    with t3:
        st.dataframe(U.COMMENTS_TABLE, hide_index=True, width="stretch")
    with t4:
        docs = U.docs_available()
        if not docs:
            st.info("Put the PDF manuals in the docs/ folder to make them available here.")
        for p in docs:
            st.download_button(f"📘 {p.name}", p.read_bytes(), p.name, mime="application/pdf")
        st.markdown("[R Project](https://www.r-project.org) · "
                    "[European River and Catchment Database (CCM2)](https://ccm.jrc.ec.europa.eu)")
    with t5:
        st.markdown("**Remaining issue (not corrected)**")
        for i in U.KNOWN_ENGINE_ISSUES:
            st.markdown(f"- {i}")
        st.markdown("**Changes in efitools-1.3**")
        for i in U.ENGINE_CHANGES:
            st.markdown(f"- {i}")
        st.caption("Compatibility changes in main.R and maindiad.R: directory read from EFI_DIR, absolute file "
                   "paths accepted, arguments read with commandArgs(trailingOnly = TRUE), comment.char = \"\" "
                   "(the original '£' is not a single byte in UTF-8). See CHANGES.txt in the engine folder.")


{"Home": page_home, "Insert data: Excel file": page_excel, "Insert data: manual": page_manual,
 "Check and run": page_check, "Results": page_results, "Help": page_help}[ss.page]()
