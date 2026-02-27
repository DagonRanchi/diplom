# Abiturients Server (FastAPI)

Простой сервер для регистрации абитуриентов:
- публичная форма подачи заявки;
- админ-логин;
- просмотр всех заявок в админ-панели;
- скачивание PDF-листа по каждой заявке из админ-панели;
- хранение данных в PostgreSQL.

## 1. Локальный запуск

```bash
cd abiturients_server
python -m pip install -r requirements.txt
python app.py
```

`.env` не обязателен: приложение запустится с дефолтами (локальная SQLite база `abiturients_local.db`, админ `admin` / `admin12345`).

Если нужно переопределить настройки, создайте `.env` на основе `.env.example` и заполните переменные.

Альтернативный запуск:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Открыть:
- `http://localhost:8000/` - форма регистрации
- `http://localhost:8000/admin/login` - вход администратора
- в таблице заявок есть кнопка `Скачать PDF` для каждой записи

## 2. Переменные окружения (опционально)

- `DATABASE_URL` - URL PostgreSQL.
- `DB_SSLMODE` - режим SSL для Postgres (для внешнего Render URL обычно `require`).
- `SECRET_KEY` - ключ подписи сессии.
- `ADMIN_USERNAME` - логин админа (по умолчанию `admin`).
- `ADMIN_PASSWORD` - пароль админа (по умолчанию `admin12345`, обязательно сменить).

При первом старте автоматически:
- создаются таблицы `applications` и `admin_users`;
- создается админ с `ADMIN_USERNAME`/`ADMIN_PASSWORD`, если его еще нет.

## 3. Деплой на Render

В папке уже есть `render.yaml`.

Ваши URL базы данных:
- Internal (для Render Web Service в том же проекте):  
  `postgresql://presentation_diplom_user:Rt3B0Sm0wFZH2KW2ybkKBiXbqeGuvDlc@dpg-d6gk0n450q8c73a4suv0-a/presentation_diplom`
- External (для локального запуска):  
  `postgresql://presentation_diplom_user:Rt3B0Sm0wFZH2KW2ybkKBiXbqeGuvDlc@dpg-d6gk0n450q8c73a4suv0-a.oregon-postgres.render.com/presentation_diplom`

Что сделать:
1. Создать новый Web Service в Render из этого репозитория.
2. Указать root directory: `abiturients_server` (если не подтянулось автоматически).
3. В переменные окружения поставить:
   - `DATABASE_URL` (лучше internal URL в Render);
   - `ADMIN_PASSWORD` (свой пароль, не дефолтный).
4. Нажать Deploy.

Healthcheck:
- `GET /health` возвращает `ok`.
