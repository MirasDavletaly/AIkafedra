# AIkafedra — cybersecurity edition

Ветка `cybersecurity` — версия приложения с усиленной защитой: CSRF, rate-limit, аудит входов, безопасные cookie, security-заголовки, требование смены дефолтного пароля.

Основной функционал — тот же (учёт преподавателей / дисциплин / нагрузки, отчёты, ИИ-ассистент, RU/KZ), но security-контур переработан.

---

## Что изменилось (security changelog)

| # | Улучшение | Файл / компонент |
|---|-----------|------------------|
| 1 | **CSRF-защита** на всех POST-формах (Flask-WTF `CSRFProtect`) | `main.py`, все `templates/*.html` |
| 2 | **Rate-limit** на `/login` — 5 попыток / 5 минут на IP (Flask-Limiter) | `main.py` |
| 3 | **Security-заголовки** — CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, Permissions-Policy, HSTS (при HTTPS) | `security.py` |
| 4 | **Безопасные cookie** — `HttpOnly`, `SameSite=Lax`, `Secure` (в проде) | `config.py`, `main.py` |
| 5 | **Session fixation** — сессия сбрасывается при логине | `main.py` |
| 6 | **Open-redirect** — `?next=` валидируется, разрешён только тот же хост | `security.py: safe_next_url` |
| 7 | **Политика паролей** — минимум 10 символов, буквы + цифры (настраивается) | `security.py`, `auth.py` |
| 8 | **Генерация admin-пароля** — в проде создаётся криптостойкий пароль (не `admin1234`) | `auth.py: ensure_default_admin` |
| 9 | **Обязательная смена пароля** — после первого входа с дефолтным паролем | `auth.py`, `main.py: _enforce_password_change` |
| 10 | **Аудит входов** — таблица `login_attempts` (username, IP, success, UA, время) | `database.py`, `auth.py` |
| 11 | **`DEBUG=False` по умолчанию**, `SECRET_KEY` обязателен в проде | `config.py`, `main.py` |
| 12 | **`/logout` только POST** — защита от logout-CSRF через `<img src=/logout>` | `main.py`, `base.html` |
| 13 | **Лимит тела запроса** — `MAX_CONTENT_LENGTH=16 MiB` | `main.py` |

## Модель угроз, которые закрыты

- **CSRF** — злоумышленник не может подделать POST от имени залогиненного пользователя
- **Brute-force** входа — ограничен по IP
- **Clickjacking** — `X-Frame-Options: DENY`
- **MIME-sniffing XSS** — `X-Content-Type-Options: nosniff`
- **Cross-site cookie leakage** — `SameSite=Lax`, `Secure` (в проде)
- **Session fixation** — id сессии сбрасывается на входе
- **Open redirect** через `next=` — блокируется валидатором
- **Утечка дефолтного пароля** — в проде генерируется случайный, с обязательной сменой
- **Отсутствие следов** — попытки входа логируются в БД

## Переменные окружения

```dotenv
# --- обязательно в проде ---
SECRET_KEY=<длинная случайная строка>
FLASK_DEBUG=0

# --- рекомендуется ---
PASSWORD_MIN_LENGTH=10
LOGIN_RATE_LIMIT=5 per 5 minutes
PERMANENT_SESSION_LIFETIME_DAYS=7
ALLOW_DEFAULT_ADMIN_PASSWORD=0   # 1 — разрешить admin/admin1234 (только DEV)

# --- ИИ ---
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
```

Сгенерировать `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Установка

```bash
git clone -b cybersecurity https://github.com/MirasDavletaly/AIkafedra.git
cd AIkafedra
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Первый запуск в проде:** в логе будет напечатан пароль сгенерированного администратора — сохраните его, повторно он не выводится. При первом входе система потребует его сменить.

## Что осталось на будущее

- Переход с `'unsafe-inline'` в CSP на nonce-based (в шаблонах есть 2 inline `<script>`)
- Двухфакторная аутентификация (TOTP)
- Хранилище rate-limit — Redis вместо памяти (для многопроцессной работы)
- Ротация паролей / срок действия
- Экспорт `login_attempts` в SIEM

## Основной функционал

Не изменился. См. предыдущие README на ветках `main` / `TEST`.
