# Корпоративный веб-портал УМЗ

Веб-портал для сотрудников корпорации «УМЗ» в Усть-Каменогорске с интегрированной системой электронного документооборота.

Система решает задачи:

- регистрация анкет сотрудников, заявлений и служебных документов;
- табличный реестр записей с inline-редактированием по принципу НОБД, но без перегруженных форм;
- кадровая проверка, передача в канцелярию, согласование и архивирование;
- папки и массовое перемещение карточек для работы с большим объемом документов;
- чат по каждой карточке обращения;
- роли, JWT-авторизация, уведомления и разграничение доступа.

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

Для Windows PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/umz_portal"
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Тестовые пользователи

Пароль для всех seed-пользователей:

```text
admin12345
```

| Роль | Email |
| --- | --- |
| Системный администратор | tech@umz.local |
| Отдел кадров | hr@umz.local |
| Канцелярия | docs@umz.local |
| Руководитель подразделения | manager@umz.local |
| Дополнительный руководитель | manager2@umz.local |
| Оператор поддержки | operator@umz.local |

## Основные маршруты frontend

Публичные:

- `/`
- `/request`
- `/case/:applicationId`

Рабочая зона:

- `/portal/overview`
- `/portal/registry`
- `/portal/archive`
- `/portal/cases/:id`
- `/portal/messages`
- `/portal/users`
- `/portal/settings`
- `/department/cases`
- `/operator/messages`

## Workflow документов

Статусы:

- `new` — новая карточка;
- `hr_review` — кадровая проверка;
- `approved_by_hr` — HR передал в документооборот;
- `document_review` — регистрация и обработка канцелярией;
- `manager_review` — согласование руководителем;
- `completed` — исполнено;
- `archived` — архив;
- `rejected` — отклонено.

## API

Ключевые endpoint-группы:

- `POST /auth/login`
- `GET /auth/me`
- `GET /public/portal-info`
- `POST /applications`
- `GET|PATCH /admin/applications`
- `POST /admin/applications/{id}/archive`
- `POST /admin/applications/{id}/reject`
- `POST /admin/applications/{id}/accept`
- `PATCH /admin/applications/bulk/update`
- `GET|PATCH /document-control/applications/{id}/details`
- `POST /document-control/applications/{id}/save`
- `GET /folders/tree`
- `POST /folders/move-items`
- `GET|POST /admin/chats/{id}/messages`
- `GET|POST /users`
- `GET /notifications`

Полная интерактивная документация доступна на `/docs`.
