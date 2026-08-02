# Design Guide — Дашборд «Агент Вера»

Гайдлайн по визуальному стилю дашборда. Используется как референс при разработке новых экранов/компонентов.

> Историческая справка: до этой редакции дашборд использовал тёмно-золотую тему, скопированную 1:1 с продуктового сайта `site_work_for_everyone` («Работа для всех»). Эта редакция — самостоятельный стиль именно для дашборда разработчика/PM, дальше темы независимо эволюционируют.

---

## Общая концепция

**Dark Developer Workspace.** Тёмная тема в духе VS Code / Postman / Linear — рабочий инструмент разработчика и PM, а не лендинг. Высокая плотность информации, спокойные многоуровневые тёмные поверхности, плавные переходы (Material-принцип), точечный glassmorphism только на крупных контейнерах (header, панель деталей, модалки) — не на канбан-карточках и списках, там он ухудшает читаемость.

Доступность (WCAG 2.2 AA) — обязательное требование, не опция: видимый `focus-visible` на всех интерактивных элементах, `aria-*`-атрибуты, контраст текста.

---

## Цветовая палитра

### Базовые токены

| Токен                  | HEX / значение                  | Применение |
|-------------------------|----------------------------------|------------|
| `--background`         | `#111827`                       | Фон страницы |
| `--surface`             | `#1a1f2e`                        | Фон колонок канбана, карточек документов |
| `--surface-elevated`    | `#242b3d`                        | Карточки задач, секции в панели деталей |
| `--surface-hover`       | `#2f374d`                        | Hover-состояние поверхностей |
| `--surface-active`      | `#374151`                        | Активный/выбранный элемент |
| `--border`              | `rgba(255,255,255,0.05)`         | Тонкие границы карточек |
| `--border-hover`        | `rgba(255,255,255,0.12)`         | Границы при hover |
| `--foreground`          | `#F0F0F0`                        | Основной текст |
| `--muted`                | `#9CA3AF`                        | Вторичный текст, подписи |
| `--accent`               | `#6366F1`                        | Основной акцент — сине-фиолетовый |
| `--accent-hover`         | `#7C83FF`                        | Hover на акцентных элементах |
| `--accent-foreground`    | `#FFFFFF`                        | Текст поверх акцентного фона |
| `--accent-secondary`     | `#06B6D4`                        | Бирюзовый — связи, коды ИСР, активность |
| `--warning`               | `#F59E0B`                        | Срок «скоро» |
| `--danger`                | `#EF4444`                        | Ошибки, просроченный срок |
| `--success`               | `#10B981`                        | Успех |

Никакого чистого `#000000` — он убивает объём многоуровневых поверхностей.

### Тени

```
--shadow-panel:    0 4px 20px rgba(0,0,0,0.3)                                    /* крупные панели */
--shadow-card:      0 2px 8px rgba(0,0,0,0.25)                                    /* карточка в покое */
--shadow-card-hover: 0 8px 25px rgba(0,0,0,0.35)                                  /* карточка при hover */
--shadow-selected:   0 0 0 1px rgba(99,102,241,0.7), 0 8px 30px rgba(99,102,241,0.15)  /* выбранная/подсвеченная карточка */
--shadow-dragging:   0 15px 40px rgba(0,0,0,0.45)                                 /* карточка в DragOverlay */
```

Тени обязательны — без них тёмная тема выглядит плоской. Не использовать жёсткие тени, большие размытые ореолы или яркое свечение.

### Принципы работы с цветом

- Акцент (`#6366F1`) — точечно: активный элемент, выбранная карточка, ссылки. Не красить им большие фоновые области.
- Второй акцент (`#06B6D4`, бирюзовый) — связи, коды ИСР (`wbs_code`), индикаторы активности.
- Не более 2–3 акцентных цветов одновременно — без «радуги».

---

## Типографика

**Основной шрифт:** Inter (Google Fonts `<link>` в `index.html`, т.к. в Vite SPA нет `next/font`).

**Моноширинный:** JetBrains Mono — для идентификаторов задач (`TASK-145`), кодов ИСР (`1.2.3`), дат, технических меток.

### Шкала размеров (практическая)

| Роль | Класс / размер |
|------|---------------|
| Заголовок страницы | `text-2xl font-bold` или `text-3xl font-bold` |
| Заголовок карточки/панели | `text-lg font-bold` |
| Заголовок секции | `text-sm font-semibold` |
| Заголовок задачи (карточка) | `text-[15px] font-semibold` |
| Основной текст | `text-sm` (14px) |
| Вторичный текст | `text-sm text-muted` или `text-[13px] text-muted` |
| Мелкие подписи, идентификаторы | `text-xs font-mono` |
| Заголовок колонки канбана | `text-sm font-semibold uppercase tracking-[0.1em]` |

### Принципы

- `font-semibold` — для меток, кнопок, заголовков секций.
- `font-bold` — заголовки страниц/панелей.
- Идентификаторы (`TASK-{id}`, `wbs_code`) — всегда `font-mono`.
- Длинные тексты на карточках — `line-clamp-2` (заголовок, описание), `line-clamp-1` (последний комментарий), не растягивать карточку.

---

## Интерактивные элементы

### Кнопка Primary

```
bg-accent text-accent-foreground (белый текст на сине-фиолетовом фоне)
hover:bg-accent-hover
transition-colors duration-150
rounded-md px-4 py-2 font-semibold
focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
disabled:opacity-60 disabled:cursor-not-allowed
```

### Кнопка Secondary (основная для большинства действий)

```
border border-white/10 bg-white/5 text-foreground
hover:border-white/20 hover:bg-white/10
transition-colors duration-150
rounded-md px-3 py-1.5 text-sm font-semibold
focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
disabled:opacity-60 disabled:cursor-not-allowed
```

Акцент в secondary-кнопках больше не используется (ни рамка, ни текст) — он точечный, не на каждой кнопке.

### Кнопка Neutral (выход, неважные действия)

```
bg-surface-hover text-foreground
hover:bg-surface-active
transition-colors duration-150
rounded-md px-3 py-1.5 text-sm font-medium
```

### Правила кнопок

- Всегда `focus-visible:outline-accent` — скринридеры и клавиатурная навигация.
- Никогда `outline-none` без альтернативы.
- Состояние disabled — через `opacity-60`, не через скрытие.
- Все варианты — `transition-colors duration-150` (Material-принцип плавных переходов).

---

## Поля ввода (inputs, textarea)

```
rounded border border-border bg-surface px-3 py-2
text-foreground placeholder:text-muted
focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
```

Ошибки поля — `text-sm text-danger`, с `role="alert"` и `aria-describedby`.

---

## Карточки и поверхности

### Стандартная карточка / секция

```
rounded-xl border border-white/[0.05] bg-surface-elevated p-4
```

### Карточка задачи канбана

```
rounded-xl border border-white/[0.05] bg-surface-elevated p-3
shadow-[var(--shadow-card)]
transition-[transform,box-shadow,border-color] duration-200 ease-out
hover:-translate-y-0.5 hover:border-white/10 hover:shadow-[var(--shadow-card-hover)]
```

Подсвеченная (выбранная/перешли из ИСР): `shadow-[var(--shadow-selected)] border-accent`.

### Glass-поверхности (только header, панель деталей, модалки)

```
backdrop-filter: blur(16px)   /* header — 16px */
backdrop-filter: blur(20px)   /* панель деталей, модалки — 20px */
background: rgba(36,43,61,0.65)   /* header */
background: rgba(26,31,46,0.85)   /* панель деталей */
border: 1px solid rgba(255,255,255,0.06)
```

Не использовать glass на канбан-карточках, в дереве ИСР, в списках — там он ухудшает читаемость.

### Hover на карточках

```
hover:-translate-y-0.5 hover:shadow-[var(--shadow-card-hover)] hover:border-white/10
```

---

## Канбан

### Колонка

```
rounded-2xl border border-white/[0.05] bg-surface
```

Заголовок: `IN PROGRESS · 12 задач` — `text-sm font-semibold uppercase tracking-[0.1em]`, разделитель `border-b-2` цветом стадии (`KanbanStage.color`).

Подсветка колонки-получателя при drag-over:
```
border border-accent/30 bg-accent/[0.08]
```

### Карточка задачи — структура

```
TASK-145
Настроить API обработки заявок
Краткое описание задачи в две строки...
💬 Последний комментарий (если есть)
wbs_code          дата          💬 N
```

- `TASK-{id}` — `font-mono text-xs text-muted`.
- Заголовок — `line-clamp-2 text-[15px] font-semibold`.
- Описание — только если есть, `line-clamp-2 text-[13px] text-muted`.
- Последний комментарий — только если есть, `bg-white/[0.03] rounded-lg`, `line-clamp-1`.
- Нижняя строка: код ИСР (`font-mono text-accent-secondary`), дата (цвет по сроку — см. ниже), счётчик комментариев `💬 N` (только если > 0).

Цвет даты по сроку:
- Просрочена → `text-danger`
- Осталось ≤3 дня → `text-warning`
- Иначе → `text-muted`

Приоритет задачи не используется — в проекте нет такого понятия.

### Drag & drop

При перетаскивании карточка рендерится в `DragOverlay` (`@dnd-kit/core`):
```
scale-[1.03] rotate-1
shadow-[var(--shadow-dragging)]
border border-accent/30
```
Исходная позиция карточки в колонке — `opacity-40`.

---

## Модальное окно задачи (TaskModal)

Детали задачи показываются в центральном модальном окне, а не в правом sidebar. Внешний контейнер:
```
max-width: 48rem
max-height: calc(100dvh - 2rem)
background: var(--surface) / 95%
border: 1px solid rgba(255,255,255,0.15)
border-radius: 1rem
backdrop-filter: blur(12px)
box-shadow: 0 24px 64px rgba(0,0,0,0.65)
```

Overlay использует `bg-black/75 backdrop-blur-md`. Секции внутри модального окна — карточки `rounded-xl bg-surface-elevated border border-white/[0.05] p-4`.

Вертикальная прокрутка оформляется общей утилитой `scrollbar-thin`: узкий прозрачный track и скруглённый thumb на токенах темы. Нативная светлая полоса прокрутки внутри тёмной модалки не допускается.

Комментарии — стиль чат-сообщений:
```
rounded-xl bg-white/[0.04] p-3
имя автора — text-accent-secondary font-semibold
```

Файлы показываются отдельной секцией между сроком и связанными документами. Плитка файла имеет ширину до `220px`, миниатюру безопасного растрового изображения либо цветную outline-иконку типа, обрезанное имя и размер. Плитки переносятся на новую строку и не создают горизонтальный скролл на мобильном экране. Изображение открывается в отдельном preview modal; остальные файлы скачиваются. Удаление доступно через иконочную кнопку с `aria-label` и подтверждением.

---

## Шапка (Header)

```
sticky top-0 z-40
background: rgba(36,43,61,0.65)
backdrop-blur-md backdrop-saturate-150
border-b border-white/[0.06]
```

Навигационные ссылки: `text-sm text-muted hover:text-foreground transition-colors`. Активная страница **не выделяется цветом** — только через `aria-current`, если потребуется. Это сознательное решение: остаётся принцип, по которому навигация не конкурирует за внимание с акцентными элементами контента.

---

## Дерево ИСР

- Фазы (depth 0): `text-base font-bold`, разделитель сверху `border-t border-border`.
- Разделы (depth 1): `text-sm font-semibold`.
- Листья: `text-sm` обычный вес.
- Прогресс-бар: `bg-border` дорожка, `bg-accent` заполнение.
- Бейдж роли: цвет из палитры ролей (`ROLE_COLORS` в `lib/types.ts`) — это данные домена (роли ИСР), а не токены темы, формула прозрачности (`${color}1A` фон / `${color}4D` рамка) применяется к любому HEX.
- Бейдж стадии канбана на листе: цвет из `STAGE_COLORS` — аналогично, данные домена, не тема.

## Интерактивная карта ИСР

- Карта — основной обзорный режим `/wbs`, дерево остаётся отдельным режимом редактирования.
- Отрисовка выполняется живым SVG из `/wbs/tree`; `docs/vera_wbs.svg` используется только как исторический визуальный референс.
- Первый уровень детализации показывает восемь фаз с агрегированным прогрессом. Разделы и листовые задачи раскрываются по веткам или командой «Все задачи»; полный граф не должен быть стартовым состоянием и автоматически уменьшать текст до нечитаемого состояния.
- Листовая карточка получает верхний маркер и рамку цвета стадии из API. Просрочка обозначается красной рамкой, но не заменяет цвет стадии.
- Родительский узел остаётся нейтральным и показывает многосегментную полосу стадий, `done/total` и процент. При 100% завершения рамка становится зелёной.
- Обязательные действия: pan, zoom, fit-to-view, раскрытие/сворачивание, поиск, фильтр фазы и стадии, открытие задачи.
- Поиск раскрывает полный путь к совпадению и визуально выделяет найденный узел. Фильтр стадии приглушает остальные ветви, сохраняя топологию карты.
- Управление картой доступно мышью, touch/pointer-событиями и клавиатурой; карточки имеют `role=button`, `tabIndex`, `aria-label` и обработку Enter/Space.
- Рабочая область имеет явную высоту, технологичную координатную сетку и компактную строку подсказок. Элементы управления не перекрывают важный контент на мобильном экране.

---

## Состояния загрузки и пустые состояния

- Спиннер: сетка анимированных точек (имитация ячейки Брайля), цвет точек переходит через `var(--border)` → `var(--accent)` (см. `@keyframes braille-dot` в `app.css`).
- Пустое состояние: `text-center text-muted py-16`.
- Ошибка: `border border-red-400/30 bg-red-400/10 text-red-400`, `role="alert"`.

---

## Доступность (обязательно)

- Все интерактивные элементы — видимый `focus-visible:outline-2 outline-offset-2 outline-accent`.
- `aria-label` на иконочных кнопках без текста.
- `aria-required`, `aria-invalid`, `aria-describedby` на полях форм.
- `role="alert"` на сообщениях об ошибках.
- `aria-live="polite"` на динамических регионах.
- Декоративные элементы — `aria-hidden="true"`.
- Скринридер-текст — `className="sr-only"`.
- Контраст: основной текст `#F0F0F0` на `#111827` — AAA. Акцент `#6366F1` с белым текстом (`#FFFFFF`) — проверен на AA для текста на кнопках.
