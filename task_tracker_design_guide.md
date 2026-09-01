# UI/UX Design Guide для Project Task Tracker

## 1. Цель и визуальное направление

Документ задаёт единый дизайн-язык при развитии существующего дашборда в полноценный task tracker. Агент должен сохранить существующую функциональность и адаптировать текущие компоненты под общую систему, а не переписывать UI без необходимости.

Целевое ощущение: **современный профессиональный desktop-инструмент с качеством хорошего нативного приложения**.

Референсы: **VS Code** — тёмная рабочая среда и плотность информации; **Linear** — минимализм и быстрые взаимодействия; **Postman** — организация технического workspace; **Material Design 3** — системность состояний и elevation; **iOS/macOS и современные Android-интерфейсы** — качество деталей, глубина и плавность.

Ключевые принципы:

- Dark-first, без чистого `#000000` как основного фона.
- Информация важнее декора.
- Высокая информационная плотность без визуальной тесноты.
- Progressive disclosure: кратко в карточке, подробно в detail panel.
- Глубина: оттенок поверхности → граница → тень → декоративный эффект.
- Цвет всегда семантичен: выбор, статус, приоритет, предупреждение, ошибка.

## 2. Design tokens и палитра

Все цвета и размеры вынести в централизованные design tokens / CSS variables.

```css
:root {
  --color-bg-app: #0d1117;
  --color-bg-sidebar: #11161d;
  --color-bg-surface: #161b22;
  --color-bg-surface-2: #1c222b;
  --color-bg-elevated: #212832;
  --color-bg-hover: #272f3a;
  --color-bg-active: #303947;

  --color-border-subtle: rgba(255,255,255,.055);
  --color-border: rgba(255,255,255,.09);
  --color-border-strong: rgba(255,255,255,.15);

  --color-text-primary: #e6edf3;
  --color-text-secondary: #b1bac4;
  --color-text-muted: #7d8793;
  --color-text-disabled: #555f6b;

  --color-accent: #58a6ff;
  --color-accent-hover: #79b8ff;
  --color-accent-soft: rgba(88,166,255,.12);
  --color-accent-border: rgba(88,166,255,.38);

  --color-success: #3fb950;
  --color-warning: #d29922;
  --color-danger: #f85149;
  --color-info: #58a6ff;
  --color-purple: #a371f7;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  --duration-fast: 120ms;
  --duration-normal: 180ms;
  --duration-slow: 240ms;
  --ease-standard: cubic-bezier(.2, 0, 0, 1);
}
```

Muted-цвет использовать только для вторичных метаданных. Основной текст должен иметь высокий контраст.

## 3. Поверхности, тени и glass

Интерфейс должен восприниматься как система слоёв: Application Background → Sidebar/Workspace → Main Surface → Card → Floating Detail Panel.

Обычная карточка:

```css
box-shadow:
  0 1px 2px rgba(0,0,0,.28),
  0 4px 12px rgba(0,0,0,.12);
```

Hover/elevated:

```css
box-shadow:
  0 4px 10px rgba(0,0,0,.28),
  0 12px 28px rgba(0,0,0,.18);
```

Floating panel/modal:

```css
box-shadow:
  0 16px 48px rgba(0,0,0,.42),
  0 0 0 1px rgba(255,255,255,.05);
```

Glassmorphism применять только к floating toolbar, modal, dropdown, command palette, detail drawer и sticky header:

```css
background: rgba(22,27,34,.82);
backdrop-filter: blur(18px);
-webkit-backdrop-filter: blur(18px);
border: 1px solid rgba(255,255,255,.07);
```

Не применять blur ко всем карточкам Kanban. Не использовать яркие glow-тени.

## 4. Типографика и spacing

Основной UI-шрифт: **Inter** или существующий качественный sans-serif. Для `TASK-142`, кодов и технических метаданных — **JetBrains Mono** / **IBM Plex Mono**.

Основной рабочий текст: 13–14 px. Название задачи: 14–15 px, weight 550–600. Не использовать крупную лендинговую типографику.

Шкала отступов: `4, 8, 12, 16, 20, 24, 32 px`. Типичная task card: `padding: 12px 14px`.

Скругления: badge 6 px; input/button 8–10 px; task card 10–12 px; panel 14 px; modal 16–18 px.

## 5. Архитектура интерфейса

Project — центральная сущность, и UI должен это отражать.

Глобально:

```text
Dashboard
Projects
```

Внутри Project Workspace:

```text
Overview
Tasks
Kanban
Documents
Structure
```

`Structure` можно скрыть до реализации автоматической структуры/ИСР.

В верхней части project workspace: название проекта, статус, прогресс, ключевые показатели и действия проекта.

## 6. Общий Dashboard

Dashboard отвечает на вопрос: **что происходит со всеми проектами сейчас?**

Приоритетные блоки: активные проекты, общий прогресс, задачи в работе, просрочки, ближайшие дедлайны, недавно изменённые и проблемные проекты. Не заполнять экран графиками без практической ценности.

Пример project card:

```text
Название проекта
Краткое описание

████████░░ 78%
18 задач · 5 в работе · 2 просрочено
Ближайший срок: 08.09
```

Красный цвет использовать только при реальной проблеме.

## 7. Kanban

Колонки должны восприниматься как части одного workspace, а не отдельные массивные панели.

```text
BACKLOG 12       IN PROGRESS 4       REVIEW 2       DONE 18
─────────────────────────────────────────────────────────────
Task             Task                Task           Task
Task             Task                Task           Task
```

Шапка колонки: название статуса, количество задач, contextual actions. Статус допускается обозначать небольшим цветным маркером. Не заливать всю колонку цветом статуса.

## 8. Task Card в Kanban

Карточка должна позволять понять состояние задачи без открытия и оставаться компактной.

```text
TASK-142                                      HIGH

Реализовать фильтрацию проектов

Добавить фильтрацию по статусу и владельцу.
Описание максимум в 2 строки.

💬 Последний комментарий максимум в 1–2 строки…

Backend / API

📅 08 Sep                                  💬 4
```

Отсутствующие данные не должны оставлять пустые блоки.

### Название
Максимум 2 строки, далее line-clamp/ellipsis. Это главный визуальный элемент.

### Описание
Если есть — 1–2 строки secondary text. Не показывать сырой Markdown. Если нет — блок не рендерить.

### Последний комментарий
Если есть комментарии — показывать compact preview:

```css
background: rgba(255,255,255,.025);
border-left: 2px solid rgba(88,166,255,.45);
border-radius: 6px;
padding: 6px 8px;
```

Можно показать иконку, автора и 1–2 строки текста. Полный поток находится внутри задачи.

### Footer
Показывать короткий breadcrumb группы/иерархии, дедлайн и количество комментариев. Внутри проекта не повторять название проекта на каждой карточке.

## 9. Priority и Deadline

```css
--priority-low: #7d8793;
--priority-medium: #58a6ff;
--priority-high: #d29922;
--priority-urgent: #f85149;
```

Приоритет отображать маленьким badge/icon/indicator. Не заливать карточку цветом приоритета.

Deadline: обычный будущий — muted; близкий — warning; просроченный — danger. Просрочку обозначать индикатором, а не красной заливкой всей карточки.

## 10. Состояния Task Card и Drag & Drop

Hover:

```css
transition:
  background-color 160ms ease,
  border-color 160ms ease,
  box-shadow 160ms ease,
  transform 160ms ease;
```

Допустим `translateY(-1px)`.

Selected:

```css
border-color: rgba(88,166,255,.55);
box-shadow: 0 0 0 1px rgba(88,166,255,.12);
```

Dragging:

```css
transform: rotate(.5deg) scale(1.015);
box-shadow: 0 18px 44px rgba(0,0,0,.42);
```

Drop target:

```css
background: rgba(88,166,255,.055);
outline: 1px dashed rgba(88,166,255,.35);
```

Drag & Drop должен восприниматься как физическое перемещение: сохранять вид карточки, показывать позицию вставки и плавно завершать drop. Большинство переходов — 120–200 ms.

## 11. Detail Panel задачи

Для быстрого просмотра/редактирования предпочтительна правая detail panel/drawer шириной примерно **420–560 px**, чтобы не терять контекст Kanban/List.

```text
TASK-142
Название задачи

Status       Priority
Deadline     Parent/Group

Description
Documents / Relations
Comments
Activity
```

Информацию разделять на секции.

Комментарии оформлять как компактный activity feed, а не как огромные speech bubbles. Историю изменений показывать timeline.

## 12. Tasks List

Kanban не должен быть единственным представлением задач.

```text
ID       TASK                         STATUS       PRIORITY    DEADLINE
142      Реализовать фильтрацию       In Progress High        08 Sep
143      Исправить API                Review      Medium      09 Sep
```

Одна сущность Task должна визуально оставаться узнаваемой во всех представлениях. Статусы и приоритеты используют одни и те же design tokens.

## 13. Статусы

Статус — бизнес-состояние, а не декоративный цвет. Один статус во всём приложении должен иметь одинаковые label, icon/marker, semantic color и порядок. Не создавать разные палитры статусов в разных компонентах.

## 14. Structure / ИСР из задач

Если структура строится из `parent_task_id`, это представление тех же задач, а не отдельная сущность UI.

```text
Project
├── Backend
│   ├── Authentication
│   │   ├── Login API
│   │   └── Refresh token
│   └── Users
└── Frontend
    └── Login screen
```

Поддержать expand/collapse, create subtask, indent/outdent, drag & drop и открытие той же detail panel. Изменение задачи в Structure сразу отражается в List и Kanban.

Сначала реализовать качественное интерактивное дерево. Граф/React Flow использовать только если появится реальная потребность показывать произвольные зависимости.

## 15. Controls и иконки

Primary button — accent. Secondary — surface + border. Destructive — danger только для destructive actions.

Все controls должны иметь hover, active, disabled и focus. Для icon-only действий обязателен tooltip и accessible label.

Использовать один icon set во всём приложении, например **Lucide** или Material Symbols. Не смешивать визуально разные библиотеки. Основной размер иконок: 14–18 px.

## 16. Accessibility

Все основные действия должны быть доступны с клавиатуры.

```css
outline: 2px solid rgba(88,166,255,.8);
outline-offset: 2px;
```

Не удалять focus outline без полноценной замены.

Обязательно:

- semantic HTML;
- настоящие button/link элементы;
- keyboard navigation;
- labels и `aria-label` для icon-only controls;
- достаточный контраст;
- состояние не передаётся только цветом;
- `prefers-reduced-motion`;
- альтернативный мыши способ изменить статус/положение задачи.

## 17. Анимации

Анимация должна объяснять изменение состояния, а не украшать интерфейс.

```css
--duration-fast: 120ms;
--duration-normal: 180ms;
--duration-slow: 240ms;
--ease-standard: cubic-bezier(.2, 0, 0, 1);
```

Анимировать hover, drawer, dropdown, drag/drop, selected state, toast и небольшие layout transitions. Не использовать bounce и чрезмерные spring-эффекты.

## 18. Loading / Empty / Error

Для каждого рабочего представления предусмотреть loading, empty, error и partial-data states. Для загрузки основного контента предпочтителен skeleton.

Empty state должен объяснять следующее действие:

```text
В проекте пока нет задач.
Создайте первую задачу, чтобы начать работу.

[Создать задачу]
```

## 19. Адаптивность

Приоритет — desktop, но layout не должен ломаться на небольших экранах.

- Sidebar может сворачиваться.
- Detail panel на узких экранах превращается в overlay/full-screen sheet.
- Kanban сохраняет горизонтальный scroll вместо сжатия колонок до нечитаемого состояния.
- Основные действия остаются доступными без hover.

## 20. Чего избегать

Не использовать:

- чистый чёрный фон повсеместно;
- яркие градиенты на каждой поверхности;
- glassmorphism для каждой карточки;
- neon/glow вокруг обычных controls;
- разноцветные карточки по статусам;
- чрезмерные тени;
- слишком большие скругления;
- крупные пустые пространства ради «воздуха»;
- разные стили одинаковых сущностей на разных экранах;
- анимации, замедляющие работу;
- цвет как единственный способ передачи состояния.

## 21. Порядок внедрения агентом

Рекомендуемый порядок рефакторинга дизайна:

1. Проанализировать текущие компоненты и не ломать рабочую функциональность.
2. Ввести централизованные design tokens.
3. Привести базовые surfaces, typography, borders, radius и controls к новой системе.
4. Обновить глобальный layout и Project Workspace.
5. Обновить Kanban columns и Task Card.
6. Реализовать все состояния hover/selected/dragging/drop target/focus.
7. Обновить detail panel, comments и activity.
8. Привести Dashboard и Project Cards к общей системе.
9. Привести Tasks List и Documents к тому же дизайн-языку.
10. Проверить keyboard navigation, контраст, reduced motion и адаптивность.
11. Удалить старые локальные CSS-значения, дублирующие design tokens.

## 22. Итоговый критерий

Интерфейс должен ощущаться как **«VS Code / Linear для управления проектами»**, но не быть их копией.

Он должен быть тёмным, спокойным, технологичным, быстрым, компактным и визуально цельным. Glass, тени и metallic-like границы используются для ощущения глубины, а не как самоцель. Пользователь прежде всего должен видеть состояние проектов и задач, а декоративная система должна помогать этому, а не конкурировать с данными.
