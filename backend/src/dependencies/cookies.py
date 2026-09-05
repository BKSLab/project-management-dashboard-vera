"""Политика cookie сессии как явная transport-зависимость.

Настройки cookie — решение транспорта, а не эндпоинта: имя, срок и флаги
безопасности одинаковы для входа и регистрации. Вынесены сюда, чтобы
обработчик не читал конфигурацию приложения сам и чтобы политику можно
было подменить в тесте.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Response

from src.dependencies.settings import SettingsDep


@dataclass(frozen=True, slots=True)
class SessionCookiePolicy:
    """Правила установки и сброса cookie сессии.

    Attributes:
        name: Имя cookie.
        secure: Требовать ли HTTPS.
        max_age_seconds: Срок жизни cookie.
    """

    name: str
    secure: bool
    max_age_seconds: int

    def set(self, response: Response, token: str) -> None:
        """Кладёт токен сессии в httpOnly cookie.

        `SameSite=Lax` закрывает CSRF: браузер не отправит такую cookie
        при кросс-сайтовых POST, PATCH и DELETE, а именно ими идут все
        мутации.

        Args:
            response: HTTP-ответ, в который ставится cookie.
            token: Подписанный токен сессии.
        """
        response.set_cookie(
            key=self.name,
            value=token,
            httponly=True,
            secure=self.secure,
            samesite="lax",
            max_age=self.max_age_seconds,
            path="/",
        )

    def clear(self, response: Response) -> None:
        """Сбрасывает cookie сессии тем же путём, каким она ставилась."""
        response.delete_cookie(key=self.name, path="/")


def get_session_cookie_policy(settings: SettingsDep) -> SessionCookiePolicy:
    """Собирает политику cookie сессии из настроек приложения."""
    return SessionCookiePolicy(
        name=settings.auth.session_cookie_name,
        secure=settings.auth.session_cookie_secure,
        max_age_seconds=settings.auth.access_token_ttl_hours * 3600,
    )


SessionCookiePolicyDep = Annotated[
    SessionCookiePolicy,
    Depends(get_session_cookie_policy),
]
