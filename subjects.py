
from database import get_connection


def get_all_subjects() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()
    conn.close()
    return rows


def get_subject_by_id(subject_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM subjects WHERE id = ?", (subject_id,)
    ).fetchone()
    conn.close()
    return row


def add_subject(
    name: str,
    code: str = "",
    description: str = "",
    credits: float = 0.0,
) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO subjects (name, code, description, credits) VALUES (?, ?, ?, ?)",
            (name.strip(), code.strip(), description.strip(), float(credits)),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise ValueError(f"Дисциплина «{name}» уже существует.") from e
    finally:
        conn.close()


def update_subject(
    subject_id: int,
    name: str,
    code: str = "",
    description: str = "",
    credits: float = 0.0,
) -> bool:
    conn = get_connection()
    cur = conn.execute(
        """UPDATE subjects SET name = ?, code = ?, description = ?, credits = ?
           WHERE id = ?""",
        (name.strip(), code.strip(), description.strip(), float(credits), subject_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def upsert_subject_by_name(
    name: str,
    code: str = "",
    description: str = "",
    credits: float = 0.0,
) -> None:
    """Создать или обновить дисциплину по уникальному названию (для импорта)."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO subjects (name, code, description, credits)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            code = excluded.code,
            description = excluded.description,
            credits = excluded.credits
        """,
        (name.strip(), code.strip(), description.strip(), float(credits)),
    )
    conn.commit()
    conn.close()


def delete_subject(subject_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted
