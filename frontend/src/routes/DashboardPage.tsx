import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FolderKanban,
  ListTodo,
  Plus,
} from "lucide-react";
import { api, endpoints, queryKeys } from "@/lib/api";
import { formatFullDate } from "@/lib/dates";
import { latestUpdate } from "@/lib/pulse";
import type { Dashboard } from "@/lib/types";
import { Page } from "@/components/layout/AppShell";
import { LinkButton } from "@/components/ui/Button";
import { Section } from "@/components/ui/Card";
import { StatStrip, StatTile } from "@/components/ui/Progress";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import { PulseBoard } from "@/components/pulse/PulseBoard";
import { PortfolioScope, PulseFacts } from "@/components/pulse/PulseBreakdown";
import { ProjectCard } from "@/components/dashboard/ProjectCard";
import { TaskRow } from "@/components/dashboard/TaskRow";
import { TaskDrawer } from "@/components/tasks/TaskDrawer";
import { useUiStore } from "@/stores/ui";

function DashboardSkeleton() {
  return (
    <div
      role="status"
      aria-label="Загрузка сводки"
      className="flex flex-col gap-6"
    >
      <Skeleton className="h-[88px] w-full" />
      <Skeleton className="h-56 w-full" />
      <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(17.5rem,1fr))]">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-40" />
        ))}
      </div>
    </div>
  );
}

/** Сколько карточек проектов помещается на экран портфеля до ссылки на список. */
const PROJECTS_ON_PORTFOLIO = 6;

/** Счётчик в заголовке секции: сколько строк, видно до чтения списка. */
function SectionCount({ value }: { value: number }) {
  return <span className="font-mono text-[12px] text-muted">{value}</span>;
}

export function DashboardPage() {
  const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);

  const dashboardQuery = useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: () => api.get<Dashboard>(endpoints.dashboard()),
  });

  // Портфель показывает витрину активных проектов, а не их полный
  // список: за полным есть отдельная страница, и дублировать её на
  // главном экране значит топить в ней всё остальное.
  const activeProjects = (dashboardQuery.data?.projects ?? []).filter(
    (project) => project.status === "ACTIVE",
  );
  const shownProjects = activeProjects.slice(0, PROJECTS_ON_PORTFOLIO);

  return (
    <Page>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h1 className="text-[22px] font-semibold tracking-[-0.03em] text-primary">
            Портфель
          </h1>
          <p className="text-[13px] text-muted">
            Что происходит со всеми проектами сейчас ·{" "}
            {formatFullDate(new Date().toISOString())}
          </p>
        </div>
        <LinkButton
          to="/projects/new"
          variant="primary"
          icon={<Plus size={15} />}
        >
          Новый проект
        </LinkButton>
      </header>

      {dashboardQuery.isPending && <DashboardSkeleton />}
      {dashboardQuery.error && (
        <ErrorMessage message={(dashboardQuery.error as Error).message} />
      )}

      {dashboardQuery.data && (
        <>
          <Section
            title="Проекты в работе"
            action={
              <Link
                to="/projects"
                className="text-[13px] text-accent hover:text-accent-hover"
              >
                Все проекты{" "}
                <span className="font-mono text-muted">
                  {dashboardQuery.data.totals.total_projects}
                </span>
              </Link>
            }
          >
            {activeProjects.length === 0 ? (
              <EmptyState
                title={
                  dashboardQuery.data.projects.length === 0
                    ? "Проектов пока нет"
                    : "Нет проектов в работе"
                }
                description={
                  dashboardQuery.data.projects.length === 0
                    ? "Создайте первый проект, чтобы начать вести задачи и структуру работ."
                    : "Проекты есть, но все вне статуса «В работе» — портфель разбирать не по чему."
                }
                icon={<FolderKanban size={24} />}
                action={
                  <LinkButton
                    to="/projects/new"
                    variant="primary"
                    icon={<Plus size={15} />}
                  >
                    Создать проект
                  </LinkButton>
                }
              />
            ) : (
              <>
                <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(17.5rem,1fr))]">
                  {shownProjects.map((project) => (
                    <ProjectCard key={project.id} project={project} />
                  ))}
                </div>
                {activeProjects.length > shownProjects.length && (
                  <Link
                    to="/projects"
                    className="text-[12px] text-muted hover:text-accent"
                  >
                    Ещё {activeProjects.length - shownProjects.length} в работе
                    — на странице проектов
                  </Link>
                )}
              </>
            )}
          </Section>

          <PulseBoard
            onOpenTask={setSelectedTaskId}
            dataUpdatedAt={latestUpdate(dashboardQuery.data.projects)}
            blockedReason={
              dashboardQuery.data.projects.some(
                (project) => project.status === "ACTIVE",
              )
                ? undefined
                : "Нет проектов в работе"
            }
            metrics={
              <StatStrip className="rounded-none border-0 bg-transparent shadow-none">
                <StatTile
                  label="Проекты в работе"
                  value={dashboardQuery.data.totals.active_projects}
                  hint={`Всего проектов: ${dashboardQuery.data.totals.total_projects}`}
                  icon={<FolderKanban size={12} />}
                />
                <StatTile
                  label="Задачи в работе"
                  value={dashboardQuery.data.totals.in_progress_tasks}
                  hint={`Всего задач: ${dashboardQuery.data.totals.total_tasks}`}
                  icon={<ListTodo size={12} />}
                />
                <StatTile
                  label="Выполнено"
                  value={`${Math.round(dashboardQuery.data.totals.completion_rate * 100)}%`}
                  hint={`${dashboardQuery.data.totals.done_tasks} задач закрыто`}
                  tone="success"
                  icon={<CheckCircle2 size={12} />}
                />
                <StatTile
                  label="Просрочено"
                  value={dashboardQuery.data.totals.overdue_tasks}
                  hint={
                    dashboardQuery.data.totals.overdue_tasks > 0
                      ? "Требует внимания"
                      : "Всё в срок"
                  }
                  tone={
                    dashboardQuery.data.totals.overdue_tasks > 0
                      ? "danger"
                      : "default"
                  }
                  icon={<AlertTriangle size={12} />}
                />
              </StatStrip>
            }
            breakdown={
              <PortfolioScope projects={dashboardQuery.data.projects} />
            }
            facts={
              <PulseFacts
                title="Требуют внимания"
                count={dashboardQuery.data.attention_tasks.length}
                empty="Просроченных и ближайших сроков нет."
              >
                {dashboardQuery.data.attention_tasks.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    onOpen={setSelectedTaskId}
                  />
                ))}
              </PulseFacts>
            }
          />

          <Section
            title="Недавно изменённые"
            action={
              <SectionCount value={dashboardQuery.data.recent_tasks.length} />
            }
          >
            <div className="overflow-hidden rounded-[var(--radius-card)] bg-surface/55 p-1.5">
              {dashboardQuery.data.recent_tasks.length === 0 ? (
                <p className="px-2.5 py-6 text-center text-[13px] text-muted">
                  Изменений пока не было.
                </p>
              ) : (
                dashboardQuery.data.recent_tasks.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    showUpdated
                    onOpen={setSelectedTaskId}
                  />
                ))
              )}
            </div>
          </Section>
        </>
      )}

      <TaskDrawer />
    </Page>
  );
}
