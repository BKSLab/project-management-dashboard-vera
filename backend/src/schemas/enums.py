"""Перечисления публичного контракта.

Значения приоритета — часть контракта API и одновременно тип столбца в
базе. Объявлены они здесь, а не в модели: транспорт не должен зависеть от
слоя персистентности ради константы, которую сам же и отдаёт наружу.
Направление зависимости обратное — модель ссылается на общее
перечисление.
"""

import enum


class TaskPriority(str, enum.Enum):
    """Приоритет задачи."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskRole(str, enum.Enum):
    """Роль, ответственная за выполнение задачи."""

    PM = "PM"
    BE = "BE"
    FE = "FE"
    UXR = "UXR"
    UXD = "UXD"
    EXPERT = "EXPERT"
    QA = "QA"
    BA = "BA"
    MKT = "MKT"


class RiskRating(str, enum.Enum):
    """Трёхуровневая шкала вероятности, влияния и итоговой оценки риска."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskStatus(str, enum.Enum):
    """Состояние рискового события независимо от стадий задач."""

    OPEN = "OPEN"
    MITIGATING = "MITIGATING"
    OCCURRED = "OCCURRED"
    CLOSED = "CLOSED"


class RiskResponseStrategy(str, enum.Enum):
    """Выбранная человеком стратегия работы с риском."""

    AVOID = "AVOID"
    MITIGATE = "MITIGATE"
    TRANSFER = "TRANSFER"
    ACCEPT = "ACCEPT"


class RiskSource(str, enum.Enum):
    """Происхождение зарегистрированного человеком риска."""

    MANUAL = "MANUAL"
    AI_SUGGESTED = "AI_SUGGESTED"


class RiskReasonCode(str, enum.Enum):
    """Проверяемые причины внимания к реестру рисков."""

    HIGH_OPEN_RISK = "HIGH_OPEN_RISK"
    RISK_REVIEW_OVERDUE = "RISK_REVIEW_OVERDUE"
    RISK_WITHOUT_OWNER = "RISK_WITHOUT_OWNER"
    RISK_WITHOUT_MITIGATION = "RISK_WITHOUT_MITIGATION"
    RISK_OCCURRED = "RISK_OCCURRED"
