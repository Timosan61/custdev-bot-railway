from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from loguru import logger

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        logger.info(
            f"User {user.id} (@{user.username}): "
            f"{event.text[:50]}..." if event.text else f"[{event.content_type}]"
        )
        
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error handling message from {user.id}: {e}")
            await event.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
            raise