# Decision record: timeout budget синхронных AI-эндпоинтов

Статус: **принято, follow-up открыт**
Дата: 2026-09-05
Контекст: этап 0 плана [BACKEND_LAYERED_ARCHITECTURE_REFACTOR_PLAN.md](../BACKEND_LAYERED_ARCHITECTURE_REFACTOR_PLAN.md)
Норма: [PAT-TIMEOUT] — `FASTAPI_PATTERNS.md` § 16, [PAT-CLIENT] — § 13.

## Проблема

Правило [PAT-TIMEOUT] требует, чтобы worst-case внешнего вызова помещался в
общий timeout budget цепочки `client → nginx → backend → upstream`. Текущая
цепочка этому неравенству не удовлетворяет.

## Измеренный worst case

Фактические значения на момент решения (`src/core/settings.py`):

| Параметр | Значение | Источник |
|---|---:|---|
| `llm_timeout` | 300 с | `LlmSettings.llm_timeout` |
| `llm_retries` | 3 | `LlmSettings.llm_retries` |
| `embedding_timeout` | 120 с | `EmbeddingSettings.embedding_timeout` |

Формула worst-case одного клиента — `timeout × attempts + backoff`:

- **LlmClient**: `300 × 3 = 900` с ожидания upstream плюс backoff между
  попытками. Итого **не менее 900 секунд**.
- **VisionClient**: те же `llm_timeout`/`llm_retries` → **не менее 900 секунд**.
- **EmbeddingClient**: повторов не выполняет, worst case равен одному
  `embedding_timeout` — **120 секунд**.
- **ProjectQdrantClient**: повторов не выполняет, worst case равен
  `qdrant_timeout` — **30 секунд** (значение введено явно на этапе 1;
  до этого действовал неявный SDK-умолчание).

Один HTTP-запрос к AI-эндпоинту может выполнить несколько таких вызовов
последовательно, поэтому 900 секунд — нижняя граница, а не полный бюджет
запроса.

## Фактический бюджет цепочки

- `nginx.conf`, `location /mcp` — `proxy_read_timeout 3600s`;
- `nginx.conf`, `location /api/` — отдельный timeout **не задан**, действует
  стандартный `proxy_read_timeout` ≈ **60 секунд**;
- frontend `fetch` — собственный timeout не зафиксирован.

Неравенство `worst_case_upstream ≤ backend_timeout ≤ proxy_timeout` нарушено:
`900 с > 60 с`. Практическое следствие — proxy отвечает клиенту `504`, а
backend продолжает выполнять запрос и удерживать ресурсы уже после того, как
ответ отдан.

## Решение

1. **Рекомендуемое целевое решение по [PAT-TIMEOUT]** — перевод долгих AI
   операций на отдельный асинхронный контракт: `job id` + polling либо realtime.
   Простое увеличение `proxy_read_timeout` до 900+ секунд решением **не
   считается**: оно консервирует занятый worker и соединение.

2. **Границы текущего рефакторинга.** Перевод на job/polling меняет публичный
   API (URL, status codes, response schemas) и поэтому исполнителю
   DI-рефакторинга **не разрешён**. В рамках плана URL, коды и схемы AI
   эндпоинтов остаются прежними.

3. **Что делается всё равно.** Этап 6 обязателен и выполняется независимо от
   продуктового решения: DB connection не удерживается во время внешнего
   вызова (`prepare → close scope → external call → persist`). Это устраняет
   исчерпание пула даже до миграции контракта.

4. **Выполнено на этапе 1.** Worst-case каждого клиента записан рядом с его
   конфигурацией в `src/core/settings.py` и доступен в коде как
   `LlmClient.worst_case_seconds` / `VisionClient.worst_case_seconds`
   (формула — `src/clients/retry.py:worst_case_seconds`). Retry разделён на
   три категории: транспорт/таймаут/429/5xx повторяются, обычные 4xx
   завершаются сразу, ошибки разбора ответа повторяются отдельной ветвью и
   логируются отдельно. Это убрало умножение бюджета на неретраебельных
   ошибках: раньше `401` стоил столько же, сколько три таймаута.

## Follow-up

| Поле | Значение |
|---|---|
| Задача | Перевести синхронные AI endpoints на async job/polling контракт |
| Область | `analytics`, `project_agent`, `task_descriptions`, `wbs_suggestion`, `task_documents`, MCP `search_project_knowledge` |
| Владелец | Владелец продукта (назначается при постановке задачи) |
| Критерий готовности | Ни один `/api/` route не может выполняться дольше `proxy_read_timeout`; долгая операция возвращает job id, статус читается отдельным запросом; worst-case каждого клиента ≤ backend timeout ≤ proxy timeout |
| Блокирует | Полное соответствие [PAT-TIMEOUT] |
| Не блокирует | Этапы 1–10 текущего рефакторинга |

## Осознанное расхождение

До закрытия follow-up проект сохраняет известное расхождение с [PAT-TIMEOUT].
Расхождение зафиксировано здесь намеренно: оно не считается корректным
состоянием и не маскируется увеличением timeout.
