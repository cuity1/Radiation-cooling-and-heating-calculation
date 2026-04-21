from __future__ import annotations

"""
Server-side MODTRAN (PcMod5) runner.

This module is intentionally self-contained and Windows-oriented:
- PcMod5 uses fixed filenames (tape5/tape6/tape7/pltout.*) in Bin directory,
  so we serialize execution with a process-wide lock.
- Each run is copied into a per-user run directory under data/modtran/{user_id}/{run_id}/.
"""

import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..settings import settings
from .modtran_ltn import LtnParams, apply_params_to_lines, load_ltn_params, save_ltn_lines
from .modtran_parser import df_preview, parse_spectrum_file, to_wavelength

# Fixed PcMod5 install path (user confirmed)
PCMOD_BIN_DIR = Path(r"D:\academic_tool\Pcmod5\Bin")
PCMOD_USR_DIR = Path(r"D:\academic_tool\Pcmod5\Usr")

# PcMod5 writes to fixed tape* names in Bin, so avoid concurrent runs.
_RUN_LOCK = threading.Lock()


@dataclass
class RunOutputs:
    run_id: str
    run_dir: Path
    freq_csv: Path
    wavelength_csv: Path
    excel: Optional[Path]
    site_dll: Optional[Path]
    tape6: Optional[Path]
    tape7: Optional[Path]
    source_file: Path
    duration_sec: float
    stdout: str
    stderr: str


class ModtranRunner:
    def __init__(
        self,
        *,
        bin_dir: Path = PCMOD_BIN_DIR,
        usr_dir: Path = PCMOD_USR_DIR,
        runs_root: Path = settings.data_dir / "modtran",
        exe_name: str = "Mod5.2.1.0.exe",
    ):
        self.bin_dir = bin_dir
        self.usr_dir = usr_dir
        self.runs_root = runs_root

        exe = self.bin_dir / exe_name
        if not exe.exists():
            for alt in ("PcModWin5.exe", "MODF37.EXE"):
                cand = self.bin_dir / alt
                if cand.exists():
                    exe = cand
                    break
        self.exe_path = exe

        self.runs_root.mkdir(parents=True, exist_ok=True)

    def _default_dll_template_path(self) -> Path:
        # Repo default DLL template (two columns: wavelength_um \t value)
        return Path(__file__).resolve().parents[2] / "default" / "1967.dll"

    def _make_site_dll(self, df_wl: pd.DataFrame, out_path: Path) -> Optional[Path]:
        """
        Create a .dll file based on default/1967.dll wavelength grid, using
        (Wavelength_um, Transmittance) from df_wl with linear interpolation.
        """
        tpl = self._default_dll_template_path()
        if not tpl.exists():
            return None

        if "Wavelength_um" not in df_wl.columns or "Transmittance" not in df_wl.columns:
            return None

        # Read template wavelengths
        tpl_wl: List[float] = []
        for ln in tpl.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.replace(",", " ").split()
            if len(parts) < 1:
                continue
            try:
                tpl_wl.append(float(parts[0]))
            except Exception:
                continue
        if not tpl_wl:
            return None

        # Source arrays (sorted by wavelength)
        src = df_wl[["Wavelength_um", "Transmittance"]].dropna().copy()
        if src.empty:
            return None
        src = src.sort_values("Wavelength_um")
        x = src["Wavelength_um"].to_numpy(dtype=float)
        y = src["Transmittance"].to_numpy(dtype=float)
        if x.size < 2:
            return None

        # Interpolate on template wavelength grid; clamp to [0,1]
        wl_grid = np.array(tpl_wl, dtype=float)
        y_grid = np.interp(wl_grid, x, y, left=float(y[0]), right=float(y[-1]))
        y_grid = np.clip(y_grid, 0.0, 1.0)

        # Write with tab delimiter (same style as default dll)
        lines = [f"{wl:g}\t{val:.6g}" for wl, val in zip(wl_grid.tolist(), y_grid.tolist())]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out_path

    def _safe_template_path(self, name: str) -> Path:
        if not name or any(ch in name for ch in ("/", "\\", "..")):
            raise ValueError("非法模板文件名")
        p = self.usr_dir / name
        if not p.exists():
            raise FileNotFoundError(f"模板不存在: {p}")
        return p

    def list_templates(self) -> List[str]:
        if not self.usr_dir.exists():
            return []
        items: List[str] = []
        for p in sorted(self.usr_dir.glob("*.ltn")):
            if ".bak_" in p.name:
                continue
            items.append(p.name)
        return items

    def load_template_params(self, name: str) -> Dict:
        p = self._safe_template_path(name)
        lines, params = load_ltn_params(p)
        return {"lines": lines[:7], "params": params}

    def run_with_params(
        self,
        *,
        template_name: str,
        params: LtnParams,
        user_id: int,
        export_excel: bool = True,
        timeout: int = 600,
    ) -> RunOutputs:
        template_path = self._safe_template_path(template_name)
        lines, _ = load_ltn_params(template_path)
        new_lines = apply_params_to_lines(lines, params)

        run_id = uuid.uuid4().hex
        run_dir = self.runs_root / str(int(user_id)) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        ltn_out = run_dir / template_name
        save_ltn_lines(new_lines, ltn_out)

        if not self.exe_path.exists():
            raise FileNotFoundError(f"PcMod5 可执行文件不存在: {self.exe_path}")

        # Run PcMod5 in Bin directory (it reads tape5 and writes tape6/tape7/pltout.*)
        with _RUN_LOCK:
            tape5_path = self.bin_dir / "tape5"
            shutil.copy(ltn_out, tape5_path)

            start = time.time()
            proc = subprocess.run(
                [str(self.exe_path)],
                cwd=str(self.bin_dir),
                capture_output=True,
                text=True,
                timeout=int(timeout),
            )
            duration = time.time() - start

            if proc.returncode != 0:
                raise RuntimeError(f"MODTRAN 运行失败 (exit={proc.returncode}): {proc.stderr.strip()}")

            # Copy raw outputs into run_dir for debugging & downloads
            tape6_src = self.bin_dir / "tape6"
            tape7_src = self.bin_dir / "tape7"
            pltout_asc = self.bin_dir / "pltout.asc"
            pltout_scn = self.bin_dir / "pltout.scn"

            tape6_dst: Optional[Path] = None
            tape7_dst: Optional[Path] = None
            if tape6_src.exists():
                tape6_dst = run_dir / "tape6"
                shutil.copy(tape6_src, tape6_dst)
            if tape7_src.exists():
                tape7_dst = run_dir / "tape7"
                shutil.copy(tape7_src, tape7_dst)
            if pltout_asc.exists():
                shutil.copy(pltout_asc, run_dir / "pltout.asc")
            if pltout_scn.exists():
                shutil.copy(pltout_scn, run_dir / "pltout.scn")

        # Choose spectrum source: tape7 -> pltout.asc -> pltout.scn
        spectrum_path: Optional[Path] = None
        if tape7_dst and tape7_dst.exists():
            spectrum_path = tape7_dst
        elif (run_dir / "pltout.asc").exists():
            spectrum_path = run_dir / "pltout.asc"
        elif (run_dir / "pltout.scn").exists():
            spectrum_path = run_dir / "pltout.scn"
        else:
            raise FileNotFoundError("未找到 tape7 / pltout 输出文件")

        df = parse_spectrum_file(spectrum_path)

        freq_csv = run_dir / "modtran_freq.csv"
        wl_csv = run_dir / "modtran_wavelength.csv"
        excel_path = run_dir / "modtran.xlsx"

        df.to_csv(freq_csv, index=False, encoding="utf-8-sig")
        df_wl = to_wavelength(df)
        df_wl.to_csv(wl_csv, index=False, encoding="utf-8-sig")

        # Create a local-use dll from wavelength csv
        site_dll: Optional[Path] = None
        try:
            site_dll = self._make_site_dll(df_wl, run_dir / "site_transmittance.dll")
        except Exception:
            site_dll = None

        excel_written: Optional[Path] = None
        if export_excel:
            try:
                with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Frequency")
                    df_wl.to_excel(writer, index=False, sheet_name="Wavelength")
                excel_written = excel_path
            except Exception:
                # Excel export is optional; don't fail the run.
                excel_written = None

        return RunOutputs(
            run_id=run_id,
            run_dir=run_dir,
            freq_csv=freq_csv,
            wavelength_csv=wl_csv,
            excel=excel_written,
            site_dll=site_dll,
            tape6=tape6_dst,
            tape7=tape7_dst,
            source_file=spectrum_path,
            duration_sec=duration,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


def summarize_run(run: RunOutputs) -> Dict:
    downloads: Dict[str, str] = {
        "freq_csv": f"/api/tools/modtran/download/{run.run_id}/modtran_freq.csv",
        "wavelength_csv": f"/api/tools/modtran/download/{run.run_id}/modtran_wavelength.csv",
    }
    if run.excel:
        downloads["excel"] = f"/api/tools/modtran/download/{run.run_id}/modtran.xlsx"
    if run.site_dll:
        # 按用户要求：下载列表显示为“本站使用dll”
        downloads["本站使用dll"] = f"/api/tools/modtran/download/{run.run_id}/{run.site_dll.name}"
    if run.tape6:
        downloads["tape6"] = f"/api/tools/modtran/download/{run.run_id}/tape6"
    if run.tape7:
        downloads["tape7"] = f"/api/tools/modtran/download/{run.run_id}/tape7"

    wl_df = pd.read_csv(run.wavelength_csv)
    return {
        "run_id": run.run_id,
        "downloads": downloads,
        "meta": {
            "duration_sec": float(run.duration_sec),
            "bin_dir": str(PCMOD_BIN_DIR),
            "usr_dir": str(PCMOD_USR_DIR),
            "rows": int(len(wl_df)),
            "spectrum_source": run.source_file.name,
        },
        "preview": df_preview(wl_df, n=80),
    }