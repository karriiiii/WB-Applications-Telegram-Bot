from typing import List, Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from src.ban_manager import BanManager

class IsAdmin(BaseFilter):
    """
    Кастомный фильтр для проверки, является ли пользователь администратором.
    """
    def __init__(self, admin_ids: List[int]):
        # Сохраняем список ID админов при инициализации фильтра
        self.admin_ids = admin_ids

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        # event.from_user может быть None в некоторых редких случаях (например, channel posts без автора)
        # но для Message и CallbackQuery от реальных пользователей он всегда будет.
        if not event.from_user:
            return False
        return event.from_user.id in self.admin_ids
    
class IsBanned(BaseFilter):
    """
    Кастомный фильтр для проверки, забанен ли пользователь, используя кэш BanManager.
    """
    def __init__(self, inverted: bool = False):
        """
        :param inverted: Если True, фильтр сработает (вернет True), если пользователь ДЕЙСТВИТЕЛЬНО забанен.
                         Если False (по умолчанию), фильтр сработает (вернет True), если пользователь НЕ ЗАБАНЕН.
        """
        self.inverted = inverted

    async def __call__(self, event: Union[Message, CallbackQuery], ban_manager: BanManager) -> bool:
        """
        :param ban_manager: Экземпляр BanManager, инжектированный через middleware или data.
        """
        if not event.from_user:
            # Для системных сообщений без автора, считаем что они "не забанены",
            # чтобы не блокировать их прохождение, если это необходимо.
            # Основные хендлеры все равно обычно ожидают event.from_user.
            return True 
        
        user_id = event.from_user.id
        
        # Проверка бана теперь очень быстрая, из памяти
        user_is_actually_banned = ban_manager.is_banned(user_id)

        if self.inverted:
            # Если inverted=True, мы хотим, чтобы фильтр сработал (вернул True),
            # если пользователь ДЕЙСТВИТЕЛЬНО забанен.
            return user_is_actually_banned
        else:
            # Если inverted=False (по умолчанию), мы хотим, чтобы фильтр сработал (вернул True),
            # если пользователь НЕ забанен (т.е. разрешаем ему доступ).
            return not user_is_actually_banned