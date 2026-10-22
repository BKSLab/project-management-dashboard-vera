# Project Task Tracker

Личный трекер проектов и разовых задач: канбан, ИСР, свободные доски,
календарь/Гантт, документы, риски, аналитика и командный чат с проектным менеджером Верой.

Есть локальная регистрация по коду приглашения, профиль и изоляция проектов.
Личные доски и задачи можно вести отдельно от проекта. Задачи поддерживают
чек-листы, файлы, комментарии, историю, версии итогового отчёта и персональное
внимание. Календарь включает baseline, критический путь, загрузку по числу задач,
PNG/PDF и ICS. Доски поддерживают фигуры, соединители, группы, историю и SVG/PNG.

Для продолжения разработки: [память проекта](MEMORY.md) и
[инструкции агентам](AGENTS.md). Описания ниже отражают реализованное поведение.

## Запуск в Docker

Нужен Docker Compose. Настройки находятся в `backend/.env`; пример —
[backend/.env.example](backend/.env.example). Создавайте файл из примера только
при первом запуске, не заменяя существующие настройки и секреты.

Для контейнерного backend:

```dotenv
POSTGRES_HOST=db
POSTGRES_PORT=5432
QDRANT_URL=http://qdrant:6333
```

`POSTGRES_DB` и `POSTGRES_NAME` должны совпадать. Задайте собственные
`POSTGRES_PASSWORD`, `JWT_SECRET` и `REGISTRATION_INVITE_CODE`.
Для AI-функций настройте LLM/embeddings/vision своего провайдера;
`EMBEDDING_DIM` должна совпадать с размерностью выбранной embedding-модели.
Параметры и ограничения перечислены в `.env.example`.

Из корня репозитория:

```powershell
docker compose up -d --build
docker compose ps
```

Приложение: **http://localhost:5173**. Backend применяет `alembic upgrade head`
перед запуском. nginx проксирует API, MCP и WebSocket. PostgreSQL, Redis и Qdrant
поднимаются тем же Compose. Для остановки без удаления данных: `docker compose stop`.
Для запуска уже собранных образов: `docker compose up -d --no-build`.

Данные сохраняются в `data/uploads` и volumes `pg_data`/`qdrant_data`.
Перед обновлением существующей БД сохраните `pg_dump` и копию `data/uploads`.
Миграции продолжают прежнюю цепочку; откат останавливается, если новые данные
невозможно представить в старой схеме. Не пересоздавайте БД ради обновления.

Backend имеет `/health/live` и `/health/ready`; готовность проверяет PostgreSQL.
Healthcheck Compose использует внутренний порт 8000. Этот порт напрямую
на хост не опубликован. Состояние и логи: `docker compose ps` и
`docker compose logs --tail=80 backend`.

## Разработка без контейнеров приложения

Используйте Python 3.12 и Node.js 22. Базы можно оставить в Docker:

```powershell
docker compose stop backend frontend nginx
docker compose up -d db redis qdrant
```

Для локального backend в `backend/.env` нужны `POSTGRES_HOST=localhost`,
`POSTGRES_PORT=5436`, `QDRANT_URL=http://localhost:6333`,
`CHAT_REDIS_URL=redis://localhost:6381/0`. Для тех же файлов, что у Compose,
задайте `UPLOADS_PATH=../data/uploads` и `AVATARS_PATH=../data/uploads/avatars`.
При возврате к контейнерному backend верните контейнерные адреса.

В первом терминале:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\hypercorn.exe main:app --bind 127.0.0.1:8000
```

Во втором:

```powershell
cd frontend
npm ci
npm run dev
```

UI — http://localhost:5173, Swagger локального backend — http://127.0.0.1:8000/docs.
Vite обращается к API на порту 8000; production-сборка использует относительный URL.

## Доступ, файлы и помощник

Cookie-сессия используется интерфейсом. Внешние клиенты поддерживают прежние
`tt_` READ/WRITE-токены и `ttk_`-ключи с выбранными scopes. Ключи ограничены
доступом своего локального владельца; секрет показывается только при выпуске,
в БД хранится хеш. Выпуск и отзыв ключей требуют UI-сессии.
Справка и готовая конфигурация MCP доступны на `/mcp`, новые ключи — на `/my-api-keys`.

`agent:ask` разрешает помощнику читать доступные владельцу данные; изменения
требуют дополнительных scopes записи. WriteGate проверяет разрешение на запись,
опасные действия дополнительно подтверждаются. Подтверждения и результаты
повторов сохраняются в БД. Вера работает в общем виджете, проектных диалогах
и по обращению в командном чате.

В проекте одна вкладка «Чат»: начните сообщение с «Вера, …», чтобы обратиться
к проектному менеджеру. Личные проектные диалоги и знания доступны через меню
этой вкладки; их переписка не публикуется команде.

Существующий MCP доступен через `/mcp`. Опциональный отдельный процесс:

```powershell
docker compose --profile mcp up -d --build
# Или из backend с локальными адресами зависимостей:
.\venv\Scripts\python.exe -m src.mcp_server.worker
```

Адрес отдельного процесса по умолчанию — http://127.0.0.1:8021/mcp/.
Он использует те же пользователей, данные, сервисы и правила доступа.
`APP_PUBLIC_URL` задаёт внешний адрес для ссылок помощника и ICS-подписок.

Файлы сохраняются локально. Текст, CSV, PDF с текстовым слоем, DOCX и Excel
разбираются кодом проекта. Изображения обрабатываются прежним настраиваемым
vision API; его можно отключить. OCR сканированных PDF, `.doc` и презентации
не поддерживаются. Содержание файла не выводится из его имени.

## Проверки

Из `backend`:

```powershell
.\venv\Scripts\ruff.exe check src tests scripts
.\venv\Scripts\python.exe -m pytest -q --cov=src --cov-report=term --cov-fail-under=78
```

Интеграционные тесты поднимают настоящий PostgreSQL через testcontainers;
нужен работающий Docker. Пропущенная интеграционная проверка не подтверждает её результат.
Правила выбора тестов: [backend/tests/README.md](backend/tests/README.md).

Из `frontend`:

```powershell
npm run lint
npm test
npm run build
$env:PLAYWRIGHT_CHANNEL='chrome'
npm run test:e2e
```

Playwright запускает отдельный Vite на порту 4179. Можно использовать Chromium,
установленный Playwright, вместо Chrome. Браузерные сценарии используют
управляемый API; реальные SQL, транзакции, миграции и файловые операции проверяются
отдельно. Для AI используются управляемые модели, если явно не запущена live-проверка.

## Архитектура и документация

Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Qdrant и PydanticAI.
Слои: HTTP/MCP → services → repositories; отдельные storage и API clients.
Фабрики зависимостей и scopes собраны в `backend/src/dependencies`.
Frontend: React, TypeScript, Vite, Tailwind, TanStack Query, Zustand, React Flow и elkjs.

| Документ | Назначение |
| --- | --- |
| [MEMORY.md](MEMORY.md) | Текущее состояние, границы переноса, миграция и проверенные результаты |
| [AGENTS.md](AGENTS.md) | Правила дальнейшей работы с проектом |
| [FASTAPI_PATTERNS.md](FASTAPI_PATTERNS.md) | Слои, DI, транзакции, доступ, HTTP/WS/MCP и тесты backend |
| [Дизайн](docs/DESIGN_GUIDE.md) | Токены, темы, компоненты и доступность |
| [ИСР](docs/wbs.md) | Размещение задач, порядок, дерево и безопасное удаление |
| [Паспорт проекта](docs/project-passport.md) | Команда, стадии, даты и история изменения срока |
| [Личные задачи](docs/personal-tasks.md) | Переносы, итоговые отчёты, внимание и иконки |
| [Доски: контракт](docs/boards-contract.md) | Данные, ревизии, сохранение и права |
| [Доски: редактор](docs/boards-drawing.md) | Рисование, группы, шаблоны и экспорт |
| [Календарь](docs/calendar.md) | Гантт, baseline, загрузка, экспорт и ICS |
| [Риски](docs/project-risks.md) | Реестр, планы реагирования, AI и MCP |
| [Чек-листы](docs/task-checklists.md) | Данные, API и правила редактирования |
| [Аналитика](docs/analytics-context.md) | Источники свода и ограничения контекста |
| [Командный чат](docs/PROJECT_CHAT.md) | История, realtime, файлы и Вера |
| [Вера и MCP](docs/agent.md) | Runtime, подтверждения, диалоги и внешние инструменты |
| [Знания](docs/knowledge.md) | Источники, локальное извлечение, outbox, поиск и саммари |
| [Сценарии MCP](docs/mcp-skills/README.md) | Примеры работы внешнего клиента |
| [Формат retrieval eval](backend/evals/knowledge_retrieval/FORMAT.md) | Входные данные проверок поиска |
