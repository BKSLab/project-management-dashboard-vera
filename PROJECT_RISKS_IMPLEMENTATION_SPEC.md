# Техническое задание: модуль рисков Project Task Tracker

## 1. Цель

Добавить в каждый Project компактный модуль управления рисками. Риски
становятся самостоятельным PM-доменом и участвуют в аналитике проекта,
Project Pulse, Task context, а в дальнейшем --- Project Health, MCP и
Project Agent.

Ключевые правила:

-   каждый Risk обязательно принадлежит Project;
-   Risk может опционально ссылаться на одну Task того же Project;
-   Risk не является Task и не использует Kanban workflow;
-   оценка риска рассчитывается backend;
-   модуль остаётся простым Risk Register, а не enterprise
    risk-management системой.

## 2. UI и навигация

Добавить вкладку:

``` text
Обзор · Канбан · Задачи · Календарь · Структура · Риски · Доска · Документы · AI-вики
```

Route:

``` text
/projects/:projectKey/risks
```

Глобальный независимый раздел рисков на первом этапе не нужен.

## 3. Модель данных

``` text
ProjectRisk
- id
- project_id                 FK, NOT NULL
- task_id                    FK, nullable
- title
- description
- probability
- impact
- risk_level                 derived
- status
- response_strategy
- mitigation_plan
- response_plan
- owner_user_id              FK, nullable
- review_date                date, nullable
- source
- created_at
- updated_at
```

Связи:

``` text
Project 1 ─── N ProjectRisk
Task    1 ─── 0..N ProjectRisk
```

Каждый конкретный Risk имеет максимум одну `task_id`. M:N на первой
версии не вводить. При удалении Task Risk не удаляется: `task_id`
становится `NULL`.

## 4. Основные поля

`title` --- обязательное краткое название потенциального события.

`description` --- описание того, что может произойти, почему и чем это
угрожает проекту. Если проект уже использует Markdown для подобных
полей, сохранить этот подход.

### Probability

``` text
LOW
MEDIUM
HIGH
```

UI: Низкая / Средняя / Высокая.

Не использовать псевдоточность вида 73%.

### Impact

``` text
LOW
MEDIUM
HIGH
```

UI: Низкое / Среднее / Высокое.

### Risk Level

Пользователь не вводит `risk_level`. Backend рассчитывает его:

  Probability  Impact   LOW      MEDIUM   HIGH
  --------------------- -------- -------- --------
  HIGH                  MEDIUM   HIGH     HIGH
  MEDIUM                LOW      MEDIUM   HIGH
  LOW                   LOW      LOW      MEDIUM

Первая версия использует `LOW / MEDIUM / HIGH`. Backend --- источник
истины.

## 5. Статус

Минимальный lifecycle:

``` text
OPEN
MITIGATING
OCCURRED
CLOSED
```

-   OPEN --- выявлен и актуален.
-   MITIGATING --- выполняются меры снижения.
-   OCCURRED --- рисковое событие реализовалось.
-   CLOSED --- риск больше не актуален.

`OCCURRED` нельзя смешивать с обычным `CLOSED`.

## 6. Стратегия реагирования

``` text
AVOID
MITIGATE
TRANSFER
ACCEPT
```

UI:

``` text
Избежать
Снизить
Передать
Принять
```

Avoid устраняет источник риска изменением подхода; Mitigate снижает
вероятность/влияние; Transfer передаёт последствия/ответственность;
Accept означает осознанное принятие.

## 7. План митигации

Отдельное поле:

``` text
mitigation_plan
```

Отвечает на вопрос:

> Что можно сделать заранее, чтобы снизить вероятность возникновения
> риска или уменьшить его влияние на проект?

Не объединять его с response plan.

## 8. План реагирования

``` text
response_plan
```

Отвечает на вопрос:

> Что будем делать, если риск потребует реакции или реализуется?

Разница:

``` text
Mitigation → превентивные меры.
Response   → действия при реакции/реализации события.
```

## 9. Ответственный и дата контроля

`owner_user_id` --- nullable FK на участника текущего Project. Участник
другого Project недопустим.

`review_date` --- опциональная календарная дата следующего пересмотра
риска. Это не deadline риска.

В дальнейшем review date может использоваться Calendar, Project Pulse,
notifications и Agent.

## 10. Связь с Task

`task_id` nullable.

Task picker показывает только Task текущего Project и ищет по key/title.

Backend проверяет:

``` text
risk.project_id == task.project_id
```

В Task Drawer показывать:

``` text
РИСКИ
⚠ RISK-12
Задержка интеграции CRM
HIGH
```

На Kanban Card допустим компактный индикатор `⚠ 1`.

## 11. Source

``` text
MANUAL
AI_SUGGESTED
```

AI в будущем может предложить риск, но ProjectRisk создаётся только
после подтверждения человека. Такой Risk получает
`source = AI_SUGGESTED`.

## 12. Backend architecture

Следовать `FASTAPI_PATTERNS.md`:

``` text
HTTP endpoint
      ↓
ProjectRiskService
      ↓
ProjectRiskRepository
      ↓
PostgreSQL
```

Endpoint: HTTP contract, auth/access, schemas и mapping errors.

Service: invariants, risk-level calculation, проверка Task/owner,
lifecycle и analytics integration.

Repository: CRUD, filtering, pagination и aggregates.

SQL не размещать в endpoint/service.

## 13. PostgreSQL / Alembic

Создать таблицу `project_risks`.

Рассмотреть индексы:

``` text
(project_id, status)
(project_id, risk_level)
(project_id, review_date)
task_id
```

Финальный набор выбирать по query patterns. Все изменения --- Alembic
migration.

## 14. API

Все endpoints project-scoped:

``` http
GET    /api/v1/projects/{project_id}/risks
POST   /api/v1/projects/{project_id}/risks
GET    /api/v1/projects/{project_id}/risks/{risk_id}
PATCH  /api/v1/projects/{project_id}/risks/{risk_id}
DELETE /api/v1/projects/{project_id}/risks/{risk_id}
```

Фильтры:

``` text
status
probability
impact
risk_level
owner_user_id
task_id
search
```

Использовать существующую pagination-модель.

Пример create body:

``` json
{
  "title": "Задержка интеграции CRM",
  "description": "...",
  "probability": "HIGH",
  "impact": "HIGH",
  "status": "OPEN",
  "response_strategy": "MITIGATE",
  "mitigation_plan": "...",
  "response_plan": "...",
  "owner_user_id": 15,
  "review_date": "2026-09-12",
  "task_id": 142
}
```

`risk_level` клиент не передаёт.

## 15. Risks Page

Основное представление:

``` text
┌──────────────────────────────────────────────────────────────────┐
│ Риски                                      [+ Добавить риск]     │
│ 5 активных · 2 HIGH · 1 требует контроля                        │
├───────────────────────────────────┬──────────────────────────────┤
│ РЕЕСТР РИСКОВ                    │ МАТРИЦА                      │
│                                   │                              │
│ HIGH  Задержка CRM                │        IMPACT                │
│       High × High                 │        L    M    H           │
│       Mitigating                  │ H      0    1    2           │
│                                   │ M      1    2    1           │
│ MED   Недоступность API           │ L      0    1    0           │
└───────────────────────────────────┴──────────────────────────────┘
```

На узком экране Matrix располагается ниже Register.

## 16. Risk Register

Компактная строка/карточка:

``` text
RISK-12
Задержка интеграции CRM

HIGH · High probability × High impact
MITIGATING

Owner: Иван · Review: 12 Sep
TASK-142
```

Полный description, mitigation и response plan в списке не показывать.

## 17. Risk Matrix

Интерактивная 3×3 matrix probability × impact.

В каждой ячейке --- count. Клик фильтрует Register по соответствующей
комбинации.

Состояние не передавать только цветом: использовать count, label/tooltip
и accessible name.

## 18. Modal создания риска

Кнопка `+ Добавить риск` открывает modal в существующем стиле проекта.

``` text
Новый риск

Название *
Описание *

Вероятность *
[Низкая | Средняя | Высокая]

Влияние *
[Низкое | Среднее | Высокое]

Уровень риска
HIGH
(рассчитывается автоматически)

Стратегия реагирования *
[Избежать | Снизить | Передать | Принять]

План митигации
Что можно сделать заранее, чтобы снизить вероятность или влияние?

План реагирования
Что делать, если риск потребует реакции или реализуется?

Ответственный
[Участник проекта]

Дата контроля
[Дата]

Связанная задача
[Поиск Task проекта]

[Отмена]                              [Создать риск]
```

Risk Level обновляется на frontend как preview, но окончательное
значение рассчитывает backend.

## 19. Risk Details

Для просмотра/редактирования использовать существующий Drawer pattern:

``` text
RISK-12
Задержка интеграции CRM

HIGH

STATUS
MITIGATING

ОЦЕНКА
Вероятность: High
Влияние: High

ОПИСАНИЕ
...

МИТИГАЦИЯ
...

ПЛАН РЕАГИРОВАНИЯ
...

OWNER
Иван

REVIEW
12 Sep

СВЯЗАННАЯ TASK
TASK-142
```

Отдельную страницу риска не создавать без необходимости.

## 20. Дизайн

Следовать общей design system и `DESIGN_REFINEMENT_APPLE_IVE_GUIDE.md`.

Semantic colors:

``` text
LOW     → neutral/success-muted
MEDIUM  → warning
HIGH    → danger
```

Не заливать большие карточки красным/жёлтым. Цвет используется как
indicator.

Risk Matrix может иметь очень слабые semantic surface tones.

Modal и Drawer используют существующие premium/floating surfaces.

## 21. Project Analytics

Риски обязательно включаются в аналитику:

``` text
total_risks
open_risks
mitigating_risks
occurred_risks
closed_risks
high_risks
medium_risks
low_risks
risks_without_owner
risks_without_mitigation
risks_due_for_review
risks_linked_to_tasks
ai_suggested_risks
```

Закрытые риски не считаются активными.

## 22. Project Overview

Добавить компактный summary:

``` text
РИСКИ

5 активных
2 HIGH
1 требует пересмотра

[Открыть реестр]
```

Не переносить всю Matrix на Overview.

## 23. Portfolio Dashboard

Использовать Risk как сигнал внимания:

``` text
Требуют внимания

Project Vera
2 HIGH risks
1 overdue task
```

Не превращать общий Dashboard в Risk Dashboard.

## 24. Project Pulse / Project Health

Добавить reason codes:

``` text
HIGH_OPEN_RISK
RISK_REVIEW_OVERDUE
RISK_WITHOUT_OWNER
RISK_WITHOUT_MITIGATION
RISK_OCCURRED
```

Risk Register становится одним из источников будущего Project Health.

## 25. Calendar integration

`review_date` в дальнейшем можно показывать небольшим контрольным
marker.

На первой итерации достаточно analytics/Project Pulse; не перегружать
Calendar Risk cards.

## 26. AI / Human-in-the-loop

Project Agent в будущем может сформировать Risk Suggestion на основании
задач, комментариев, документов, сроков и ИСР.

Пример:

``` text
Возможный риск

Задержка интеграции с внешним API.

Почему:
- TASK-142 переносилась дважды;
- документация поставщика не получена;
- от задачи зависит тестирование;
- milestone через 12 дней.

Probability: HIGH
Impact: HIGH
Strategy: MITIGATE

[Создать риск] [Изменить] [Отклонить]
```

AI не создаёт ProjectRisk самостоятельно.

Принцип:

> AI наблюдает и предлагает. Человек проверяет и принимает решение.

## 27. Qdrant / AI Wiki

Risk --- содержательная сущность Project и в дальнейшем индексируется в
project collection.

Semantic representation может включать title, description, mitigation
plan и response plan.

PostgreSQL остаётся source of truth для status, probability, impact,
owner и review date.

Использовать существующий Knowledge Indexing Service.

## 28. MCP

В дальнейшем добавить:

``` text
list_project_risks
get_project_risk
create_project_risk
update_project_risk
```

Write tools соблюдают существующие scopes и не обходят
ProjectRiskService.

## 29. История изменений

Если существует универсальный activity/audit pattern, использовать его.

Полезные события:

``` text
RISK_CREATED
RISK_STATUS_CHANGED
RISK_LEVEL_CHANGED
RISK_OWNER_CHANGED
RISK_REVIEW_DATE_CHANGED
RISK_TASK_LINK_CHANGED
```

Не создавать вторую audit-систему.

## 30. Backend tests

Service: - create; - project access; - все комбинации risk-level
matrix; - Task другого Project запрещена; - owner другого Project
запрещён; - probability/impact update пересчитывает level; - lifecycle
status; - удаление Task не удаляет Risk.

Repository integration: - CRUD; - filters; - pagination; - aggregates; -
FK behavior.

API: - success contracts; - 404 для чужого Project/Risk; - validation; -
filters; - create/update/delete.

Migration: - upgrade/downgrade; - constraints/indexes; - существующие
данные не затронуты.

## 31. Frontend tests

Проверить: - loading; - empty; - error; - create modal; - validation; -
risk-level preview; - Task picker; - owner picker; - Matrix filtering; -
Risk Drawer; - editing; - delete confirmation; - responsive; -
keyboard/focus.

## 32. Empty State

``` text
В проекте пока нет зарегистрированных рисков.

Зафиксируйте то, что может повлиять на сроки,
результат или выполнение проекта.

[Добавить первый риск]
```

Не создавать onboarding wizard.

## 33. Порядок реализации

### Этап 1 --- Domain

Enums, model, Alembic, repository, service, schemas, CRUD API, tests.

### Этап 2 --- Risks Page

Route/tab, register, filters, summary, empty/loading/error.

### Этап 3 --- Create/Edit UX

Modal, calculated level preview, owner/task picker, Drawer.

### Этап 4 --- Risk Matrix

3×3 matrix, counts, click-to-filter, accessibility.

### Этап 5 --- Integrations

Project Overview, Analytics, Project Pulse, Task Drawer/Kanban
indicator.

### Этап 6 --- Knowledge/AI/MCP

Только после стабильного ручного Risk workflow: Qdrant indexing, Agent
suggestions и MCP tools.

## 34. Acceptance Criteria

Модуль готов, если:

1.  Risk невозможно создать вне Project.
2.  Task-ссылка опциональна и ограничена текущим Project.
3.  Probability и Impact выбирает пользователь.
4.  Risk Level рассчитывает backend.
5.  Есть OPEN / MITIGATING / OCCURRED / CLOSED.
6.  Есть response strategy.
7.  Есть отдельные mitigation plan и response plan.
8.  Есть owner и review date.
9.  Risk создаётся через modal.
10. Risk Register и Matrix работают совместно.
11. Risk редактируется через Drawer.
12. Risk учитывается в Project Analytics.
13. HIGH risks влияют на Project Pulse.
14. Связанный Risk виден из Task.
15. UI соответствует общей дизайн-системе.
16. AI не принимает решение за пользователя.

## 35. Целевой результат

Модуль должен отвечать на три простых вопроса:

``` text
Что может помешать проекту?
Насколько это опасно?
Что мы собираемся с этим делать?
```

Risk Register не должен становиться бюрократической таблицей ради самой
таблицы.

Он должен быть связан с реальной жизнью Project: Task, сроками,
аналитикой, Project Pulse и в дальнейшем PM Copilot.

Главный продуктовый принцип остаётся неизменным:

> AI помогает заметить риск и подготовить решение. Ответственность за
> оценку, верификацию и принятие решения остаётся за человеком.
