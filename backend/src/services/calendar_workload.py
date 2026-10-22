"""Календарь проектных и разовых задач с доступом по локальным назначениям."""

import logging
from datetime import date

from src.exceptions.base import RepositoryError
from src.exceptions.calendar import CalendarServiceError
from src.exceptions.projects import ProjectNotFoundError
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.users import UsersRepository
from src.schemas.calendar_workload import (
    CalendarWorkloadResponseSchema,
    WorkloadDaySchema,
    WorkloadOtherTaskSchema,
    WorkloadPersonSchema,
)
from src.services.calendar import validate_calendar_range
from src.services.tasks import PERSONAL_TASK_KEY, build_task_key
from src.utils.workload import DayLoad, load_level, spread_task

logger = logging.getLogger(__name__)

MAX_WORKLOAD_ROWS = 5000
PERSONAL_SOURCE_NAME = "Разовые задачи"


class CalendarWorkloadService:
    """Считает загрузку участников проекта по рабочим дням периода."""

    def __init__(
        self,
        *,
        projects_repository: ProjectsRepository,
        members_repository: ProjectMembersRepository,
        users_repository: UsersRepository,
        tasks_repository: TasksRepository,
    ) -> None:
        self.projects_repository = projects_repository
        self.members_repository = members_repository
        self.users_repository = users_repository
        self.tasks_repository = tasks_repository

    async def get_workload(
        self,
        *,
        project_id: int,
        viewer_id: int,
        date_from: date,
        date_to: date,
    ) -> CalendarWorkloadResponseSchema:
        """Собирает загрузку команды проекта.

        Args:
            project_id: Проект (доступ смотрящего уже проверен маршрутом).
            viewer_id: Кто смотрит — от него зависит, какие чужие задачи раскрыть.
            date_from: Первый день периода включительно.
            date_to: Последний день периода включительно.

        Returns:
            Люди команды с нагрузкой по дням.

        Raises:
            CalendarRangeError: Если период некорректен.
            ProjectNotFoundError: Если проекта нет.
            CalendarServiceError: Если прочитать данные не удалось.
        """
        validate_calendar_range(date_from=date_from, date_to=date_to)
        try:
            project = await self.projects_repository.get_by_id(project_id=project_id)
            if project is None:
                raise ProjectNotFoundError(project_id=project_id)
            members = await self.members_repository.get_for_project(project_id)
            viewer_projects = set(
                await self.members_repository.get_project_ids_for_user(user_id=viewer_id)
            )
            rows = await self.tasks_repository.get_workload_rows(
                user_ids={member.user_id for member in members},
                date_from=date_from,
                date_to=date_to,
                limit=MAX_WORKLOAD_ROWS + 1,
            )
        except RepositoryError as error:
            logger.error("❌ Не удалось собрать загрузку проекта id=%s.", project_id, exc_info=True)
            raise CalendarServiceError(str(error)) from error

        truncated = len(rows) > MAX_WORKLOAD_ROWS
        rows = rows[:MAX_WORKLOAD_ROWS]

        def visible(row) -> bool:
            return (
                row.project_id in viewer_projects
                if row.project_id is not None
                else row.user_id == viewer_id
            )

        by_user: dict[int, list] = {}
        for row in rows:
            by_user.setdefault(row.user_id, []).append(row)

        people: list[WorkloadPersonSchema] = []
        for member in members:
            inside: dict[date, DayLoad] = {}
            outside: dict[date, DayLoad] = {}
            visible_outside: set[str] = set()
            other_tasks: list[WorkloadOtherTaskSchema] = []
            hidden = 0
            for row in by_user.get(member.user_id, []):
                key, source_name = _task_key_and_source(row)
                own = row.project_id == project_id
                spread_task(
                    inside if own else outside,
                    key=key,
                    start_date=row.start_date,
                    due_date=row.due_date,
                    date_from=date_from,
                    date_to=date_to,
                )
                if own:
                    continue
                if visible(row):
                    visible_outside.add(key)
                    other_tasks.append(
                        WorkloadOtherTaskSchema(
                            key=key,
                            title=row.title,
                            source_name=source_name,
                            start_date=row.start_date,
                            due_date=row.due_date,
                        )
                    )
                else:
                    hidden += 1
            days = []
            for day in sorted(inside.keys() | outside.keys()):
                mine = inside.get(day, DayLoad())
                other = outside.get(day, DayLoad())
                days.append(
                    WorkloadDaySchema(
                        date=day,
                        project_tasks=mine.tasks,
                        project_keys=mine.keys,
                        other_tasks=other.tasks,
                        other_keys=[key for key in other.keys if key in visible_outside],
                        level=load_level(
                            tasks=mine.tasks + other.tasks,
                        ),
                    )
                )
            user = member.user
            people.append(
                WorkloadPersonSchema(
                    user_id=member.user_id,
                    name=" ".join(part for part in (user.last_name, user.first_name) if part)
                    or user.username,
                    days=days,
                    other_tasks=other_tasks,
                    other_hidden=hidden,
                )
            )
        logger.info(
            "✅ Загрузка проекта id=%s собрана: людей %s, строк %s.",
            project_id,
            len(people),
            len(rows),
        )
        return CalendarWorkloadResponseSchema(
            date_from=date_from, date_to=date_to, people=people, truncated=truncated
        )


def _task_key_and_source(row) -> tuple[str, str]:
    """Ключ задачи вида KEY-42 и подпись её источника."""
    if row.project_id is not None:
        return build_task_key(project_key=row.project_key, number=row.number), row.project_name
    return build_task_key(project_key=PERSONAL_TASK_KEY, number=row.number), PERSONAL_SOURCE_NAME
