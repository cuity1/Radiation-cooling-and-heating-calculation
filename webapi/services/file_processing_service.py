from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProcessResult:
    processed_id: str
    processed_path: Path
    original_name: str
    output_type: str  # reflectance | emissivity | transmittance
    rows: int
    tips: list[str]
    preview: list[list[float]]


def _normalize_number_token(token: str) -> float:
    s = token.strip()
    if s.endswith('%'):
        s = s[:-1]
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    return float(s)


def _parse_txt_bytes(content: bytes) -> np.ndarray:
    # Mirror gui/file_processor.py behavior.
    trans = str.maketrans(
        {
            '０': '0',
            '１': '1',
            '２': '2',
            '３': '3',
            '４': '4',
            '５': '5',
            '６': '6',
            '７': '7',
            '８': '8',
            '９': '9',
            '．': '.',
            '，': ',',
            '。': '.',
            '、': ' ',
            '－': '-',
            '—': '-',
            '～': '-',
            '‒': '-',
            '–': '-',
            '−': '-',
        }
    )

    # UTF-16 BOM detection must come first; otherwise UTF-8/GBK decoding
    # with errors='ignore' silently drops \x00 bytes and mangles the text.
    if len(content) >= 2:
        if content[:2] == b'\xff\xfe':
            # UTF-16-LE BOM  → decode as UTF-16-LE
            text = content.decode('utf-16-le', errors='replace')
            rows = _extract_rows_from_text(text, trans)
            return np.array(rows, dtype=float)
        if content[:2] == b'\xfe\xff':
            # UTF-16-BE BOM  → decode as UTF-16-BE
            text = content.decode('utf-16-be', errors='replace')
            rows = _extract_rows_from_text(text, trans)
            return np.array(rows, dtype=float)

    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'gb18030', 'latin1', 'utf-16']
    number_pattern = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\d*\.\d+)(?:[eE][+-]?\d+)?%?")

    for enc in encodings:
        try:
            text = content.decode(enc, errors='ignore')
        except Exception:
            continue

        rows = _extract_rows_from_text(text, trans, number_pattern)
        if rows:
            return np.array(rows, dtype=float)

    raise ValueError('Unable to parse TXT: must contain at least two numeric columns')


def _extract_rows_from_text(
    text: str,
    trans: dict,
    number_pattern: re.Pattern | None = None,
) -> list[list[float]]:
    """Extract two-column numeric data from decoded text."""
    if number_pattern is None:
        number_pattern = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\d*\.\d+)(?:[eE][+-]?\d+)?%?")

    rows: list[list[float]] = []
    for raw_line in io.StringIO(text):
        line = raw_line.translate(trans)
        tokens = number_pattern.findall(line)
        if not tokens:
            continue
        vals: list[float] = []
        for tk in tokens:
            try:
                vals.append(_normalize_number_token(tk))
            except Exception:
                continue
            if len(vals) == 2:
                break
        if len(vals) >= 2:
            rows.append(vals[:2])
    return rows


def _read_csv_bytes(content: bytes) -> np.ndarray:
    # UTF-16 BOM detection must come first (same issue as TXT).
    if len(content) >= 2:
        if content[:2] == b'\xff\xfe':
            df = pd.read_csv(io.BytesIO(content[2:]), encoding='utf-16-le', header=None)
            return df.values
        if content[:2] == b'\xfe\xff':
            df = pd.read_csv(io.BytesIO(content[2:]), encoding='utf-16-be', header=None)
            return df.values

    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'gb18030']
    last_err: Exception | None = None
    for enc in encodings:
        try:
            text = content.decode(enc)
            df = pd.read_csv(io.StringIO(text), encoding=None, header=None)
            return df.values
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f'Unable to read CSV with common encodings: {last_err}')


def _read_excel_bytes(content: bytes) -> np.ndarray:
    # Use pandas engine detection; relies on openpyxl for xlsx.
    bio = io.BytesIO(content)
    df = pd.read_excel(bio, header=None)
    return df.values


def _clean_data(data) -> np.ndarray:
    cleaned_rows: list[list[float]] = []

    for row in data:
        row_str = [str(cell) for cell in row]
        has_text = False
        for cell in row_str:
            if re.search(r'[\u4e00-\u9fff]', str(cell)):
                has_text = True
                break
            if re.search(r'[a-zA-Z]', str(cell)) and not re.match(r'^[\d\.\-\+eE]+$', str(cell)):
                has_text = True
                break

        if has_text:
            continue

        numeric_values: list[float] = []
        for cell in row_str:
            try:
                numeric_values.append(float(cell))
                continue
            except Exception:
                pass

            numbers = re.findall(r'-?\d+\.?\d*[eE]?[+-]?\d*', str(cell))
            if numbers:
                try:
                    numeric_values.append(float(numbers[0]))
                except Exception:
                    pass

        if len(numeric_values) >= 2:
            cleaned_rows.append(numeric_values[:2])

    return np.array(cleaned_rows) if cleaned_rows else np.array([])


def _postprocess_output(data: np.ndarray, output_type: str) -> tuple[np.ndarray, list[str]]:
    tips: list[str] = []
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError('Data must have at least two columns')

    arr = arr[:, :2]
    mask = np.isfinite(arr).all(axis=1)
    arr = arr[mask]
    if arr.shape[0] == 0:
        raise ValueError('No valid numeric rows')

    idx = np.argsort(arr[:, 0])
    arr = arr[idx]

    if arr.shape[0] > 1:
        _, uniq_idx = np.unique(arr[:, 0], return_index=True)
        arr = arr[uniq_idx]

    y = arr[:, 1]
    if np.nanmax(y) > 1.5:
        arr[:, 1] = y / 100.0
        tips.append('Detected percentage values; divided by 100')

    arr[:, 1] = np.clip(arr[:, 1], 0.0, 1.0)

    x = arr[:, 0]
    if np.median(x) > 100:
        arr[:, 0] = x * 0.001
        tips.append('Detected wavelength in nm; converted to µm (÷1000)')

    return arr, tips


def process_upload(
    *,
    filename: str,
    content: bytes,
    output_type: str,
    processed_dir: Path,
) -> ProcessResult:
    # Allow transmittance to share the same processing pipeline as
    # reflectance / emissivity (same normalization and clipping rules).
    if output_type not in {'reflectance', 'emissivity', 'transmittance'}:
        raise ValueError('output_type must be reflectance, emissivity or transmittance')

    suffix = Path(filename).suffix.lower()

    if suffix == '.txt':
        raw = _parse_txt_bytes(content)
    elif suffix == '.csv':
        raw = _read_csv_bytes(content)
    elif suffix in {'.xlsx', '.xls'}:
        raw = _read_excel_bytes(content)
    else:
        raise ValueError(f'Unsupported file type: {suffix}')

    if raw.size == 0 or getattr(raw, 'shape', (0,))[0] == 0:
        raise ValueError('File is empty or contains no readable data')

    # If not purely numeric, try to clean.
    try:
        is_numeric = np.issubdtype(np.array(raw).dtype, np.number)
    except Exception:
        is_numeric = False

    cleaned = np.array(raw, dtype=float) if is_numeric else _clean_data(raw)
    if cleaned.size == 0 or cleaned.shape[0] == 0:
        raise ValueError('No valid numeric rows after cleaning (need at least two numeric columns)')

    output_data, tips = _postprocess_output(cleaned[:, :2], output_type)

    if output_data.shape[0] < 5:
        raise ValueError('Too few valid rows (< 5) after processing')

    processed_id = str(uuid.uuid4())
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f'{processed_id}.txt'

    np.savetxt(out_path, output_data, fmt='%.6f', delimiter=' ', encoding='utf-8')

    preview = output_data[:1000].tolist()

    return ProcessResult(
        processed_id=processed_id,
        processed_path=out_path,
        original_name=filename,
        output_type=output_type,
        rows=int(output_data.shape[0]),
        tips=tips,
        preview=preview,
    )


def combine_reflectance_and_transmittance(
    reflectance_path: Path,
    transmittance_path: Path,
    out_dir: Path,
    *,
    combined_name: str | None = None,
) -> Path:
    """Align and combine R(λ) and T(λ) → (R+T)(λ) on the reflectance grid.

    - Load both processed TXT files (2 columns: λ, value in [0,1]).
    - Interpolate T(λ) onto the reflectance wavelength grid.
    - Compute y_combined = clip(R + T_interp, 0, 1).
    - Save combined spectrum as a new TXT file and return its path.
    """
    # Load processed arrays
    r_data = np.loadtxt(reflectance_path, dtype=float)
    t_data = np.loadtxt(transmittance_path, dtype=float)

    if r_data.ndim != 2 or r_data.shape[1] < 2:
        raise ValueError("reflectance file must have at least two columns")
    if t_data.ndim != 2 or t_data.shape[1] < 2:
        raise ValueError("transmittance file must have at least two columns")

    x_r = r_data[:, 0]
    y_r = r_data[:, 1]

    x_t = t_data[:, 0]
    y_t = t_data[:, 1]

    if x_r.size < 5 or x_t.size < 5:
        raise ValueError("Both reflectance and transmittance must have at least 5 rows")

    # Interpolate transmittance onto reflectance wavelength grid.
    # Outside the original domain, assume T = 0.
    y_t_interp = np.interp(x_r, x_t, y_t, left=0.0, right=0.0)

    y_combined = np.clip(y_r + y_t_interp, 0.0, 1.0)
    combined = np.column_stack([x_r, y_combined])

    out_dir.mkdir(parents=True, exist_ok=True)

    if combined_name is None:
        combined_name = f"combined_{uuid.uuid4().hex}.txt"

    out_path = out_dir / combined_name
    np.savetxt(out_path, combined, fmt="%.6f", delimiter=" ", encoding="utf-8")
    return out_path
