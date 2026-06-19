# project-management-dashboard-vera

Внутренний дашборд управления проектом «Агент Вера» — документация, иерархическая структура работ (ИСР) и канбан-доска в одном инструменте, с живым редактированием прямо в браузере.

Подробный архитектурный план: [`docs/PROJECT_DASHBOARD_PLAN.md`](docs/PROJECT_DASHBOARD_PLAN.md). Дизайн-система: [`docs/DESIGN_GUIDE.md`](docs/DESIGN_GUIDE.md) и [`DESIGN_REDESIGN_PLAN.md`](DESIGN_REDESIGN_PLAN.md).

---

## Зачем это нужно

Проектная документация, ИСР и статус задач изначально существовали как статичные файлы (`.txt`/`.html`) в репозитории — их нельзя было редактировать интерактивно, двигать задачи между стадиями или видеть прогресс по фазам. Этот дашборд решает это: документы редактируются прямо в браузере, ИСР — раскрывающееся дерево с rollup-прогрессом, канбан синхронизирован с ИСР 1:1 (каждый листовой пункт ИСР — это карточка канбана).

Авторизации нет — дашборд публичный, используется как открытая отчётность по ходу проекта.

---

## Экраны

- **Главная** (`/`) — сводка: % готовности ИСР, количество документов, ближайшие сроки, пульс канбана (donut-чарт), последние задачи по стадиям, превью бэклога.
- **Документы** (`/docs`) — список, просмотр (рендер markdown), создание/редактирование/удаление.
- **ИСР** (`/wbs`) — дерево фаз → разделов → задач с прогресс-барами, бейджами ролей, инлайн-CRUD узлов.
- **Канбан** (`/kanban`) — drag&drop-доска (`@dnd-kit`), карточки сгруппированы и отсортированы по коду ИСР в бэклоге, поиск, панель деталей задачи (описание, срок, комментарии, история изменений, связанные документы).

---

## Стек

**Backend:** FastAPI · PostgreSQL · SQLAlchemy (async) · Alembic · Pydantic v2 · Hypercorn.
Слои: `api → services → repositories → db`, плюс `schemas` (Pydantic) и `dependencies` (DI-фабрики).

**Frontend:** Vite · React 19 · TypeScript · Tailwind CSS v4 (CSS-токены, без `tailwind.config.*`) · TanStack Query (server state) · Zustand (client state) · `@dnd-kit` (drag&drop) · `react-aria-components` (доступные примитивы) · `remark`/`rehype` + DOMPurify (markdown-пайплайн для документов).

Дизайн — тёмная тема «Dark Developer Workspace» (сине-фиолетовый/бирюзовый акцент, многоуровневые поверхности, точечный glassmorphism), без сторонних UI-библиотек.

---

## Структура репозитория

```
backend/
├── main.py                  # FastAPI app
├── entrypoint.sh             # alembic upgrade head → seed_from_json.py → hypercorn
├── alembic.ini
├── requirements.txt
├── scripts/
│   ├── data/wbs_seed.json    # базовый снэпшот ИСР (247 узлов / 195 листьев)
│   ├── export_wbs_json.py    # парсит docs/AGENT_VERA_WBS.txt → обновляет wbs_seed.json
│   ├── seed_from_json.py     # сидирует ИСР+стадии из wbs_seed.json, если БД пустая (идемпотентно)
│   └── seed_initial_data.py  # альтернативный сидинг: документы из site_work_for_everyone + ИСР из .txt
└── src/
    ├── core/        # настройки (pydantic-settings), логирование
    ├── db/          # модели SQLAlchemy, сессия, миграции Alembic
    ├── repositories/
    ├── services/
    ├── schemas/
    ├── dependencies/
    └── api/

frontend/
├── index.html
├── vite.config.ts
└── src/
    ├── app.css                # дизайн-токены, тени, типографика
    ├── lib/                    # api-клиент, markdown-пайплайн, типы
    ├── components/             # ui/, layout/, docs/, wbs/, kanban/, dashboard/
    ├── routes/                 # HomePage, DocumentsPage, WbsPage, KanbanPage и др.
    └── stores/                 # Zustand (UI state)

docs/                # документация проекта «Агент Вера» (паспорт, ИСР, риски, дизайн-гайд)
nginx/               # конфиг единой точки входа для docker-compose
docker-compose.yml   # db + backend + frontend + nginx
```

---

## Запуск локально без Docker

### Backend

```bash
cd backend
python -m venv venv
venv/Scripts/activate          # Windows; на Linux/macOS — source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # заполнить креды локального Postgres (POSTGRES_HOST=localhost)
alembic upgrade head
python scripts/seed_from_json.py   # один раз — заполнит ИСР+стадии, если БД пустая
hypercorn main:app
```

Backend поднимется на `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env            # VITE_API_URL=http://localhost:8000
npm run dev -- --port 3000
```

Frontend — на `http://localhost:3000`.

---

## Запуск через Docker Compose

```bash
cp .env.example .env                              # креды Postgres для контейнера db
cp backend/.env.docker.example backend/.env.docker # креды + POSTGRES_HOST=db для контейнера backend
docker compose up -d --build
```

Дашборд будет доступен на `http://<хост>:93/` (порт выбран, чтобы не конфликтовать с другими внутренними сервисами на том же сервере — см. `docs/PROJECT_DASHBOARD_PLAN.md`, раздел 10.7).

Сервисы:

| Сервис | Назначение | Порт на хосте |
|---|---|---|
| `db` | PostgreSQL 16 | `5436` → `5432` |
| `backend` | FastAPI (только внутренняя сеть) | — |
| `frontend` | Статика Vite-бандла (nginx внутри образа, только внутренняя сеть) | — |
| `nginx` | Единая точка входа: `/` → frontend, `/api/` → backend | `93` → `80` |

`entrypoint.sh` backend-контейнера сам прогоняет `alembic upgrade head`, затем `scripts/seed_from_json.py` (идемпотентно — если ИСР уже загружена, ничего не делает) перед стартом сервера.

### Переменные окружения — где что лежит

| Файл | Используется | Ключевые переменные |
|---|---|---|
| `.env` (корень) | `docker-compose.yml` → сервис `db` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| `backend/.env` | Локальный запуск backend без Docker | `POSTGRES_HOST=localhost`, `POSTGRES_*` |
| `backend/.env.docker` | `docker-compose.yml` → сервис `backend` | `POSTGRES_HOST=db`, `POSTGRES_*` (значения должны совпадать с корневым `.env`) |
| `frontend/.env` | Локальный запуск frontend (`npm run dev`) | `VITE_API_URL` |

Каждый файл — самостоятельный (`env_file:` без подстановки переменных между сервисами); при смене пароля/имени БД нужно обновить и `.env`, и `backend/.env.docker` вручную.

---

## Сидинг данных

- **ИСР + стадии канбана** — `backend/scripts/seed_from_json.py`, запускается автоматически при старте контейнера (через `entrypoint.sh`) и вручную при локальном запуске. Источник — `backend/scripts/data/wbs_seed.json`, сгенерированный из `docs/AGENT_VERA_WBS.txt`. Идемпотентен: если в БД уже есть хотя бы один узел ИСР — пропускает.
- Чтобы обновить базовый снэпшот после изменения `docs/AGENT_VERA_WBS.txt`:
  ```bash
  cd backend
  python scripts/export_wbs_json.py
  ```
  и закоммитить обновлённый `wbs_seed.json`.
- **Документы** — не сидируются автоматически. Создаются и редактируются прямо в дашборде (`/docs` → «+ Новый документ»).

---

## Полезные команды (backend)

```bash
alembic revision --autogenerate -m "описание"   # новая миграция
alembic upgrade head                             # применить миграции
python scripts/export_wbs_json.py                # обновить wbs_seed.json из AGENT_VERA_WBS.txt
python scripts/seed_from_json.py                 # засеять ИСР+стадии (no-op, если уже есть)
```

---

## Связанные документы

- [`docs/PROJECT_DASHBOARD_PLAN.md`](docs/PROJECT_DASHBOARD_PLAN.md) — архитектурный план, модель данных, API, статус реализации по разделам.
- [`docs/DESIGN_GUIDE.md`](docs/DESIGN_GUIDE.md) — актуальная дизайн-система.
- [`DESIGN_REDESIGN_PLAN.md`](DESIGN_REDESIGN_PLAN.md) — план перехода со старой золотой темы на текущий стиль.
- [`docs/AGENT_VERA_RISK_MANAGEMENT_PLAN.md`](docs/AGENT_VERA_RISK_MANAGEMENT_PLAN.md) — реестр рисков проекта «Агент Вера» с планами реагирования.
- [`docs/AGENT_VERA_WBS.txt`](docs/AGENT_VERA_WBS.txt) — канонический источник ИСР.
