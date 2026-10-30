"""Bridge to the R engine efitools-1.3 (main.R / maindiad.R) through Rscript."""
from __future__ import annotations

import functools
import glob
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import schema as S

ENGINE_DIR = Path(os.environ.get("EFI_ENGINE_DIR", Path(__file__).resolve().parent.parent / "engine"))

R_ERRORS = {
    "-1": "non convenient command",
    "0": "non convenient arguments",
    "1": "input file cannot be read",
    "2": "efiminus.R is absent",
    "3": "internal.zip is absent",
    "4": "input file does not contain the required columns",
    "5": "diadromous input file cannot be read",
    "6": "output file cannot be written",
}


class EngineError(RuntimeError):
    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


@dataclass
class RunResult:
    output: pd.DataFrame
    log: str
    script: str
    rscript: str
    workdir: str | None   # folder with input/output files, None when it was a temporary folder (deleted)


def find_rscript(user_path: str | None = None) -> str | None:
    """Locate Rscript: explicit path, EFI_RSCRIPT, PATH, then usual Windows/macOS locations."""
    for cand in (user_path, os.environ.get("EFI_RSCRIPT")):
        if cand and Path(cand).is_file():
            return str(cand)
    found = shutil.which("Rscript")
    if found:
        return found
    patterns = [
        r"C:\Program Files\R\R-*\bin\Rscript.exe",
        r"C:\Program Files\R\R-*\bin\x64\Rscript.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\R\R-*\bin\Rscript.exe"),
        "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        "/opt/homebrew/bin/Rscript", "/usr/local/bin/Rscript",
    ]
    hits = []
    for p in patterns:
        hits += glob.glob(p)
    if not hits:
        return None

    def ver(p):
        m = re.search(r"R-(\d+)\.(\d+)\.(\d+)", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    return sorted(hits, key=ver)[-1]


@functools.lru_cache(maxsize=8)
def r_version(rscript: str) -> str:
    """First line of 'Rscript --version' (cached: the GUI asks for it on every refresh)."""
    try:
        r = subprocess.run([rscript, "--version"], capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip().splitlines()[0]
    except Exception as e:  # noqa: BLE001
        return f"unknown ({e})"


def check_engine() -> list[str]:
    """Return the list of missing engine files (empty list = engine complete)."""
    need = ["main.R", "maindiad.R", "internal/efiminus.R", "internal/internal.zip",
            "internal/inputplus.txt", "internal/diadromousplus.txt"]
    return [n for n in need if not (ENGINE_DIR / n).is_file()]


def _write_txt(df: pd.DataFrame, path: Path, columns: list[str]):
    df = df[columns].copy()
    for c in df.columns:
        df[c] = df[c].map(lambda v: "" if v is None else (f"{v:.10g}" if isinstance(v, float) else str(v)))
    df.to_csv(path, sep=";", index=False, lineterminator="\n", encoding="utf-8")


def complete_input2(input1: pd.DataFrame, input2: pd.DataFrame) -> pd.DataFrame:
    """Add a NoData diadromous record for samples of input1 absent from input2."""
    k1 = input1.drop_duplicates(S.KEY_COLUMNS)[S.DIAD_KEY_COLUMNS]
    key = lambda d: d[S.KEY_COLUMNS].astype(str).agg("_".join, axis=1)  # noqa: E731
    miss = k1[~key(k1).isin(set(key(input2)))]
    if miss.empty:
        return input2
    add = miss.copy()
    for c in S.DIAD_SPECIES_COLUMNS:
        add[c] = S.NODATA
    return pd.concat([input2, add[S.DIAD_COLUMNS]], ignore_index=True)


def run(input1: pd.DataFrame, input2: pd.DataFrame | None = None, rscript: str | None = None,
        timeout: int = 600, keep_dir: str | None = None) -> RunResult:
    """Write input.txt (and diadromous.txt), run the R script, read output.txt."""
    missing = check_engine()
    if missing:
        raise EngineError(f"efitools-1.3 engine incomplete in {ENGINE_DIR}: missing {', '.join(missing)}")
    rs = find_rscript(rscript)
    if not rs:
        raise EngineError("Rscript not found. Install R (https://cran.r-project.org) or give the path to Rscript.")

    if keep_dir:
        work = Path(keep_dir)
        work.mkdir(parents=True, exist_ok=True)
        return _run_in(work, rs, input1, input2, timeout, keep=True)
    with tempfile.TemporaryDirectory(prefix="efiplus_") as tmp:
        return _run_in(Path(tmp), rs, input1, input2, timeout, keep=False)


def _run_in(work: Path, rs: str, input1: pd.DataFrame, input2: pd.DataFrame | None,
            timeout: int, keep: bool) -> RunResult:
    inp, out = work / "input.txt", work / "output.txt"
    _write_txt(input1, inp, S.INPUT_COLUMNS)
    args = [rs, "--vanilla", str(ENGINE_DIR / "main.R"), str(inp), str(out)]
    script = "main.R"
    if input2 is not None and not input2.empty:
        diad = work / "diadromous.txt"
        _write_txt(complete_input2(input1, input2), diad, S.DIAD_COLUMNS)
        args = [rs, "--vanilla", str(ENGINE_DIR / "maindiad.R"), str(inp), str(out), str(diad)]
        script = "maindiad.R"

    env = dict(os.environ, EFI_DIR=str(ENGINE_DIR), LANG="C.UTF-8", LC_ALL="C.UTF-8")
    if os.name == "nt":
        env.pop("LC_ALL")
        env.pop("LANG")
    try:
        proc = subprocess.run(args, cwd=str(ENGINE_DIR), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise EngineError(f"R computation stopped after {timeout} s.", str(e.stdout or "")) from e
    log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    (work / "info.out").write_text(log, encoding="utf-8")

    if proc.returncode != 0 or not out.is_file():
        m = re.search(r"Error (-?\d+):", log)
        msg = f"R error {m.group(1)}: {R_ERRORS.get(m.group(1), '')}" if m else "R computation failed."
        tail = [l for l in log.splitlines() if l.strip()][-6:]
        raise EngineError(msg + "\n" + "\n".join(tail), log)

    res = pd.read_csv(out, sep=";", na_values=["NA", "NaN"], keep_default_na=True)
    return RunResult(output=res, log=log, script=script, rscript=rs, workdir=str(work) if keep else None)
