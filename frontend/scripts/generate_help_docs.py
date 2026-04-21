from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "modules"
OUT_FILE = HERE.parent / "src" / "help" / "generatedHelpDocs.ts"


DOC_MAP: dict[str, str] = {
    "cooling": "01_辐射制冷模块.md",
    "heating": "02_辐射制热模块.md",
    "wind_cloud": "03_风速与制冷效率云图.md",
    "solar_efficiency": "04_光热转化效率_理论光热_vs_光照.md",
    "emissivity_solar_cloud": "05_大气发射率_太阳光强_云图.md",
    "power_components": "06_功率分量曲线图.md",
    "angular_power": "07_天空窗口角分辨分析.md",
    "in_situ_era5": "08_原位模拟_ERA5.md",
    "material_comparison": "09_材料对比模块.md",
}


def main() -> None:
    missing = [name for name in DOC_MAP.values() if not (DOCS_DIR / name).exists()]
    if missing:
        raise SystemExit(f"Missing docs files in {DOCS_DIR}: {missing}")

    docs: dict[str, str] = {}
    for key, filename in DOC_MAP.items():
        text = (DOCS_DIR / filename).read_text(encoding="utf-8")
        docs[key] = text

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(docs, ensure_ascii=False, indent=2)

    OUT_FILE.write_text(
        "\n".join(
            [
                "/* AUTO-GENERATED FILE. DO NOT EDIT MANUALLY.",
                " *",
                " * Source: docs/modules/*.md (converted into TS string constants).",
                " * Regenerate: python frontend/scripts/generate_help_docs.py",
                " */",
                "",
                "export type HelpDocKey =",
                "  | 'cooling'",
                "  | 'heating'",
                "  | 'wind_cloud'",
                "  | 'solar_efficiency'",
                "  | 'emissivity_solar_cloud'",
                "  | 'power_components'",
                "  | 'angular_power'",
                "  | 'in_situ_era5'",
                "  | 'material_comparison'",
                "",
                f"export const HELP_DOCS_RAW: Record<HelpDocKey, string> = {payload} as any",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Wrote: {OUT_FILE}")


if __name__ == "__main__":
    main()

