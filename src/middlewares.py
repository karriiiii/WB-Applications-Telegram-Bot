from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.ban_manager import BanManager

class AdminChatIdMiddleware(BaseMiddleware):
    def __init__(self, admin_chat_id: int):
        super().__init__()
        self.admin_chat_id_for_notifications = admin_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["admin_chat_id_from_mw"] = self.admin_chat_id_for_notifications
        return await handler(event, data)
    
class BanManagerMiddleware(BaseMiddleware):
    def __init__(self, ban_manager: BanManager):
        super().__init__()
        self.ban_manager = ban_manager

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Добавляем экземпляр BanManager в data
        # Ключ должен совпадать с именем аргумента в хендлерах и фильтрах ('ban_manager')
        data["ban_manager"] = self.ban_manager
        return await handler(event, data)

__all__ = ['AdminChatIdMiddleware', 'BanManagerMiddleware']