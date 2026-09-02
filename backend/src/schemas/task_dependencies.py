from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models.task_dependencies import TaskDependencyType


class TaskDependencySchema(BaseModel):
    """Направленная зависимость двух задач проекта."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    predecessor_task_id: int
    successor_task_id: int
    dependency_type: TaskDependencyType
    lag_days: int
    created_at: datetime


class TaskDependencyCreateSchema(BaseModel):
    """Тело создания зависимости Finish-to-Start."""

    predecessor_task_id: int = Field(..., gt=0)
    successor_task_id: int = Field(..., gt=0)
    dependency_type: TaskDependencyType = TaskDependencyType.FINISH_TO_START
    lag_days: int = Field(0, ge=0, le=3650)
