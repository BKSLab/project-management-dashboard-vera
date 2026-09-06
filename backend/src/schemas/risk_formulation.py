"""Контракт AI-помощи для формулировок полей риска."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.enums import RiskRating, RiskResponseStrategy, RiskStatus


class RiskFormulationField(StrEnum):
    DESCRIPTION = "description"
    MITIGATION_PLAN = "mitigation_plan"
    RESPONSE_PLAN = "response_plan"


class RiskFormulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: RiskFormulationField
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=20000)
    probability: RiskRating
    impact: RiskRating
    response_strategy: RiskResponseStrategy
    status: RiskStatus = RiskStatus.OPEN
    mitigation_plan: str = Field("", max_length=20000)
    response_plan: str = Field("", max_length=20000)

    @field_validator("title", "description", "mitigation_plan", "response_plan")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if "\x00" in value:
            raise ValueError("Текст не может содержать нулевой символ.")
        return value


class RiskFormulationResponse(BaseModel):
    field: RiskFormulationField
    text: str = Field(..., min_length=1, max_length=20000)
    warnings: list[str] = Field(default_factory=list)
