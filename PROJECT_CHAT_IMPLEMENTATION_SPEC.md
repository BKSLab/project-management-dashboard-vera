# Техническое задание: Project Chat

## 1. Концепция

Добавить в каждый Project один встроенный командный чат. Ключевой
принцип: **1 Project = 1 Project Chat**.

Project Chat --- часть Project Workspace. Task Comments остаются
обсуждением конкретной задачи; Project Chat предназначен для общего
разговора команды.

Первая версия: realtime messages, полная история, replies, цитирование,
@mentions, reactions, файлы, read/unread, typing, online presence,
edit/delete, поиск, Entity Cards и Project Agent как специальный actor.

Не реализовывать channels, личные сообщения и отдельные Task chats.

## 2. Lifecycle и membership

Chat создаётся автоматически при создании Project. Project и ProjectChat
желательно создавать одной бизнес-операцией/транзакцией.

Все участники Project автоматически являются участниками Chat. **Project
membership --- source of truth.** Отдельное управление chat members не
требуется.

При добавлении участника в Project он автоматически получает Chat и
видит **всю историю с первого сообщения**, независимо от даты
вступления.

При удалении из Project пользователь немедленно теряет HTTP/WS-доступ.
Активное socket-соединение должно быть закрыто/деавторизовано.

Чтобы новый участник не получил тысячи historical unread, при вступлении
можно установить initial read boundary на последнее существующее
сообщение. Полная старая история остаётся доступной.

## 3. UI

Вкладка:
`Обзор · Канбан · Задачи · Календарь · Структура · Риски · Доска · Чат · Документы · AI-вики`.

Route: `/projects/:projectKey/chat`.

В навигации показывать realtime unread badge: `Чат 7`.

## 4. Realtime architecture

PostgreSQL --- source of truth persistent data. Redis --- ephemeral
realtime coordination. WebSocket --- realtime transport.

``` text
Browser
  │ WebSocket
  ↓
WS Handler
  ├─ Redis Pub/Sub → other app instances
  ├─ Redis presence / typing
  └─ ChatService
       ↓
     short DB session
       ↓
     COMMIT
       ↓
     release connection
```

**WebSocket никогда не удерживает PostgreSQL session/connection всё
время жизни socket.**

Каждая persistent операция открывает короткую DB session, выполняет
service operation, commit/rollback и возвращает connection в pool.
Presence и typing не пишутся в PostgreSQL на каждый event.

## 5. Никакого polling

Не использовать периодический GET сообщений. WebSocket + Redis ---
основной realtime-контур.

HTTP используется для initial history, cursor pagination, search,
uploads и reconnect/resync.

## 6. Horizontal scaling и Redis

Backend поддерживает несколько instances. Каждый instance держит только
local sockets; fan-out выполняется через Redis.

Namespace: `project_chat:{project_id}`.

Events: `message.created`, `message.updated`, `message.deleted`,
`reaction.updated`, `read.updated`, `typing.started`, `typing.stopped`,
`presence.updated`, `agent.activity`.

Redis не является persistent message store.

## 7. Reconnect, auth, heartbeat

WebSocket delivery не считается гарантированной историей. Клиент хранит
`last_known_message_id`/cursor. После reconnect выполняет HTTP resync и
продолжает realtime.

WebSocket использует существующую authentication model и обязательно
проверяет Project membership.

Реализовать heartbeat/ping-pong для dead connections, освобождения
ресурсов и presence TTL.

## 8. Persistent model

Минимальные сущности: `ProjectChat`, `ChatMessage`, `ChatMessageEntity`,
`ChatAttachment`, `ChatReaction`, `ChatReadState`, `ChatMessageMention`.

Отдельный `ProjectChatMember` нужен только при архитектурной
необходимости; Project membership остаётся source of truth.

### ProjectChat

``` text
id
project_id UNIQUE NOT NULL
created_at
updated_at
```

### ChatMessage

``` text
id
chat_id
project_id
author_type
author_user_id nullable
author_agent_id nullable
content
reply_to_message_id nullable
client_message_id
created_at
updated_at
edited_at nullable
deleted_at nullable
```

Author types: `USER`, `AGENT`, `SYSTEM`.

Content --- plain text либо безопасный ограниченный Markdown.
Произвольный HTML запрещён. Порядок сообщений определяет
server-generated sortable ID/sequence, не client timestamp.

## 9. Replies, quotes, mentions, reactions

Reply ссылается на сообщение того же Chat. Если source удалён, preview
показывает `Сообщение удалено`.

Quote --- отдельный механизм выбранного текста; для MVP допустим
безопасный Markdown/text. Reply, Quote и Entity Reference не смешивать.

Поддержать `@user`. Composer предлагает только участников текущего
Project. Mention хранить структурированно, а не восстанавливать regex
после отправки.

Минимальные reactions: `👍 ❤️ 👀 ✅ 🎉`. Unique
`(message_id, user_id, reaction)`.

## 10. Файлы

Binary не хранить в PostgreSQL. Переиспользовать существующий
storage/File abstraction.

ChatAttachment: id, message_id, storage_key/file_id, original_name,
content_type, size_bytes, created_at.

UI: image → thumbnail/preview/download; document → icon/name/size;
unknown → attachment row/download.

Обязательны server-side size limit, content-type validation, безопасное
имя и Project access. Не выдавать permanent public URL при защищённом
storage.

## 11. Entity References

Сообщение поддерживает структурированные ссылки на сущности текущего
Project: `TASK`, `DOCUMENT`, `RISK`, `MILESTONE`, `WBS_NODE`.

ChatMessageEntity: id, message_id, entity_type, entity_id, position,
created_at.

Backend проверяет существование, принадлежность Project и access.

Persistence хранит `entity_type + entity_id`, а не snapshot
title/status. Read model hydrates актуальный preview. Если Task стала
DONE, старая карточка показывает DONE. Если сущность удалена ---
`Объект больше недоступен`.

Пример Task Card:

``` text
┌───────────────────────────────────────┐
│ TASK-142                  IN PROGRESS │
│ Реализовать авторизацию               │
│ HIGH · Иван · 24 Sep                  │
└───────────────────────────────────────┘
```

Переходы: TASK → Task Drawer; RISK → Risk Drawer; DOCUMENT → Document;
MILESTONE → Calendar focus; WBS_NODE → Structure focus.

## 12. Entity picker и Agent

Trigger `#` открывает поиск по сущностям Project. После выбора в
composer появляется structured chip. Внутренний URL приложения также
можно преобразовывать в Entity Reference.

Project Agent использует тот же message contract и тот же EntityCard
registry, что USER.

Пример Agent payload: `content + entities:[{type:"TASK", id:142}]`.

**Человек и Agent говорят на одном UI-языке Project.**

## 13. Read state и unread

Не создавать `message × user` запись для каждого просмотра.

ChatReadState: chat_id, user_id, last_read_message_id, updated_at.
Unique `(chat_id, user_id)`.

Из этого рассчитываются unread count и unread divider. Read update
отправлять при фактическом просмотре новых сообщений с
debounce/throttle.

Полную историю individual viewers не создавать без отдельной продуктовой
необходимости.

## 14. Typing и presence

Typing --- ephemeral Redis state с коротким TTL:
`typing:{project_id}:{user_id}`. Events: `typing.started`,
`typing.stopped`. Не писать в PostgreSQL и не отправлять event на каждый
keypress.

Presence --- Redis + TTL. Первая версия: `online/offline`. Обновление:
WS connect / heartbeat / disconnect / TTL.

## 15. Edit/Delete

Пользователь редактирует только собственные сообщения согласно
permissions.

Edit устанавливает `edited_at`, пересобирает mentions/entities и
рассылает `message.updated`.

Delete --- soft через `deleted_at`; UI показывает `Сообщение удалено`.
Replies сохраняют целостность. Attachments/entity cards удалённого
сообщения скрываются.

## 16. Pagination, search, notifications

При входе загружаются последние N сообщений. Scroll вверх → older
messages. Использовать cursor/keyset pagination вместо глубокого OFFSET.
Scroll anchor не должен прыгать.

Предусмотреть PostgreSQL FTS по сообщениям текущего Project. Результат
позволяет перейти к сообщению и загрузить surrounding context.

Realtime notifications: новое сообщение, когда Chat не в фокусе;
@mention; reply; Agent message/mention по сценарию. Unread badge
обновляется realtime. Browser push/email не входят в базовый scope.

## 17. Send flow и DB connections

``` text
WS message.send
↓
validate actor + Project membership
↓
open short DB session
↓
ChatService.create_message
↓
validate reply / mentions / entities / attachments
↓
persist
↓
COMMIT
↓
release DB connection
↓
publish message.created to Redis
↓
instances receive
↓
fan-out to local project sockets
```

Realtime event публикуется **после успешного commit**.

Если проект уже использует transactional outbox для durable domain
events, его можно переиспользовать там, где это оправдано.
Typing/presence через outbox не проводить.

## 18. Idempotency и backpressure

Frontend отправляет `client_message_id` UUID. Backend предотвращает
duplicate message при retry/reconnect. Scope: author + chat +
client_message_id либо эквивалент.

Ограничить длину content, число mentions/entity refs/attachments, размер
файла, send rate и typing rate.

Для socket использовать bounded outbound queue/разумный disconnect
медленного клиента, а не бесконечное накопление сообщений в памяти.

## 19. WebSocket handler и protocol

WS handler --- тонкий transport layer. Он не содержит SQL, entity
hydration business logic или permission rules.

Он валидирует envelope, вызывает service, отправляет ack/error,
поддерживает connection и маршрутизирует normalized events.

Client event содержит `type`, `request_id`, `client_message_id`,
content, reply, mentions, entities и attachment_ids.

Server ack возвращает client_message_id и persistent message_id.
Broadcast возвращает normalized message read model.

## 20. HTTP/WS API

HTTP:

``` text
GET  /api/v1/projects/{project_id}/chat
GET  /api/v1/projects/{project_id}/chat/messages?before=...&limit=...
GET  /api/v1/projects/{project_id}/chat/messages?after=...
GET  /api/v1/projects/{project_id}/chat/search?q=...
POST /api/v1/projects/{project_id}/chat/attachments
```

WebSocket:

``` text
/api/v1/projects/{project_id}/chat/ws
```

REST и WS write paths должны вызывать один ChatService, а не иметь две
реализации бизнес-логики.

## 21. Frontend architecture

Рекомендуемые компоненты: ProjectChatPage, ChatHeader, ChatMessageList,
ChatMessage, ChatComposer, ChatReplyPreview, ChatQuote,
ChatMentionPicker, ChatEntityPicker, EntityCard, ChatAttachment,
ChatReactionBar, ChatTypingIndicator, ChatUnreadDivider,
ChatConnectionState.

TanStack Query: initial history, pagination, search, upload metadata.

WebSocket layer: live events, reconnect, heartbeat, resync.

Local/Zustand: reply target, quote draft, composer, connection status,
picker UI.

Не хранить полную историю в нескольких независимых stores.

## 22. Message list performance

Архитектура должна позволять виртуализацию большой истории.

Корректно сохранять scroll anchor при prepend, новых сообщениях и
изменении высоты attachments/entity cards.

Не автоскроллить вниз, если пользователь читает старую историю.
Показывать `Новые сообщения ↓`.

Optimistic send показывает `sending/sent/failed`. При failure текст не
исчезает; доступен Retry с тем же client_message_id.

## 23. Agent architecture

Project Agent --- специальный actor в том же Chat, но его бизнес-логика
не находится в WebSocket handler.

Базовый Chat предоставляет author_type=AGENT, delivery, Entity Cards и
realtime events.

Правила вызова Agent, tools, permissions и human-in-the-loop описываются
отдельным Agent spec.

## 24. Project Knowledge

Chat в будущем является источником Project Knowledge, но отправка
сообщения **не блокируется embeddings/Qdrant**.

Не индексировать каждое `ок`, `спасибо`, `понял` синхронно. Knowledge
pipeline --- асинхронный. Позднее использовать conversation chunks и/или
extraction значимых решений, рисков и договорённостей.

PostgreSQL остаётся source of truth.

## 25. Дизайн

Следовать DESIGN_REFINEMENT_APPLE_IVE_GUIDE.md.

Не копировать Telegram/Slack bubbles. Целевой стиль --- спокойная
business/developer conversation feed на matte/mineral background.

Composer снизу --- floating glass/metal surface. Agent отличается
небольшим AI marker/blue-violet accent. Entity Cards --- компактные
matte interactive surfaces.

## 26. Accessibility

Обязательно: keyboard navigation, focus-visible, semantic buttons,
aria-label icon actions, accessible composer, reply/entity/reaction
доступны без hover, typing/presence не создают шум screen reader,
умеренный aria-live для новых сообщений, reduced motion.

## 27. Backend layers

Следовать FASTAPI_PATTERNS.md:

``` text
HTTP / WS transport
       ↓
ChatService
       ↓
ChatRepository
       ↓
PostgreSQL

ChatService
       ↓
RealtimePublisher
       ↓
Redis
```

Redis/storage/DB clients управляются через существующий lifespan/DI
pattern.

Рассмотреть индексы: chat_messages(chat_id,id),
chat_messages(project_id,id), unique chat_read_states(chat_id,user_id),
индексы foreign keys и FTS index.

## 28. Tests

Backend: - Chat автоматически создаётся с Project; - участник получает
доступ; - новый участник видит всю историю; - removed member теряет
HTTP/WS access; - send/edit/delete/reply; - mentions; - entity
cross-project rejection; - attachment access; - idempotent retry; - read
state; - cursor pagination; - reconnect resync; - repository tests на
реальном PostgreSQL; - DB connection не удерживается lifecycle socket.

Frontend: - initial history; - older pagination/scroll anchor; -
optimistic send/ack/failure/retry; - reconnect/resync; - unread; -
reply/quote; - mention/entity picker; - cards; - attachments; -
typing/presence; - edit/delete; - search jump; - keyboard/accessibility.

Load/integration: - множество idle sockets не исчерпывают DB pool; -
fan-out через несколько app instances; - burst сообщений; - reconnect
storm; - slow client/backpressure; - Redis temporary failure; -
PostgreSQL pool metrics.

## 29. Observability

Метрики: active WebSockets, connections per instance,
connect/disconnect/reconnect rate, messages/sec, Redis publish/fan-out
latency, DB message-write latency, DB pool used/free/wait, outbound
queue size/drops, failed sends, attachment errors.

Structured logs включают project_id, chat_id, actor id, event type,
request/client_message_id и duration, но не логируют полный приватный
текст сообщения без необходимости.

## 30. Порядок реализации

1.  ProjectChat lifecycle + migration.
2.  Message/reply/read/reaction/entity/attachment models.
3.  Repositories/services + tests.
4.  HTTP history/pagination/search.
5.  WebSocket transport без долгоживущих DB sessions.
6.  Redis fan-out + multi-instance design.
7.  reconnect/resync/idempotency.
8.  typing/presence.
9.  frontend message list/composer.
10. replies/quotes/mentions/reactions.
11. files.
12. Entity Cards + entity picker.
13. unread/notifications.
14. Agent actor support.
15. design/accessibility.
16. load/regression tests + observability.

## 31. Acceptance Criteria

1.  Project автоматически получает ровно один Chat.
2.  Все Project members автоматически имеют доступ.
3.  Новый member видит всю историю.
4.  Removed member теряет доступ, включая active WS.
5.  Idle WebSockets не занимают DB connections.
6.  Realtime работает через WebSocket + Redis без polling.
7.  Несколько backend instances корректно fan-out события.
8.  Reconnect не теряет сообщения.
9.  Retry не создаёт duplicate messages.
10. Replies, quotes, mentions, reactions работают.
11. Файлы безопасно отображаются/скачиваются.
12. Read/unread работает без таблицы message×user.
13. Typing/presence не нагружают PostgreSQL.
14. Entity references проверяются по Project и отображаются актуальными
    Cards.
15. USER и AGENT используют один Entity Card contract.
16. Большая история загружается cursor pagination.
17. UI соответствует общей design system и доступен с клавиатуры.
18. Chat не превращается в отдельный Slack внутри продукта.

## 32. Целевой результат

Project Chat должен быть естественным коммуникационным слоем Project.

Главный технический принцип:

> WebSocket держит realtime connection, Redis координирует realtime,
> PostgreSQL хранит факты, а DB connection существует только на время
> конкретной persistent операции.
