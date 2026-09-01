# Концептуальное ТЗ: база знаний и AI-агент проекта

## 1. Цель

Расширить Project Task Tracker встроенной базой знаний по каждому проекту и AI-агентом. Пользователь должен иметь возможность задавать вопросы о проекте с опорой на задачи, комментарии, документы, ИСР/Structure и актуальные данные основной БД.

Ключевой принцип: **каждый Project получает отдельную collection внутри общего Qdrant**. PostgreSQL остаётся источником истины, Qdrant — семантическим индексом, а AI-агент объединяет оба источника.

## 2. Архитектурные принципы

### Project как граница знаний

При создании Project создаётся collection:

```text
project_<stable_project_id>
```

Имя строится по стабильному ID, а не названию проекта.

```text
Qdrant
├── project_<id_1>
├── project_<id_2>
└── project_<id_3>
```

Агент открытого проекта работает только с его collection.

### PostgreSQL — Source of Truth

Из PostgreSQL всегда получать актуальные:
- статусы;
- дедлайны;
- приоритеты;
- исполнителей;
- количество задач;
- ИСР;
- бизнес-связи и другие структурированные данные.

Qdrant не использовать как источник истины для динамического состояния.

### Qdrant — Semantic Knowledge Layer

Qdrant используется для смыслового поиска по:
- задачам и их описаниям;
- документам;
- комментариям;
- содержательному контексту структуры проекта.

## 3. Жизненный цикл collection

При создании Project:
1. сохранить Project в PostgreSQL;
2. создать Qdrant collection;
3. связать её со стабильным `project_id`.

При переименовании проекта collection не переименовывать.

При удалении проекта удалить соответствующую collection согласно общей логике удаления/архивации.

Qdrant должен быть полностью восстанавливаемым индексом. Уникальная бизнес-информация не должна существовать только в нём.

## 4. Индексируемые сущности

Первая итерация:

```text
Task
Document
Comment
```

Дополнительно допускается индексировать содержательные WbsNode либо добавлять путь ИСР в контекст связанных задач.

Архитектура должна позволять позже добавить:
- Decision;
- Project Event;
- Meeting Note;
- Release Note;
- текст вложений.

Каждый point должен иметь `entity_type` и ссылку на исходную сущность.

## 5. Индексация Task

При создании или содержательном изменении Task формируется semantic representation, например:

```text
Тип: задача
Название: Реализовать авторизацию пользователей
Раздел структуры: Backend / API / Authentication

Описание:
Добавить JWT authentication и refresh token.
```

Минимальный payload:

```json
{
  "entity_type": "task",
  "entity_id": "...",
  "task_id": "...",
  "title": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

Статус, priority и deadline допустимо хранить в payload или semantic representation как контекст, но при ответе об их текущем состоянии агент обязан получать актуальные значения из PostgreSQL.

## 6. Когда переиндексировать Task

Переиндексацию выполнять при semantic changes:
- title;
- description;
- значимом текстовом содержании;
- изменении пути ИСР, если он входит в embedding document.

Обычные operational changes:
- status;
- priority;
- deadline;
- Kanban position

не должны без необходимости запускать новый embedding. При необходимости обновлять только payload либо получать эти данные из PostgreSQL.

Drag & Drop задачи между колонками Kanban не должен автоматически означать дорогостоящую переиндексацию текста.

## 7. Комментарии

Комментарии важны, поскольку содержат причины решений, проблемы, уточнения, блокеры и договорённости.

Предпочтительно индексировать комментарии отдельными semantic objects с привязкой к Task:

```json
{
  "entity_type": "comment",
  "entity_id": "...",
  "task_id": "...",
  "author_id": "...",
  "created_at": "..."
}
```

Удалённый комментарий должен удаляться из knowledge layer.

В дальнейшем можно добавить выделение значимых решений из длинных discussion threads, но это не требуется в первой версии.

## 8. Документы

Pipeline:

```text
Document
↓
Parsing
↓
Semantic Chunking
↓
Embedding
↓
Qdrant
```

Большой документ не сохранять одним point.

Payload chunk:

```json
{
  "entity_type": "document_chunk",
  "entity_id": "...",
  "document_id": "...",
  "chunk_index": 3,
  "title": "...",
  "section_title": "...",
  "updated_at": "..."
}
```

Chunking должен учитывать структуру документа: заголовки, секции и логические блоки. Не резать текст механически на одинаковое число символов, если доступна смысловая структура.

При обновлении документа переиндексировать его актуальные chunks. При удалении удалить все points документа.

## 9. ИСР / Structure

Сама структура WBS остаётся в PostgreSQL.

Путь:

```text
Backend / API / Authentication
```

желательно добавлять в semantic representation Task. Это позволит искать задачи по смысловому контексту структуры без превращения Qdrant в источник истины для WBS.

Отдельный WbsNode имеет смысл индексировать только при наличии содержательного описания.

## 10. Knowledge Indexing Service

Embedding/Qdrant-логику изолировать от бизнес-сервисов.

```text
Task / Document / Comment Service
                │
                ↓
       Knowledge Indexing Service
                │
       ┌────────┼─────────┐
       ↓        ↓         ↓
 Document    Embedding   Qdrant
 Builder      Client     Repository
       │
     Chunker
```

Бизнес-сервис не должен знать детали embedding model, vector dimensions, chunking или структуры Qdrant points.

Реализация должна соответствовать существующей слоистой архитектуре и `FASTAPI_PATTERNS.md`.

## 11. Асинхронная индексация

Embedding не должен без необходимости увеличивать latency CRUD.

Предпочтительный flow:

```text
Create / Update entity
↓
PostgreSQL commit
↓
Indexing job/event
↓
Embedding
↓
Qdrant upsert
```

Использовать существующий инфраструктурный механизм фоновых задач/очередей, если он уже есть. Не вводить тяжёлую инфраструктуру только ради этой функции.

Ошибка embedding provider/Qdrant не должна отменять уже успешно сохранённую Task или Document. Индексация должна иметь retry.

## 12. Идемпотентность

Повторная обработка сущности не должна создавать дубликаты.

Point IDs детерминированно связывать с:
- `entity_type`;
- `entity_id`;
- для документа — также с chunk identity/version.

Upsert одной сущности должен обновлять существующий индекс.

## 13. Reindex

Предусмотреть административную операцию:

```text
Reindex Project Knowledge
```

Она полностью восстанавливает semantic index проекта из PostgreSQL и документов.

Это обязательное следствие принципа:

> Qdrant — производный индекс, а не первичное хранилище.

## 14. Project Agent

Внутри Project появляется AI-интерфейс, рабочее название:

```text
Ask Project
```

или:

```text
Project Knowledge
```

Backend самостоятельно определяет collection по `project_id`. Frontend никогда не передаёт произвольное имя collection.

Перед retrieval обязательно проверяется доступ пользователя к Project.

## 15. Инструменты агента

Агент получает два класса tools.

### Semantic

```text
search_project_knowledge
```

Поиск только внутри collection текущего Project с возможностью фильтрации:

```text
entity_type = task
entity_type = document_chunk
entity_type = comment
```

### Structured

Концептуальный набор:

```text
get_project
get_task
get_project_tasks
get_tasks_by_status
get_overdue_tasks
get_project_statistics
get_project_structure
get_recent_project_activity
```

Точный API реализовать в стиле существующего приложения.

## 16. Routing вопросов

Semantic:

```text
Что мы решили по авторизации?
```

→ Qdrant.

Structured:

```text
Сколько задач сейчас In Progress?
```

→ PostgreSQL/application tool.

Hybrid:

```text
Почему авторизация ещё не завершена?
```

→ найти релевантные Task → получить актуальные состояния из PostgreSQL → найти связанные комментарии/документы → сформировать grounded answer.

Агент должен самостоятельно выбирать нужные источники и при необходимости использовать несколько tools.

## 17. Grounding и источники

Ответы должны ссылаться на реальные сущности проекта.

Пример:

```text
Основной блокер связан с TASK-142.

В последнем обсуждении указано, что backend ожидает уточнения
формата refresh token.

В документе "Authentication Architecture" описана схема,
которая отличается от текущей реализации.
```

Под ответом UI показывает Sources:

```text
TASK-142 · Реализовать авторизацию
Authentication Architecture
Comment · TASK-142 · 31 Aug
```

Источники интерактивны:
- Task → открыть Task Detail Drawer;
- Document → открыть документ;
- Comment → открыть Task и сфокусировать комментарий.

При недостатке данных агент должен прямо сообщить, что информации в проекте недостаточно, а не достраивать факты.

## 18. UI

На уровне Project добавить:

```text
Overview | Tasks | Kanban | Documents | Structure | Ask Project
```

Стартовый экран Ask Project:

```text
┌──────────────────────────────────────────────────────┐
│ Ask Project                                          │
│                                                      │
│ Спросите что-нибудь об этом проекте                  │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Что сейчас блокирует завершение backend?        │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ [Что сейчас в работе?]                               │
│ [Какие задачи просрочены?]                           │
│ [Что решили по авторизации?]                         │
│ [Что изменилось недавно?]                            │
└──────────────────────────────────────────────────────┘
```

Интерфейс должен соответствовать общей dark design system трекера.

## 19. Context-aware AI

Архитектура должна позволять позже открыть AI как floating panel из Kanban, Task, Document или Structure.

Помимо `project_id` тогда передаётся UI context:

```text
current_entity_type
current_entity_id
```

Например, находясь в TASK-142, пользователь спрашивает:

```text
Почему мы выбрали этот подход?
```

Агент использует текущую Task как дополнительный retrieval context.

Это не обязательно реализовывать в первой итерации.

## 20. Статус индексации и диагностика

Необходимо иметь технический статус:

```text
pending
indexed
failed
```

или эквивалентный статус indexing job.

Логировать минимум:

```text
project_id
entity_type
entity_id
operation
embedding_model
collection
duration
result
error
```

Полезные метрики:
- successful/failed indexing;
- embedding latency;
- Qdrant latency;
- retrieval latency;
- количество points в project collection;
- reindex operations.

## 21. Безопасность

Project — жёсткая граница данных.

Алгоритм запроса:

```text
Frontend sends project_id
↓
Backend checks access
↓
Backend resolves collection name
↓
Agent / retrieval works only with this collection
```

Нельзя принимать collection name от клиента.

AI не должен иметь возможности выполнять cross-project retrieval.

## 22. Удаление данных

При удалении:
- Task → удалить её points;
- Comment → удалить point комментария;
- Document → удалить все chunks;
- Project → удалить project collection согласно lifecycle проекта.

Удаление из Qdrant не заменяет основную бизнес-операцию в PostgreSQL.

## 23. Возможное развитие

Архитектура должна позволять позже добавить:

### Project Decisions
Фиксацию решений, причин и связанных Task/Documents.

### Project Summary
Автоматическое резюме состояния проекта.

### Weekly Digest
Что изменилось, завершено, заблокировано и какие решения приняты.

### Similarity
Похожие задачи и связанные документы.

### Knowledge Extraction
Автоматическое выделение из обсуждений решений, рисков, блокеров и договорённостей.

### Project Memory
Более долговременную память агента, но только как отдельный контролируемый слой, а не смешанную с source-of-truth данными.

## 24. Первая итерация

MVP:

1. Автоматическое создание Qdrant collection для Project.
2. Индексация Task.
3. Индексация Documents с chunking.
4. Индексация Comments.
5. Upsert/delete при изменении исходных сущностей.
6. Project-scoped semantic search.
7. Structured tools для актуальных данных PostgreSQL.
8. Project Agent.
9. UI `Ask Project`.
10. Интерактивные Sources.
11. Retry индексации.
12. Полный Reindex Project.

Не включать в MVP:
- multi-agent orchestration;
- knowledge graph;
- сложную автономную память;
- автоматическое создание решений;
- embeddings на каждое operational изменение Task.

## 25. Целевой результат

После реализации каждый Project становится самостоятельным knowledge workspace.

Обычная работа пользователя автоматически формирует знания:

```text
Tasks ───────┐
Comments ────┼──→ Project Knowledge Collection
Documents ───┤              │
Structure ───┘              ↓
                       Semantic Search
                              │
PostgreSQL ── Structured Tools│
          └───────────────────┤
                              ↓
                         Project Agent
                              ↓
                    Grounded Project Answer
```

Пользователю не требуется вручную поддерживать отдельную Wiki.

Task Tracker сам накапливает знания проекта, а AI-агент предоставляет единый разговорный интерфейс к структурированным данным и накопленному текстовому контексту.
