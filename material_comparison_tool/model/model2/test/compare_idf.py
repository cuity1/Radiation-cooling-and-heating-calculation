from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


def parse_objects(path: Path) -> List[Tuple[str, str, str]]:
    """
    Very light-weight EnergyPlus IDF parser:
    - Groups lines into objects by semicolon
    - Extracts object type from the first non-comment line before the first comma/semicolon
    Returns list of (object_type, header_line, raw_block).
    """
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    objects: List[Tuple[str, str, str]] = []
    buf: List[str] = []

    for line in text:
        raw = line.rstrip("\n")
        # Remove inline comments starting with '!'
        if "!" in raw:
            raw_nocom = raw.split("!", 1)[0]
        else:
            raw_nocom = raw

        if not raw_nocom.strip():
            # Skip pure comment/empty lines between fields, but keep buffer
            buf.append(raw)
        else:
            buf.append(raw)

        # End of object when a non-comment part contains ';'
        if ";" in raw_nocom:
            header = None
            for l in buf:
                s = l.strip()
                if not s or s.startswith("!"):
                    continue
                if "!" in s:
                    s = s.split("!", 1)[0].strip()
                header = s
                break

            if header is None:
                buf.clear()
                continue

            header_for_type = header
            for sep in (",", ";"):
                if sep in header:
                    header_for_type = header.split(sep, 1)[0]
                    break

            obj_type = header_for_type.strip()
            if obj_type:
                objects.append((obj_type, header, "\n".join(buf)))

            buf.clear()

    return objects


def main() -> None:
    base = Path(__file__).resolve().parent
    old_path = base / "old.idf"
    new_path = base / "new.idf"

    if not old_path.exists() or not new_path.exists():
        print("old.idf or new.idf not found next to compare_idf.py")
        return

    old_objs = parse_objects(old_path)
    new_objs = parse_objects(new_path)

    old_types = Counter(t for t, _, _ in old_objs)
    new_types = Counter(t for t, _, _ in new_objs)

    print("=== Object type counts where old.idf has more than new.idf ===")
    for t in sorted(set(old_types) | set(new_types)):
        co, cn = old_types.get(t, 0), new_types.get(t, 0)
        if co > cn:
            print(f"{t}: old={co}, new={cn}")

    print("\n=== Object types missing completely in new.idf (present in old.idf) ===")
    for t in sorted(old_types):
        if old_types[t] > 0 and new_types.get(t, 0) == 0:
            print(t)

    # For some key object types, show which specific names are missing in new.idf
    key_types = [
        "Zone",
        "BuildingSurface:Detailed",
        "FenestrationSurface:Detailed",
        "HVACTemplate:Zone:IdealLoadsAirSystem",
        "Material",
    ]

    def extract_name(header_line: str) -> str:
        # header like: "Zone,    ZN_1_FLR_1, ..."
        s = header_line
        if "!" in s:
            s = s.split("!", 1)[0]
        parts = [p.strip() for p in s.split(",")]
        return parts[1] if len(parts) > 1 else ""

    by_type_old: Dict[str, List[str]] = {k: [] for k in key_types}
    by_type_new: Dict[str, List[str]] = {k: [] for k in key_types}

    for t, header, _ in old_objs:
        if t in by_type_old:
            by_type_old[t].append(extract_name(header))

    for t, header, _ in new_objs:
        if t in by_type_new:
            by_type_new[t].append(extract_name(header))

    print("\n=== Names present in old.idf but missing in new.idf for key object types ===")
    for t in key_types:
        old_names = set(by_type_old.get(t, []))
        new_names = set(by_type_new.get(t, []))
        missing = sorted(n for n in old_names if n and n not in new_names)
        if missing:
            print(f"\n{t}:")
            for n in missing:
                print(f"  - {n}")


if __name__ == "__main__":
    main()

