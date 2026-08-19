from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from database import get_connection
from i18n import t
from config import DEFAULT_LANG

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

    def __init__(self, id, username, full_name, role, is_active=True):
        self.id        = id
        self.username  = username
        self.full_name = full_name
        self.role      = role
        self._active   = is_active

    @property
    def is_active(self):
        return self._active

    def is_admin(self):
        return self.role == "admin"

    def can_edit(self):
        return self.role in ("admin", "editor")


def get_user_by_id(user_id: int):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["full_name"],
                    row["role"], bool(row["is_active"]))
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
        return User(row["id"], row["username"], row["full_name"],
                    row["role"], bool(row["is_active"]))
    return None


def get_all_users() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, password: str, full_name: str, role: str) -> int:
    username = username.strip().lower()
    if get_user_by_username(username):
        raise ValueError(t("users.flash.exists", _current_lang(), name=username))

    pw_hash = generate_password_hash(password)
    conn    = get_connection()
    cur     = conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
        (username, pw_hash, full_name.strip(), role)
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def update_user(user_id: int, full_name: str, role: str,
                is_active: bool, new_password: str = "") -> bool:
    conn = get_connection()
    if new_password:
        pw_hash = generate_password_hash(new_password)
        conn.execute(
            "UPDATE users SET full_name=?, role=?, is_active=?, password_hash=? WHERE id=?",
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
    conn  = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if count == 0:
        create_user("admin", "admin1234", "Администратор системы", "admin")
        print("[AUTH] Создан пользователь admin / admin1234  (смените пароль!)")


ROLES = [
    ("admin",  "Администратор — полный доступ"),
    ("editor", "Редактор — добавление и редактирование"),
    ("viewer", "Наблюдатель — только просмотр"),
]

ROLE_KEYS = ["admin", "editor", "viewer"]