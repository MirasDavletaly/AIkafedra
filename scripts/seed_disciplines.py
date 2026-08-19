# -*- coding: utf-8 -*-
"""
Импорт дисциплин из data/disciplines_tii_2025_2026.json (см. extract_disciplines_from_xls.py).

Запуск из корня проекта:
  .venv\\Scripts\\python scripts/seed_disciplines.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db  # noqa: E402
import subjects as sub  # noqa: E402


def main():
    init_db()
    data_path = ROOT / "data" / "disciplines_tii_2025_2026.json"
    if not data_path.is_file():
        print("Нет файла:", data_path)
        print("Сначала выполните: python scripts/extract_disciplines_from_xls.py")
        sys.exit(1)
    items = json.loads(data_path.read_text(encoding="utf-8"))
    n = 0
    for d in items:
        desc = (
            f"Импорт из расчёта кафедры ТИИ; семестр {d.get('semester', '?')}; "
            f"компонент: {d.get('component', '—')}"
        )
        sub.upsert_subject_by_name(
            d["name"],
            code=d.get("code", "") or "",
            description=desc,
            credits=float(d.get("credits", 0)),
        )
        n += 1
    print(f"Импортировано/обновлено записей: {n}")


if __name__ == "__main__":
    main()
