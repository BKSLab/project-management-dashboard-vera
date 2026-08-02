# Frontend Project Management Dashboard Vera

React-интерфейс персонального таск-трекера проекта «Агент Вера».

## Стек

- React 19 и TypeScript;
- Vite;
- Tailwind CSS v4;
- TanStack Query для server state;
- Zustand для UI state;
- `@dnd-kit` для канбана;
- `react-aria-components` для доступных UI-примитивов.

## Запуск

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

По умолчанию Vite использует `http://localhost:5173`. Backend должен быть доступен по адресу из `.env`:

```dotenv
VITE_API_URL=http://localhost:8000
```

Все запросы отправляются на API с префиксом `/api/v1`.

## Основные экраны

- `/` — сводка проекта и шкалы «Пульса канбана»;
- `/kanban` — доска, поиск и модальное окно задачи;
- `/wbs` — дерево ИСР и rollup-прогресс;
- `/docs` — поиск и управление документами;
- `/docs/:slug` — просмотр и редактирование Markdown-документа.

## Проверки

```powershell
npm run lint
npm run build
```

Актуальные правила интерфейса находятся в `../docs/DESIGN_GUIDE.md`, а полное описание проекта — в корневом `README.md`.
