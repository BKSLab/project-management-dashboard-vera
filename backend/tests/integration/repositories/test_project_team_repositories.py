from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_members import ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_participants import TaskParticipantRole
from src.db.models.users import User
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.task_participants import TaskParticipantsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.users import UsersRepository


async def test_project_members_are_loaded_with_safe_user_identity(
    db_session: AsyncSession,
    project: Project,
    user: User,
) -> None:
    repository = ProjectMembersRepository(db_session)
    await repository.save(
        data={"project_id": project.id, "user_id": user.id, "role": ProjectRole.OWNER}
    )

    members = await repository.get_for_project(project_id=project.id)

    assert len(members) == 1
    assert members[0].user.username == "owner"
    assert members[0].role is ProjectRole.OWNER


async def test_task_participants_round_trip_and_follow_membership_cascade(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    user: User,
) -> None:
    users_repository = UsersRepository(db_session)
    executor = await users_repository.save(
        data={
            "username": "executor",
            "password_hash": "hash",
            "last_name": "Исполнителей",
            "first_name": "Ирина",
            "is_active": True,
        }
    )
    members_repository = ProjectMembersRepository(db_session)
    owner_member = await members_repository.save(
        data={"project_id": project.id, "user_id": user.id, "role": ProjectRole.OWNER}
    )
    executor_member = await members_repository.save(
        data={"project_id": project.id, "user_id": executor.id, "role": ProjectRole.MEMBER}
    )
    task = await TasksRepository(db_session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Назначенная задача",
            "position": 1000,
        }
    )
    participants_repository = TaskParticipantsRepository(db_session)
    await participants_repository.replace_for_task(
        task_id=task.id,
        assignments=[
            {
                "project_member_id": executor_member.id,
                "role": TaskParticipantRole.EXECUTOR,
            },
            {
                "project_member_id": owner_member.id,
                "role": TaskParticipantRole.REPORTER,
            },
        ],
    )

    grouped = await participants_repository.get_by_task_ids([task.id])

    assert [item.role for item in grouped[task.id]] == [
        TaskParticipantRole.EXECUTOR,
        TaskParticipantRole.REPORTER,
    ]
    assert grouped[task.id][0].project_member.user.username == "executor"

    await members_repository.delete(member=executor_member)
    remaining = await participants_repository.get_by_task_ids([task.id])
    assert [item.role for item in remaining[task.id]] == [TaskParticipantRole.REPORTER]
