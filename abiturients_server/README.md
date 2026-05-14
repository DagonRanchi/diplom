# Система приема в Колледж экономики и техники

Современная веб-система подачи заявок на поступление:

- публичный сайт колледжа;
- форма подачи заявки с проверкой ИИН;
- чат абитуриента с администрацией;
- FastAPI backend с PostgreSQL, JWT, RBAC и Alembic;
- React + Vite + TypeScript frontend;
- административная панель с ролями и файловым менеджером папок;
- Docker Compose для локального запуска;
- `render.yaml` для деплоя на Render.

## Стек

Backend:

- FastAPI
- SQLAlchemy ORM
- PostgreSQL
- Alembic
- JWT авторизация
- Passlib/bcrypt для паролей

Frontend:

- React
- Vite
- TypeScript
- React Router
- Lucide icons

## Быстрый запуск через Docker

```bash
docker compose up --build
```

После старта:

- frontend: http://localhost:5173
- backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

Backend при запуске выполняет:

```bash
alembic upgrade head
python -m app.seed
```

Seed можно запускать повторно, он не создает дубли.

## Локальный запуск без Docker

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Для Windows PowerShell можно использовать:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/cet_admissions"
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Env-переменные

Backend:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/cet_admissions
JWT_SECRET=change-this-secret-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
CORS_ORIGINS=http://localhost:5173,http://localhost:8080
ENVIRONMENT=local
```

Frontend:

```env
VITE_API_URL=http://localhost:8000
```

## Тестовые пользователи

Все seed-пользователи создаются с паролем:

```text
admin12345
```

Аккаунты:

| Роль | Email |
| --- | --- |
| Технический администратор | tech@cet.local |
| Приемная комиссия | admissions@cet.local |
| Учебная часть | education@cet.local |
| Преподаватель | teacher@cet.local |
| Дополнительный преподаватель | teacher2@cet.local |
| Помощник | assistant@cet.local |

## Основные маршруты frontend

Публичные:

- `/`
- `/apply`
- `/chat/:applicationId`

Админ:

- `/admin/login`
- `/admin/dashboard`
- `/admin/applications`
- `/admin/file-manager`
- `/admin/applications/:id`
- `/admin/chats`
- `/admin/users`
- `/admin/settings`

Преподаватель:

- `/teacher/students`
- `/teacher/students/:id`

Помощник:

- `/assistant/chats`
- `/assistant/chats/:id`

## Проверка ИИН

ИИН должен состоять строго из 12 цифр.
Первые 6 цифр должны совпадать с датой рождения в формате `YYMMDD`.

Например:

- дата рождения: `2006-04-24`
- ИИН начинается с `060424`

Пользователю всегда показывается одна ошибка:

```text
Неправильный ИИН
```

Проверка реализована и на frontend, и на backend.

## Workflow заявок

Статусы:

- `new`
- `in_admissions_review`
- `archived_by_admissions`
- `rejected`
- `accepted_by_admissions`
- `education_review`
- `enrolled`
- `completed`

Переходы:

1. Абитуриент подает заявку.
2. Заявка попадает в папку `Приемная комиссия / Новые заявки`.
3. Приемная комиссия может архивировать, отклонить или принять заявку.
4. При принятии заявка переходит в `Учебная часть / Требуют оформления`.
5. Учебная часть назначает куратора, группу, курс и тип оплаты.
6. После сохранения полностью оформленный студент переходит в папку своей группы.
7. Преподаватель-куратор видит только своих студентов.

## Деплой на Render

В репозитории есть `render.yaml`:

- `cet-admissions-api` — Docker web service для FastAPI;
- `cet-admissions-web` — static site для React/Vite;
- `cet-admissions-db` — PostgreSQL database.

Шаги:

1. Загрузите репозиторий в GitHub/GitLab.
2. В Render выберите New Blueprint.
3. Укажите репозиторий с `render.yaml`.
4. После создания сервисов проверьте `VITE_API_URL` у frontend и `CORS_ORIGINS` у backend.
5. Backend автоматически применит миграции и seed при первом запуске.

Если Render выдаст другой URL сервисов, обновите:

- `VITE_API_URL` на URL backend;
- `CORS_ORIGINS` на URL frontend.

## API

Ключевые группы endpoint-ов:

- `POST /auth/login`
- `GET /auth/me`
- `GET /public/college-info`
- `POST /applications`
- `GET /applications/{id}/public-status`
- `GET|POST /applications/{id}/chat/messages`
- `GET|PATCH /admin/applications`
- `POST /admin/applications/{id}/archive`
- `POST /admin/applications/{id}/reject`
- `POST /admin/applications/{id}/accept`
- `POST /admin/applications/bulk/archive`
- `POST /admin/applications/bulk/reject`
- `POST /admin/applications/bulk/accept`
- `GET|PATCH /education/applications/{id}/details`
- `POST /education/applications/{id}/save`
- `GET /folders/tree`
- `POST /folders/move-items`
- `GET|POST /admin/chats/{id}/messages`
- `GET|POST /users`
- `GET /notifications`

Полная интерактивная документация доступна на `/docs`.
