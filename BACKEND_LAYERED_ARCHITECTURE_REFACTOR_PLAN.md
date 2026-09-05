# План рефакторинга backend под слоистую архитектуру и DI

Статус: повторно проверен по коду и [FASTAPI_PATTERNS.md](./FASTAPI_PATTERNS.md)
2026-09-04; готов к
реализации с оговоркой по синхронным AI-контрактам из раздела «Границы задачи».

Источник правил: [FASTAPI_PATTERNS.md](./FASTAPI_PATTERNS.md), разделы 1–3,
5–10, 13, 15, 16 и 18.

Область работ: `backend/src/**` и необходимые тесты в `backend/tests/**`.

## Журнал выполнения

Отметка ставится после того, как этап полностью выполнен, `ruff` и затронутые
тесты прошли, а изменения закоммичены.

| Этап | Статус | Тесты после этапа | Коммит |
|---|---|---|---|
| 0. Safety net | ✅ выполнен | 633 passed | `stage-0` |
| 1. Client/config dependencies | ✅ выполнен | 791 passed | `stage-1` |
| 2. Auth/access в сервисы, write scope | ✅ выполнен | 882 passed | `stage-2` |
| 3. Exception boundaries | ⬜ | — | — |
| 4. Транзакционные границы | ⬜ | — | — |
| 5. Атомарный импорт документа | ⬜ | — | — |
| 6. Короткие DB scopes | ⬜ | — | — |
| 7. Очистка endpoints | ⬜ | — | — |
| 8. MCP на сервисы | ⬜ | — | — |
| 9. DI knowledge worker | ⬜ | — | — |
| 10. Архитектурные тесты | ⬜ | — | — |

Baseline до рефакторинга: `pytest 587 passed`, `ruff All checks passed`.

### Уточнения фактических чисел

Повторный обход собранного приложения на старте работ дал **84 маршрута**, из
них **56 non-GET**, а не 57 как записано ниже в разделе 4. Фактическая
классификация: **47 доменных мутаций**, 3 public auth route, 2 session-only
route управления токенами и 4 read-only POST. Эти числа зафиксированы тестом
`tests/characterization/test_route_inventory.py` и используются вместо оценок
плана на этапах 2 и 10.

## Нормативная карта

В плане используются короткие ссылки на конкретные правила исходного документа:

- [PAT-ARCH] — § 1 «Слоистая архитектура»: направление зависимостей и границы
  endpoint/service/repository/client;
- [PAT-STRUCT] — § 2 «Структура проекта»: отдельные DI-модули для session,
  repositories, services, clients и HTTP client;
- [PAT-CONFIG] — § 3 «Конфигурация»: `get_settings()` как composition-time access и
  явные ресурсные лимиты;
- [PAT-LIFESPAN] — § 5 «Точка входа и lifespan»: создание и гарантированное закрытие
  тяжёлых ресурсов владельцем lifespan;
- [PAT-DI] — § 6 «Dependency Injection»: уровни фабрик, обязательные зависимости и
  `...Dep` aliases;
- [PAT-AUTH] — § 6 «Авторизация как Depends-зависимость»: auth dependency вызывает
  сервис и только преобразует ожидаемую доменную ошибку в `HTTPException`;
- [PAT-HTTP] — § 6 «Жизненный цикл HTTP-клиента»: один выбранный lifecycle,
  constructor injection и отсутствие fallback-создания клиента;
- [PAT-STREAM] — § 6 «Долгоживущие соединения»: короткий preflight scope и никаких
  yield-зависимостей с ограниченным ресурсом в streaming-фазе;
- [PAT-ENDPOINT] — § 7 «Эндпоинты»: endpoint знает готовый сервис и мапит только его
  перечисленные доменные ошибки;
- [PAT-ERROR] — § 8 «Исключения»: собственная иерархия каждого слоя и преобразование
  ошибки на границе;
- [PAT-SERVICE] — § 9 «Сервисный слой»: use case и все его зависимости передаются
  через конструктор;
- [PAT-REPO] — § 10 «Репозитории»: один публичный repository method — один запрос,
  явный `commit` contract и repository error boundary;
- [PAT-TX] — § 10 «Транзакционная граница составного use-case»: один
  application-service owner, `commit=False` у вложенных операций и один финальный
  commit;
- [PAT-EVENTS] — § 10 «Журнал кейса»: обязательная constructor dependency для
  событий, входящих в один бизнес-факт;
- [PAT-CLIENT] — § 13 «Клиенты внешних API/LLM»: injected transport, retry policy и
  рассчитанный worst-case budget;
- [PAT-MIGRATION] — § 15 «Миграции»: Alembic содержит только DDL;
- [PAT-TIMEOUT] — § 16 «Инфраструктура и запуск»: единый budget timeout-ов и
  асинхронный контракт для операций, которые в него не помещаются;
- [PAT-TEST] — § 18 «Тестирование»: layer-specific tests, real PostgreSQL,
  `dependency_overrides`, AST и dependency-graph guards.

Смысл формулировок:

- **требование паттерна** — правило прямо зафиксировано в `FASTAPI_PATTERNS.md`;
- **проектное применение** — конкретный способ применить это правило к текущему
  коду; допустима эквивалентная реализация, если она сохраняет тот же инвариант и
  покрыта тестом;
- **граница задачи** — исполнитель не расширяет публичный контракт или область
  diff без отдельного решения владельца продукта.

## 1. Цель

Привести backend к однонаправленной схеме зависимостей:

```text
HTTP endpoint / MCP tool / worker loop
                 ↓
       application service
          ↙             ↘
   repository          external client / storage
       ↓
      DB
```

Это прямое требование [PAT-ARCH]; способ сборки графа через отдельные фабрики —
[PAT-DI] и [PAT-STRUCT].

После рефакторинга:

- HTTP- и MCP-адаптеры не обращаются к репозиториям и SQLAlchemy;
- `dependencies/` только собирает граф и преобразует доменные ошибки авторизации в транспортные;
- все зависимости сервисов обязательны и передаются через конструктор;
- сервисы не читают глобальные settings и не используют service locator;
- внешние клиенты создаются один раз в lifespan, имеют явного владельца и закрываются при shutdown;
- DB и HTTP pools имеют явные, документированные лимиты из Settings;
- медленный внешний вызов и streaming-ответ не удерживают соединение с PostgreSQL;
- транзакцией составного use case владеет верхнеуровневый application service;
- ограничения архитектуры закреплены автоматическими тестами.

## 2. Границы задачи

Нужно сохранить без изменений:

- URL, HTTP-методы, request/response schemas и status codes публичного API;
- имена, аргументы и формат результата MCP tools;
- структуру таблиц и существующие данные;
- формат файлов в storage и имена Qdrant collections;
- текущую бизнес-логику доступа: чужой или отсутствующий объект отвечает одинаковым 404;
- cookie-аутентификацию и Bearer API tokens;
- семантику `knowledge_enabled`;
- семантику текущих SQL-запросов; форму запроса можно менять только там, где это
  необходимо для правила «один repository method — один SQL» или атомарного claim;

Не входят в эту задачу:

- frontend;
- визуальные и продуктовые изменения;
- массовое переименование моделей, schemas и URL;
- переработка OpenAPI-текстов, логов и docstrings, если строка не затронута архитектурным изменением;
- правка уже применённых Alembic migrations.

Это архитектурный/DI-аудит, а не полный style-аудит всех 18 разделов документа.
Правила логирования, оформление каждой OpenAPI-операции, полнота `doc/comment` у
моделей и визуальная настройка admin не расширяют этот план, если они не
затронуты переносом архитектурной границы.

Важно: в исторических migrations уже есть DML, запрещённый [PAT-MIGRATION]:
`20260901_1800_users_and_project_members.py`,
`20260901_2100_project_knowledge_jobs.py`,
`20260903_1200_wbs_task_placement.py`,
`20260904_1100_project_sticker_coordinates.py`. Не переписывать применённую
историю в рамках этого рефакторинга. Вынос backfill в operational-команды должен
быть отдельной задачей.

Отдельная подтверждённая граница: перевод синхронных AI endpoints на
job/polling меняет публичный контракт и поэтому не разрешён исполнителю этого
рефакторинга автоматически. При этом [PAT-CLIENT] и [PAT-TIMEOUT] требуют такого
перевода, если worst-case внешнего вызова не помещается в общий timeout budget.
Ниже это оформлено как обязательный decision record и отдельная продуктовая
задача; short DB scopes исправляются в текущем плане независимо от решения.

## 3. Что проверено

Аудит охватил:

- 206 Python-файлов и 30 086 строк в `backend/src`;
- 22 endpoint-модуля;
- 26 service-модулей;
- 19 repository/UoW-модулей;
- 4 клиента внешних систем;
- HTTP dependency graph собранного FastAPI-приложения;
- MCP transport, read/write tools и ручную сборку сервисов;
- knowledge worker и lifecycle клиентов;
- 82 тестовых файла.

Исходный baseline на момент аудита:

```text
pytest: 587 passed, 3 warnings
ruff:  All checks passed
```

Уже соответствуют целевой архитектуре и не требуют переписывания с нуля:

- обычные JSON-endpoints не создают репозитории и не пишут SQL;
- сервисы не импортируют FastAPI и SQLAlchemy;
- основной FastAPI DI-граф уже имеет уровни session → repository → service;
- большинство составных мутаций уже используют общий `UnitOfWork` и transactional outbox;
- репозитории принимают `AsyncSession` через конструктор и в основном нормализуют DB errors;
- все репозитории имеют integration-тесты на PostgreSQL;
- knowledge worker уже выполняет внешнюю часть index job после закрытия подготовительной DB-сессии; это поведение нужно сохранить.

## 4. Подтверждённые отклонения

### P0. Write scope объявлен, но не подключён к HTTP-мутациям

Файл: `backend/src/dependencies/auth.py:99-142`.

`WriteScopeDep` существует, однако повторный обход собранного графа показал:
проверено 57 POST/PATCH/DELETE routes, и ни в одном нет
`require_write_scope`. В результате Bearer token со scope `READ` проходит через
`CurrentUserDep` и может вызывать HTTP-мутации. В MCP аналогичная проверка есть
через `tool_context(..., require_write=True)`, то есть два транспорта уже
расходятся по правилам доступа.

Это не повод запретить все POST-запросы: часть из них логически read-only (`calendar/scenarios/preview`, `tasks/rephrase`, `wbs/suggestion`, `knowledge/ask`). Нужна явная классификация use cases.

Основание: [PAT-AUTH] и [PAT-DI]. Само соответствие scope конкретному use case —
проектный security-инвариант, поэтому его нужно закрепить route-graph тестом, а
не выводить только из HTTP-метода ([PAT-TEST]).

### P0. Streaming выдача файла удерживает request-scoped DB dependency

Файл: `backend/src/api/v1/endpoints/task_attachments.py:123-171`.

Маршрут возвращает `FileResponse`, но его dependency graph включает одновременно:

- `get_accessible_task`;
- `get_task_attachments_service`;
- несколько repository dependencies;
- `get_db_session`.

Yield-зависимость FastAPI освобождается после завершения ответа, поэтому медленное скачивание может держать сессию/соединение до конца передачи файла. Это прямое нарушение раздела 6 о streaming routes.

Основание и требуемый шаблон: короткий auth/access preflight, закрытие DB scope,
затем передача в streaming-фазу только immutable metadata — [PAT-STREAM].

### P0. Синхронные AI use cases могут держать DB connection во время внешнего вызова

Затронуты:

- `services/analytics.py:237-307`;
- `services/project_agent.py:199-365`;
- `services/task_descriptions.py:62-181`;
- `services/wbs_suggestion.py:90-153`;
- `services/task_documents.py:49-124`;
- MCP `search_project_knowledge` в `mcp_server/server.py:269-322`.

В этих route/use-case графах request-scoped `AsyncSession` участвует либо через
репозитории самого сервиса, либо через auth/access dependency. После первого
SELECT SQLAlchemy открывает транзакцию, затем код обращается к
LLM/embedding/Qdrant/vision, а FastAPI закрывает сессию только после ответа. При
timeout до 300 секунд и retry это создаёт риск `idle in transaction` и
исчерпания пула. В частности, `TaskDescriptionService` сам не принимает
репозиторий, но его endpoint удерживает сессию через `get_accessible_project` —
исправлять нужно весь dependency graph, а не только constructor сервиса.

`knowledge/worker.py` уже реализует правильный шаблон prepare in DB scope → close session → external call; тот же инвариант нужен HTTP и MCP AI-сценариям.

Основание: требование считать worst-case и не удерживать DB connection во время
долгого upstream-вызова — [PAT-CLIENT]; короткие resource scopes и их
пороговая проверка — [PAT-STREAM] и [PAT-TEST]. Разделение на
prepare → external → persist является проектным применением этих правил.

### P0. Timeout budget синхронных AI endpoints не согласован

Фактические настройки: `llm_timeout=300`, `llm_retries=3`; только ожидания
upstream дают worst case около 900 секунд, плюс backoff. В `nginx/nginx.conf`
таймаут 3600 секунд задан только для MCP, а `/api/` использует стандартный
`proxy_read_timeout` около 60 секунд. Во frontend `fetch` отдельный timeout не
зафиксирован. Значит текущая цепочка не удовлетворяет неравенству из
[PAT-TIMEOUT], а запрос может продолжать работу после ответа 504 от proxy.

Рекомендация [PAT-CLIENT]/[PAT-TIMEOUT]: явно посчитать и задокументировать
worst-case каждого AI-клиента; если он не помещается в бюджет, использовать
job id + polling/realtime, а не просто увеличивать timeout. Это изменение
публичного API вынесено из текущего DI-рефакторинга: исполнитель создаёт decision
record/follow-up и не меняет response schemas без отдельного одобрения. При этом
этап с короткими DB scopes остаётся обязательным и устраняет утечку ресурса даже
до продуктовой миграции.

### P1. Бизнес-логика аутентификации и доступа находится в Depends-слое

Файлы:

- `backend/src/dependencies/auth.py:41-200`;
- `backend/src/dependencies/access.py:49-176`.

Сейчас dependencies:

- напрямую принимают repository dependencies;
- ищут пользователей, токены, проекты, задачи, стадии, документы, комментарии и связи;
- проверяют membership/owner role;
- обновляют `last_used_at` токена;
- возвращают SQLAlchemy ORM instances;
- ловят repository/base `ApplicationError` и сразу формируют HTTP errors.

Исключение из `FASTAPI_PATTERNS.md` разрешает auth dependency преобразовать доменную ошибку в `HTTPException`, но не переносит в Depends бизнес-правила и доступ к данным. Сейчас к тому же часть repository errors из `get_accessible_*` не преобразуется локально, потому что try/except охватывает только `_authorize`.

Дополнительное нарушение: обязательные `users_repository` и `tokens_repository` в `get_principal` объявлены с `= None`, поэтому отсутствие зависимости не является ошибкой сборки графа.

Основание: endpoint/adapter зависит от сервиса, а сервис — от repository
([PAT-ARCH], [PAT-DI]); auth dependency имеет узкое исключение только для
service-error → `HTTPException` mapping ([PAT-AUTH]).

### P1. Скрытые global/service-locator dependencies в сервисах

Прямой `get_settings()` используется в:

- `services/auth.py`;
- `services/api_tokens.py`;
- `services/analytics.py`;
- `services/project_agent.py`;
- `services/task_documents.py`.

Fallback `runtime or get_knowledge_runtime()` используется в:

- `services/analytics.py`;
- `services/project_agent.py`;
- `services/knowledge_index.py`;
- `services/task_descriptions.py`;
- `services/task_documents.py`;
- `services/wbs_suggestion.py`.

Из-за fallback production DI-фабрики фактически не передают AI clients: сервис сам находит глобальный runtime. `knowledge/runtime.py` лениво создаёт singleton и `httpx.AsyncClient`, то есть lifecycle скрыт от места сборки.

Основание: все service dependencies передаются через constructor
([PAT-SERVICE]); сетевой transport также обязателен и не создаётся через fallback
([PAT-HTTP], [PAT-CLIENT]).

### P1. Обязательные production-зависимости объявлены optional

`KnowledgeEvents | None = None` допускается в восьми мутирующих сервисах: projects, tasks, wbs_nodes, wbs_suggestion, documents, milestones, task_comments, task_attachments. Ветка `if self.knowledge_events is not None` молча отключает transactional outbox.

Аналогично:

- `ProjectsService` и `TasksService` допускают отсутствие `TaskAttachmentStorage`;
- `ProjectAgentService` допускает отсутствие milestones repository, calendar service и scenario service и молча урезает набор инструментов;
- AI-сервисы допускают отсутствие runtime и переходят к global fallback.

В production все эти зависимости уже доступны. Optional defaults существуют в основном ради удобства тестов и нарушают fail-fast DI.

Основание: обязательные зависимости должны ломать сборку графа, а не тихо
отключать поведение ([PAT-DI], [PAT-SERVICE]). Для `KnowledgeEvents` применяется
инвариант обязательного transactional event collaborator из [PAT-EVENTS]; это
аналогия текущего домена, а не требование создать именно `CaseEventService`.

### P1. Нет DI-слоя внешних клиентов

В проекте отсутствуют предусмотренные документом `dependencies/http_client.py` и `dependencies/clients.py`.

`knowledge/runtime.py` одновременно:

- создаёт `httpx.AsyncClient`;
- создаёт четыре client wrappers;
- читает settings;
- хранит global singleton;
- управляет shutdown.

Это мешает `dependency_overrides`, скрывает resource ownership и заставляет worker/MCP/HTTP пользоваться service locator. У `httpx.AsyncClient` также не заданы явные `Limits`.

Если метрик нагрузки ещё нет, безопасный стартовый вариант — явно зафиксировать
текущее поведение httpx (`max_connections=100`,
`max_keepalive_connections=20`, `keepalive_expiry=5`) как baseline в Settings и
описать, что значения подлежат пересмотру по измеренной конкурентности. Важен не
сам набор чисел, а осознанный лимит и единая точка его изменения.

Дополнительно `ProjectQdrantClient` сам создаёт `AsyncQdrantClient`. Для
специализированного SDK нужно применить тот же принцип: готовый transport/client
создаёт lifespan composition root и передаёт wrapper-у, либо wrapper явно
объявляется единственным lifespan-owned владельцем и тестируется на одно
закрытие. Первый вариант предпочтительнее, поскольку лучше подменяется в тестах.

Основание: структура DI — [PAT-STRUCT], shared lifecycle — [PAT-LIFESPAN] и
[PAT-HTTP], injected transport — [PAT-CLIENT], явные лимиты — [PAT-CONFIG].

### P1. Параметры DB pool оставлены библиотечным defaults

Файл: `backend/src/db/session.py:1-8`.

`create_async_engine()` получает только URL; в `DBSettings` нет `pool_size`,
`pool_max_overflow`, `pool_timeout` и `pool_recycle`, не включён
`pool_pre_ping`. Это особенно опасно рядом с уже подтверждённым удержанием
сессий: поведение при исчерпании пула определяется не решением проекта, а
умолчаниями SQLAlchemy.

Рекомендация [PAT-CONFIG]: для текущего single-worker compose явно сохранить
размерный baseline `pool_size=5`, `pool_max_overflow=10`, сократить
`pool_timeout` до 5 секунд, включить `pool_pre_ping=True` и
`pool_recycle=1800`; каждое значение вынести в `DBSettings` с комментарием.
При изменении числа workers обязательно пересчитывать
`(pool_size + overflow) × processes` относительно `max_connections` PostgreSQL
с операционным запасом. Конкретные значения допускается скорректировать по
метрикам, но не оставлять неявными.

### P1. MCP read adapter обходит сервисный слой

Прямые repository constructors вне разрешённой composition-фабрики:

- `mcp_server/context.py` — 5;
- `mcp_server/server.py` — 13;
- `mcp_server/write_tools.py` — 3.

`mcp_server/server.py` выполняет фильтрацию, агрегацию и semantic search непосредственно в tool handlers. `mcp_server/context.py` вручную вызывает FastAPI dependency `get_principal`, ловит `HTTPException` и отдаёт `AsyncSession` через `ToolContext`. `mcp_server/presenters.py` типизирован ORM-моделями.

`mcp_server/services.py` можно оставить местом ручной сборки DI для MCP, но presentation-модули не должны видеть session/repositories.

Основание: MCP — транспортный adapter, поэтому к нему применяется та же цепочка
[PAT-ARCH]; orchestration принадлежит use-case service ([PAT-SERVICE]), а запрет
импортов закрепляется согласно [PAT-TEST].

### P1. Worker сам является и циклом, и composition root, и DB/application layer

Файл: `backend/src/knowledge/worker.py`.

Внутри worker напрямую используются:

- global `async_session_factory`;
- `get_settings()`;
- `get_knowledge_runtime()`;
- 10 concrete repository constructions;
- ручная сборка `KnowledgeIndexService`.

Короткие сессии реализованы правильно, но зависимости нельзя подменить без monkeypatch модульных globals. Цикл worker должен получать готовые фабрики/use-case services через конструктор.

Основание: constructor injection [PAT-SERVICE], явный composition/lifecycle
[PAT-DI] и [PAT-LIFESPAN]. Сохраняемый short-scope шаблон уже является хорошей
реализацией resource-инварианта [PAT-CLIENT].

### P1. Транзакционная стратегия репозиториев непоследовательна

Сейчас есть два неявных режима:

- `ApiTokensRepository`, `UsersRepository`, `DocumentLinksRepository` и часть `KnowledgeIndexJobsRepository` самостоятельно делают commit;
- большинство остальных write-методов всегда делают flush и рассчитывают на внешний `UnitOfWork`, но не имеют явного `commit=False`.

Это расходится с [PAT-REPO] и [PAT-TX]: самостоятельная запись по умолчанию
делает commit, а участие в составном use case выражается явным keyword-only
`commit=False`; владельцем финального commit остаётся application service.

Повторная проверка показала, что первоначальный список multi-query методов был
неполным:

- в 24 write-методах после DML вызывается `session.refresh()`, то есть публичный
  метод выполняет дополнительный SELECT: `AnalyticsReports.save`,
  `ApiTokens.create`, `DocumentLinks.create`, `Documents.create/update`,
  `KnowledgeIndexJobs.enqueue`, `Milestones.save/update`, `ProjectMembers.save`,
  `ProjectStages.save_many/save/update`, `Projects.save/update`,
  `TaskActivity.save`, `TaskAttachments.save`, `TaskComments.save`,
  `TaskDependencies.save`, `Tasks.save/update`, `Users.save/update`,
  `WbsNodes.save/update`;
- `ProjectStickersRepository.create` делает INSERT и `get_by_id`,
  `update_position` — UPDATE и `get_by_id`, а `update` — UPDATE стикера, DELETE и
  INSERT связей, затем `get_by_id`;
- `TaskParticipantsRepository.replace_for_task` совмещает DELETE и INSERT;
- `KnowledgeIndexJobsRepository.enqueue` совмещает поиск дубликата, INSERT и
  refresh, а `enqueue_many` повторяет этот цикл для каждого элемента;
- `KnowledgeIndexJobsRepository.claim_next_batch` выполняет от одного до трёх
  SELECT-запросов, меняет ORM-объекты и делает commit;
- `KnowledgeIndexJobsRepository.mark_failed` сначала загружает job, затем
  сохраняет новый статус отдельным запросом;
- `ProjectStagesRepository.save_many` является допустимым batch-use case, но
  выполняет отдельный refresh для каждой строки вместо одного batch/RETURNING.

Требуемый результат [PAT-REPO]: каждый обычный публичный repository method
соответствует одному SQL statement; orchestration нескольких операций переезжает
в service. Для возвращаемых server-generated полей использовать PostgreSQL
`RETURNING` или проверенное ORM eager-default поведение, а не последующий
`refresh()`. Массовые операции остаются явно названными batch-методами и следуют
отдельному правилу батчей из § 10. Не менять запрос только ради косметики — каждый
rewrite должен иметь integration test на реальном PostgreSQL ([PAT-TEST]).

### P1. Импорт документа состоит из нескольких независимых commit

Файлы:

- `services/task_documents.py:49-154`;
- `services/task_attachments.py:124-216`;
- `services/documents.py:123-174`;
- `services/document_links.py:53-115`;
- `repositories/document_links.py:119-176`.

`TaskDocumentImportService` последовательно вызывает три публичных сервиса, каждый фиксирует свою часть. При сбое выполняется best-effort компенсация уже закоммиченных данных. Это не единый DB-факт и не соответствует правилу nested service `commit=False` + один финальный commit.

Кроме того, endpoint импорта вынужден ловить пять разных семейств ошибок, поскольку верхний сервис не закрывает свою exception boundary.

Основание и целевой шаблон: [PAT-TX] для одной DB-транзакции, [PAT-ERROR] для
преобразования ошибок вложенных сервисов и [PAT-ENDPOINT] для единственной
верхнеуровневой exception hierarchy в endpoint.

### P1. Исключения внешних слоёв имеют тип сервисного слоя

- Все AI clients поднимают `KnowledgeProviderError`, который наследуется от `KnowledgeServiceError`.
- `AvatarStorage` поднимает `AvatarStorageError`, который наследуется от `UsersServiceError`.
- `TaskAttachmentStorageError` не имеет общего явного storage-layer base.

Таким образом client/storage фактически бросают ошибку вышестоящего слоя, а endpoints местами ловят client error напрямую. В ряде сервисов `try` также охватывает собственные доменные ошибки, после чего используется `except OwnServiceError: raise`.

Основание: каждый слой имеет собственные исключения, а вышестоящий слой явно их
преобразует через `raise ... from error` — [PAT-ERROR] и [PAT-ARCH].

### P1. Нет автоматических архитектурных ограничителей

В `backend/tests` нет AST/import-boundary тестов и нет проверки собранного route
dependency graph. Поэтому прямой repository import, global settings fallback,
DB dependency у streaming route или забытый write-scope не ломают CI.

Основание: [PAT-TEST] прямо требует закреплять такие ограничения AST-анализом и
обходом `route.dependant`, включая пороговые resource tests.

### P2. LLM/Vision retry повторяет неретраебельные 4xx

`LlmClient` и `VisionClient` ловят общий `httpx.HTTPError` внутри retry loop;
следовательно, 400/401/403/404 повторяются так же, как timeout, 429 и 5xx. Это не
слоистая ошибка сама по себе, но она находится в уже изменяемом client seam и
увеличивает подтверждённый worst-case без пользы.

Рекомендация [PAT-CLIENT]: повторять network/timeout, 429 и 5xx; остальные 4xx
завершать сразу; ошибки content/Pydantic validation продолжать retry-ить как
отдельную категорию и логировать отдельно.

### P2. Несколько HTTP endpoints знают детали ниже своего уровня

- `api/v1/endpoints/calendar.py` импортирует `TaskPriority` из ORM-модели;
- `api/v1/endpoints/auth.py` читает settings и импортирует `to_user_schema` из реализации сервиса;
- `api/v1/endpoints/tasks.py:167-221` импортирует константу и DTO из
  service-модулей; Pydantic-разбор multipart JSON относится к transport adapter и
  может остаться здесь, а доменные file limits/normalization должны находиться в
  service/upload adapter;
- `api/v1/endpoints/task_documents.py` знает ошибки всех вложенных сервисов;
- auth/register endpoint сам оркестрирует `register` и последующий `login`.

Основная масса endpoints уже тонкая; нужен локальный рефакторинг только этих мест.

Основание: [PAT-ENDPOINT] и [PAT-ARCH]. Важно не переносить transport-валидацию
Pydantic/`UploadFile` в сервис: рекомендация касается только бизнес-правил и
неправильных импортов.

### Карта «отклонение → этап реализации»

| Отклонение | Этап | Главный проверяемый инвариант |
|---|---:|---|
| Write scope, auth/access в Depends | 2 | transport вызывает auth/access service; 48 mutation routes защищены |
| Streaming attachment | 6 | в route graph нет `get_db_session` |
| DB scope во время AI | 6 | external call начинается после закрытия read scope |
| Несогласованный AI timeout budget | 0, 1, follow-up | worst-case записан; публичный async contract меняется только отдельно |
| Global runtime/settings и client DI | 1 | один lifespan owner; сервисы получают узкие constructor dependencies |
| Неявные DB pool defaults | 1 | пять pool-параметров заданы явно и проверены |
| Optional production collaborators | 1, 5 | dependency обязательна; выключенная функция представлена явным no-op |
| Исключения client/storage/service | 3 | каждый слой преобразует только ошибки непосредственного нижнего слоя |
| Неявные commit и multi-query repositories | 4 | один statement на обычный method, `commit=False` в composite use case |
| Неатомарный task document import | 5 | один DB commit; компенсация только внешнего файла |
| MCP repository/session bypass | 8 | handler/presenter получает service/DTO, не session/ORM |
| Worker как composition root | 9 | loop получает typed dependencies через constructor |
| Оставшиеся endpoint leaks | 7 | endpoint содержит только transport logic и вызов верхнего сервиса |
| Нет architecture guards | 10 | AST, route graph и threshold tests обязательны в CI |

## 5. Целевая организация DI

### Обычный короткий HTTP request

```text
DbSessionDep
  → RepositoryDep / UnitOfWorkDep
    → ServiceDep
      → endpoint

app.state HTTP/client resources
  → ClientDep
    → ServiceDep
      → endpoint
```

Это конкретная проекция четырёх уровней из [PAT-DI] и shared client lifecycle из
[PAT-HTTP].

### Auth/access dependency

```text
Cookie/Header value
  + AuthServiceDep / AccessServiceDep
    → transport-neutral Principal / AccessGrant
      → dependency maps expected service error to HTTPException
```

`dependencies/auth.py` и `dependencies/access.py` не импортируют repositories, DB models или SQLAlchemy.

Depends-слой здесь остаётся transport adapter: разрешённый ему
service-error → `HTTPException` mapping описан в [PAT-AUTH].

### Streaming и медленные внешние операции

```text
non-yield factory dependency
  → open short DB scope
  → prepare immutable data / authorize
  → close DB scope
  → stream or call external client
  → optionally open a new short DB scope to persist result
```

Application service не должен принимать `AsyncSession` или импортировать SQLAlchemy. Если use case требует нескольких DB-фаз, передать ему абстракцию короткого scope/factory, а SQLAlchemy-реализацию собрать в DI/composition layer.

Инвариант взят из [PAT-STREAM] и [PAT-CLIENT]. Абстракция scope factory —
проектное применение: документ не предписывает имя интерфейса, но запрещает
удерживать ограниченный ресурс и скрывать его lifecycle.

Scope factory должен быть узким typed protocol (`prepare`/`persist` либо
конкретный UoW context), а не контейнером с `get_repository(name)` и не словарём
зависимостей. Иначе global service locator будет лишь заменён локальным.

### MCP и worker

FastAPI `Depends` там не нужен. Использовать ручную constructor injection в выделенных composition modules:

- `mcp_server/services.py` — единственное место MCP, где разрешены concrete repository/service constructors;
- новый `knowledge/composition.py` либо эквивалентный явно названный builder — единственное место worker, где разрешена сборка repository graph.

Presentation loop/tool handler получает сервис/use case, а не session.

Это ручной эквивалент [PAT-DI] для транспортов без FastAPI `Depends` и сохраняет
границу [PAT-ARCH].

## 6. Порядок реализации

Этапы выполнять последовательно. После каждого этапа запускать затронутые unit/API/integration tests и `ruff`; публичный контракт должен оставаться рабочим на каждом шаге.

### Этап 0. Зафиксировать safety net — ✅ выполнен

Результат: baseline `587 passed` сохранён; добавлены 46 characterization
тестов в `backend/tests/characterization/` (контракт входа, Bearer-токенов и
доступа, публичный контракт MCP, выдача файла задачи, импорт документа,
замороженный инвентарь маршрутов); decision record по timeout budget —
[docs/AI_TIMEOUT_BUDGET_DECISION.md](./docs/AI_TIMEOUT_BUDGET_DECISION.md).
Итог: `633 passed`, `ruff All checks passed`.

Нормативное основание: characterization/API tests и реальные layer tests —
[PAT-TEST].

1. Сохранить текущий baseline команд из раздела 8.
2. Добавить characterization tests для критичных контрактов до перестройки:
   - cookie login/register/logout;
   - Bearer auth и одинаковый ответ для неизвестного/expired/revoked token;
   - 404 для чужого project/task/document;
   - публичные MCP schemas и результаты read/write tools;
   - успешный и аварийный task document import;
   - выдача attachment с теми же headers и filename.
3. Зафиксировать decision record по AI timeout budget:
   - известный worst case LLM — не менее `300 × 3 + backoff` секунд;
   - nginx `/api/` сейчас имеет стандартный timeout около 60 секунд;
   - рекомендуемое целевое решение по [PAT-TIMEOUT] — отдельный async
     job/polling/realtime контракт;
   - до отдельного одобрения не менять URL/status/response schema в этом
     рефакторинге и зарегистрировать follow-up с владельцем и критерием готовности.
4. Не добавлять временные production compatibility fallbacks. Если один этап требует переходного адаптера, он должен быть локальным, обязательным и удаляться в том же этапе.

Критерий готовности: исходные 587 тестов остаются зелёными, новые
characterization tests фиксируют контракт, а не текущую внутреннюю реализацию;
timeout mismatch не остаётся без записанного решения.

### Этап 1. Ввести явные client/config dependencies — ✅ выполнен

Результат: `DBSettings` получил пять явных параметров пула, `HttpClientSettings`
и `qdrant_timeout` — явные пределы исходящих соединений; `KnowledgeRuntime` стал
контейнером, которым владеет lifespan (ленивый global и `get_knowledge_runtime()`
как локатор удалены); добавлены `dependencies/http_client.py`,
`dependencies/clients.py` и `dependencies/settings.py`; сервисы получают узкие
клиенты и значения конструктором, `get_settings()` из `services/**` убран;
`VisionClient | None` заменён на `VisionCapability` с `DisabledVisionCapability`;
`ProjectQdrantClient` принимает готовый `AsyncQdrantClient`; retry разделён на
transport / content / fail-fast; `build_mcp_app(settings=...)`; worker получает
settings и runtime аргументами.

Ресурсы попадают в `scope["state"]` из lifespan, поэтому смонтированный
MCP-транспорт видит тот же контейнер клиентов, что и HTTP-граф, — второго
набора соединений не возникает.

Итог: `791 passed`, `ruff All checks passed`.

Нормативное основание: [PAT-STRUCT], [PAT-CONFIG], [PAT-LIFESPAN], [PAT-HTTP],
[PAT-CLIENT].

Создать:

- `backend/src/dependencies/http_client.py`;
- `backend/src/dependencies/clients.py`.

Сделать следующее:

1. Добавить в `DBSettings` явные pool fields и передать их в
   `create_async_engine`: для текущего single-worker baseline — `pool_size=5`,
   `pool_max_overflow=10`, `pool_timeout=5`, `pool_pre_ping=True`,
   `pool_recycle=1800`. Рядом документировать формулу общего лимита по числу
   процессов; значения остаются env-configurable.
2. Превратить `KnowledgeRuntime` только в lifespan-owned контейнер ресурсов. Удалить lazy global `_runtime` и функции service locator после перевода всех consumers.
3. Создавать общий `httpx.AsyncClient` в `main.lifespan`, задав из Settings явные
   `httpx.Limits`, timeout и владельца закрытия. При отсутствии нагрузочных
   данных явно сохранить baseline 100 max / 20 keep-alive / 5 секунд expiry и
   задокументировать основание.
4. Создавать embedding/LLM/Qdrant/vision wrappers в lifespan и хранить container в `app.state`. Для Qdrant предпочтительно создавать готовый `AsyncQdrantClient` там же и передавать его в `ProjectQdrantClient`, чтобы создание и закрытие SDK transport имели одного видимого владельца.
5. В `dependencies/clients.py` добавить фабрики и `...Dep` aliases для каждого клиента. Фабрики только извлекают уже созданные ресурсы; они не создают новый сетевой клиент на запрос.
6. Передавать сервисам только реально используемые clients/capabilities, а не omnibus service locator:
   - analytics и WBS suggestion — LLM client;
   - task descriptions — LLM + обязательная vision capability;
   - project agent — LLM + embedding + Qdrant;
   - knowledge index — embedding + Qdrant + обязательная vision capability;
   - task document import — обязательная vision capability.
7. Не передавать `VisionClient | None`. При выключенном feature flag собирать явную `DisabledVisionCapability`/no-op реализацию того же protocol; отсутствие constructor dependency остаётся ошибкой DI. No-op обязан либо возвращать заранее оговорённый результат, либо поднимать конкретную feature-disabled domain/client error — без проверки `if client is not None` в сервисе.
8. Убрать `get_settings()` из всех сервисов. Передавать узкие значения или immutable config dataclass через constructor:
   - invite code;
   - max active API tokens;
   - semantic limit/threshold и knowledge-enabled flag;
   - extract/file context limits;
   - имя фактически используемой LLM-модели брать у injected `LlmClient` либо передавать явно.
9. Фабрики и aliases в `dependencies/services.py` располагать сразу после соответствующей фабрики, чтобы downstream factories использовали `UsersServiceDep`, `CalendarServiceDep` и т. п., а не повторяли raw `Annotated[..., Depends(...)]`.
10. `build_mcp_app` должен принимать app settings явно из `main.py`, а не вызывать `get_settings()` внутри transport module.
11. Для LLM/Vision retry отделить transport/timeout, 429, 5xx и content-validation failures; обычные 4xx завершать без повторной попытки.
12. Для каждого внешнего клиента записать формулу worst-case (`timeout × attempts + backoff`) и сверить её с фактической цепочкой timeout-ов. Этот пункт не разрешает увеличивать timeout или менять HTTP contract в обход decision record этапа 0.

Тесты этапа:

- unit tests каждой client factory через fake `app.state`;
- settings/engine test проверяет все пять явных DB pool параметров;
- startup/shutdown test: один client создаётся и закрывается ровно один раз;
- `dependency_overrides` подменяет каждый client;
- client tests подтверждают: 401/403 не retry-ятся, 429/5xx/timeout retry-ятся,
  content validation использует отдельную retry-ветку;
- unit tests сервисов создают их только с явными mocks (`AsyncMock(spec=...)`);
- AST-test запрещает `get_settings()` и `get_knowledge_runtime()` в `services/**`.

### Этап 2. Перенести auth/access в сервисный слой и включить write scope — ✅ выполнен

Результат: появились `services/access.py` с `AccessService` и `AccessGrant`,
`exceptions/access.py`, transport-neutral `Principal` в `services/auth.py`;
`AuthService` владеет разрешением принципала для обоих транспортов.
`dependencies/auth.py` и `dependencies/access.py` больше не импортируют ни
репозитории, ни модели БД — они только переводят доменную ошибку в
`HTTPException`. ORM-алиасы `AccessibleProjectDep`, `OwnedProjectDep` и
прочие удалены: эндпоинт работает с идентификатором пути.

**Закрыта дыра P0:** все **47 доменных мутаций** требуют `require_write_scope`;
4 read-only POST и 2 session-only маршрута его не имеют по явному решению.
Раньше READ-токен проходил через `CurrentUserDep` и мог вызвать любую мутацию.

MCP перешёл на тот же сервисный контракт: `mcp_server/context.py` не ловит
`HTTPException` и не собирает репозитории аутентификации сам, а `ToolContext`
несёт `Principal` вместо ORM-модели пользователя.

Итог: `882 passed`, `ruff All checks passed`.

Нормативное основание: [PAT-ARCH], [PAT-DI], специальное правило auth adapter —
[PAT-AUTH]. Полный route graph должен защищаться по [PAT-TEST].

Создать или выделить:

- transport-neutral principal DTO вне `dependencies/`;
- `services/access.py`;
- `exceptions/access.py`;
- фабрики `AuthServiceDep`/`AccessServiceDep` в `dependencies/services.py`.

Рекомендуемая форма principal: безопасные пользовательские поля (`id`, `username`, display name), scope и признак API token. Не передавать ORM `User` в endpoints/MCP.

Порядок:

1. Расширить/разделить `AuthService`, чтобы он владел:
   - разбором уже извлечённого session token или bearer secret;
   - поиском active token/user;
   - одинаковой доменной ошибкой для invalid/expired/revoked credentials;
   - best-effort обновлением `last_used_at` через явную транзакционную зависимость.
2. `dependencies/auth.py` оставить HTTP-adapter: получить cookie/header, вызвать сервис, преобразовать ожидаемую auth service error в `HTTPException`.
3. Удалить `= None` у repository/service dependencies. Обязательная зависимость должна отсутствовать только при ошибке сборки.
4. `AccessService` должен реализовать membership/owner/resource-to-project правила и бросать свои service errors.
5. `dependencies/access.py` должен только получить path id/current principal, вызвать `AccessService` и преобразовать ошибку в HTTP 404/403/500.
6. Удалить ORM return aliases `AccessibleProjectDep`, `OwnedProjectDep`, `AccessibleTaskDep` и аналогичные. Endpoint использует обычный path id; access guard не переносит persistence model вверх.
7. Для endpoints, которым нужен actor, передавать principal/user DTO либо только `actor_id`/`actor_name` в service use case.
8. Добавить `WriteScopeDep` ко всем фактическим HTTP-мутациям:
   - profile/password/avatar changes;
   - analytics report generation;
   - calendar scenario apply;
   - project/membership/stage/task/WBS/sticker mutations;
   - document/link/comment/dependency/attachment mutations;
   - task document import;
   - knowledge reindex.
9. Не требовать write scope для логически read-only POST:
   - calendar scenario preview;
   - task description rephrase;
   - WBS suggestion preview;
   - knowledge ask/search;
   - auth endpoints.
10. API-token management по-прежнему защищать `SessionUserDep`, а не bearer scope.

По текущему route inventory ожидаемая классификация такова: 57 non-GET routes,
из них 48 доменных мутаций требуют write scope; 3 auth routes, 2 session-only
token-management routes и 4 read-only POST routes составляют явные исключения.
Тест должен хранить конкретные `(method, path)` множества и падать при появлении
неклассифицированного маршрута; не использовать правило «любой POST — write».

Тесты этапа:

- unit tests `AuthService` и `AccessService` с `AsyncMock(spec=Repository)`;
- API tests mapping service errors → 401/403/404/500;
- parameterized API test: READ token получает 403 на каждом классе мутаций;
- parameterized test: READ token проходит read-only POST use cases;
- route-graph test проверяет полный allowlist/denylist и не позволяет забыть `WriteScopeDep` в новом маршруте;
- MCP auth tests используют тот же service contract и больше не ловят FastAPI `HTTPException`.

### Этап 3. Нормализовать exception boundaries

Нормативное основание: [PAT-ERROR], [PAT-ARCH] и endpoint mapping из
[PAT-ENDPOINT].

1. Ввести явные нижнеуровневые bases/types для client и storage errors. Они не наследуются от `ServiceError` и не имеют HTTP-контракта, если не выходят за свой слой.
2. AI clients преобразуют httpx/Qdrant/content errors в client-layer errors.
3. Storage implementations преобразуют filesystem errors в storage-layer errors.
4. Каждый application service ловит только перечисленные errors непосредственных dependencies и преобразует их в своё service exception.
5. Endpoints больше не ловят client/storage/repository/UoW errors.
6. `TaskDocumentImportService` всегда отдаёт собственные доменные ошибки; его endpoint не знает `DocumentsServiceError`, `DocumentLinksServiceError`, `KnowledgeProviderError` и ошибки attachment subservice.
7. Уменьшить try-блоки так, чтобы собственная доменная валидация выполнялась вне перехвата lower layer. Удалить шаблон `except OwnServiceError: raise`, где он возник только из-за слишком широкого try.
8. Не ловить общий `ApplicationError` там, где известен точный lower-layer contract. Broad catch допустим только на финальной границе worker/MCP transport с безопасным внешним сообщением.

Тесты этапа:

- для каждого нового client/storage error — unit test исходной ошибки и `raise ... from error`;
- для каждого service mapping — unit test итогового типа/status/detail;
- API tests подтверждают, что внутренние details не утекли;
- AST/import test запрещает client/storage modules импортировать `*ServiceError`.

### Этап 4. Сделать транзакционные границы явными

Нормативное основание: one-statement repository contract [PAT-REPO] и
service-owned transaction [PAT-TX]. Это два разных инварианта; один нельзя
«исправить» только добавлением `commit` flag.

1. Сначала зафиксировать integration tests для всех перечисленных в finding
   multi-query методов и 24 refresh sites; тесты должны проверять возвращаемые
   server defaults/relations, чтобы удаление `refresh()` не поменяло результат.
2. Для repository write methods, которые используются самостоятельно или как
   часть составного сценария, ввести keyword-only contract `commit: bool = True`:
   - `commit=True` — завершить самостоятельную запись;
   - `commit=False` — `flush`, финальный commit выполняет service-owner.
3. Во всех составных сервисах передавать `commit=False` явно для каждой записи и вызывать один `UnitOfWork.commit()` после бизнес-модели, activity и knowledge outbox.
4. Простые standalone use cases используют `commit=True`; выбор должен быть виден в call site. Не добавлять flag методам чтения и не протаскивать его в HTTP payload.
5. Привести к этому контракту прежде всего:
   - api_tokens;
   - users;
   - document_links;
   - knowledge_index_jobs;
   - затем остальные write repositories, уже работающие через flush.
6. Удалить дополнительные SELECT после обычных DML во всех 24 refresh sites:
   использовать `INSERT/UPDATE ... RETURNING` либо подтверждённое PostgreSQL
   eager-default поведение ORM. Не возвращать полузаполненный объект и не
   подменять проверку `refresh()` ручным присваиванием server defaults.
7. Разделить multi-operation repository methods:
   - `ProjectStickersRepository.create/update/update_position` — запись sticker,
     управление task links и повторное чтение сделать отдельными однозапросными
     repository operations; orchestration и один commit принадлежат service;
   - `TaskParticipantsRepository.replace_for_task` — delete/save-many координирует service;
   - `KnowledgeIndexJobsRepository.enqueue/enqueue_many` — отделить
     deduplication orchestration от однозапросной записи; batch не должен делать
     N последовательных `SELECT + INSERT + refresh`;
   - `KnowledgeIndexJobsRepository.claim_next_batch` — предпочтительно один PostgreSQL `UPDATE ... WHERE id IN (subquery ... FOR UPDATE SKIP LOCKED) RETURNING`; commit выполняет queue service/UoW;
   - `KnowledgeIndexJobsRepository.mark_failed` — выразить переход одним
     `UPDATE ... RETURNING` либо разделить read/decision/write в queue service с
     явной блокировкой и одной транзакцией.
8. `ProjectStagesRepository.save_many` оставить явно массовой операцией, но
   убрать per-row refresh и применять batch/RETURNING по правилу массовой вставки
   [PAT-REPO].
9. Repository по-прежнему делает rollback и преобразует SQLAlchemy/Integrity errors в свой тип при любом режиме.
10. `UnitOfWorkRepositoryError` никогда не выходит в endpoint/MCP tool как есть; service-owner преобразует его в своё service exception.

Тесты этапа:

- integration test `commit=True` делает запись видимой новой session;
- integration test `commit=False` не делает запись видимой до UoW commit;
- integration tests подтверждают, что все 24 изменённых save/update methods
  возвращают те же id/server defaults без отдельного refresh;
- rollback одного composite use case удаляет и бизнес-запись, и outbox/activity;
- concurrent queue claim не возвращает одну job двум workers;
- enqueue/enqueue_many сохраняют текущую deduplication semantics для уже
  существующего pending job и повторяющихся batch inputs; усиление гарантии для
  одновременных enqueue требует отдельного constraint/locking решения и не
  должно появиться скрыто;
- unique constraint по-прежнему преобразуется в конкретный 409-domain case.

### Этап 5. Сделать task document import одной транзакцией

Этот этап выполняется поверх единого `commit` contract.

Нормативное основание: [PAT-TX], обязательный event collaborator [PAT-EVENTS] и
границы ошибок [PAT-ERROR].

1. Добавить `UnitOfWork` в обязательные зависимости `TaskDocumentImportService`.
2. Выполнить auth/read preflight в коротком scope, закрыть его, затем выполнить
   подготовку/извлечение текста до начала write transaction и без удержания DB
   connection.
3. Внутри одного DB scope вызвать nested services с явным `commit=False`:
   - attachment metadata/file save;
   - project document save;
   - document-task link save;
   - необходимые outbox events.
4. Выполнить один финальный `UnitOfWork.commit()`.
5. При ошибке до commit сделать rollback; компенсирующе удалить только внешний файл, который БД откатить не может.
6. Удалить компенсационное удаление уже закоммиченных DB rows: после изменения они не должны коммититься промежуточно.
7. Сделать `KnowledgeEvents` обязательной no-op/configured dependency во всех мутирующих сервисах и удалить `if ... is not None`.
8. Сделать `TaskAttachmentStorage` обязательным в `ProjectsService` и `TasksService`; тесты обязаны передавать mock, а не использовать optional constructor default.

Тесты этапа:

- integration: attachment + document + link + outbox появляются одним commit;
- fail after каждого шага: в БД не остаётся ни одной промежуточной строки;
- fail commit: физический файл удаляется best-effort;
- fail cleanup: исходная service error не маскируется;
- endpoint ловит только `TaskDocumentImportError` hierarchy.

### Этап 6. Устранить удержание DB ресурсов в streaming и AI use cases

Нормативное основание: [PAT-STREAM], worst-case rule [PAT-CLIENT] и threshold
tests [PAT-TEST]. Prepare/external/persist — выбранное проектное применение.

#### Attachment download

1. Вынести auth + access + metadata resolution в non-yield preflight dependency/use case с внутренним коротким `async with session_factory()`.
2. Закрыть DB scope до создания/возврата `FileResponse`.
3. В долгоживущую фазу передавать только immutable `path`, media type, filename, disposition и headers.
4. На route не должно быть `CurrentUserDep`, `get_accessible_task`, `...RepositoryDep` или `...ServiceDep`, построенных поверх `DbSessionDep`.

#### AI HTTP/MCP scenarios

1. Для analytics, project agent, task rephrase, WBS suggestion, task document import и MCP semantic search разделить use case на фазы:
   - короткая DB-фаза собирает полностью материализованный immutable snapshot;
   - DB scope закрывается;
   - выполняется LLM/embedding/Qdrant/vision;
   - при необходимости новая короткая DB-фаза сохраняет результат с UoW.
2. Не передавать `AsyncSession` в service. Для многофазного use case передать constructor-injected abstraction/factory короткого application scope; SQLAlchemy implementation остаётся в DI/composition module.
   Factory имеет typed interface только для этого процесса и не предоставляет
   произвольный доступ ко всем repositories/services.
3. Не оставлять ORM objects, lazy relationships или expired attributes в snapshot. На границе DB-фазы преобразовать данные в dataclass/Pydantic DTO.
4. Если между snapshot и записью возможна конкуренция, проверять revision/updated_at во второй DB-фазе и поднимать существующий 409-domain conflict, а не держать транзакцию открытой.
5. Сохранить синхронные API-контракты в этой задаче согласно зафиксированной
   границе. Это осознанное временное расхождение с [PAT-TIMEOUT], а не признание
   текущего budget корректным; перевод долгих операций в job/polling выполняется
   по decision record отдельной продуктовой задачей.

Тесты этапа:

- unit scope-tracker, аналогичный существующему worker test: fake LLM/client assert, что DB scope уже inactive;
- route dependency graph attachment download не содержит `get_db_session` транзитивно;
- threshold integration test с маленьким DB pool и заблокированным fake external client: обычный DB GET продолжает отвечать;
- при отказе второй DB-фазы первая read-фаза не оставляет `idle in transaction`;
- отдельный budget test/расчёт фиксирует текущие `timeout`, attempts, backoff и
  proxy timeout и ссылается на follow-up по async contract;
- output/status codes не меняются.

### Этап 7. Очистить оставшиеся HTTP endpoints

Нормативное основание: [PAT-ENDPOINT], [PAT-ARCH] и [PAT-ERROR].

1. `auth.py`: добавить единый service use case `register_and_login`; endpoint только ставит cookie из результата. Cookie policy/settings передать явной transport dependency, убрать `get_settings()`.
2. `/auth/me`: возвращать safe principal/user schema, не импортировать mapper из реализации сервиса.
3. `calendar.py`: убрать прямой импорт ORM enum; использовать transport/domain enum, не зависящий от `db.models`.
4. `tasks.py` rephrase:
   - endpoint оставляет Pydantic-разбор JSON из multipart, bounded чтение файла,
     mapping malformed transport data в 4xx и гарантированное закрытие
     `UploadFile`;
   - лимит количества, empty/size/type business rules принадлежат сервису или
     явно выделенному upload adapter; transport при этом может читать не более
     `configured_limit + 1`, чтобы не загружать неограниченный файл в память;
   - input DTO переносится в schemas/application-contract module и не
     импортируется из service implementation.
5. `task_documents.py`: ловить только ошибку верхнего import service.
6. Проверить остальные endpoints AST-тестом: разрешены schemas, service dependency aliases, service exceptions и auth/access dependencies; запрещены repositories, SQLAlchemy, DB session/models, client implementations и прямые service constructors.

Тесты этапа:

- API tests всех изменённых endpoints через `dependency_overrides` соответствующей service factory;
- malformed multipart JSON/file cases сохраняют текущие 4xx;
- registration вызывает один публичный service use case;
- AST boundary test проходит для всех 22 endpoint-модулей.

### Этап 8. Перевести MCP на application services

Нормативное основание: транспортная граница [PAT-ARCH], constructor-injected
use cases [PAT-SERVICE] и архитектурные guards [PAT-TEST].

1. Оставить `mcp_server/services.py` явным manual composition root и запретить repository constructors в остальных MCP-модулях.
2. Его builders получают typed config, client capabilities и short-scope factory
   явно из `build_mcp_app`/main composition; не вызывают
   `get_knowledge_runtime()` и не скрывают глобальную session factory.
3. `ToolContext` больше не содержит и не публикует `AsyncSession`; он содержит transport-neutral principal и готовые application services/use-case facade.
4. `mcp_server/context.py` не импортирует FastAPI `HTTPException`, `get_principal`, DB models, session factory или repositories. Он вызывает общий auth/access service contract и преобразует service errors в `ToolError`.
5. Read tools сопоставить существующим use cases:
   - projects — `ProjectsService`/project overview use case;
   - tasks/search — `TasksService` и `ProjectStagesService` либо transport-neutral project query service;
   - comments — `TaskCommentsService`;
   - calendar — `CalendarService`;
   - milestones — `MilestonesService`;
   - semantic search — отдельный `KnowledgeSearchService` с injected embedding/Qdrant clients.
6. Если один tool требует агрегации нескольких сервисов, создать transport-neutral process service, а не переносить orchestration обратно в handler.
7. Write tools продолжают использовать Tasks/Comments/Milestones services; `_project_stages` и `_project_member_user_id` перенести в соответствующие service use cases.
8. `presenters.py` принимать schemas/DTO, а не SQLAlchemy models.
9. Внешний semantic call выполнять после закрытия auth/access DB scope.
10. Сохранить tool names, descriptions, input schema и внешний JSON без изменений.

Тесты этапа:

- текущие `tests/unit/mcp_server/**` переписать на service doubles с `spec`;
- contract test публичного списка tools и JSON schema;
- AST test запрещает `src.repositories`, `src.db` и `sqlalchemy` в `context.py`, `server.py`, `write_tools.py`, `presenters.py`;
- semantic client test подтверждает закрытый DB scope;
- одинаковые auth/access scenarios дают эквивалентный результат HTTP и MCP.

### Этап 9. Инъецировать зависимости knowledge worker

Нормативное основание: [PAT-SERVICE], [PAT-DI], [PAT-LIFESPAN] и resource budget
[PAT-CLIENT].

1. Выделить `KnowledgeWorker` или эквивалентный объект с constructor dependencies:
   - immutable worker config;
   - short DB/application scope factory;
   - queue service;
   - knowledge index service factory;
   - explicit client bundle/capabilities.
2. `run()`/worker loop не вызывает `get_settings`, `get_knowledge_runtime` и global `async_session_factory`.
3. `_maintain_queue`, claim и persist status выполнять через `KnowledgeQueueService`, а не repository из loop.
4. Concrete repositories и `KnowledgeIndexService` собирать только в `knowledge/composition.py` (или одном эквивалентном builder module), вызываемом из lifespan.
5. `main.lifespan` создаёт worker с явными зависимостями, запускает task и гарантированно завершает task/resources в обратном порядке.
6. Сохранить текущие важные инварианты:
   - claim/persist используют короткие сессии;
   - embedding/Qdrant выполняются без активной DB-сессии;
   - cancellation не превращается в failed job;
   - task batch по-прежнему делится при частичном отказе;
   - delayed payload-index backfill повторяется.

Тесты этапа:

- worker tests передают fakes через constructor, без monkeypatch module globals;
- existing session-lifetime tests остаются;
- lifecycle test проверяет cancellation и закрытие clients/engine;
- integration tests очереди проверяют retry/status transitions и concurrent claim.

### Этап 10. Закрепить архитектуру тестами

Нормативное основание: [PAT-TEST] прямо требует AST, dependency-graph и threshold
guards; repository-specific ограничения следуют из [PAT-REPO].

Создать `backend/tests/architecture/` минимум с четырьмя файлами.

`test_layer_boundaries.py` через `ast` проверяет:

- endpoints не импортируют repositories, DB, SQLAlchemy и client implementations;
- services не импортируют FastAPI, dependencies, `db.session` и SQLAlchemy;
- auth/access dependencies не импортируют repositories или DB models;
- MCP presentation и worker loop не импортируют repositories/DB session;
- concrete repository/service/client constructors разрешены только в перечисленных composition modules;
- clients/storage не импортируют service-layer exceptions.

`test_dependency_contracts.py` проверяет:

- `get_knowledge_runtime()` удалён; `get_settings()` запрещён в
  services/endpoints/MCP/worker loop и разрешён только в явном bootstrap/DI
  allowlist (`main.py`, dependency factories и другие заранее перечисленные
  composition entry points);
- конкретный перечень обязательных constructor dependencies не имеет default
  `None`; не запрещать все optional domain-аргументы по одному синтаксическому
  признаку;
- для каждой публичной dependency factory есть `...Dep` alias;
- downstream factories используют aliases, а не дублируют raw `Depends`.

`test_repository_contracts.py` проверяет:

- в публичных write methods нет `session.refresh()` после DML;
- обычный публичный метод не содержит несколько `session.execute/scalar/get` и не
  вызывает другой публичный query method того же repository;
- разрешённые batch methods перечислены явно и не делают per-row refresh;
- методы, участвующие в составных сценариях, имеют keyword-only `commit` и их
  service call sites явно передают `commit=False`.

AST-проверка здесь является guard от возврата уже найденных форм нарушения, а не
доказательством количества SQL на все возможные конструкции SQLAlchemy. Реальное
поведение `RETURNING`, visibility и rollback подтверждают integration tests на
PostgreSQL.

`test_route_dependency_graph.py` проверяет собранное приложение:

- attachment streaming route транзитивно не зависит от `get_db_session`;
- множества mutation/read-only/public/session-only routes полностью покрывают
  все 57 текущих non-GET routes; новая неклассифицированная route ломает тест;
- каждая mutation route содержит `require_write_scope`, public/session-only
  routes имеют свой guard;
- read-only POST routes не требуют write scope;
- WebSocket routes обходятся отдельно;
- streaming routes входят в явный registry/marker и не получают yield dependency
  с ограниченным ресурсом. Не пытаться угадывать runtime `FileResponse` только
  по декоратору FastAPI: такой тест даст ложную гарантию.

Тесты должны сообщать точный файл/route/import, а не только `assert False`.

## 7. Матрица обязательных регрессионных тестов

| Область | Unit | API/contract | Integration/resource |
|---|---|---|---|
| Auth/access | service errors, principal, roles/scopes | 401/403/404, READ vs WRITE | token `last_used`, rollback |
| Client DI | retry/error mapping, explicit config, worst-case formula | dependency override | lifespan create/close |
| DB pool | settings validation | — | explicit limits + threshold exhaustion behavior |
| Repositories | one-statement guards, no post-DML refresh | — | RETURNING/defaults/visibility on PostgreSQL |
| Transactions | service calls `commit=False`, один UoW | прежние HTTP ответы | visibility/rollback/concurrency |
| Task document import | orchestration and compensation | один верхний error contract | atomic rows + outbox + file cleanup |
| Streaming download | prepared immutable result | headers/body/404 | DB scope closed during stream |
| AI scenarios | snapshot/external/persist phases, budget calculation | прежние schemas/status | pool remains available |
| MCP | handlers call services | tool schema/output unchanged | DB scope closed before external call |
| Worker | injected loop, cancellation | — | claim/retry/status and no held session |
| Architecture | AST rules | route graph | threshold pool test |

Для новых mocks обязательно использовать `spec=`. Repository correctness проверять на testcontainers PostgreSQL, а не на mock `AsyncSession` и не на SQLite — это прямые рекомендации [PAT-TEST].

## 8. Команды проверки

Из каталога `backend` в PowerShell:

```powershell
.\venv\Scripts\ruff.exe check src tests
.\venv\Scripts\python.exe -m pytest tests/architecture -q
.\venv\Scripts\python.exe -m pytest tests/unit -q
.\venv\Scripts\python.exe -m pytest tests/api -q
.\venv\Scripts\python.exe -m pytest tests/integration -q
.\venv\Scripts\python.exe -m pytest -q
```

Перед integration/resource tests убедиться, что Docker доступен. Не считать локальный `skip` testcontainers успешной проверкой интеграционного этапа; в CI Docker failure должен падать.

После рефакторинга дополнительно проверить приложение через compose:

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 200 backend
```

Smoke scenarios:

1. cookie login → GET project/task → logout;
2. READ API token читает проект и получает 403 на мутации;
3. WRITE API token выполняет разрешённую мутацию;
4. attachment download продолжается, параллельный DB GET отвечает;
5. blocked fake/controlled AI request не исчерпывает DB pool;
6. MCP list/get/search и одна write-команда сохраняют прежний формат;
7. worker обрабатывает job и корректно завершается при shutdown.

## 9. Definition of Done

Рефакторинг завершён только если одновременно выполнено всё ниже:

- [ ] Все существующие публичные HTTP и MCP contracts сохранены.
- [ ] READ token не может выполнить ни одну доменную HTTP-мутацию.
- [ ] `dependencies/auth.py` и `dependencies/access.py` не содержат business DB access.
- [ ] Ни один endpoint/MCP handler/worker loop не создаёт repository напрямую.
- [ ] Ни один service не вызывает `get_settings()` или `get_knowledge_runtime()`.
- [ ] Все production dependencies сервисов обязательны; no-op поведение оформлено явным объектом, а не `None`.
- [ ] HTTP/client resources создаются и закрываются lifespan-владельцем ровно один раз.
- [ ] DB engine получает явные pool size/overflow/timeout/pre-ping/recycle из
  `DBSettings`; формула общего числа соединений задокументирована.
- [ ] Streaming attachment route не имеет DB session в dependency graph.
- [ ] Внешний AI call выполняется без checked-out DB connection.
- [ ] Worst-case всех AI clients рассчитан; несоответствие `/api` timeout budget
  связано с отдельной одобренной async-contract задачей и не замаскировано
  увеличением timeout.
- [ ] Обычные публичные repository write methods выполняют один SQL statement;
  24 post-DML refresh sites устранены, batch-исключения перечислены явно.
- [ ] Каждый составной DB-факт имеет один service-owned commit.
- [ ] Task document import атомарен для всех DB rows/outbox, внешний файл компенсируется.
- [ ] MCP presentation зависит только от application services/DTO.
- [ ] Worker получает config/scopes/services/clients через constructor injection.
- [ ] Client/storage/repository/service errors принадлежат своим слоям и преобразуются на границах.
- [ ] Архитектурные AST и route-graph tests добавлены и проходят.
- [ ] Полный `pytest` и `ruff` проходят; integration tests реально запущены на PostgreSQL.
- [ ] В diff нет изменений frontend, исторических migrations и несвязанных файлов.

## 10. Рекомендации агенту-исполнителю

- При расхождении плана и `FASTAPI_PATTERNS.md` нормативный документ имеет
  приоритет; проектные применения можно заменить только эквивалентным решением с
  тем же тестируемым инвариантом.
- Не делать механический rewrite всех 30 тысяч строк. Менять только перечисленные seams и их callers/tests.
- Сначала добавлять контракт/тест границы, затем переносить реализацию.
- Не оставлять два параллельных DI-пути после завершения этапа.
- Не сохранять старый global runtime как «временный fallback».
- Не ослаблять `spec` у mocks ради упрощения обновления тестов.
- Не смешивать архитектурный рефакторинг с форматированием всего проекта.
- Перед правкой проверять dirty worktree и не включать чужие изменения в коммит.

[PAT-ARCH]: ./FASTAPI_PATTERNS.md#1-слоистая-архитектура
[PAT-STRUCT]: ./FASTAPI_PATTERNS.md#2-структура-проекта
[PAT-CONFIG]: ./FASTAPI_PATTERNS.md#3-конфигурация-coresettingspy
[PAT-LIFESPAN]: ./FASTAPI_PATTERNS.md#5-точка-входа-mainpy-и-lifespan
[PAT-DI]: ./FASTAPI_PATTERNS.md#6-dependency-injection
[PAT-AUTH]: ./FASTAPI_PATTERNS.md#авторизация-как-depends-зависимость
[PAT-HTTP]: ./FASTAPI_PATTERNS.md#жизненный-цикл-http-клиента-для-внешних-api
[PAT-STREAM]: ./FASTAPI_PATTERNS.md#долгоживущие-соединения-websocket-sse-streaming
[PAT-ENDPOINT]: ./FASTAPI_PATTERNS.md#7-эндпоинты-apiv1endpointspy
[PAT-ERROR]: ./FASTAPI_PATTERNS.md#8-исключения-трёхслойная-система
[PAT-SERVICE]: ./FASTAPI_PATTERNS.md#9-сервисный-слой
[PAT-REPO]: ./FASTAPI_PATTERNS.md#10-репозитории
[PAT-TX]: ./FASTAPI_PATTERNS.md#транзакционная-граница-составного-use-case
[PAT-EVENTS]: ./FASTAPI_PATTERNS.md#журнал-кейса-case_events
[PAT-CLIENT]: ./FASTAPI_PATTERNS.md#13-клиенты-внешних-apillm
[PAT-MIGRATION]: ./FASTAPI_PATTERNS.md#15-миграции-alembic
[PAT-TIMEOUT]: ./FASTAPI_PATTERNS.md#16-инфраструктура-и-запуск
[PAT-TEST]: ./FASTAPI_PATTERNS.md#18-тестирование
