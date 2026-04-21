from __future__ import annotations

"""
Utility helpers to read / update MODTRAN .ltn cards while preserving field
spacing. Derived from the desktop modtran_gui.py logic, trimmed for backend use.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


FieldSpan = Tuple[int, int, str]  # (start, end, text)


def _field_spans(line: str) -> List[FieldSpan]:
    spans: List[FieldSpan] = []
    i = 0
    n = len(line)
    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not line[j].isspace():
            j += 1
        spans.append((i, j, line[i:j]))
        i = j
    return spans


def _replace_field_by_index(line: str, field_index_0based: int, new_text: str) -> str:
    spans = _field_spans(line)
    if field_index_0based < 0 or field_index_0based >= len(spans):
        raise IndexError(f"字段索引越界: {field_index_0based}, 字段数={len(spans)}")
    start, end, old = spans[field_index_0based]
    width = end - start
    s = str(new_text)
    if len(s) < width:
        s = s.rjust(width)
    elif len(s) > width:
        s = s[:width]
    return line[:start] + s + line[end:]


def _format_float_like(old_field: str, value: float) -> str:
    if "." in old_field:
        decimals = len(old_field.split(".", 1)[1])
        fmt = f"{{:.{decimals}f}}"
        s = fmt.format(value)
    else:
        s = str(int(round(value)))
    return s


def _parse_line6_start_end(line6: str) -> tuple[float, float, str]:
    parts = line6.split()
    if not parts:
        raise ValueError("第6行为空，无法解析")
    token = parts[0]
    token_pos = line6.find(token)
    if token_pos < 0:
        raise ValueError("无法定位第6行的起止波数token")
    rest = line6[token_pos + len(token):]

    candidates: List[tuple[float, float, int]] = []
    for k in range(1, len(token)):
        left = token[:k]
        right = token[k:]
        if left.count(".") != 1 or right.count(".") != 1:
            continue
        if left.startswith(".") or left.endswith(".") or right.startswith(".") or right.endswith("."):
            continue
        try:
            a = float(left)
            b = float(right)
        except Exception:
            continue
        if not (a > 0 and b > 0 and b > a):
            continue
        if a > 1e6 or b > 1e6:
            continue
        candidates.append((a, b, k))

    if not candidates:
        raise ValueError(f"无法从token解析起止波数: {token!r}")

    def score(c: tuple[float, float, int]) -> tuple[int, int]:
        _, _, k = c
        right = token[k:]
        leading0 = 1 if (len(right) > 1 and right[0] == "0") else 0
        int_digits = len(right.split(".", 1)[0].lstrip("+-"))
        return (leading0, -int_digits)

    best = sorted(candidates, key=score)[0]
    return best[0], best[1], rest


def _write_line6_with_start_end(
    line6: str,
    start_cm1: float,
    end_cm1: float,
    res_cm1: float | None = None,
    out_res_cm1: float | None = None,
) -> str:
    parts = line6.split()
    if not parts:
        raise ValueError("第6行为空，无法写回")
    old_token = parts[0]
    token_pos = line6.find(old_token)
    if token_pos < 0:
        raise ValueError("无法定位第6行的起止波数token")
    prefix = line6[:token_pos]
    rest = line6[token_pos + len(old_token):]

    new_token = f"{start_cm1:.5f}{end_cm1:.4f}"

    if res_cm1 is not None or out_res_cm1 is not None:
        rest_spans = _field_spans(rest)
        float_field_idxs: List[int] = []
        for idx, (_, __, txt) in enumerate(rest_spans):
            try:
                float(txt)
                float_field_idxs.append(idx)
            except Exception:
                pass
            if len(float_field_idxs) >= 2:
                break
        new_rest = rest
        if len(float_field_idxs) >= 1 and res_cm1 is not None:
            s_old = rest_spans[float_field_idxs[0]][2]
            new_rest = _replace_field_by_index(new_rest, float_field_idxs[0], _format_float_like(s_old, res_cm1))
        if len(float_field_idxs) >= 2 and out_res_cm1 is not None:
            rest_spans2 = _field_spans(new_rest)
            s_old2 = rest_spans2[float_field_idxs[1]][2]
            new_rest = _replace_field_by_index(new_rest, float_field_idxs[1], _format_float_like(s_old2, out_res_cm1))
        rest = new_rest

    return prefix + new_token + rest


@dataclass
class LtnParams:
    model_type: str  # T/R
    atmosphere_model: int
    aerosol_model: int
    observer_zenith_deg: float
    observer_azimuth_deg: float
    solar_zenith_deg: float
    solar_azimuth_deg: float
    ground_alt_km: float
    start_cm1: float
    end_cm1: float
    res_cm1: float
    out_res_cm1: float


def load_ltn_params(ltn_path: Path) -> tuple[list[str], LtnParams]:
    lines = ltn_path.read_text(encoding="ascii", errors="ignore").splitlines()
    if len(lines) < 7:
        raise ValueError(f".ltn行数不足: {len(lines)}")

    line1 = lines[0]
    s1 = _field_spans(line1)
    model_type = s1[0][2]
    atmosphere_model = int(float(s1[2][2]))
    aerosol_model = int(float(s1[3][2]))

    line4 = lines[3]
    s4 = _field_spans(line4)
    ground_alt_km = float(s4[10][2])

    line5 = lines[4]
    s5 = _field_spans(line5)
    observer_zenith = float(s5[0][2])
    observer_azimuth = float(s5[1][2])
    solar_zenith = float(s5[2][2])
    solar_azimuth = float(s5[3][2])

    line6 = lines[5]
    start_cm1, end_cm1, rest = _parse_line6_start_end(line6)
    rest_spans = _field_spans(rest)
    floats: list[float] = []
    for (_, __, txt) in rest_spans:
        try:
            floats.append(float(txt))
        except Exception:
            pass
        if len(floats) >= 2:
            break
    if len(floats) < 2:
        raise ValueError("第6行无法解析分辨率字段")
    res_cm1 = floats[0]
    out_res_cm1 = floats[1]

    params = LtnParams(
        model_type=model_type,
        atmosphere_model=atmosphere_model,
        aerosol_model=aerosol_model,
        observer_zenith_deg=observer_zenith,
        observer_azimuth_deg=observer_azimuth,
        solar_zenith_deg=solar_zenith,
        solar_azimuth_deg=solar_azimuth,
        ground_alt_km=ground_alt_km,
        start_cm1=start_cm1,
        end_cm1=end_cm1,
        res_cm1=res_cm1,
        out_res_cm1=out_res_cm1,
    )
    return lines, params


def apply_params_to_lines(lines: list[str], params: LtnParams) -> list[str]:
    out = list(lines)
    out[0] = _replace_field_by_index(out[0], 0, params.model_type)
    out[0] = _replace_field_by_index(out[0], 2, str(int(params.atmosphere_model)))
    out[0] = _replace_field_by_index(out[0], 3, str(int(params.aerosol_model)))

    s4 = _field_spans(out[3])
    old_ground = s4[10][2]
    out[3] = _replace_field_by_index(out[3], 10, _format_float_like(old_ground, params.ground_alt_km))

    s5 = _field_spans(out[4])
    out[4] = _replace_field_by_index(out[4], 0, _format_float_like(s5[0][2], params.observer_zenith_deg))
    s5b = _field_spans(out[4])
    out[4] = _replace_field_by_index(out[4], 1, _format_float_like(s5b[1][2], params.observer_azimuth_deg))
    s5c = _field_spans(out[4])
    out[4] = _replace_field_by_index(out[4], 2, _format_float_like(s5c[2][2], params.solar_zenith_deg))
    s5d = _field_spans(out[4])
    out[4] = _replace_field_by_index(out[4], 3, _format_float_like(s5d[3][2], params.solar_azimuth_deg))

    out[5] = _write_line6_with_start_end(
        out[5],
        params.start_cm1,
        params.end_cm1,
        params.res_cm1,
        params.out_res_cm1,
    )
    return out


def save_ltn_lines(lines: list[str], target: Path) -> None:
    """Write lines with CRLF to mimic PcMod5 style."""
    target.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii", errors="ignore"))
