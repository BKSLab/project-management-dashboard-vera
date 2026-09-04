# AI-вики проектов: отчёт о реализации

Документ фиксирует фактическую реализацию AI-вики и Project Agent в Project Management Dashboard Vera на 1 сентября 2026 года. Он предназначен для разработки, ревью, эксплуатации и дальнейшего развития функции.

Основной источник требований — [«Концептуальное ТЗ: база знаний и AI-агент проекта»](../project_knowledge_ai_concept.md). Архитектурные правила backend взяты из [FASTAPI_PATTERNS.md](../FASTAPI_PATTERNS.md).

## 1. Использованные источники

| Источник | Что использовано | Зависимость в runtime |
|---|---|---|
| [Концептуальное ТЗ](../project_knowledge_ai_concept.md) | граница знаний по Project, Qdrant как производный индекс, индексируемые сущности, очередь, reindex, hybrid RAG, источники, UI и безопасность | Да, это основной контракт функции |
| [FASTAPI_PATTERNS.md](../FASTAPI_PATTERNS.md) | слои endpoint → service → repository, DI, lifespan внешних клиентов, исключения, Alembic и пирамида тестов | Да, это архитектурный стандарт репозитория |
| `C:\work\biocard\projects\biocard-wiki` | референс разделения PostgreSQL/Qdrant, Markdown chunking и общего RAG-контура | Нет; код и данные проекта не импортируются |
| `C:\work\BKS.Lab\python\my_projects\vera_rag_service` | референс извлечения PDF/DOCX/Markdown/TXT, ограничения PDF и проверки ответов AI API | Нет; реализация адаптирована внутри этого репозитория |
| `C:\work\biocard\projects\FileTextParser` | референс разбора Excel (скрытые строки, объединённые ячейки, плоские записи) и распознавания изображений vision-моделью | Нет; логика перенесена и адаптирована под async-контур и настройки этого репозитория |

Внешние проекты использовались только как локальные референсы. Для сборки и запуска AI-вики они не требуются.

## 2. Карта требований и реализации

| Пункт ТЗ | Статус | Реализация |
|---|---|---|
| [§ 1. Цель](../project_knowledge_ai_concept.md#1-цель) | Реализовано | У каждого проекта есть AI-вики и чат Project Agent по задачам, комментариям, документам, вложениям, ИСР и актуальному SQL-состоянию. |
| [§ 2. Архитектурные принципы](../project_knowledge_ai_concept.md#2-архитектурные-принципы) | Реализовано | PostgreSQL остаётся Source of Truth; Qdrant используется только как semantic layer; collection вычисляется сервером из `project_id`. |
| [§ 3. Жизненный цикл collection](../project_knowledge_ai_concept.md#3-жизненный-цикл-collection) | Реализовано асинхронно | Создание проекта ставит полный reindex, который создаёт `project_<id>`; переименование не меняет имя collection; удаление проекта ставит `DELETE_COLLECTION`. |
| [§ 4. Индексируемые сущности](../project_knowledge_ai_concept.md#4-индексируемые-сущности) | Реализовано с расширением | Индексируются Project, Task, Document, Comment и поддерживаемые Task Attachment. WBS хранится в SQL, а путь включается в Task. |
| [§ 5. Индексация Task](../project_knowledge_ai_concept.md#5-индексация-task) | Реализовано | Semantic representation содержит ключ, заголовок, описание и путь ИСР. Оперативные поля намеренно исключены и всегда читаются из SQL. |
| [§ 6. Когда переиндексировать Task](../project_knowledge_ai_concept.md#6-когда-переиндексировать-task) | Реализовано | Новый embedding создаётся при создании Task, изменении `title`/`description_md` и изменении назначения в ИСР. Priority, assignee, deadline, stage и Kanban position embedding не запускают. |
| [§ 7. Комментарии](../project_knowledge_ai_concept.md#7-комментарии) | Реализовано | Каждый комментарий — отдельный point; создание ставит upsert, удаление — delete; источник ведёт в Task Drawer. |
| [§ 8. Документы](../project_knowledge_ai_concept.md#8-документы) | Реализовано | Markdown делится по заголовкам, секциям и абзацам; обновление заменяет актуальные chunks; удаление очищает все points документа. |
| [§ 9. ИСР / Structure](../project_knowledge_ai_concept.md#9-иср--structure) | Реализовано | В Qdrant не копируется дерево WBS. В Task embedding добавляется вычисленный путь `Parent / Child`; структурные изменения ставят reindex. |
| [§ 10. Knowledge Indexing Service](../project_knowledge_ai_concept.md#10-knowledge-indexing-service) | Реализовано | Builders, chunking, extraction, embedding client, Qdrant client и orchestration изолированы от CRUD-сервисов. |
| [§ 11. Асинхронная индексация](../project_knowledge_ai_concept.md#11-асинхронная-индексация) | Реализовано | CRUD сначала сохраняется в PostgreSQL, затем создаётся постоянное задание; один фоновый worker выполняет внешние вызовы и retry. |
| [§ 12. Идемпотентность](../project_knowledge_ai_concept.md#12-идемпотентность) | Реализовано | Point ID — детерминированный UUIDv5 от project/type/entity/chunk; повторный upsert заменяет сущность, ожидающие одинаковые jobs дедуплицируются. |
| [§ 13. Reindex](../project_knowledge_ai_concept.md#13-reindex) | Реализовано | `POST /projects/{id}/knowledge/reindex` и кнопка UI полностью пересобирают collection из PostgreSQL и файлов. |
| [§ 14. Project Agent](../project_knowledge_ai_concept.md#14-project-agent) | Реализовано | Agent получает только доступный Project; имя collection отсутствует в клиентском контракте. |
| [§ 15. Инструменты агента](../project_knowledge_ai_concept.md#15-инструменты-агента) | Реализовано в MVP-форме | Вместо автономного tool-calling каждый запрос детерминированно объединяет semantic search и актуальный SQL-срез проекта. Фильтрация semantic search по `entity_type` пока не вынесена в API. |
| [§ 16. Routing вопросов](../project_knowledge_ai_concept.md#16-routing-вопросов) | Реализовано в MVP-форме | Pipeline всегда hybrid: SQL-контекст передаётся обязательно, Qdrant-контекст — при доступности. LLM выбирает факты из обоих блоков, SQL имеет приоритет. |
| [§ 17. Grounding и источники](../project_knowledge_ai_concept.md#17-grounding-и-источники) | Реализовано частично | Ответ содержит только валидированные `source_id`. Task/Comment/Attachment открывают Task Drawer, Document — страницу документа. Фокус на конкретном комментарии внутри Drawer пока не реализован. |
| [§ 18. UI](../project_knowledge_ai_concept.md#18-ui) | Реализовано | Добавлена вкладка «AI-вики», чат, стартовые вопросы, Markdown-ответы, Sources, статус, ошибки и ручной reindex в общей dark design system. |
| [§ 19. Context-aware AI](../project_knowledge_ai_concept.md#19-context-aware-ai) | Отложено по ТЗ | Floating panel и передача `current_entity_type/current_entity_id` не входят в текущую итерацию. |
| [§ 20. Статус и диагностика](../project_knowledge_ai_concept.md#20-статус-индексации-и-диагностика) | Реализовано частично | Есть состояния job, attempts, последняя ошибка, число points и статусный API. Полные histogram-метрики latency и отдельный metrics backend пока отсутствуют. |
| [§ 21. Безопасность](../project_knowledge_ai_concept.md#21-безопасность) | Реализовано | Сначала проверяется доступ к Project, затем сервер вычисляет collection. Cross-project collection/query из запроса клиента невозможны. |
| [§ 22. Удаление данных](../project_knowledge_ai_concept.md#22-удаление-данных) | Реализовано | Delete jobs удаляют Task-контекст, Comment, Document, Attachment либо всю collection после основной SQL-операции. |
| [§ 23. Возможное развитие](../project_knowledge_ai_concept.md#23-возможное-развитие) | Не входит в MVP | Decisions, Summary, Weekly Digest, Similarity, extraction решений и долговременная память не реализованы. Архитектура допускает новые `entity_type` и builders. |
| [§ 24. Первая итерация](../project_knowledge_ai_concept.md#24-первая-итерация) | Реализовано | Закрыты все 12 MVP-пунктов; вложения добавлены сверх минимального списка. Исключённые multi-agent, knowledge graph и автономная память не добавлялись. |
| [§ 25. Целевой результат](../project_knowledge_ai_concept.md#25-целевой-результат) | Реализовано | Обычные CRUD-операции автоматически поддерживают project-scoped knowledge workspace, а Agent объединяет semantic и structured data. |

## 3. Итоговая архитектура

### 3.1. Контур записи

```text
Project / Task / Document / Comment / Attachment / WBS service
                              │
                              │ основная операция и commit
                              ▼
                         PostgreSQL
                              │
                              │ best-effort KnowledgeEvents
                              ▼
                  knowledge_index_jobs (persistent)
                              │
                              │ background worker
                              ▼
                  KnowledgeIndexService
                    │       │        │
                    │       │        └─ file extraction
                    │       └────────── document builders/chunking
                    └────────────────── embeddings API
                              │
                              ▼
                    Qdrant project_<id>
```

Основная бизнес-операция не зависит от доступности Qdrant или AI-провайдера. `KnowledgeEvents` перехватывает ошибку постановки события, пишет warning и не откатывает уже сохранённую сущность. Ошибка worker-а переводит job обратно в `PENDING` с задержкой либо в `FAILED` после исчерпания попыток.

Основание: [ТЗ § 10](../project_knowledge_ai_concept.md#10-knowledge-indexing-service), [§ 11](../project_knowledge_ai_concept.md#11-асинхронная-индексация) и [архитектурные слои FastAPI](../FASTAPI_PATTERNS.md#1-слоистая-архитектура).

### 3.2. Контур вопроса

```text
POST /projects/{project_id}/knowledge/ask
                    │
                    ▼
       AccessibleProjectDep: session + membership
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 актуальный SQL-срез     embedding вопроса
 Project/Stages/Tasks          │
 WBS/Documents/Activity        ▼
                         Qdrant project_<id>
          │                   │
          └─────────┬─────────┘
                    ▼
       LLM structured JSON response
                    │
                    ▼
       проверка source_id по контексту
                    │
                    ▼
        Markdown answer + Sources
```

Если embeddings или Qdrant временно недоступны, запрос продолжается с SQL-контекстом. Если недоступен LLM, endpoint возвращает `503`: SQL fallback означает отказоустойчивость retrieval, а не замену генеративной модели шаблонным ответом.

Основание: [ТЗ § 2](../project_knowledge_ai_concept.md#2-архитектурные-принципы), [§ 16](../project_knowledge_ai_concept.md#16-routing-вопросов), [§ 17](../project_knowledge_ai_concept.md#17-grounding-и-источники).

## 4. PostgreSQL: постоянная очередь

Модель: [`KnowledgeIndexJob`](../backend/src/db/models/knowledge_index_jobs.py). Миграция: [`20260901_2100_project_knowledge_jobs.py`](../backend/src/db/alembic/versions/20260901_2100_project_knowledge_jobs.py).

### 4.1. Enum-типы

| Enum | Значения |
|---|---|
| `knowledge_entity_type` | `PROJECT`, `TASK`, `DOCUMENT`, `COMMENT`, `ATTACHMENT` |
| `knowledge_index_operation` | `UPSERT`, `DELETE`, `REINDEX_PROJECT`, `DELETE_COLLECTION` |
| `knowledge_index_status` | `PENDING`, `PROCESSING`, `SUCCEEDED`, `FAILED` |

### 4.2. Поля job

| Поле | Назначение |
|---|---|
| `project_id` | стабильная граница знаний; намеренно без FK, чтобы удаление collection пережило удаление Project |
| `entity_type`, `entity_id` | исходная сущность; `entity_id` отсутствует у операций над всей collection |
| `operation` | требуемое действие синхронизации |
| `status` | текущее состояние задания |
| `attempts` | число фактических захватов worker-ом |
| `available_at` | время следующей разрешённой попытки |
| `last_error` | последние детали ошибки, обрезанные до 4000 символов |
| `created_at`, `updated_at` | аудит жизненного цикла |

Индексы ускоряют выбор следующего job по `(status, available_at, id)` и диагностику проекта по `(project_id, status)`. Миграция ставит `REINDEX_PROJECT` для каждого уже существующего проекта.

### 4.3. Обработка и retry

Репозиторий [`KnowledgeIndexJobsRepository`](../backend/src/repositories/knowledge_index_jobs.py):

- не создаёт второй идентичный `PENDING` job;
- захватывает готовое задание через `FOR UPDATE SKIP LOCKED`;
- перед обработкой переводит его в `PROCESSING` и увеличивает `attempts`;
- возвращает оставшиеся после аварийного shutdown `PROCESSING` jobs в `PENDING` при старте;
- использует exponential backoff `2^attempts` секунд с верхней границей 300 секунд;
- после `KNOWLEDGE_INDEX_MAX_ATTEMPTS` оставляет задание в `FAILED`;
- хранит успешные и ошибочные jobs для диагностики; автоматическая очистка истории пока не добавлена.

Текущая конфигурация запускает один последовательный worker в lifespan FastAPI. Репозиторий допускает безопасный конкурентный claim, если позже появится несколько worker-процессов.

## 5. Qdrant и модель point

Клиент: [`ProjectQdrantClient`](../backend/src/clients/qdrant.py).

### 5.1. Collection

- Имя вычисляется только backend: `<QDRANT_COLLECTION_PREFIX>_<project_id>`.
- Значение по умолчанию: `project_<id>`.
- Prefix приводится к нижнему регистру, дефисы заменяются подчёркиваниями.
- Используется один unnamed vector с `COSINE` distance.
- Размер vector задаётся `EMBEDDING_DIM` и валидируется перед upsert.
- Collection создаётся лениво при первом upsert или явно пересоздаётся полным reindex.
- Qdrant хранится в Docker volume `qdrant_data`.

Frontend не передаёт и не получает имя collection. Дополнительный `project_id` хранится в payload для диагностики, но изоляция обеспечивается прежде всего отдельной collection.

### 5.2. Детерминированный ID

Point ID строится как UUIDv5 от строки:

```text
project-management-dashboard-vera:knowledge:
<project_id>:<entity_type>:<entity_id>:<chunk_index>
```

Поэтому повторная обработка того же chunk обновляет тот же point. Перед upsert сущности старые chunks удаляются фильтром `entity_type + entity_id`; это также удаляет хвост, если после обновления документ стал короче.

### 5.3. Общий payload

```json
{
  "project_id": "7",
  "entity_type": "document",
  "entity_id": "42",
  "source_id": "document:42",
  "task_id": null,
  "title": "Архитектура авторизации",
  "text": "Текст semantic representation",
  "chunk_index": 3,
  "updated_at": "2026-09-01T18:00:00+00:00"
}
```

Дополнительные поля зависят от типа: `task_key`, `wbs_path`, `document_slug`, `heading`, `attachment_id`, `author_name`. Для документов выбран `entity_type=document`, а конкретный chunk определяется `chunk_index`; это упрощение относительно примера `document_chunk` из [ТЗ § 8](../project_knowledge_ai_concept.md#8-документы).

## 6. Что именно векторизуется

Builders находятся в [`knowledge/documents.py`](../backend/src/knowledge/documents.py), chunking — в [`knowledge/chunking.py`](../backend/src/knowledge/chunking.py).

| Сущность | Semantic representation | Разбиение |
|---|---|---|
| Project | код, название, Markdown-описание | один point |
| Task | ключ, заголовок, путь ИСР, Markdown-описание | один point |
| Comment | задача, имя автора, текст комментария | один point на комментарий |
| Document | название, текущий Markdown, заголовок секции | несколько chunks |
| Attachment | задача, имя файла, извлечённый текст | несколько chunks |

Статус, стадия, завершённость, priority, role, assignee, deadline и Kanban position не входят в Task embedding. Это защищает от лишних внешних вызовов при drag & drop и не позволяет устаревшему vector payload конкурировать с PostgreSQL. Все эти значения добавляются в `CURRENT_POSTGRES_STATE` непосредственно перед каждым ответом агента.

Основание: [ТЗ § 5](../project_knowledge_ai_concept.md#5-индексация-task), [§ 6](../project_knowledge_ai_concept.md#6-когда-переиндексировать-task), [§ 9](../project_knowledge_ai_concept.md#9-иср--structure) и запрет embeddings на каждое operational-изменение в [§ 24](../project_knowledge_ai_concept.md#24-первая-итерация).

### 6.1. Markdown chunking

1. Нормализуются CRLF/CR в LF.
2. Текст сначала делится по Markdown-заголовкам уровней 1–6.
3. Секции делятся по абзацам и логическим переносам.
4. Слишком большой абзац делится по границе слов.
5. В следующий chunk переносится хвост предыдущего размером до `KNOWLEDGE_CHUNK_OVERLAP_CHARS`.
6. Индексы chunks детерминированы порядком исходного документа.

Значения по умолчанию: целевой размер 2200 символов, overlap 300 символов.

### 6.2. Извлечение вложений

Модуль: [`knowledge/extract.py`](../backend/src/knowledge/extract.py).

| Формат | Поведение |
|---|---|
| `.pdf` | `pdfminer.six`, текст страниц по порядку, максимум 2000 страниц |
| `.docx` | `python-docx`, параграфы и строки таблиц в порядке XML-блоков |
| `.md`, `.txt`, `.csv`, `.log` | подбор кодировки: utf-8, затем уверенная догадка `chardet`, затем cp1251 |
| `.xlsx`, `.xlsm`, `.xls` | `openpyxl`/`xlrd`, все видимые листы, см. ниже |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif` | распознавание vision-моделью через [`clients/vision.py`](../backend/src/clients/vision.py) |
| остальные | не индексируются, но остаются обычными Task Attachment |

Разбор Excel ([`knowledge/excel.py`](../backend/src/knowledge/excel.py)) идёт по реальному формату книги, а не по расширению: сначала пробуется `openpyxl`, затем `xlrd`. Скрытые листы и скрытые (в том числе свёрнутые группировкой) строки пропускаются, объединённые ячейки разворачиваются в каждую ячейку диапазона, первая видимая строка листа считается шапкой. Каждая строка данных превращается в запись `колонка: значение, колонка: значение`, а лист предваряется строкой `Лист: <название>` — плоский формат, который эмбеддинг понимает лучше, чем реконструированную таблицу.

Изображения ([`knowledge/images.py`](../backend/src/knowledge/images.py)) без локального декодирования или преобразования кодируются в data URL с исходным MIME-типом и напрямую отправляются в vision-модель. Локального OCR нет намеренно: модель читает и рукописные пометки, и схемы, и таблицы на скриншотах, чего Tesseract не даёт. Формат `.avif` разрешён к загрузке, но пока не индексируется.

Разбор файлов выполняется через `asyncio.to_thread`, поэтому синхронные библиотеки не блокируют event loop; сетевой вызов vision-модели асинхронный. Ошибка разбора или пустой текст отдельного вложения логируется, вложение пропускается, а остальная индексация проекта продолжается — но недоступность vision-модели (`KnowledgeProviderError`) сознательно пробрасывается наверх, чтобы job ушла на повторную попытку, а не потеряла содержимое навсегда. Текст длиннее `KNOWLEDGE_EXTRACT_MAX_CHARS` обрезается. Старый `.doc`, RTF, ODF и PowerPoint не входят в текущую реализацию.

## 7. Матрица событий индексации

Publisher: [`KnowledgeEvents`](../backend/src/services/knowledge_events.py).

| Доменная операция | Задание | Причина |
|---|---|---|
| Create Project | `REINDEX_PROJECT` | создать collection после сохранения проекта и стадий |
| Update Project `key/name/description_md` | `REINDEX_PROJECT` | обновить semantic passport и task keys |
| Update Project operational-полей | нет | актуальные значения берутся из SQL |
| Delete Project | `DELETE_COLLECTION` | удалить весь производный индекс после SQL delete |
| Create Task | `UPSERT TASK` | создать semantic object |
| Update Task `title/description_md` | `UPSERT TASK` | изменился смысловой текст |
| Update priority/role/assignee/due date | нет | operational data, источник истины — SQL |
| Move Task / Kanban reorder | нет | stage и position не векторизуются |
| Назначить Task в WBS node | `UPSERT TASK` | изменился путь ИСР в semantic representation |
| Create/rename/move/delete WBS node | `REINDEX_PROJECT` | могли измениться пути нескольких задач |
| Create/update Document | `UPSERT DOCUMENT` | заменить актуальные chunks |
| Delete Document | `DELETE DOCUMENT` | удалить все chunks документа |
| Create Comment | `UPSERT COMMENT` | добавить отдельный semantic object |
| Delete Comment | `DELETE COMMENT` | убрать semantic object |
| Upload indexable Attachment | `UPSERT ATTACHMENT` | извлечь, разбить и проиндексировать текст |
| Delete Attachment | `DELETE ATTACHMENT` | удалить chunks файла |
| Create/update/delete Project Stage | нет | стадии и их состояние всегда читаются из SQL |

Удаление Task выполняет фильтр по `task_id`, поэтому одним действием удаляются point самой задачи и дочерние comments/attachments, даже если SQL cascade уже удалил их записи.

## 8. Полный reindex и согласованность

Сервис: [`KnowledgeIndexService`](../backend/src/services/knowledge_index.py).

Полный reindex:

1. Загружает Project, Tasks, WBS, Documents, Comments и Attachments из PostgreSQL/локального storage.
2. Строит все semantic documents.
3. Получает embeddings батчами.
4. Только после успешного получения и проверки всех vectors пересоздаёт collection.
5. Записывает points батчами и завершает job.

Так сбой embeddings API не уничтожает рабочую collection. Если сбой произойдёт уже во время пересоздания или записи Qdrant, job уйдёт на retry и повторит полную сборку. Alias-based atomic swap в текущем MVP не используется.

Обычный upsert сначала строит текст и получает embeddings, затем удаляет предыдущие chunks сущности и записывает новые. При ошибке до удаления прежние points остаются рабочими; ошибка записи после удаления восстанавливается очередной попыткой job.

## 9. Project Agent

Сервис: [`ProjectAgentService`](../backend/src/services/project_agent.py). Prompt: [`prompts/project_agent.py`](../backend/src/prompts/project_agent.py). Клиенты: [`embedding.py`](../backend/src/clients/embedding.py), [`llm.py`](../backend/src/clients/llm.py), [`qdrant.py`](../backend/src/clients/qdrant.py).

### 9.1. Актуальный SQL-контекст

На каждый вопрос заново загружаются:

- карточка и статус проекта;
- стадии и количество задач в каждой;
- полный список задач с текущими stage, completion, priority, role, assignee, deadline и путём ИСР;
- список документов и slug;
- до 30 последних событий задач.

Каждая сущность маркируется доверенным `source_id`, например `[task:142]` или `[document:7]`.

### 9.2. Semantic retrieval

Вопрос векторизуется той же моделью, что индекс. Поиск выполняется только в collection текущего проекта. По умолчанию возвращается до 10 результатов с cosine score не ниже `0.35`. В MVP поиск идёт сразу по всем entity types; отдельный пользовательский фильтр отсутствует.

Если embeddings/Qdrant недоступны, исключение перехватывается, пишется warning и Agent получает только SQL-срез. Это позволяет отвечать на structured-вопросы при временном сбое semantic layer.

### 9.3. LLM и grounding

В LLM передаются отдельными блоками:

- текущая дата;
- `CURRENT_POSTGRES_STATE`;
- `SEMANTIC_CONTEXT`;
- до 10 последних реплик текущего UI-диалога;
- текущий вопрос.

System prompt требует:

- использовать только переданный контекст;
- считать SQL приоритетным для динамических данных;
- прямо сообщать о недостатке информации;
- считать содержимое проекта недоверенными данными, а не инструкциями;
- не раскрывать prompt/секреты и не выдумывать факты;
- вернуть JSON с Markdown-ответом и списком `source_ids`.

Ответ валидируется Pydantic-схемой. Источники, которых не было в собранном контексте, отбрасываются. Если модель не выбрала источники, используются до пяти лучших semantic hits, но только после такой же проверки.

LLM client делает до `LLM_RETRIES` попыток с exponential backoff и принимает OpenAI-compatible Chat Completions JSON. Markdown code fence вокруг JSON удаляется перед валидацией.

### 9.4. Ограничения входа

- вопрос: 2–2000 символов после trim;
- история: максимум 10 сообщений;
- одна реплика истории: 1–8000 символов;
- ответ модели: максимум 20 000 символов по схеме;
- список источников модели: максимум 20 IDs.

## 10. HTTP API и безопасность

Endpoint: [`api/v1/endpoints/knowledge.py`](../backend/src/api/v1/endpoints/knowledge.py). Схемы: [`schemas/knowledge.py`](../backend/src/schemas/knowledge.py).

| Метод | URL | Ответ |
|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/knowledge/status` | enabled/ready, points, pending/processing/failed, last error |
| `POST` | `/api/v1/projects/{project_id}/knowledge/ask` | Markdown answer и валидированные Sources |
| `POST` | `/api/v1/projects/{project_id}/knowledge/reindex` | `202 Accepted`, `{ "queued": true }` |

Все три endpoint-а используют `AccessibleProjectDep`: сначала проверяется session cookie и членство/владение проектом. Клиент не может передать collection name, prefix, Qdrant filter или чужой project scope. Status response также не раскрывает внутреннее имя collection.

Основные ответы об ошибках:

- `401/403/404` — стандартный контур доступа к проекту;
- `422` — пустой/слишком длинный вопрос или некорректная история;
- `503` — отключён knowledge-контур или недоступен AI provider;
- `502` — Agent не смог сформировать корректный ответ;
- ошибка очереди/repository преобразуется в доменное исключение сервиса.

API следует [Depends-архитектуре](../FASTAPI_PATTERNS.md#6-dependency-injection) и [трёхслойной системе исключений](../FASTAPI_PATTERNS.md#8-исключения--трёхслойная-система).

## 11. Frontend «AI-вики»

Главная страница: [`ProjectKnowledgePage.tsx`](../frontend/src/routes/ProjectKnowledgePage.tsx). Маршрут регистрируется в [`App.tsx`](../frontend/src/App.tsx), вкладка — в [`ProjectLayout.tsx`](../frontend/src/components/projects/ProjectLayout.tsx), API/types — в [`lib/api.ts`](../frontend/src/lib/api.ts) и [`lib/types.ts`](../frontend/src/lib/types.ts).

Реализовано:

- project-scoped маршрут `/projects/:key/knowledge`;
- вкладка «AI-вики»;
- четыре стартовых вопроса;
- чат с локальной историей текущего открытия страницы;
- Enter для отправки, Shift+Enter для новой строки;
- состояние ожидания и отображение API-ошибки;
- безопасный Markdown-renderer через общий DOMPurify-контур;
- кликабельные Sources с иконками типов;
- Task/Comment/Attachment открывают Task Drawer;
- Document открывает `/projects/:key/docs/:slug`;
- status polling каждые 3 секунды;
- число Qdrant points, jobs в очереди, failed jobs и последняя ошибка;
- кнопка полного reindex, заблокированная во время активной индексации;
- responsive layout: диагностическая колонка скрывается ниже `lg`.

История не сохраняется в PostgreSQL и очищается при повторном входе на страницу/смене проекта. Streaming ответа не реализован: UI получает готовый JSON после завершения LLM-вызова.

## 12. Конфигурация

Настройки описаны в [`core/settings.py`](../backend/src/core/settings.py). Секреты загружаются из `backend/.env`, который исключён из Git.

### 12.1. LLM

| Переменная | Назначение | Default |
|---|---|---|
| `LLM_API_KEY` | Bearer token OpenAI-compatible API | обязательна |
| `LLM_API_URL` | Chat Completions endpoint | обязательна |
| `AGENT_MODEL` | модель Project Agent | `google/gemini-3.7-flash` |
| `LLM_MODEL` | общая модель для последующих AI-сценариев | `google/gemini-3.7-flash` |
| `LLM_TIMEOUT` | таймаут запроса, секунды | `300` |
| `LLM_RETRIES` | число попыток клиента | `3` |
| `VISION_MODEL` | модель распознавания изображений | `google/gemini-3.7-flash` |
| `VISION_MAX_TOKENS` | лимит ответа vision-модели | `4000` |

Vision-клиент переиспользует `LLM_API_URL`, `LLM_API_KEY`, `LLM_TIMEOUT` и `LLM_RETRIES`: это тот же OpenAI-совместимый Chat Completions endpoint, отличается только модель.

### 12.2. Embeddings

| Переменная | Назначение | Default |
|---|---|---|
| `EMBEDDING_API_KEY` | Bearer token embeddings API | обязательна |
| `EMBEDDING_API_URL` | OpenAI-compatible embeddings endpoint | обязательна |
| `EMBEDDING_MODEL` | модель векторизации | `openai/text-embedding-3-large` |
| `EMBEDDING_DIM` | ожидаемый размер vector | `3072` |
| `EMBEDDING_TIMEOUT` | таймаут батча, секунды | `120` |

### 12.3. Knowledge/Qdrant

| Переменная | Назначение | Default |
|---|---|---|
| `KNOWLEDGE_ENABLED` | включает publisher, worker, search и reindex | `true` |
| `QDRANT_URL` | адрес Qdrant | `http://localhost:6333` |
| `QDRANT_API_KEY` | ключ managed Qdrant, пустой для локального | пусто |
| `QDRANT_COLLECTION_PREFIX` | prefix project collections | `project` |
| `QDRANT_SCORE_THRESHOLD` | минимальный cosine score | `0.35` |
| `KNOWLEDGE_INDEX_POLL_SECONDS` | пауза idle worker | `2.0` |
| `KNOWLEDGE_INDEX_MAX_ATTEMPTS` | максимум попыток job | `5` |
| `KNOWLEDGE_EMBEDDING_BATCH_SIZE` | размер embedding/upsert batch | `32` |
| `KNOWLEDGE_CHUNK_TARGET_CHARS` | целевой размер chunk | `2200` |
| `KNOWLEDGE_CHUNK_OVERLAP_CHARS` | overlap соседних chunks | `300` |
| `KNOWLEDGE_AGENT_SEMANTIC_LIMIT` | максимум retrieval hits | `10` |
| `KNOWLEDGE_VISION_ENABLED` | распознавание изображений vision-моделью | `true` |
| `KNOWLEDGE_EXTRACT_MAX_CHARS` | предел текста одного вложения | `350000` |

При `KNOWLEDGE_VISION_ENABLED=false` изображения загружаются как обычно, но в индекс не попадают: остальные форматы не затрагиваются.

Размерность модели и `EMBEDDING_DIM` обязаны совпадать. После смены embedding-модели или размерности нужен полный reindex всех проектов.

## 13. Docker и запуск

[`docker-compose.yml`](../docker-compose.yml) содержит:

| Сервис | Порт хоста | Persistent data |
|---|---|---|
| PostgreSQL 16 | `5436` | `pg_data` |
| Qdrant 1.12.6 | `6333`, `6334` | `qdrant_data` |
| Backend | только внутренняя сеть, `8000` | uploads bind mount |
| Frontend | только внутренняя сеть, `80` | immutable image |
| Nginx gateway | `5173` | нет |

PostgreSQL и backend получают параметры через `env_file: ./backend/.env`; секции Compose `environment` для них не добавлены. В контейнерном режиме `POSTGRES_HOST=db`, `QDRANT_URL=http://qdrant:6333`, а `POSTGRES_DB` задаёт создаваемую базу. Для запуска backend непосредственно на Windows адреса меняются на `localhost`.

Команды:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Интерфейс: `http://localhost:5173/`. Qdrant REST: `http://localhost:6333/collections`.

Файл [`.gitattributes`](../.gitattributes) фиксирует LF для `*.sh`; это предотвращает попадание `\r` в аргументы Alembic/Hypercorn внутри Linux-контейнера.

## 14. Карта файлов реализации

| Область | Файлы |
|---|---|
| API и контракт | `backend/src/api/v1/endpoints/knowledge.py`, `backend/src/schemas/knowledge.py`, `backend/src/exceptions/knowledge.py` |
| Внешние клиенты | `backend/src/clients/embedding.py`, `llm.py`, `qdrant.py` |
| Постоянная очередь | model `knowledge_index_jobs.py`, repository `knowledge_index_jobs.py`, Alembic migration |
| Индексация | `backend/src/services/knowledge_events.py`, `knowledge_index.py`, `backend/src/knowledge/worker.py` |
| Представление знаний | `backend/src/knowledge/documents.py`, `chunking.py`, `extract.py` |
| Runtime | `backend/src/knowledge/runtime.py`, FastAPI lifespan в `backend/src/main.py` |
| Agent | `backend/src/services/project_agent.py`, `backend/src/prompts/project_agent.py` |
| CRUD-интеграция | services Projects, Tasks, Documents, Comments, Attachments и WBS |
| UI | `frontend/src/routes/ProjectKnowledgePage.tsx` и связанные route/API/type-файлы |
| Инфраструктура | `docker-compose.yml`, `backend/requirements.txt`, `backend/entrypoint.sh`, `.gitattributes` |

## 15. Тесты и проверки

Добавлены проверки:

- API: grounded answer/sources, validation пустого вопроса, mapping provider error в `503`, отсутствие collection name в status;
- access control: все knowledge endpoints закрыты authentication/project access;
- repository integration: дедупликация, claim и successful state постоянной очереди;
- unit: Markdown chunking, детерминированность, DOCX paragraphs/tables, пропуск неподдерживаемых файлов;
- unit извлечения: CSV в cp1251, книги `.xlsx`/`.xls` со скрытыми строками и объединёнными ячейками, выравнивание нумерации строк для таблицы не с первой строки, повреждённая книга, распознавание изображения и его пропуск при выключенной vision-модели, обрезка по лимиту;
- unit vision-клиента: формирование data URL, склейка multipart-ответа, retry и переход в `KnowledgeProviderError`; отдельно — что недоступность vision-модели роняет job, а не пропускает вложение;
- unit: отказ очереди не ломает доменную операцию, `KNOWLEDGE_ENABLED=false` отключает события;
- unit: Agent объединяет SQL и semantic context и продолжает работать без semantic provider;
- unit: создание/semantic update Task ставят upsert, operational update и Kanban move не запускают embedding.

Проверки перед фиксацией:

```text
backend pytest: 157 passed, 18 skipped
backend ruff:   passed
frontend vitest: 33 passed
frontend eslint: passed
frontend production Docker build: passed
Docker smoke: frontend 200, Qdrant 200, protected API 401 без session
Alembic in Docker: e7b5d29c41a0 (head)
```

18 integration-тестов штатно пропускаются окружением тестов, когда отдельный testcontainers PostgreSQL недоступен/не запрошен; основной Docker PostgreSQL при этом прошёл healthcheck, а миграция применена в запущенном приложении.

## 16. Известные ограничения и следующий этап

1. SQL-контекст сейчас включает полный список задач и документов проекта. Для очень больших проектов потребуется routing/tool-calling с выборочными SQL-запросами или ограничением контекста.
2. Semantic retrieval пока не принимает фильтр `entity_type`; поиск выполняется по всем типам внутри project collection.
3. Нет streaming token-ов и персистентной истории чата.
4. Comment source открывает Task Drawer, но не прокручивает к конкретному комментарию.
5. Нет OCR, `.doc`, RTF, Excel, PowerPoint и image understanding.
6. Нет Prometheus/OpenTelemetry-метрик latency; доступны структурные логи, очередь и status endpoint.
7. История `SUCCEEDED/FAILED` jobs автоматически не очищается.
8. Полный reindex пересоздаёт collection напрямую без временной collection и alias swap.
9. Работает один встроенный worker; отдельный process/queue broker не добавлялся согласно требованию не вводить тяжёлую инфраструктуру для MVP.
10. Context-aware floating panel, Decisions, Weekly Digest, knowledge graph и долговременная Project Memory оставлены для будущих итераций по [ТЗ § 19](../project_knowledge_ai_concept.md#19-context-aware-ai) и [§ 23](../project_knowledge_ai_concept.md#23-возможное-развитие).

## 17. Критерий восстановления

Qdrant не содержит уникальной бизнес-информации. Для восстановления достаточно PostgreSQL, Markdown-документов и файлов в uploads:

1. поднять PostgreSQL, backend и Qdrant;
2. открыть «AI-вики» нужного проекта;
3. нажать «Переиндексировать» либо вызвать `POST /api/v1/projects/{id}/knowledge/reindex`;
4. дождаться `pending_jobs=0`, `processing_jobs=0` и ненулевого `points_count`;
5. проверить контрольный вопрос и Sources.

Это непосредственно реализует принцип восстанавливаемого производного индекса из [ТЗ § 3](../project_knowledge_ai_concept.md#3-жизненный-цикл-collection) и [§ 13](../project_knowledge_ai_concept.md#13-reindex).
