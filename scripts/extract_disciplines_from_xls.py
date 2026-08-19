# -*- coding: utf-8 -*-
"""Извлечение дисциплин и кредитов из расчёта кафедры ТИИ (.xls)."""
import json
import re
import sys
from pathlib import Path

import xlrd

SKIP_NAME = re.compile(
    r"^(итого|бакалавриат|магистратура|докторантура|\d\s*курс|"
    r"зимний приём|эдвайзерство|почасовой фонд|председатель|рецензир|"
    r"оппонирование|руководство зарубеж|консультация зарубеж|вакансия\s*$)",
    re.I,
)


def norm_name(s: str) -> str:
    s = str(s).replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*\(\s*\)\s*$", "", s).strip()
    return s


def should_skip(name: str) -> bool:
    n = name.strip()
    if len(n) < 4:
        return True
    if SKIP_NAME.search(n.split(":")[0].strip()):
        return True
    if "итого" in n.lower():
        return True
    if "почасовой фонд" in n.lower():
        return True
    return False


def parse_sheet(sh, semester_hint: str) -> list[dict]:
    out = []
    for r in range(sh.nrows):
        row = [sh.cell_value(r, c) for c in range(sh.ncols)]
        if len(row) < 10:
            continue
        title_disc = norm_name(row[2])
        if not title_disc or should_skip(title_disc):
            continue
        try:
            credits = float(row[9]) if row[9] != "" else 0.0
        except (TypeError, ValueError):
            credits = 0.0
        if credits <= 0:
            continue
        code = norm_name(row[3]) if len(row) > 3 else ""
        comp = norm_name(row[1]) if len(row) > 1 else ""
        out.append(
            {
                "sheet": sh.name,
                "semester": semester_hint,
                "name": title_disc,
                "code": code,
                "component": comp,
                "credits": round(credits, 4),
            }
        )
    return out


def extract(path: Path) -> list[dict]:
    wb = xlrd.open_workbook(str(path))
    collected: list[dict] = []

    for si in range(wb.nsheets):
        sh = wb.sheet_by_index(si)
        name = sh.name.strip()
        if name in ("ТИИ-1", "ТИИ-1 (почасовой)"):
            sem = "1"
        elif name in ("ТИИ-2", "ТИИ-2 (почасовой)"):
            sem = "2"
        else:
            continue
        collected.extend(parse_sheet(sh, sem))

    # Уникальность: по нормализованному названию; при дубликатах — макс. кредитов
    by_name: dict[str, dict] = {}
    for item in collected:
        key = item["name"].lower()
        if key not in by_name or item["credits"] > by_name[key]["credits"]:
            by_name[key] = item

    merged = sorted(by_name.values(), key=lambda x: x["name"].lower())
    return merged


def main():
    xls = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"c:\Users\davle\Downloads\++Расчет часов кафедры ТИИ на  2025-2026уч (Автосохраненный).xls"
    )
    data = extract(xls)
    out_path = Path(__file__).resolve().parent.parent / "data" / "disciplines_tii_2025_2026.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(data)} unique disciplines to {out_path}")


if __name__ == "__main__":
    main()
