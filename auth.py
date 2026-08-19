from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from database import get_connection
from i18n import t
from config import (
    DEFAULT_LANG,
    PASSWORD_MIN_LENGTH,
    ALLOW_DEFAULT_ADMIN_PASSWORD,
)
from security import validate_password, generate_secure_password

try:
    from flask import has_request_context, session
except Exception:  # pragma: no cover
    has_request_context = lambda: False  # type: ignore
    session = None  # type: ignore


def _current_lang():
    try:
        if has_request_context() and session is not None:
            return session.get("lang", DEFAULT_LANG)
    except Exception:
        pass
    return DEFAULT_LANG


class User(UserMixin):

    def __init__(self, id, username, full_name, role,
                 is_active=True, must_change_password=False):
        self.id                    = id
        self.username              = username
        self.full_name             = full_name
        self.role                  = role
        self._active               = is_active
        self.must_change_password  = must_change_password

    @property
    def is_active(self):
        return self._active

    def is_admin(self):
        return self.role == "admin"

    def can_edit(self):
        return self.role in ("admin", "editor")


def _row_to_user(row) -> "User":
    return User(
        row["id"], row["username"], row["full_name"], row["role"],
        bool(row["is_active"]),
        bool(row["must_change_password"]) if "must_change_password" in row.keys() else False,
    )


def get_user_by_id(user_id: int):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return _row_to_user(row)
    return None


def get_user_by_username(username: str):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
    ).fetchone()
    conn.close()
    return row


def verify_password(username: str, password: str):
    row = get_user_by_username(username)
    if row and row["is_active"] and check_password_hash(row["password_hash"], password):
        return _row_to_user(row)
    return None


def record_login_attempt(username: str, ip: str, success: bool, user_agent: str = "") -> None:
    """Пишет в аудит-лог попытку входа. Ошибки БД не должны ломать логин."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO login_attempts (username, ip, success, user_agent) "
            "VALUES (?, ?, ?, ?)",
            ((username or "").strip().lower()[:64], ip[:64], int(bool(success)), (user_agent or "")[:255]),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # pragma: no cover
        print(f"[AUTH] Не удалось записать попытку входа: {e}")


def get_recent_login_attempts(limit: int = 100) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, ip, success, user_agent, created_at "
        "FROM login_attempts ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_must_change_password(user_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET must_change_password = 0 WHERE id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_all_users() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _ensure_password_strength(password: str) -> None:
    err = validate_password(password, PASSWORD_MIN_LENGTH)
    if err:
        raise ValueError(t(err, _current_lang(), min=PASSWORD_MIN_LENGTH))


def create_user(username: str, password: str, full_name: str, role: str,
                must_change_password: bool = False) -> int:
    username = username.strip().lower()
    if get_user_by_username(username):
        raise ValueError(t("users.flash.exists", _current_lang(), name=username))

    _ensure_password_strength(password)

    pw_hash = generate_password_hash(password)
    conn    = get_connection()
    cur     = conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role, must_change_password) "
        "VALUES (?,?,?,?,?)",
        (username, pw_hash, full_name.strip(), role, int(bool(must_change_password))),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def update_user(user_id: int, full_name: str, role: str,
                is_active: bool, new_password: str = "") -> bool:
    conn = get_connection()
    if new_password:
        _ensure_password_strength(new_password)
        pw_hash = generate_password_hash(new_password)
        conn.execute(
            "UPDATE users SET full_name=?, role=?, is_active=?, password_hash=?, "
            "must_change_password=0 WHERE id=?",
            (full_name.strip(), role, int(is_active), pw_hash, user_id)
        )
    else:
        conn.execute(
            "UPDATE users SET full_name=?, role=?, is_active=? WHERE id=?",
            (full_name.strip(), role, int(is_active), user_id)
        )
    conn.commit()
    ok = conn.execute("SELECT changes()").fetchone()[0] > 0
    conn.close()
    return ok


def change_password(user_id: int, new_password: str) -> None:
    _ensure_password_strength(new_password)
    pw_hash = generate_password_hash(new_password)
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
        (pw_hash, user_id),
    )
    conn.commit()
    conn.close()


def delete_user(user_id: int) -> bool:
    conn   = get_connection()
    target = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if target and target["role"] == "admin":
        admins = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1"
        ).fetchone()[0]
        if admins <= 1:
            conn.close()
            raise ValueError(t("users.flash.last_admin", _current_lang()))
    cur = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def ensure_default_admin():
    """Создаёт администратора при пустой БД.

    - Если `ALLOW_DEFAULT_ADMIN_PASSWORD=1` (DEBUG-режим по умолчанию) —
      создаётся admin с фиксированным паролем `admin1234` и флагом
      обязательной смены при первом входе.
    - Иначе (прод) — генерируется криптостойкий пароль и печатается в лог
      один раз при старте. Флаг must_change_password тоже выставляется.
    """
    conn  = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if count > 0:
        return

    if ALLOW_DEFAULT_ADMIN_PASSWORD:
        # DEBUG-режим: короткий пароль запрещён валидатором, обходим напрямую.
        pw_hash = generate_password_hash("admin1234")
        conn = get_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role, must_change_password) "
            "VALUES (?,?,?,?,1)",
            ("admin", pw_hash, "Администратор системы", "admin"),
        )
        conn.commit()
        conn.close()
        print("[AUTH] Создан пользователь admin / admin1234 (DEBUG)."
              " Требуется смена пароля при первом входе.")
    else:
        # Прод: генерируем сильный пароль и печатаем его один раз.
        pw = generate_secure_password(16)
        create_user("admin", pw, "Администратор системы", "admin",
                    must_change_password=True)
        print("=" * 60)
        print("[AUTH] Создан администратор:")
        print(f"       username: admin")
        print(f"       password: {pw}")
        print("       Сохраните пароль — он больше не будет показан.")
        print("       Требуется смена при первом входе.")
        print("=" * 60)


ROLES = [
    ("admin",  "Администратор — полный доступ"),
    ("editor", "Редактор — добавление и редактирование"),
    ("viewer", "Наблюдатель — только просмотр"),
]

ROLE_KEYS = ["admin", "editor", "viewer"]
