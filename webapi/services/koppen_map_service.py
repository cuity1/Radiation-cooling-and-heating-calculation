"""
Köppen-Geiger zone raster map generator.

Architecture:
  1. One-time download of the world base raster (LA PNG, ~300 KB) from GEE.
     Stored in data/koppen_base/base_raster.png.  Subsequent calls use the
     local copy, so no network is required at runtime.
  2. Colorize the 31 climate-zone indices using a discrete colormap locally.
  3. Results are further cached (per CSV/colormap) in data/koppen_preview/ so
     repeated previews with the same settings are instant.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path

import ee
import matplotlib as mpl
import numpy as np
from PIL import Image
from pydantic import BaseModel

from ..settings import settings

# ─── Public API ────────────────────────────────────────────────────────────────


class KoppenMapParams(BaseModel):
    csv_content: str
    colormap: str = "Blues"
    title: str = ""
    colorbar_label: str = ""
    z_min: float | None = None
    z_max: float | None = None
    add_grid: bool = False


class KoppenPreviewResult(BaseModel):
    data_url: str        # base64 PNG data URL (inline, no server round-trip)
    cache_key: str       # SHA-256 hash used as cache identifier
    vmin: float
    vmax: float
    colormap: str
    colorbar_label: str
    zones_loaded: list[str]


def get_koppen_preview(params: KoppenMapParams) -> KoppenPreviewResult:
    """
    Generate (or return cached) world-map preview PNG as an inline data URL.

    The base raster is cached locally after the first network fetch; the
    per-CSV / per-colormap coloured result is cached separately so that
    identical requests are served from disk without any work.
    """
    cache_key = _make_cache_key(params)
    cache_dir = settings.data_dir / "koppen_preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.png"

    if cache_path.exists():
        png_bytes = cache_path.read_bytes()
    else:
        png_bytes = _generate_raster(params)
        cache_path.write_bytes(png_bytes)

    data_url = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
    vmin, vmax, zones_loaded, colorbar_label = _extract_meta(params)

    return KoppenPreviewResult(
        data_url=data_url,
        cache_key=cache_key,
        vmin=vmin,
        vmax=vmax,
        colormap=params.colormap,
        colorbar_label=colorbar_label,
        zones_loaded=zones_loaded,
    )


def download_base_raster() -> dict:
    """
    Download the Köppen-Geiger world base raster from GEE and save it locally.

    Returns a dict with keys:
        path       (Path)    – absolute path to the saved file
        shape      (tuple)   – (height, width) in pixels
        sha256     (str)     – hex digest of the file contents
        is_fresh   (bool)    – True if the file was freshly downloaded, False if
                                it already existed and was reused

    Call this once (with network available) to prepare the local base raster.
    Afterwards get_koppen_preview() works fully offline.
    """
    return _ensure_base_raster(force_refresh=False)


# ─── Internal helpers ────────────────────────────────────────────────────────


EE_PROJECT = "stellar-mercury-491509-t3"

KG_NAMES = [
    "Af", "Am", "As", "Aw",
    "BSh", "BSk", "BWh", "BWk",
    "Cfa", "Cfb", "Cfc",
    "Csa", "Csb", "Csc",
    "Cwa", "Cwb", "Cwc",
    "Dfa", "Dfb", "Dfc", "Dfd",
    "Dsa", "Dsb", "Dsc", "Dsd",
    "Dwa", "Dwb", "Dwc", "Dwd",
    "EF", "ET",
]


# ── Local base-raster management ─────────────────────────────────────────────


def _base_dir() -> Path:
    d = settings.data_dir / "koppen_base"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _base_raster_path() -> Path:
    return _base_dir() / "base_raster.png"


def _ensure_base_raster(
    *, force_refresh: bool = False
) -> dict:
    """
    Return the local base raster bytes, downloading from GEE if needed.

    Args:
        force_refresh: re-download even if a local copy already exists.

    Returns:
        dict with path, shape, sha256, is_fresh keys.
    """
    local_path = _base_raster_path()
    is_fresh = False

    if force_refresh or not local_path.exists():
        data = _fetch_gee_raster_bytes()
        local_path.write_bytes(data)
        is_fresh = True

    raw = local_path.read_bytes()
    from PIL import Image
    img = Image.open(io.BytesIO(raw))
    h, w = img.size[1], img.size[0]   # PIL: size = (width, height)
    sha = hashlib.sha256(raw).hexdigest()

    return dict(path=local_path, shape=(h, w), sha256=sha, is_fresh=is_fresh)


def _fetch_gee_raster_bytes() -> bytes:
    """
    Download the raw Köppen-Geiger raster directly from GEE.
    Called only when the local cache is missing (first run) or being refreshed.
    """
    import requests
    proxy = settings.gee_proxy
    saved = _apply_proxy(proxy, restore=False)

    try:
        ee.Initialize(project=EE_PROJECT)
    except Exception as e:
        raise RuntimeError(
            f"GEE initialization failed.\n"
            f"  If offline / in China: download the base raster once with network via:\n"
            f"    python -m webapi.services.koppen_map_service\n"
            f"  Or set gee_proxy in settings.py (e.g. gee_proxy='http://127.0.0.1:7890').\n"
            f"  Otherwise run: earthengine authenticate\n"
            f"Error: {e}"
        ) from None

    kg = ee.Image("users/fsn1995/Global_19862010_KG_5m")
    masked = kg.updateMask(kg.gte(0).And(kg.lte(30)))
    region = ee.Geometry.Rectangle([-179.5, -89.5, 179.5, 89.5], None, False)
    thumb_url = masked.getThumbURL({
        "dimensions": 2048,
        "format": "png",
        "crs": "EPSG:4326",
        "region": region,
    })

    session = requests.Session()
    if proxy:
        session.proxies = {"https": proxy, "http": proxy}
    try:
        resp = session.get(thumb_url, timeout=300)
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(
            f"Failed to download GEE thumbnail (HTTP {resp.status_code}).\n"
            f"  URL: {thumb_url[:80]}...\n"
            f"  If in China / offline: download the base raster once with network via:\n"
            f"    python -m webapi.services.koppen_map_service\n"
            f"Error: {e}"
        ) from None

    _apply_proxy(proxy, restore=True, saved=saved)   # restore env vars
    return resp.content


def _apply_proxy(
    proxy: str, *, restore: bool, saved: dict | None = None
) -> dict | None:
    """
    When restore=False:  save the four proxy env vars and set them from `proxy`.
    When restore=True:   restore the previously saved values.

    Returns the saved dict (on save) or None (on restore).
    """
    keys = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")
    if not restore:
        saved = {k: os.environ.get(k) for k in keys}
        if proxy:
            for k in keys:
                os.environ[k] = proxy
        return saved
    else:
        if saved is None:
            return None
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return None


# ── Core raster pipeline ─────────────────────────────────────────────────────


def _load_base_raster() -> tuple[np.ndarray, np.ndarray]:
    """
    Load the local base raster and return (gray, alpha) as 2-D int16 arrays.
    gray : Köppen class index 0-30 (land pixels)
    alpha: 0 = ocean / no-data, 255 = valid land pixel
    """
    _ensure_base_raster()
    img = Image.open(io.BytesIO(_base_raster_path().read_bytes()))
    arr = np.array(img)
    if arr.ndim == 3 and arr.shape[2] >= 2:
        gray = arr[:, :, 0].astype(np.int16)
        alpha = arr[:, :, 1]
    else:
        gray = arr.astype(np.int16)
        alpha = np.full(gray.shape, 255, dtype=np.uint8)
    return gray, alpha


def _build_palette(
    cmap_key: str, ordered: list[float], vmin: float, vmax: float
) -> np.ndarray:
    """
    Build a 31-row RGB palette from the user's colormap and value range.

    Args:
        cmap_key:  matplotlib colormap name
        ordered:   [value for each of the 31 KG_NAMES in index order]
        vmin, vmax: normalisation bounds

    Returns:
        (31, 3) float32 array, values in [0, 1].
    """
    cmap_raw = mpl.colormaps[cmap_key]
    # Map the 31 zone indices through the user-value scale
    vals = np.array(ordered, dtype=np.float64)
    norm_vals = np.clip((vals - vmin) / max(vmax - vmin, 1e-9), 0.0, 1.0)
    colors = np.array([cmap_raw(float(v))[:3] for v in norm_vals], dtype=np.float64)
    return colors


def _colorize(
    gray: np.ndarray, alpha: np.ndarray, palette: np.ndarray
) -> np.ndarray:
    """
    Apply a (31, 3) discrete palette to a (H, W) zone-index array.
    Ocean / no-data pixels (alpha < 128) are set to white (1.0).
    Returns (H, W, 3) uint8 RGB.
    """
    rgb = palette[np.clip(gray, 0, 30)]   # (H, W, 3) float
    ocean = alpha < 128
    rgb[ocean] = 1.0
    return (np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8)


def _make_colorbar_png(
    cmap_key: str,
    vmin: float,
    vmax: float,
    label: str,
    width: int,
    dpi: int = 150,
) -> Image.Image:
    """
    Render a horizontal colorbar strip with tick marks and label as a PIL RGBA image.

    Uses a dedicated colorbar axes only (no full-figure dummy subplot), so
    ``bbox_inches='tight'`` does not reserve a huge blank band above the bar.
    Output is scaled to ``width`` px wide; height follows content aspect ratio.
    """
    import matplotlib.pyplot as plt

    plt.switch_backend("Agg")
    cmap = mpl.colormaps[cmap_key] if cmap_key in mpl.colormaps else mpl.colormaps["Blues"]

    fig_w_in = width / dpi
    fig_h_in = 1.35
    fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=dpi, facecolor="white")

    # Single horizontal colorbar axis only — avoids empty main axes eating vertical space
    cax = fig.add_axes([0.05, 0.52, 0.90, 0.16])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])

    cb = fig.colorbar(
        sm,
        cax=cax,
        orientation="horizontal",
        ticklocation="bottom",
    )
    cb.set_label(label, fontsize=14, color="#333333", labelpad=6)
    cb.ax.tick_params(labelsize=12, colors="#555555", length=5)
    cb.outline.set_visible(False)

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
        pad_inches=0.06,
    )
    plt.close(fig)
    buf.seek(0)

    result = Image.open(buf).convert("RGBA")
    if result.width != width:
        ratio = width / result.width
        new_h = max(1, int(round(result.height * ratio)))
        result = result.resize((width, new_h), Image.LANCZOS)
    return result


def _draw_latlon_grid(img: Image.Image, *, line_color: tuple[int, int, int] = (140, 140, 140), line_width: int = 1) -> Image.Image:
    """
    Overlay a lat/lon graticule on ``img`` (EPSG:4326, -179.5°..179.5° × -89.5°..89.5°).

    Grid lines are drawn every 30° for both latitude and longitude;
    the equator and prime meridian are drawn a little darker (170).
    Degree labels (°N / °S / °E / °W) are rendered in the four margins using
    PIL's built-in bitmap font (no extra dependencies).
    """
    from PIL import ImageDraw, ImageFont

    W, H = img.size
    # Map pixel (x, y) ↔ (lon, lat):
    #   lon = x / W * 359 - 179.5
    #   lat = 89.5 - y / H * 179
    # Equator  → y = H / 2
    #   0°E     → x = W * 179.5 / 359

    equator_y  = round(H / 2)
    pm_x       = round(W * 179.5 / 359)

    draw = ImageDraw.Draw(img)

    # Try to use a slightly larger built-in font for readability; fall back gracefully
    try:
        font = ImageFont.truetype("arial.ttf", 11)
        font_bold = ImageFont.truetype("arialbd.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    # ── Vertical longitude lines ──────────────────────────────────────────────
    for lon in range(-180, 181, 30):
        x = round((lon + 179.5) / 359 * W)
        col = (170, 170, 170) if lon in (0,) else line_color
        draw.line([(x, 0), (x, H - 1)], fill=col, width=line_width)
        if 0 < lon < 180:
            label = f"{lon}°E"
        elif lon < 0:
            label = f"{-lon}°W"
        else:
            label = f"{lon}°"
        draw.text((x + 2, H - 16), label, fill=(120, 120, 120), font=font)

    # ── Horizontal latitude lines ──────────────────────────────────────────────
    for lat in range(-90, 91, 30):
        y = round((89.5 - lat) / 179 * H)
        col = (170, 170, 170) if lat == 0 else line_color
        draw.line([(0, y), (W - 1, y)], fill=col, width=line_width)
        if lat > 0:
            label = f"{lat}°N"
        elif lat < 0:
            label = f"{-lat}°S"
        else:
            label = "0°"
        draw.text((2, y + 1), label, fill=(120, 120, 120), font=font)

    return img


def _generate_raster(params: KoppenMapParams) -> bytes:
    """Colorize the world base raster using the CSV values and return PNG bytes."""
    csv_data = _parse_csv(params.csv_content)
    ordered = _build_ordered(csv_data)

    vmin = float(min(ordered))
    vmax = float(max(ordered))
    if params.z_min is not None:
        vmin = float(params.z_min)
    if params.z_max is not None:
        vmax = float(params.z_max)

    cmap_key = params.colormap if params.colormap in mpl.colormaps else "Blues"
    palette = _build_palette(cmap_key, ordered, vmin, vmax)

    gray, alpha = _load_base_raster()
    rgb_arr = _colorize(gray, alpha, palette)

    map_img = Image.fromarray(rgb_arr).convert("RGBA")
    W = map_img.width

    if params.add_grid:
        map_img = _draw_latlon_grid(map_img)

    # Render colorbar strip with matplotlib
    cbar_img = _make_colorbar_png(cmap_key, vmin, vmax, params.colorbar_label, W)

    # Thin spacer between map and colorbar (avoid double margin with cbar crop)
    gap_h = max(4, int(map_img.height * 0.003))
    spacer = Image.new("RGBA", (W, gap_h), (255, 255, 255, 255))

    # Stack: map → spacer → colorbar
    total_h = map_img.height + gap_h + cbar_img.height
    combined = Image.new("RGBA", (W, total_h), (255, 255, 255, 255))
    combined.paste(map_img, (0, 0))
    combined.paste(spacer, (0, map_img.height))
    combined.paste(cbar_img, (0, map_img.height + gap_h))

    buf = io.BytesIO()
    combined.save(buf, format="PNG")
    return buf.getvalue()


# ── CSV helpers ──────────────────────────────────────────────────────────────


def _make_cache_key(params: KoppenMapParams) -> str:
    payload = json.dumps({
        "v": 5,  # bump: lat/lon grid toggle
        "csv": params.csv_content,
        "cm": params.colormap,
        "t": params.title,
        "l": params.colorbar_label,
        "zmin": params.z_min,
        "zmax": params.z_max,
        "grid": params.add_grid,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _canonical_fq(fq: str) -> str | None:
    """Match user FQ (any case) to KG_NAMES, e.g. Bsh → BSh."""
    f = fq.strip()
    if not f:
        return None
    for n in KG_NAMES:
        if n.lower() == f.lower():
            return n
    return None


def _parse_csv(csv_content: str) -> dict[str, float]:
    """Parse FQ → value. Handles both short (ID,QID,FQ,results) and legacy wide rows."""
    out: dict[str, float] = {}
    text = csv_content.strip()
    if not text:
        return out
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        return out
    header = [h.strip().lower() for h in rows[0]]
    fq_idx: int | None = None
    val_idx: int | None = None
    for i, h in enumerate(header):
        if h in ("fq", "koppen", "climate", "zone"):
            fq_idx = i
        if h in ("results", "result", "value", "values"):
            val_idx = i
    if fq_idx is None:
        fq_idx = 2 if len(header) > 2 else 0
    if val_idx is None:
        if len(header) >= 4:
            val_idx = 3
        elif len(header) >= 11:
            val_idx = 10
        else:
            val_idx = min(fq_idx + 1, len(header) - 1)

    SKIP_ZONES = {"as"}

    for row in rows[1:]:
        if len(row) <= max(fq_idx, val_idx):
            continue
        canon = _canonical_fq(row[fq_idx].strip())
        if not canon:
            continue
        if canon.lower() in SKIP_ZONES:
            continue
        try:
            out[canon] = float(row[val_idx].strip())
        except (ValueError, IndexError):
            continue
    return out


def _build_ordered(csv_data: dict[str, float]) -> list[float]:
    return [csv_data.get(n, 0.0) for n in KG_NAMES]


def _extract_meta(params: KoppenMapParams):
    csv_data = _parse_csv(params.csv_content)
    ordered = _build_ordered(csv_data)
    vmin = float(min(ordered))
    vmax = float(max(ordered))
    if params.z_min is not None:
        vmin = float(params.z_min)
    if params.z_max is not None:
        vmax = float(params.z_max)
    label = params.colorbar_label or r"Cooling Energy Saving ($MJ/m^2$)"
    return vmin, vmax, list(csv_data.keys()), label


# ── Export helpers ───────────────────────────────────────────────────────────


def get_export_png_path(cache_key: str) -> Path | None:
    cache_dir = settings.data_dir / "koppen_preview"
    path = cache_dir / f"{cache_key}.png"
    return path if path.exists() else None


# ── CLI entry point ──────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download the Köppen-Geiger world base raster from GEE "
                    "and save it locally.  Run once with network access; "
                    "afterwards get_koppen_preview() works fully offline."
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force re-download even if a local copy already exists."
    )
    args = parser.parse_args()

    print("Connecting to GEE to download base raster …")
    result = _ensure_base_raster(force_refresh=args.refresh)
    print(f"  Saved to : {result['path']}")
    print(f"  Shape    : {result['shape']}")
    print(f"  SHA-256  : {result['sha256']}")
    print(f"  Fresh    : {result['is_fresh']}")
    print("Done.  get_koppen_preview() will now use this local copy.")
