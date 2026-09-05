from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class UsersRepositoryError(RepositoryError):
    """Ошибка доступа к пользователям."""

    detail = "Ошибка базы данных при обработке пользователей."


class UsernameAlreadyExistsRepositoryError(UsersRepositoryError):
    """Логин уже занят на уровне базы данных."""

    def __init__(self, username: str):
        self.username = username
        super().__init__(error_details=f"Логин {username!r} уже занят.")


class UsersServiceError(ServiceError):
    """Ошибка бизнес-операции с пользователями."""

    detail = "Не удалось выполнить операцию с пользователем."


class UserNotFoundError(UsersServiceError):
    """Пользователь не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(error_details=f"Пользователь id={user_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Пользователь с id={self.user_id} не найден."


class UsernameConflictError(UsersServiceError):
    """Логин уже занят."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, username: str):
        self.username = username
        super().__init__(error_details=f"Логин {username!r} уже занят.")

    @property
    def detail(self) -> str:
        return f"Логин «{self.username}» уже занят."


class AvatarNotFoundError(UsersServiceError):
    """У пользователя нет загруженной фотографии."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Фотография не загружена."

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(error_details=f"У пользователя id={user_id} нет фотографии.")


class AvatarTooLargeError(UsersServiceError):
    """Файл фотографии превышает допустимый размер."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        super().__init__(error_details=f"Файл больше {max_bytes} байт.")

    @property
    def detail(self) -> str:
        return f"Файл больше {self.max_bytes // (1024 * 1024)} МБ."


class AvatarUnsupportedTypeError(UsersServiceError):
    """Тип файла не подходит для фотографии профиля."""

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    detail = "Загрузить можно только изображение: JPEG, PNG или WebP."

    def __init__(self, content_type: str):
        self.content_type = content_type
        super().__init__(error_details=f"Неподдерживаемый тип {content_type!r}.")


class AvatarOperationError(UsersServiceError):
    """Сервис не смог выполнить операцию с фотографией профиля.

    Ошибка хранилища преобразуется сюда на границе сервиса: наружу не
    должно уходить исключение слоя файлов.
    """

    detail = "Не удалось выполнить операцию с фотографией."
