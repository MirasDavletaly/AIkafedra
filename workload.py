from database import get_connection
from utils import calculate_total_credits


def get_all_workload() -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            w.id,
            t.full_name      AS teacher_name,
            t.position,
            s.name           AS subject_name,
            s.code           AS subject_code,
            w.lecture_credits,
            w.practice_credits,
            w.lab_credits,
            (w.lecture_credits + w.practice_credits + w.lab_credits) AS total_credits,
            w.semester,
            w.academic_year,
            w.teacher_id,
            w.subject_id
        FROM workload w
        JOIN teachers t ON t.id = w.teacher_id
        JOIN subjects s ON s.id = w.subject_id
        ORDER BY t.full_name, w.semester
    """).fetchall()
    conn.close()
    return rows


def get_workload_by_teacher(teacher_id: int) -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            w.id,
            s.name           AS subject_name,
            s.code           AS subject_code,
            w.lecture_credits,
            w.practice_credits,
            w.lab_credits,
            (w.lecture_credits + w.practice_credits + w.lab_credits) AS total_credits,
            w.semester,
            w.academic_year
        FROM workload w
        JOIN subjects s ON s.id = w.subject_id
        WHERE w.teacher_id = ?
        ORDER BY w.semester, s.name
    """, (teacher_id,)).fetchall()
    conn.close()
    return rows


def get_workload_entry(workload_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workload WHERE id = ?", (workload_id,)
    ).fetchone()
    conn.close()
    return row


def assign_workload(teacher_id: int, subject_id: int,
                    lecture_credits: float, practice_credits: float, lab_credits: float,
                    semester: int, academic_year: str) -> int:
    conn = get_connection()
    existing = conn.execute("""
        SELECT id FROM workload
        WHERE teacher_id = ? AND subject_id = ? AND semester = ? AND academic_year = ?
    """, (teacher_id, subject_id, semester, academic_year)).fetchone()

    if existing:
        conn.execute("""
            UPDATE workload
            SET lecture_credits = ?, practice_credits = ?, lab_credits = ?
            WHERE id = ?
        """, (lecture_credits, practice_credits, lab_credits, existing["id"]))
        conn.commit()
        row_id = existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO workload
                (teacher_id, subject_id, lecture_credits, practice_credits, lab_credits, semester, academic_year)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (teacher_id, subject_id, lecture_credits, practice_credits, lab_credits, semester, academic_year))
        conn.commit()
        row_id = cur.lastrowid

    conn.close()
    return row_id


def update_workload(workload_id: int, lecture_credits: float,
                    practice_credits: float, lab_credits: float,
                    semester: int, academic_year: str) -> bool:
    conn = get_connection()
    cur = conn.execute("""
        UPDATE workload
        SET lecture_credits = ?, practice_credits = ?, lab_credits = ?,
            semester = ?, academic_year = ?
        WHERE id = ?
    """, (lecture_credits, practice_credits, lab_credits, semester, academic_year, workload_id))
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def delete_workload(workload_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM workload WHERE id = ?", (workload_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_teacher_total_credits(teacher_id: int) -> float:
    conn = get_connection()
    row = conn.execute("""
        SELECT COALESCE(SUM(lecture_credits + practice_credits + lab_credits), 0) AS total
        FROM workload
        WHERE teacher_id = ?
    """, (teacher_id,)).fetchone()
    conn.close()
    return round(row["total"], 2) if row else 0.0


def get_workload_stats() -> dict:
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COUNT(*)                            AS entries,
            COALESCE(SUM(lecture_credits), 0)   AS total_lecture,
            COALESCE(SUM(practice_credits), 0)  AS total_practice,
            COALESCE(SUM(lab_credits), 0)       AS total_lab,
            COUNT(DISTINCT teacher_id)          AS teachers_with_load
        FROM workload
    """).fetchone()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    for k in ("total_lecture", "total_practice", "total_lab"):
        d[k] = round(d[k] or 0, 2)
    return d
