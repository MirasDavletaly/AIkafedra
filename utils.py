
from config import POSITION_MAX_WORKLOAD, MAX_WORKLOAD_DEFAULT, HOURS_PER_CREDIT, DEFAULT_LANG
from i18n import t


def get_max_workload_for_position(position: str) -> int:
    return POSITION_MAX_WORKLOAD.get(position, MAX_WORKLOAD_DEFAULT)


def calculate_total_credits(lecture: float, practice: float, lab: float) -> float:
    """Сумма кредитов по видам занятий (лекции + практика + лаб.)."""
    return float(lecture or 0) + float(practice or 0) + float(lab or 0)


def credits_to_hours(credits: float) -> float:
    """Перевод кредитов в академические часы (Приложение 3, п. 1–2 PDF)."""
    return round(float(credits or 0) * HOURS_PER_CREDIT, 2)


def workload_status(current: float, maximum: float, lang: str = DEFAULT_LANG) -> dict:
    """Статус загруженности преподавателя (в кредитах).

    Возвращает dict с полями:
      percent, label (локализованная), label_key (i18n-ключ), color.
    Шаблоны могут перевести label через t(label_key, current_lang).
    """
    if not maximum:
        return {"percent": 0, "label": t("status.none", lang),
                "label_key": "status.none", "color": "secondary"}

    percent = round(current / maximum * 100, 1)

    if percent < 60:
        label_key, color = "status.low", "info"
    elif percent < 85:
        label_key, color = "status.normal", "success"
    elif percent <= 100:
        label_key, color = "status.high", "warning"
    else:
        label_key, color = "status.overload", "danger"

    return {"percent": min(percent, 100), "label": t(label_key, lang),
            "label_key": label_key, "color": color}


def validate_credits(value, field_name: str) -> tuple[float, str | None]:
    """Парсит дробное значение кредитов (≥ 0). Возвращает (значение, ошибка)."""
    try:
        if value is None or value == "":
            return 0.0, None
        val = float(str(value).replace(",", "."))
        if val < 0:
            raise ValueError
        return round(val, 2), None
    except (ValueError, TypeError):
        return 0.0, f"Поле «{field_name}» должно быть неотрицательным числом."


def format_teacher_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    return full_name
