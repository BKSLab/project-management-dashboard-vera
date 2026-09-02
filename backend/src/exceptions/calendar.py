from fastapi import status

from src.exceptions.base import ServiceError


class CalendarServiceError(ServiceError):
    """Ошибка бизнес-операции календаря проекта."""

    detail = "Не удалось получить данные календаря."


class CalendarRangeError(CalendarServiceError):
    """Некорректный диапазон календаря."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT

    def __init__(self, details: str):
        super().__init__(error_details=details)

    @property
    def detail(self) -> str:
        return self.error_details


class CalendarFilterError(CalendarServiceError):
    """Фильтр ссылается на объект вне выбранного проекта."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Недопустимое значение фильтра календаря."

    def __init__(self, filter_name: str):
        self.filter_name = filter_name
        super().__init__(error_details=f"Недопустимый фильтр {filter_name}.")


class CalendarScenarioConflictError(CalendarServiceError):
    """Предложенный сценарий нарушает ограничения расписания."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, details: str = "Сценарий содержит конфликты расписания."):
        super().__init__(error_details=details)

    @property
    def detail(self) -> str:
        return self.error_details


class CalendarScenarioVersionConflictError(CalendarServiceError):
    """Задача изменилась после preview сценария."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Данные задач изменились после preview. Обновите сценарий."

    def __init__(self):
        super().__init__(error_details=self.detail)
