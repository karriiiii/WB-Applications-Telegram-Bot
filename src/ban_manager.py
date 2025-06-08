import logging
import aiosqlite
from typing import Set

from src.database import get_banlist, add_to_banlist

logger = logging.getLogger(__name__)

class BanManager:
    def __init__(self):
        self._banned_users_cache: Set[int] = set()
        logger.info("BanManager инициализирован. Кэш пуст.")

    async def load_banned_users_from_db(self):
        """
        Загружает всех забаненных пользователей из базы данных в кэш.
        Вызывается при старте бота.
        """
        banned_ids = await get_banlist()
        self._banned_users_cache = banned_ids
        logger.info(f"Кэш забаненных пользователей загружен из БД. Забанено: {len(self._banned_users_cache)}.")

    async def add_banned_user(self, user_id: int, ban_reason: str) -> bool:
        """
        Добавляет пользователя в банлист (в БД и обновляет кэш).
        Возвращает True, если пользователь был успешно забанен, False если уже был забанен.
        """
        if self.is_banned(user_id): # Проверка по кэшу сначала
            logger.warning(f"Попытка забанить уже забаненного пользователя {user_id}.")
            return False # Уже забанен (согласно кэшу)

        try:
            await add_to_banlist(user_id, ban_reason)
            self._banned_users_cache.add(user_id)
            return True

        except aiosqlite.IntegrityError: # На случай, если кэш был несинхронизирован
            logger.warning(f"Пользователь {user_id} уже находится в банлисте (ошибка БД). Обновляем кэш.")
            self._banned_users_cache.add(user_id)
            return False 

    def is_banned(self, user_id: int) -> bool:
        """
        Проверяет, забанен ли пользователь, используя кэш.
        Это синхронная функция для быстрой проверки в фильтрах.
        """
        return user_id in self._banned_users_cache

