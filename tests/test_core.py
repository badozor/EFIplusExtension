import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from efiplus import schema as S, validate, engine, excel_io
from efiplus.examples import example_input1, example_input2

def test_example_runs_and_matches_direct_r():
    res = validate.check(example_input1(), example_input2())
    assert res.ok, res.issues_frame()
    r = engine.run(res.input1, res.input2)
    assert r.script == "maindiad.R" and len(r.output) == 5
    ref = pd.read_csv(Path(__file__).parent / "data" / "out_diad.txt", sep=";")
    pd.testing.assert_frame_equal(r.output.sort_values("Site.code").reset_index(drop=True),
                                  ref.sort_values("Site.code").reset_index(drop=True), check_dtype=False)
    assert r.output.set_index("Site.code").loc["PL0005", "FishIndex.class"] == 5

def test_diadromous_labels_fixed_in_v13():
    res = validate.check(example_input1(), example_input2())
    o = engine.run(res.input1, res.input2).output.set_index("Site.code")
    # ES0004: eel historic+present, salmon historic only -> 2 historic, 1 present
    assert o.loc["ES0004", "Hist.ric.diadromous"] == 2 and o.loc["ES0004", "Present.ric.diadromous"] == 1
    assert (o["Hist.ric.diadromous"] >= o["Present.ric.diadromous"]).all()
    ratio = (o["Present.ric.diadromous"] / o["Hist.ric.diadromous"]).round(6)
    assert ratio.equals(o["Ids.ric.diadromous"].round(6))

def test_temporary_folder_removed(tmp_path):
    import tempfile, glob, os
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "efiplus_*")))
    res = validate.check(example_input1())
    r = engine.run(res.input1, None)
    assert r.workdir is None
    assert set(glob.glob(os.path.join(tempfile.gettempdir(), "efiplus_*"))) == before
    r = engine.run(res.input1, None, keep_dir=str(tmp_path / "run"))
    assert (tmp_path / "run" / "output.txt").is_file() and (tmp_path / "run" / "info.out").is_file()

def test_main_without_diadromous():
    res = validate.check(example_input1())
    r = engine.run(res.input1, None)
    assert r.script == "main.R" and "Ids.ric.diadromous" not in r.output.columns

def test_month_and_length_warnings():
    df = example_input1()
    df.loc[0, "Number.length.over.150"] = 99
    res = validate.check(df)
    f = res.issues_frame()
    w = f[f.level == "warning"]
    assert (w.message.str.startswith("Outside the EFI+ sampling period")).sum() == 1   # PL0005, once per sample
    assert ((w.column == "Total.number.run1") & (w.row == 2)).any()

def test_template_roundtrip():
    b = excel_io.build_template(example=True)
    i1, i2, notes = excel_io.read_workbook(b)
    res = validate.check(i1, i2)
    assert res.ok, res.issues_frame()
    assert len(res.warnings) == 1
    assert len(res.input1) == len(example_input1()) and len(res.input2) == 5

def test_errors_detected():
    df = example_input1().astype(object)
    df.loc[0, "Latitude"] = 80          # out of range
    df.loc[1, "Method"] = "Helicopter"  # bad modality
    df.loc[2, "Geomorph.river.type"] = "Meandering regular"  # alias -> warning
    df.loc[3, "Total.number.run1"] = "abc"
    res = validate.check(df)
    f = res.issues_frame()
    errs = set(zip(f[f.level == "error"].row, f[f.level == "error"].column))
    assert (2, "Latitude") in errs and (3, "Method") in errs and (5, "Total.number.run1") in errs
    assert ((f.level == "warning") & (f.column == "Geomorph.river.type")).any()
    assert res.input1.loc[4, "Geomorph.river.type"] == "Meand regular"
    # Latitude differs within CH0001 -> consistency error too
    assert ((f.message.str.startswith("Different values")) & (f.column == "Latitude")).any()

def test_diadromous_unmatched_and_completion():
    i2 = example_input2().iloc[:3].copy()
    res = validate.check(example_input1(), i2)
    assert res.ok and any("no diadromous record" in i.message for i in res.warnings)
    r = engine.run(res.input1, res.input2)
    assert r.output["Ids.ric.diadromous"].notna().sum() >= 3
    i2.loc[0, "Site.code"] = "XX9999"
    res = validate.check(example_input1(), i2)
    assert not res.ok

def test_output_workbook():
    res = validate.check(example_input1(), example_input2())
    r = engine.run(res.input1, res.input2)
    b = excel_io.build_output_workbook(r.output, res.input1, res.input2, r.log, {"R": "x"})
    x = pd.read_excel(io.BytesIO(b), sheet_name=None, header=1)
    assert "EFI+ output" in x and len(x["EFI+ output"]) == 5
