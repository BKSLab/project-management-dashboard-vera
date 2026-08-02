"""Переиспользуемые описания ошибок OpenAPI для API v1."""

NOT_FOUND_RESPONSE = {
    "description": "Запрашиваемый объект не найден.",
    "content": {"application/json": {"example": {"detail": "Объект не найден."}}},
}
CONFLICT_RESPONSE = {
    "description": "Операция конфликтует с текущим состоянием данных.",
    "content": {"application/json": {"example": {"detail": "Операция недоступна."}}},
}
VALIDATION_RESPONSE = {
    "description": "Параметры или тело запроса не прошли валидацию.",
    "content": {"application/json": {"example": {"detail": "Ошибка валидации."}}},
}
SERVER_ERROR_RESPONSE = {
    "description": "Внутренняя ошибка обработки запроса.",
    "content": {"application/json": {"example": {"detail": "Внутренняя ошибка."}}},
}
