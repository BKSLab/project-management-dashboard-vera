# Project Management Dashboard Vera

Персональный таск-трекер проекта «Агент Вера»: канбан-доска, иерархическая структура работ (ИСР), проектные документы и сводка состояния проекта в одном интерфейсе.

Проект рассчитан на первоначальную загрузку базовой ИСР из версионированного JSON-снэпшота. После этого данные живут в PostgreSQL и изменяются через интерфейс таск-трекера. Авторизации в текущем контуре нет — это осознанное ограничение проекта.

## Текущее состояние

Реализованы и работают:

- главная страница со сводными показателями и «Пульсом канбана» в виде шкал прогресса;
- канбан с drag-and-drop, сохранённым порядком карточек и центральным модальным окном задачи;
- описание, срок, файлы, комментарии, история изменений и связанные документы внутри задачи;
- дерево ИСР с rollup-прогрессом и синхронизацией листовых работ с канбаном;
- создание, редактирование, удаление и связывание Markdown-документов;
- полнотекстовый поиск PostgreSQL по задачам, комментариям и документам;
- поиск по началу русского слова и подсветка найденных фрагментов;
- миграции Alembic, проверяемая предзагрузка ИСР и подробное логирование backend-запросов;
- API v1 с OpenAPI/Swagger по адресу `/docs`.

## Архитектура

Backend следует слоистой схеме:

```text
HTTP endpoint → service → repository → PostgreSQL
                       ↘ storage → локальный диск
```

- `api/v1/endpoints` — HTTP-контракт, OpenAPI, преобразование доменных ошибок в ответы;
- `services` — бизнес-сценарии и сборка данных из нескольких репозиториев;
- `repositories` — SQLAlchemy-запросы, транзакции и преобразование ошибок БД;
- `db/models` — одна SQLAlchemy-модель на файл;
- `schemas` — Pydantic-схемы запросов и ответов;
- `dependencies` — трёхуровневый граф FastAPI Depends;
- `exceptions` — отдельная иерархия ошибок для каждого домена;
- `src/main.py` — FastAPI-приложение, lifespan, CORS и системные обработчики ошибок;
- `main.py` — совместимая точка входа для `hypercorn main:app`.

Правила backend-архитектуры зафиксированы в [`FASTAPI_PATTERNS.md`](FASTAPI_PATTERNS.md).

Frontend построен на React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query и `@dnd-kit`. Запросы собраны в `frontend/src/lib/api.ts`: локально используется `http://localhost:8000`, а Docker-сборка обращается к API через относительный путь.

## Структура репозитория

```text
backend/
├── main.py                         # совместимая точка входа
├── logging.ini                     # единая конфигурация логирования
├── entrypoint.sh                   # миграции → проверка ИСР → Hypercorn
├── requirements.txt
├── requirements-dev.txt
├── scripts/
│   ├── data/wbs_seed.json          # базовая ИСР: 247 узлов
│   ├── export_wbs_json.py          # экспорт ИСР в JSON
│   ├── seed_from_json.py           # идемпотентная загрузка ИСР
│   └── seed_initial_data.py        # опциональная загрузка документов
├── src/
│   ├── api/v1/endpoints/
│   ├── core/
│   ├── db/alembic/versions/
│   ├── db/models/
│   ├── dependencies/
│   ├── exceptions/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── storage/
│   └── utils/
└── tests/
    ├── unit/services/
    ├── api/endpoints/
    └── integration/repositories/

frontend/
├── src/components/
│   ├── dashboard/
│   ├── docs/
│   ├── files/
│   ├── kanban/
│   ├── layout/
│   ├── ui/
│   └── wbs/
├── src/lib/
├── src/routes/
└── src/stores/

docs/                               # планы, дизайн-гайд и материалы проекта
docker-compose.yml                  # PostgreSQL + backend + frontend + nginx
nginx/nginx.conf                    # единая точка входа в Docker
```

## Поиск

Векторный поиск хранится непосредственно в PostgreSQL в вычисляемых `tsvector`-полях:

| Сущность | Поля поиска | Приоритет |
|---|---|---|
| Задача | `title`, `description_md` | заголовок выше описания |
| Комментарий | `body_md`, `author_name` | текст выше автора |
| Документ | `title`, `content_md` | заголовок выше содержимого |

Для каждого вектора создан GIN-индекс. Запрос строится через `websearch_to_tsquery`; для обычного текста дополнительно поддерживается безопасный префиксный поиск от трёх символов, поэтому `пользова` находит формы слова «пользователь». Спецсимволы не приводят к синтаксическим ошибкам. Backend формирует фрагменты через `ts_headline`, а frontend выделяет совпадения жёлтым цветом.

По коду ИСР выполняется отдельный безопасный поиск по подстроке. Результаты канбана сохраняют предметный порядок карточек, а не сортируются по релевантности.

## Локальный запуск

### PostgreSQL и backend

Требуется Python 3.12 и доступный PostgreSQL 16.

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Заполните `backend/.env`, затем выполните:

```powershell
alembic upgrade head
python scripts/seed_from_json.py
hypercorn main:app
```

Backend доступен на `http://127.0.0.1:8000`:

- Swagger UI: `http://127.0.0.1:8000/docs`;
- OpenAPI: `http://127.0.0.1:8000/openapi.json`;
- API: `http://127.0.0.1:8000/api/v1`.

Проверка после запуска:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/kanban/stages
```

Каждый вызов endpoint-а пишет в консоль начало и успешное завершение запроса. Если сервер стартовал, но запросов в логах нет, проверьте, какой процесс занимает порт:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite по умолчанию откроет `http://localhost:5173`. При необходимости фиксированного порта:

```powershell
npm run dev -- --port 3000
```

Frontend не требует `.env`: при локальном запуске backend ожидается на `http://localhost:8000`.

## Запуск через Docker Compose

```bash
docker compose up -d --build
```

PostgreSQL и backend используют единый файл `backend/.env`. Для Docker в нём должны быть активны `POSTGRES_HOST=db`, `POSTGRES_PORT=5432`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_NAME` и `POSTGRES_DB`.

После запуска интерфейс доступен на `http://<хост>:93/`.

| Сервис | Назначение | Порт хоста |
|---|---|---|
| `db` | PostgreSQL 16 | `5436` |
| `backend` | FastAPI/Hypercorn | только внутренняя сеть |
| `frontend` | собранная Vite-статика | только внутренняя сеть |
| `nginx` | frontend и proxy `/api/` | `93` |

`backend/entrypoint.sh` последовательно:

1. применяет `alembic upgrade head`;
2. запускает `scripts/seed_from_json.py`;
3. запускает Hypercorn с access/error logs в stdout.

Docker-конфигурация не выполняет отдельный импорт документов и не очищает существующую БД.

Файлы задач сохраняются на хосте в `data/uploads` и монтируются в backend как `/app/uploads`. Каталог не входит в Git и сохраняется при пересоздании контейнера. Для полного резервного копирования нужны одновременно дамп PostgreSQL и каталог `data/uploads`.

## Файлы задач

К задаче можно прикрепить до 20 файлов размером до 10 МБ каждый. Поддерживаются изображения, PDF, документы Office, текстовые файлы и распространённые архивы. SVG, HTML и исполняемые файлы не принимаются.

В PostgreSQL хранятся исходное имя, MIME-тип, размер и уникальный storage key. Физическое содержимое находится в `data/uploads/tasks/<task_id>/`; безопасное растровое изображение показывается inline, остальные типы выдаются для скачивания. При удалении задачи удаляются и её метаданные, и физический каталог файлов.

## ИСР и начальные данные

Канонический снэпшот находится в `backend/scripts/data/wbs_seed.json` и содержит 247 узлов. `InitialDataService` проверяет:

- наличие пяти базовых стадий канбана;
- наличие всех ожидаемых кодов ИСР;
- наличие связанной задачи у каждого листового узла;
- версионированный маркер `vera_wbs_v1` в таблице `seed_state`.

Повторный запуск не перезаписывает названия, статусы, сроки и пользовательские задачи. Если базовый узел или его листовая задача отсутствуют, загрузчик восстановит недостающую запись. Пользовательские узлы сверх базового набора сохраняются.

Миграции содержат только изменения схемы. Импорт и восстановление данных выполняются отдельными скриптами.

Чтобы сформировать снэпшот заново:

```powershell
cd backend
python scripts/export_wbs_json.py
```

Документы по умолчанию создаются через интерфейс. Опциональный импорт документов и ИСР доступен через `scripts/seed_initial_data.py`.

## Основные API-маршруты

Все маршруты имеют префикс `/api/v1`.

| Метод | Маршрут | Назначение |
|---|---|---|
| `GET/POST` | `/documents` | список/поиск и создание документов |
| `GET/PATCH/DELETE` | `/documents/{slug}` | просмотр, изменение и удаление документа |
| `GET` | `/documents/{slug}/links` | связи документа с задачами и ИСР |
| `GET/POST` | `/kanban/stages` | список и создание стадий |
| `PATCH/DELETE` | `/kanban/stages/{id}` | изменение и удаление пустой стадии |
| `GET/POST` | `/kanban/tasks` | список/поиск и создание задач |
| `GET/PATCH/DELETE` | `/kanban/tasks/{id}` | просмотр, изменение и удаление ручной задачи |
| `PATCH` | `/kanban/tasks/{id}/move` | перемещение карточки с сохранением позиции |
| `GET/POST` | `/kanban/tasks/{id}/comments` | комментарии задачи |
| `GET/POST` | `/kanban/tasks/{id}/attachments` | список и загрузка файлов задачи |
| `GET/DELETE` | `/kanban/tasks/{id}/attachments/{attachment_id}...` | получение содержимого и удаление файла |
| `GET` | `/kanban/tasks/{id}/activity` | история значимых изменений |
| `GET` | `/kanban/tasks/{id}/links` | связанные документы |
| `GET` | `/wbs/tree` | полное дерево ИСР с rollup-прогрессом |
| `POST/PATCH/DELETE` | `/wbs/items...` | управление узлами ИСР |
| `POST/DELETE` | `/document-links...` | управление связями документов |

Полный контракт с примерами ответов доступен в Swagger UI.

## Проверки перед коммитом

Backend:

```powershell
cd backend
ruff check .
ruff format --check .
flake8 .
pytest -q
alembic check
```

Интеграционные repository-тесты используют настоящий PostgreSQL через Testcontainers и требуют запущенный Docker. При локально недоступном Docker они пропускаются; обычные unit/API-тесты продолжают выполняться.

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

CI в репозитории пока не настроен: проверки запускаются локально перед commit/push.

## Документация

- [`FASTAPI_PATTERNS.md`](FASTAPI_PATTERNS.md) — обязательные backend-паттерны;
- [`docs/PROJECT_DASHBOARD_PLAN.md`](docs/PROJECT_DASHBOARD_PLAN.md) — актуальная архитектура и принятые решения;
- [`docs/DESIGN_GUIDE.md`](docs/DESIGN_GUIDE.md) — дизайн-система интерфейса;
- [`DESIGN_REDESIGN_PLAN.md`](DESIGN_REDESIGN_PLAN.md) — выполненный план редизайна;
- [`docs/AGENT_VERA_RISK_MANAGEMENT_PLAN.md`](docs/AGENT_VERA_RISK_MANAGEMENT_PLAN.md) — риски проекта;
- `docs/AGENT_VERA_WBS.txt` — исходный текст ИСР, если файл присутствует в рабочем наборе проекта.

## Осознанные ограничения

- авторизация пока не реализуется;
- внешние API и LLM-клиенты отсутствуют;
- списки канбана, стадий и дерево ИСР возвращаются целиком, поскольку frontend строит полное состояние доски и иерархии;
- Hunspell и автоматическое исправление опечаток через `pg_trgm` пока не подключены;
- frontend production bundle требует дальнейшего code splitting, но собирается корректно.
