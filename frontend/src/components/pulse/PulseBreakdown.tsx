import type { ReactNode } from "react";
import type {
  DashboardProject,
  StageBreakdown as StageBreakdownItem,
} from "@/lib/types";
import { SegmentedProgress } from "@/components/ui/Progress";
import { StatusDot } from "@/components/ui/Badge";

/**
 * Охват портфельного разбора одной строкой.
 *
 * Карточки проектов стоят выше на странице, поэтому перечислять их здесь
 * второй раз незачем. Но границу разбора назвать нужно: без неё непонятно,
 * почему проект вне работы не упомянут в выводе.
 */
export function PortfolioScope({ projects }: { projects: DashboardProject[] }) {
  const active = projects.filter(
    (project) => project.status === "ACTIVE",
  ).length;
  const resting = projects.length - active;

  if (active === 0) {
    return (
      <p className="text-[12px] text-muted">
        Активных проектов нет — разбирать нечего. Переведите проект в статус «В
        работе».
      </p>
    );
  }

  return (
    <p className="text-[12px] text-muted">
      В разборе <span className="font-mono text-secondary">{active}</span>{" "}
      {plural(
        active,
        "активный проект",
        "активных проекта",
        "активных проектов",
      )}
      {resting > 0 && (
        <span className="text-disabled">
          {" · "}
          {resting} вне работы и в разбор не входят
        </span>
      )}
    </p>
  );
}

/** Русское склонение существительного при числе. */
function plural(count: number, one: string, few: string, many: string): string {
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 14) {
    return many;
  }
  if (mod10 === 1) {
    return one;
  }
  if (mod10 >= 2 && mod10 <= 4) {
    return few;
  }
  return many;
}

/**
 * Разрез проекта: сколько задач в каждой стадии.
 *
 * Для проекта единица разбора — задача, поэтому и разрез задачный: полоса
 * стадий показывает, где именно стоит работа, о которой говорит вывод.
 */
export function StageBreakdown({ stages }: { stages: StageBreakdownItem[] }) {
  if (stages.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2.5">
      <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
        По стадиям
      </h3>
      <SegmentedProgress
        segments={stages.map((item) => ({
          id: item.stage_id,
          value: item.tasks_count,
          color: item.color,
          label: item.stage_name,
        }))}
      />
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {stages.map((item) => (
          <span
            key={item.stage_id}
            className="inline-flex items-center gap-1.5 text-[12px] text-muted"
          >
            <StatusDot color={item.color} />
            {item.stage_name}
            <span className="font-mono text-secondary">{item.tasks_count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Поимённые факты области внутри пульса: задачи, требующие решения.
 *
 * Показатели говорят «просрочено 3», разбор объясняет почему — а этот
 * список показывает, какие именно это задачи. Он стоит между ними и
 * держит тот же визуальный язык, что и остальные списки приложения.
 */
export function PulseFacts({
  title,
  count,
  empty,
  children,
}: {
  title: string;
  count: number;
  empty: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold tracking-[0.06em] text-muted uppercase">
          {title}
        </h3>
        {count > 0 && (
          <span className="font-mono text-[11px] text-disabled">{count}</span>
        )}
      </div>
      {count === 0 ? (
        <p className="rounded-[var(--radius-card)] bg-app/40 px-3 py-3 text-[12.5px] text-disabled">
          {empty}
        </p>
      ) : (
        <div className="scrollbar-thin -mx-1 max-h-64 overflow-y-auto px-1">
          {children}
        </div>
      )}
    </div>
  );
}
