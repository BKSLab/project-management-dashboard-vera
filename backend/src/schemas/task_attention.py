from pydantic import BaseModel, Field


class TaskViewSchema(BaseModel):
    revision: int = Field(
        ..., ge=1, description="Версия содержимого при открытии карточки.", examples=[3]
    )
    deadline_revision: int = Field(
        ..., ge=1, description="Версия срока при открытии карточки.", examples=[1]
    )
    overdue: bool = Field(..., description="Был ли срок нарушен при открытии.", examples=[False])


class TaskAttentionItem(TaskViewSchema):
    task_id: int = Field(..., description="Идентификатор задачи.", examples=[42])
    is_new: bool = Field(
        ..., description="Карточка ни разу не открыта этим человеком.", examples=[True]
    )
    is_overdue: bool = Field(
        ..., description="Нарушение срока ещё не просмотрено.", examples=[False]
    )
    is_updated: bool = Field(
        ..., description="После просмотра появились изменения или комментарии.", examples=[False]
    )


class TaskAttentionSnapshot(BaseModel):
    new_tasks: int = Field(..., description="Непросмотренные новые задачи.", examples=[2])
    overdue_tasks: int = Field(
        ..., description="Задачи с непросмотренным нарушением срока.", examples=[1]
    )
    updated_tasks: int = Field(
        ..., description="Задачи с непросмотренными изменениями.", examples=[3]
    )
    total: int = Field(
        ..., description="Уникальные задачи с хотя бы одним непросмотренным сигналом.", examples=[5]
    )
    items: list[TaskAttentionItem] = Field(
        ..., description="Персональные признаки задач без ограничения 500 строк."
    )
