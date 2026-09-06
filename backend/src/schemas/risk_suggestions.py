"""Контракты AI-черновиков; регистрация выполняется отдельным CRUD-запросом."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.enums import RiskRating, RiskResponseStrategy


class RiskSuggestionFieldsSchema(BaseModel):
    """Редактируемое содержание предложения без серверных полей реестра."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Предлагаемое рисковое событие.",
        examples=["Задержка интеграции"],
    )
    description: str = Field(
        min_length=1,
        max_length=3000,
        description="Причины и последствия, требующие проверки человеком.",
        examples=["Согласование контракта API ещё не завершено."],
    )
    probability: RiskRating = Field(description="Предварительная вероятность.", examples=["MEDIUM"])
    impact: RiskRating = Field(description="Предварительное влияние.", examples=["HIGH"])
    response_strategy: RiskResponseStrategy = Field(
        description="Предлагаемая стратегия.", examples=["MITIGATE"]
    )
    mitigation_plan: str = Field(
        max_length=3000,
        description="Предложение превентивных мер.",
        examples=["Согласовать контракт API."],
    )
    response_plan: str = Field(
        max_length=3000,
        description="Предложение действий при наступлении.",
        examples=["Использовать резервный адаптер."],
    )


class RiskSuggestionDraftSchema(RiskSuggestionFieldsSchema):
    """Внутренний ответ модели с проверяемыми ссылками на снимок."""

    task_key: str | None = Field(
        None,
        max_length=32,
        description="Ключ существующей задачи из снимка либо null.",
        examples=["PROJ-12"],
    )
    evidence_refs: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(
        min_length=1,
        max_length=5,
        description="Идентификаторы подтверждающих источников из снимка.",
        examples=[["S2", "S3"]],
    )


class RiskSuggestionDraftSetSchema(BaseModel):
    """Ограниченный набор черновиков модели."""

    suggestions: list[RiskSuggestionDraftSchema] = Field(
        max_length=5,
        description="До пяти предложений; пустой список при недостатке оснований.",
        examples=[[]],
    )


class RiskSuggestionSchema(RiskSuggestionFieldsSchema):
    """Предложение после проверки ссылок, ещё не сохранённое в реестр."""

    task_id: int | None = Field(
        None, description="Задача, проверенная по текущему проекту.", examples=[12]
    )
    evidence: list[str] = Field(
        description="Фактические основания из серверного снимка.",
        examples=[["PROJ-12: контракт API ожидает согласования"]],
    )


class RiskSuggestionsSchema(BaseModel):
    """Предложения для просмотра, редактирования и явного подтверждения."""

    suggestions: list[RiskSuggestionSchema] = Field(
        description="Проверенные предложения, не создающие записи автоматически.", examples=[[]]
    )
