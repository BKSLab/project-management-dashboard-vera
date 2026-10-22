"""Ограничивает сведения об авторе временем одного ASGI-запроса."""

from starlette.types import ASGIApp, Receive, Scope, Send

from src.utils.request_actor import reset_request_actor, set_request_actor


class RequestActorMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        token = set_request_actor(None)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_actor(token)
