"""Security utilities: headers, safe redirects, password strength.

Централизует всё, что нужно для харденинга Flask-приложения — так проще
поддерживать единый security-контур и не размазывать логику по main.py.
"""

from __future__ import annotations

import re
import secrets
import string
from urllib.parse import urlparse, urljoin

from flask import Flask, request


# ── CSP: относительно строгая, но допускает inline-стили ──
# Многие шаблоны используют inline `style="..."`, поэтому unsafe-inline для
# style-src сохраняем. Скрипты — только self.
# NB: `'unsafe-inline'` в script-src сохранён из-за пары inline-скриптов
# в шаблонах (base.html, workload_form.html). Более строгий вариант —
# nonce-based CSP; при желании легко переключить.
_CDN = "https://cdnjs.cloudflare.com"
_DEFAULT_CSP = (
    "default-src 'self'; "
    f"script-src 'self' 'unsafe-inline' {_CDN}; "
    f"style-src 'self' 'unsafe-inline' {_CDN}; "
    "img-src 'self' data:; "
    f"font-src 'self' data: {_CDN}; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


def install_security_headers(app: Flask) -> None:
    """Навешивает после каждого ответа заголовки, ломающие типовые атаки."""

    @app.after_request
    def _apply(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        response.headers.setdefault("Content-Security-Policy", _DEFAULT_CSP)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # HSTS — только при HTTPS (иначе браузер игнорирует, но не будем засорять)
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


def safe_next_url(target: str | None, fallback: str) -> str:
    """Защита от open-redirect: разрешаем только относительные URL того же хоста.

    Возвращает `fallback`, если target пуст, содержит внешнюю схему/хост или
    начинается с `//` (protocol-relative — потенциальный редирект наружу).
    """
    if not target:
        return fallback
    # Явный protocol-relative URL — потенциальный редирект наружу
    if target.startswith("//"):
        return fallback
    host_url = request.host_url
    test_url = urlparse(urljoin(host_url, target))
    ref_url = urlparse(host_url)
    if test_url.scheme not in ("http", "https"):
        return fallback
    if test_url.netloc != ref_url.netloc:
        return fallback
    # Возвращаем как относительный путь + query + fragment
    return test_url.path + (f"?{test_url.query}" if test_url.query else "") + (
        f"#{test_url.fragment}" if test_url.fragment else ""
    )


def validate_password(password: str, min_length: int) -> str | None:
    """Возвращает None, если пароль ок, иначе — ключ ошибки для i18n."""
    if not password or len(password) < min_length:
        return "password.too_short"
    if not re.search(r"[A-Za-zА-Яа-яЁё]", password):
        return "password.needs_letter"
    if not re.search(r"\d", password):
        return "password.needs_digit"
    return None


def generate_secure_password(length: int = 16) -> str:
    """Генерирует криптостойкий пароль (буквы+цифры+символы)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_+="
    # Гарантируем наличие буквы, цифры и символа
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isalpha() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(not c.isalnum() for c in pw)
        ):
            return pw


def client_ip() -> str:
    """Возвращает IP клиента с учётом X-Forwarded-For (если стоит прокси)."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Берём самый левый — исходный клиент
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"
