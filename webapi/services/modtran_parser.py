from __future__ import annotations

"""Parse MODTRAN outputs (tape7 / pltout) and export helper utilities."""

from pathlib import Path
from typing import Dict, List

import pandas as pd


def parse_spectrum_file(path: Path) -> pd.DataFrame:
    """
    Parse tape7 or pltout-style files.
    - Auto-detect header line containing FREQ.
    - Fallback: first numeric-looking line.
    - Columns: Frequency_cm-1, Transmittance, optional H2O_Trans/UMIX_Trans/O3_Trans.
    """
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) <= 5 and any("-9999" in ln for ln in lines):
        raise ValueError("tape7 只有结束标记(-9999)，未生成光谱数据；请检查 tape6 的警告/错误与输入参数。")

    data_start = None
    for i, line in enumerate(lines):
        upper = line.upper()
        if "FREQ" in upper and ("CM-1" in upper or "CM" in upper):
            data_start = i + 2
            break

    if data_start is None:
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped[0].isdigit():
                parts = stripped.split()
                if len(parts) >= 2:
                    try:
                        float(parts[0])
                        float(parts[1])
                        data_start = i
                        break
                    except ValueError:
                        continue

    if data_start is None:
        raise ValueError("无法找到数据开始位置。文件可能为空或格式不正确。")

    rows: List[Dict[str, float]] = []
    for line in lines[data_start:]:
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            freq = float(parts[0])
            trans = float(parts[1])
        except ValueError:
            continue
        row: Dict[str, float] = {"Frequency_cm-1": freq, "Transmittance": trans}
        if len(parts) > 2:
            try:
                row["H2O_Trans"] = float(parts[2])
                row["UMIX_Trans"] = float(parts[3])
                row["O3_Trans"] = float(parts[4])
            except Exception:
                pass
        rows.append(row)

    if not rows:
        raise ValueError("未能从光谱文件解析出任何数据行。")

    return pd.DataFrame(rows)


def to_wavelength(df: pd.DataFrame) -> pd.DataFrame:
    if "Frequency_cm-1" not in df.columns or "Transmittance" not in df.columns:
        raise ValueError("DataFrame缺少 Frequency_cm-1 或 Transmittance 列")
    valid = (
        (df["Frequency_cm-1"] > 0.1)
        & (df["Frequency_cm-1"] < 100000)
        & (df["Transmittance"] >= 0)
        & (df["Transmittance"] <= 1)
    )
    d = df.loc[valid].copy()
    d["Wavelength_um"] = 10000.0 / d["Frequency_cm-1"]
    cols = ["Wavelength_um", "Transmittance"]
    for c in ["H2O_Trans", "UMIX_Trans", "O3_Trans"]:
        if c in d.columns:
            cols.append(c)
    return d[cols].sort_values("Wavelength_um").reset_index(drop=True)


def df_preview(df: pd.DataFrame, n: int = 50) -> list[dict]:
    return df.head(n).to_dict(orient="records")
