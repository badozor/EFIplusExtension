"""Checks of the input data before the R computation (manual Part II, 4.1-4.2).

Categorical data are checked against the list of allowed classes, numerical
variables against the ranges of Table 16. Errors block the computation,
warnings do not.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd

from . import schema as S


@dataclass
class Issue:
    sheet: str
    row: int | None      # 1-based row number as seen in Excel (header = row 1)
    column: str
    value: str
    level: str           # "error" or "warning"
    message: str


@dataclass
class CheckResult:
    input1: pd.DataFrame
    input2: pd.DataFrame | None
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def issues_frame(self) -> pd.DataFrame:
        cols = ["sheet", "row", "column", "value", "level", "message"]
        f = pd.DataFrame([asdict(i) for i in self.issues], columns=cols)
        f["_lvl"] = (f["level"] != "error").astype(int)
        f["_row"] = pd.to_numeric(f["row"], errors="coerce").fillna(0)
        return f.sort_values(["sheet", "_lvl", "_row"], kind="stable").drop(columns=["_lvl", "_row"]).reset_index(drop=True)


def _isnum(v) -> bool:
    return pd.api.types.is_number(v) and not isinstance(v, bool)


def _is_missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"nodata", "na", "nan", "-999", "-999.0"}


def _rename_columns(df: pd.DataFrame, expected: list[str]) -> pd.DataFrame:
    """Map tolerant header spellings onto the exact names used by R."""
    lookup = {S.norm_header(c): c for c in expected}
    mapping = {}
    for c in df.columns:
        key = S.norm_header(c)
        if key in lookup:
            mapping[c] = lookup[key]
    return df.rename(columns=mapping)


def _to_number(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip().replace(",", ".")
    return float(s)


def check_input1(df: pd.DataFrame, sheet: str = S.SHEET_INPUT1) -> tuple[pd.DataFrame, list[Issue]]:
    issues: list[Issue] = []
    df = _rename_columns(df.copy(), S.INPUT_COLUMNS)
    df = df.dropna(how="all")
    df.index = range(2, len(df) + 2)  # Excel row numbers

    missing_cols = [v.name for v in S.INPUT_VARS if v.name not in df.columns]
    for name in missing_cols:
        v = S.VAR_BY_NAME[name]
        if v.mandatory:
            issues.append(Issue(sheet, None, name, "", "error", "Mandatory column is missing."))
        else:
            issues.append(Issue(sheet, None, name, "", "warning",
                                "Optional column is missing: filled with NoData."))
            df[name] = S.NODATA
    if any(i.level == "error" for i in issues):
        return df, issues
    if df.empty:
        issues.append(Issue(sheet, None, "", "", "error", "The sheet contains no data row."))
        return df, issues

    out = pd.DataFrame(index=df.index)
    for v in S.INPUT_VARS:
        col = []
        for r, raw in df[v.name].items():
            if _is_missing(raw):
                if v.kind in ("int", "float"):
                    if v.mandatory:
                        issues.append(Issue(sheet, r, v.name, "", "error" if v.level == "species" or v.name in S.KEY_COLUMNS else "warning",
                                            "Missing value (coded -999)."))
                    col.append(S.NA_NUM)
                else:
                    if v.name in ("Site.code", "Species", "Ecoreg", "Eft.type"):
                        issues.append(Issue(sheet, r, v.name, "", "error", "Missing value."))
                    elif v.mandatory:
                        issues.append(Issue(sheet, r, v.name, "", "warning", "Missing value (coded NoData)."))
                    col.append(S.NODATA)
                continue

            if v.kind in ("int", "float"):
                try:
                    num = _to_number(raw)
                except (TypeError, ValueError):
                    issues.append(Issue(sheet, r, v.name, str(raw), "error", "Not a number."))
                    col.append(S.NA_NUM)
                    continue
                if v.kind == "int":
                    if float(num) != int(float(num)):
                        issues.append(Issue(sheet, r, v.name, str(raw), "error", "Integer expected."))
                    num = int(float(num))
                if v.choices and num not in v.choices:
                    issues.append(Issue(sheet, r, v.name, str(raw), "error",
                                        f"Allowed values: {', '.join(map(str, v.choices))}."))
                elif (v.vmin is not None and num < v.vmin) or (v.vmax is not None and num > v.vmax):
                    issues.append(Issue(sheet, r, v.name, str(raw), "error",
                                        f"Out of range [{v.vmin:g}; {v.vmax:g}]{' ' + v.unit if v.unit else ''}."))
                col.append(num)
            else:
                s = " ".join(str(raw).split())
                if v.name == "Species":
                    s2 = s.replace(".", " ")
                    s2 = " ".join(s2.split()).lower()
                    s2 = s2[:1].upper() + s2[1:]
                    if s2 not in S.SPECIES:
                        issues.append(Issue(sheet, r, v.name, s, "warning",
                                            "Species not in the EFI+ guild table: ignored by the metrics."))
                    col.append(s2)
                    continue
                if v.kind == "cat":
                    canon = {str(c).lower(): c for c in v.choices}
                    canon.update({a.lower(): c for a, c in v.aliases.items()})
                    if s.lower() in canon:
                        new = canon[s.lower()]
                        if new != s and s.lower() not in {str(c).lower() for c in v.choices}:
                            issues.append(Issue(sheet, r, v.name, s, "warning", f"Recoded as '{new}'."))
                        s = new
                        if s == S.NODATA and v.name in ("Floodplain.site", "Water.source.type",
                                                        "Geomorph.river.type", "Natural.sediment", "Method"):
                            issues.append(Issue(sheet, r, v.name, s, "warning",
                                                "NoData: expected values or class may not be computed."))
                    else:
                        issues.append(Issue(sheet, r, v.name, s, "error",
                                            f"Allowed values: {', '.join(map(str, v.choices))}."))
                col.append(s)
        out[v.name] = col

    # Length classes must add up to the total of run 1 (checked by ValidatedLength in R).
    for r in out.index:
        t, b, o = (out.at[r, c] for c in ("Total.number.run1", "Number.length.below.150", "Number.length.over.150"))
        if S.NA_NUM not in (t, b, o) and all(_isnum(x) for x in (t, b, o)) and b + o != t:
            issues.append(Issue(sheet, r, "Total.number.run1", f"{t} ≠ {b} + {o}", "warning",
                                "Length classes do not add up to the total: length-based metric set to NA."))

    # Day/month validity and sampling period.
    for r in out.index:
        d, m, y = out.at[r, "Day"], out.at[r, "Month"], out.at[r, "Year"]
        if S.NA_NUM not in (d, m, y):
            try:
                pd.Timestamp(year=int(y), month=int(m), day=int(d))
            except ValueError:
                issues.append(Issue(sheet, r, "Day", f"{d}/{m}/{y}", "error", "Invalid date."))

    # Site variables must be constant within one fishing occasion.
    key = out[S.KEY_COLUMNS].astype(str).agg("_".join, axis=1)
    for v in S.SAMPLE_VARS:
        if v.name in S.KEY_COLUMNS:
            continue
        nun = out.groupby(key)[v.name].nunique()
        for k in nun[nun > 1].index:
            rows = list(out.index[key == k])
            issues.append(Issue(sheet, rows[0], v.name, k, "error",
                                f"Different values within the same sample (rows {rows[0]}-{rows[-1]}): "
                                "site variables must be identical for all species of a sample."))
    dup = out.duplicated(subset=S.KEY_COLUMNS + ["Species"], keep=False)
    for r in out.index[dup]:
        issues.append(Issue(sheet, r, "Species", out.at[r, "Species"], "error",
                            "Species recorded twice for the same sample."))

    # Months outside the EFI+ sampling period (August to November): warning only.
    for r in out.index:
        m = out.at[r, "Month"]
        if m != S.NA_NUM and _isnum(m) and not 8 <= m <= 11:
            issues.append(Issue(sheet, r, "Month", str(m), "warning",
                                "Outside the EFI+ sampling period (August to November)."))
    return out, _dedupe_month_warnings(issues, out)


def _dedupe_month_warnings(issues: list[Issue], out: pd.DataFrame) -> list[Issue]:
    """Keep one 'sampling period' warning per sample instead of one per species row."""
    seen, res = set(), []
    key = out[S.KEY_COLUMNS].astype(str).agg("_".join, axis=1)
    for i in issues:
        if i.message.startswith("Outside the EFI+ sampling period") and i.row in key.index:
            k = key[i.row]
            if k in seen:
                continue
            seen.add(k)
        res.append(i)
    return res


def check_input2(df: pd.DataFrame, input1: pd.DataFrame, sheet: str = S.SHEET_INPUT2):
    issues: list[Issue] = []
    df = _rename_columns(df.copy(), S.DIAD_COLUMNS)
    df = df.dropna(how="all")
    if df.empty:
        return None, issues
    df.index = range(2, len(df) + 2)
    for c in S.DIAD_KEY_COLUMNS[:4]:
        if c not in df.columns:
            issues.append(Issue(sheet, None, c, "", "error", "Mandatory column is missing."))
    if issues:
        return None, issues

    out = pd.DataFrame(index=df.index)
    for c in S.DIAD_SPECIES_COLUMNS:
        if c not in df.columns:
            issues.append(Issue(sheet, None, c.strip(), "", "warning", "Column missing: filled with NoData."))
            out[c] = S.NODATA
            continue
        vals = []
        for r, raw in df[c].items():
            if _is_missing(raw):
                vals.append(S.NODATA)
                continue
            s = str(raw).strip().lower()
            m = {"yes": "Yes", "no": "No", "1": "Yes", "0": "No", "1.0": "Yes", "0.0": "No", "true": "Yes", "false": "No"}
            if s in m:
                vals.append(m[s])
            else:
                issues.append(Issue(sheet, r, c.strip(), str(raw), "error", "Allowed values: Yes, No, NoData."))
                vals.append(S.NODATA)
        out[c] = vals
    for c in S.DIAD_KEY_COLUMNS:
        out[c] = df[c] if c in df.columns else S.NA_NUM
    for c in ("Day", "Month", "Year"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(S.NA_NUM).astype(int)
    out["Site.code"] = out["Site.code"].astype(str).str.strip()

    k1 = set(input1[S.KEY_COLUMNS].astype(str).agg("_".join, axis=1))
    k2 = out[S.KEY_COLUMNS].astype(str).agg("_".join, axis=1)
    for r, k in k2.items():
        if k not in k1:
            issues.append(Issue(sheet, r, "Site.code", k, "error",
                                "No matching sample (Site code + date) in input1."))
    for r in out.index[k2.duplicated(keep=False)]:
        issues.append(Issue(sheet, r, "Site.code", k2[r], "error", "Sample recorded twice."))
    missing = sorted(k1 - set(k2))
    if missing:
        issues.append(Issue(sheet, None, "Site.code", ", ".join(missing[:5]) + (" …" if len(missing) > 5 else ""),
                            "warning", f"{len(missing)} sample(s) of input1 have no diadromous record: "
                            "diadromous index computed from NoData."))
    return out[S.DIAD_COLUMNS], issues


def check(input1: pd.DataFrame, input2: pd.DataFrame | None = None) -> CheckResult:
    clean1, issues = check_input1(input1)
    clean2 = None
    if input2 is not None and not issues_have_errors(issues):
        clean2, iss2 = check_input2(input2, clean1)
        issues += iss2
    return CheckResult(clean1, clean2, issues)


def issues_have_errors(issues) -> bool:
    return any(i.level == "error" for i in issues)
