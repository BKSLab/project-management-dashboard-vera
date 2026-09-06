# План доработки дизайна Project Task Tracker

> Практическое дизайн-ТЗ для AI-агента. Функциональность и архитектуру
> продукта не переделывать. Задача --- системно поднять визуальное
> качество существующего frontend.

## 1. Целевое направление

Формула дизайна:

**Apple / Jony Ive discipline + VS Code / Linear density + Material
interaction + restrained glass + dark anodized metal + matte
mineral/concrete surfaces + 5--10% AI-punk.**

Нужен премиальный профессиональный desktop-инструмент, а не типовая
SaaS-админка.

У Apple/Jony Ive брать не конкретные компоненты, а принципы: минимум
постоянно видимого, пространство как часть композиции, сильную
типографическую иерархию, точность alignment, ощущение материала,
глубину, физически понятную реакцию интерфейса и progressive disclosure.

У Material брать состояния hover/focus/pressed/selected, elevation,
semantic colors и motion как объяснение изменения.

У VS Code/Linear сохранить высокую информационную плотность, dark
developer aesthetic, компактность и keyboard-first характер.

## 2. Что уже хорошо и должно сохраниться

Сохранить текущие сильные стороны:

-   единый dark visual language;
-   компактность;
-   ограниченную палитру;
-   единый Task Drawer;
-   Project Workspace;
-   Structure canvas;
-   Calendar/Time Map;
-   AI Wiki;
-   status/priority semantics;
-   существующие design tokens и общие компоненты.

Не переписывать экраны ради новой стилистики.

## 3. Главная проблема текущего UI

Сейчас слишком много смысловых блоков оформлены одинаковой формулой:

``` text
background + border + border-radius
```

Это создаёт container overload.

Новый порядок способов разделения информации:

``` text
1. spacing
2. typography
3. surface difference
4. border
```

Не каждый смысловой блок должен быть карточкой. Сократить визуально
заметные borders ориентировочно на 30--50%, не теряя структуры.

## 4. Чего делать нельзя

Не превращать продукт в cyberpunk HUD, neon UI, glassmorphism showcase
или старый буквальный skeuomorphism.

Не использовать:

-   leather/chrome textures;
-   фотографии металла/бетона;
-   заметную bitmap-текстуру бетона;
-   glow вокруг каждого элемента;
-   gradients на каждой карточке;
-   blur на всём приложении;
-   чрезмерные pills;
-   bounce-анимации;
-   постоянное декоративное движение.

AI-punk --- только лёгкий характер специальных AI-функций.

## 5. Система физических уровней

Ввести понятие elevation layers:

``` text
LEVEL 0 — void / application background
LEVEL 1 — workspace
LEVEL 2 — interactive surface
LEVEL 3 — elevated surface
LEVEL 4 — floating surface
```

### Level 0

``` css
--surface-void: #0b0f14;
```

Допустим почти незаметный tonal gradient, чтобы фон не ощущался цифровой
пустотой.

### Level 1

``` css
--surface-workspace: #10151c;
```

Основные рабочие пространства Dashboard, Project, Calendar, Structure.

### Level 2

``` css
--surface-interactive: #161c24;
```

Task Card, Project Card, inputs, timeline bars.

### Level 3

``` css
--surface-elevated: #1b222c;
```

Selected/hover objects, dropdowns, context menu.

### Level 4

Drawer, modal, command palette, AI panel, What-if panel.

``` css
background:
  linear-gradient(180deg, rgba(29,35,44,.985), rgba(18,23,30,.985));
box-shadow:
  0 24px 70px rgba(0,0,0,.42),
  0 0 0 1px rgba(255,255,255,.055);
```

## 6. Материалы

Материал создаётся оттенком, микроконтрастом, highlight, shadow и blur
--- не картинкой текстуры.

### Dark anodized metal

Использовать точечно для toolbar, selected structural node, важных
controls и project identity.

``` css
background:
  linear-gradient(180deg, rgba(255,255,255,.025), rgba(255,255,255,0) 45%),
  var(--surface-interactive);
border: 1px solid rgba(255,255,255,.075);
```

Характер: холодный, матовый, без зеркального блеска.

### Glass

Только для реально плавающих объектов: Drawer, popover, floating
toolbar, command palette, AI assistant, scenario panel.

``` css
background: rgba(20,26,34,.84);
backdrop-filter: blur(18px) saturate(120%);
border: 1px solid rgba(255,255,255,.07);
```

### Mineral / concrete

Не использовать literal texture. Создать matte/mineral ощущение через
нейтральный тон и при необходимости почти невидимый grain. Применять
только на больших canvas/background поверхностях.

## 7. AI-punk

Только AI Wiki, Project Agent, AI suggestions, semantic search и What-if
могут иметь дополнительный AI accent:

``` css
--ai-blue: #6aa9ff;
--ai-violet: #9b8cff;
--ai-cyan: #55d7e8;
```

Допустим слабый blue-violet gradient. Обычные Task и Project Card его не
используют.

AI должен ощущаться дополнительным интеллектуальным слоем системы, а не
общей темой интерфейса.

## 8. Borders, shadows, radius

``` css
--border-subtle: rgba(255,255,255,.045);
--border-default: rgba(255,255,255,.075);
--border-strong: rgba(255,255,255,.13);

--radius-control: 7px;
--radius-card: 10px;
--radius-panel: 14px;
--radius-floating: 16px;
```

Обычная surface:

``` css
box-shadow: 0 1px 2px rgba(0,0,0,.22);
```

Hover:

``` css
box-shadow: 0 6px 18px rgba(0,0,0,.24);
```

Floating:

``` css
box-shadow: 0 24px 70px rgba(0,0,0,.42);
```

Selected:

``` css
box-shadow:
  0 0 0 1px rgba(88,166,255,.22),
  0 8px 24px rgba(0,0,0,.28);
```

Не использовать glow.

## 9. Типографика

Основной UI: Inter или текущий sans-serif. Mono --- JetBrains
Mono/текущий mono только для TASK-123, project code, WBS number, дат в
техническом контексте и компактных metrics.

Ориентиры:

``` text
Page title: 20–24px / 600
Section:    14–16px / 600
Body:       13–14px / 400
Metadata:   11–12px
```

Premium достигается точностью, а не крупным текстом.

## 10. Buttons и inputs

Primary button не должен постоянно быть самым ярким объектом страницы.
Default accent спокойнее; hover ярче; active ощущается слегка нажатым.

Secondary почти сливается с surface.

Inputs сделать легче:

``` css
background: rgba(255,255,255,.025);
border: 1px solid rgba(255,255,255,.065);
```

Focus:

``` css
border-color: rgba(88,166,255,.72);
box-shadow: 0 0 0 3px rgba(88,166,255,.10);
```

Исправить browser autofill, чтобы он не становился светлым.

## 11. Sidebar

Sidebar должен ощущаться частью корпуса приложения.

Не делать каждый navigation item карточкой.

Selected: тонкий accent indicator + мягкий accent surface. Рассмотреть
вертикальный marker 2px вместо сильной синей заливки.

Project list разделять spacing/typography.

## 12. Project Header

Сделать главным визуальным якорем workspace:

``` text
● Тестовый проект   TEST   [В работе]
  3 задачи · 0 в работе · 0 готово

Обзор  Канбан  Задачи  Календарь  Структура  Документы  AI-вики
```

Project color --- маленький identity marker, не крупная заливка.

## 13. Dashboard

Это главный кандидат на переработку.

Четыре одинаковые metric cards выглядят как стандартный SaaS dashboard.
Объединить metrics в единый информационный strip/слой:

``` text
Проекты          В работе         Выполнено        Просрочено
1                0                0%               0
Всего: 1         3 задачи         0 закрыто        Всё в срок
```

Не обязательно четыре отдельных bordered boxes.

Project Card оставить физическим интерактивным объектом.

«Требуют внимания» и «Недавно изменённые» по возможности оформить как
списки на спокойной общей surface, а не две тяжёлые карточки.

Цель: dashboard --- информационное полотно, а не коллекция контейнеров.

## 14. Project Card

Default: matte surface, minimal border, subtle shadow.

Hover: +1px visual elevation, slightly brighter surface, border
становится заметнее.

Project color --- маленькая точка или тонкая identity line.

## 15. Project Overview

Metrics объединить в strip. Уменьшить число независимых карточек.

`Распределение по стадиям` оставлять отдельной surface только если
визуализация этого требует.

`Ближайшие сроки` и `О проекте` организовать преимущественно
layout/spacing.

## 16. Task Drawer

Должен стать одним из самых premium объектов.

Drawer физически лежит над workspace: Level 4 surface, мягкий gradient,
выраженная тень, тонкий highlight по краю.

Header sticky.

Sections:

``` text
СВОЙСТВА
ОПИСАНИЕ
ДОКУМЕНТЫ
ФАЙЛЫ
КОММЕНТАРИИ
ACTIVITY
```

Сократить горизонтальные разделители; использовать spacing/typography.

Открытие 180--220ms без bounce. Workspace позади можно слегка затемнить,
сохраняя контекст.

## 17. Modal создания Task/Project

Floating object, меньше внутренних borders, яснее hierarchy, чуть больше
breathing room.

Не делать все поля одинаково визуально тяжёлыми.

Footer легче, primary action справа.

## 18. Structure

Structure --- текущий визуальный эталон направления. Сохранить canvas,
minimap, auto-layout, compact controls и свободное пространство.

Улучшить:

-   canvas: почти незаметный mineral/grain;
-   Project Root: restrained dark-metal identity + project accent;
-   WBS Node: matte surface;
-   Task Node: легче и компактнее;
-   edges: default спокойнее, selected path accent;
-   zoom/minimap controls: floating glass/metal instruments.

Никакого glow.

## 19. Calendar / Time Map

Calendar должен выглядеть как precision instrument.

### Toolbar

Сейчас controls имеют слишком одинаковый вес.

Иерархия:

Primary:

``` text
Сентябрь 2026     Месяц
```

Secondary:

``` text
Сегодня   ‹ ›
```

Tertiary:

``` text
Фильтры
```

Постоянные select
`Все стадии / Все приоритеты / Все исполнители / Вся ИСР` желательно
свернуть в один floating Filters popover. При активных фильтрах:
`Фильтры · 2`.

### Timeline

Grid lines максимально тихие. Today --- тонкая luminous accent line.

Task bars --- matte metal objects, не Kanban cards.

Milestones --- маленькие precision markers.

Baseline --- muted ghost layer.

Proposed What-if --- полупрозрачный слой, визуально отличный от
сохранённых данных.

Project Pulse можно оставить отдельной surface, поскольку он является
самостоятельным инструментом анализа, но сделать его легче и менее
boxed.

## 20. AI Wiki

AI Wiki --- место, где допустим чуть более характерный AI-punk.

Empty state сделать менее похожим на обычную карточку.

Agent icon может иметь очень слабый blue-violet depth.

Input внизу должен ощущаться command surface.

Suggested questions --- не четыре тяжёлые cards, а лёгкие action
chips/rows.

Правая колонка knowledge status остаётся технической и спокойной.

При генерации ответа допустим очень слабый AI activity indicator, но без
sci-fi-анимаций.

## 21. Profile / Registration

Формы сейчас ближе всего к enterprise Material.

Уменьшить визуальный вес контейнеров и inputs.

Profile sections разделять spacing и headings, а не обязательно большой
bordered card на каждый блок.

Регистрация должна ощущаться чистой и спокойной. Не добавлять
декоративный hero.

## 22. Micro-interactions

Все основные объекты получают физически понятные состояния:

``` text
default
hover
focus
pressed
selected
dragging
disabled
```

Motion tokens:

``` css
--motion-fast: 120ms;
--motion-normal: 180ms;
--motion-slow: 240ms;
--ease-standard: cubic-bezier(.2,0,0,1);
```

Hover может слегка поднимать объект (`translateY(-1px)`), pressed
возвращает его на поверхность.

Drag --- чуть больше elevation, но без сильного scale/rotate.

Поддерживать `prefers-reduced-motion`.

## 23. Progressive disclosure

Это ключевой Apple-подход.

Не показывать control постоянно только потому, что он существует.

Примеры:

-   Calendar filters → popover;
-   secondary Task actions → context menu;
-   Project settings → gear/menu;
-   advanced AI options → только внутри AI context;
-   редкие destructive actions → menu/dialog.

Сложность продукта не должна быть постоянно видима.

## 24. Accessibility

Не жертвовать доступностью ради визуальной чистоты.

Обязательно:

-   заметный `focus-visible`;
-   keyboard navigation;
-   semantic HTML;
-   aria-label icon-only buttons;
-   достаточный contrast;
-   состояние не только цветом;
-   DnD имеет недраг-альтернативу;
-   `prefers-reduced-motion`.

Focus ring может быть аккуратным, но должен быть отчётливо виден.

## 25. Порядок внедрения

### Проход 1 --- Tokens

Унифицировать surfaces, borders, shadows, radii, motion. Убрать
локальные значения.

### Проход 2 --- Container reduction

Пройти Dashboard, Overview, Profile, AI Wiki и убрать лишние card
wrappers/borders.

### Проход 3 --- Physical hierarchy

Настроить уровни surface/elevation и состояния hover/pressed/selected.

### Проход 4 --- Floating objects

Task Drawer, modal, popover, toolbar, AI panel привести к единой
glass/metal модели.

### Проход 5 --- Dashboard

Перестроить metrics и информационные блоки без изменения данных.

### Проход 6 --- Calendar

Упростить toolbar, спрятать вторичные filters, улучшить grid/task
bars/Project Pulse.

### Проход 7 --- Structure

Добавить restrained materiality canvas/nodes/controls без изменения
layout engine.

### Проход 8 --- AI identity

Добавить очень умеренный AI-punk только AI-компонентам.

### Проход 9 --- Forms

Облегчить inputs, registration, project/task forms и profile.

### Проход 10 --- Motion & accessibility

Проверить все states, keyboard, focus, reduced motion, contrast.

## 26. Acceptance criteria

Редизайн успешен, если:

1.  функциональность не потеряна;
2.  интерфейс остаётся плотным;
3.  количество визуально тяжёлых контейнеров заметно снизилось;
4.  по внешнему виду понятно, что является background, surface,
    interactive object и floating object;
5.  Drawer/modal физически ощущаются над workspace;
6.  primary actions не доминируют постоянно;
7.  Calendar toolbar стал спокойнее;
8.  Structure сохранил свою сильную пространственную композицию;
9.  AI-функции получили собственный, но сдержанный характер;
10. стекло используется только для floating surfaces;
11. металл/mineral ощущаются через свет и тон, а не literal texture;
12. нет неонового/cyberpunk перегруза;
13. интерфейс остаётся доступным;
14. дизайн выглядит как единый продукт, а не набор эффектов.

## 27. Финальный ориентир

Нужен не «сайт в стиле Apple» и не копия macOS.

Нужно ощущение, что каждый пиксель интерфейса имеет причину.

Итоговый продукт должен соединять:

``` text
точность Apple
+ дисциплину Jony Ive
+ плотность VS Code
+ скорость Linear
+ предсказуемость Material
+ глубину стекла и тёмного металла
+ матовую минеральную основу
+ едва заметный AI-punk
```

Главный критерий:

> пользователь сначала замечает качество и ясность интерфейса, а уже
> потом --- визуальные эффекты.
