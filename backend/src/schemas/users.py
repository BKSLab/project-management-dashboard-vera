from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,50}$"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72


class UserSchema(BaseModel):
    """Карточка пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Уникальный идентификатор пользователя.", examples=[1])
    username: str = Field(..., description="Логин пользователя.", examples=["boris"])
    last_name: str = Field(..., description="Фамилия.", examples=["Кузнецов"])
    first_name: str = Field(..., description="Имя.", examples=["Борис"])
    middle_name: str | None = Field(None, description="Отчество.", examples=["Сергеевич"])
    email: str | None = Field(
        None,
        description="Электронная почта.",
        examples=["boris@example.com"],
    )
    phone: str | None = Field(None, description="Телефон.", examples=["+7 900 000-00-00"])
    telegram: str | None = Field(None, description="Ник в Telegram.", examples=["@boris"])
    has_avatar: bool = Field(..., description="Загружена ли фотография.", examples=[True])
    created_at: datetime = Field(
        ...,
        description="Дата регистрации.",
        examples=["2026-09-01T10:00:00Z"],
    )


class PasswordPairMixin(BaseModel):
    """Проверка совпадения пароля и его подтверждения.

    Клиент проверяет совпадение до отправки ради быстрого отклика, но
    гарантией остаётся сервер.
    """

    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="Пароль.",
        examples=["надёжный-пароль"],
    )
    password_confirm: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="Повтор пароля.",
        examples=["надёжный-пароль"],
    )

    @model_validator(mode="after")
    def check_passwords_match(self) -> Self:
        """Проверяет, что пароль и подтверждение совпадают."""
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают.")
        return self


class UserRegisterSchema(PasswordPairMixin):
    """Тело запроса регистрации."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "boris",
                "password": "надёжный-пароль",
                "password_confirm": "надёжный-пароль",
                "last_name": "Кузнецов",
                "first_name": "Борис",
                "invite_code": "код-приглашения",
            }
        }
    )

    username: str = Field(
        ...,
        pattern=USERNAME_PATTERN,
        description="Логин: латиница, цифры, точка, дефис и подчёркивание.",
        examples=["boris"],
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Фамилия.",
        examples=["Кузнецов"],
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Имя.",
        examples=["Борис"],
    )
    middle_name: str | None = Field(
        None,
        max_length=100,
        description="Отчество; необязательно.",
        examples=["Сергеевич"],
    )
    email: str | None = Field(
        None,
        max_length=255,
        description="Электронная почта; необязательна и не подтверждается.",
        examples=["boris@example.com"],
    )
    phone: str | None = Field(
        None, max_length=32, description="Телефон.", examples=["+79000000000"]
    )
    telegram: str | None = Field(None, max_length=64, description="Telegram.", examples=["@boris"])
    invite_code: str = Field(
        ...,
        min_length=1,
        description="Код приглашения: регистрация закрыта для посторонних.",
        examples=["код-приглашения"],
    )

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """Приводит логин к нижнему регистру, чтобы «Boris» и «boris» не разошлись."""
        return value.lower()


class UserLoginSchema(BaseModel):
    """Тело запроса входа."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "boris", "password": "надёжный-пароль"}}
    )

    username: str = Field(
        ..., min_length=1, max_length=50, description="Логин.", examples=["boris"]
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Пароль.",
        examples=["надёжный-пароль"],
    )


class UserUpdateSchema(BaseModel):
    """Тело запроса обновления профиля."""

    model_config = ConfigDict(json_schema_extra={"example": {"telegram": "@boris"}})

    last_name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Новая фамилия.",
        examples=["Кузнецов"],
    )
    first_name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Новое имя.",
        examples=["Борис"],
    )
    middle_name: str | None = Field(
        None,
        max_length=100,
        description="Новое отчество или null для очистки.",
        examples=["Сергеевич"],
    )
    email: str | None = Field(
        None,
        max_length=255,
        description="Новая почта или null для очистки.",
        examples=["boris@example.com"],
    )
    phone: str | None = Field(
        None,
        max_length=32,
        description="Новый телефон или null для очистки.",
        examples=["+79000000000"],
    )
    telegram: str | None = Field(
        None,
        max_length=64,
        description="Новый Telegram или null для очистки.",
        examples=["@boris"],
    )


class PasswordChangeSchema(PasswordPairMixin):
    """Тело запроса смены пароля."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "старый-пароль",
                "password": "новый-пароль",
                "password_confirm": "новый-пароль",
            }
        }
    )

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Текущий пароль.",
        examples=["старый-пароль"],
    )


class AvatarSchema(BaseModel):
    """Ссылка на загруженную фотографию профиля."""

    content_url: str = Field(
        ...,
        description="Адрес выдачи фотографии.",
        examples=["/api/v1/users/me/avatar"],
    )
