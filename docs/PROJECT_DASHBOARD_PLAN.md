# Дашборд управления проектом — архитектурный план

> Статус: backend и все 4 экрана фронтенда (Документы, ИСР, Канбан, Главная) реализованы и проверены через build/type-check/API (см. разделы 10.1–10.6). Осталось: `docker-compose.yml`. Дата обновления: 2026-06-18.
> Это план **нового, отдельного проекта** `project_dashboard`. Он не модифицирует код `site_work_for_everyone` — только переиспользует его дизайн-систему и архитектурные конвенции как образец.

---

## Содержание

1. [Зачем это нужно](#1-зачем-это-нужно)
2. [Принятые решения](#2-принятые-решения)
3. [Расположение и структура репозитория](#3-расположение-и-структура-репозитория)
4. [Дизайн-система: что переносим 1:1](#4-дизайн-система-что-переносим-11)
5. [Модель данных](#5-модель-данных)
6. [Backend: структура и API](#6-backend-структура-и-api)
7. [Frontend: структура и экраны](#7-frontend-структура-и-экраны)
8. [WBS ↔ канбан: как это работает на практике](#8-wbs--канбан-как-это-работает-на-практике)
9. [Сидирование начальных данных](#9-сидирование-начальных-данных)
10. [Пошаговый план реализации](#10-пошаговый-план-реализации)
11. [Критерии готовности и проверка](#11-критерии-готовности-и-проверка)
12. [Сознательно не делаем в v1](#12-сознательно-не-делаем-в-v1)

---

## 1. Зачем это нужно

Вся проектная документация по «Агенту Вере» (паспорт проекта, описание, дорожная карта, ИСР, матрица стейкхолдеров, технический план) и рабочая документация платформы (`BUGS.md`, `DESIGN_GUIDE.md`, `ADMIN_STATS_GUIDE.md`, `FRONTEND_AUDIT_REPORT.md` и др.) сейчас существует как статичные файлы в корне репозитория. Из этого вытекают три проблемы:

1. **Документы нельзя редактировать интерактивно** — любое изменение требует открыть файл в IDE, отредактировать markdown/HTML руками, закоммитить.
2. **Нет интерактивного канбана** — ИСР (`AGENT_VERA_WBS.txt`, `AGENT_VERA_WBS.html`) фиксирует задачи и роли, но не отражает текущий статус выполнения, нет возможности подвигать задачу между стадиями, оставить комментарий, проставить срок.
3. **ИСР существует только как текст/HTML-таблица** — нет дерева, по которому можно кликать, сворачивать/разворачивать, видеть % выполнения по фазам.

Решение — отдельный веб-дашборд: просмотр + редактирование документации, канбан-доска задач и дерево ИСР, связанное с канбаном.

---

## 2. Принятые решения

| Вопрос | Решение | Почему |
|---|---|---|
| Где живёт новый проект | Отдельный репозиторий/каталог, не подкаталог `site_work_for_everyone` | Чтобы не мешать продуктовому коду «Работы для всех»; разный жизненный цикл, разный деплой |
| Frontend-фреймворк | **Vite + React SPA**, не Next.js | Внутренний/отчётный инструмент без необходимости в SSR и SEO — Vite даёт более простой и быстрый стек |
| Авторизация | **Не нужна** | Дашборд публичный, используется как открытая отчётность по ходу проекта |
| Связь WBS ↔ канбан | **ИСР — источник задач.** Каждый листовой пункт ИСР (например `1.1.1`) — это и есть карточка канбана (1:1 связь через FK). Промежуточные узлы (`1.1`, фазы) — узлы группировки в дереве с rollup-статусом | Не плодим две независимые системы учёта задач; дерево ИСР становится "живой" визуализацией прогресса |
| Backend | FastAPI + PostgreSQL + Alembic, по конвенциям `backend/` основного проекта | Единый стиль кода у разработчика, меньше когнитивной нагрузки при переключении между проектами |
| Дизайн | Точно тот же визуальный язык, что в `frontend/` (тёмная тема, золотой акцент, токены) | Чтобы инструменты разработчика ощущались как единая экосистема |
| UI-библиотека | **Нет** — своя дизайн-система (CSS-токены + `react-aria-components` + инлайн SVG), не MUI и не shadcn/ui | Любая готовая библиотека визуально конфликтует с уже сложившимся стилем основного проекта, который мы клонируем |
| Управление состоянием | Server state — **TanStack Query** (с optimistic updates), client state (открытые панели, выбранная задача, фильтры) — **Zustand** | Тот же паттерн, что уже используется в `frontend/` (`stores/auth.ts` + TanStack Query); не изобретаем новый подход |
| История изменений задачи | **Да, в v1** — таблица `TaskActivity`, лог смены стадии/срока | Дашборд — это публичная отчётность по ходу проекта; история статусов — часть этой отчётности, не опциональная фича |

---

## 3. Расположение и структура репозитория

```
D:\BKS.Lab\python\my_projects\project_dashboard\        ← новый, отдельный проект (сосед site_work_for_everyone)
├── backend/
│   ├── main.py
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── scripts/
│   │   └── seed_initial_data.py
│   └── src/
│       ├── core/
│       ├── db/
│       ├── repositories/
│       ├── services/
│       ├── schemas/
│       ├── dependencies/
│       └── api/
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── src/
│       ├── app.css
│       ├── lib/
│       ├── components/
│       ├── routes/
│       └── main.tsx
├── docker-compose.yml        # backend + postgres + frontend (опционально, по образцу корневого compose)
└── README.md
```

---

## 4. Дизайн-система: что переносим 1:1

Источник истины: `frontend/src/app/globals.css` и `frontend/src/components/ui/*` текущего проекта, плюс `DESIGN_GUIDE.md`.

### 4.1. CSS-токены (Tailwind v4, `@theme inline`, без `tailwind.config.*`)

```css
@import "tailwindcss";

:root {
  --background: #0A0A0A;
  --foreground: #F0F0F0;
  --accent: #F5B800;
  --accent-hover: #E0A800;
  --accent-foreground: #0A0A0A;
  --surface: #1A1A1A;
  --surface-hover: #252525;
  --border: #2D2D2D;
  --muted: #999999;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-accent: var(--accent);
  --color-accent-hover: var(--accent-hover);
  --color-accent-foreground: var(--accent-foreground);
  --color-surface: var(--surface);
  --color-surface-hover: var(--surface-hover);
  --color-border: var(--border);
  --color-muted: var(--muted);
}

body { background: var(--background); color: var(--foreground); }

@keyframes braille-dot {
  0%, 100% { transform: scale(0.35); background-color: var(--border); box-shadow: none; }
  50% {
    transform: scale(1);
    background-color: var(--accent);
    box-shadow: 0 0 8px var(--accent), 0 0 16px color-mix(in srgb, var(--accent) 40%, transparent);
  }
}
```

Этот файл копируется в `frontend/src/app.css` нового проекта **без изменений**.

### 4.2. UI-примитивы — переносятся как есть

Из `frontend/src/components/ui/`: `Button.tsx`, `Modal.tsx` (на `react-aria-components`), `Badge.tsx`, `Spinner.tsx`, `ErrorMessage.tsx`, `EmptyState.tsx`, `Pagination.tsx`, `SkipLink.tsx`, `FocusHeading.tsx`. Все они — чистый React, не зависят от Next.js, переносятся файл-в-файл.

`ServiceError.tsx` и `SourceBadge.tsx` используют `next/link`/`next/image` — дашборду они не нужны напрямую, не переносим.

### 4.3. Markdown pipeline — переносится как есть

Из `frontend/src/lib/blog/posts.ts`:

```
markdown-текст
  → remark()              // парсинг в AST
  → remark-gfm            // таблицы, чек-листы, strikethrough
  → remark-rehype({ allowDangerousHtml: true })
  → rehype-slug            // id для заголовков
  → rehype-stringify({ allowDangerousHtml: true })
  → DOMPurify.sanitize()   // санитизация перед dangerouslySetInnerHTML
```

В новом проекте используется **браузерный** `dompurify` (не `isomorphic-dompurify`), так как рендеринг полностью клиентский (Vite SPA, нет server components). Версии пакетов — как в `frontend/package.json`: `remark@15`, `remark-gfm@4`, `remark-rehype@11`, `rehype-slug@6`, `rehype-stringify@10`.

Этот pipeline используется в двух местах: просмотр документа и live-превью при редактировании.

### 4.4. Прочее

- Иконки — инлайн SVG, без иконочной библиотеки (как в исходном проекте).
- `clsx` + `tailwind-merge` → хелпер `cn()` переносится как есть.
- Шрифт — Geist (через `@fontsource/geist-sans` или прямой `<link>` на Google Fonts, поскольку `next/font` недоступен в Vite).

---

## 5. Модель данных

### 5.1. `Document`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `slug` | `str`, unique | URL-идентификатор (`design-guide`, `bugs`, `readme`) |
| `title` | `str` | Заголовок для списка документов |
| `content_md` | `text` | Markdown-содержимое, редактируемое |
| `created_at` / `updated_at` | `datetime(tz)` | Таймстемпы (миксин, как в `db/models/users.py` исходного проекта) |

### 5.2. `WbsItem` (ИСР)

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `parent_id` | `int`, FK на себя, nullable | `NULL` — фаза верхнего уровня |
| `code` | `str` | `"1"`, `"1.1"`, `"1.1.1"` — как в `AGENT_VERA_WBS.txt` |
| `phase_name` | `str`, nullable | Заполнено только у узлов верхнего уровня: «Инициация», «Проектирование» и т.д. |
| `title` | `str` | Название задачи/подзадачи |
| `role` | `enum`, nullable | `PM \| BE \| FE \| UXR \| UXD \| EXPERT \| QA \| BA \| MKT` |
| `order_index` | `int` | Порядок среди братских узлов |
| `is_leaf` | `bool` | `true` → у узла есть связанная `KanbanTask` |

Глубина дерева — максимум 3 уровня (фаза → задача → подзадача), как в текущем ИСР.

### 5.3. `KanbanStage`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `name` | `str` | «Backlog», «To Do», «In Progress», «Review», «Done» (сид по умолчанию, редактируется) |
| `order_index` | `int` | Порядок колонок на доске |
| `color` | `str` | HEX, для полоски/бейджа колонки (в стиле ролевых цветов из `AGENT_VERA_ROADMAP.html`) |

### 5.4. `KanbanTask`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `wbs_item_id` | `int`, FK, nullable, **unique** | 1:1 с листовым `WbsItem`; `NULL` — задача создана вручную, не из ИСР |
| `stage_id` | `int`, FK | Текущая стадия |
| `title` | `str` | По умолчанию = `wbs_item.title` |
| `description_md` | `text`, nullable | Markdown-описание |
| `due_date` | `date`, nullable | Срок |
| `position` | `float` | Сортировка внутри стадии (drag&drop переставляет, можно дробные значения для вставки между карточками) |
| `created_at` / `updated_at` | `datetime(tz)` | |

### 5.5. `TaskComment`

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `task_id` | `int`, FK | |
| `author_name` | `str`, nullable | Свободный текст (нет авторизации/аккаунтов — просто подпись, опционально) |
| `body_md` | `text` | |
| `created_at` | `datetime(tz)` | |

### 5.6. `TaskActivity` (история изменений)

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `task_id` | `int`, FK | |
| `event_type` | `enum` | `STAGE_CHANGED \| DUE_DATE_CHANGED \| DESCRIPTION_CHANGED \| COMMENT_ADDED` |
| `from_value` | `str`, nullable | Текстовое представление старого значения (например, название стадии) |
| `to_value` | `str`, nullable | Текстовое представление нового значения |
| `created_at` | `datetime(tz)` | |

Запись создаётся в сервисном слое (`services/kanban.py`) при каждом изменении задачи — не пользователем напрямую, а как побочный эффект `move_task` / `update_task` / `add_comment`. Отдаётся через `GET /api/kanban/tasks/{id}/activity`, рендерится в `TaskDrawer` под комментариями в хронологическом порядке.

### 5.7. `DocumentLink` (связь документа с задачей или узлом ИСР)

| Поле | Тип | Описание |
|---|---|---|
| `id` | `int`, PK | |
| `document_id` | `int`, FK | |
| `kanban_task_id` | `int`, FK, nullable | Заполнено, если связь — с конкретной задачей |
| `wbs_item_id` | `int`, FK, nullable | Заполнено, если связь — с узлом ИСР |

Ограничение на уровне сервиса: ровно одно из `kanban_task_id` / `wbs_item_id` должно быть заполнено. Эта таблица — единственное, что мы берём из идеи "документация связана с WBS и с задачами": не полноценный граф связей (как в Miro), а простой список ссылок, отображаемый в `TaskDrawer` («Связанные документы: ...») и на странице документа («Используется в: ...»).

### 5.8. Вычисляемая агрегация (не хранится)

При запросе `GET /api/wbs/tree` для каждого нелистового узла backend вычисляет:
```
done_count / total_count   среди задач всех потомков-листьев
```
и отдаёт как `progress: { done: int, total: int }` в ответе — это не отдельная таблица, а агрегирующий `GROUP BY` в репозитории `wbs.py` (join `WbsItem` → `KanbanTask` → `KanbanStage`, фильтр `stage.name == "Done"` или явный признак "финальная стадия" `KanbanStage.is_done_stage: bool`).

> Уточнение по сравнению с черновым вариантом плана: чтобы не хардкодить понятие «Done» по имени строки, в `KanbanStage` добавляется булево поле `is_done_stage` — отмечает, какая стадия считается завершающей для расчёта прогресса. По умолчанию `true` только у одной сид-стадии («Done»).

---

## 6. Backend: структура и API

Конвенции — точная копия слоёв из `backend/src/` основного проекта: `api → services → repositories → db`, плюс `schemas` (Pydantic) и `dependencies` (DI-фабрики).

```
backend/src/
├── core/
│   └── settings.py        # pydantic-settings: DBSettings (postgres_*), AppSettings (cors_origins, debug)
├── db/
│   ├── session.py         # create_async_engine + async_sessionmaker (как db/session.py исходного проекта)
│   ├── models/
│   │   ├── base.py        # DeclarativeBase + TimestampMixin
│   │   ├── documents.py
│   │   ├── wbs.py
│   │   └── kanban.py
│   └── alembic/
│       ├── env.py         # async-миграции, target_metadata = Base.metadata
│       └── versions/
├── repositories/
│   ├── documents.py       # DocumentsRepository: get_all, get_by_slug, update
│   ├── wbs.py              # WbsRepository: get_tree (с join на kanban_task/kanban_stage)
│   ├── kanban.py           # KanbanRepository: stages CRUD, tasks CRUD, move_task, comments CRUD, activity log insert
│   └── document_links.py   # DocumentLinksRepository: create/delete/get_by_document/get_by_task/get_by_wbs_item
├── services/
│   ├── documents.py
│   ├── wbs.py               # собирает дерево из плоского списка в сервисном слое
│   ├── kanban.py             # бизнес-правила (move_task → пересчёт position + запись TaskActivity, update_task → diff полей → TaskActivity)
│   └── document_links.py    # валидация "ровно одно из kanban_task_id/wbs_item_id"
├── schemas/
│   ├── documents.py        # DocumentSchema, DocumentUpdateSchema
│   ├── wbs.py                # WbsNodeSchema (рекурсивная, с progress и nullable task)
│   ├── kanban.py              # StageSchema, TaskSchema, TaskMoveSchema, CommentSchema, ActivitySchema
│   └── document_links.py      # DocumentLinkSchema, DocumentLinkCreateSchema
├── dependencies/
│   ├── db_session.py        # DbSessionDep (Annotated), как в исходном проекте
│   ├── repositories.py      # *RepositoryDep фабрики
│   └── services.py          # *ServiceDep фабрики
└── api/
    ├── documents.py
    ├── wbs.py
    ├── kanban.py
    └── document_links.py
```

### 6.1. `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.documents import router as documents_router
from src.api.wbs import router as wbs_router
from src.api.kanban import router as kanban_router
from src.core.settings import get_settings

app = FastAPI()
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,   # напр. ["http://localhost:5173"]
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(wbs_router, prefix="/api/wbs", tags=["wbs"])
app.include_router(kanban_router, prefix="/api/kanban", tags=["kanban"])
```

CORS middleware — единственное реально новое по сравнению с основным backend: там его нет, потому что Next.js проксирует запросы на сервере (same-origin для браузера). Здесь Vite SPA обращается к API с другого origin напрямую.

### 6.2. Эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/documents` | Список документов (id, slug, title, updated_at) |
| `GET` | `/api/documents/{slug}` | Полный документ с `content_md` |
| `PATCH` | `/api/documents/{slug}` | Обновить `content_md` / `title` |
| `GET` | `/api/wbs/tree` | Дерево ИСР с `progress` и `task` на листьях |
| `GET` | `/api/kanban/stages` | Список стадий |
| `POST` | `/api/kanban/stages` | Создать стадию |
| `PATCH` | `/api/kanban/stages/{id}` | Переименовать / поменять порядок / `is_done_stage` |
| `DELETE` | `/api/kanban/stages/{id}` | Удалить (если нет задач в ней) |
| `GET` | `/api/kanban/tasks?stage_id=` | Список задач (опц. фильтр по стадии) |
| `POST` | `/api/kanban/tasks` | Создать задачу вручную (`wbs_item_id = null`) |
| `PATCH` | `/api/kanban/tasks/{id}` | Обновить title/description/due_date |
| `PATCH` | `/api/kanban/tasks/{id}/move` | `{ stage_id, position }` — для drag&drop |
| `DELETE` | `/api/kanban/tasks/{id}` | Удалить задачу (если `wbs_item_id is null`, иначе 409 — листовая задача из ИСР не удаляется, только перемещается) |
| `GET` | `/api/kanban/tasks/{id}/comments` | Список комментариев |
| `POST` | `/api/kanban/tasks/{id}/comments` | Добавить комментарий |
| `DELETE` | `/api/kanban/comments/{id}` | Удалить комментарий |
| `GET` | `/api/kanban/tasks/{id}/activity` | История изменений задачи (`TaskActivity`), хронологически |
| `GET` | `/api/documents/{slug}/links` | Связанные задачи/узлы ИСР для документа |
| `GET` | `/api/kanban/tasks/{id}/links` | Связанные документы для задачи |
| `POST` | `/api/document-links` | Создать связь `{ document_id, kanban_task_id? , wbs_item_id? }` |
| `DELETE` | `/api/document-links/{id}` | Удалить связь |

### 6.3. Пример схемы дерева ИСР (`WbsNodeSchema`)

```json
{
  "id": 12,
  "code": "1.1",
  "title": "Формирование функциональных и нефункциональных требований...",
  "role": "PM",
  "progress": { "done": 5, "total": 8 },
  "task": null,
  "children": [
    {
      "id": 13,
      "code": "1.1.1",
      "title": "Назначение и проведение рабочих встреч со стейкхолдерами",
      "role": "PM",
      "progress": null,
      "task": { "id": 41, "stage_id": 2, "stage_name": "In Progress", "due_date": null },
      "children": []
    }
  ]
}
```

---

## 7. Frontend: структура и экраны

```
frontend/src/
├── app.css                          # скопированные токены + keyframes
├── lib/
│   ├── api.ts                       # fetch-клиент (base URL из import.meta.env.VITE_API_URL)
│   ├── markdown.ts                  # remark/rehype/dompurify pipeline
│   └── cn.ts                        # clsx + tailwind-merge хелпер
├── components/
│   ├── ui/                          # Button, Modal, Badge, Spinner, ErrorMessage, EmptyState, Pagination, SkipLink, FocusHeading
│   ├── layout/
│   │   ├── Header.tsx               # sticky, blur, золотой акцент; пункты: Документы / ИСР / Канбан
│   │   └── Footer.tsx
│   ├── docs/
│   │   ├── DocumentList.tsx
│   │   └── MarkdownEditor.tsx       # split view: textarea + live-превью
│   ├── wbs/
│   │   └── WbsNode.tsx              # рекурсивный узел дерева, разворачивание, бейдж роли, прогресс-бар
│   └── kanban/
│       ├── Board.tsx                # DndContext (@dnd-kit), колонки
│       ├── Column.tsx
│       ├── TaskCard.tsx
│       └── TaskDrawer.tsx           # описание, due date, комментарии, история (TaskActivity), связанные документы
├── routes/
│   ├── HomePage.tsx                 # сводка: % готовности ИСР, кол-во документов, ближайшие сроки
│   ├── DocumentsPage.tsx
│   ├── DocumentDetailPage.tsx       # просмотр + кнопка "редактировать" → MarkdownEditor
│   ├── WbsPage.tsx
│   └── KanbanPage.tsx
├── stores/
│   └── ui.ts                        # Zustand: selectedTaskId, drawerOpen, kanbanFilters, wbsExpandedNodes
├── App.tsx                          # React Router: "/", "/docs", "/docs/:slug", "/wbs", "/kanban"
└── main.tsx
```

### 7.1. Ключевые новые зависимости (нет в исходном frontend)

| Пакет | Назначение |
|---|---|
| `react-router-dom` | Роутинг (вместо Next App Router) |
| `zustand` | Client state (выбранная задача, открытость панелей, фильтры, развёрнутые узлы дерева) — версия 5, та же библиотека, что уже используется в исходном `frontend/src/stores/auth.ts` |
| `@dnd-kit/core`, `@dnd-kit/sortable` | Drag&drop для канбана — активно поддерживается, доступен из коробки, в отличие от `react-beautiful-dnd` |
| `dompurify` (не `isomorphic-`) | Санитизация — чисто клиентский рендеринг |

Переносятся без изменений: `@tanstack/react-query`, `react-aria-components`, `clsx`, `tailwind-merge`, `remark`/`remark-gfm`/`remark-rehype`/`rehype-slug`/`rehype-stringify`.

**Server state vs client state.** Документы/задачи/ИСР/комментарии/история — это TanStack Query (с `invalidateQueries` после мутаций, как в `useFavorites.ts` исходного проекта). Какая задача открыта в `TaskDrawer`, какие узлы дерева развёрнуты, какие фильтры на канбане — это Zustand, не должно гонять лишние ре-рендеры через React Query кэш.

**Optimistic updates на drag&drop.** `PATCH /api/kanban/tasks/{id}/move` оборачивается в `useMutation` с `onMutate` (карточка сразу переезжает в новую колонку в локальном кэше React Query) и `onError` (откат + `ErrorMessage`). Без этого drag&drop будет визуально "запаздывать" на round-trip к серверу.

### 7.2. Layout — Master-Detail

Везде, где есть список + детали (канбан, ИСР), используется один и тот же паттерн: `Sidebar` (навигация Документы/ИСР/Канбан) → `Main Content` (доска/дерево/список документов) → `Details Panel` справа (`TaskDrawer` для канбана и ИСР-листьев; для документов — отдельная страница `/docs/:slug`, без боковой панели, так как там нужно больше пространства для текста).

### 7.3. Дерево ИСР — почему не Gantt/SVG

Глубина дерева — максимум 3 уровня, узлов — несколько десятков. Полноценная Gantt-визуализация (как `AGENT_VERA_ROADMAP.html`) для этого избыточна и плохо сочетается с интерактивностью (клик → переход к карточке канбана). Вместо этого — раскрывающийся вложенный список:

```
▾ Фаза 1. Инициация                                    [███████░░░] 7/10
  ▾ 1.1 Формирование требований к ассистенту [PM]        [████░░] 5/8
      1.1.1 Назначение и проведение рабочих встреч...   ● In Progress
      1.1.2 Подготовка опросников для сбора требований  ✓ Done
      ...
  ▸ 1.2 Изучение ТЗ, выбор архитектуры сервисов [Backend] [██████] 6/6
```

Бейдж роли использует ту же цветовую палитру, что определена в `AGENT_VERA_ROADMAP.html` (PM — золото, BE — оранжевый, FE — голубой, UX-R — фиолетовый, UX-D — розовый, Expert — зелёный, QA — красный, BA — синий, MKT — бирюзовый).

### 7.3. Канбан-доска

Стандартная доска: колонки = `KanbanStage` (сортировка по `order_index`), карточки = `KanbanTask`. Карточка показывает: заголовок, бейдж роли (если связана с WBS), due date (с подсветкой, если просрочена), счётчик комментариев. Клик на карточку → `TaskDrawer` (боковая панель): полное описание (markdown, редактируемое), due date picker, список комментариев с формой добавления, ссылка «Открыть в ИСР» (если `wbs_item_id` не null).

---

## 8. WBS ↔ канбан: как это работает на практике

1. При сидировании (раз, при первом запуске) для каждого листового пункта ИСР создаётся ровно одна `KanbanTask` в стадии «Backlog».
2. Пользователь двигает карточку по канбану — `PATCH /api/kanban/tasks/{id}/move`.
3. На странице `/wbs` для каждого родительского узла отображается прогресс — сколько из дочерних листовых задач находятся в стадии с `is_done_stage = true`.
4. Кликнув на листовой узел ИСР, пользователь видит текущую стадию и переходит в канбан с подсветкой нужной карточки (`?highlight=task_id`).
5. Ручные задачи (не из ИСР, `wbs_item_id = null`) создаются прямо в канбане — для разовых дел, не описанных в ИСР изначально (например, "починить баг X"). Они не отображаются в дереве ИСР.

---

## 9. Сидирование начальных данных

`backend/scripts/seed_initial_data.py` — одноразовый скрипт (запускается вручную после `alembic upgrade head`):

1. **Документы.** Читает выбранный набор `.md`-файлов из `site_work_for_everyone` (путь передаётся аргументом скрипта или константой) — кандидаты: `README.md`, `AGENT_VERA_ARCHITECTURE.md`, `DESIGN_GUIDE.md`, `BUGS.md`, `BLOG_CHEATSHEET.md`, `ADMIN_STATS_GUIDE.md`, `FRONTEND_AUDIT_REPORT.md`, `focus_management_best_practices_accessibility_guide.md`, `BUG-001_FAVORITES_FIX_REPORT.md`. Для каждого — создаёт `Document(slug=filename_without_ext, title=первый_H1, content_md=raw_content)`.
2. **ИСР.** Парсит структуру `AGENT_VERA_WBS.txt` (фазы → `N.N` → `N.N.N`) построчно по отступам и нумерации, создаёт дерево `WbsItem`. Для каждого узла без потомков (`is_leaf=true`) создаёт связанную `KanbanTask` со `stage_id` = id стадии «Backlog».
3. **Стадии.** Сидирует 5 стадий по умолчанию: Backlog, To Do, In Progress, Review, Done (`is_done_stage=true` только у Done).

> HTML-отчёты (`AGENT_VERA_PROJECT_PASSPORT.html`, `AGENT_VERA_ROADMAP.html`, `AGENT_VERA_STAKEHOLDER_MATRIX.html`, `AGENT_VERA_TECHNICAL_PLAN.html`, `vera_wbs.html`) **не сидируются как `Document`** в v1 — это самостоятельные печатные отчёты с инлайн-стилями, конвертация в markdown потеряла бы их вёрстку. Если понадобится редактировать и их — добавим позже либо как markdown-конверсию, либо как отдельный тип `Document.content_type = "html"` с рендерингом в `<iframe sandbox>`.

---

## 10. Пошаговый план реализации

1. ✅ Backend skeleton: `main.py`, `core/settings.py`, `db/session.py`, `db/models/base.py`, `alembic` (async-паттерн из исходного проекта).
2. ✅ Модели (`Document`, `WbsItem`, `KanbanStage`, `KanbanTask`, `TaskComment`, `TaskActivity`, `DocumentLink`) + первая Alembic-миграция (применена к локальной БД `project_management_dashboard_vera`).
3. ✅ Слои `repositories → services → schemas → api` для `documents`, затем `kanban`, затем `wbs` (wbs последним, так как зависит от kanban-задач для прогресса).
4. ✅ `document_links` слой (репозиторий/сервис/схемы/эндпоинты, валидация «ровно одно поле»).
5. ✅ `seed_initial_data.py` — документы (9 файлов), 5 стадий канбана, дерево ИСР (247 узлов, 195 листьев = 195 связанных задач), идемпотентность проверена повторным запуском.
6. ✅ Frontend skeleton: Vite + React + TS, `app.css`, перенос UI-примитивов и markdown pipeline.
7. ✅ Экран «Документы»: список → просмотр → редактирование (split view).
8. ✅ Экран «ИСР»: рекурсивное дерево, прогресс-бары, бейджи ролей.
9. ✅ Экран «Канбан»: колонки, drag&drop (`@dnd-kit`) с optimistic updates, `TaskDrawer` (описание/срок/комментарии/история/связанные документы), переход из ИСР с подсветкой карточки.
10. ✅ Главная страница со сводкой.
11. ⏳ `docker-compose.yml` для локального подъёма backend + postgres + frontend — **делается в конце, один на весь проект**. Файлы написаны, запуск через Docker отложен пользователем на потом (не проверено).

### 10.1. Статус реализации backend (детали)

- Каталог: `backend/` (venv создан, зависимости в `requirements.txt`, `.env` с локальными кредами `project_management_dashboard_vera`).
- Все эндпоинты из раздела 6.2 реализованы и проверены вручную (curl): документы (список/получение/обновление/связи), канбан (стадии CRUD, задачи CRUD, move с записью `TaskActivity`, комментарии, история), ИСР (`/api/wbs/tree` с rollup-прогрессом), `document-links` (создание/удаление со валидацией).
- Найден и исправлен баг в `main.py`: обработчик `RequestValidationError` не сериализовал `ctx.error` pydantic-исключений в JSON (`jsonable_encoder` добавлен).
- Источники документации копируются из `site_work_for_everyone` (соседний проект), путь к ИСР — `docs/AGENT_VERA_WBS.txt` внутри этого репозитория (документы переехали в `docs/` в процессе работы).
- Эндпоинт `/api/kanban/tasks/{id}/links` и `/api/documents/{slug}/links` — рабочие, проверены сценарием создания связи и удаления.

### 10.2. Статус реализации frontend (детали)

- Каталог: `frontend/` (Vite + React 19 + TS, создан через `npm create vite@latest . -- --template react-ts`).
- Алиас `@/*` → `src/*` настроен в `vite.config.ts` и `tsconfig.app.json`.
- Перенесены 1:1 (с правкой импорта `cn` на `@/lib/cn`): `Button`, `Modal`, `Badge` (упрощён — без бейджей источников вакансий, не нужны дашборду), `Spinner`, `ErrorMessage`, `EmptyState`, `Pagination`, `SkipLink`, `FocusHeading`. `ServiceError`/`SourceBadge` не переносились (привязаны к Next.js/вакансиям).
- `lib/markdown.ts` — remark/remark-gfm/remark-rehype/rehype-slug/rehype-stringify + браузерный `dompurify` (без `isomorphic-`, т.к. чистый SPA).
- `lib/api.ts` — типизированный fetch-клиент (`VITE_API_URL`, по умолчанию `http://localhost:8000`), `lib/types.ts` — TS-интерфейсы под все backend-схемы + палитра цветов ролей ИСР.
- `stores/ui.ts` (Zustand) — `selectedTaskId`, `drawerOpen`, `wbsExpandedNodes`.
- Роутинг (`react-router-dom`): `/`, `/docs`, `/docs/:slug`, `/wbs`, `/kanban` — пока заглушки-страницы.
- Проверено: `tsc -b` чисто, `npm run build` собирается, dev-сервер (`npm run dev`) поднимается и получает данные от backend (`/api/documents`).

### 10.3. Статус реализации экрана «Документы»

- `components/docs/DocumentList.tsx` — список со ссылками на `/docs/:slug`, дата обновления.
- `components/docs/MarkdownEditor.tsx` — split view: textarea + live-превью через `useRenderedMarkdown` (дебаунс не нужен — рендер дёшев, чанки документации небольшие).
- `lib/useRenderedMarkdown.ts` — хук с `useEffect`/`useState` оборачивающий асинхронный `renderMarkdown`.
- `routes/DocumentsPage.tsx` и `routes/DocumentDetailPage.tsx` — TanStack Query (`useQuery`/`useMutation`), `Spinner`/`ErrorMessage`/`EmptyState` для состояний загрузки/ошибки/пустого списка.
- Стили рендеренного markdown — собственный класс `.markdown-body` в `app.css` (без `@tailwindcss/typography`, чтобы не тащить лишний плагин).
- Проверено: `tsc -b` чисто; ручной round-trip через `PATCH /api/documents/{slug}` (тот же вызов, что делает `DocumentDetailPage`) — изменение и восстановление контента документа `design_guide` прошло корректно.
- **Не проверено визуально в браузере** — окружение без GUI/скриншотов, тестировалось через build/type-check/API round-trip, а не реальный рендеринг.

### 10.4. Статус реализации экрана «ИСР»

- `components/wbs/WbsNode.tsx` — рекурсивный узел: разворачивание/сворачивание (состояние в `stores/ui.ts`), прогресс-бар для нелистовых узлов, бейдж роли (цвета из `lib/types.ts: ROLE_COLORS`, по палитре из раздела 7.3 плана), для листьев — бейдж текущей стадии канбана (цвет — локальная карта `STAGE_COLORS`, совпадающая с сидом стадий) и due date.
- Клик на бейдж стадии у листового узла → переход на `/kanban?highlight={task_id}` (сама подсветка карточки в `KanbanPage` будет добавлена в задаче «Экран Канбан»).
- `routes/WbsPage.tsx` — корневые узлы (8 фаз) разворачиваются автоматически при первой загрузке.
- Проверено: `tsc -b` чисто; `GET /api/wbs/tree` на реальных данных отдаёт все 247 узлов (8 корней — все фазы на месте); dev-сервер поднимается без ошибок.
- **Не проверено визуально в браузере** (см. 10.3) — клик-взаимодействие дерева и переход в канбан не протестированы реальным кликом.

### 10.5. Статус реализации экрана «Канбан»

- `components/kanban/Board.tsx` — `DndContext` (`@dnd-kit/core`) + `SortableContext` на колонку; `onDragEnd` вычисляет позицию вставки **дробным индексированием** ((prev+next)/2 между соседями), а не пересчётом позиций всех карточек — меньше PATCH-запросов, нет конфликтов при параллельной работе.
- Optimistic update — `useMutation.onMutate` пишет `stage_id`/`position` прямо в кэш `['kanban','tasks']` до ответа сервера; `onError` восстанавливает снимок; `onSettled` инвалидирует `['kanban','tasks']` и `['wbs','tree']` (чтобы прогресс ИСР обновился после перетаскивания).
- `components/kanban/TaskDrawer.tsx` — боковая панель (не центральный `Modal`, отдельная реализация с фиксированным правым сайдбаром): описание (split-view редактор, переиспользует `MarkdownEditor`), срок (`input type=date`), список и форма комментариев, история изменений (человекочитаемые подписи событий), связанные документы (`GET /api/kanban/tasks/{id}/links`).
- **Важное упрощение**: в backend нет одиночного `GET /api/kanban/tasks/{id}` (только список и подресурсы) — drawer берёт объект задачи из уже загруженного списка `['kanban','tasks']` в `KanbanPage`, без отдельного запроса.
- **Сознательное упрощение по сравнению с разделом 7.3 плана**: бейдж роли на карточке не показан — `KanbanTaskSchema` не возвращает роль ИСР (только `wbs_item_id`), а добавлять join ради бейджа на доске посчитали избыточным для v1; счётчик комментариев на карточке также не показан (требует доп. агрегата на backend). Можно добавить позже, если понадобится.
- Переход «Открыть в канбане» из ИСР (`/kanban?highlight=task_id`) реализован: подсвечивает карточку (золотая рамка/свечение) и автоматически открывает `TaskDrawer` для неё.
- Проверено: `tsc -b` и `npm run build` чисто; полный e2e через curl (move со сменой стадии → запись `STAGE_CHANGED` в `TaskActivity`, `due_date` → `DUE_DATE_CHANGED`, комментарий → `COMMENT_ADDED`, удаление комментария) — всё соответствует тому, что делают мутации на фронте.
- **Не проверено визуально в браузере** (см. 10.3) — реальный drag&drop мышью не протестирован, только логика позиционирования и API-вызовы.

### 10.6. Статус реализации главной страницы

- `routes/HomePage.tsx` — три карточки сводки: % готовности ИСР (сумма `progress.done/total` по корневым узлам дерева), количество документов, ближайшие сроки (задачи с `due_date`, не в финальной стадии, топ-5 по дате) — с переходами на `/wbs`, `/docs`, `/kanban`.
- Все экраны из раздела 10 (документы, ИСР, канбан, главная) реализованы. Осталось только `docker-compose.yml` (пункт 11) — по решению пользователя делается отдельно, в конце, один файл на весь проект (backend + postgres + frontend).
- Проверено: `tsc -b` и `npm run build` чисто.
- **Не проверено визуально в браузере** (см. 10.3).

### 10.7. Статус docker-compose

- Пользователь добавил в корень `docker-compose.yml` и `nginx/nginx.conf`, скопированные из `site_work_for_everyone` — но это файлы под Next.js + домен `work-for-everyone.ru` + certbot/SSL + маршруты `/api/v1/assistant/`, `/api/v1/vacancies/`, которых в этом проекте нет; `docker-compose.yml` также ссылался на несуществующий `./backend/nginx/default.conf`. Полностью переписаны под реальную архитектуру.
- Итоговая схема (4 сервиса, без auth/SSL — внутренний дашборд): `db` (postgres:16-alpine, порт 5436→5432, чтобы не конфликтовать с другими проектами на том же сервере — `5434` уже занят `site_work_for_everyone`, `5435` — `api_work_for_everyone`), `backend` (FastAPI, `entrypoint.sh` сам гоняет `alembic upgrade head` + сидинг ИСР из `wbs_seed.json`), `frontend` (multi-stage: `node` собирает Vite-бандл → `nginx:alpine` отдаёт статику), `nginx` (единая точка входа на порту 93→80, по аналогии с нумерацией портов других внутренних сервисов на сервере (`90`, `91`): `/` → frontend, `/api/` → backend). Доступ — по IP сервера, без домена/TLS.
- `frontend/Dockerfile` и `frontend/nginx.conf` — новые файлы (frontend сам по себе становится `nginx:alpine` с SPA fallback `try_files ... /index.html`, отдельный Node-процесс не нужен — это статика, не Next.js).
- БД-креды для контейнеров не берутся из `backend/.env` напрямую (там `POSTGRES_HOST=localhost` для локального запуска без Docker) — в `docker-compose.yml` они переопределяются через `environment:` (`POSTGRES_HOST=db` и т.д.) из корневого `.env` (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, гитигнорится, есть `.env.example`). Так один и тот же `backend/.env` работает и локально, и в Docker без правок.
- `VITE_API_URL` в проде собирается пустой строкой — фронт ходит на относительный `/api/...`, тот же origin, что отдаёт nginx; проксирование снимает необходимость в CORS для прод-сборки.
- **Не проверено** — пользователь попросил запуск через Docker отложить; `docker compose config`/`up` не выполнялись.

### 10.8. Доработки по фидбэку: редактирование ИСР, визуальная связь с канбаном

После первого прохода пользователь дал предметный фидбэк по реальному использованию (скриншоты): дерево ИСР и Бэклог визуально не различались, не было возможности добавлять/редактировать узлы ИСР, не было видно к какой фазе относится карточка, не было поиска, при возврате в Бэклог карточка падала в конец списка а не на своё место по ИСР. Реализовано:

- **Backend: полноценный CRUD узлов ИСР** — `POST /api/wbs/items`, `PATCH /api/wbs/items/{id}`, `DELETE /api/wbs/items/{id}`. Код узла (`1.1.1`) генерируется автоматически от родителя + порядкового номера среди братьев. При создании дочернего узла у листа родитель автоматически становится фазой/разделом (`is_leaf=False`), а его собственная карточка канбана удаляется (у фазы не может быть карточки). При переименовании листа название синхронизируется с заголовком связанной `KanbanTask`. При удалении узла рекурсивно удаляются все связанные карточки канбана у всех потомков (не оставляя «осиротевших» задач) — реализовано через `WbsService._delete_linked_tasks_recursively`.
- **Backend: код и фаза ИСР на карточках канбана** — `TaskSchema` получил `wbs_code`/`wbs_phase_name`; `KanbanService.get_task_list` строит карту `wbs_item_id → (код, фаза)` через `WbsRepository.get_all_items()` и обогащает список задач. `KanbanService` и `WbsService` теперь зависят от обоих репозиториев (`KanbanRepository` + `WbsRepository`), через `dependencies/services.py`.
- **Frontend: редактирование ИСР** — `components/wbs/WbsNode.tsx` получил инлайн-формы добавления подзадачи / редактирования (`ItemForm`, переиспользуемый компонент) и кнопку удаления с `window.confirm`. На `/wbs` добавлена кнопка «+ Новая фаза» для узлов верхнего уровня.
- **Frontend: визуальная иерархия дерева** — фазы (depth 0) выделены жирным и разделителем сверху, разделы (depth 1) — полужирным, листья — обычным текстом.
- **Frontend: Бэклог сортируется и группируется по ИСР** — `lib/sortCode.ts` (`compareWbsCode`) — натуральная сортировка кодов (`1.10` после `1.2`, а не лексикографически). В `Board.tsx` находим стадию с минимальным `order_index` (= Бэклог) и сортируем её задачи по `wbs_code` вместо `position`; остальные стадии остаются на свободной сортировке по `position` (там порядок выбирает команда). `Column.tsx` рисует подзаголовки фаз (`groupByPhase` проп), когда список отсортирован по коду — группы получаются смежными автоматически, т.к. сортировка по коду уже кладёт всё «1.x» подряд. `TaskCard.tsx` показывает код ИСР перед названием.
- **Frontend: поиск в канбане** — поле поиска на странице `/kanban` (не только в Бэклоге — фильтрует весь список задач по названию/коду ИСР перед передачей в `Board`, поэтому очевидным образом сильнее всего разгружает именно Бэклог за счёт объёма).
- Проверено через прямые HTTP-вызовы (создание фазы → лист → лист становится фазой при добавлении подзадачи с удалением его карточки → переименование с синхронизацией title в канбане → рекурсивное удаление без «осиротевших» карточек), `tsc -b` и `npm run build` чисто. Целостность данных после тестов проверена (247 узлов ИСР, 195 задач, 0 ручных «сирот»).
- **Не проверено визуально в браузере** (см. 10.3) — клики/формы/drag не протестированы реальной мышью.

### 10.9. Создание и удаление документов

Изначально в плане (раздел 6.2) для документов был только `PATCH` (редактирование уже засеянных файлов). По запросу пользователя добавлена возможность создавать и удалять документы прямо из дашборда:

- **Backend**: `POST /api/documents` (`title`, опц. `slug`, опц. `content_md`) и `DELETE /api/documents/{slug}`. Slug генерируется из заголовка (`slugify` сохраняет кириллицу — URL поддерживает unicode, транслитерация не нужна); при коллизии подбирается свободный вариант (`-2`, `-3`...). `DocumentSlugConflictError` предусмотрен в exceptions, хотя на практике авто-подбор слага делает конфликт практически невозможным.
- **Frontend**: кнопка «+ Новый документ» на `/docs` — инлайн-форма с заголовком, после создания переход на `/docs/:slug`. На странице документа — кнопка «Удалить» с `window.confirm`, после удаления переход обратно на `/docs`. Новый документ создаётся с пустым `content_md` и сразу открывается в режиме просмотра — пользователь нажимает «Редактировать» и попадает в уже существующий `MarkdownEditor` (split view), никакой новой логики рендеринга не потребовалось.
- Проверено через HTTP: создание, авто-уникальный slug при дублирующемся заголовке, получение, удаление, 404 после удаления — все сценарии отработали; `tsc -b` и `npm run build` чисто. Тестовые документы подчищены, в БД снова ровно 9 (исходный сид).

### 10.10. Виджет «Пульс канбана» на главной

По образцу дизайна другого проекта пользователя (`dispatch-audit`, `DashboardPage.tsx`) — donut-чарт с количеством по центру + горизонтальные сегментированные бары по стадиям. Добавлена зависимость `recharts` (только для этого виджета — единственное место в проекте, где есть процедурный график; остальной UI остаётся на ручных div/CSS, без сторонних UI-китов, как и решили в начале).

- `components/dashboard/KanbanPulse.tsx` — принимает уже загруженные `stages`/`tasks` (без новых эндпоинтов), считает количество задач на стадию на клиенте. Цвета стадий берутся из `KanbanStage.color` (то же поле, что красит колонки канбана) — никакой отдельной цветовой карты не потребовалось.
- Подключен на `HomePage.tsx` под существующими тремя карточками сводки.
- Проверено: `tsc -b` и `npm run build` чисто (размер бандла выросл с ~560KB до ~870KB из-за recharts — для внутреннего инструмента некритично).

## 11. Критерии готовности и проверка

- `alembic upgrade head` поднимает схему без ошибок.
- `python scripts/seed_initial_data.py` идемпотентно создаёт документы, стадии и дерево ИСР с задачами (повторный запуск не дублирует записи — проверка по `slug`/`code`).
- `GET /api/wbs/tree` возвращает дерево, совпадающее по структуре с `AGENT_VERA_WBS.txt`, с корректными `progress` на родительских узлах.
- На `/wbs` дерево разворачивается/сворачивается, бейджи ролей соответствуют палитре `AGENT_VERA_ROADMAP.html`.
- На `/kanban` карточка перетаскивается между колонками **мгновенно** (optimistic update, без ожидания ответа сервера); при ошибке запроса — откат в исходную колонку и сообщение об ошибке. После перетаскивания и обновления `/wbs` прогресс родительского узла пересчитан.
- В `TaskDrawer` после смены стадии/срока/добавления комментария в блоке истории появляется новая запись `TaskActivity` без перезагрузки страницы.
- На `/docs/:slug` редактирование и сохранение (`PATCH`) переживает перезагрузку страницы; live-превью при редактировании визуально идентично рендерингу блога в исходном проекте (тот же markdown pipeline).
- Визуально дашборд неотличим по стилю (цвета, типографика, кнопки, фокус-стили) от `site_work_for_everyone/frontend` — никаких следов чужой UI-библиотеки (MUI/shadcn).

## 12. Сознательно не делаем в v1

Рассмотрели и осознанно отложили (в т.ч. по итогам сравнения с рекомендациями другого агента, ориентированными на Linear/Notion/Jira/Miro):

- **Авторизацию** — по явному решению, публичная отчётность.
- **Полноценный WYSIWYG-редактор (TipTap)** — textarea + live-превью достаточно для объёма документации; апгрейд — отдельная итерация, если markdown перестанет хватать.
- **react-complex-tree / drag&drop по дереву ИСР** — дерево всего 3 уровня и десятки узлов, кастомный рекурсивный компонент проще, легче стилизуется под наш дизайн и не тащит чужие UI-паттерны. Drag&drop оставляем только для канбана.
- **MUI / shadcn/ui** — конфликтует с решением визуально клонировать дизайн-систему `site_work_for_everyone` (свои CSS-токены, без готовых компонентных библиотек).
- **Виртуализацию списков (react-window/react-virtual)** — преждевременная оптимизация: десятки задач и узлов ИСР, не тысячи.
- **Miro-style граф связей и масштабируемое холст-представление ИСР** — избыточно для текущего масштаба; дерево с rollup-прогрессом покрывает потребность.
- **Полноценное вложенное дерево документов (Notion-style)** — пока ~9 плоских документов, иерархия не нужна; если документов станет много, можно добавить вложенность в `Document` (`parent_id`) позже по той же схеме, что и `WbsItem`.
- **Импорт HTML-отчётов** (паспорт, дорожная карта, матрица стейкхолдеров, технический план) как редактируемых документов — см. раздел 9.
- **Gantt/SVG-визуализацию ИСР** — вложенное дерево достаточно для текущей глубины и масштаба ИСР.

Что **взяли** из рекомендаций другого агента и уже отражено в плане выше: Master-Detail layout (раздел 7.2), разделение Server State (TanStack Query + optimistic updates) / Client State (Zustand) (раздел 7.1), история изменений задачи `TaskActivity` (раздел 5.6, теперь в v1, а не отложено), связи документ↔задача/ИСР `DocumentLink` (раздел 5.7) — в облегчённом виде, без полноценного графа связей.
