"""
Static publication-style world map (PNG): Köppen zones colored by results (Blues),
Robinson projection, horizontal colorbar — no HTML.
"""
from __future__ import annotations

import io
import os

import ee
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image

# --- Google Earth Engine project ---
EE_PROJECT = "stellar-mercury-491509-t3"

# --- Output ---
OUT_PNG = "koppen_energy_saving_map.png"
CACHE_PNG = "koppen_gee_raster_cache.png"
DPI = 300
FIG_W, FIG_H = 14.0, 8.2  # wide figure, white margins like journal maps

# Map title (optional); reference figure uses mainly the colorbar label.
MAP_TITLE: str | None = None

# Colorbar label (LaTeX-style unit). Match reference style; edit if your metric differs.
CBAR_LABEL = r"Cooling Energy Saving ($MJ/m^2$)"


def load_results_by_fq(csv_path: str) -> dict[str, float]:
    out: dict[str, float] = {}
    skip_zones = {"as"}
    with open(csv_path, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 11:
                continue
            fq = parts[2].strip()
            raw = parts[10].strip()
            if not fq or not raw:
                continue
            if fq.lower() in skip_zones:
                continue
            try:
                out[fq] = float(raw)
            except ValueError:
                pass
    return out


def build_ordered_values(names: list[str], data: dict[str, float]) -> list[float]:
    return [data.get(n, 0.0) for n in names]


def blues_palette_stops(n: int = 256) -> list[str]:
    """GEE expects comma-separated hex without leading #."""
    cmap = mpl.colormaps["Blues"]
    return [
        mcolors.to_hex(cmap(i / max(n - 1, 1))).lstrip("#") for i in range(n)
    ]


def fetch_gee_raster_png(
    remapped: ee.Image,
    vmin: float,
    vmax: float,
    palette_csv: str,
    max_dim: int = 4096,
    cache_path: str | None = None,
) -> np.ndarray:
    # Load from cache if available.
    if cache_path and os.path.exists(cache_path):
        print(f"Loading raster from cache: {cache_path}")
        img = Image.open(cache_path).convert("RGB")
        return np.asarray(img)

    # Slightly inset global bounds avoids GEE reprojection edge errors at ±180/±90.
    region = ee.Geometry.Rectangle([-179.5, -89.5, 179.5, 89.5], None, False)
    url = remapped.getThumbURL(
        {
            "min": vmin,
            "max": vmax,
            "palette": palette_csv,
            "region": region,
            "dimensions": max_dim,
            "format": "png",
            "crs": "EPSG:4326",
        }
    )
    print("Downloading raster from Earth Engine (may take a moment)...")
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    arr = np.asarray(bg)

    # Persist to local cache.
    if cache_path:
        Image.fromarray(arr).save(cache_path)
        print(f"Raster cached to: {cache_path}")

    return arr


def plot_robinson(
    rgb: np.ndarray,
    vmin: float,
    vmax: float,
    title: str | None,
    cbar_label: str,
    out_path: str,
) -> None:
    try:
        import cartopy.crs as ccrs
    except ImportError as e:
        raise SystemExit(
            "cartopy is required for Robinson projection. Install: pip install cartopy"
        ) from e

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "axes.linewidth": 0,
        }
    )

    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor="white")
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())
    ax.set_facecolor("white")

    ax.imshow(
        rgb,
        origin="upper",
        extent=(-180, 180, -90, 90),
        transform=ccrs.PlateCarree(),
        interpolation="nearest",
    )
    ax.set_global()
    ax.set_frame_on(False)
    # Thin white lines between land and ocean (reference-style separation)
    ax.coastlines(resolution="110m", color="#ffffff", linewidth=0.22, alpha=0.9)

    cmap = mpl.colormaps["Blues"].copy()
    cmap.set_bad(color="#d3d3d3")
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])

    cbar = fig.colorbar(
        sm,
        ax=ax,
        orientation="horizontal",
        fraction=0.048,
        pad=0.12,
        aspect=36,
        shrink=0.82,
    )
    cbar.ax.tick_params(labelsize=10)
    for label in cbar.ax.get_xticklabels():
        label.set_fontweight("bold")

    cbar.set_label(cbar_label, fontsize=11, fontweight="bold", labelpad=12)

    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold", y=0.97, color="#111111")

    plt.tight_layout(rect=[0, 0.05, 1, 0.98 if title else 0.99])
    fig.savefig(out_path, dpi=DPI, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base, "data.csv")

    names = [
        "Af",
        "Am",
        "As",
        "Aw",
        "BSh",
        "BSk",
        "BWh",
        "BWk",
        "Cfa",
        "Cfb",
        "Cfc",
        "Csa",
        "Csb",
        "Csc",
        "Cwa",
        "Cwb",
        "Cwc",
        "Dfa",
        "Dfb",
        "Dfc",
        "Dfd",
        "Dsa",
        "Dsb",
        "Dsc",
        "Dsd",
        "Dwa",
        "Dwb",
        "Dwc",
        "Dwd",
        "EF",
        "ET",
    ]

    data = load_results_by_fq(csv_path)
    ordered = build_ordered_values(names, data)
    vmin, vmax = float(min(ordered)), float(max(ordered))

    ee.Initialize(project=EE_PROJECT)

    kg = ee.Image("users/fsn1995/Global_19862010_KG_5m")
    masked = kg.updateMask(kg.gte(0).And(kg.lte(30)))
    remapped = masked.remap(list(range(31)), ordered).rename("results").toFloat()

    palette = blues_palette_stops(256)
    palette_csv = ",".join(palette)

    print("Downloading raster from Earth Engine (may take a minute)...")
    rgb = fetch_gee_raster_png(
        remapped, vmin, vmax, palette_csv,
        max_dim=4096, cache_path=os.path.join(base, CACHE_PNG)
    )

    out_path = os.path.join(base, OUT_PNG)
    plot_robinson(
        rgb,
        vmin,
        vmax,
        title=MAP_TITLE,
        cbar_label=CBAR_LABEL,
        out_path=out_path,
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
