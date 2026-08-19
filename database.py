import sqlite3
from config import DATABASE_PATH, HOURS_PER_CREDIT


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # включаем поддержку FK
    return conn


def init_db():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name    TEXT    NOT NULL,          -- ФИО
            position     TEXT    NOT NULL,          -- Должность
            rate         REAL    NOT NULL DEFAULT 1.0,  -- Ставка (0.25 … 1.5)
            max_workload REAL    NOT NULL DEFAULT 30,  -- Макс. нагрузка (кредитов/год)
            email        TEXT,                      -- Email (опционально)
            created_at   TEXT    DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,    -- Название дисциплины
            code        TEXT,                       -- Код дисциплины (напр. CS401)
            description TEXT,                       -- Краткое описание
            credits     REAL    NOT NULL DEFAULT 0, -- Зачётные единицы (кредиты) по УП
            created_at  TEXT    DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workload (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id        INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
            subject_id        INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
            lecture_credits   REAL    NOT NULL DEFAULT 0,   -- Лекции (кредитов)
            practice_credits  REAL    NOT NULL DEFAULT 0,   -- Практические (кредитов)
            lab_credits       REAL    NOT NULL DEFAULT 0,   -- Лабораторные (кредитов)
            semester          INTEGER NOT NULL DEFAULT 1,   -- Семестр (1 или 2)
            academic_year     TEXT    NOT NULL DEFAULT '2025-2026',
            created_at        TEXT    DEFAULT (datetime('now')),
            UNIQUE(teacher_id, subject_id, semester, academic_year)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,       -- Логин (строчные)
            password_hash TEXT    NOT NULL,              -- Хэш пароля (werkzeug)
            full_name     TEXT    NOT NULL,              -- ФИО / отображаемое имя
            role          TEXT    NOT NULL DEFAULT 'viewer', -- admin|editor|viewer
            is_active     INTEGER NOT NULL DEFAULT 1,    -- 1=активен, 0=заблокирован
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    _migrate_subjects_credits()
    _migrate_hours_to_credits()
    _migrate_teachers_rate()
    print("[DB] База данных инициализирована успешно.")


def _migrate_teachers_rate():
    """Добавляет столбец rate (ставка) к таблице teachers, если его ещё нет."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(teachers)")
    cols = {row[1] for row in cur.fetchall()}
    if "rate" not in cols:
        cur.execute("ALTER TABLE teachers ADD COLUMN rate REAL NOT NULL DEFAULT 1.0")
        conn.commit()
        print("[DB] Миграция: добавлен столбец teachers.rate (ставка)")
    conn.close()


def _migrate_subjects_credits():
    """Добавляет столбец credits к существующим базам (до появления поля в схеме)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(subjects)")
    cols = {row[1] for row in cur.fetchall()}
    if "credits" not in cols:
        cur.execute(
            "ALTER TABLE subjects ADD COLUMN credits REAL NOT NULL DEFAULT 0"
        )
        conn.commit()
        print("[DB] Миграция: добавлен столбец subjects.credits")
    conn.close()


def _migrate_hours_to_credits():
    """Переводит старую схему «нагрузка в часах» в «нагрузка в кредитах».

    Согласно П ЕНУ K.V.14-22 (Приложение 3): 1 кредит = 15 ак. часов
    для чтения лекций, проведения практических (семинарских) и
    лабораторных занятий. Пересчёт: credits = hours / 15.
    Также пересчитываем teachers.max_workload (исторически в часах/год).
    """
    conn = get_connection()
    cur = conn.cursor()

    # ── workload: переименование колонок и пересчёт ─────────
    cur.execute("PRAGMA table_info(workload)")
    wcols = {row[1] for row in cur.fetchall()}

    rename_map = [
        ("lecture_hours",  "lecture_credits"),
        ("practice_hours", "practice_credits"),
        ("lab_hours",      "lab_credits"),
    ]
    renamed_any = False
    for old, new in rename_map:
        if old in wcols and new not in wcols:
            cur.execute(f"ALTER TABLE workload RENAME COLUMN {old} TO {new}")
            renamed_any = True
    if renamed_any:
        # Пересчёт значений (часы → кредиты)
        cur.execute(f"""
            UPDATE workload
            SET lecture_credits  = ROUND(lecture_credits  / {HOURS_PER_CREDIT}, 2),
                practice_credits = ROUND(practice_credits / {HOURS_PER_CREDIT}, 2),
                lab_credits      = ROUND(lab_credits      / {HOURS_PER_CREDIT}, 2)
        """)
        conn.commit()
        print(f"[DB] Миграция: workload переведён из часов в кредиты "
              f"(1 кредит = {int(HOURS_PER_CREDIT)} ак.ч.)")

    # ── teachers.max_workload: пересчёт (часы/год → кредиты/год) ─────
    cur.execute("SELECT id, max_workload FROM teachers")
    rows = cur.fetchall()
    # Эвристика: если значение > 200, это историческое значение в часах —
    # пересчитываем в кредиты. Иначе считаем, что данные уже в кредитах.
    needs_update = [r for r in rows if (r["max_workload"] or 0) > 200]
    if needs_update:
        for r in needs_update:
            new_val = round((r["max_workload"] or 0) / HOURS_PER_CREDIT)
            cur.execute(
                "UPDATE teachers SET max_workload = ? WHERE id = ?",
                (new_val, r["id"]),
            )
        conn.commit()
        print(f"[DB] Миграция: teachers.max_workload переведён в кредиты "
              f"({len(needs_update)} строк)")

    conn.close()
