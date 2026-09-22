"""Паспорт, команда, стикеры и реестр рисков проекта."""

from src.agent.tools import AgentToolContext
from src.schemas import project_tool_inputs as inputs
from src.schemas.project_risks import ProjectRiskFilters
from src.services.agent_action_helpers import page
from src.services.agent_tool_scope import AgentProjectToolScope


async def get_project(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.EmptyInput
) -> dict:
    """Читает паспорт, статистику и историю сроков проекта."""
    return {
        "project": (await db.projects.get_project(ctx.project_id)).model_dump(mode="json"),
        "statistics": (await db.projects.get_project_stats(ctx.project_id)).model_dump(mode="json"),
        "deadline_history": [
            item.model_dump(mode="json")
            for item in await db.projects.get_deadline_history(ctx.project_id)
        ],
        "source_id": f"project:{ctx.project_id}",
    }


async def update_project(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.ProjectChangesInput
) -> dict:
    """Обновляет паспорт и настройки с проверкой причин переноса срока."""
    await db.access.ensure_project_ownership(project_id=ctx.project_id, user_id=ctx.user_id)
    item = await db.projects.update_project(
        ctx.project_id, args.model_dump(exclude_unset=True), updated_by_user_id=ctx.user_id
    )
    return {"project": item.model_dump(mode="json"), "source_id": f"project:{ctx.project_id}"}


async def list_members(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.PageInput
) -> dict:
    """Читает публичные карточки участников без личных контактов."""
    return page(await db.members.get_member_list(ctx.project_id), args)


async def add_member(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.MemberAddInput
) -> dict:
    """Владелец добавляет существующего пользователя по точному логину."""
    await db.access.ensure_project_ownership(project_id=ctx.project_id, user_id=ctx.user_id)
    item = await db.members.add_member(ctx.project_id, args.username)
    return {"member": item.model_dump(mode="json"), "source_id": f"member:{item.id}"}


async def remove_member(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.MemberInput
) -> dict:
    """Владелец удаляет участника с очисткой назначений, сохраняя себя."""
    await db.access.ensure_project_ownership(project_id=ctx.project_id, user_id=ctx.user_id)
    await db.members.remove_member(ctx.project_id, args.user_id)
    return {"removed": True, "user_id": args.user_id}


async def transfer_ownership(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.MemberInput
) -> dict:
    """Передаёт роль владельца другому участнику после отдельного решения."""
    await db.access.ensure_project_ownership(project_id=ctx.project_id, user_id=ctx.user_id)
    item = await db.projects.transfer_ownership(ctx.project_id, args.user_id, ctx.user_id)
    return {"project": item.model_dump(mode="json"), "source_id": f"project:{ctx.project_id}"}


async def list_stickers(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.PageInput
) -> dict:
    """Возвращает стикеры вместе с ревизиями, координатами и связями."""
    return page(await db.stickers.list_stickers(ctx.project_id), args)


async def create_sticker(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.StickerCreateInput
) -> dict:
    """Создаёт стикер с реальным авторством участника."""
    item = await db.stickers.create_sticker(
        project_id=ctx.project_id,
        data=args,
        author_id=ctx.user_id,
        author_username=ctx.username,
        author_display_name=ctx.display_name,
    )
    return {"sticker": item.model_dump(mode="json"), "source_id": f"sticker:{item.id}"}


async def update_sticker(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.StickerUpdateInput
) -> dict:
    """Меняет стикер с проверкой ревизии."""
    item = await db.stickers.update_sticker(
        project_id=ctx.project_id, sticker_id=args.sticker_id, data=args.changes
    )
    return {"sticker": item.model_dump(mode="json"), "source_id": f"sticker:{item.id}"}


async def move_sticker(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.StickerMoveInput
) -> dict:
    """Меняет координаты и размер стикера."""
    item = await db.stickers.move_sticker(
        project_id=ctx.project_id, sticker_id=args.sticker_id, data=args.position
    )
    return {"sticker": item.model_dump(mode="json"), "source_id": f"sticker:{item.id}"}


async def delete_sticker(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.StickerDeleteInput
) -> dict:
    """Удаляет прочитанную ревизию стикера."""
    await db.stickers.delete_sticker(
        project_id=ctx.project_id, sticker_id=args.sticker_id, revision=args.revision
    )
    return {"deleted": True, "sticker_id": args.sticker_id}


async def list_risks(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.RiskListInput
) -> dict:
    """Возвращает постраничный реестр зарегистрированных рисков."""
    return (
        await db.risks.list_risks(
            project_id=ctx.project_id,
            user_id=ctx.user_id,
            filters=ProjectRiskFilters.model_validate(
                args.model_dump(exclude={"page", "page_size"})
            ),
            page=args.page,
            page_size=args.page_size,
        )
    ).model_dump(mode="json")


async def get_risk(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.RiskInput
) -> dict:
    """Возвращает риск, его владельца, оценки, планы и связи."""
    item = await db.risks.get_risk(
        project_id=ctx.project_id, risk_id=args.risk_id, user_id=ctx.user_id
    )
    return {"risk": item.model_dump(mode="json"), "source_id": f"risk:{item.id}"}


async def create_risk(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.RiskCreateInput
) -> dict:
    """Создаёт риск с доменной проверкой участника и связанной задачи."""
    item = await db.risks.create_risk(project_id=ctx.project_id, user_id=ctx.user_id, data=args)
    return {"risk": item.model_dump(mode="json"), "source_id": f"risk:{item.id}"}


async def update_risk(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.RiskUpdateInput
) -> dict:
    """Редактирует риск или переводит его в CLOSED через обычную модель статусов."""
    item = await db.risks.update_risk(
        project_id=ctx.project_id, user_id=ctx.user_id, risk_id=args.risk_id, data=args.changes
    )
    return {"risk": item.model_dump(mode="json"), "source_id": f"risk:{item.id}"}


async def delete_risk(
    db: AgentProjectToolScope, ctx: AgentToolContext, args: inputs.RiskInput
) -> dict:
    """Удаляет риск из проекта после подтверждения."""
    await db.risks.delete_risk(project_id=ctx.project_id, user_id=ctx.user_id, risk_id=args.risk_id)
    return {"deleted": True, "risk_id": args.risk_id}
