import { useMemo, useRef, useState } from "react";
import {
    DndContext,
    DragOverlay,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    type DragEndEvent,
    type DragStartEvent,
} from "@dnd-kit/core";
import {
    useInfiniteQuery,
    useMutation,
    useQuery,
    useQueryClient,
    type InfiniteData,
} from "@tanstack/react-query";
import { Beaker, CalendarRange, Filter } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { CalendarAgenda } from "@/components/calendar/CalendarAgenda";
import { CalendarRecentChanges } from "@/components/calendar/CalendarRecentChanges";
import { CalendarTask } from "@/components/calendar/CalendarTask";
import { CalendarToolbar } from "@/components/calendar/CalendarToolbar";
import { DeadlineDialog } from "@/components/calendar/DeadlineDialog";
import { DependencyDialog } from "@/components/calendar/DependencyDialog";
import { DependencyPanel } from "@/components/calendar/DependencyPanel";
import { MilestoneDialog } from "@/components/calendar/MilestoneDialog";
import { MilestonePanel } from "@/components/calendar/MilestonePanel";
import { ProjectPulse } from "@/components/calendar/ProjectPulse";
import { ScenarioPanel } from "@/components/calendar/ScenarioPanel";
import { TimelineGrid } from "@/components/calendar/TimelineGrid";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { EmptyState, ErrorMessage, Skeleton } from "@/components/ui/States";
import {
    buildTimelineDays,
    dateFromDropId,
    localToday,
    moveTaskInterval,
    normalizeDate,
    normalizeScale,
    rescheduleCalendarTask,
    resizeTaskInterval,
    shiftTimelineAnchor,
    tasksByDate,
    timelineRange,
    timelineTitle,
    type TimelineScale,
} from "@/lib/calendar";
import { api, endpoints, queryKeys } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type {
    CalendarTask as CalendarTaskModel,
    ProjectCalendar,
    ProjectMilestone,
    ProjectMilestoneInput,
    ScenarioApplyResult,
    ScenarioChangeInput,
    ScenarioPreview,
    Task,
    TaskDependency,
    TaskDependencyInput,
    TaskPriority,
    UnscheduledTasksPage,
} from "@/lib/types";
import { PRIORITY_LABELS, PRIORITY_ORDER } from "@/lib/types";
import { useProjectOutlet } from "@/lib/useProjectOutlet";
import { useUiStore } from "@/stores/ui";

const FILTER_NAMES = ["stage", "priority", "assignee", "wbs"] as const;

interface TaskDatesVariables {
    taskId: number;
    dueDate: string | null;
    startDate?: string | null;
}

export function ProjectCalendarPage() {
    const project = useProjectOutlet();
    const queryClient = useQueryClient();
    const toast = useToast();
    const setSelectedTaskId = useUiStore((state) => state.setSelectedTaskId);
    const [searchParams, setSearchParams] = useSearchParams();
    const today = localToday();
    const scale = normalizeScale(searchParams.get("scale"));
    const anchor = normalizeDate(searchParams.get("anchor"), today);
    const range = useMemo(() => timelineRange(anchor, scale), [anchor, scale]);
    const initialSelected = today >= range.dateFrom && today <= range.dateTo ? today : range.dateFrom;
    const [selectedDate, setSelectedDate] = useState(initialSelected);
    const [activeTask, setActiveTask] = useState<CalendarTaskModel | null>(null);
    const [deadlineTask, setDeadlineTask] = useState<CalendarTaskModel | null>(null);
    const [milestoneDialog, setMilestoneDialog] = useState<"new" | ProjectMilestone | null>(null);
    const [isDependencyDialogOpen, setDependencyDialogOpen] = useState(false);
    const [isScenarioMode, setScenarioMode] = useState(false);
    const [scenarioInputs, setScenarioInputs] = useState<ScenarioChangeInput[]>([]);
    const [scenarioPreview, setScenarioPreview] = useState<ScenarioPreview | null>(null);
    const scenarioRevision = useRef(0);
    const activeSelectedDate =
        selectedDate >= range.dateFrom && selectedDate <= range.dateTo
            ? selectedDate
            : initialSelected;
    const stageFilter = searchParams.get("stage") ?? "";
    const priorityFilter = searchParams.get("priority") ?? "";
    const assigneeFilter = searchParams.get("assignee") ?? "";
    const wbsFilter = searchParams.get("wbs") ?? "";
    const days = useMemo(() => buildTimelineDays(range, today), [range, today]);
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
        useSensor(KeyboardSensor),
    );

    const commonParams = useMemo(() => {
        const params = new URLSearchParams({ today });
        if (stageFilter) params.set("stage_id", stageFilter);
        if (priorityFilter) params.set("priority", priorityFilter);
        if (assigneeFilter) params.set("assignee", assigneeFilter);
        if (wbsFilter) params.set("wbs_node_id", wbsFilter);
        return params;
    }, [assigneeFilter, priorityFilter, stageFilter, today, wbsFilter]);
    const rangeParams = useMemo(() => {
        const params = new URLSearchParams(commonParams);
        params.set("date_from", range.dateFrom);
        params.set("date_to", range.dateTo);
        return params;
    }, [commonParams, range]);
    const calendarKey = queryKeys.calendar(project.id, rangeParams.toString());
    const unscheduledKey = queryKeys.calendarUnscheduled(project.id, commonParams.toString());

    const calendarQuery = useQuery({
        queryKey: calendarKey,
        queryFn: () =>
            api.get<ProjectCalendar>(
                `${endpoints.projectCalendar(project.id)}?${rangeParams.toString()}`,
            ),
    });
    const unscheduledQuery = useInfiniteQuery<UnscheduledTasksPage>({
        queryKey: unscheduledKey,
        initialPageParam: null,
        queryFn: ({ pageParam }) => {
            const params = new URLSearchParams(commonParams);
            params.set("limit", "50");
            if (pageParam !== null) params.set("cursor", String(pageParam));
            return api.get<UnscheduledTasksPage>(
                `${endpoints.projectCalendarUnscheduled(project.id)}?${params.toString()}`,
            );
        },
        getNextPageParam: (page) => page.next_cursor ?? undefined,
    });
    const milestonesQuery = useQuery({
        queryKey: queryKeys.milestones(project.id),
        queryFn: () => api.get<ProjectMilestone[]>(endpoints.projectMilestones(project.id)),
    });
    const tasksQuery = useQuery({
        queryKey: queryKeys.tasks(project.id),
        queryFn: () => api.get<Task[]>(endpoints.projectTasks(project.id)),
    });

    const deadlineMutation = useMutation({
        mutationFn: ({ taskId, dueDate, startDate }: TaskDatesVariables) =>
            api.patch<Task>(endpoints.task(taskId), {
                due_date: dueDate,
                ...(startDate !== undefined && { start_date: startDate }),
            }),
        onMutate: async ({ taskId, dueDate, startDate }: TaskDatesVariables) => {
            await Promise.all([
                queryClient.cancelQueries({ queryKey: calendarKey }),
                queryClient.cancelQueries({ queryKey: unscheduledKey }),
            ]);
            const previousCalendar = queryClient.getQueryData<ProjectCalendar>(calendarKey);
            const previousUnscheduled =
                queryClient.getQueryData<InfiniteData<UnscheduledTasksPage>>(unscheduledKey);
            const sourceTask =
                previousCalendar?.tasks.find((task) => task.id === taskId) ??
                previousUnscheduled?.pages
                    .flatMap((page) => page.items)
                    .find((task) => task.id === taskId);
            if (sourceTask) {
                const changed = rescheduleCalendarTask(
                    sourceTask,
                    dueDate,
                    today,
                    startDate === undefined ? sourceTask.start_date : startDate,
                );
                queryClient.setQueryData<ProjectCalendar>(calendarKey, (old) => {
                    if (!old) return old;
                    const intervalStart = changed.start_date ?? changed.due_date;
                    const intervalEnd = changed.due_date ?? changed.start_date;
                    const willBeVisible =
                        intervalStart !== null &&
                        intervalEnd !== null &&
                        intervalEnd >= old.range.date_from &&
                        intervalStart <= old.range.date_to;
                    const wasUnscheduled =
                        sourceTask.start_date === null && sourceTask.due_date === null;
                    const isUnscheduled =
                        changed.start_date === null && changed.due_date === null;
                    const tasks = old.tasks.filter((task) => task.id !== taskId);
                    if (willBeVisible) tasks.push(changed);
                    return {
                        ...old,
                        tasks,
                        summary: {
                            ...old.summary,
                            overdue:
                                old.summary.overdue -
                                Number(sourceTask.is_overdue) +
                                Number(changed.is_overdue),
                            due_soon:
                                old.summary.due_soon -
                                Number(sourceTask.is_due_soon) +
                                Number(changed.is_due_soon),
                            unscheduled:
                                old.summary.unscheduled +
                                Number(isUnscheduled) -
                                Number(wasUnscheduled),
                            drifted:
                                old.summary.drifted -
                                Number(
                                    sourceTask.drift_days !== null &&
                                        sourceTask.drift_days !== 0,
                                ) +
                                Number(changed.drift_days !== null && changed.drift_days !== 0),
                        },
                    };
                });
                queryClient.setQueryData<InfiniteData<UnscheduledTasksPage>>(
                    unscheduledKey,
                    (old) => {
                        if (!old) return old;
                        const pages = old.pages.map((page) => ({
                            ...page,
                            items: page.items.filter((task) => task.id !== taskId),
                        }));
                        if (
                            changed.start_date === null &&
                            changed.due_date === null &&
                            pages[0]
                        ) {
                            pages[0] = { ...pages[0], items: [changed, ...pages[0].items] };
                        }
                        return { ...old, pages };
                    },
                );
            }
            return { previousCalendar, previousUnscheduled };
        },
        onError: (error, _variables, context) => {
            if (context?.previousCalendar) {
                queryClient.setQueryData(calendarKey, context.previousCalendar);
            }
            if (context?.previousUnscheduled) {
                queryClient.setQueryData(unscheduledKey, context.previousUnscheduled);
            }
            toast.error(`Не удалось изменить даты: ${(error as Error).message}`);
        },
        onSuccess: () => toast.success("Плановые даты задачи обновлены."),
        onSettled: (_data, _error, variables) => {
            queryClient.invalidateQueries({ queryKey: ["projects", project.id] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
            queryClient.invalidateQueries({ queryKey: queryKeys.task(variables.taskId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.taskActivity(variables.taskId) });
        },
    });
    const baselineMutation = useMutation({
        mutationFn: (taskId: number) => api.post<Task>(endpoints.taskBaseline(taskId)),
        onSuccess: (_task, taskId) => {
            toast.success("Baseline задачи зафиксирован.");
            queryClient.invalidateQueries({ queryKey: ["projects", project.id] });
            queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.taskActivity(taskId) });
        },
        onError: (error) =>
            toast.error(`Не удалось зафиксировать baseline: ${(error as Error).message}`),
    });
    const refreshMilestones = () => {
        queryClient.invalidateQueries({ queryKey: queryKeys.milestones(project.id) });
        queryClient.invalidateQueries({
            queryKey: ["projects", project.id, "calendar"],
        });
    };
    const createMilestoneMutation = useMutation({
        mutationFn: (data: ProjectMilestoneInput) =>
            api.post<ProjectMilestone>(endpoints.projectMilestones(project.id), data),
        onSuccess: () => {
            setMilestoneDialog(null);
            refreshMilestones();
            toast.success("Веха создана.");
        },
        onError: (error) => toast.error(`Не удалось создать веху: ${(error as Error).message}`),
    });
    const updateMilestoneMutation = useMutation({
        mutationFn: ({ milestoneId, data }: { milestoneId: number; data: ProjectMilestoneInput }) =>
            api.patch<ProjectMilestone>(
                endpoints.projectMilestone(project.id, milestoneId),
                data,
            ),
        onSuccess: () => {
            setMilestoneDialog(null);
            refreshMilestones();
            toast.success("Веха обновлена.");
        },
        onError: (error) => toast.error(`Не удалось обновить веху: ${(error as Error).message}`),
    });
    const deleteMilestoneMutation = useMutation({
        mutationFn: (milestoneId: number) =>
            api.delete<void>(endpoints.projectMilestone(project.id, milestoneId)),
        onSuccess: () => {
            refreshMilestones();
            toast.success("Веха удалена.");
        },
        onError: (error) => toast.error(`Не удалось удалить веху: ${(error as Error).message}`),
    });
    const isMilestoneSaving =
        createMilestoneMutation.isPending ||
        updateMilestoneMutation.isPending ||
        deleteMilestoneMutation.isPending;
    const createDependencyMutation = useMutation({
        mutationFn: (data: TaskDependencyInput) =>
            api.post<TaskDependency>(endpoints.projectTaskDependencies(project.id), data),
        onSuccess: () => {
            setDependencyDialogOpen(false);
            queryClient.invalidateQueries({
                queryKey: ["projects", project.id, "calendar"],
            });
            toast.success("Зависимость создана.");
        },
        onError: (error) =>
            toast.error(`Не удалось создать зависимость: ${(error as Error).message}`),
    });
    const deleteDependencyMutation = useMutation({
        mutationFn: (dependencyId: number) =>
            api.delete<void>(endpoints.projectTaskDependency(project.id, dependencyId)),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ["projects", project.id, "calendar"],
            });
            toast.success("Зависимость удалена.");
        },
        onError: (error) =>
            toast.error(`Не удалось удалить зависимость: ${(error as Error).message}`),
    });
    const isDependencySaving =
        createDependencyMutation.isPending || deleteDependencyMutation.isPending;
    const previewScenarioMutation = useMutation({
        mutationFn: ({ changes }: { revision: number; changes: ScenarioChangeInput[] }) =>
            api.post<ScenarioPreview>(endpoints.projectCalendarScenarioPreview(project.id), {
                changes,
            }),
        onSuccess: (preview, variables) => {
            if (variables.revision === scenarioRevision.current) {
                setScenarioPreview(preview);
            }
        },
        onError: (error, variables) => {
            if (variables.revision === scenarioRevision.current) {
                setScenarioPreview(null);
                toast.error(`Не удалось рассчитать сценарий: ${(error as Error).message}`);
            }
        },
    });
    const applyScenarioMutation = useMutation({
        mutationFn: (preview: ScenarioPreview) =>
            api.post<ScenarioApplyResult>(endpoints.projectCalendarScenarioApply(project.id), {
                changes: preview.changes.map((change) => ({
                    task_id: change.task_id,
                    start_date: change.proposed.start_date,
                    due_date: change.proposed.due_date,
                    expected_updated_at: change.expected_updated_at,
                })),
            }),
        onSuccess: (result) => {
            scenarioRevision.current += 1;
            setScenarioMode(false);
            setScenarioInputs([]);
            setScenarioPreview(null);
            queryClient.invalidateQueries({ queryKey: ["projects", project.id] });
            queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
            for (const taskId of result.task_ids) {
                queryClient.invalidateQueries({ queryKey: queryKeys.task(taskId) });
                queryClient.invalidateQueries({ queryKey: queryKeys.taskActivity(taskId) });
            }
            toast.success(`Сценарий применён: ${result.applied_count} задач.`);
        },
        onError: (error) =>
            toast.error(`Не удалось применить сценарий: ${(error as Error).message}`),
    });

    const groupedTasks = useMemo(
        () => tasksByDate(calendarQuery.data?.tasks ?? []),
        [calendarQuery.data?.tasks],
    );
    const stagesById = useMemo(
        () => new Map((calendarQuery.data?.stages ?? []).map((stage) => [stage.id, stage])),
        [calendarQuery.data?.stages],
    );
    const unscheduledTasks = useMemo(
        () => unscheduledQuery.data?.pages.flatMap((page) => page.items) ?? [],
        [unscheduledQuery.data?.pages],
    );

    function setViewParam(name: string, value: string) {
        const next = new URLSearchParams(searchParams);
        if (value) next.set(name, value);
        else next.delete(name);
        setSearchParams(next, { replace: true });
    }

    function movePeriod(delta: number) {
        const nextAnchor = shiftTimelineAnchor(anchor, scale, delta);
        setSelectedDate(nextAnchor);
        setViewParam("anchor", nextAnchor);
    }

    function goToday() {
        setSelectedDate(today);
        setViewParam("anchor", today);
    }

    function changeScale(nextScale: TimelineScale) {
        setViewParam("scale", nextScale);
    }

    function resetFilters() {
        const next = new URLSearchParams(searchParams);
        for (const name of FILTER_NAMES) next.delete(name);
        setSearchParams(next, { replace: true });
    }

    function taskWithScenario(task: CalendarTaskModel): CalendarTaskModel {
        const change = scenarioPreview?.changes.find((item) => item.task_id === task.id);
        return change
            ? {
                  ...task,
                  start_date: change.proposed.start_date,
                  due_date: change.proposed.due_date,
              }
            : task;
    }

    function stopScenario() {
        scenarioRevision.current += 1;
        setScenarioMode(false);
        setScenarioInputs([]);
        setScenarioPreview(null);
        setDeadlineTask(null);
    }

    function requestScenarioPreview(changes: ScenarioChangeInput[]) {
        if (changes.length === 0) {
            scenarioRevision.current += 1;
            setScenarioPreview(null);
            return;
        }
        const revision = scenarioRevision.current + 1;
        scenarioRevision.current = revision;
        previewScenarioMutation.mutate({ revision, changes });
    }

    function changeDates(task: CalendarTaskModel, dates: Omit<TaskDatesVariables, "taskId">) {
        const startDate = dates.startDate === undefined ? task.start_date : dates.startDate;
        if (
            task.due_date === dates.dueDate &&
            task.start_date === startDate
        ) {
            return;
        }
        if (isScenarioMode) {
            const original =
                calendarQuery.data?.tasks.find((item) => item.id === task.id) ??
                unscheduledTasks.find((item) => item.id === task.id);
            const remaining = scenarioInputs.filter((item) => item.task_id !== task.id);
            const next =
                original?.start_date === startDate && original.due_date === dates.dueDate
                    ? remaining
                    : [
                          ...remaining,
                          {
                              task_id: task.id,
                              start_date: startDate,
                              due_date: dates.dueDate,
                          },
                      ];
            setScenarioInputs(next);
            requestScenarioPreview(next);
            return;
        }
        deadlineMutation.mutate({ taskId: task.id, ...dates });
    }

    function handleDragStart(event: DragStartEvent) {
        setActiveTask((event.active.data.current?.task as CalendarTaskModel | undefined) ?? null);
    }

    function handleDragEnd(event: DragEndEvent) {
        const sourceTask =
            (event.active.data.current?.task as CalendarTaskModel | undefined) ?? null;
        const dragKind = event.active.data.current?.dragKind as string | undefined;
        const targetDate = event.over ? dateFromDropId(event.over.id) : null;
        setActiveTask(null);
        if (!sourceTask || !targetDate) return;
        const task = taskWithScenario(sourceTask);
        setSelectedDate(targetDate);
        if (dragKind === "interval") {
            const moved = moveTaskInterval(task, targetDate);
            changeDates(task, { startDate: moved.startDate, dueDate: moved.dueDate });
        } else if (dragKind === "unscheduled") {
            changeDates(task, { startDate: targetDate, dueDate: targetDate });
        } else {
            changeDates(task, { dueDate: targetDate });
        }
    }

    function resizeTask(task: CalendarTaskModel, edge: "start" | "end", deltaDays: number) {
        const effectiveTask = taskWithScenario(task);
        const resized = resizeTaskInterval(effectiveTask, edge, deltaDays);
        if (resized) {
            changeDates(effectiveTask, { startDate: resized.startDate, dueDate: resized.dueDate });
        }
    }

    const error = calendarQuery.error ?? unscheduledQuery.error;
    const selectedTasks = groupedTasks.get(activeSelectedDate) ?? [];
    const hasFilters = FILTER_NAMES.some((name) => searchParams.has(name));

    return (
        <div className="scrollbar-thin h-full overflow-y-auto bg-app">
            <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-3 px-3 py-3 sm:px-5 sm:py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <CalendarToolbar
                        title={timelineTitle(range, scale)}
                        scale={scale}
                        onScaleChange={changeScale}
                        onToday={goToday}
                        onPrevious={() => movePeriod(-1)}
                        onNext={() => movePeriod(1)}
                    />
                    <div className="flex flex-wrap items-center gap-1.5">
                        <Button
                            size="sm"
                            variant={isScenarioMode ? "primary" : "secondary"}
                            icon={<Beaker size={13} aria-hidden="true" />}
                            onClick={() => {
                                if (isScenarioMode) stopScenario();
                                else setScenarioMode(true);
                            }}
                        >
                            {isScenarioMode ? "Сценарий активен" : "Что, если"}
                        </Button>
                        <Filter size={13} className="text-disabled" aria-hidden="true" />
                        <Select
                            aria-label="Фильтр календаря по стадии"
                            value={stageFilter}
                            className="w-auto min-w-32"
                            onChange={(event) => setViewParam("stage", event.target.value)}
                        >
                            <option value="">Все стадии</option>
                            {calendarQuery.data?.stages.map((stage) => (
                                <option key={stage.id} value={stage.id}>
                                    {stage.name}
                                </option>
                            ))}
                        </Select>
                        <Select
                            aria-label="Фильтр календаря по приоритету"
                            value={priorityFilter}
                            className="w-auto min-w-32"
                            onChange={(event) => setViewParam("priority", event.target.value)}
                        >
                            <option value="">Все приоритеты</option>
                            {PRIORITY_ORDER.map((priority: TaskPriority) => (
                                <option key={priority} value={priority}>
                                    {PRIORITY_LABELS[priority]}
                                </option>
                            ))}
                        </Select>
                        <Select
                            aria-label="Фильтр календаря по исполнителю"
                            value={assigneeFilter}
                            className="w-auto min-w-36"
                            onChange={(event) => setViewParam("assignee", event.target.value)}
                        >
                            <option value="">Все исполнители</option>
                            {calendarQuery.data?.assignees.map((assignee) => (
                                <option key={assignee} value={assignee}>
                                    {assignee}
                                </option>
                            ))}
                        </Select>
                        <Select
                            aria-label="Фильтр календаря по разделу ИСР"
                            value={wbsFilter}
                            className="w-auto min-w-36"
                            onChange={(event) => setViewParam("wbs", event.target.value)}
                        >
                            <option value="">Вся ИСР</option>
                            {calendarQuery.data?.wbs_nodes.map((node) => (
                                <option key={node.id} value={node.id}>
                                    {node.title}
                                </option>
                            ))}
                        </Select>
                        {hasFilters && (
                            <button
                                type="button"
                                onClick={resetFilters}
                                className="h-7 px-2 text-[11px] text-muted hover:text-accent"
                            >
                                Сбросить
                            </button>
                        )}
                    </div>
                </div>

                {error && <ErrorMessage message={(error as Error).message} />}
                {(calendarQuery.isPending || unscheduledQuery.isPending) && (
                    <div
                        role="status"
                        aria-label="Загрузка временной карты"
                        className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]"
                    >
                        <Skeleton className="h-[620px] w-full" />
                        <div className="flex flex-col gap-3">
                            <Skeleton className="h-36 w-full" />
                            <Skeleton className="h-72 w-full" />
                        </div>
                    </div>
                )}

                {calendarQuery.data && unscheduledQuery.data && (
                    <DndContext
                        sensors={sensors}
                        onDragStart={handleDragStart}
                        onDragEnd={handleDragEnd}
                        onDragCancel={() => setActiveTask(null)}
                    >
                        {calendarQuery.data.tasks.length === 0 &&
                            unscheduledTasks.length === 0 &&
                            calendarQuery.data.project.due_date === null && (
                                <EmptyState
                                    title="Временная карта пока пуста"
                                    description="Добавьте плановые даты задаче или проекту — работа появится на шкале."
                                    icon={<CalendarRange size={24} />}
                                    className="mb-3 py-6"
                                />
                            )}
                        <div className="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
                            <div className="hidden min-w-0 md:block">
                                <TimelineGrid
                                    days={days}
                                    range={range}
                                    scale={scale}
                                    tasks={calendarQuery.data.tasks}
                                    wbsNodes={calendarQuery.data.wbs_nodes}
                                    stagesById={stagesById}
                                    milestones={calendarQuery.data.milestones}
                                    dependencies={calendarQuery.data.dependencies}
                                    scenarioChanges={scenarioPreview?.changes ?? []}
                                    selectedDate={activeSelectedDate}
                                    onSelectDate={setSelectedDate}
                                    onOpenTask={setSelectedTaskId}
                                    onScheduleTask={(task) =>
                                        setDeadlineTask(taskWithScenario(task))
                                    }
                                    onResizeTask={resizeTask}
                                />
                            </div>
                            <div className="flex min-w-0 flex-col gap-3">
                                {isScenarioMode && (
                                    <ScenarioPanel
                                        preview={scenarioPreview}
                                        isPreviewing={previewScenarioMutation.isPending}
                                        isApplying={applyScenarioMutation.isPending}
                                        onCancel={stopScenario}
                                        onApply={() => {
                                            if (
                                                scenarioPreview &&
                                                window.confirm(
                                                    `Применить изменения к ${scenarioPreview.changes.length} задачам?`,
                                                )
                                            ) {
                                                applyScenarioMutation.mutate(scenarioPreview);
                                            }
                                        }}
                                    />
                                )}
                                <ProjectPulse summary={calendarQuery.data.summary} />
                                {!isScenarioMode && (
                                    <>
                                        <MilestonePanel
                                            milestones={milestonesQuery.data ?? []}
                                            projectDueDate={calendarQuery.data.project.due_date}
                                            isLoading={milestonesQuery.isPending}
                                            error={(milestonesQuery.error as Error | null) ?? null}
                                            isSaving={isMilestoneSaving}
                                            onCreate={() => setMilestoneDialog("new")}
                                            onEdit={setMilestoneDialog}
                                            onDelete={(milestone) => {
                                                if (
                                                    window.confirm(
                                                        `Удалить веху «${milestone.title}»?`,
                                                    )
                                                ) {
                                                    deleteMilestoneMutation.mutate(milestone.id);
                                                }
                                            }}
                                        />
                                        <DependencyPanel
                                            dependencies={calendarQuery.data.dependencies}
                                            tasks={tasksQuery.data ?? []}
                                            isSaving={isDependencySaving}
                                            onCreate={() => setDependencyDialogOpen(true)}
                                            onDelete={(dependency) => {
                                                if (
                                                    window.confirm(
                                                        "Удалить зависимость задач?",
                                                    )
                                                ) {
                                                    deleteDependencyMutation.mutate(
                                                        dependency.id,
                                                    );
                                                }
                                            }}
                                        />
                                    </>
                                )}
                                <div className="md:hidden">
                                    <label
                                        className="mb-1 block text-[11px] text-muted"
                                        htmlFor="calendar-agenda-date"
                                    >
                                        День agenda
                                    </label>
                                    <Input
                                        id="calendar-agenda-date"
                                        type="date"
                                        value={activeSelectedDate}
                                        min={range.dateFrom}
                                        max={range.dateTo}
                                        onChange={(event) => setSelectedDate(event.target.value)}
                                    />
                                </div>
                                <CalendarAgenda
                                    selectedDate={activeSelectedDate}
                                    tasks={selectedTasks}
                                    unscheduledTasks={unscheduledTasks}
                                    stagesById={stagesById}
                                    hasMoreUnscheduled={unscheduledQuery.hasNextPage}
                                    isLoadingMore={unscheduledQuery.isFetchingNextPage}
                                    onOpenTask={setSelectedTaskId}
                                    onScheduleTask={(task) =>
                                        setDeadlineTask(taskWithScenario(task))
                                    }
                                    onLoadMore={() => void unscheduledQuery.fetchNextPage()}
                                />
                                <CalendarRecentChanges
                                    changes={calendarQuery.data.recent_changes}
                                    onOpenTask={setSelectedTaskId}
                                />
                            </div>
                        </div>
                        <DragOverlay>
                            {activeTask && (
                                <div className="w-64">
                                    <CalendarTask
                                        task={activeTask}
                                        stageName={stagesById.get(activeTask.stage_id)?.name}
                                        onOpen={() => undefined}
                                    />
                                </div>
                            )}
                        </DragOverlay>
                    </DndContext>
                )}
            </div>
            {deadlineTask && (
                <DeadlineDialog
                    key={`${deadlineTask.id}:${deadlineTask.start_date ?? "none"}:${deadlineTask.due_date ?? "none"}`}
                    task={deadlineTask}
                    isSaving={deadlineMutation.isPending || baselineMutation.isPending}
                    onClose={() => setDeadlineTask(null)}
                    onSave={(startDate, dueDate) => {
                        changeDates(deadlineTask, { startDate, dueDate });
                        setDeadlineTask(null);
                    }}
                    onFixBaseline={
                        isScenarioMode
                            ? undefined
                            : () => {
                                  baselineMutation.mutate(deadlineTask.id);
                                  setDeadlineTask(null);
                              }
                    }
                />
            )}
            {milestoneDialog && (
                <MilestoneDialog
                    key={milestoneDialog === "new" ? "new" : milestoneDialog.id}
                    milestone={milestoneDialog === "new" ? null : milestoneDialog}
                    initialDueDate={project.due_date ?? today}
                    wbsNodes={calendarQuery.data?.wbs_nodes ?? []}
                    isSaving={isMilestoneSaving}
                    onClose={() => setMilestoneDialog(null)}
                    onSave={(data) => {
                        if (milestoneDialog === "new") {
                            createMilestoneMutation.mutate(data);
                        } else {
                            updateMilestoneMutation.mutate({
                                milestoneId: milestoneDialog.id,
                                data,
                            });
                        }
                    }}
                />
            )}
            {isDependencyDialogOpen && (
                <DependencyDialog
                    tasks={tasksQuery.data ?? []}
                    isLoading={tasksQuery.isPending}
                    isSaving={createDependencyMutation.isPending}
                    onClose={() => setDependencyDialogOpen(false)}
                    onSave={(data) => createDependencyMutation.mutate(data)}
                />
            )}
        </div>
    );
}
